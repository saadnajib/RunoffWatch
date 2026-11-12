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
    assert (days.loc[dry, ["runoff_mm", "loss_gha", "high_loss_chance"]] == 0).all().all()
    assert (days[["runoff_mm", "loss_gha", "high_loss_chance"]] >= 0).all().all()
    assert (days["high_loss_chance"] <= 1).all()
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
    assert out["rank"].between(1, len(cands)).all()
    assert out["rank"].min() == 1
    assert (out["predicted_loss_gha"] >= 0).all()
    assert out["chance_of_high_loss_day"].between(0, 1).all()
    assert out["days_covered"].tolist() == [14, 14, 14, 14, 6]     # weather ends 4 April
    best = out.loc[out["rank"] == 1, "predicted_loss_gha"]
    assert (best <= out["predicted_loss_gha"].min()).all()


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
