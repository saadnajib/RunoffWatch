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


# --------------------------------------------------------------------------- #
# Balance errors and the two trust rules (build_run_quality, audit)
# --------------------------------------------------------------------------- #
TOL = quality.BALANCE_TOLERANCE
# run name -> extra arguments for conftest.build_run; two years, sprayed on 1 March 1990 and 1991
BALANCE_RUNS = {
    "run_0000001_grid_000001": dict(balance=[1e-8, 2e-8]),             # clean
    "run_0000002_grid_000002": dict(balance=[1e-8, 5.0]),              # large error in year 2
    "run_0000003_grid_000003": dict(balance=[1e-8, 1e-8], zts_days=300),  # small errors, but crashed
    "run_0000004_grid_000004": dict(),                                 # no balance lines at all
    "run_0000005_grid_000005": dict(balance=[1e-8, "NaN"]),            # NaN counts as infinitely large
    "run_0000006_grid_000006": dict(balance=[-TOL / 2, 1e-7]),         # negative: the size counts
    "run_0000007_grid_000007": dict(balance=[TOL, 1e-9]),              # exactly at the tolerance
    **{f"run_00000{i}_grid_0000{i}": dict(balance=[1e-8, 1e-8]) for i in range(10, 14)},  # more clean runs
}
TRUSTED = {"run_0000001_grid_000001", "run_0000006_grid_000006", "run_0000007_grid_000007",
           *(f"run_00000{i}_grid_0000{i}" for i in range(10, 14))}


@pytest.fixture(scope="module")
def balance_data(tmp_path_factory):
    """Run folders plus the `inventory` and `qc` output that build_run_quality needs."""
    from conftest import build_run, full_inp_lines

    from runoffwatch import batch

    tmp = tmp_path_factory.mktemp("balance")
    root = tmp / "runs"
    for i, (name, kw) in enumerate(BALANCE_RUNS.items()):
        build_run(root / "run_000000_to_000999", name=name, days=730, app_days=(59, 424),
                  inp_lines=full_inp_lines(slope=1 + i), **kw)
    runs = batch.find_runs(root)
    interim = tmp / "interim"
    interim.mkdir()
    batch.inventory(runs)[0].to_csv(interim / "inventory_runs.csv", index=False)
    # qc_run one by one: the same rows qc_all writes, without starting worker processes
    pd.DataFrame([batch.qc_run(r, interim / "daily") for r in runs]).to_csv(interim / "runs_qc.csv", index=False)
    return root, interim


@pytest.fixture(scope="module")
def rq_envelope(balance_data):
    return quality.build_run_quality(*balance_data)[0]


@pytest.fixture(scope="module")
def rq_balance(balance_data):
    return quality.build_run_quality(*balance_data, trust="balance")[0]


def test_balance_error_table(balance_data):
    from runoffwatch.batch import find_runs

    t = quality.balance_error_table(find_runs(balance_data[0]))
    assert t["run_0000001_grid_000001"] == pytest.approx(2e-8)
    assert t["run_0000002_grid_000002"] == pytest.approx(5.0)
    assert np.isnan(t["run_0000004_grid_000004"])
    assert t["run_0000005_grid_000005"] == np.inf
    assert t["run_0000006_grid_000006"] == pytest.approx(TOL / 2)      # absolute value


def test_build_run_quality_rejects_unknown_rule(balance_data):
    with pytest.raises(ValueError, match="trust"):
        quality.build_run_quality(*balance_data, trust="other")


@pytest.mark.parametrize("mode", ["envelope", "balance"])
def test_new_columns_in_both_modes(mode, rq_envelope, rq_balance):
    rq = rq_envelope if mode == "envelope" else rq_balance
    assert {"max_balance_error", "above_envelope_app_year"} <= set(rq.columns)
    assert rq.loc["run_0000002_grid_000002", "max_balance_error"] == pytest.approx(5.0)
    assert rq.loc["run_0000003_grid_000003", "crashed"]


def test_envelope_mode_is_unchanged(rq_envelope):
    pd.testing.assert_series_equal(rq_envelope["above_envelope_app_year"], rq_envelope["first_bad_app_year"],
                                   check_names=False)
    # the envelope rule does not look at balance errors: the run with error 5 kg/ha keeps its clean years
    assert rq_envelope.loc["run_0000002_grid_000002", "clean_until"] == pd.Timestamp("1991-03-01")


def test_balance_mode_keeps_envelope_result_for_information(rq_envelope, rq_balance):
    pd.testing.assert_series_equal(rq_balance["above_envelope_app_year"], rq_envelope["above_envelope_app_year"])


def test_balance_mode_trusts_clean_runs_to_the_end(rq_balance):
    for run in sorted(TRUSTED):
        row = rq_balance.loc[run]
        assert row["clean_until"] == pd.Timestamp(row["end"]) + pd.Timedelta(days=1), run
        assert row["clean_until"] == pd.Timestamp("1992-01-01"), run
        assert np.isnan(row["first_bad_app_year"]), run


@pytest.mark.parametrize("run", ["run_0000002_grid_000002",     # large balance error
                                 "run_0000003_grid_000003",     # crashed
                                 "run_0000004_grid_000004",     # no balance error reported
                                 "run_0000005_grid_000005"])    # NaN balance error
def test_balance_mode_does_not_trust(run, rq_balance):
    row = rq_balance.loc[run]
    assert pd.isna(row["clean_until"])
    assert not np.isnan(row["first_bad_app_year"])
    assert pd.isna(row["clean_years"])


def test_balance_mode_trusted_set(rq_balance):
    assert set(rq_balance.index[rq_balance["clean_until"].notna()]) == TRUSTED


def test_balance_mode_clean_years_not_more_than_pesticide_years(rq_balance):
    t = rq_balance[rq_balance["clean_until"].notna()]
    assert (t["clean_years"] <= t["pesticide_years"]).all(), t[["clean_years", "pesticide_years"]]


@pytest.fixture(scope="module")
def audit_balance(balance_data, tmp_path_factory):
    import warnings

    out = tmp_path_factory.mktemp("audit")
    with warnings.catch_warnings(), np.errstate(all="ignore"):
        warnings.simplefilter("ignore")            # tiny synthetic data: undefined AUC, tight layout
        s = quality.audit(*balance_data, results=out / "results", figures=out / "figures", trust="balance")
    return s, out


def test_audit_balance_summary(audit_balance, balance_data):
    s, out = audit_balance
    assert s["trust_rule"] == "balance"
    assert s["balance_tolerance_kgha"] == TOL
    assert s["trusted_runs"] == len(TRUSTED)
    assert s["runs_with_balance_error_above_tolerance"] == 2      # the 5 kg/ha run and the NaN run
    assert (out / "results" / "quality_summary.json").exists()
    rq = pd.read_csv(balance_data[1] / "run_quality.csv", index_col="run")
    assert {"max_balance_error", "above_envelope_app_year"} <= set(rq.columns)
    assert set(rq.index[rq["clean_until"].notna()]) == TRUSTED


def test_audit_balance_quantiles_keep_the_largest_error(audit_balance):
    s, _ = audit_balance
    # one run reports NaN, which counts as infinitely large: the maximum must say so
    assert s["balance_error_quantiles_kgha"]["1.0"] == np.inf
