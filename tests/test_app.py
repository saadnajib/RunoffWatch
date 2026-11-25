"""Tests for the Streamlit app (`app.py`, run in-process with AppTest) and its helpers (runoffwatch.appdata)."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pandas as pd
import pytest

from runoffwatch import appdata as ad

ROOT = Path(__file__).resolve().parents[1]
APP = str(ROOT / "app.py")


# --------------------------------------------------------------------------- #
# Pure helpers
# --------------------------------------------------------------------------- #
def test_formats():
    assert ad.fmt_gha(1234.0) == "1,234 g/ha"
    assert ad.fmt_gha(12.34) == "12.3 g/ha"
    assert ad.fmt_gha(1.234) == "1.23 g/ha"
    assert ad.fmt_gha(0.0042, unit=False) == "0.004"
    assert ad.fmt_gha(None) == "n/a" and ad.fmt_gha(float("nan")) == "n/a"
    assert ad.fmt_pct(0.9166, 0, share=True) == "92%"
    assert ad.fmt_pct(12.345) == "12.3%"
    assert ad.fmt_pct_small(0.0778) == "0.078%" and ad.fmt_pct_small(0.52) == "0.5%"
    assert ad.fmt_r2(0.97993) == "0.98"
    assert ad.fmt_day("2026-03-03") == "Tue 3 Mar 2026"


def test_spraying_text_and_labels(tmp_path):
    assert ad.spraying_text({"day": 1, "month": 3, "rate_kgha": 2.4}) == "sprayed on 1 March with 2.4 kg/ha (2,400 g/ha)"
    assert ad.spraying_text(None) == "spraying not stated"
    assert ad.spraying_text({"day": 1, "month": 13}) == "spraying not stated"
    sub = tmp_path / "autumn"
    assert ad.scenario_label(tmp_path, None, tmp_path) == "Standard run"
    assert ad.scenario_label(sub, {"spraying": {"day": 15, "month": 10, "rate_kgha": 1.2}}, tmp_path) == \
        "Scenario 'autumn': sprayed on 15 October with 1.2 kg/ha (1,200 g/ha)"
    assert ad.half_month("03 Mar 1-15") == "Mar 1-15" and ad.half_month("odd") == "odd"
    assert ad.first_year("training years (2006-2015)") == 2006 and ad.first_year("x") == 9999
    assert ad.season("10 Oct 1-15").startswith("Autumn") and ad.season("02 Feb 16-end").startswith("Spring")


def test_spray_windows_and_limits():
    days = list(range(46, 122)) + list(range(274, 336))
    assert ad.spray_windows(days) == "15 Feb-30 Apr and 1 Oct-30 Nov"
    assert ad.spray_windows([60, 61]) == "1 Mar"
    assert "only know" in ad.spray_limits({"trained_on": {}})
    text = ad.spray_limits({"trained_on": {"spray_days_seen": days, "doses_kgha": [0.24, 2.4]}})
    assert "240 to 2,400 g/ha" in text


def test_read_csv_safely(tmp_path):
    p = tmp_path / "a.csv"
    assert ad.read_csv(p) is None                                   # missing
    p.write_text("")
    assert ad.read_csv(p) is None                                   # empty
    p.write_text("x,y,extra\n1,2,a\n3,4,b\n5,")                     # half-written last line
    df = ad.read_csv(p, required=("x",), numeric=("x", "y"))
    assert list(df["x"]) == [1, 3] and "extra" in df.columns
    assert ad.read_csv(p, required=("z",)) is None                  # missing column
    p.write_bytes(b"\x00\xff\xfe garbage \"unclosed")
    ad.read_csv(p)                                                  # must not raise


def test_read_json_and_dig(tmp_path):
    p = tmp_path / "a.json"
    assert ad.read_json(p) is None
    p.write_text('{"a": {"b": 1}')                                  # half-written
    assert ad.read_json(p) is None
    p.write_text("[1, 2]")
    assert ad.read_json(p) is None
    p.write_text('{"a": {"b": 1}}')
    d = ad.read_json(p)
    assert ad.dig(d, "a", "b") == 1 and ad.dig(d, "a", "c") is None and ad.dig(None, "a", default=3) == 3
    assert ad.mtime(p) is not None and ad.mtime(tmp_path / "nope") is None


def test_find_scenarios(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    res = Path("docs/results/varied")
    assert ad.find_scenarios(res) == []
    (res / "autumn").mkdir(parents=True)
    (res / "empty").mkdir()
    (res / "autumn" / "france_by_year.csv").write_text("app_year\n1979\n")
    assert ad.find_scenarios(res) == [res / "autumn"]
    (res / "france_by_year.csv").write_text("app_year\n1979\n")
    assert ad.find_scenarios(res) == [res, res / "autumn"]
    # seen from the standard results folder, the folders of the other data sets are not scenarios
    std = Path("docs/results")
    (std / "france_by_year.csv").write_text("app_year\n1979\n")
    (std / "delivered").mkdir()
    (std / "delivered" / "france_by_year.csv").write_text("app_year\n1979\n")
    assert ad.find_scenarios(std) == [std]


def test_model_set(tmp_path):
    assert ad.model_set(tmp_path)["name"] == "standard"
    (tmp_path / "models/varied").mkdir(parents=True)
    (tmp_path / "models/varied/meta.json").write_text("{}")
    s = ad.model_set(tmp_path)
    assert s["name"] == "varied" and s["results"] == tmp_path / "docs/results/varied"


def test_headline_and_template():
    ranked = pd.DataFrame({"spray_date": pd.to_datetime(["2026-03-03", "2026-03-04"]).date,
                           "predicted_loss_gha": [0.5, 3.25]})
    text = ad.headline(ranked, 14)
    assert text.startswith("Lowest predicted loss: spraying on **Tue 3 Mar 2026**: **0.50 g/ha** in the following 14 days.")
    assert "Highest: spraying on **Wed 4 Mar 2026**: **3.25 g/ha**" in text
    w = pd.DataFrame({"rain_mm": [0.0, 1.5], "temp_c": [3.0, 4.0]},
                     index=pd.date_range("2026-01-01", periods=2, name="date"))
    assert ad.weather_template(w).splitlines() == ["date,rain_mm,temp_c", "2026-01-01,0.0,3.0", "2026-01-02,1.5,4.0"]


# --------------------------------------------------------------------------- #
# The app itself (in-process, no browser)
# --------------------------------------------------------------------------- #
def run_app(cwd: Path, monkeypatch):
    """Run app.py in-process with `cwd` as the working directory (skipped without streamlit)."""
    pytest.importorskip("streamlit")
    pytest.importorskip("lightgbm")
    from streamlit.testing.v1 import AppTest
    monkeypatch.chdir(cwd)
    at = AppTest.from_file(APP, default_timeout=120)
    return at.run()


def texts(at) -> str:
    parts = [m.value for m in at.markdown] + [c.value for c in at.caption] + [i.value for i in at.info]
    return "\n".join(str(p) for p in parts)


def errors(at) -> list[str]:
    return [str(e.value) for e in at.error]


needs_models = pytest.mark.skipif(not (ROOT / "models/meta.json").exists(), reason="no trained models in the repo")


@needs_models
def test_app_with_repo_files(monkeypatch):
    at = run_app(ROOT, monkeypatch)
    assert not at.exception, [e.value for e in at.exception]
    assert [t.label for t in at.tabs] == ["Compare spray days", "How good is the copy?", "Spray date",
                                         "45 years of French weather", "About and limits"]
    body = texts(at)
    if not errors(at):                               # models loaded (they may be mid-rewrite)
        assert "Lowest predicted loss: spraying on" in body
        assert ad.CAUTION in body
    # change inputs and run again
    at.slider[0].set_value(8.0).run()
    assert not at.exception
    if not errors(at):
        slider = {s.label: s for s in at.slider}
        slider["Number of candidate days"].set_value(14).run()
        at.date_input[0].set_value(pd.Timestamp("2026-03-20").date()).run()   # late in the example weather
        assert not at.exception
        assert any("not ranked" in str(w.value) for w in at.warning)     # windows past the end of the weather
        day = next(s for s in at.selectbox if s.label == "Spray day to look at")
        day.set_value(day.options[-1]).run()
        assert not at.exception
    at.radio[0].set_value("Upload my own CSV").run()
    assert not at.exception
    assert "Upload a file to continue" in texts(at)


@needs_models
def test_app_without_results(tmp_path, monkeypatch):
    """Only the models are there: every tab shows a note, nothing fails."""
    shutil.copytree(ROOT / "models", tmp_path / "models", ignore=shutil.ignore_patterns("delivered", "lstm.pt"))
    at = run_app(tmp_path, monkeypatch)
    assert not at.exception, [e.value for e in at.exception]
    body = texts(at)
    assert "Not available yet" in body
    if not errors(at):
        assert "Lowest predicted loss: spraying on" in body


@needs_models
def test_app_with_broken_results(tmp_path, monkeypatch):
    """Half-written and odd result files (as while the training job rewrites them)."""
    shutil.copytree(ROOT / "models", tmp_path / "models", ignore=shutil.ignore_patterns("delivered", "lstm.pt"))
    res = tmp_path / ad.model_set(tmp_path)["results"].relative_to(tmp_path)
    res.mkdir(parents=True)
    (res / "cv_summary.json").write_text('{"pooled": {"runoff_r2": 0.9')
    (res / "cv_by_year.csv").write_text("test_year,other\n1990,1\n")
    (res / "model_metrics.json").write_text('{"speed": {}}')
    (res / "loss_by_spray_date.csv").write_text("sprayed,mean_pct_of_dose_lost\n03 Mar 1-15,0.07\n04 Apr")
    (res / "loss_after_spraying.csv").write_text("sprayed,days_after_spraying\n")
    (res / "france_by_year.csv").write_text("app_year,loss_gha_mean\n1979,1.2\n1980,")
    (res / "france_summary.json").write_text(json.dumps({"spraying": {"day": 1, "month": 3, "rate_kgha": 2.4},
                                                         "by_period": {"x": {}}, "worst_years_by_mean_loss": {}}))
    (res / "france_by_grid.csv").write_text("grid,LATITUDE\n1,45\n")
    (res / "autumn").mkdir()
    (res / "autumn" / "france_by_year.csv").write_text("app_year,loss_gha_mean\n1979,3.2\n1980,2.1\n")
    (res / "autumn" / "france_summary.json").write_text(
        json.dumps({"spraying": {"day": 15, "month": 10, "rate_kgha": 2.4}}))
    at = run_app(tmp_path, monkeypatch)
    assert not at.exception, [e.value for e in at.exception]
    assert "Scenario" in [s.label for s in at.selectbox]
    scen = next(s for s in at.selectbox if s.label == "Scenario")
    scen.set_value(scen.options[1]).run()
    assert not at.exception


def test_app_without_models(tmp_path, monkeypatch):
    """No models at all: the advisor shows an error, the other tabs still work."""
    at = run_app(tmp_path, monkeypatch)
    assert not at.exception, [e.value for e in at.exception]
    assert any("could not be loaded" in e for e in errors(at))
