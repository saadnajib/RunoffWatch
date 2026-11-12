"""Tests for runoffwatch.quality (folder status and the envelope rule)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from runoffwatch import quality
from runoffwatch.quality import (BIN_DAYS, ENVELOPE_FACTOR, ENVELOPE_QUANTILE, app_year, clean_until_dates,
                                 envelope_limit, fit_envelope, folder_status)


# --------------------------------------------------------------------------- #
# Application year
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("date, year", [
    ("1991-02-28", 1990), ("1991-03-01", 1991), ("1990-03-01", 1990), ("1991-01-01", 1990),
    ("1992-02-29", 1991), ("1991-12-31", 1991),
])
def test_app_year(date, year):
    assert app_year(pd.DatetimeIndex([date]))[0] == year


def test_app_year_accepts_series():
    s = pd.Series(pd.to_datetime(["1991-02-28", "1991-03-01"]))
    np.testing.assert_array_equal(app_year(s), [1990, 1991])


# --------------------------------------------------------------------------- #
# Envelope
# --------------------------------------------------------------------------- #
def synthetic_events(seed=0, n_runs=20):
    """Runoff events of healthy runs: loss per mm falls with days since spraying."""
    rng = np.random.default_rng(seed)
    rows = []
    for r in range(n_runs):
        for year in (1990, 1991):
            dsa = np.sort(rng.integers(0, 365, 40))
            dates = pd.Timestamp(f"{year}-03-01") + pd.to_timedelta(dsa, unit="D")
            runoff = rng.uniform(0.1, 5, len(dsa))
            lpm = 2.0 * np.exp(-0.03 * dsa) * rng.lognormal(0, 0.3, len(dsa))
            rows.append(pd.DataFrame({"run": f"run_{r:03d}", "date": dates, "days_since_app": dsa.astype(float),
                                      "runoff_mm": runoff, "pest_runoff_gha": lpm * runoff}))
    ev = pd.concat(rows, ignore_index=True)
    ev["app_year"] = app_year(ev["date"])
    ev["loss_per_mm"] = ev["pest_runoff_gha"] / ev["runoff_mm"]
    return ev


def test_fit_envelope_non_increasing_and_first_bin():
    ev = synthetic_events()
    env = fit_envelope(ev)
    assert env.index.name == "dsa_bin"
    assert env.index[0] == 0 and env.index[-1] == 366 // BIN_DAYS
    assert (np.diff(env.to_numpy()) <= 0).all()
    ref = ev[(ev["app_year"] == 1990) & (ev["days_since_app"] < BIN_DAYS)]
    expected = ENVELOPE_FACTOR * np.quantile(ref["loss_per_mm"], ENVELOPE_QUANTILE)
    assert env.iloc[0] == pytest.approx(expected)


def test_fit_envelope_uses_reference_year_only():
    ev = synthetic_events()
    ev.loc[ev["app_year"] == 1991, "loss_per_mm"] *= 1000      # later years must not matter
    assert fit_envelope(ev).equals(fit_envelope(synthetic_events()))
    with pytest.raises(ValueError):
        fit_envelope(ev, ref_app_year=1980)


def test_envelope_limit_clips_bins():
    env = pd.Series([10.0, 5.0, 1.0], index=pd.RangeIndex(3, name="dsa_bin"))
    got = envelope_limit([0, 14, 15, 29, 30, 999, np.nan], env)
    np.testing.assert_array_equal(got, [10, 10, 5, 5, 1, 1, 10])


def test_clean_until_dates():
    env = pd.Series(np.full(366 // BIN_DAYS + 1, 1.0), index=pd.RangeIndex(366 // BIN_DAYS + 1, name="dsa_bin"))
    ev = pd.DataFrame({
        "run": ["bad", "bad", "bad", "good", "good"],
        "app_year": [1993, 1995, 1997, 1990, 1998],
        "days_since_app": [10.0, 40.0, 5.0, 3.0, 100.0],
        "loss_per_mm": [0.5, 3.0, 9.0, 0.9, 0.2],          # bad: first above envelope in 1995
    })
    last = pd.Series({"bad": 1999, "good": 1999})
    out = clean_until_dates(ev, env, last)
    assert out.loc["bad", "first_bad_app_year"] == 1995
    assert out.loc["bad", "clean_until"] == pd.Timestamp("1994-03-01")        # guard of one year
    assert pd.isna(out.loc["good", "first_bad_app_year"])
    assert out.loc["good", "clean_until"] == pd.Timestamp("1999-03-01")      # last year never trusted
    assert quality.GUARD_YEARS == 1


def test_clean_until_ignores_events_before_first_spraying():
    env = pd.Series(np.full(366 // BIN_DAYS + 1, 1.0), index=pd.RangeIndex(366 // BIN_DAYS + 1, name="dsa_bin"))
    ev = pd.DataFrame({"run": ["a"], "app_year": [1992], "days_since_app": [np.nan], "loss_per_mm": [50.0]})
    out = clean_until_dates(ev, env, pd.Series({"a": 1995}))
    assert out.loc["a", "clean_until"] == pd.Timestamp("1995-03-01")


# --------------------------------------------------------------------------- #
# Folder status
# --------------------------------------------------------------------------- #
def test_folder_status(tmp_path):
    from conftest import build_run, write_log

    batch = tmp_path / "runs" / "run_000000_to_000999"
    batch.mkdir(parents=True)

    nf = batch / "run_0000001_grid_000001"
    nf.mkdir()
    write_log(nf / "mc.log", error=True)

    no = batch / "run_0000002_grid_000002"
    no.mkdir()
    write_log(no / "mc.log", error=False)
    (no / "Run 1-1_a1.inp").write_text("Run 1\n")
    (no / "focusprzm_weather.met").write_text(" 010190  0.0 0.0 0.0 0.0 0.0\n")

    em = batch / "run_0000003_grid_000003"
    em.mkdir()
    (em / "Run 1-1_a1.inp").write_text("Run 1\n")
    (em / "RUN 1-1_A1.ZTS").write_text(" TSRTIME SERIES OUTPUT FILES\n TSR  Run 1\n")

    build_run(batch, name="run_0000004_grid_000004", days=30)

    (tmp_path / "runs" / "notes.txt").write_text("not a batch folder")
    st = folder_status(tmp_path / "runs").set_index("run")
    assert st["status"].to_dict() == {
        "run_0000001_grid_000001": "no_field",
        "run_0000002_grid_000002": "no_output",
        "run_0000003_grid_000003": "empty_output",
        "run_0000004_grid_000004": "has_output",
    }
    assert (st["batch"] == "run_000000_to_000999").all()
