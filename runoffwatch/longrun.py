"""
Run the surrogate on 46 years of real weather (Agri4Cast, France, 1979-2024).

Every simulated field gets the full weather record of its own Agri4Cast grid
cell, a spraying on 1 March of every year, and the surrogate's prediction of
daily runoff and pesticide loss. PRZM itself is not run.

Two facts this module rests on (both checked against the data):

* The weather in the PRZM runs is labelled 1990-1999 but is the real weather of
  2006-2015: every value equals the Agri4Cast record shifted by 16 years
  (`YEAR_SHIFT`). So "application year 1994" in the other reports is really 2010.
* PRZM's "pan evaporation" in the runs equals the ET0 column of the weather file.

What the result is and is not: for 2006-2015 the surrogate was trained on these
very years, so agreement with PRZM there is not a test. For 1979-2005 and
2016-2024 there is no PRZM result to compare with: the numbers are predictions
of what PRZM would say, with the accuracy estimated by the leave-one-year-out
test (models.yearly_cv). Everything still assumes Flufenacet, 2.4 kg/ha, on
winter cereals, sprayed on 1 March.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import numpy as np
import pandas as pd

from .features import DEFAULT_RATE_KGHA, HIGH_LOSS_GHA, MIN_RAIN_MM, field_of, weather_features
from .models import conc_per_mm, load_models
from .przm_inp import SOIL_FEATURES
from .quality import app_year

log = logging.getLogger("runoffwatch")

YEAR_SHIFT = 16                     # label year in the PRZM runs + 16 = real year
TRAIN_YEARS = (2006, 2015)          # real years covered by the PRZM runs
WEATHER_COLUMNS = {"PRECIPITATION": "rain_mm", "TEMPERATURE_AVG": "temp_c", "ET0": "pan_evap_mm"}


def load_weather(path: str | Path) -> pd.DataFrame:
    """Read the Agri4Cast table (CSV with `;` or the parquet copy) sorted by grid cell and date."""
    path = Path(path)
    if path.suffix == ".parquet":
        w = pd.read_parquet(path)
    else:
        w = pd.read_csv(path, sep=";")
        w["date"] = pd.to_datetime(w["DAY"].astype(str), format="%Y%m%d")
        w = w.drop(columns="DAY")
    need = {"GRID_NO", "date", "LATITUDE", "LONGITUDE", *WEATHER_COLUMNS}
    if not need <= set(w.columns):
        raise ValueError(f"weather table needs columns {sorted(need)}")
    return w.sort_values(["GRID_NO", "date"]).reset_index(drop=True)


def grid_of(run_name: str) -> int:
    """Agri4Cast grid number from a run folder name (run_0000140_grid_086080 -> 86080)."""
    return int(field_of(run_name).rsplit("grid_", 1)[1])


def check_shift(weather: pd.DataFrame, daily_dir: str | Path, runs: list[str]) -> dict:
    """Confirm that the run weather equals the real weather shifted by YEAR_SHIFT years."""
    worst = {"rain_mm": 0.0, "temp_c": 0.0, "pan_evap_mm": 0.0}
    for run in runs:
        d = pd.read_parquet(Path(daily_dir) / f"{run}.parquet", columns=list(worst))
        g = weather[weather["GRID_NO"] == grid_of(run)].set_index("date").rename(columns=WEATHER_COLUMNS)
        real = g.loc[f"{d.index[0].year + YEAR_SHIFT}-01-01":].iloc[: len(d)]
        for c in worst:
            worst[c] = max(worst[c], float(np.abs(real[c].to_numpy() - d[c].to_numpy()).max()))
    return {"runs_checked": len(runs), "max_abs_difference": worst, "matches": max(worst.values()) < 1e-3}


def predict_fields(weather: pd.DataFrame, fields: pd.DataFrame, models: dict, app_day: int = 1, app_month: int = 3,
                   rate_kgha: float = DEFAULT_RATE_KGHA) -> pd.DataFrame:
    """One row per field and application year: rain, predicted runoff, predicted loss, high-loss days.

    fields: index = run name; columns = SOIL_FEATURES, cn_1..cn_4.
    app_day, app_month, rate_kgha: every field is sprayed on this day of every year with this dose.
    An "application year" runs from one spraying to the day before the next.
    """
    try:
        pd.Timestamp(year=2001, month=app_month, day=app_day)
    except ValueError:
        raise ValueError(f"day {app_day}, month {app_month} is not a date that exists every year") from None
    if not (np.isfinite(rate_kgha) and rate_kgha > 0):
        raise ValueError("the dose must be a number above zero")
    meta = models["meta"]
    fields = fields.assign(grid=[grid_of(r) for r in fields.index])
    by_grid = {g: d.set_index("date").rename(columns=WEATHER_COLUMNS) for g, d in weather.groupby("GRID_NO")}
    out = []
    groups = fields.groupby(["grid", "cn_1", "cn_2", "cn_3", "cn_4"])
    for i, ((grid, *cn), members) in enumerate(groups, start=1):
        daily = by_grid[grid]
        years = range(daily.index[0].year, daily.index[-1].year + 1)
        apps = [pd.Timestamp(year=y, month=app_month, day=app_day) for y in years]
        f = weather_features(daily[["rain_mm", "temp_c", "pan_evap_mm"]], apps, tuple(cn), rate_kgha)
        f = f[(f["rain_mm"] >= MIN_RAIN_MM) & f["days_since_app"].notna()]
        season = pd.Series(daily.index.year, index=daily.index).where(daily.index.isin(apps)).ffill()
        ay = season.reindex(f.index).to_numpy(dtype=int)
        rain_by_year = daily["rain_mm"].groupby(season).sum()
        n = len(f)
        X = pd.concat([f] * len(members), ignore_index=True)
        for c in SOIL_FEATURES:
            X[c] = np.repeat(members[c].to_numpy(dtype=float), n)
        runoff = models["runoff"].predict(X[meta["runoff_features"]])
        loss = runoff * conc_per_mm(meta, models["conc"].predict(X[meta["conc_features"]]), rate_kgha)
        res = pd.DataFrame({"run": np.repeat(members.index.to_numpy(), n), "app_year": np.tile(ay, len(members)),
                            "runoff_mm": runoff, "loss_gha": loss, "high_loss_days": loss >= HIGH_LOSS_GHA,
                            "max_day_loss_gha": loss, "max_rain_mm": np.tile(f["rain_mm"].to_numpy(), len(members))})
        agg = res.groupby(["run", "app_year"], sort=False).agg(
            runoff_mm=("runoff_mm", "sum"), loss_gha=("loss_gha", "sum"), high_loss_days=("high_loss_days", "sum"),
            max_day_loss_gha=("max_day_loss_gha", "max"), max_rain_mm=("max_rain_mm", "max")).reset_index()
        agg["grid"] = grid
        agg["rain_mm"] = agg["app_year"].map(rain_by_year).to_numpy()
        out.append(agg)
        if i % 500 == 0 or i == groups.ngroups:
            log.info("long run: %d / %d weather-and-curve-number groups", i, groups.ngroups)
    return pd.concat(out, ignore_index=True)


def przm_field_years(features_path: str | Path) -> pd.DataFrame:
    """PRZM's own yearly totals for the trusted run-years, with real years (for the consistency check)."""
    t = pd.read_parquet(features_path, columns=["run", "date", "runoff_mm", "loss_gha", "pest_clean", "days_since_app"])
    t = t[t["days_since_app"].notna()]
    t["app_year"] = app_year(pd.DatetimeIndex(t["date"])) + YEAR_SHIFT
    g = t.groupby(["run", "app_year"], observed=True)
    out = g.agg(runoff_przm=("runoff_mm", "sum"), loss_przm=("loss_gha", "sum"), clean=("pest_clean", "all")).reset_index()
    out["run"] = out["run"].astype(str)
    return out


def run_france(weather_path: str | Path = "data/raw/france_weather/france_weather.parquet",
               interim: str | Path = "data/interim", features_path: str | Path = "data/processed/features.parquet",
               model_dir: str | Path = "models", out_path: str | Path = "data/processed/france_field_years.parquet",
               results: str | Path = "docs/results", figures: str | Path = "docs/figures",
               limit: int | None = None, app_day: int = 1, app_month: int = 3,
               rate_kgha: float = DEFAULT_RATE_KGHA) -> dict:
    """Predict every field for every year of the weather table.

    app_day, app_month, rate_kgha: the spraying that is assumed for every field and year. The
    comparison with PRZM's own totals is only made for the delivered spraying (1 March, 2.4 kg/ha),
    because that is what the PRZM runs in `interim` were sprayed with.
    """
    from sklearn.metrics import r2_score

    interim, results = Path(interim), Path(results)
    weather = load_weather(weather_path)
    models = load_models(model_dir)
    rq = pd.read_csv(interim / "run_quality.csv", index_col="run", low_memory=False)
    fields = rq[rq["clean_until"].notna() & rq["usle_k"].notna()][SOIL_FEATURES + [f"cn_{k}" for k in (1, 3, 4)]]
    fields = fields[~pd.Index([field_of(r) for r in fields.index]).duplicated()]      # one run per field
    fields = fields.iloc[:limit]
    have = set(weather["GRID_NO"].unique())
    missing = [r for r in fields.index if grid_of(r) not in have]
    if missing:
        log.warning("%d fields have no weather in the table and are skipped", len(missing))
        fields = fields.drop(index=missing)

    shift = check_shift(weather, interim / "daily", list(fields.index[:: max(1, len(fields) // 25)]))
    if not shift["matches"]:
        raise ValueError(f"run weather does not equal the weather table shifted by {YEAR_SHIFT} years: {shift}")

    fy = predict_fields(weather, fields, models, app_day, app_month, rate_kgha)
    last_full = int(weather["date"].max().year) - 1          # the last spraying has no full year after it
    fy = fy[fy["app_year"] <= last_full]
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    fy.to_parquet(out_path, index=False)

    period = np.select([fy["app_year"] < TRAIN_YEARS[0], fy["app_year"] <= TRAIN_YEARS[1]],
                       ["before (1979-2005)", "training years (2006-2015)"], "after (2016-2023)")
    fy["period"] = period
    by_year = fy.groupby("app_year").agg(
        fields=("run", "nunique"), rain_mm_median=("rain_mm", "median"), runoff_mm_median=("runoff_mm", "median"),
        loss_gha_median=("loss_gha", "median"), loss_gha_p10=("loss_gha", lambda s: s.quantile(0.1)),
        loss_gha_p90=("loss_gha", lambda s: s.quantile(0.9)), loss_gha_mean=("loss_gha", "mean"),
        high_loss_days_per_field=("high_loss_days", "mean"),
        fields_with_high_loss_day_pct=("high_loss_days", lambda s: 100 * (s > 0).mean()))
    coords = weather.groupby("GRID_NO")[["LATITUDE", "LONGITUDE", "ALTITUDE"]].first()
    by_grid = fy.groupby("grid").agg(fields=("run", "nunique"), loss_gha_per_year=("loss_gha", "mean"),
                                     runoff_mm_per_year=("runoff_mm", "mean"), rain_mm_per_year=("rain_mm", "mean"),
                                     high_loss_days_per_year=("high_loss_days", "mean")).join(coords)
    by_period = fy.groupby("period").agg(years=("app_year", "nunique"), loss_gha_mean=("loss_gha", "mean"),
                                         loss_gha_median=("loss_gha", "median"), runoff_mm_mean=("runoff_mm", "mean"),
                                         rain_mm_mean=("rain_mm", "mean"),
                                         high_loss_days_per_field_year=("high_loss_days", "mean"),
                                         max_rain_mm=("max_rain_mm", "max"))

    # consistency with PRZM on the years it simulated (NOT a test: the final models were trained on these)
    delivered_spraying = (app_day, app_month) == (1, 3) and abs(rate_kgha - DEFAULT_RATE_KGHA) < 1e-9
    consistency = None
    if delivered_spraying:
        pz = przm_field_years(features_path).merge(fy, on=["run", "app_year"], how="inner")
        clean = pz[pz["clean"]]
        consistency = {"field_years": int(len(pz)), "field_years_trusted_pesticide": int(len(clean)),
                       "runoff_r2_yearly": float(r2_score(pz["runoff_przm"], pz["runoff_mm"])),
                       "loss_r2_yearly": float(r2_score(clean["loss_przm"], clean["loss_gha"])),
                       "loss_sum_ratio": float(clean["loss_gha"].sum() / clean["loss_przm"].sum())}

    train_max_rain = float(models["meta"]["trained_on"]["feature_ranges"]["rain_mm"][1])
    yearly_total = fy.groupby("app_year")["loss_gha"].mean()
    summary = {
        "weather": {"grid_cells_in_table": int(weather["GRID_NO"].nunique()), "first_day": str(weather["date"].min().date()),
                    "last_day": str(weather["date"].max().date())},
        "year_shift_check": shift, "year_shift": YEAR_SHIFT,
        "fields": int(fy["run"].nunique()), "grid_cells_used": int(fy["grid"].nunique()),
        "spraying": {"day": app_day, "month": app_month, "rate_kgha": rate_kgha},
        "application_years": [int(fy["app_year"].min()), int(fy["app_year"].max())],
        "field_years": int(len(fy)),
        "by_period": json.loads(by_period.round(4).to_json(orient="index")),
        "worst_years_by_mean_loss": {int(k): round(float(v), 3) for k, v in yearly_total.nlargest(5).items()},
        "best_years_by_mean_loss": {int(k): round(float(v), 3) for k, v in yearly_total.nsmallest(5).items()},
        "ratio_worst_to_median_year": float(yearly_total.max() / yearly_total.median()),
        "share_of_all_loss_in_worst_5_years": float(yearly_total.nlargest(5).sum() / yearly_total.sum()),
        "field_years_with_a_rain_day_heavier_than_99.9pct_of_training_rain_days_pct":
            float(100 * (fy["max_rain_mm"] > train_max_rain).mean()),
        "training_rain_99.9pct_mm": train_max_rain,
        "consistency_with_przm_2006_2015_not_a_test": consistency,
    }
    results.mkdir(parents=True, exist_ok=True)
    by_year.round(4).to_csv(results / "france_by_year.csv")
    by_grid.round(4).to_csv(results / "france_by_grid.csv")
    (results / "france_summary.json").write_text(json.dumps(summary, indent=2))
    from .figures import france_figures
    france_figures(by_year, by_grid, Path(figures))
    return summary
