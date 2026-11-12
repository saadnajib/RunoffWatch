"""
Task 1 - Data quality audit: which simulation results can be trusted?

What the audit found in the project data (see docs/DATA_REPORT.md):

* The pesticide part of many PRZM runs is numerically broken. Pesticide mass is
  created in the deep soil and, in part of the runs, reaches the surface, where
  it produces impossible runoff losses (up to 1e34 g/ha for 2400 g/ha applied).
* The water part (rain -> runoff) is not affected.

So quality is decided per run AND per year:

    hydrology   usable for every readable run
    pesticide   usable only up to `clean_until` (a date per run)

How `clean_until` is found ("envelope rule"):

1. loss_per_mm = pesticide lost / mm of runoff water on a runoff day. In a
   healthy run it falls steadily with the days since spraying (the pesticide
   decays), so it has an upper limit for each "days since spraying".
2. That limit (the envelope) is learned from the first application year, 1990,
   before the fake mass has had time to reach the surface: the 99th percentile
   per 15-day bin, forced to be non-increasing, times a safety factor.
3. The first day a run goes above the envelope marks its first bad application
   year (application years run 1 March - end of February).
4. Guard: the application year before the first bad one is dropped too, and the
   last simulated application year is never trusted, because contamination
   grows gradually and a year can only be confirmed by a clean following year.

An Isolation Forest (unsupervised ML) is run on per-run summary features as an
independent second opinion, and a gradient-boosted classifier shows which run
settings predict the breakdown (to report back to the model owners).
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import numpy as np
import pandas as pd

from .przm_inp import InpFormatError, parse_inp
from .przm_io import read_soil_decay

log = logging.getLogger("runoffwatch")

BIN_DAYS = 15
ENVELOPE_QUANTILE = 0.99
ENVELOPE_FACTOR = 5.0
GUARD_YEARS = 1
CLEARLY_BROKEN_FACTOR = 50.0   # for reporting only: runs this far above the reference are beyond doubt
APP_MONTH = 3            # application years start on 1 March in this data set


# --------------------------------------------------------------------------- #
# Folder status
# --------------------------------------------------------------------------- #
def folder_status(runs_root: str | Path) -> pd.DataFrame:
    """Classify every run folder by what it contains.

    no_field      only mc.log: PRZM was never started for this grid cell
    no_output     inputs exist but no result files were kept
    empty_output  result file exists but holds no data rows
    has_output    result file with data
    """
    rows = []
    for batch in sorted(p for p in Path(runs_root).iterdir() if p.is_dir()):
        for run in sorted(p for p in batch.iterdir() if p.is_dir()):
            sfx = {p.suffix.lower(): p for p in run.iterdir() if p.is_file()}
            if ".zts" in sfx:
                status = "has_output" if sfx[".zts"].stat().st_size > 400 else "empty_output"
            elif ".inp" in sfx or ".met" in sfx:
                status = "no_output"
            else:
                status = "no_field"
            rows.append({"run": run.name, "batch": batch.name, "status": status})
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------- #
# Envelope rule
# --------------------------------------------------------------------------- #
def app_year(dates: pd.DatetimeIndex | pd.Series) -> np.ndarray:
    """Application year of each date (1 March 1990 - 28 Feb 1991 -> 1990)."""
    d = pd.DatetimeIndex(dates)
    return (d.year - (d.month < APP_MONTH)).to_numpy()


def load_events(daily_dir: str | Path) -> pd.DataFrame:
    """All runoff days of all runs (one row per run and day with runoff > 0)."""
    parts = []
    for f in sorted(Path(daily_dir).glob("*.parquet")):
        d = pd.read_parquet(f, columns=["rain_mm", "runoff_mm", "pest_runoff_gha", "days_since_app"])
        d = d[d["runoff_mm"] > 0]
        parts.append(d.assign(run=f.stem, date=d.index).reset_index(drop=True))
    ev = pd.concat(parts, ignore_index=True)
    ev["app_year"] = app_year(ev["date"])
    ev["loss_per_mm"] = ev["pest_runoff_gha"] / ev["runoff_mm"]
    return ev


def fit_envelope(events: pd.DataFrame, ref_app_year: int | None = None) -> pd.Series:
    """Upper limit of loss_per_mm per 15-day bin of days-since-spraying.

    Index = bin number (days_since_app // 15), values = limit in g/ha per mm.
    """
    ev = events[events["days_since_app"].notna() & (events["pest_runoff_gha"] > 0)]
    ref = int(ev["app_year"].min()) if ref_app_year is None else ref_app_year
    ev = ev[ev["app_year"] == ref]
    if ev.empty:
        raise ValueError("no runoff events in the reference application year")
    b = (ev["days_since_app"] // BIN_DAYS).astype(int)
    q = ev.groupby(b)["loss_per_mm"].quantile(ENVELOPE_QUANTILE)
    q = q.reindex(range(0, 366 // BIN_DAYS + 1)).interpolate().ffill().bfill()
    env = q.cummin() * ENVELOPE_FACTOR
    env.index.name = "dsa_bin"
    return env.rename("limit_g_per_ha_per_mm")


def envelope_limit(days_since_app, envelope: pd.Series) -> np.ndarray:
    b = (np.asarray(days_since_app, dtype=float) // BIN_DAYS)
    b = np.clip(np.nan_to_num(b, nan=0), 0, envelope.index.max()).astype(int)
    return envelope.to_numpy()[b]


def clean_until_dates(events: pd.DataFrame, envelope: pd.Series, last_app_year: pd.Series) -> pd.DataFrame:
    """Per run: first bad application year and the date up to which pesticide results are trusted.

    last_app_year: per run, the last application year that was simulated.
    """
    ev = events[events["days_since_app"].notna()]
    exceed = ev[ev["loss_per_mm"] > envelope_limit(ev["days_since_app"], envelope)]
    first_bad = exceed.groupby("run")["app_year"].min()
    out = pd.DataFrame({"last_app_year": last_app_year})
    out["first_bad_app_year"] = first_bad.reindex(out.index)
    # trusted years end GUARD_YEARS before the first bad one; with no bad year, before the last (unverifiable) one
    end_year = out["first_bad_app_year"].fillna(out["last_app_year"] + 1) - GUARD_YEARS
    out["clean_until"] = pd.to_datetime(dict(year=end_year.astype(int), month=APP_MONTH, day=1))
    return out


# --------------------------------------------------------------------------- #
# Run-level table
# --------------------------------------------------------------------------- #
def run_parameters(runs: list[Path]) -> pd.DataFrame:
    rows = []
    for r in runs:
        inp = [p for p in r.iterdir() if p.suffix.lower() == ".inp"]
        try:
            rows.append({"run": r.name, **parse_inp(inp[0])})
        except (InpFormatError, IndexError):
            continue
    return pd.DataFrame(rows).set_index("run")


def soil_decay_table(runs: list[Path]) -> pd.DataFrame:
    """Yearly 'total soil decay' per run (columns = year number 0, 1, ...)."""
    rows = {}
    for r in runs:
        out = [p for p in r.iterdir() if p.suffix.lower() == ".out"]
        if out:
            rows[r.name] = read_soil_decay(out[0])
    return pd.DataFrame.from_dict(rows, orient="index")


def build_run_quality(runs_root: str | Path, interim: str | Path):
    """Combine everything into one row per run. Needs `qc` and `inventory` output in `interim`.

    Returns (run_quality, envelope, events, yearly soil decay).
    """
    from .batch import find_runs

    interim = Path(interim)
    qc = pd.read_csv(interim / "runs_qc.csv").set_index("run")
    inv = pd.read_csv(interim / "inventory_runs.csv").set_index("run")
    status = folder_status(runs_root).set_index("run")
    runs = find_runs(runs_root)

    events = load_events(interim / "daily")
    envelope = fit_envelope(events)

    ok = qc[qc["read_ok"]].copy()
    ok["end"] = pd.to_datetime(ok["end"])
    last_app_year = pd.Series(app_year(ok["end"]), index=ok.index)
    cu = clean_until_dates(events, envelope, last_app_year)

    decay = soil_decay_table(runs)
    first, last = decay.iloc[:, 0], decay.ffill(axis=1).iloc[:, -1]
    n_years = decay.notna().sum(axis=1)

    rq = status.join(ok[["n_days", "end", "unstable", "max_decay_growth", "loss_total_gha",
                         "applied_total_gha", "runoff_days", "rain_total_mm"]])
    rq = rq.join(cu).join(inv[["met_hash"]])
    rq["crashed"] = rq["n_days"] < rq["n_days"].max()
    rq["decay_growth_per_year"] = (last / first).reindex(rq.index) ** (1 / (n_years.reindex(rq.index) - 1).clip(lower=1))
    rq["loss_fraction"] = rq["loss_total_gha"] / rq["applied_total_gha"]
    late = events[events["days_since_app"] > 150].groupby("run")["loss_per_mm"].max()
    rq["max_late_loss_per_mm"] = late.reindex(rq.index)
    # how far above the reference-year 99th percentile the run ever gets (the rule flags at ENVELOPE_FACTOR)
    ev = events[events["days_since_app"].notna()]
    ratio = ev["loss_per_mm"] / (envelope_limit(ev["days_since_app"], envelope) / ENVELOPE_FACTOR)
    rq["worst_ratio_to_reference"] = ratio.groupby(ev["run"]).max().reindex(rq.index)
    # pesticide results start with the first spraying, so years are counted from then
    first_app = pd.Timestamp(year=int(events["date"].dt.year.min()), month=APP_MONTH, day=1)
    rq["clean_years"] = ((rq["clean_until"] - first_app).dt.days / 365.25).clip(lower=0).round(2)
    rq["pesticide_years"] = ((pd.to_datetime(rq["end"]) - first_app).dt.days / 365.25).clip(lower=0).round(2)
    rq = rq.join(run_parameters(runs))
    return rq, envelope, events, decay


# --------------------------------------------------------------------------- #
# ML second opinion and drivers
# --------------------------------------------------------------------------- #
ANOMALY_FEATURES = ["decay_growth_per_year", "loss_fraction", "max_late_loss_per_mm", "max_decay_growth"]


def isolation_forest_flags(rq: pd.DataFrame, contamination: float | str = "auto", seed: int = 0) -> pd.Series:
    """Unsupervised anomaly flag per run (True = anomalous), on log-scaled summary features."""
    from sklearn.ensemble import IsolationForest

    X = np.log10(rq[ANOMALY_FEATURES].astype(float).clip(lower=1e-12)).dropna()
    model = IsolationForest(n_estimators=300, contamination=contamination, random_state=seed).fit(X)
    return pd.Series(model.predict(X) == -1, index=X.index, name="iforest_anomaly")


def instability_drivers(rq: pd.DataFrame, seed: int = 0) -> dict:
    """Which run settings predict that pesticide results break? (cross-validated AUC + importance)"""
    import lightgbm as lgb
    from sklearn.model_selection import cross_val_score

    d = rq[rq["clean_until"].notna() & rq["usle_k"].notna()]
    y = d["first_bad_app_year"].notna().astype(int)
    X = d[[c for c in d.columns if c.startswith(("h1_", "h3_", "usle_", "slope", "cn_2"))]]
    X = X.loc[:, X.nunique() > 1].assign(rain_mm_per_year=d["rain_total_mm"] / (d["n_days"] / 365.25))
    model = lgb.LGBMClassifier(n_estimators=200, learning_rate=0.05, num_leaves=15, verbose=-1, random_state=seed)
    auc = cross_val_score(model, X, y, cv=5, scoring="roc_auc")
    model.fit(X, y)
    gain = pd.Series(model.booster_.feature_importance("gain"), X.columns)
    return {"cv_auc_mean": float(auc.mean()), "share_bad": float(y.mean()),
            "importance": (gain / gain.sum()).sort_values(ascending=False).round(3).head(8).to_dict()}


# --------------------------------------------------------------------------- #
# Driver
# --------------------------------------------------------------------------- #
def audit(runs_root: str | Path = "data/raw/runs", interim: str | Path = "data/interim",
          results: str | Path = "docs/results", figures: str | Path = "docs/figures") -> dict:
    """Run the whole audit; write run_quality.csv, envelope.csv, a JSON summary and figures."""
    interim, results = Path(interim), Path(results)
    results.mkdir(parents=True, exist_ok=True)
    rq, envelope, events, decay = build_run_quality(runs_root, interim)

    has = rq[rq["status"] == "has_output"]
    readable = has[has["n_days"].notna()].copy()
    iso = isolation_forest_flags(readable)
    rq["iforest_anomaly"] = iso.reindex(rq.index)
    readable["iforest_anomaly"] = iso.reindex(readable.index)

    rule_bad = readable["first_bad_app_year"].notna()
    both = readable["iforest_anomaly"].fillna(False).astype(bool)
    n_years_total = (readable["n_days"].max() / 365.25)
    worst = readable["worst_ratio_to_reference"].fillna(0)
    clearly = worst >= CLEARLY_BROKEN_FACTOR
    sub = readable[readable["h3_oc"].notna()]
    oc_bins = pd.cut(sub["h3_oc"], [-0.01, 0.3, 0.4, 0.5, 1.0, 100])
    by_oc = pd.DataFrame({
        "runs": sub.groupby(oc_bins, observed=False).size(),
        "share_flagged": sub["first_bad_app_year"].notna().groupby(oc_bins, observed=False).mean(),
        "share_clearly_broken": (sub["worst_ratio_to_reference"].fillna(0) >= CLEARLY_BROKEN_FACTOR)
        .groupby(oc_bins, observed=False).mean()})

    summary = {
        "folders": int(len(rq)),
        "status_counts": rq["status"].value_counts().to_dict(),
        "readable_runs": int(len(readable)),
        "distinct_weather_files": int(readable["met_hash"].nunique()),
        "crashed_before_end": int(readable["crashed"].sum()),
        "decay_rule_unstable": int(readable["unstable"].sum()),
        "envelope_rule_bad_runs": int(rule_bad.sum()),
        "runs_never_above_envelope": int((~rule_bad).sum()),
        # the flag count depends on the safety factor: there is no sharp gap between healthy and broken
        "flagged_runs_by_factor": {str(f): int((worst > f).sum()) for f in (5, 10, 50, 1000)},
        "clearly_broken_runs": int(clearly.sum()),
        "clearly_broken_factor": CLEARLY_BROKEN_FACTOR,
        "first_bad_app_year_counts": {int(k): int(v) for k, v in
                                      readable["first_bad_app_year"].value_counts().sort_index().items()},
        "median_decay_growth_per_year": float(readable["decay_growth_per_year"].median()),
        "share_runs_decay_growing_gt_1p5": float((readable["decay_growth_per_year"] > 1.5).mean()),
        "max_loss_fraction_of_applied": float(readable["loss_fraction"].max()),
        "clean_run_years": float(readable["clean_years"].sum()),
        "total_run_years": float(readable["pesticide_years"].sum()),
        "runs_with_at_least_3_clean_years": int((readable["clean_years"] >= 3).sum()),
        "full_length_years": float(n_years_total),
        "iforest_flagged": int(both.sum()),
        "iforest_agrees_with_decay_rule": float((both == readable["unstable"].astype(bool)).mean()),
        "iforest_recall_of_decay_rule": float(both[readable["unstable"].astype(bool)].mean()),
        "iforest_recall_of_envelope_flagged": float(both[rule_bad].mean()),
        "iforest_recall_of_clearly_broken": float(both[clearly].mean()),
        "bad_share_by_subsoil_oc": {str(k): {"runs": int(v["runs"]), "share_flagged": round(float(v["share_flagged"]), 3),
                                             "share_clearly_broken": round(float(v["share_clearly_broken"]), 3)}
                                    for k, v in by_oc.iterrows()},
        "drivers": instability_drivers(readable),
        "envelope": {"quantile": ENVELOPE_QUANTILE, "factor": ENVELOPE_FACTOR,
                     "bin_days": BIN_DAYS, "guard_years": GUARD_YEARS},
    }

    rq.to_csv(interim / "run_quality.csv")
    envelope.to_csv(results / "envelope.csv")
    (results / "quality_summary.json").write_text(json.dumps(summary, indent=2, default=str))

    from .figures import quality_figures
    quality_figures(rq, envelope, events, decay, Path(figures))
    log.info("audit: %d folders, %d readable runs, %d with bad pesticide years, %.0f of %.0f run-years clean",
             summary["folders"], summary["readable_runs"], summary["envelope_rule_bad_runs"],
             summary["clean_run_years"], summary["total_run_years"])
    return summary

