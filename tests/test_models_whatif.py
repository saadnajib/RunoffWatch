"""Tests for runoffwatch.models and runoffwatch.whatif (no real data, small synthetic tables)."""

from __future__ import annotations

import json
import time
import warnings

import numpy as np
import pandas as pd
import pytest

from runoffwatch import models, whatif
from runoffwatch.features import CLASSIFIER_FEATURES, HIGH_LOSS_GHA, build_feature_table
from runoffwatch.models import (MODEL_FILES, TEST_APP_YEARS, VAL_APP_YEARS, curve_number_runoff,
                                fit_decay_baseline, risk_calendar, split_by_weather, split_rows)
from runoffwatch.przm_inp import SOIL_FEATURES


def fake_hashes(n=30, seed=0):
    """Hex strings like md5 digests, with int(h, 16) % 10 cycling through 0..9."""
    rng = np.random.default_rng(seed)
    return [format(int(rng.integers(1, 2**40)) * 10 + (i % 10), "032x") for i in range(n)]


# --------------------------------------------------------------------------- #
# Split
# --------------------------------------------------------------------------- #
def test_split_by_weather_deterministic_and_grouped():
    hashes = fake_hashes(30)
    rng = np.random.default_rng(1)
    s = pd.Series(rng.choice(hashes, 3000))
    a, b = split_by_weather(s), split_by_weather(s.astype("category"))
    pd.testing.assert_series_equal(a, b)
    pd.testing.assert_series_equal(a, split_by_weather(s.sample(frac=1, random_state=2)).reindex(s.index))
    per_hash = pd.DataFrame({"h": s, "split": a}).groupby("h")["split"].nunique()
    assert (per_hash == 1).all()
    # 30 hashes with buckets 0..9 three times: 6 test, 3 val, 21 train
    counts = pd.DataFrame({"h": s, "split": a}).drop_duplicates("h")["split"].value_counts()
    assert counts.to_dict() == {"train": 21, "test": 6, "val": 3}
    assert set(a) == {"train", "val", "test"}


def test_split_rows():
    hashes = fake_hashes(30)
    dates = pd.date_range("1990-01-01", "1999-12-31", freq="7D")
    df = pd.DataFrame([(h, d) for h in hashes for d in dates], columns=["met_hash", "date"])
    df["met_hash"] = df["met_hash"].astype("category")
    lab = split_rows(df["met_hash"], df["date"])
    files = split_by_weather(df["met_hash"])
    ay = df["date"].dt.year - (df["date"].dt.month < 3)
    assert set(lab) <= set(models.SPLITS)
    # no weather file in both training and test
    tr_h = set(df.loc[lab == "train", "met_hash"])
    te_h = set(df.loc[lab.isin(["test", "test_seen_years"]), "met_hash"])
    assert tr_h and te_h and not (tr_h & te_h)
    assert not (set(df.loc[lab == "val", "met_hash"]) & te_h)
    # years
    assert ay[lab == "test"].isin(TEST_APP_YEARS).all()
    assert set(ay[lab == "test"]) == set(TEST_APP_YEARS)
    assert ay[lab == "val"].isin(VAL_APP_YEARS).all()
    assert not ay[lab == "train"].isin(TEST_APP_YEARS + VAL_APP_YEARS).any()
    assert not ay[lab == "test_seen_years"].isin(TEST_APP_YEARS + VAL_APP_YEARS).any()
    assert (files[lab == "test"] == "test").all()
    assert (files[lab == "test_seen_years"] == "test").all()
    # val uses training AND validation files, never test files
    assert set(files[lab == "val"]) == {"train", "val"}
    # what is left over: val-files in non-val years, train-files in test years, test-files in 1994
    unused = lab == "unused"
    assert (((files == "val") & ~ay.isin(VAL_APP_YEARS))
            | ((files == "train") & ay.isin(TEST_APP_YEARS))
            | ((files == "test") & ay.isin(VAL_APP_YEARS)))[unused].all()


def test_split_rows_jan_feb_belong_to_previous_app_year():
    h = fake_hashes(10)[0]                               # bucket 0 -> test file
    assert split_by_weather(pd.Series([h]))[0] == "test"
    dates = pd.to_datetime(["1992-02-29", "1992-03-01", "1993-02-28", "1993-03-01", "1997-01-15", "1996-12-31"])
    lab = split_rows(pd.Series([h] * len(dates)), pd.Series(dates))
    assert lab.tolist() == ["test_seen_years", "test", "test", "test_seen_years", "test", "test"]
    hv = fake_hashes(10)[5]                              # bucket 5 -> train file
    lab = split_rows(pd.Series([hv] * 3), pd.Series(pd.to_datetime(["1994-02-28", "1994-03-01", "1995-02-28"])))
    assert lab.tolist() == ["train", "val", "val"]


# --------------------------------------------------------------------------- #
# Baselines
# --------------------------------------------------------------------------- #
def test_curve_number_runoff():
    # CN 80: S = 25400/80 - 254 = 63.5 mm, initial abstraction 0.2 S = 12.7 mm
    got = curve_number_runoff([0, 5, 12.7, 30.0], [80, 80, 80, 80])
    assert got[0] == got[1] == got[2] == 0.0
    assert got[3] == pytest.approx((30 - 12.7) ** 2 / (30 + 50.8))
    assert got[3] == pytest.approx(3.70408, rel=1e-5)
    # scalar curve number broadcasts; a higher CN gives more runoff
    assert (curve_number_runoff([30, 60], 90) > curve_number_runoff([30, 60], 80)).all()


def test_fit_decay_baseline_recovers_parameters():
    rng = np.random.default_rng(0)
    runoff = rng.uniform(0.1, 10, 500)
    dsa = rng.integers(0, 300, 500).astype(float)
    loss = 0.37 * runoff * np.exp(-0.021 * dsa)
    runoff[:20] = 0.0                                    # non-runoff days are ignored
    dsa[20:30] = np.nan                                  # days before spraying are ignored
    a, k = fit_decay_baseline(runoff, dsa, loss)
    assert a == pytest.approx(0.37, rel=1e-6)
    assert k == pytest.approx(0.021, rel=1e-6)


def test_risk_calendar():
    rows = []
    for i in range(300):                                 # week 1, 10-20 mm: 300 rows, 1/3 high loss
        rows.append(dict(date="1990-03-03", run="a", rain_mm=15.0, days_since_app=2, runoff_mm=1.0,
                         loss_gha=3.0 if i % 3 == 0 else 0.0, high_loss=i % 3 == 0))
    for i in range(50):                                  # too few rows for the grid: NaN cell
        rows.append(dict(date="1990-06-10", run="b", rain_mm=3.0, days_since_app=100, runoff_mm=0.0,
                         loss_gha=0.0, high_loss=False))
    d = pd.DataFrame(rows)
    d["date"] = pd.to_datetime(d["date"])
    cal = risk_calendar(d)
    bm = cal["by_month"]
    assert bm.loc[3, "rain_days"] == 300 and bm.loc[6, "rain_days"] == 50
    assert bm.loc[3, "high_loss_days"] == 100
    assert bm.loc[3, "high_loss_chance_pct_of_rain_days"] == pytest.approx(100 / 3, abs=1e-3)
    assert bm.loc[6, "runoff_chance_pct_of_rain_days"] == 0
    assert bm["share_of_all_loss_pct"].sum() == pytest.approx(100)
    assert bm.attrs["run_years"] == 2
    g = cal["by_rain_and_weeks"]
    assert g.loc["week 1", "10-20"] == pytest.approx(33.33, abs=0.01)
    assert np.isnan(g.loc["weeks 9-16", "1-5"])
    assert list(g.columns) == ["1-5", "5-10", "10-20", "20-30", "30-50", "50+"]


# --------------------------------------------------------------------------- #
# End-to-end smoke test: synthetic interim data -> features -> train -> what-if
# --------------------------------------------------------------------------- #
def _synthetic_interim(root, n_files=30, seed=0):
    """`run_quality.csv` + daily parquet files with a known rain -> runoff -> loss relation."""
    rng = np.random.default_rng(seed)
    idx = pd.date_range("1990-01-01", "1999-12-31", freq="D")
    doy = idx.dayofyear.to_numpy()
    last_march1 = pd.to_datetime({"year": idx.year - (idx.month < 3), "month": 3, "day": 1})
    dsa = np.where(idx >= pd.Timestamp("1990-03-01"), (idx - pd.DatetimeIndex(last_march1)).days, np.nan)
    (root / "daily").mkdir(parents=True)
    rq = []
    for i, h in enumerate(fake_hashes(n_files, seed)):
        run = f"run_{i:07d}_grid_{i:06d}"
        rain = np.where(rng.random(len(idx)) < 0.3, rng.gamma(1.0, 10.0, len(idx)), 0.0).round(1)
        runoff = np.clip(rain - 10, 0, None) * 0.2
        loss = np.nan_to_num(runoff * 5.0 * np.exp(-0.02 * dsa))
        daily = pd.DataFrame({
            "rain_mm": rain, "temp_c": 8 - 8 * np.cos(2 * np.pi * doy / 365.25) + rng.normal(0, 2, len(idx)),
            "pan_evap_mm": 2.2 - 1.8 * np.cos(2 * np.pi * doy / 365.25), "runoff_mm": runoff,
            "pest_runoff_gha": loss, "applied_gha": np.where((idx.month == 3) & (idx.day == 1), 2400.0, 0.0),
        }, index=idx)
        daily.to_parquet(root / "daily" / f"{run}.parquet")
        cn2 = list(whatif.CN_SETS)[i % 4]
        soil = {k: v * (1 + 0.1 * rng.uniform(-1, 1)) for k, v in whatif.DEFAULT_SOIL.items()}
        soil["cn_2"] = cn2
        cn = whatif.CN_SETS[cn2]
        rq.append({"run": run, "clean_until": "2000-03-01", "met_hash": h, **soil,
                   "cn_1": cn[0], "cn_3": cn[2], "cn_4": cn[3]})
    pd.DataFrame(rq).to_csv(root / "run_quality.csv", index=False)


@pytest.fixture(scope="module")
def trained(tmp_path_factory):
    root = tmp_path_factory.mktemp("e2e")
    interim = root / "interim"
    _synthetic_interim(interim)
    features = root / "features.parquet"
    t0 = time.perf_counter()
    table = build_feature_table(interim, features)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        metrics = models.train_all(features, model_dir=root / "models", results=root / "results",
                                   figures=root / "figures", rounds=20)
    return {"root": root, "table": table, "metrics": metrics, "seconds": time.perf_counter() - t0,
            "models": models.load_models(root / "models")}


def test_synthetic_feature_table_is_usable(trained):
    t = trained["table"]
    assert t["met_hash"].nunique() == 30
    split = split_rows(t["met_hash"], t["date"])
    for s in ("train", "val", "test"):
        part = t[(split == s) & t["pest_clean"]]
        assert part["high_loss"].sum() >= 5, s
    assert (t["high_loss"] == (t["loss_gha"] >= HIGH_LOSS_GHA)).all()


def test_train_all_writes_models_and_metrics(trained):
    root, m = trained["root"], trained["metrics"]
    for f in MODEL_FILES.values():
        assert (root / "models" / f).stat().st_size > 0
    meta = json.loads((root / "models" / "meta.json").read_text())
    assert meta["classifier_features"] == CLASSIFIER_FEATURES
    saved = json.loads((root / "results" / "model_metrics.json").read_text())
    assert {"runoff", "loss", "high_loss", "seen_years", "split"} <= set(saved)
    assert m["runoff"]["surrogate"]["r2_daily"] > 0.5
    assert m["seen_years"]["runoff"]["surrogate"]["r2_daily"] > 0.5
    assert m["split"]["rows"]["test"] > 0 and m["split"]["rows"]["val"] > 0
    assert (root / "results" / "risk_calendar_month.csv").exists()
    assert trained["seconds"] < 60


WEATHER_SPRAY = pd.Timestamp("2026-03-01")


def test_predict_days(trained):
    w = whatif.example_weather()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        days = whatif.predict_days(w, WEATHER_SPRAY, models=trained["models"])
    assert days.index[0] == WEATHER_SPRAY and days.index[-1] == w.index[-1]
    assert days["days_since_spraying"].iloc[0] == 0
    np.testing.assert_array_equal(days["days_since_spraying"], np.arange(len(days)))
    dry = days["rain_mm"] < 1
    assert dry.any() and (~dry).any()
    assert (days.loc[dry, ["runoff_mm", "loss_gha"]] == 0).all().all()
    assert (days[["runoff_mm", "loss_gha"]] >= 0).all().all()
    assert not days.loc[dry, "high_loss_day"].any()
    assert (days["high_loss_day"] == (days["loss_gha"] >= 1.0)).all()
    assert days.attrs["notes"] == []
    assert days.loc["2026-03-10", "runoff_mm"] > days.loc[~dry, "runoff_mm"].min()   # the 32 mm storm


def test_predict_days_rejects_spray_date_outside_weather(trained):
    with pytest.raises(ValueError, match="spray date"):
        whatif.predict_days(whatif.example_weather(), "2027-03-01", models=trained["models"])


def test_predict_days_warns_outside_spring(trained):
    w = whatif.example_weather(start="2026-05-01")
    with pytest.warns(UserWarning, match="February-April"):
        whatif.predict_days(w, "2026-06-05", models=trained["models"])


def test_example_weather_short_period():
    w = whatif.example_weather(days=40)
    assert len(w) == 40


def test_compare_spray_days(trained):
    cands = ["2026-02-25", "2026-03-01", "2026-03-08", "2026-03-15", "2026-03-30"]
    out = whatif.compare_spray_days(whatif.example_weather(), cands, horizon_days=14, models=trained["models"])
    assert len(out) == len(cands)
    assert [str(d) for d in out["spray_date"]] == cands
    assert (out["predicted_loss_gha"] >= 0).all()
    assert (out["high_loss_days"] >= 0).all()
    assert out["days_covered"].tolist() == [14, 14, 14, 14, 6]     # weather ends 4 April
    # only candidates with a full 14-day window are ranked; the truncated one must not win by default
    assert out["rank"].isna().tolist() == [False, False, False, False, True]
    full = out[out["rank"].notna()]
    assert full["rank"].min() == 1 and full["rank"].between(1, 4).all()
    best = full.loc[full["rank"] == 1, "predicted_loss_gha"]
    assert (best <= full["predicted_loss_gha"].min()).all()
    assert any("not ranked" in n for n in out.attrs["notes"])


def test_compare_spray_days_collects_notes(trained):
    w = whatif.example_weather(start="2026-05-01")
    out = whatif.compare_spray_days(w, ["2026-06-05", "2026-06-06"], horizon_days=7, models=trained["models"])
    assert sum("February-April" in n for n in out.attrs["notes"]) == 1      # reported once, not per candidate


# --------------------------------------------------------------------------- #
# what-if inputs
# --------------------------------------------------------------------------- #
def test_soil_settings():
    s = whatif.soil_settings(h1_oc=2.0)
    assert s["h1_kd"] == pytest.approx(7.55)
    assert set(s) == set(SOIL_FEATURES)
    assert whatif.soil_settings(h1_oc=2.0, h1_kd=1.0)["h1_kd"] == 1.0
    assert whatif.soil_settings() == whatif.DEFAULT_SOIL
    with pytest.raises(ValueError, match="unknown"):
        whatif.soil_settings(ph=6.5)
    with pytest.raises(ValueError, match="cn_2"):
        whatif.soil_settings(cn_2=80)


def test_prepare_weather():
    w = whatif.example_weather()
    p = whatif.prepare_weather(w)
    assert "pan_evap_mm" in p
    assert p.loc["2026-01-31", "pan_evap_mm"] == whatif.MONTHLY_EVAP_MM[0]
    assert p.loc["2026-03-15", "pan_evap_mm"] == whatif.MONTHLY_EVAP_MM[2]
    # a 'date' column works as well, and given evaporation is kept
    q = whatif.prepare_weather(w.assign(pan_evap_mm=1.5).reset_index())
    assert (q["pan_evap_mm"] == 1.5).all() and isinstance(q.index, pd.DatetimeIndex)
    with pytest.raises(ValueError, match="gaps"):
        whatif.prepare_weather(w.drop(index=w.index[10]))
    neg = w.copy()
    neg.iloc[5, neg.columns.get_loc("rain_mm")] = -1.0
    with pytest.raises(ValueError, match="negative"):
        whatif.prepare_weather(neg)
    nan = w.copy()
    nan.iloc[5, nan.columns.get_loc("temp_c")] = np.nan
    with pytest.raises(ValueError):
        whatif.prepare_weather(nan)
    with pytest.raises(ValueError, match="columns"):
        whatif.prepare_weather(w.drop(columns="temp_c"))


def test_example_weather_has_storm():
    w = whatif.example_weather()
    assert len(w) == 75 and (w["rain_mm"] >= 0).all()
    assert w.loc["2026-03-10", "rain_mm"] == 32.0


def test_yearly_cv_smoke(trained, tmp_path):
    """Leave-one-year-out evaluation runs end to end and never tests on a trained year."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        out = models.yearly_cv(trained["root"] / "features.parquet", results=tmp_path, figures=tmp_path, rounds=10)
    by_year = pd.read_csv(tmp_path / "cv_by_year.csv", index_col="test_year")
    assert list(by_year.index) == out["held_out_years"] and len(by_year) >= 5
    assert (tmp_path / "cv_summary.json").exists() and (tmp_path / "m7_scores_by_held_out_year.png").exists()
    assert out["rows_scored"] > 0
    assert 0 <= out["pooled"]["pr_auc_surrogate"] <= 1
    lo, hi = out["range_over_years"]["runoff_r2"]
    assert lo <= out["pooled"]["runoff_r2"] + 0.2 and lo <= hi


# --------------------------------------------------------------------------- #
# Dose and spray date in the models
# --------------------------------------------------------------------------- #
from runoffwatch.features import CONC_FEATURES, DEFAULT_RATE_KGHA, RUNOFF_FEATURES  # noqa: E402


def _table(n=2000, seed=0, dose=2.4, water_row=None):
    """Small synthetic feature table with every model input and a known loss per kg/ha sprayed."""
    rng = np.random.default_rng(seed)
    t = pd.DataFrame({c: rng.uniform(0, 1, n) for c in CLASSIFIER_FEATURES})
    t["rain_mm"] = rng.gamma(1.0, 10.0, n) + 1
    t["cn_runoff_mm"] = np.clip(t["rain_mm"] - 10, 0, None) * 0.3
    t["days_since_app"] = rng.integers(0, 300, n).astype(float)
    t["app_doy"] = 60.0
    t["app_rate_kgha"] = dose
    t["runoff_mm"] = np.clip(t["rain_mm"] - 10, 0, None) * 0.2
    t["loss_gha"] = t["runoff_mm"] * 2.0 * np.exp(-0.02 * t["days_since_app"]) * t["app_rate_kgha"]
    t["pest_clean"] = True
    t["high_loss"] = t["loss_gha"] >= HIGH_LOSS_GHA
    if water_row is not None:
        t["water_row"] = water_row
    return t


def test_rate_water_and_conc_helpers():
    t = _table(10, dose=1.2)
    np.testing.assert_array_equal(models._rate(t), np.full(10, 1.2))
    np.testing.assert_array_equal(models._rate(t.drop(columns="app_rate_kgha")), np.full(10, DEFAULT_RATE_KGHA))
    assert models._water(t) is t                                         # no column: every row
    w = t.assign(water_row=[True, False] * 5)
    assert len(models._water(w)) == 5 and models._water(w)["water_row"].all()
    t = pd.DataFrame({"loss_gha": [2.4, 1.2, -1.0, 0.0], "runoff_mm": [1.0, 2.0, 1.0, 3.0],
                      "app_rate_kgha": [2.4, 0.6, 1.0, 1.0]})
    np.testing.assert_allclose(models._conc(t), [1.0, 1.0, 0.0, 0.0])      # per mm and per kg/ha, never negative
    np.testing.assert_allclose(models._conc(t.drop(columns="app_rate_kgha")), [1.0, 0.25, 0.0, 0.0])


def test_conc_target_unchanged_when_loss_and_dose_double():
    t = _table(200)
    t2 = t.assign(loss_gha=2 * t["loss_gha"], app_rate_kgha=2 * t["app_rate_kgha"])
    c = models._conc_rows(t)
    pd.testing.assert_series_equal(models._conc(c), models._conc(models._conc_rows(t2)))


def test_doubled_dose_gives_doubled_loss():
    """Doubling every loss together with the dose leaves the concentration target as it is, so a
    model trained on the original table predicts doubled losses for the doubled dose."""
    t = _table(2000)
    t2 = t.assign(loss_gha=2 * t["loss_gha"], app_rate_kgha=2 * t["app_rate_kgha"])
    conc = models.fit_conc(t, rounds=15)
    conc2 = models.fit_conc(t2, rounds=15)
    rows = _table(300, seed=5)
    rows2 = rows.assign(app_rate_kgha=2 * rows["app_rate_kgha"])
    loss = models.predict_loss(conc, rows, rows["runoff_mm"])
    assert loss.sum() > 0
    np.testing.assert_allclose(models.predict_loss(conc, rows2, rows2["runoff_mm"]), 2 * loss, rtol=1e-9)
    # the model trained on the doubled table is the same model
    np.testing.assert_allclose(conc2.predict(rows[CONC_FEATURES]), conc.predict(rows[CONC_FEATURES]), rtol=1e-9)
    np.testing.assert_allclose(models.predict_loss(conc2, rows2, rows2["runoff_mm"]), 2 * loss, rtol=1e-9)


def test_predict_loss_is_runoff_times_conc_times_dose():
    t = _table(1000)
    conc = models.fit_conc(t, rounds=10)
    rows = _table(50, seed=3).assign(app_rate_kgha=np.linspace(0.1, 3.0, 50))
    runoff = np.linspace(0, 5, 50)
    expect = runoff * conc.predict(rows[CONC_FEATURES]) * rows["app_rate_kgha"].to_numpy()
    np.testing.assert_allclose(models.predict_loss(conc, rows, runoff), expect)
    assert models.predict_loss(conc, rows, pd.Series(runoff)).shape == (50,)


@pytest.mark.parametrize("kind, raw, rate, expected", [
    (models.CONC_OUTPUT, [0.5, 1.0], 2.0, [1.0, 2.0]),                      # per kg/ha: raw x dose
    ("g_per_ha_per_mm", [0.6, 1.2], 1.2, [0.3, 0.6]),                       # older: raw x dose / 2.4
    ("g_per_ha_per_mm", [0.6, 1.2], 2.4, [0.6, 1.2]),
    (None, [0.0, -1.0], 2.4, [1.0, 0.1]),                                   # first models: log10
    ("log10", [1.0], 4.8, [20.0]),
])
def test_conc_per_mm_three_kinds_of_model(kind, raw, rate, expected):
    meta = {} if kind is None else {"conc_output": kind}
    np.testing.assert_allclose(models.conc_per_mm(meta, raw, rate), expected)


def test_conc_per_mm_with_one_dose_per_row():
    got = models.conc_per_mm({"conc_output": models.CONC_OUTPUT}, [1.0, 1.0, 2.0], [0.5, 1.0, 2.0])
    np.testing.assert_allclose(got, [0.5, 1.0, 4.0])
    assert models.CONC_OUTPUT == "g_per_ha_per_mm_per_kg_applied"


def test_spray_window():
    doy = [1, 31, 32, 60, 121, 122, 200, 273, 274, 300, 335, 336, 366, np.nan]
    assert list(models.spray_window(doy)) == (
        ["other", "other"] + ["spring (Feb-Apr)"] * 3 + ["other"] * 3 + ["autumn (Oct-Nov)"] * 3
        + ["other"] * 3)
    assert models.spray_window(60.0).item() == "spring (Feb-Apr)"


def _capture_fit(monkeypatch):
    seen = []
    real = models._fit

    def spy(params, Xtr, ytr, Xva=None, yva=None, rounds=1500, patience=40, wtr=None, wva=None):
        seen.append({"Xtr": Xtr, "ytr": ytr, "Xva": Xva, "yva": yva})
        return real(params, Xtr, ytr, Xva, yva, rounds=rounds, patience=patience, wtr=wtr, wva=wva)

    monkeypatch.setattr(models, "_fit", spy)
    return seen


def test_fit_runoff_uses_only_water_rows(monkeypatch):
    seen = _capture_fit(monkeypatch)
    water = np.arange(1000) % 3 == 0
    tr = _table(1000, water_row=water)
    tr.loc[~water, "runoff_mm"] = 500.0                  # copies would teach nonsense if they were used
    va = _table(300, seed=1, water_row=np.arange(300) % 2 == 0)
    booster = models.fit_runoff(tr, va, rounds=20)
    assert len(seen[0]["Xtr"]) == water.sum() and len(seen[0]["Xva"]) == 150
    assert list(seen[0]["Xtr"].columns) == RUNOFF_FEATURES
    assert (seen[0]["ytr"] < 500).all()
    assert booster.predict(tr.loc[water, RUNOFF_FEATURES]).max() < 100
    # without the column every row is used
    models.fit_runoff(tr.drop(columns="water_row"), rounds=5)
    assert len(seen[-1]["Xtr"]) == 1000 and seen[-1]["Xva"] is None


def test_fit_classifier_thins_negatives_keeps_positives(monkeypatch):
    seen = _capture_fit(monkeypatch)
    monkeypatch.setattr(models, "MAX_CLASSIFIER_ROWS", 300)
    t = _table(2000)
    t["high_loss"] = np.arange(2000) % 20 == 0           # 100 positives
    t.loc[t.index[-200:], "pest_clean"] = False          # never used, thinned or not
    t.loc[t.index[-200:], "high_loss"] = True
    models.fit_classifier(t, rounds=5)
    X, y = seen[0]["Xtr"], seen[0]["ytr"]
    clean_pos = t.index[t["pest_clean"] & t["high_loss"]]
    assert set(clean_pos) <= set(X.index) and int(y.sum()) == len(clean_pos) == 90
    assert set(X.index) <= set(t.index[t["pest_clean"]])
    assert 200 <= len(X) <= 420                          # about MAX_CLASSIFIER_ROWS rows
    # the same rows every time (fixed seed)
    models.fit_classifier(t, rounds=5)
    assert list(seen[1]["Xtr"].index) == list(X.index)


def test_fit_classifier_below_limit_uses_every_clean_row(monkeypatch):
    seen = _capture_fit(monkeypatch)
    t = _table(500)
    t["high_loss"] = np.arange(500) % 10 == 0
    t.loc[t.index[:50], "pest_clean"] = False
    models.fit_classifier(t, rounds=5)
    assert len(seen[0]["Xtr"]) == 450


def test_group_scores():
    P = pd.DataFrame({"loss_gha": [0.5, 2.0, 3.0, 0.0, 0.0, 4.0],
                      "loss_pred": [0.4, 1.5, 0.5, 0.0, 0.1, 3.0],
                      "high_loss": [False, True, True, False, False, True]})
    out = models._group_scores(P, pd.Series(["a", "a", "a", "b", "b", "c"]))
    assert set(out) == {"a", "b", "c"}
    a = out["a"]
    assert a["rows"] == 3 and a["high_loss_days"] == 2
    assert a["loss_total_pred_over_true"] == pytest.approx(2.4 / 5.5)
    assert a["alarm_precision"] == 1.0 and a["alarm_recall"] == 0.5
    assert 0 <= a["pr_auc_surrogate"] <= 1 and a["loss_r2"] is not None
    b = out["b"]                                         # no loss, no positives, no alarms
    assert b["loss_total_pred_over_true"] is None and b["pr_auc_surrogate"] is None
    assert b["alarm_precision"] is None and b["alarm_recall"] is None
    assert out["c"]["loss_r2"] is None                   # one row: no R2
    json.dumps(out)                                      # goes into cv_summary.json
    # numeric group keys become strings
    assert set(models._group_scores(P, pd.Series([2.4, 2.4, 2.4, 0.6, 0.6, 0.6]))) == {"0.6", "2.4"}


def _seasons(rows):
    """rows: (run, season, app_doy, rate, last_day, loss_gha per row list)."""
    out = []
    for run, season, doy, rate, last_day, losses in rows:
        for i, loss in enumerate(losses):
            out.append({"run": run, "app_season": float(season), "app_doy": float(doy), "app_rate_kgha": rate,
                        "days_since_app": float(last_day if i == len(losses) - 1 else i), "loss_gha": loss,
                        "high_loss": loss >= HIGH_LOSS_GHA})
    return pd.DataFrame(out)


def test_loss_by_spray_date():
    clean = _seasons([
        ("r1", 1990, 60, 2.4, 350, [12.0, 12.0]),        # 1 March: 24 g of 2400 g = 1 %
        ("r2", 1990, 70, 1.2, 320, [6.0]),                # 11 March: 6 g of 1200 g = 0.5 %
        ("r1", 1991, 288, 2.4, 330, [2.4]),               # 15 October: 0.1 %
        ("r2", 1991, 289, 0.6, 330, [3.0]),               # 16 October: 0.5 %
        ("r3", 1990, 60, 2.4, 299, [500.0]),              # cut off by the end of the run: left out
    ])
    out = models.loss_by_spray_date(clean)
    assert list(out.index) == ["03 Mar 1-15", "10 Oct 1-15", "10 Oct 16-end"]
    assert out.loc["03 Mar 1-15", "seasons"] == 2
    assert out.loc["03 Mar 1-15", "mean_pct_of_dose_lost"] == pytest.approx(0.75)
    assert out.loc["03 Mar 1-15", "median_pct_of_dose_lost"] == pytest.approx(0.75)
    assert out.loc["03 Mar 1-15", "mean_loss_gha"] == pytest.approx(15.0)
    assert out.loc["10 Oct 1-15", "mean_pct_of_dose_lost"] == pytest.approx(0.1)
    assert out.loc["10 Oct 16-end", "mean_pct_of_dose_lost"] == pytest.approx(0.5)
    assert {"p90_pct_of_dose_lost"} <= set(out.columns)


def test_loss_by_spray_date_same_label_in_leap_years():
    """15 March is in the first half of March, also in a leap year (day of the year 75 instead of 74)."""
    sprayed = [pd.Timestamp("1991-03-15"), pd.Timestamp("1992-03-15"), pd.Timestamp("1992-03-16")]
    clean = _seasons([(f"r{i}", d.year, d.dayofyear, 2.4, 330, [2.4]) for i, d in enumerate(sprayed)])
    out = models.loss_by_spray_date(clean)
    assert out.loc["03 Mar 1-15", "seasons"] == 2
    assert out.loc["03 Mar 16-end", "seasons"] == 1


def test_loss_by_spray_date_empty_cases():
    clean = _seasons([("r1", 1990, 60, 2.4, 350, [1.0])])
    for col in ("app_season", "app_doy", "app_rate_kgha"):
        assert models.loss_by_spray_date(clean.drop(columns=col)).empty
    short = _seasons([("r1", 1990, 60, 2.4, 200, [1.0])])
    assert models.loss_by_spray_date(short).empty


def _after_rows(run, season, doy, rate, days, loss, runoff, rain, cn):
    """Rain-day rows of one season for loss_after_spraying; the lists hold one value per row."""
    return pd.DataFrame({"run": run, "app_season": float(season), "app_doy": float(doy), "app_rate_kgha": rate,
                         "days_since_app": [float(d) for d in days], "loss_gha": loss, "runoff_mm": runoff,
                         "rain_mm": rain, "cn_today": cn, "high_loss": [x >= HIGH_LOSS_GHA for x in loss]})


def _after_example():
    return pd.concat([
        # 1 March, 2400 g/ha: 24 g = 1 % in days 0-30, 2.4 g = 0.1 % in days 31-120, nothing later
        _after_rows("r1", 1990, 60, 2.4, [2, 20, 50, 200, 330], [12.0, 12.0, 2.4, 0.0, 0.0],
                    [5.0, 3.0, 2.0, 0.0, 0.0], [30.0, 20.0, 15.0, 10.0, 5.0], [80, 90, 70, 60, 60]),
        # 11 March, 1200 g/ha: 6 g = 0.5 % in days 0-30; no rain day at all in days 31-120
        _after_rows("r2", 1990, 70, 1.2, [10, 125, 320], [6.0, 0.0, 0.0],
                    [4.0, 0.0, 0.0], [25.0, 8.0, 4.0], [85, 65, 65]),
        # 15 October, 2400 g/ha: a separate half-month
        _after_rows("r1", 1991, 288, 2.4, [5, 40, 330], [2.4, 0.0, 0.0],
                    [1.0, 0.0, 0.0], [12.0, 6.0, 3.0], [75, 70, 70]),
        # 1 March but cut off by the end of the run (299 days): left out
        _after_rows("r3", 1990, 60, 2.4, [3, 299], [500.0, 0.0], [50.0, 0.0], [90.0, 1.0], [99, 99]),
    ], ignore_index=True)


def test_loss_after_spraying():
    out = models.loss_after_spraying(_after_example())
    assert out.index.names == ["sprayed", "days_after_spraying"]
    assert list(out.index) == [(s, p) for s in ("03 Mar 1-15", "10 Oct 1-15") for p in ("0-30", "31-120", "121+")]
    assert list(out.columns) == ["seasons", "rain_mm", "runoff_mm", "pct_of_dose_lost", "curve_number",
                                 "pct_of_dose_per_mm_runoff"]
    mar = out.loc["03 Mar 1-15"]
    assert (mar["seasons"] == 2).all()                       # r3 is too short, the same count in each period
    assert mar.loc["0-30", "rain_mm"] == pytest.approx((30 + 20 + 25) / 2)
    assert mar.loc["0-30", "runoff_mm"] == pytest.approx((5 + 3 + 4) / 2)
    assert mar.loc["0-30", "pct_of_dose_lost"] == pytest.approx((1.0 + 0.5) / 2)
    assert mar.loc["0-30", "curve_number"] == pytest.approx((80 + 90 + 85) / 3)
    assert mar.loc["0-30", "pct_of_dose_per_mm_runoff"] == pytest.approx(0.75 / 6, abs=1e-4)
    assert mar.loc["31-120", "rain_mm"] == pytest.approx(15 / 2)   # r2 had no rain day here: counts as 0
    assert mar.loc["31-120", "pct_of_dose_lost"] == pytest.approx(0.05)
    assert mar.loc["31-120", "curve_number"] == pytest.approx(70)
    assert mar.loc["121+", "rain_mm"] == pytest.approx((10 + 5 + 8 + 4) / 2)
    assert mar.loc["121+", "runoff_mm"] == 0 and np.isnan(mar.loc["121+", "pct_of_dose_per_mm_runoff"])
    octo = out.loc["10 Oct 1-15"]
    assert (octo["seasons"] == 1).all()
    assert octo.loc["0-30", "pct_of_dose_lost"] == pytest.approx(0.1)
    assert octo.loc["0-30", "pct_of_dose_per_mm_runoff"] == pytest.approx(0.1)
    # the periods add up to the whole season, as in loss_by_spray_date
    by_date = models.loss_by_spray_date(_after_example())
    assert out.groupby(level="sprayed")["pct_of_dose_lost"].sum().to_dict() == \
        pytest.approx(by_date["mean_pct_of_dose_lost"].to_dict())


def test_loss_after_spraying_other_periods_and_empty_cases():
    out = models.loss_after_spraying(_after_example(), periods=((0, 14), (15, None)))
    assert list(out.index.get_level_values("days_after_spraying").unique()) == ["0-14", "15+"]
    assert out.loc[("03 Mar 1-15", "0-14"), "pct_of_dose_lost"] == pytest.approx((0.5 + 0.5) / 2)   # day 20 is later
    clean = _after_example()
    for col in ("run", "app_season", "app_doy", "app_rate_kgha", "days_since_app", "loss_gha", "runoff_mm",
                "rain_mm", "cn_today"):
        assert models.loss_after_spraying(clean.drop(columns=col)).empty
    assert models.loss_after_spraying(clean[clean["run"] == "r3"]).empty


def test_loss_by_spray_date_unchanged_by_shared_season_helper():
    """loss_by_spray_date gives the same table as the code it had before the season helper was split off."""
    def old(clean):
        g = clean.groupby(["run", "app_season"], observed=True)
        s = g.agg(loss_gha=("loss_gha", "sum"), app_doy=("app_doy", "first"), rate=("app_rate_kgha", "first"),
                  last_day=("days_since_app", "max"), high_loss_days=("high_loss", "sum"))
        s = s[s["last_day"] >= 300].copy()
        s["pct_of_dose_lost"] = 100 * s["loss_gha"] / (1000 * s["rate"])
        year = s.index.get_level_values("app_season").astype(int)
        when = pd.Series(pd.to_datetime({"year": year, "month": 1, "day": 1}).to_numpy(), index=s.index) \
            + pd.to_timedelta(s["app_doy"] - 1, unit="D")
        s["sprayed"] = when.dt.strftime("%m %b ") + np.where(when.dt.day <= 15, "1-15", "16-end")
        return s.groupby("sprayed").agg(seasons=("loss_gha", "size"),
                                        mean_pct_of_dose_lost=("pct_of_dose_lost", "mean"),
                                        median_pct_of_dose_lost=("pct_of_dose_lost", "median"),
                                        p90_pct_of_dose_lost=("pct_of_dose_lost", lambda x: x.quantile(0.9)),
                                        mean_loss_gha=("loss_gha", "mean")).round(4)

    other = _seasons([("r1", 1990, 60, 2.4, 350, [12.0, 12.0]), ("r2", 1992, 75, 1.2, 320, [6.0]),
                      ("r1", 1991, 289, 0.6, 330, [3.0])])
    for clean in (_after_example(), other):
        pd.testing.assert_frame_equal(models.loss_by_spray_date(clean), old(clean))


def test_train_all_writes_spray_outputs_and_meta(trained):
    root = trained["root"]
    meta = json.loads((root / "models" / "meta.json").read_text())
    assert meta["conc_output"] == models.CONC_OUTPUT
    assert meta["conc_features"] == CONC_FEATURES and meta["runoff_features"] == RUNOFF_FEATURES
    on = meta["trained_on"]
    assert on["doses_kgha"] == [2.4]
    assert set(on["spray_days_seen"]) == {60, 61}                  # 1 March in common and leap years
    assert on["spray_day_of_year"] == [60, 61]
    by_spray = pd.read_csv(root / "results" / "loss_by_spray_date.csv", index_col=0)
    assert list(by_spray.index) == ["03 Mar 1-15"] and by_spray["seasons"].iloc[0] > 0
    after = pd.read_csv(root / "results" / "loss_after_spraying.csv", index_col=[0, 1])
    assert list(after.index) == [("03 Mar 1-15", p) for p in ("0-30", "31-120", "121+")]
    assert (after["seasons"] == by_spray["seasons"].iloc[0]).all()
    assert (root / "figures" / "m9_loss_by_spray_date.png").stat().st_size > 0
    m = trained["metrics"]["final_models"]
    assert m["rain_day_rows_one_run_per_field"] == m["rain_day_rows"]   # no copies in this table


def test_yearly_cv_scores_by_spray_window_and_dose(trained, tmp_path):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        out = models.yearly_cv(trained["root"] / "features.parquet", results=tmp_path, figures=tmp_path, rounds=5)
    assert set(out["by_spray_window"]) == {"spring (Feb-Apr)"}
    assert set(out["by_dose_kgha"]) == {"2.4"}
    assert out["by_dose_kgha"]["2.4"]["rows"] == out["rows_scored"]
    saved = json.loads((tmp_path / "cv_summary.json").read_text())
    assert saved["by_spray_window"] == out["by_spray_window"]
    assert set(saved["alarm_by_share_of_dose"]) == {f"{p:g}" for p in models.SHARE_OF_DOSE_LIMITS_PCT}
    kept = pd.read_parquet(trained["root"] / "features_cv_predictions.parquet")     # for scoring other limits later
    assert len(kept) == out["rows_scored"] and {"loss_gha", "loss_pred", "app_rate_kgha"} <= set(kept.columns)


# --------------------------------------------------------------------------- #
# what-if with a dose and with models that know several spray days
# --------------------------------------------------------------------------- #
def _with_meta(trained, **trained_on):
    m = dict(trained["models"])
    meta = json.loads(json.dumps(m["meta"]))
    meta["trained_on"].update(trained_on)
    m["meta"] = meta
    return m


def _predict(w, day, m, **kw):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return whatif.predict_days(w, day, models=m, **kw)


def test_predict_days_loss_scales_with_dose(trained):
    w = whatif.example_weather()
    base = _predict(w, WEATHER_SPRAY, trained["models"])
    half = _predict(w, WEATHER_SPRAY, trained["models"], rate_kgha=1.2)
    assert base["loss_gha"].sum() > 0
    np.testing.assert_allclose(half["runoff_mm"], base["runoff_mm"])
    np.testing.assert_allclose(half["loss_gha"], base["loss_gha"] / 2, rtol=1e-9)
    assert any("scaled in proportion" in n for n in half.attrs["notes"])
    assert not any("kg/ha" in n for n in base.attrs["notes"])
    with pytest.warns(UserWarning, match="scaled in proportion"):
        whatif.predict_days(w, WEATHER_SPRAY, models=trained["models"], rate_kgha=0.24)


@pytest.mark.parametrize("dose", [0, -1.0, np.nan])
def test_predict_days_refuses_dose_not_above_zero(trained, dose):
    with pytest.raises(ValueError, match="dose"):
        whatif.predict_days(whatif.example_weather(), WEATHER_SPRAY, models=trained["models"], rate_kgha=dose)
    with pytest.raises(ValueError, match="dose"):
        whatif.compare_spray_days(whatif.example_weather(), [WEATHER_SPRAY], models=trained["models"], rate_kgha=dose)


def test_compare_spray_days_with_dose(trained):
    w = whatif.example_weather()
    cands = ["2026-02-25", "2026-03-08"]
    base = whatif.compare_spray_days(w, cands, horizon_days=14, models=trained["models"])
    low = whatif.compare_spray_days(w, cands, horizon_days=14, models=trained["models"], rate_kgha=0.6)
    np.testing.assert_allclose(low["predicted_loss_gha"], base["predicted_loss_gha"] / 4, atol=1e-3)
    # the share of the dose is computed with the given dose, so it does not change here
    np.testing.assert_allclose(low["loss_pct_of_dose"], base["loss_pct_of_dose"], atol=2e-4)
    np.testing.assert_allclose(base["loss_pct_of_dose"], 100 * base["predicted_loss_gha"] / 2400, atol=2e-4)
    assert low["rank"].tolist() == base["rank"].tolist()
    assert sum("scaled in proportion" in n for n in low.attrs["notes"]) == 1


def test_predict_days_old_model_kind_is_scaled_from_the_delivered_dose(trained):
    w = whatif.example_weather()
    new = _predict(w, WEATHER_SPRAY, trained["models"], rate_kgha=1.2)
    old = dict(trained["models"]); old["meta"] = {**old["meta"], "conc_output": "g_per_ha_per_mm"}
    got = _predict(w, WEATHER_SPRAY, old, rate_kgha=1.2)
    # the same raw output read as "g/ha per mm at 2.4 kg/ha" instead of "per kg/ha": 2.4 times less
    big = new["loss_gha"] > 1e-3
    assert big.any()
    np.testing.assert_allclose(got.loc[big, "loss_gha"], new.loc[big, "loss_gha"] / 2.4, rtol=1e-9)


SEEN = [60, 75, 290]           # 1 March, 16 March, 17 October (common year)


@pytest.mark.parametrize("day, guess", [
    ("2026-03-01", False), ("2026-03-11", False), ("2026-03-26", False),   # within ten days of 60 or 75
    ("2026-03-27", True),                                                  # 11 days after 16 March
    ("2026-02-18", True), ("2026-02-19", False),
    ("2026-10-27", False), ("2026-11-15", True), ("2026-06-15", True),
])
def test_several_spray_days_guess_note(trained, day, guess):
    m = _with_meta(trained, spray_days_seen=SEEN, doses_kgha=[0.6, 1.2, 2.4])
    w = whatif.example_weather(start="2026-01-01", days=365)
    notes = _predict(w, day, m).attrs["notes"]
    assert any("guess" in n for n in notes) == guess
    assert not any("February-April" in n for n in notes)       # that note is for 1-March-only models


@pytest.mark.parametrize("dose, note", [(0.6, False), (1.0, False), (2.4, False), (0.3, True), (3.0, True)])
def test_several_doses_note_outside_trained_doses(trained, dose, note):
    m = _with_meta(trained, spray_days_seen=SEEN, doses_kgha=[0.6, 1.2, 2.4])
    notes = _predict(whatif.example_weather(), WEATHER_SPRAY, m, rate_kgha=dose).attrs["notes"]
    assert any("outside the doses" in n for n in notes) == note
    assert not any("scaled in proportion" in n for n in notes)


def test_meta_without_spray_keys_behaves_as_before(trained):
    m = dict(trained["models"])
    meta = json.loads(json.dumps(m["meta"]))
    for k in ("spray_days_seen", "doses_kgha", "spray_day_of_year"):
        meta["trained_on"].pop(k)
    m["meta"] = meta
    w = whatif.example_weather(start="2026-05-01")
    notes = _predict(w, "2026-06-05", m, rate_kgha=1.2).attrs["notes"]
    assert any("February-April" in n for n in notes)
    assert any("All training simulations used 2.4 kg/ha" in n for n in notes)


# --------------------------------------------------------------------------- #
# End to end with varied spray dates and doses: 1 March runs + copies of the same fields
# --------------------------------------------------------------------------- #
VARIED = [((15, 10), 0.6), ((1, 3), 1.2), ((15, 10), 2.4)]      # (day, month), kg/ha per copy


def _varied_copies(fixed, varied):
    """Copies `<run>__v1` of every run in `fixed`: same weather and runoff, other spray date and dose."""
    (varied / "daily").mkdir(parents=True)
    rq = pd.read_csv(fixed / "run_quality.csv")
    for i, run in enumerate(rq["run"]):
        (day, month), dose = VARIED[i % len(VARIED)]
        d = pd.read_parquet(fixed / "daily" / f"{run}.parquet")
        is_app = (d.index.month == month) & (d.index.day == day)
        last = pd.Series(d.index.where(is_app), index=d.index).ffill()
        dsa = (d.index - last).dt.days.to_numpy(dtype=float)
        d["applied_gha"] = np.where(is_app, 1000 * dose, 0.0)
        d["pest_runoff_gha"] = np.nan_to_num(d["runoff_mm"] * 5.0 * np.exp(-0.02 * dsa) * dose / 2.4)
        d.to_parquet(varied / "daily" / f"{run}__v1.parquet")
    rq.assign(run=rq["run"] + "__v1").to_csv(varied / "run_quality.csv", index=False)


@pytest.fixture(scope="module")
def trained_varied(tmp_path_factory):
    root = tmp_path_factory.mktemp("varied")
    _synthetic_interim(root / "fixed", n_files=12, seed=4)
    _varied_copies(root / "fixed", root / "varied")
    features = root / "features.parquet"
    table = build_feature_table([root / "fixed", root / "varied"], features)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        metrics = models.train_all(features, model_dir=root / "models", results=root / "results",
                                   figures=root / "figures", rounds=10)
    return {"root": root, "table": table, "metrics": metrics}


def test_varied_feature_table(trained_varied):
    t = trained_varied["table"]
    assert t["field"].nunique() == 12 and t["run"].nunique() == 24
    assert set(t.loc[t["water_row"], "run"].astype(str)) == {r for r in t["run"].astype(str) if "__v" not in r}
    assert {round(float(x), 3) for x in t["app_rate_kgha"].dropna().unique()} == {0.6, 1.2, 2.4}
    assert {60, 61, 288, 289} <= set(t["app_doy"].dropna().astype(int))
    # the copies hold the same water as the field they come from
    a = t[t["run"] == "run_0000000_grid_000000"].set_index("date")
    b = t[t["run"] == "run_0000000_grid_000000__v1"].set_index("date")
    pd.testing.assert_series_equal(a["runoff_mm"], b["runoff_mm"])


def test_varied_train_all_meta_and_spray_table(trained_varied):
    root, m = trained_varied["root"], trained_varied["metrics"]
    meta = json.loads((root / "models" / "meta.json").read_text())
    on = meta["trained_on"]
    assert on["doses_kgha"] == [0.6, 1.2, 2.4]
    assert {60, 61, 288, 289} <= set(on["spray_days_seen"])
    assert on["spray_day_of_year"][0] == min(on["spray_days_seen"])
    assert on["spray_day_of_year"][1] == max(on["spray_days_seen"])
    assert m["final_models"]["rain_day_rows_one_run_per_field"] * 2 == m["final_models"]["rain_day_rows"]
    by_spray = pd.read_csv(root / "results" / "loss_by_spray_date.csv", index_col=0)
    assert {"03 Mar 1-15", "10 Oct 1-15"} <= set(by_spray.index)
    assert (root / "figures" / "m9_loss_by_spray_date.png").exists()
    # the loss is proportional to the dose here, so the share of the dose lost is about the same for each dose
    assert (by_spray["mean_pct_of_dose_lost"] > 0).all()


def test_varied_models_in_whatif(trained_varied):
    m = models.load_models(trained_varied["root"] / "models")
    w = whatif.example_weather()
    a = _predict(w, WEATHER_SPRAY, m, rate_kgha=1.2)
    assert not any("guess" in n or "kg/ha" in n for n in a.attrs["notes"])
    assert (a["loss_gha"] >= 0).all()
    far = _predict(whatif.example_weather(start="2026-05-01"), "2026-06-05", m).attrs["notes"]
    assert any("guess" in n for n in far)
    out = _predict(w, WEATHER_SPRAY, m, rate_kgha=5.0).attrs["notes"]
    assert any("outside the doses" in n for n in out)


def test_alarm_by_share_of_dose_uses_the_dose_of_each_row():
    """0.1 % of the dose is 2.4 g/ha at 2.4 kg/ha and 0.24 g/ha at 0.24 kg/ha."""
    P = pd.DataFrame({"app_rate_kgha": [2.4, 2.4, 2.4, 0.24, 0.24, 0.24],
                      "loss_gha":      [3.0, 1.0, 3.0, 0.30, 0.10, 0.10],
                      "loss_pred":     [2.5, 2.5, 0.0, 0.25, 0.00, 0.30]})
    out = models.alarm_by_share_of_dose(P, limits_pct=(0.1,))["0.1"]
    assert out["high_loss_days"] == 3 and out["alarms"] == 4
    assert out["precision"] == pytest.approx(2 / 4) and out["recall"] == pytest.approx(2 / 3)
    low = out["by_dose_kgha"]["0.24"]
    assert low == {"high_loss_days": 1, "alarms": 2, "precision": 0.5, "recall": 1.0}
    json.dumps(out)


def test_alarm_by_share_of_dose_without_any_high_loss_day():
    P = pd.DataFrame({"app_rate_kgha": [2.4, 2.4], "loss_gha": [0.0, 0.1], "loss_pred": [0.0, 0.2]})
    out = models.alarm_by_share_of_dose(P, limits_pct=(0.5,))["0.5"]
    assert out == {"high_loss_days": 0, "alarms": 0, "precision": None, "recall": None,
                   "by_dose_kgha": {"2.4": {"high_loss_days": 0, "alarms": 0, "precision": None, "recall": None}}}
