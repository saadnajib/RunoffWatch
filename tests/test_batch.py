"""Tests for runoffwatch.batch and the command line, on synthetic run folders."""
import zipfile

import pandas as pd
import pytest

from runoffwatch import batch
from runoffwatch.__main__ import main

from conftest import build_run


def _zip_dir(src_parent, run_name, archive):
    with zipfile.ZipFile(archive, "w") as z:
        for f in (src_parent / run_name).iterdir():
            z.write(f, f"{run_name}/{f.name}")


@pytest.fixture
def two_batches(tmp_path):
    """data/runs/<batch>/<run> with two batches, one stable and one unstable run."""
    root = tmp_path / "runs"
    a = build_run(root / "run_000000_to_000999", name="run_0000001_grid_000001", days=60)
    b = build_run(root / "run_001000_to_001999", name="run_0001001_grid_000002", days=60,
                  unstable=True, log_error=True)
    return root, a, b


def test_find_runs(two_batches):
    root, a, b = two_batches
    assert batch.find_runs(root) == sorted([a.folder, b.folder])


def test_find_runs_empty(tmp_path):
    with pytest.raises(FileNotFoundError):
        batch.find_runs(tmp_path)


def test_extract_zip_and_marker(tmp_path):
    src = tmp_path / "src"
    build_run(src, name="run_0000001_grid_000001")
    arcs = tmp_path / "archives"; arcs.mkdir()
    _zip_dir(src, "run_0000001_grid_000001", arcs / "batch_a.zip")

    out = tmp_path / "runs"
    [target] = batch.extract_archives(arcs, out)
    assert (target / ".unpacked").exists()
    assert batch.find_runs(out) == [target / "run_0000001_grid_000001"]

    # second call skips: delete a file and check it is not restored
    (target / "run_0000001_grid_000001" / "mc.log").unlink()
    batch.extract_archives(arcs, out)
    assert not (target / "run_0000001_grid_000001" / "mc.log").exists()


def test_extract_redoes_interrupted_unpack(tmp_path):
    src = tmp_path / "src"
    build_run(src, name="run_0000001_grid_000001")
    arcs = tmp_path / "archives"; arcs.mkdir()
    _zip_dir(src, "run_0000001_grid_000001", arcs / "batch_a.zip")
    (tmp_path / "runs" / "batch_a").mkdir(parents=True)          # left over, no marker
    (tmp_path / "runs" / "batch_a" / "partial.txt").write_text("x")
    batch.extract_archives(arcs, tmp_path / "runs")
    assert (tmp_path / "runs" / "batch_a" / ".unpacked").exists()


def test_extract_7z(tmp_path):
    py7zr = pytest.importorskip("py7zr")
    src = tmp_path / "src"
    build_run(src, name="run_0000001_grid_000001")
    arcs = tmp_path / "archives"; arcs.mkdir()
    with py7zr.SevenZipFile(arcs / "batch_a.7z", "w") as z:
        z.writeall(src / "run_0000001_grid_000001", "run_0000001_grid_000001")
    batch.extract_archives(arcs, tmp_path / "runs")
    assert len(batch.find_runs(tmp_path / "runs")) == 1


def test_extract_rejects_unsafe_paths(tmp_path):
    arcs = tmp_path / "archives"; arcs.mkdir()
    with zipfile.ZipFile(arcs / "evil.zip", "w") as z:
        z.writestr("../escape.txt", "x")
    with pytest.raises(ValueError, match="unsafe path"):
        batch.extract_archives(arcs, tmp_path / "runs")
    assert not (tmp_path / "escape.txt").exists()


def test_extract_no_archives(tmp_path):
    with pytest.raises(FileNotFoundError):
        batch.extract_archives(tmp_path, tmp_path / "runs")


def test_inventory_identical_runs(tmp_path):
    runs = [build_run(tmp_path, name=f"run_{i}").folder for i in range(3)]
    per_run, varying = batch.inventory(runs)
    assert per_run["met_hash"].nunique() == 1
    assert per_run["inp_hash"].nunique() == 1
    assert varying.empty


def test_inventory_finds_varying_weather_and_inp_line(tmp_path):
    a = build_run(tmp_path, name="run_a").folder
    b = build_run(tmp_path, name="run_b").folder
    met_b = b / "focusprzm_weather.met"
    met_b.write_text(met_b.read_text().replace("0.5000", "0.6000", 1))
    inp_b = next(b.glob("*.inp"))
    lines = inp_b.read_text().splitlines()
    lines[0] = lines[0] + " changed"
    inp_b.write_text("\n".join(lines) + "\n")

    per_run, varying = batch.inventory([a, b])
    assert per_run["met_hash"].nunique() == 2
    assert list(varying["line_no"]) == [1]
    assert varying.iloc[0]["n_distinct"] == 2


def test_qc_run_records_checks(two_batches):
    _, a, b = two_batches
    good, bad = batch.qc_run(a.folder), batch.qc_run(b.folder)
    assert good["read_ok"] and bad["read_ok"]
    assert good["unstable"] is False and bad["unstable"] is True
    assert good["n_log_errors"] == 0 and bad["n_log_errors"] == 1
    assert good["n_days"] == 60
    assert good["applied_total_gha"] == pytest.approx(2400)


def test_qc_run_unreadable_folder_does_not_raise(tmp_path):
    broken = tmp_path / "run_broken"; broken.mkdir()
    (broken / "x.ZTS").write_text("nothing useful\n")
    row = batch.qc_run(broken)
    assert row["read_ok"] is False and "error" in row


def test_qc_all_writes_csv_and_parquet(two_batches, tmp_path):
    root, a, b = two_batches
    out_csv, daily = tmp_path / "interim" / "runs_qc.csv", tmp_path / "interim" / "daily"
    qc = batch.qc_all(batch.find_runs(root), out_csv, daily, workers=2)
    assert len(qc) == 2 and out_csv.exists()
    assert sorted(p.stem for p in daily.glob("*.parquet")) == sorted([a.folder.name, b.folder.name])
    d = pd.read_parquet(daily / f"{a.folder.name}.parquet")
    assert {"rain_mm", "pest_runoff_gha", "is_spike"} <= set(d.columns)


def test_cli_inventory_and_qc(two_batches, tmp_path, capsys):
    root, _, _ = two_batches
    out = tmp_path / "interim"
    assert main(["inventory", "--runs", str(root), "--out", str(out)]) == 0
    assert (out / "inventory_runs.csv").exists()
    assert main(["qc", "--runs", str(root), "--out", str(out), "--workers", "1", "--no-daily"]) == 0
    assert "unstable: 1" in capsys.readouterr().out
    assert not (out / "daily").exists()


# --------------------------------------------------------------------------- #
# add_weather: weather files for result folders made by `rerun --variants`
# --------------------------------------------------------------------------- #
import logging  # noqa: E402

MET = "focusprzm_weather.met"


def _folder(path, met_text=None, extra=("RUN 1-1_A.ZTS",)):
    path.mkdir(parents=True)
    for name in extra:
        (path / name).write_text("results\n")
    if met_text is not None:
        (path / MET).write_text(met_text)
    return path


@pytest.fixture
def varied_tree(tmp_path):
    src, res = tmp_path / "runs", tmp_path / "runs_varied"
    _folder(src / "batch_a" / "run_0000001_grid_000001", "weather 1\n")
    _folder(src / "batch_b" / "deeper" / "run_0000002_grid_000002", "weather 2\n")
    v = {
        "copy1": _folder(res / "batch_x" / "run_0000001_grid_000001__v1"),
        "copy2": _folder(res / "batch_x" / "run_0000001_grid_000001__v2"),
        "other": _folder(res / "batch_y" / "run_0000002_grid_000002__v1"),
        "has": _folder(res / "batch_y" / "run_0000002_grid_000002__v2", "my own weather\n"),
        "plain": _folder(res / "batch_y" / "run_0000002_grid_000002"),
        "orphan": _folder(res / "batch_y" / "run_0000099_grid_000099__v1"),
    }
    return src, res, v


def test_add_weather(varied_tree, caplog):
    src, res, v = varied_tree
    with caplog.at_level(logging.WARNING, logger="runoffwatch"):
        n = batch.add_weather(res, src)
    assert n == 4
    assert (v["copy1"] / MET).read_text() == "weather 1\n"
    assert (v["copy2"] / MET).read_text() == "weather 1\n"
    assert (v["other"] / MET).read_text() == "weather 2\n"            # found deeper under the source root
    assert (v["plain"] / MET).read_text() == "weather 2\n"            # a folder without __vN uses its own name
    assert (v["has"] / MET).read_text() == "my own weather\n"         # left alone
    assert sorted(p.name for p in v["has"].iterdir()) == ["RUN 1-1_A.ZTS", MET]
    assert not any(p.suffix == ".met" for p in v["orphan"].iterdir())  # no source: only a warning
    assert any("run_0000099_grid_000099__v1" in r.getMessage() for r in caplog.records)
    # the source files are untouched, and a second call has nothing left to do except the orphan
    assert (src / "batch_a" / "run_0000001_grid_000001" / MET).read_text() == "weather 1\n"
    assert batch.add_weather(res, src) == 0


def test_add_weather_uppercase_met_counts_as_present(tmp_path):
    src, res = tmp_path / "src", tmp_path / "res"
    _folder(src / "b" / "run_1_grid_1", "w\n")
    d = _folder(res / "b" / "run_1_grid_1__v1", extra=("OLD.MET",))
    assert batch.add_weather(res, src) == 0
    assert sorted(p.name for p in d.iterdir()) == ["OLD.MET"]


def test_add_weather_only_looks_two_levels_deep(tmp_path):
    """Result folders are <results_root>/<batch>/<field>__vN; a folder directly under the root is a batch."""
    src, res = tmp_path / "src", tmp_path / "res"
    _folder(src / "b" / "run_1_grid_1", "w\n")
    top = _folder(res / "run_1_grid_1__v1")
    assert batch.add_weather(res, src) == 0
    assert not (top / MET).exists()


def test_add_weather_empty_roots(tmp_path):
    (tmp_path / "a").mkdir(); (tmp_path / "b").mkdir()
    assert batch.add_weather(tmp_path / "a", tmp_path / "b") == 0


def test_cli_add_weather(varied_tree, capsys):
    src, res, v = varied_tree
    assert main(["add-weather", "--runs", str(res), "--source", str(src)]) == 0
    assert "weather file added to 4 result folders" in capsys.readouterr().out
    assert (v["copy1"] / MET).exists()

