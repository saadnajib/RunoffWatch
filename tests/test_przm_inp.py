"""Tests for runoffwatch.przm_inp (reading run settings from a PRZM 3 .inp)."""

from __future__ import annotations

import pytest

from conftest import DEFAULT_FACTORS, DEFAULT_HORIZONS, full_inp_lines, write_full_inp
from runoffwatch.przm_inp import SOIL_FEATURES, InpFormatError, parse_inp
from runoffwatch.przm_io import read_zts_scale_factors


def _index(lines, prefix):
    return next(i for i, l in enumerate(lines) if l.startswith(prefix))


def test_synthetic_file_has_the_73_line_layout():
    lines = full_inp_lines()
    assert len(lines) == 73
    assert lines[23].startswith("Chemical Input Data")
    assert lines[38].startswith("Soil Series")
    assert lines[40] == "    43000.30E-01   22.70"


def test_parse_inp_field_and_curve_numbers(tmp_path):
    p = write_full_inp(tmp_path / "a.inp", usle_k=0.29, usle_ls=0.47, usle_p=0.8, slope=3.5,
                       cn=(77, 77, 82, 88))
    d = parse_inp(p)
    assert d["usle_k"] == pytest.approx(0.29)
    assert d["usle_ls"] == pytest.approx(0.47)
    assert d["usle_p"] == pytest.approx(0.8)
    assert d["slope_pct"] == pytest.approx(3.5)
    assert [d[f"cn_{i}"] for i in range(1, 5)] == [77, 77, 82, 88]


def test_parse_inp_pesticide_block(tmp_path):
    p = write_full_inp(tmp_path / "a.inp", pesticide="Testazol", app_day=15, app_month=4,
                       app_rate=1.25, n_apps=10)
    d = parse_inp(p)
    assert d["pesticide"] == "Testazol"
    assert d["app_day"] == 15
    assert d["app_month"] == 4
    assert d["app_rate_kgha"] == pytest.approx(1.25)
    assert d["n_apps"] == 10
    assert "app_varies_between_years" not in d


def test_parse_inp_flags_applications_that_vary(tmp_path):
    p = write_full_inp(tmp_path / "a.inp", app_rates=[2.4] * 9 + [1.2])
    d = parse_inp(p)
    assert d["app_rate_kgha"] == pytest.approx(2.4)        # first application
    assert d["app_varies_between_years"] is True


def test_parse_inp_fewer_applications_keeps_layout_anchored(tmp_path):
    # with 3 applications the soil block moves up; the marker lines keep it readable
    p = write_full_inp(tmp_path / "a.inp", n_apps=3)
    d = parse_inp(p)
    assert d["n_apps"] == 3
    assert d["h1_kd"] == pytest.approx(DEFAULT_HORIZONS[0]["kd"])


def test_parse_inp_henry_from_fixed_width_columns(tmp_path):
    # "    43000.30E-01   22.70": DAIR=4300 and HENRYK=0.30E-01 run together
    d = parse_inp(write_full_inp(tmp_path / "a.inp"))
    assert d["henry"] == pytest.approx(0.03)
    d = parse_inp(write_full_inp(tmp_path / "b.inp", henry_field="0.12E-03"))
    assert d["henry"] == pytest.approx(1.2e-4)


def test_parse_inp_soil_horizons_and_decay(tmp_path):
    d = parse_inp(write_full_inp(tmp_path / "a.inp", decay=0.02310))
    for h, hz in enumerate(DEFAULT_HORIZONS, start=1):
        assert d[f"h{h}_thick_cm"] == pytest.approx(hz["thick"])
        assert d[f"h{h}_bd"] == pytest.approx(hz["bd"])
        assert d[f"h{h}_fc"] == pytest.approx(hz["fc"])
        assert d[f"h{h}_wp"] == pytest.approx(hz["wp"])
        assert d[f"h{h}_oc"] == pytest.approx(hz["oc"])
        assert d[f"h{h}_kd"] == pytest.approx(hz["kd"])
        assert d[f"h{h}_sand"] == pytest.approx(hz["sand"])
        assert d[f"h{h}_clay"] == pytest.approx(hz["clay"])
    assert d["decay_rate_per_day"] == pytest.approx(0.0231)
    assert set(SOIL_FEATURES) <= set(d)


def test_full_inp_still_readable_by_tser_reader(tmp_path):
    p = write_full_inp(tmp_path / "a.inp")
    factors = read_zts_scale_factors(p)
    assert set(factors) == set(DEFAULT_FACTORS)
    assert factors["RFLX1"] == pytest.approx(1e8)


# --------------------------------------------------------------------------- #
# Rejected files
# --------------------------------------------------------------------------- #
def test_rejects_file_without_marker_lines(tmp_path):
    lines = [l for l in full_inp_lines() if not l.startswith("Chemical Input Data")]
    with pytest.raises(InpFormatError, match="marker"):
        parse_inp(write_full_inp(tmp_path / "a.inp", lines=lines))
    lines = [l for l in full_inp_lines() if not l.startswith("Soil Series")]
    with pytest.raises(InpFormatError, match="marker"):
        parse_inp(write_full_inp(tmp_path / "b.inp", lines=lines))


def test_rejects_tser_only_inp_from_existing_fixture(make_run):
    run = make_run(days=10)
    with pytest.raises(InpFormatError):
        parse_inp(run.files["inp"])


def test_rejects_wrong_number_of_horizons(tmp_path):
    p = write_full_inp(tmp_path / "a.inp", n_horizons=3)
    with pytest.raises(InpFormatError, match="horizons"):
        parse_inp(p)
    p = write_full_inp(tmp_path / "b.inp", horizons=DEFAULT_HORIZONS[:3])
    with pytest.raises(InpFormatError, match="horizons"):
        parse_inp(p)


@pytest.mark.parametrize("keep_after_soil", [3, 12, 20])
def test_rejects_truncated_file(tmp_path, keep_after_soil):
    lines = full_inp_lines()
    soil = _index(lines, "Soil Series")
    p = write_full_inp(tmp_path / "a.inp", lines=lines[: soil + keep_after_soil])
    with pytest.raises(InpFormatError):
        parse_inp(p)


def test_rejects_line_12_that_is_not_curve_numbers(tmp_path):
    lines = full_inp_lines()
    lines[11] = "0.20 0.20 0.40 0.90"
    with pytest.raises(InpFormatError, match="line 12"):
        parse_inp(write_full_inp(tmp_path / "a.inp", lines=lines))
    lines[11] = "  81   81   86"                     # only three numbers
    with pytest.raises(InpFormatError, match="line 12"):
        parse_inp(write_full_inp(tmp_path / "b.inp", lines=lines))


def test_rejects_field_line_with_wrong_count(tmp_path):
    lines = full_inp_lines()
    lines[4] = "    0.34    0.11    0.50"
    with pytest.raises(InpFormatError, match="line 5"):
        parse_inp(write_full_inp(tmp_path / "a.inp", lines=lines))


def test_inp_format_error_is_a_value_error():
    assert issubclass(InpFormatError, ValueError)
