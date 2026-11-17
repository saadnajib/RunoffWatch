"""Tests for the long-run prediction on a weather table (synthetic data only)."""
import warnings

import numpy as np
import pandas as pd
import pytest

from runoffwatch import longrun, models
from runoffwatch.features import build_feature_table
from test_models_whatif import _synthetic_interim


def test_grid_of():
    assert longrun.grid_of("run_0000140_grid_086080") == 86080


def test_load_weather_csv_sorts_and_parses(tmp_path):
    p = tmp_path / "w.csv"
    p.write_text("GRID_NO;LATITUDE;LONGITUDE;ALTITUDE;DAY;TEMPERATURE_AVG;WINDSPEED;PRECIPITATION;ET0;RADIATION\n"
                 "2;45;1;100;19790102;5;1;0;1;100\n1;44;2;50;19790102;6;1;3;1;100\n1;44;2;50;19790101;4;1;0;1;100\n")
    w = longrun.load_weather(p)
    assert list(w["GRID_NO"]) == [1, 1, 2]
    assert list(w["date"].dt.strftime("%Y-%m-%d")) == ["1979-01-01", "1979-01-02", "1979-01-02"]
    with pytest.raises(ValueError):
        longrun.load_weather(_drop(p, tmp_path))


def _drop(p, tmp_path):
    q = tmp_path / "bad.csv"
    q.write_text("\n".join(";".join(l.split(";")[:5]) for l in p.read_text().splitlines()) + "\n")
    return q


@pytest.fixture(scope="module")
def setup(tmp_path_factory):
    root = tmp_path_factory.mktemp("longrun")
    interim = root / "interim"
    _synthetic_interim(interim, n_files=20)
    features = root / "features.parquet"
    build_feature_table(interim, features)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        models.train_all(features, model_dir=root / "models", results=root / "r", figures=root / "f", rounds=15)
    # weather table: each run's own weather, relabelled +16 years (as in the real data), plus 4 extra years
    rq = pd.read_csv(interim / "run_quality.csv", index_col="run")
    parts = []
    for run in rq.index:
        d = pd.read_parquet(interim / "daily" / f"{run}.parquet", columns=["rain_mm", "temp_c", "pan_evap_mm"])
        real = pd.DataFrame({"date": pd.date_range("2006-01-01", periods=len(d)), "PRECIPITATION": d["rain_mm"].to_numpy(),
                             "TEMPERATURE_AVG": d["temp_c"].to_numpy(), "ET0": d["pan_evap_mm"].to_numpy()})
        before = real.iloc[: 4 * 365].assign(date=pd.date_range("2002-01-02", periods=4 * 365))
        w = pd.concat([before, real], ignore_index=True)
        parts.append(w.assign(GRID_NO=longrun.grid_of(run), LATITUDE=45.0, LONGITUDE=2.0, ALTITUDE=100.0))
    wpath = root / "weather.parquet"
    pd.concat(parts, ignore_index=True).to_parquet(wpath)
    return root, interim, features, wpath


def test_check_shift_detects_match_and_mismatch(setup):
    root, interim, _, wpath = setup
    w = longrun.load_weather(wpath)
    runs = list(pd.read_csv(interim / "run_quality.csv", index_col="run").index[:3])
    assert longrun.check_shift(w, interim / "daily", runs)["matches"]
    w2 = w.assign(PRECIPITATION=w["PRECIPITATION"] + 1.0)
    assert not longrun.check_shift(w2, interim / "daily", runs)["matches"]


def test_run_france_end_to_end(setup, tmp_path):
    root, interim, features, wpath = setup
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        s = longrun.run_france(wpath, interim, features, root / "models", tmp_path / "fy.parquet", tmp_path, tmp_path)
    fy = pd.read_parquet(tmp_path / "fy.parquet")
    assert s["fields"] == fy["run"].nunique() == 20
    assert s["application_years"] == [2002, 2014]              # last application year must be complete
    assert not fy.duplicated(["run", "app_year"]).any()
    assert (fy[["runoff_mm", "loss_gha", "high_loss_days"]] >= 0).all().all()
    assert np.isfinite(fy[["runoff_mm", "loss_gha", "rain_mm"]]).all().all()
    for f in ("france_by_year.csv", "france_by_grid.csv", "france_summary.json", "f1_france_by_year.png", "f2_france_map.png"):
        assert (tmp_path / f).exists()
    c = s["consistency_with_przm_2006_2015_not_a_test"]
    assert c["field_years"] > 0 and c["runoff_r2_yearly"] > 0.3


def test_run_france_refuses_unshifted_weather(setup, tmp_path):
    root, interim, features, wpath = setup
    w = pd.read_parquet(wpath)
    w["PRECIPITATION"] = w["PRECIPITATION"].sample(frac=1, random_state=0).to_numpy()
    bad = tmp_path / "bad.parquet"; w.to_parquet(bad)
    with pytest.raises(ValueError, match="shifted"):
        longrun.run_france(bad, interim, features, root / "models", tmp_path / "x.parquet", tmp_path, tmp_path)
