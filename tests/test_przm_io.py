"""Tests for runoffwatch.przm_io on small synthetic PRZM_SW run folders."""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd
import pytest

from conftest import (APPLIED_G_PER_CM2, ZTS_VARS, met_line, write_inp, write_out,
                      zts_header, zts_line)
from runoffwatch import przm_io
from runoffwatch.przm_io import (LANGLEY_TO_MJ, check_soil_decay, read_met, read_run, read_zts,
                                 read_zts_scale_factors)

LOGGER = "runoffwatch"


def _warnings(caplog, text):
    return [r for r in caplog.records
            if r.name == LOGGER and r.levelno >= logging.WARNING and text in r.getMessage()]


# --------------------------------------------------------------------------- .met

def test_read_met_unit_conversion(make_run):
    run = make_run(days=20)
    met = read_met(run.files["met"])
    raw = run.met
    assert list(met.columns) == ["rain_mm", "pan_evap_mm", "temp_c", "wind_ms", "solar_mj"]
    np.testing.assert_allclose(met["rain_mm"], raw["rain_cm"] * 10)          # cm -> mm
    np.testing.assert_allclose(met["pan_evap_mm"], raw["evap_cm"] * 10)
    np.testing.assert_allclose(met["temp_c"], raw["temp_c"])
    np.testing.assert_allclose(met["wind_ms"], raw["wind_cms"] / 100)         # cm/s -> m/s
    np.testing.assert_allclose(met["solar_mj"], raw["solar_ly"] * 0.04184)    # ly -> MJ/m2
    assert LANGLEY_TO_MJ == pytest.approx(0.04184)
    # spot values: 0.5 cm -> 5 mm, 300 cm/s -> 3 m/s, 250 ly -> 10.46 MJ/m2
    assert met["rain_mm"].iloc[3] == pytest.approx(5.0)
    assert met["wind_ms"].iloc[0] == pytest.approx(3.0)
    assert met["solar_mj"].iloc[0] == pytest.approx(10.46)
    pd.testing.assert_index_equal(met.index, run.dates, check_names=False)
    assert met.index.name == "date"


@pytest.mark.parametrize("mmddyy, expected", [
    ("010190", "1990-01-01"),
    ("123199", "1999-12-31"),
    ("030105", "2005-03-01"),
    ("022800", "2000-02-28"),
    ("060149", "2049-06-01"),
    ("060150", "1950-06-01"),
])
def test_two_digit_years(mmddyy, expected):
    got = przm_io._two_digit_date(pd.Series([mmddyy]))
    assert got.iloc[0] == pd.Timestamp(expected)


def test_two_digit_date_restores_dropped_leading_zero():
    # a date written without its leading zero (e.g. read as an int) is zero-padded
    got = przm_io._two_digit_date(pd.Series([10190, "30105"]))
    assert list(got) == [pd.Timestamp("1990-01-01"), pd.Timestamp("2005-03-01")]


def test_read_met_two_digit_years_across_century(tmp_path):
    dates = pd.date_range("1999-12-30", "2000-01-02")
    p = tmp_path / "w.met"
    p.write_text("\n".join(met_line(d, 0.1, 0.05, 5.0, 300, 250) for d in dates) + "\n")
    met = read_met(p)
    assert list(met.index) == list(dates)


def test_read_met_too_few_columns_raises(tmp_path):
    p = tmp_path / "w.met"
    p.write_text(" 010190    0.2000    0.0480    5.9000  580.0000\n"
                 " 010290    0.0000    0.0490    6.5000  320.0000\n")
    with pytest.raises(ValueError, match="expected 6 columns"):
        read_met(p)


@pytest.mark.parametrize("days", [
    ["1990-01-02", "1990-01-01", "1990-01-03"],     # goes backwards
    ["1990-01-01", "1990-01-02", "1990-01-02"],     # duplicate
])
def test_read_met_non_increasing_dates_raises(tmp_path, days):
    p = tmp_path / "w.met"
    p.write_text("\n".join(met_line(pd.Timestamp(d), 0.1, 0.05, 5.0, 300, 250) for d in days) + "\n")
    with pytest.raises(ValueError, match="not strictly increasing"):
        read_met(p)


def test_read_met_negative_rain_raises(tmp_path):
    p = tmp_path / "w.met"
    p.write_text(met_line(pd.Timestamp("1990-01-01"), 0.1, 0.05, 5.0, 300, 250) + "\n"
                 + met_line(pd.Timestamp("1990-01-02"), -0.1, 0.05, 5.0, 300, 250) + "\n")
    with pytest.raises(ValueError, match="negative rainfall"):
        read_met(p)


def test_read_met_missing_days_warns(tmp_path, caplog):
    days = [pd.Timestamp("1990-01-01"), pd.Timestamp("1990-01-02"), pd.Timestamp("1990-01-05")]
    p = tmp_path / "w.met"
    p.write_text("\n".join(met_line(d, 0.1, 0.05, 5.0, 300, 250) for d in days) + "\n")
    with caplog.at_level(logging.WARNING, logger=LOGGER):
        read_met(p)
    assert _warnings(caplog, "2 missing days")


# --------------------------------------------------------------------------- .inp / .ZTS

def test_read_zts_scale_factors(make_run):
    run = make_run(days=5)
    f = read_zts_scale_factors(run.files["inp"])
    assert f == {"RUNF": 10.0, "ESLS": 1e3, "PRCP": 10.0, "INFL": 10.0,
                 "RFLX1": 1e8, "EFLX1": 1e8, "TPAP": 1.0}


def test_read_zts_scale_factors_last_block_wins(tmp_path):
    # real .inp files repeat the TSER block; the last one is used
    p = tmp_path / "a.inp"
    p.write_text("    RUNF    TSER   0   0  10.0\n  other line\n    RUNF    TSER   0   0  100.0\n"
                 "    INFL    TSER 118 118  10.0\n")
    assert read_zts_scale_factors(p) == {"RUNF": 100.0, "INFL": 10.0}


def test_read_zts_unit_conversion(make_run):
    run = make_run(days=30)
    z = read_zts(run.files["zts"], run.files["inp"])
    w = run.zts                                            # values as written
    assert list(z.columns) == ["runoff_mm", "eroded_soil_t", "rain_mm", "infiltration_mm",
                               "pest_runoff_gha", "pest_erosion_gha", "applied_gha"]
    # PRCP/RUNF/INFL: written = cm * 10 -> /10 -> cm -> *10 -> mm (== written value)
    np.testing.assert_allclose(z["rain_mm"], w["PRCP"], rtol=1e-3)
    np.testing.assert_allclose(z["runoff_mm"], w["RUNF"], rtol=1e-3)
    np.testing.assert_allclose(z["infiltration_mm"], w["INFL"], rtol=1e-3)
    # ESLS: written = t * 1e3
    np.testing.assert_allclose(z["eroded_soil_t"], w["ESLS"] / 1e3, rtol=1e-3)
    # RFLX1/EFLX1: written = g/cm2 * 1e8 -> /1e8 -> g/cm2 -> *1e8 -> g/ha (== written value)
    np.testing.assert_allclose(z["pest_runoff_gha"], w["RFLX1"], rtol=1e-3)
    np.testing.assert_allclose(z["pest_erosion_gha"], w["EFLX1"], rtol=1e-3)
    # TPAP: written = g/cm2 * 1.0 -> g/ha = * 1e8 ; 2.4e-5 g/cm2 = 2400 g/ha = 2.4 kg/ha
    assert z["applied_gha"].iloc[5] == pytest.approx(APPLIED_G_PER_CM2 * 1e8)
    assert z["applied_gha"].iloc[5] == pytest.approx(2400.0)
    assert z["applied_gha"].drop(z.index[5]).eq(0).all()
    assert z.index.name == "date"
    assert z.index[0] == pd.Timestamp("1990-01-01")


def test_read_zts_rflx_with_other_factor(tmp_path):
    """The conversion divides by the factor first: RFLX1 0.3796 g/ha written with
    factor 1.0 appears as 3.796e-9 (raw g/cm2) and must still give 0.3796 g/ha."""
    d = pd.Timestamp("1991-03-01")
    zts = tmp_path / "x.ZTS"
    zts.write_text("\n".join(zts_header(names=["RUNF", "RFLX1"])
                             + [zts_line(d, [2.449, 3.796e-9])]) + "\n")
    inp = tmp_path / "x.inp"
    write_inp(inp, {"RUNF": "100.0", "RFLX1": "1.0"})
    z = read_zts(zts, inp)
    assert z.loc[d, "pest_runoff_gha"] == pytest.approx(0.3796)
    assert z.loc[d, "runoff_mm"] == pytest.approx(0.2449)       # 2.449 / 100 cm * 10


def test_read_zts_parses_fortran_e_notation(tmp_path):
    zts = tmp_path / "x.ZTS"
    zts.write_text("\n".join(zts_header()) + "\n"
                   " TSR PRZ  1991  3  1          0.2449        0.3445E-01     14.00         12.78"
                   "        0.3796        0.3405E-03    0.2400E-04\n")
    inp = tmp_path / "x.inp"
    write_inp(inp, {"RUNF": "10.0", "ESLS": "1.E3", "PRCP": "10.0", "INFL": "10.0",
                    "RFLX1": "1.E8", "EFLX1": "1.E8", "TPAP": "1.0"})
    row = read_zts(zts, inp).iloc[0]
    assert row["eroded_soil_t"] == pytest.approx(3.445e-5)
    assert row["pest_erosion_gha"] == pytest.approx(3.405e-4)
    assert row["applied_gha"] == pytest.approx(2400.0)
    assert row["rain_mm"] == pytest.approx(14.0)


def test_read_zts_without_factors_warns_and_keeps_raw(make_run, caplog):
    run = make_run(days=10)
    with caplog.at_level(logging.WARNING, logger=LOGGER):
        z = read_zts(run.files["zts"])
    assert list(z.columns) == ZTS_VARS
    np.testing.assert_allclose(z["TPAP"], run.zts["TPAP"], rtol=1e-3)
    assert len(_warnings(caplog, "no scale factor")) == len(ZTS_VARS)


def test_read_zts_no_data_rows_raises(tmp_path):
    zts = tmp_path / "x.ZTS"
    zts.write_text("\n".join(zts_header()) + "\n")
    with pytest.raises(ValueError, match="no data rows"):
        read_zts(zts)


def test_read_zts_no_header_raises(tmp_path):
    zts = tmp_path / "x.ZTS"
    zts.write_text(" some other file\n TSR PRZ  1990  1  1   0.000   1.000\n")
    with pytest.raises(ValueError, match="no variable header"):
        read_zts(zts)


def test_read_zts_title_containing_variable_name(tmp_path):
    zts = tmp_path / "x.ZTS"
    zts.write_text("\n".join(zts_header(title="PRCP sensitivity run")
                             + [zts_line(pd.Timestamp("1990-01-01"), [0, 0, 2.0, 1.6, 0, 0, 0])]) + "\n")
    z = read_zts(zts)
    assert list(z.columns) == ZTS_VARS


# --------------------------------------------------------------------------- .OUT

def test_check_soil_decay_stable(tmp_path):
    p = tmp_path / "a.OUT"
    write_out(p, [0.169, 0.31, 0.42, 0.47, 0.49, 0.5])
    assert check_soil_decay(p) is False


def test_check_soil_decay_blow_up(tmp_path, caplog):
    p = tmp_path / "a.OUT"
    write_out(p, [0.169, 0.31, 0.64, 1.9, 8.87, 82.1, 996.6, 7076.5])
    with caplog.at_level(logging.ERROR, logger=LOGGER):
        assert check_soil_decay(p) is True
    assert any("NUMERICAL BLOW-UP" in r.getMessage() for r in caplog.records)


def test_check_soil_decay_single_jump_is_not_unstable(tmp_path):
    p = tmp_path / "a.OUT"
    write_out(p, [1.0, 1.2, 10.0, 11.0, 11.5])      # one >5x step only
    assert check_soil_decay(p) is False


def test_check_soil_decay_two_consecutive_jumps(tmp_path):
    p = tmp_path / "a.OUT"
    write_out(p, [1.0, 1.1, 6.0, 40.0])             # 5.45x then 6.7x
    assert check_soil_decay(p) is True


def test_check_soil_decay_too_few_years(tmp_path):
    p = tmp_path / "a.OUT"
    write_out(p, [1.0, 100.0])
    assert check_soil_decay(p) is False


def test_check_soil_decay_two_isolated_jumps_are_not_a_blow_up(tmp_path):
    p = tmp_path / "a.OUT"
    write_out(p, [1.0, 10.0, 10.5, 10.8, 100.0, 101.0, 102.0])
    assert check_soil_decay(p) is False


# --------------------------------------------------------------------------- read_run

def test_read_run_joins_weather_and_results(make_run):
    run = make_run(days=40)
    df = read_run(run.folder)
    assert len(df) == 40
    pd.testing.assert_index_equal(df.index, run.dates, check_names=False)
    for col in ["rain_mm", "pan_evap_mm", "temp_c", "wind_ms", "solar_mj", "runoff_mm",
                "eroded_soil_t", "infiltration_mm", "pest_runoff_gha", "pest_erosion_gha",
                "applied_gha", "snow_day"]:
        assert col in df.columns
    # rain comes from the .met (the ZTS copy is dropped), no duplicate column
    assert list(df.columns).count("rain_mm") == 1
    np.testing.assert_allclose(df["rain_mm"], run.met["rain_cm"] * 10)
    np.testing.assert_allclose(df["pest_runoff_gha"], run.zts["RFLX1"], rtol=1e-3)
    assert df["applied_gha"].sum() == pytest.approx(2400.0)
    assert df.attrs["run"] == run.folder.name
    assert df.attrs["unstable"] is False


def test_read_run_stable_run_has_no_warnings(make_run, caplog):
    run = make_run(days=40)
    with caplog.at_level(logging.WARNING, logger=LOGGER):
        df = read_run(run.folder)
    assert [r.getMessage() for r in caplog.records if r.levelno >= logging.WARNING] == []
    assert df.attrs["unstable"] is False
    assert df.attrs.get("mass_balance_ok", True) is True


def test_read_run_flags_unstable(make_run, caplog):
    run = make_run(days=20, unstable=True)
    with caplog.at_level(logging.WARNING, logger=LOGGER):
        df = read_run(run.folder)
    assert df.attrs["unstable"] is True
    assert any(r.levelno == logging.ERROR and "BLOW-UP" in r.getMessage() for r in caplog.records)


def test_read_run_without_out_file_has_no_unstable_attr(make_run):
    df = read_run(make_run(days=10, write_out_file=False).folder)
    assert "unstable" not in df.attrs


def test_read_run_short_zts_warns_about_overlap(make_run, caplog):
    run = make_run(days=40, zts_days=30)
    with caplog.at_level(logging.WARNING, logger=LOGGER):
        df = read_run(run.folder)
    assert len(df) == 30
    assert _warnings(caplog, "overlap on only 30 of 40 days")


def test_read_run_snow_day_does_not_trigger_mismatch(make_run, caplog):
    run = make_run(days=30, snow_day=True)
    i = run.snow_idx
    assert run.met["temp_c"].iloc[i] <= 0 and run.met["rain_cm"].iloc[i] > 0
    assert run.zts["PRCP"].iloc[i] == 0                      # snow is not in PRCP
    with caplog.at_level(logging.WARNING, logger=LOGGER):
        df = read_run(run.folder)
    assert not _warnings(caplog, "differ by")
    assert df["snow_day"].iloc[i]
    assert df["snow_day"].sum() == 1


def test_read_run_warm_day_mismatch_warns(make_run, caplog):
    run = make_run(days=30, warm_mismatch=True)
    with caplog.at_level(logging.WARNING, logger=LOGGER):
        df = read_run(run.folder)
    w = _warnings(caplog, "differ by up to 3.00 mm on warm days")
    assert len(w) == 1
    assert df.attrs.get("weather_mismatch_mm", 3.0) == pytest.approx(3.0)


def test_read_run_snow_and_warm_mismatch_together(make_run, caplog):
    run = make_run(days=30, snow_day=True, warm_mismatch=True)
    with caplog.at_level(logging.WARNING, logger=LOGGER):
        read_run(run.folder)
    # only the 3 mm warm-day difference counts, not the 3 mm of snow
    assert _warnings(caplog, "differ by up to 3.00 mm")


def test_read_run_mc_log_error_warns(make_run, caplog):
    run = make_run(days=10, log_error=True)
    with caplog.at_level(logging.WARNING, logger=LOGGER):
        df = read_run(run.folder)
    w = _warnings(caplog, "ERROR line(s) in mc.log")
    assert len(w) == 1
    assert "1 ERROR line(s)" in w[0].getMessage() and "TIFFOpen" in w[0].getMessage()
    if "log_errors" in df.attrs:
        assert len(df.attrs["log_errors"]) == 1


def test_read_run_clean_log_no_warning(make_run, caplog):
    run = make_run(days=10, log_error=False)
    with caplog.at_level(logging.WARNING, logger=LOGGER):
        read_run(run.folder)
    assert not _warnings(caplog, "mc.log")


def test_read_run_mass_balance_warning(make_run, caplog):
    # 0.38 g/ha per runoff day is fine; 2000 g/ha per runoff day exceeds 2400 g/ha applied
    run = make_run(days=60, runoff_gha=2000.0)
    with caplog.at_level(logging.WARNING, logger=LOGGER):
        df = read_run(run.folder)
    assert _warnings(caplog, "mass balance broken")
    if "mass_balance_ok" in df.attrs:
        assert df.attrs["mass_balance_ok"] is False


def test_read_run_missing_file_raises(make_run):
    run = make_run(days=10)
    run.files["zts"].unlink()
    with pytest.raises(FileNotFoundError, match="found 0"):
        read_run(run.folder)


def test_read_run_two_met_files_raises(make_run):
    run = make_run(days=10)
    (run.folder / "other.met").write_text(run.files["met"].read_text())
    with pytest.raises(FileNotFoundError, match="found 2"):
        read_run(run.folder)
