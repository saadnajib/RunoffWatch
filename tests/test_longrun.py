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


# --------------------------------------------------------------------------- #
# Spray day and dose; copies of a field
# --------------------------------------------------------------------------- #
import json  # noqa: E402
import shutil  # noqa: E402

from runoffwatch.przm_inp import SOIL_FEATURES  # noqa: E402


@pytest.mark.parametrize("name, grid", [("run_0000140_grid_086080__v1", 86080), ("run_0000140_grid_086080__v12", 86080),
                                        ("run_1_grid_7", 7)])
def test_grid_of_copies(name, grid):
    assert longrun.grid_of(name) == grid


def _fields(interim, n=3):
    rq = pd.read_csv(interim / "run_quality.csv", index_col="run")
    return rq[SOIL_FEATURES + [f"cn_{k}" for k in (1, 3, 4)]].iloc[:n]


@pytest.fixture(scope="module")
def small_weather(setup):
    _, interim, _, wpath = setup
    w = longrun.load_weather(wpath)
    fields = _fields(interim)
    grids = [longrun.grid_of(r) for r in fields.index]
    return w[w["GRID_NO"].isin(grids) & (w["date"] < "2010-01-01")], fields


def test_predict_fields_loss_scales_with_dose(setup, small_weather):
    root = setup[0]
    w, fields = small_weather
    m = models.load_models(root / "models")
    a = longrun.predict_fields(w, fields, m)
    b = longrun.predict_fields(w, fields, m, rate_kgha=0.6)
    assert a["loss_gha"].sum() > 0
    np.testing.assert_allclose(b["runoff_mm"], a["runoff_mm"])
    np.testing.assert_allclose(b["loss_gha"], a["loss_gha"] / 4, rtol=1e-6)
    np.testing.assert_allclose(b["max_day_loss_gha"], a["max_day_loss_gha"] / 4, rtol=1e-6)
    assert (b["high_loss_days"] <= a["high_loss_days"]).all()


def test_predict_fields_other_spray_day(setup, small_weather):
    root = setup[0]
    w, fields = small_weather
    m = models.load_models(root / "models")
    march = longrun.predict_fields(w, fields, m)
    october = longrun.predict_fields(w, fields, m, app_day=15, app_month=10)
    first, last = w["date"].min().year, w["date"].max().year       # 2002 .. 2009
    assert sorted(march["app_year"].unique()) == list(range(first, last + 1))
    assert sorted(october["app_year"].unique()) == list(range(first, last + 1))
    assert len(october) == len(fields) * (last - first + 1)
    assert not october.duplicated(["run", "app_year"]).any()
    # an application year runs from one spraying to the day before the next: rain sums differ
    assert not np.allclose(october.sort_values(["run", "app_year"])["rain_mm"].to_numpy(),
                           march.sort_values(["run", "app_year"])["rain_mm"].to_numpy())
    g = w[w["GRID_NO"] == longrun.grid_of(fields.index[0])].set_index("date")
    expect = g.loc["2003-10-15":"2004-10-14", "PRECIPITATION"].sum()
    row = october[(october["run"] == fields.index[0]) & (october["app_year"] == 2003)]
    assert row["rain_mm"].iloc[0] == pytest.approx(expect)


@pytest.fixture(scope="module")
def interim_with_copies(setup, tmp_path_factory):
    """The run table of `setup` plus a copy `<run>__v1` of the first five fields (listed first)."""
    _, interim, _, _ = setup
    root = tmp_path_factory.mktemp("copies") / "interim"
    shutil.copytree(interim, root)
    rq = pd.read_csv(root / "run_quality.csv")
    copies = rq.iloc[:5].assign(run=rq["run"].iloc[:5] + "__v1")
    for run in rq["run"].iloc[:5]:
        shutil.copyfile(root / "daily" / f"{run}.parquet", root / "daily" / f"{run}__v1.parquet")
    pd.concat([copies, rq], ignore_index=True).to_csv(root / "run_quality.csv", index=False)
    return root


def test_run_france_keeps_one_run_per_field(setup, interim_with_copies, tmp_path):
    root, _, features, wpath = setup
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        s = longrun.run_france(wpath, interim_with_copies, features, root / "models", tmp_path / "fy.parquet",
                               tmp_path, tmp_path, app_day=15, app_month=10, rate_kgha=1.2)
    fy = pd.read_parquet(tmp_path / "fy.parquet")
    assert s["fields"] == 20
    assert fy["run"].map(lambda r: r.split("__")[0]).nunique() == 20
    assert not fy.duplicated(["run", "app_year"]).any()
    assert s["spraying"] == {"day": 15, "month": 10, "rate_kgha": 1.2}
    assert s["consistency_with_przm_2006_2015_not_a_test"] is None
    saved = json.loads((tmp_path / "france_summary.json").read_text())
    assert saved["spraying"] == s["spraying"] and saved["consistency_with_przm_2006_2015_not_a_test"] is None


@pytest.mark.parametrize("day, month, rate, compared", [
    (1, 3, 2.4, True), (1, 3, 1.2, False), (2, 3, 2.4, False), (1, 4, 2.4, False),
])
def test_run_france_compares_with_przm_only_for_the_delivered_spraying(setup, tmp_path, day, month, rate, compared):
    root, interim, features, wpath = setup
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        s = longrun.run_france(wpath, interim, features, root / "models", tmp_path / "fy.parquet", tmp_path, tmp_path,
                               limit=3, app_day=day, app_month=month, rate_kgha=rate)
    assert s["spraying"] == {"day": day, "month": month, "rate_kgha": rate}
    c = s["consistency_with_przm_2006_2015_not_a_test"]
    assert (c is not None) == compared
    if compared:
        assert c["field_years"] > 0


def test_run_france_consistency_leaves_out_warm_up_field_years(setup, tmp_path):
    import shutil

    root, interim, features, wpath = setup
    warm = tmp_path / "interim"
    shutil.copytree(interim, warm)
    rq = pd.read_csv(warm / "run_quality.csv", index_col="run")
    first = pd.Timestamp(pd.read_parquet(warm / "daily" / f"{rq.index[0]}.parquet").index[0])
    rq["clean_from"] = pd.Timestamp(first.year, 11, 12)          # the first application year is warm-up
    rq.to_csv(warm / "run_quality.csv")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        old, new = (longrun.run_france(wpath, folder, features, root / "models", tmp_path / f"{k}.parquet",
                                       tmp_path, tmp_path, limit=3) for k, folder in enumerate((interim, warm)))
    c_old, c_new = (s["consistency_with_przm_2006_2015_not_a_test"] for s in (old, new))
    pz = longrun.przm_field_years(features)
    assert (pz["app_year"] == first.year + longrun.YEAR_SHIFT).any()       # PRZM has rows in that year
    assert c_new["field_years"] < c_old["field_years"]
