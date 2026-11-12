"""Tests for runoffwatch.features (model inputs from daily weather)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from runoffwatch.features import (HISTORY_FEATURES, MIN_RAIN_MM, WEATHER_FEATURES, curve_number_today,
                                  run_feature_rows, weather_features)
from runoffwatch.przm_inp import SOIL_FEATURES

# 20 days, spraying on day 5 and day 14
RAIN = [0, 2, 0, 12, 0, 3, 1, 0, 15, 4, 0, 0, 7, 0, 5, 2, 11, 0, 0, 6]
APP1, APP2 = 5, 14


def small_daily(rain=RAIN, start="2021-02-20"):
    idx = pd.date_range(start, periods=len(rain), freq="D")
    return pd.DataFrame({"rain_mm": np.asarray(rain, float),
                         "temp_c": np.linspace(-2, 8, len(rain)),
                         "pan_evap_mm": np.linspace(0.5, 2.0, len(rain))}, index=idx)


def random_daily(days=80, seed=0):
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2020-01-10", periods=days, freq="D")
    return pd.DataFrame({"rain_mm": np.where(rng.random(days) < 0.5, rng.gamma(1.5, 6, days), 0.0),
                         "temp_c": rng.normal(3, 4, days),
                         "pan_evap_mm": rng.uniform(0.2, 2.5, days)}, index=idx)


@pytest.fixture
def feats():
    d = small_daily()
    return d, weather_features(d, [d.index[APP1], d.index[APP2]], cn=(81, 81, 86, 91))


def test_all_feature_columns_present(feats):
    _, f = feats
    assert set(WEATHER_FEATURES + HISTORY_FEATURES) <= set(f.columns)


# --------------------------------------------------------------------------- #
# No future leakage
# --------------------------------------------------------------------------- #
def _assert_equal_nan(a: pd.DataFrame, b: pd.DataFrame):
    pd.testing.assert_frame_equal(a, b, check_exact=False, rtol=1e-12, atol=1e-12)


@pytest.mark.parametrize("k", [0, 3, 10, 21, 22, 23, 24, 40, 55, 79])
def test_no_future_leakage_from_rain(k):
    d = random_daily()
    apps = [d.index[22], d.index[50]]
    base = weather_features(d, apps, cn=(81, 81, 86, 91))
    d2 = d.copy()
    d2.iloc[k, d2.columns.get_loc("rain_mm")] += 37.0
    new = weather_features(d2, apps, cn=(81, 81, 86, 91))
    # earlier days are untouched
    _assert_equal_nan(base.iloc[:k], new.iloc[:k])
    # on day k itself only the features that are defined from today's rain may change:
    # rain_mm, cn_runoff_mm (curve-number runoff of today's rain) and, during the first three
    # days after a spraying, rain_first3d_after_app_mm
    changed = [c for c in base.columns
               if not np.isclose(base[c].iloc[k], new[c].iloc[k], equal_nan=True)]
    dsa = base["days_since_app"].iloc[k]
    allowed = {"rain_mm", "cn_runoff_mm"} | ({"rain_first3d_after_app_mm"} if 0 <= dsa <= 2 else set())
    assert "rain_mm" in changed and set(changed) <= allowed


@pytest.mark.parametrize("col", ["temp_c", "pan_evap_mm"])
@pytest.mark.parametrize("k", [5, 22, 30, 60])
def test_no_future_leakage_from_temp_and_evap(col, k):
    d = random_daily()
    apps = [d.index[22], d.index[50]]
    base = weather_features(d, apps)
    d2 = d.copy()
    d2.iloc[k, d2.columns.get_loc(col)] += 9.0
    new = weather_features(d2, apps)
    _assert_equal_nan(base.iloc[:k], new.iloc[:k])


# --------------------------------------------------------------------------- #
# Hand-checked values
# --------------------------------------------------------------------------- #
def test_rain_windows_exclude_today(feats):
    d, f = feats
    r = d["rain_mm"].to_numpy()
    assert np.isnan(f["rain_7d_mm"].iloc[0])
    for i in range(1, len(r)):
        assert f["rain_7d_mm"].iloc[i] == pytest.approx(r[max(0, i - 7):i].sum())
        assert f["rain_14d_mm"].iloc[i] == pytest.approx(r[max(0, i - 14):i].sum())
        assert f["rain_prev1_mm"].iloc[i] == r[i - 1]
    for i in range(3, len(r)):
        assert f["rain_prev2_3_mm"].iloc[i] == r[i - 2] + r[i - 3]
    np.testing.assert_array_equal(f["rain_mm"].to_numpy(), r)


def test_days_since_app_counts_up_and_resets(feats):
    _, f = feats
    dsa = f["days_since_app"].to_numpy()
    assert np.isnan(dsa[:APP1]).all()
    np.testing.assert_array_equal(dsa[APP1:APP2], np.arange(APP2 - APP1))
    np.testing.assert_array_equal(dsa[APP2:], np.arange(len(dsa) - APP2))


def test_history_features_nan_before_first_spraying(feats):
    _, f = feats
    assert f[HISTORY_FEATURES].iloc[:APP1].isna().all().all()
    assert f[HISTORY_FEATURES].iloc[APP1:].notna().all().all()
    # weather features are filled in before the first spraying too
    assert f["rain_7d_mm"].iloc[1:APP1].notna().all()


def test_rain_since_app_sums_spray_day_to_yesterday(feats):
    d, f = feats
    r = d["rain_mm"].to_numpy()
    for i in range(APP1, APP2):
        assert f["rain_since_app_mm"].iloc[i] == pytest.approx(r[APP1:i].sum())
        assert f["heavy_rain_days_since_app"].iloc[i] == (r[APP1:i] >= 10).sum()
    for i in range(APP2, len(r)):
        assert f["rain_since_app_mm"].iloc[i] == pytest.approx(r[APP2:i].sum())
        assert f["heavy_rain_days_since_app"].iloc[i] == (r[APP2:i] >= 10).sum()
    assert f["rain_since_app_mm"].iloc[APP1] == 0
    assert f["rain_since_app_mm"].iloc[APP2] == 0          # reset at the second spraying


def test_rain_first3d_after_app(feats):
    d, f = feats
    r = d["rain_mm"].to_numpy()
    got = f["rain_first3d_after_app_mm"].to_numpy()
    # running sum over the spray day and the 2 days after it (today included), then constant
    assert got[APP1] == r[APP1]
    assert got[APP1 + 1] == r[APP1] + r[APP1 + 1]
    for i in range(APP1 + 2, APP2):
        assert got[i] == r[APP1:APP1 + 3].sum()
    assert got[APP2] == r[APP2]                             # reset
    for i in range(APP2 + 2, len(r)):
        assert got[i] == r[APP2:APP2 + 3].sum()


def test_temp_since_app(feats):
    d, f = feats
    t = d["temp_c"].to_numpy()
    assert f["temp_since_app_c"].iloc[APP1] == pytest.approx(t[APP1])
    for i in range(APP1 + 1, APP2):
        assert f["temp_since_app_c"].iloc[i] == pytest.approx(t[APP1:i].mean())


def test_frozen_precip_counts_only_cold_days_before_today():
    d = small_daily(rain=[4, 4, 4, 4, 4])
    d["temp_c"] = [-1.0, 2.0, 0.0, -3.0, 5.0]
    f = weather_features(d, [])
    np.testing.assert_allclose(f["frozen_precip_30d_mm"].to_numpy(), [np.nan, 4, 4, 8, 12], equal_nan=True)


def test_app_date_outside_table_is_ignored():
    d = small_daily()
    f = weather_features(d, [pd.Timestamp("2000-01-01")])
    assert f[HISTORY_FEATURES].isna().all().all()


def test_cn_today_none_is_nan():
    d = small_daily()
    assert weather_features(d, [d.index[2]])["cn_today"].isna().all()


@pytest.mark.parametrize("date, expected", [
    ("2021-01-15", 70), ("2021-06-09", 70), ("2021-06-10", 75), ("2021-07-30", 75),
    ("2021-07-31", 80), ("2021-10-31", 80), ("2021-11-01", 90), ("2021-11-11", 90),
    ("2021-11-12", 70), ("2021-12-31", 70),
])
def test_curve_number_today_switch_dates(date, expected):
    out = curve_number_today(pd.DatetimeIndex([date]), (70, 75, 80, 90))
    assert out[0] == expected


def test_cn_today_in_weather_features():
    idx = pd.date_range("2021-06-08", "2021-06-12")
    d = pd.DataFrame({"rain_mm": 0.0, "temp_c": 10.0, "pan_evap_mm": 3.0}, index=idx)
    f = weather_features(d, [], cn=(70, 75, 80, 90))
    assert f["cn_today"].tolist() == [70, 70, 75, 75, 75]


def test_missing_columns_raise():
    d = small_daily().drop(columns="pan_evap_mm")
    with pytest.raises(ValueError, match="columns"):
        weather_features(d, [])


def test_gap_in_dates_raises():
    d = small_daily().drop(index=small_daily().index[7])
    with pytest.raises(ValueError, match="gaps"):
        weather_features(d, [])


def test_unsorted_dates_raise():
    d = small_daily().iloc[::-1]
    with pytest.raises(ValueError):
        weather_features(d, [])


# --------------------------------------------------------------------------- #
# run_feature_rows
# --------------------------------------------------------------------------- #
def _params():
    p = {c: float(i) for i, c in enumerate(SOIL_FEATURES)}
    p.update(cn_1=81, cn_2=81, cn_3=86, cn_4=91)
    return p


def _run_daily(days=120, seed=1):
    d = random_daily(days, seed)
    d.loc[d.index[::4], "rain_mm"] = 6.0                 # plenty of rain days
    d.loc[d.index[1::4], "rain_mm"] = 0.4                # some drizzle below 1 mm
    d["runoff_mm"] = (d["rain_mm"] - 10).clip(lower=0) * 0.2
    d["pest_runoff_gha"] = d["runoff_mm"] * 0.5
    d["applied_gha"] = 0.0
    d.loc[d.index[[30, 95]], "applied_gha"] = 2400.0
    return d


def test_run_feature_rows_only_rain_days_and_targets():
    d = _run_daily()
    rows = run_feature_rows(d, _params(), pd.Timestamp("2020-03-20"))
    assert (rows["rain_mm"] >= MIN_RAIN_MM).all()
    # all rain days except those in the first three calendar days of the run
    rain_days = d.index[(d["rain_mm"] >= MIN_RAIN_MM) & (d.index >= d.index[3])]
    assert list(rows.index) == list(rain_days)
    pd.testing.assert_series_equal(rows["runoff_mm"], d.loc[rows.index, "runoff_mm"], check_names=False)
    pd.testing.assert_series_equal(rows["loss_gha"], d.loc[rows.index, "pest_runoff_gha"], check_names=False)
    params = _params()
    for c in SOIL_FEATURES:
        assert (rows[c] == params[c]).all()
    assert (rows["days_since_app"].dropna() >= 0).all()


def test_run_feature_rows_pest_clean_flag():
    d = _run_daily()
    first_app = d.index[30]
    clean_until = pd.Timestamp("2020-03-20")
    rows = run_feature_rows(d, _params(), clean_until)
    before = rows.index < first_app
    after_cu = rows.index >= clean_until
    assert before.any() and after_cu.any()
    assert not rows.loc[before, "pest_clean"].any()
    assert not rows.loc[after_cu, "pest_clean"].any()
    between = (~before) & (~after_cu)
    assert between.any() and rows.loc[between, "pest_clean"].all()


def test_run_feature_rows_no_clean_until_means_never_clean():
    rows = run_feature_rows(_run_daily(), _params(), None)
    assert not rows["pest_clean"].astype(bool).any()


def test_run_feature_rows_drops_first_three_days_not_first_three_rain_days():
    # Only the first three calendar days are dropped (no rain history yet). After a long dry
    # start, the first rain day is kept.
    d = _run_daily()
    d.iloc[:40, d.columns.get_loc("rain_mm")] = 0.0
    rows = run_feature_rows(d, _params(), None)
    rain_days = d.index[d["rain_mm"] >= MIN_RAIN_MM]
    assert rows.index[0] == rain_days[0]
    assert rows.index[0] >= d.index[40]
