"""Tests for runoffwatch.przm_spikes on small hand-made daily tables."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from runoffwatch.przm_io import read_run
from runoffwatch.przm_spikes import daily_features, flag_spikes, spike_probability, summarize


def _frame(rain, pest=None, applied=None, runoff=None, start="1995-03-01"):
    idx = pd.date_range(start, periods=len(rain), freq="D", name="date")
    df = pd.DataFrame({"rain_mm": np.asarray(rain, dtype=float)}, index=idx)
    if pest is not None:
        df["pest_runoff_gha"] = np.asarray(pest, dtype=float)
    if applied is not None:
        df["applied_gha"] = np.asarray(applied, dtype=float)
    if runoff is not None:
        df["runoff_mm"] = np.asarray(runoff, dtype=float)
    return df


# --------------------------------------------------------------------------- daily_features

def test_antecedent_rain_excludes_today():
    rain = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
    f = daily_features(_frame(rain), antecedent_days=3)
    ant = f["antecedent_3d_mm"]
    assert ant.iloc[:3].isna().all()                 # not enough history yet
    # day 3 (rain 4) -> 1+2+3 ; today's rain never included
    assert ant.iloc[3] == 6
    assert ant.iloc[9] == 7 + 8 + 9
    assert f["rain_prev1_mm"].iloc[5] == 5
    assert np.isnan(f["rain_prev1_mm"].iloc[0])
    assert f["rain_prev2_3_mm"].iloc[5] == 4 + 3
    assert list(f["month"].unique()) == [3]


def test_antecedent_default_seven_days():
    f = daily_features(_frame([10.0] + [0.0] * 9))
    ant = f["antecedent_7d_mm"]
    assert ant.iloc[:7].isna().all()
    assert ant.iloc[7] == 10.0                       # days 0..6
    assert ant.iloc[8] == 0.0                        # day 0 has left the window


def test_daily_features_does_not_modify_input():
    df = _frame([1, 2, 3], applied=[0, 1, 0])
    before = df.copy()
    daily_features(df)
    pd.testing.assert_frame_equal(df, before)


def test_days_since_app_counts_from_last_application():
    applied = [0, 0, 100, 0, 0, 0, 100, 0, 0]
    f = daily_features(_frame([0] * 9, applied=applied))
    d = f["days_since_app"]
    assert d.iloc[:2].isna().all()                   # NaN before the first application
    assert d.iloc[2:].tolist() == [0, 1, 2, 3, 0, 1, 2]


def test_days_since_app_absent_without_applied_column():
    assert "days_since_app" not in daily_features(_frame([1, 2]))


# --------------------------------------------------------------------------- flag_spikes

def test_flag_spikes_top_ten_percent_of_nonzero_days():
    pest = [0.0] * 30 + list(range(1, 21))          # 20 non-zero days: 1..20
    out = flag_spikes(_frame([5] * 50, pest=pest))
    thr = pd.Series(range(1, 21), dtype=float).quantile(0.9)
    assert out.attrs["spike_threshold"] == pytest.approx(thr)
    assert out["is_spike"].sum() == 2               # 10% of 20
    assert out.loc[out["is_spike"], "pest_runoff_gha"].tolist() == [19, 20]
    assert out["is_runoff_event"].sum() == 20
    # zero days never count, no matter how many there are
    assert not out.loc[out["pest_runoff_gha"] == 0, "is_spike"].any()


def test_flag_spikes_abs_floor_raises_threshold():
    pest = [0.0] * 5 + list(range(1, 21))
    df = _frame([5] * 25, pest=pest)
    out = flag_spikes(df, abs_floor=19.5)
    assert out.attrs["spike_threshold"] == 19.5
    assert out["is_spike"].sum() == 1
    # a floor below the quantile does not lower the threshold
    low = flag_spikes(df, abs_floor=1.0)
    assert low.attrs["spike_threshold"] == pytest.approx(flag_spikes(df).attrs["spike_threshold"])
    assert low["is_spike"].sum() == 2


def test_flag_spikes_all_zero_series():
    out = flag_spikes(_frame([5] * 10, pest=[0.0] * 10))
    assert not out["is_spike"].any()
    assert np.isnan(out.attrs["spike_threshold"])


def test_spike_probability_after_all_zero_flag():
    out = flag_spikes(_frame([5] * 10, pest=[0.0] * 10))
    res = spike_probability(out, by="rain_mm", bins=[0, 10, 100])
    assert res["spike_days"].sum() == 0


# --------------------------------------------------------------------------- spike_probability

def test_spike_probability_uses_only_rain_days():
    rain = [0.0, 0.5, 0.9, 1.0, 3.0, 4.0, 20.0, 30.0, 40.0, 50.0]
    pest = [9.0, 9.0, 9.0, 0.0, 0.0, 1.0, 2.0, 3.0, 4.0, 10.0]
    df = flag_spikes(_frame(rain, pest=pest), top_fraction=0.25)
    # dry days (< 1 mm) are large on purpose: they must be ignored
    res = spike_probability(df, by="rain_mm", bins=[0, 5, 100])
    assert res["rain_days"].sum() == 7
    assert res["rain_days"].tolist() == [3, 4]      # 1.0, 3.0, 4.0 | 20, 30, 40, 50
    assert res["runoff_days"].tolist() == [1, 4]
    assert res["total_pest_runoff_gha"].tolist() == [1.0, 19.0]
    rainy = df[df["rain_mm"] >= 1]
    exp_spikes = [int(rainy["is_spike"][rainy["rain_mm"] <= 5].sum()),
                  int(rainy["is_spike"][rainy["rain_mm"] > 5].sum())]
    assert res["spike_days"].tolist() == exp_spikes
    assert res["spike_chance_%"].tolist() == pytest.approx(
        [round(100 * s / n, 1) for s, n in zip(exp_spikes, [3, 4])])


def test_spike_probability_by_other_feature_keeps_empty_bins():
    df = _frame([5.0] * 4, pest=[0.0, 1.0, 2.0, 10.0])
    df["days_since_app"] = [0, 1, 2, 3]
    df = flag_spikes(df)
    res = spike_probability(df, by="days_since_app", bins=[0, 1, 3, 100])
    assert len(res) == 3                             # observed=False keeps empty bin
    assert res["rain_days"].tolist() == [2, 2, 0]
    assert res["spike_days"].tolist() == [0, 1, 0]


# --------------------------------------------------------------------------- summarize

SUMMARY_KEYS = {"days", "rain_days_>=1mm", "runoff_days", "pesticide_runoff_days", "spike_days",
                "spike_threshold_gha", "applied_total_gha", "pest_runoff_total_gha",
                "share_in_top5_days_%"}


def test_summarize_keys_and_top5_share():
    pest = [10.0, 8.0, 6.0, 4.0, 2.0, 1.0, 1.0, 1.0, 1.0, 1.0] + [0.0] * 10
    rain = [12.0] * 10 + [0.5] * 5 + [0.0] * 5
    runoff = [p * 0.5 for p in pest]
    applied = [0.0] * 20
    applied[0] = 1000.0
    df = flag_spikes(_frame(rain, pest=pest, applied=applied, runoff=runoff))
    s = summarize(df)
    assert set(s) == SUMMARY_KEYS
    assert s["days"] == 20
    assert s["rain_days_>=1mm"] == 10
    assert s["runoff_days"] == 10
    assert s["pesticide_runoff_days"] == 10
    assert s["spike_days"] == int(df["is_spike"].sum())
    assert s["spike_threshold_gha"] == round(df.attrs["spike_threshold"], 3)
    assert s["applied_total_gha"] == 1000.0
    assert s["pest_runoff_total_gha"] == 35.0
    assert s["share_in_top5_days_%"] == round(100 * 30 / 35, 1)     # 85.7


def test_summarize_all_zero_runoff():
    df = flag_spikes(_frame([5.0] * 5, pest=[0.0] * 5, runoff=[0.0] * 5))
    s = summarize(df)
    assert s["spike_days"] == 0
    assert s["pest_runoff_total_gha"] == 0
    assert np.isnan(s["share_in_top5_days_%"])
    assert np.isnan(s["spike_threshold_gha"])
    assert np.isnan(s["applied_total_gha"])          # no applied column


# --------------------------------------------------------------------------- end to end

def test_pipeline_on_synthetic_run(make_run):
    df = read_run(make_run(days=60).folder)
    f = flag_spikes(daily_features(df))
    s = summarize(f)
    assert set(s) == SUMMARY_KEYS
    assert s["days"] == 60
    assert s["applied_total_gha"] == pytest.approx(2400.0)
    assert f["days_since_app"].iloc[:5].isna().all() and f["days_since_app"].iloc[5] == 0
    res = spike_probability(f, by="antecedent_7d_mm", bins=[0, 5, 10, 50])
    assert res["rain_days"].sum() <= s["rain_days_>=1mm"]
