"""
Tasks 2 and 3 - the models.

Surrogate of PRZM (Task 3), built in two physically meaningful stages:

    runoff model   daily weather + soil            -> mm of water running off        (hydrology)
    conc model     history since spraying + soil   -> g/ha of pesticide per mm runoff (chemistry)
    pesticide loss = runoff x concentration

The runoff model is trained on every readable run (the water side of PRZM is
sound). The conc model is trained only on rows whose pesticide results passed
the quality audit.

High-loss classifier (Task 2): is today a day with >= 1 g/ha pesticide loss?
Compared against a rain-threshold rule, logistic regression and the surrogate.

Honest evaluation: the test set holds weather files AND years that training never
saw (see `split_rows`). A split by row or by run would leak, because many runs
share one weather file and neighbouring weather files share the same storms.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, precision_recall_curve, r2_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from .features import (CLASSIFIER_FEATURES, CONC_FEATURES, HIGH_LOSS_GHA, RUNOFF_FEATURES,
                       curve_number_runoff)  # noqa: F401  (re-exported)

log = logging.getLogger("runoffwatch")

CONC_FLOOR = 1e-7          # g/ha per mm; below this the pesticide loss is zero for all purposes
MODEL_FILES = {"runoff": "runoff.txt", "conc": "conc.txt", "high_loss": "high_loss.txt"}


# --------------------------------------------------------------------------- #
# Split
# --------------------------------------------------------------------------- #
def split_by_weather(met_hash: pd.Series) -> pd.Series:
    """'train' / 'val' / 'test' per row, decided by the weather file (70 / 10 / 20 %)."""
    codes = met_hash.astype(str)
    bucket = codes.map({h: int(h, 16) % 10 for h in codes.unique()})
    return pd.Series(np.select([bucket < 2, bucket == 2], ["test", "val"], "train"), index=met_hash.index)


TEST_APP_YEARS = (1992, 1996)      # application years (1 March - end of February) kept out of training
VAL_APP_YEARS = (1994,)
SPLITS = ("train", "val", "test", "test_seen_years", "unused")


def split_rows(met_hash: pd.Series, dates: pd.Series) -> pd.Series:
    """Split by weather file AND by application year.

    Why both: the 695 weather files are neighbouring grid cells of the same decade, so a
    test file nearly always has a twin in the training files with the same storms on the
    same days (daily-rain correlation > 0.9). Holding out whole years as well makes the
    test storms truly unseen.

        train            training files, training years
        val              non-test files, validation year (unseen year; used for early stopping)
        test             test files, test years            <- the honest score
        test_seen_years  test files, training years        <- easier, for comparison
        unused           the rest
    """
    from .quality import app_year

    files = split_by_weather(met_hash).to_numpy()
    year = app_year(pd.DatetimeIndex(dates))
    y_test, y_val = np.isin(year, TEST_APP_YEARS), np.isin(year, VAL_APP_YEARS)
    y_train = ~y_test & ~y_val
    label = np.select(
        [(files == "train") & y_train, (files != "test") & y_val, (files == "test") & y_test, (files == "test") & y_train],
        ["train", "val", "test", "test_seen_years"], "unused")
    return pd.Series(label, index=met_hash.index)


# --------------------------------------------------------------------------- #
# Baselines
# --------------------------------------------------------------------------- #
def fit_decay_baseline(runoff_mm, days_since_app, loss_gha) -> tuple[float, float]:
    """loss = a * runoff * exp(-k * days_since_app): straight line in log space on runoff days."""
    m = (runoff_mm > 0) & (loss_gha > 0) & np.isfinite(days_since_app)
    slope, intercept = np.polyfit(days_since_app[m], np.log(loss_gha[m] / runoff_mm[m]), 1)
    return float(np.exp(intercept)), float(-slope)


# --------------------------------------------------------------------------- #
# Training
# --------------------------------------------------------------------------- #
def _fit(params: dict, Xtr, ytr, Xva, yva, rounds: int, patience: int = 40) -> lgb.Booster:
    dtr = lgb.Dataset(Xtr, ytr, free_raw_data=False)
    dva = lgb.Dataset(Xva, yva, reference=dtr)
    # Small trees on purpose: millions of rows, but only ten years of regional weather behind them.
    base = {"learning_rate": 0.05, "num_leaves": 15, "min_data_in_leaf": 100, "feature_fraction": 0.8,
            "bagging_fraction": 0.8, "bagging_freq": 1, "verbose": -1, "seed": 0}
    return lgb.train({**base, **params}, dtr, num_boost_round=rounds, valid_sets=[dva],
                     callbacks=[lgb.early_stopping(patience, verbose=False)])


def _conc_rows(d: pd.DataFrame) -> pd.DataFrame:
    return d[d["pest_clean"] & (d["runoff_mm"] > 0)]


def _log_conc(d: pd.DataFrame) -> np.ndarray:
    return np.log10((d["loss_gha"] / d["runoff_mm"]).clip(lower=CONC_FLOOR))


def train_all(features_path: str | Path = "data/processed/features.parquet", model_dir: str | Path = "models",
              results: str | Path = "docs/results", figures: str | Path = "docs/figures",
              rounds: int = 1500) -> dict:
    """Train the three models, evaluate them on held-out weather files AND held-out years, save everything."""
    t = pd.read_parquet(features_path)
    t["split"] = split_rows(t["met_hash"], t["date"])
    tr, va = t[t["split"] == "train"], t[t["split"] == "val"]
    model_dir, results = Path(model_dir), Path(results)
    model_dir.mkdir(parents=True, exist_ok=True); results.mkdir(parents=True, exist_ok=True)
    count = lambda col: {s: int(t.loc[t["split"] == s, col].nunique()) for s in SPLITS}  # noqa: E731
    metrics: dict = {"split": {"test_app_years": list(TEST_APP_YEARS), "val_app_years": list(VAL_APP_YEARS),
                               "rows": t["split"].value_counts().to_dict(),
                               "weather_files": count("met_hash"), "runs": count("run")},
                     "high_loss_threshold_gha": HIGH_LOSS_GHA}

    # ---------------- Stage 1: runoff (water) --------------------------------
    log.info("training runoff model on %d rows", len(tr))
    runoff = _fit({"objective": "tweedie", "tweedie_variance_power": 1.2, "metric": "rmse",
                   "min_data_in_leaf": min(2000, max(20, len(tr) // 200))},
                  tr[RUNOFF_FEATURES], tr["runoff_mm"], va[RUNOFF_FEATURES], va["runoff_mm"], rounds)
    runoff.save_model(model_dir / MODEL_FILES["runoff"])

    # ---------------- Stage 2: pesticide per mm of runoff --------------------
    ctr, cva = _conc_rows(tr), _conc_rows(va)
    log.info("training concentration model on %d rows", len(ctr))
    conc = _fit({"objective": "regression", "metric": "rmse", "num_leaves": 31,
                 "min_data_in_leaf": min(200, max(20, len(ctr) // 200))},
                ctr[CONC_FEATURES], _log_conc(ctr), cva[CONC_FEATURES], _log_conc(cva), rounds)
    conc.save_model(model_dir / MODEL_FILES["conc"])
    a, k = fit_decay_baseline(ctr["runoff_mm"].to_numpy(), ctr["days_since_app"].to_numpy(), ctr["loss_gha"].to_numpy())

    # ---------------- Task 2: high-loss classifier ---------------------------
    cl_tr, cl_va = tr[tr["pest_clean"]], va[va["pest_clean"]]
    log.info("training high-loss classifier on %d rows (%d positives)", len(cl_tr), int(cl_tr["high_loss"].sum()))
    clf = _fit({"objective": "binary", "metric": "binary_logloss", "learning_rate": 0.03},
               cl_tr[CLASSIFIER_FEATURES], cl_tr["high_loss"].astype(int),
               cl_va[CLASSIFIER_FEATURES], cl_va["high_loss"].astype(int), rounds, patience=100)
    clf.save_model(model_dir / MODEL_FILES["high_loss"])
    neg = cl_tr[~cl_tr["high_loss"]].sample(min(300_000, int((~cl_tr["high_loss"]).sum())), random_state=0)
    lr_train = pd.concat([cl_tr[cl_tr["high_loss"]], neg])
    logreg = make_pipeline(StandardScaler(), LogisticRegression(max_iter=500, class_weight="balanced"))
    logreg.fit(lr_train[CLASSIFIER_FEATURES], lr_train["high_loss"])
    threshold = _best_f1_threshold(cl_va["high_loss"].to_numpy(), clf.predict(cl_va[CLASSIFIER_FEATURES]))
    metrics["trees"] = {"runoff": runoff.num_trees(), "conc": conc.num_trees(), "high_loss": clf.num_trees()}
    metrics["loss_baseline_fit"] = {"a_g_per_ha_per_mm": a, "k_per_day": k, "half_life_days": float(np.log(2) / k)}

    # ---------------- Evaluation ---------------------------------------------
    def evaluate(te: pd.DataFrame) -> tuple[dict, pd.DataFrame, pd.DataFrame, dict]:
        te = te.copy()
        te["runoff_pred"] = runoff.predict(te[RUNOFF_FEATURES])
        te["runoff_cn"] = te["cn_runoff_mm"]
        tc = te[te["pest_clean"]].copy()
        conc_pred = 10 ** conc.predict(tc[CONC_FEATURES])
        tc["loss_pred"] = tc["runoff_pred"] * conc_pred                 # full surrogate: no PRZM output used
        tc["loss_pred_true_runoff"] = tc["runoff_mm"] * conc_pred       # diagnostic: chemistry stage alone
        tc["loss_base"] = a * tc["runoff_cn"] * np.exp(-k * tc["days_since_app"])
        y = tc["high_loss"].to_numpy()
        scores = {"rain_today_rule": tc["rain_mm"].to_numpy(),
                  "logistic_regression": logreg.predict_proba(tc[CLASSIFIER_FEATURES])[:, 1],
                  "gradient_boosting": clf.predict(tc[CLASSIFIER_FEATURES]),
                  "surrogate_predicted_loss": tc["loss_pred"].to_numpy()}
        hit = scores["gradient_boosting"] >= threshold
        sur_hit = scores["surrogate_predicted_loss"] >= HIGH_LOSS_GHA
        alarm = lambda h: {"alarms": int(h.sum()), "precision": float(y[h].mean()) if h.any() else 0.0,  # noqa: E731
                           "recall": float(h[y].mean()) if y.any() else 0.0,
                           "share_of_loss_on_alarm_days": float(tc.loc[h, "loss_gha"].sum() / tc["loss_gha"].sum())}
        m = {
            "rows": int(len(te)), "rows_with_trusted_pesticide": int(len(tc)),
            "runoff": {"surrogate": _regression_scores(te["runoff_mm"], te["runoff_pred"], te["run"]),
                       "curve_number_baseline": _regression_scores(te["runoff_mm"], te["runoff_cn"], te["run"])},
            "loss": {"surrogate": _loss_scores(tc, "loss_pred"),
                     "chemistry_stage_alone": _loss_scores(tc, "loss_pred_true_runoff"),
                     "decay_x_curve_number_baseline": _loss_scores(tc, "loss_base")},
            "high_loss": {**{name: _classification_scores(y, s) for name, s in scores.items()},
                          "positives": int(y.sum()), "positive_rate": float(y.mean()),
                          "alarms_gradient_boosting": {"threshold": float(threshold), **alarm(hit)},
                          "alarms_surrogate_at_1_gha": alarm(sur_hit)},
        }
        return m, te, tc, scores

    test = t[t["split"] == "test"]
    strict, te, tc, scores = evaluate(test)
    metrics.update({k: strict[k] for k in ("runoff", "loss", "high_loss")})
    metrics["strict_test_rows"] = {k: strict[k] for k in ("rows", "rows_with_trusted_pesticide")}
    # the same scores for each held-out year on its own: shows how much they move from year to year
    from .quality import app_year
    test_year = app_year(pd.DatetimeIndex(test["date"]))
    metrics["by_test_year"] = {}
    for y in sorted(set(test_year)):
        m = evaluate(test[test_year == y])[0]
        metrics["by_test_year"][int(y)] = {
            "runoff_r2_daily": m["runoff"]["surrogate"]["r2_daily"],
            "runoff_r2_daily_curve_number": m["runoff"]["curve_number_baseline"]["r2_daily"],
            "loss_r2_daily": m["loss"]["surrogate"]["r2_daily"],
            "loss_total_ratio": m["loss"]["surrogate"]["total_loss_ratio_pred_over_true"],
            "high_loss_days": m["high_loss"]["positives"],
            "high_loss_pr_auc_surrogate": m["high_loss"]["surrogate_predicted_loss"]["pr_auc"],
            "high_loss_pr_auc_gradient_boosting": m["high_loss"]["gradient_boosting"]["pr_auc"]}
    seen = t[t["split"] == "test_seen_years"]
    if len(seen):
        metrics["seen_years"] = evaluate(seen)[0]

    # ---------------- SHAP (which conditions drive the classifier) -----------
    sample = pd.concat([tc.sample(min(60_000, len(tc)), random_state=0), tc[tc["high_loss"]]])
    sample = sample[~sample.index.duplicated()]
    contrib = clf.predict(sample[CLASSIFIER_FEATURES], pred_contrib=True)[:, :-1]
    shap_rank = pd.Series(np.abs(contrib).mean(axis=0), CLASSIFIER_FEATURES).sort_values(ascending=False)
    metrics["shap_mean_abs"] = shap_rank.round(4).head(12).to_dict()

    # ---------------- speed ---------------------------------------------------
    one_run = t[t["run"] == t["run"].iloc[0]]
    t0 = time.perf_counter()
    for _ in range(20):
        runoff.predict(one_run[RUNOFF_FEATURES]); conc.predict(one_run[CONC_FEATURES])
    metrics["speed"] = {"surrogate_seconds_per_10_year_run": (time.perf_counter() - t0) / 20,
                        "przm_seconds_per_run_from_logs": "about 2-4"}

    # ---------------- risk calendar ------------------------------------------
    calendar = risk_calendar(t[t["pest_clean"]])
    calendar["by_month"].to_csv(results / "risk_calendar_month.csv")
    calendar["by_rain_and_weeks"].to_csv(results / "risk_by_rain_and_weeks_since_spraying.csv")

    meta = {"runoff_features": RUNOFF_FEATURES, "conc_features": CONC_FEATURES,
            "classifier_features": CLASSIFIER_FEATURES, "high_loss_threshold_gha": HIGH_LOSS_GHA,
            "classifier_alarm_threshold": float(threshold), "conc_floor": CONC_FLOOR,
            "trained_on": {"application": "2400 g/ha Flufenacet on 1 March, winter cereals, FOCUS R1",
                           "feature_ranges": {c: [float(tr[c].quantile(0.001)), float(tr[c].quantile(0.999))]
                                              for c in CLASSIFIER_FEATURES}}}
    (model_dir / "meta.json").write_text(json.dumps(meta, indent=2))
    (results / "model_metrics.json").write_text(json.dumps(metrics, indent=2))

    from .figures import model_figures
    model_figures(te, tc, scores, shap_rank, sample, contrib, calendar, Path(figures))
    return metrics


# --------------------------------------------------------------------------- #
# Scores
# --------------------------------------------------------------------------- #
def _regression_scores(y, p, runs) -> dict:
    y, p = np.asarray(y, float), np.asarray(p, float)
    tot = pd.DataFrame({"y": y, "p": p, "run": np.asarray(runs)}).groupby("run", observed=True)[["y", "p"]].sum()
    rel = (tot["p"] - tot["y"]).abs() / tot["y"].clip(lower=1e-9)
    return {"r2_daily": float(r2_score(y, p)), "rmse_mm": float(np.sqrt(np.mean((y - p) ** 2))),
            "r2_run_totals": float(r2_score(tot["y"], tot["p"])),
            "median_abs_error_of_run_total_pct": float(100 * rel.median())}


def _loss_scores(d: pd.DataFrame, col: str) -> dict:
    y, p = d["loss_gha"].to_numpy(float), d[col].to_numpy(float)
    tot = d.groupby("run", observed=True)[["loss_gha", col]].sum()
    tot = tot[tot["loss_gha"] > 0]
    rel = (tot[col] - tot["loss_gha"]).abs() / tot["loss_gha"]
    ev = (y > 0) & (p > 0)
    top = np.argsort(-y)[: max(1, int(0.001 * len(y)))]
    return {"r2_daily": float(r2_score(y, p)),
            "r2_log10_on_runoff_days": float(r2_score(np.log10(y[ev]), np.log10(p[ev]))),
            "r2_run_totals": float(r2_score(tot["loss_gha"], tot[col])),
            "median_abs_error_of_run_total_pct": float(100 * rel.median()),
            "total_loss_ratio_pred_over_true": float(p.sum() / y.sum()),
            "ratio_on_top_0p1pct_days": float(p[top].sum() / y[top].sum())}


def _best_f1_threshold(y, s) -> float:
    prec, rec, thr = precision_recall_curve(y, s)
    f1 = 2 * prec * rec / np.clip(prec + rec, 1e-12, None)
    return float(thr[np.argmax(f1[:-1])])


def _classification_scores(y, s) -> dict:
    prec, rec, _ = precision_recall_curve(y, s)
    f1 = 2 * prec * rec / np.clip(prec + rec, 1e-12, None)
    i = int(np.argmax(f1))
    return {"pr_auc": float(average_precision_score(y, s)), "best_f1": float(f1[i]),
            "precision_at_best_f1": float(prec[i]), "recall_at_best_f1": float(rec[i]),
            "precision_at_80pct_recall": float(prec[rec >= 0.8].max())}


# --------------------------------------------------------------------------- #
# Risk calendar (from trusted simulation results)
# --------------------------------------------------------------------------- #
def risk_calendar(clean: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """When is pesticide loss likely? Uses only rows with trusted pesticide results."""
    month = pd.DatetimeIndex(clean["date"]).month
    g = clean.groupby(month)
    run_years = clean.groupby([clean["run"], pd.DatetimeIndex(clean["date"]).year], observed=True).ngroups
    by_month = pd.DataFrame({
        "rain_days": g.size(),
        "high_loss_days": g["high_loss"].sum(),
        "high_loss_chance_pct_of_rain_days": 100 * g["high_loss"].mean(),
        "runoff_chance_pct_of_rain_days": 100 * g["runoff_mm"].apply(lambda s: (s > 0).mean()),
        "mean_loss_gha_per_rain_day": g["loss_gha"].mean(),
        "share_of_all_loss_pct": 100 * g["loss_gha"].sum() / clean["loss_gha"].sum(),
    }).round(4)
    by_month.index.name = "month"
    by_month.attrs["run_years"] = run_years

    rain_cls = pd.cut(clean["rain_mm"], [1, 5, 10, 20, 30, 50, 1000], right=False,
                      labels=["1-5", "5-10", "10-20", "20-30", "30-50", "50+"])
    weeks = pd.cut(clean["days_since_app"], [0, 7, 14, 28, 56, 112, 366], right=False,
                   labels=["week 1", "week 2", "weeks 3-4", "weeks 5-8", "weeks 9-16", "later"])
    grid = clean.groupby([weeks, rain_cls], observed=False)["high_loss"].agg(["mean", "size"])
    table = (100 * grid["mean"]).where(grid["size"] >= 200).unstack().round(2)
    table.index.name, table.columns.name = "since_spraying", "rain_today_mm"
    return {"by_month": by_month, "by_rain_and_weeks": table}


# --------------------------------------------------------------------------- #
# Loading (for the what-if tool)
# --------------------------------------------------------------------------- #
def load_models(model_dir: str | Path = "models") -> dict:
    model_dir = Path(model_dir)
    missing = [f for f in [*MODEL_FILES.values(), "meta.json"] if not (model_dir / f).exists()]
    if missing:
        raise FileNotFoundError(f"{model_dir}: missing {missing}. Run `python -m runoffwatch train` first.")
    out = {name: lgb.Booster(model_file=str(model_dir / f)) for name, f in MODEL_FILES.items()}
    out["meta"] = json.loads((model_dir / "meta.json").read_text())
    return out
