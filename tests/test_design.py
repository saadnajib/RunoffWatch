"""Tests for runoffwatch.design (designed experiment: design table, .xrun, weather CSVs, 7z archives).

All data is synthetic: a small run_quality table and short .met files from conftest.build_run.
"""

from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np
import pandas as pd
import py7zr
import pytest

from conftest import build_run
from runoffwatch import design as D

SIM_START, SIM_END = "1990-01-01", "1990-03-31"        # short period: synthetic .met has 120 days
N_DAYS = 90


def _rq_row(i: int, unstable: bool, met_hash: str, batch: str) -> dict:
    r = {"batch": batch, "clean_until": "1995-03-01", "usle_k": 0.3, "slope_pct": 0.5 + i,
         "met_hash": met_hash, "unstable": unstable, "henry": 0.03}
    for h, thick in zip(range(1, 5), (10, 20, 30, 40)):
        base = {1: 0, 2: 0, 3: 1, 4: 2}[h]          # h1 == h2 like in the real runs
        r.update({f"h{h}_thick_cm": thick, f"h{h}_bd": 1.3 + 0.05 * base + 0.001 * i,
                  f"h{h}_oc": [1.2, 0.4, 0.1][base] + 0.01 * i,
                  f"h{h}_sand": 10 + base + i, f"h{h}_clay": 20 + 2 * base})
    return r


@pytest.fixture
def rq() -> pd.DataFrame:
    """12 eligible runs (4 unstable), 6 distinct weather files, plus 2 ineligible rows."""
    rows, names = [], []
    for i in range(12):
        rows.append(_rq_row(i, unstable=i < 4, met_hash=f"{i % 6:012x}", batch=f"batch_{i // 6}"))
        names.append(f"run_{i:07d}_grid_000001")
    bad1 = _rq_row(20, False, "0000000000aa", "batch_0")
    bad1["clean_until"] = None
    bad2 = _rq_row(21, True, "0000000000bb", "batch_0")
    bad2["usle_k"] = np.nan
    rows += [bad1, bad2]
    names += ["run_bad_clean", "run_bad_usle"]
    return pd.DataFrame(rows, index=pd.Index(names, name="run"))


@pytest.fixture
def runs_root(tmp_path, rq) -> Path:
    root = tmp_path / "runs"
    for run, r in rq.iterrows():
        if run.startswith("run_bad"):
            continue
        build_run(root / r["batch"], name=run, days=120, start="1990-01-01")
    return root


def small(rq, **kw):
    kw.setdefault("n_controls", 4)
    kw.setdefault("n_weather", 3)
    return D.make_design(rq, n=kw.pop("n", 30), seed=kw.pop("seed", 1),
                         sim_start=SIM_START, sim_end=SIM_END, **kw)


# --------------------------------------------------------------------------- #
# Design table
# --------------------------------------------------------------------------- #
def test_default_app_dates():
    assert len(D.APP_DATES) == 26
    assert D.APP_DATES[0] == "01-04" and D.APP_DATES[1] == "01-18" and D.APP_DATES[-1] == "12-20"


def test_deterministic_by_seed(rq):
    a, b, c = small(rq, seed=7), small(rq, seed=7), small(rq, seed=8)
    pd.testing.assert_frame_equal(a, b)
    assert not a.equals(c)


def test_main_levels_from_allowed_sets(rq):
    d = small(rq, n=300, n_weather=3)
    m = d[d["group"] == "main"]
    assert len(m) == 300
    assert list(d["run_id"][:3]) == ["run_000001", "run_000002", "run_000003"]
    assert d["run_id"].is_unique
    assert set(m["app_date"]) <= set(D.APP_DATES)
    assert set(m["app_rate_gha"]) == set(D.APP_RATES_GHA)
    assert set(m["dt50_d"]) == set(D.DT50_DAYS)
    assert set(m["koc"]) == set(D.KOC_VALUES)
    assert (d["henry"] == D.HENRY_DEFAULT).all()
    assert m["met_hash"].nunique() == 3
    assert m["source_run"].isin(rq.index[:12]).all()
    assert not d["source_run"].str.startswith("run_bad").any()
    assert (m["substance"] == [f"S_dt50-{D.fmt_num(a)}_koc-{D.fmt_num(b)}"
                               for a, b in zip(m["dt50_d"], m["koc"])]).all()
    assert "S_dt50-30_koc-100" == D.substance_label(30, 100)
    assert (d["weather_file"] == d["met_hash"] + ".csv").all()


def test_custom_levels_and_henry(rq):
    d = small(rq, app_dates=["05-15"], app_rates=[100], dt50s=[5], kocs=[50], henry=1e-5, n_controls=0)
    assert set(d["group"]) == {"main"}
    assert set(d["app_date"]) == {"05-15"} and set(d["app_rate_gha"]) == {100}
    assert set(d["henry"]) == {1e-5}


def test_control_group(rq):
    d = small(rq, n_controls=6)
    c = d[d["group"] == "control"]
    assert len(c) == 6
    assert c["source_run"].is_unique
    assert (c["app_date"] == "03-01").all() and (c["app_rate_gha"] == 2400).all()
    assert (c["dt50_d"] == 41.68).all() and (c["koc"] == 377.5).all()
    assert (c["henry"] == D.HENRY_DEFAULT).all()
    # own weather and own soil
    assert (c["met_hash"].to_numpy() == rq.loc[c["source_run"], "met_hash"].to_numpy()).all()
    assert (c["slope_pct"].to_numpy() == rq.loc[c["source_run"], "slope_pct"].to_numpy()).all()
    # stratified half/half
    assert rq.loc[c["source_run"], "unstable"].sum() == 3


def test_control_stratification_refills_when_short(rq):
    d = small(rq, n_controls=10)                       # only 4 unstable runs available
    c = d[d["group"] == "control"]
    assert rq.loc[c["source_run"], "unstable"].sum() == 4
    assert len(c) == 10 and c["source_run"].is_unique


def test_unstable_as_strings(rq):
    rq2 = rq.copy()
    rq2["unstable"] = rq2["unstable"].map({True: "True", False: "False"}).astype(object)
    a = small(rq, n_controls=6)
    b = small(rq2, n_controls=6)
    assert list(a["source_run"]) == list(b["source_run"])


def test_soil_conversion(rq):
    d = small(rq)
    for _, r in d.iterrows():
        s = rq.loc[r["source_run"]]
        assert r["slope_pct"] == s["slope_pct"]
        for i, h in enumerate((1, 3, 4), start=1):
            assert r[f"thick_{i}"] == (30, 30, 40)[i - 1]
            assert r[f"bd_{i}"] == pytest.approx(s[f"h{h}_bd"])
            assert r[f"om_{i}"] == pytest.approx(s[f"h{h}_oc"] * 1.724)
            assert r[f"sand_{i}"] == pytest.approx(s[f"h{h}_sand"])
            assert r[f"silt_{i}"] == pytest.approx(100 - s[f"h{h}_sand"] - s[f"h{h}_clay"])


def test_silt_clipped_at_zero():
    row = _rq_row(0, False, "x" * 12, "b")
    row["h1_sand"], row["h1_clay"] = 70, 40
    assert D.soil_fields(row)["silt_1"] == 0


def test_more_weather_than_available(rq, caplog):
    with caplog.at_level(logging.WARNING, logger="runoffwatch"):
        d = small(rq, n=200, n_weather=40, n_controls=0)
    assert d["met_hash"].nunique() == 6
    assert "distinct weather files" in caplog.text


@pytest.mark.parametrize("kw, msg", [
    (dict(n=0), "n must"),
    (dict(n=-3), "n must"),
    (dict(app_dates=["3-1"]), "Bad date"),
    (dict(app_dates=["13-01"]), "Bad date"),
    (dict(app_dates=["02-30"]), "Bad date"),
    (dict(app_dates=["03-01 to 03-01"]), "Bad date"),
    (dict(app_dates=[]), "no dates"),
    (dict(app_rates=[0, 600]), "app_rates"),
    (dict(app_rates=[-600]), "app_rates"),
    (dict(dt50s=[0]), "dt50s"),
    (dict(kocs=[-1]), "kocs"),
    (dict(henry=0), "henry"),
    (dict(n_controls=100), "n_controls"),
])
def test_errors(rq, kw, msg):
    with pytest.raises(ValueError, match=msg):
        small(rq, **kw)


def test_empty_eligible(rq):
    with pytest.raises(ValueError, match="No eligible"):
        D.make_design(rq.assign(usle_k=np.nan), n=5)


# --------------------------------------------------------------------------- #
# xrun
# --------------------------------------------------------------------------- #
def test_render_parse_roundtrip(rq):
    d = small(rq)
    r = d.iloc[0]
    text = D.render_xrun(r)
    assert text.startswith('<?xml version="1.0" encoding="utf-8"?>\n<Parameters>')
    root = ET.fromstring(text.encode("utf-8"))
    assert root.tag == "Parameters" and len(root) == 45
    p = D.parse_xrun(text)
    assert p["Project"] == r"{Model}\scenario\schematic-100x100"
    assert p["SimID"] == "{SimId}"
    assert p["Weather"] == "{Exp}\\" + r["weather_file"]
    assert p["SimulationStart"] == SIM_START and p["SimulationEnd"] == SIM_END
    assert p["Substance"] == r["substance"]
    assert float(p["DT50"]) == r["dt50_d"] and float(p["KocSoil"]) == r["koc"]
    assert float(p["Substance_HenryConstant"]) == r["henry"]
    assert float(p["ApplicationRate"]) == r["app_rate_gha"]
    assert p["ApplicationWindows"] == f"{r['app_date']} to {r['app_date']}"
    assert float(p["Fields_Slope"]) == pytest.approx(r["slope_pct"])
    assert p["Fields_SoilHorizonThicknesses"] == "30 30 40"
    om = [float(x) for x in p["Fields_SoilHorizonOrganicMaterialContents"].split()]
    assert om == pytest.approx([r["om_1"], r["om_2"], r["om_3"]])
    silt = [float(x) for x in p["Fields_SoilHorizonSiltFractions"].split()]
    assert silt == pytest.approx([r["silt_1"], r["silt_2"], r["silt_3"]])
    # fixed template values
    assert p["FreundlichExponent"] == "0.957"
    assert p["CropParameters_Crops"] == "Cereals,Winter|OffCrop"
    assert p["CropParameters_SedimentMitigations"] == "0 -0.153"
    assert "e" not in p["ApplicationRate"] + p["DT50"] + p["Fields_SoilHorizonBulkDensities"]


def test_render_escapes_xml(rq):
    r = small(rq).iloc[0].copy()
    r["substance"] = "A&B<C>"
    text = D.render_xrun(r)
    assert "A&amp;B&lt;C&gt;" in text
    assert D.parse_xrun(text)["Substance"] == "A&B<C>"


def test_number_formatting():
    assert D.fmt_num(2400.0) == "2400"
    assert D.fmt_num(41.68) == "41.68"
    assert D.fmt_num(1.2 * 1.724) == "2.0688"
    assert D.fmt_num(0.0001) == "0.0001"
    assert D.fmt_henry(2.4e-7) == "2.4e-07"
    assert D.fmt_henry(0.03) == "0.03"


def test_parse_xrun_rejects_other_root():
    with pytest.raises(ValueError):
        D.parse_xrun("<Other><a>1</a></Other>")


# --------------------------------------------------------------------------- #
# Writing: weather, archives, README
# --------------------------------------------------------------------------- #
def test_weather_csv_reconstruction(tmp_path):
    run = build_run(tmp_path, name="r", days=120)
    out = tmp_path / "w.csv"
    assert D.met_to_weather_csv(run.files["met"], out, SIM_START, SIM_END) == N_DAYS
    assert out.read_text().splitlines()[0] == ",".join(D.WEATHER_COLUMNS)
    w = pd.read_csv(out)
    dates = pd.to_datetime(dict(year=w.YEAR, month=w.MONTH, day=w.DAY))
    assert (dates == pd.date_range(SIM_START, SIM_END)).all()
    met = run.met.loc[SIM_START:SIM_END]
    np.testing.assert_allclose(w["PRECIPITATION"], met["rain_cm"] * 10, atol=1e-3)       # cm -> mm
    np.testing.assert_allclose(w["ET0"], met["evap_cm"] * 10, atol=1e-3)
    np.testing.assert_allclose(w["TEMPERATURE_AVG"], met["temp_c"], atol=1e-3)
    np.testing.assert_allclose(w["WINDSPEED"], met["wind_cms"] / 100, atol=1e-3)         # cm/s -> m/s
    np.testing.assert_allclose(w["RADIATION"], met["solar_ly"] * 0.04184 * 1000, atol=0.01)  # ly -> kJ/m2
    assert (w["GRID_NO"] == 0).all()


def test_weather_must_cover_period(tmp_path):
    run = build_run(tmp_path, name="r", days=30)
    with pytest.raises(ValueError, match="does not cover"):
        D.met_to_weather_csv(run.files["met"], tmp_path / "w.csv", SIM_START, SIM_END)


def _archive_names(path: Path) -> list[str]:
    with py7zr.SevenZipFile(path, "r") as z:
        return z.getnames()


def test_write_design_archives(rq, runs_root, tmp_path, caplog):
    d = small(rq, n=25, n_controls=6)
    out = tmp_path / "design"
    with caplog.at_level(logging.WARNING, logger="runoffwatch"):
        res = D.write_design(d, out, runs_root=runs_root, batch_size=10, name="t")
    assert caplog.text.count("RECONSTRUCTED") == 1
    assert res["n_runs"] == 31 and res["n_archives"] == 4
    assert (out / "design.csv").is_file() and (out / "README.txt").is_file()
    assert len(list((out / "xrun").glob("*.xrun"))) == 31
    assert {p.name for p in (out / "weather").iterdir()} == set(d["weather_file"])

    seen = []
    archive_names = [Path(a["path"]).name for a in res["archives"]]
    assert archive_names == [f"t_batch_{i:03d}.7z" for i in range(1, 5)]
    for a in res["archives"]:
        names = _archive_names(Path(a["path"]))
        assert all("/" not in n and "\\" not in n for n in names)          # archive root
        assert len(names) == len(set(names))
        xruns = [n for n in names if n.endswith(".xrun")]
        csvs = {n for n in names if n.endswith(".csv")}
        assert 1 <= len(xruns) <= 10 and csvs
        assert len(names) == len(xruns) + len(csvs)
        referenced = {D.parse_xrun((out / "xrun" / x).read_text(encoding="utf-8"))["Weather"].split("\\")[-1]
                      for x in xruns}
        assert csvs == referenced                                          # exactly what is referenced
        assert a["size_bytes"] > 0
        seen += [x[:-5] for x in xruns]
    assert sorted(seen) == sorted(d["run_id"])                             # every run exactly once

    written = pd.read_csv(out / "design.csv")
    assert (written["weather_source"] == D.RECONSTRUCTED).all()
    readme = (out / "README.txt").read_text()
    assert D.APP_WINDOW_NOTE in readme
    assert "RECONSTRUCTED" in readme and "31 in total" in readme and "Henry" in readme


def test_archive_content_matches_files(rq, runs_root, tmp_path):
    d = small(rq, n=3, n_controls=0)
    out = tmp_path / "o"
    res = D.write_design(d, out, runs_root=runs_root)
    assert res["n_archives"] == 1
    ex = tmp_path / "ex"
    with py7zr.SevenZipFile(res["archives"][0]["path"], "r") as z:
        z.extractall(ex)
    for rid in d["run_id"]:
        assert (ex / f"{rid}.xrun").read_bytes() == (out / "xrun" / f"{rid}.xrun").read_bytes()


def test_weather_dir_originals_preferred(rq, runs_root, tmp_path):
    d = small(rq, n=10, n_controls=0)
    wdir = tmp_path / "mars"
    wdir.mkdir()
    one = d["met_hash"].iloc[0]
    content = ",".join(D.WEATHER_COLUMNS) + "\n1990,1,1,7,1.5,0.5,3.0,2.0,9000\n"
    (wdir / f"{one}.csv").write_text(content)
    assert (D.make_design(rq, n=10, seed=1, n_weather=3, n_controls=0, sim_start=SIM_START, sim_end=SIM_END,
                          weather_dir=wdir).query("met_hash == @one")["weather_source"]
            == D.ORIGINAL_WEATHER).all()
    out = tmp_path / "o"
    D.write_design(d, out, runs_root=runs_root, weather_dir=wdir)
    assert (out / "weather" / f"{one}.csv").read_text() == content
    w = pd.read_csv(out / "design.csv", dtype={"met_hash": str})
    assert (w.loc[w.met_hash == one, "weather_source"] == D.ORIGINAL_WEATHER).all()
    assert (w.loc[w.met_hash != one, "weather_source"] == D.RECONSTRUCTED).all()

    # mapping works too, without any .met available
    mapping = {h: wdir / f"{one}.csv" for h in d["met_hash"].unique()}
    out2 = tmp_path / "o2"
    res = D.write_design(d, out2, runs_root=tmp_path / "nowhere", weather_dir=mapping)
    assert res["n_weather_reconstructed"] == 0
    assert "RECONSTRUCTED" not in (out2 / "README.txt").read_text()


def test_overwrite_refusal(rq, runs_root, tmp_path):
    d = small(rq, n=3, n_controls=0)
    out = tmp_path / "o"
    out.mkdir()
    (out / "something.txt").write_text("keep")
    with pytest.raises(FileExistsError):
        D.write_design(d, out, runs_root=runs_root)
    D.write_design(d, out, runs_root=runs_root, overwrite=True)
    d2 = small(rq, n=2, n_controls=0, seed=5)
    D.write_design(d2, out, runs_root=runs_root, overwrite=True)
    assert len(list((out / "xrun").glob("*.xrun"))) == 2                    # stale files removed
    assert (out / "something.txt").read_text() == "keep"


def test_write_errors(rq, runs_root, tmp_path):
    d = small(rq, n=3, n_controls=0)
    with pytest.raises(ValueError):
        D.write_design(d, tmp_path / "a", runs_root=runs_root, batch_size=0)
    with pytest.raises(ValueError):
        D.write_design(d, tmp_path / "b", runs_root=runs_root, name="bad name/x")
    with pytest.raises(FileNotFoundError):
        D.write_design(d, tmp_path / "c", runs_root=tmp_path / "nowhere")


def test_summarize_design(rq):
    d = small(rq, n=50, n_controls=4)
    s = D.summarize_design(d)
    assert s["n_runs"] == 54 and s["n_main"] == 50 and s["n_control"] == 4
    for f in ("app_date", "app_rate_gha", "dt50_d", "koc"):
        assert sum(s["main_levels"][f].values()) == 50
    assert set(s["main_levels"]["app_rate_gha"]) <= {"600", "1200", "2400"}
    assert s["control_unstable"] == {"False": 2, "True": 2}
    assert s["henry"] == [D.HENRY_DEFAULT]
