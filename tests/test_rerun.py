"""Tests for runoffwatch.rerun (patching PRZM inputs and re-running WINPRZM.exe).

WINPRZM.exe cannot run here, so every test that runs a folder injects a fake
`runner(work, exe, timeout)` that writes the result files PRZM would write.
All input files are built in this module; no real data is used.
"""

from __future__ import annotations

import csv
import os
import subprocess
import threading
import time
from pathlib import Path

import pytest

from runoffwatch.rerun import (HENRY_FIXED, MAX_PATH_CHARS, MOISTURE_REF_FIXED, RUN_FILE, RerunError,
                               find_inputs, has_inputs, is_done, patch_inp, patch_run, read_settings,
                               rerun_all, rerun_one)

CRLF = b"\r\n"
WORK_NAME = r"C:\Temp\rr\w0"

PRE_LINES = [
    "Run 1",
    "                    Simulation Location: R1Crop: Synthetic",
    "    0.84    0.20       0      15       1       1",
    "Chemical Input Data: ",
    "      10       1       0       0",
    "Synthocide  ",
    "       0    0.07    0.50",
]
CHEM_LINES = [
    "Soil Series:         R1",
    "     100           0   0   2   0   0   0   2   1   0",
    "    43000.30E-01   22.70",
    "    0.96",
    " 0.18 0.18 0.18 0.18 0.18 0.18 0.18 0.18 0.18 0.18 0.18 0.18 0.96   10",
    "   10   10   10   10   10   10   10   10   10   10   10   10",
    "    2.20      20",
    "       2    0.70     100",
    "       4",
]
POST_LINES = [
    "       1      10   1.410   0.270       0       0       0",
    "         0.01663 0.01663       0",
    "    WATR    YEAR      10    PEST    YEAR      10    CONC    YEAR      10   0",
]
SOIL = len(PRE_LINES)              # index of the "Soil Series" line

RUN_TEXT = "\r\n".join([
    "*** PRZM run file (synthetic)",
    "PRZM                    ON",
    "VADOFT                  OFF",
    "*** input file records",
    "  PATH                  E:\\Temp\\X3E6KQT8DM5KBWQ1S9\\",
    "  METEOROLOGY       1   focusprzm_weather.met",
    "  PRZM INPUT        1   Run 1-1_123.inp",
    "*** output file records",
    "  PATH                  E:\\Temp\\X3E6KQT8DM5KBWQ1S9\\output\\",
    "  TIME SERIES       1   Run 1-1_123.ZTS",
    "  PRZM OUTPUT       1   Run 1-1_123.OUT",
    "*** scratch file records",
    "  PATH",
    "  PRZM RESTART      1   RESTART.PRZ",
    "ENDFILES",
    "",
]).encode()


def inp_bytes(lines: list[str] | None = None) -> bytes:
    lines = PRE_LINES + CHEM_LINES + POST_LINES if lines is None else lines
    return CRLF.join(l.encode() for l in lines) + CRLF


def make_folder(base: Path, batch: str = "batchA", run: str = "run_x", *, met: bool = True,
                run_file: bool = True, inp: bool = True) -> Path:
    folder = base / batch / run
    folder.mkdir(parents=True)
    if inp:
        (folder / "Run 1-1_123.inp").write_bytes(inp_bytes())
    if met:
        (folder / "focusprzm_weather.met").write_bytes(b" 010190     0.0000    0.0480    6.0000  300.0000  250.0000\r\n")
    if run_file:
        (folder / RUN_FILE).write_bytes(RUN_TEXT)
    (folder / "mc.log").write_text("INFO  MC run finished\n")
    return folder


class FakeRunner:
    """Writes the two result files PRZM would write; records calls and concurrency."""

    def __init__(self, zts_bytes: int = 1000, write: bool = True, delay: float = 0.0, exc: Exception | None = None):
        self.zts_bytes, self.write, self.delay, self.exc = zts_bytes, write, delay, exc
        self.calls: list[Path] = []
        self.run_files: list[bytes] = []
        self.active: set[Path] = set()
        self.max_active = 0
        self.overlaps: list[Path] = []
        self._lock = threading.Lock()

    def __call__(self, work: Path, exe: Path, timeout: float) -> None:
        with self._lock:
            if work in self.active:
                self.overlaps.append(work)
            self.active.add(work)
            self.max_active = max(self.max_active, len(self.active))
            self.calls.append(work)
            self.run_files.append((work / RUN_FILE).read_bytes())
        try:
            if self.delay:
                time.sleep(self.delay)
            if self.exc is not None:
                raise self.exc
            if self.write:
                (work / "output" / "RUN X.ZTS").write_bytes(b"Z" * self.zts_bytes)
                (work / "output" / "RUN X.OUT").write_bytes(b" PRZM-3 OUTPUT (fake)\r\n")
        finally:
            with self._lock:
                self.active.discard(work)


# --------------------------------------------------------------------------- #
# read_settings / patch_inp
# --------------------------------------------------------------------------- #
def test_read_settings_values():
    s = read_settings(inp_bytes())
    assert s["henry"] == pytest.approx(0.03)
    assert s["q10"] == pytest.approx(2.2)
    assert s["q10_base_temp"] == pytest.approx(20)
    assert s["moisture_flag"] == 2
    assert s["moisture_exp"] == pytest.approx(0.7)
    assert s["moisture_ref"] == pytest.approx(100)


def test_read_settings_also_reads_lf_files():
    raw = inp_bytes().replace(CRLF, b"\n")
    assert read_settings(raw)["henry"] == pytest.approx(0.03)


def test_patch_inp_changes_exactly_the_two_fields():
    raw = inp_bytes()
    new = patch_inp(raw)
    assert len(new) == len(raw)
    old_lines, new_lines = raw.split(CRLF), new.split(CRLF)
    assert len(new_lines) == len(old_lines)
    assert new.count(CRLF) == raw.count(CRLF)
    assert b"\n" not in new.replace(CRLF, b"")                # no bare LF introduced
    changed = [i for i, (a, b) in enumerate(zip(old_lines, new_lines)) if a != b]
    assert changed == [SOIL + 2, SOIL + 7]
    assert new_lines[SOIL + 2] == b"    43000.37E-06   22.70"
    assert new_lines[SOIL + 7] == b"       2    0.70       1"
    s = read_settings(new)
    assert s["henry"] == pytest.approx(float(HENRY_FIXED))
    assert s["moisture_ref"] == pytest.approx(float(MOISTURE_REF_FIXED))
    assert s["q10"] == pytest.approx(2.2) and s["moisture_exp"] == pytest.approx(0.7)


def test_patch_inp_none_leaves_value_untouched():
    raw = inp_bytes()
    assert patch_inp(raw, henry=None, moisture_ref=None) == raw
    only_henry = patch_inp(raw, henry="0.12E-03", moisture_ref=None)
    assert read_settings(only_henry)["henry"] == pytest.approx(1.2e-4)
    assert only_henry.split(CRLF)[SOIL + 7] == raw.split(CRLF)[SOIL + 7]
    only_moist = patch_inp(raw, henry=None, moisture_ref="0.5")
    assert read_settings(only_moist)["moisture_ref"] == pytest.approx(0.5)
    assert only_moist.split(CRLF)[SOIL + 2] == raw.split(CRLF)[SOIL + 2]


def test_patch_inp_keeps_lf_files_lf():
    raw = inp_bytes().replace(CRLF, b"\n")
    new = patch_inp(raw)
    assert b"\r" not in new and len(new) == len(raw)


@pytest.mark.parametrize("kwargs", [dict(henry="0.370E-06"), dict(moisture_ref="123456789")])
def test_patch_inp_rejects_values_too_wide(kwargs):
    with pytest.raises(RerunError, match="does not fit"):
        patch_inp(inp_bytes(), **kwargs)


def test_patch_inp_rejects_file_without_soil_series():
    lines = [l for l in PRE_LINES + CHEM_LINES + POST_LINES if not l.startswith("Soil Series")]
    with pytest.raises(RerunError, match="Soil Series"):
        patch_inp(inp_bytes(lines))
    with pytest.raises(RerunError, match="Soil Series"):
        read_settings(inp_bytes(lines))


def test_patch_inp_rejects_truncated_chemical_block():
    lines = PRE_LINES + CHEM_LINES[:5]
    with pytest.raises(RerunError):
        patch_inp(inp_bytes(lines))


def test_patch_inp_rejects_short_moisture_line():
    lines = PRE_LINES + CHEM_LINES + POST_LINES
    lines[SOIL + 7] = "       2  0.70 100"
    with pytest.raises(RerunError, match="shorter"):
        patch_inp(inp_bytes(lines))


def test_rerun_error_is_a_value_error():
    assert issubclass(RerunError, ValueError)


# --------------------------------------------------------------------------- #
# patch_run
# --------------------------------------------------------------------------- #
def test_patch_run_replaces_both_filled_path_lines():
    new = patch_run(RUN_TEXT, WORK_NAME)
    old_lines, new_lines = RUN_TEXT.split(CRLF), new.split(CRLF)
    assert len(new_lines) == len(old_lines)
    changed = [i for i, (a, b) in enumerate(zip(old_lines, new_lines)) if a != b]
    assert changed == [4, 8]
    assert new_lines[4] == b"  PATH                  C:\\Temp\\rr\\w0\\"
    assert new_lines[8] == b"  PATH                  C:\\Temp\\rr\\w0\\output\\"
    assert new_lines[12] == b"  PATH"                          # scratch PATH stays empty
    assert b"X3E6KQT8DM5KBWQ1S9" not in new
    assert new.count(CRLF) == RUN_TEXT.count(CRLF)


def test_patch_run_accepts_trailing_separator():
    assert patch_run(RUN_TEXT, WORK_NAME + "\\") == patch_run(RUN_TEXT, WORK_NAME)


def test_patch_run_rejects_too_long_work_path():
    long_name = "C:\\" + "x" * (MAX_PATH_CHARS - len("C:\\\\output\\") + 1)
    assert len(long_name + "\\output\\") == MAX_PATH_CHARS + 1
    with pytest.raises(RerunError, match="too long"):
        patch_run(RUN_TEXT, long_name)
    ok_name = long_name[:-1]                                    # exactly MAX_PATH_CHARS
    assert b"output" in patch_run(RUN_TEXT, ok_name)


def test_patch_run_rejects_space_in_work_path():
    with pytest.raises(RerunError, match="space"):
        patch_run(RUN_TEXT, r"C:\Temp\r r")


def test_patch_run_needs_two_filled_path_lines():
    one = RUN_TEXT.replace(b"  PATH                  E:\\Temp\\X3E6KQT8DM5KBWQ1S9\\output\\", b"  PATH")
    with pytest.raises(RerunError, match="found 1"):
        patch_run(one, WORK_NAME)


# --------------------------------------------------------------------------- #
# has_inputs / find_inputs
# --------------------------------------------------------------------------- #
def test_has_inputs(tmp_path):
    assert has_inputs(make_folder(tmp_path, run="full"))
    assert not has_inputs(make_folder(tmp_path, run="no_met", met=False))
    assert not has_inputs(make_folder(tmp_path, run="no_run", run_file=False))
    assert not has_inputs(make_folder(tmp_path, run="no_inp", inp=False))


def test_find_inputs_skips_incomplete_folders(tmp_path):
    good1 = make_folder(tmp_path, "batchA", "run_1")
    good2 = make_folder(tmp_path, "batchB", "run_2")
    make_folder(tmp_path, "batchA", "run_no_met", met=False)
    make_folder(tmp_path, "batchA", "run_no_run", run_file=False)
    assert find_inputs(tmp_path) == sorted([good1, good2])
    assert find_inputs(str(tmp_path)) == sorted([good1, good2])


def test_find_inputs_empty_root_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        find_inputs(tmp_path)
    make_folder(tmp_path, run="no_met", met=False)
    with pytest.raises(FileNotFoundError):
        find_inputs(tmp_path)


# --------------------------------------------------------------------------- #
# rerun_one
# --------------------------------------------------------------------------- #
def _one(tmp_path, runner, **kw):
    src = make_folder(tmp_path / "runs")
    dest = tmp_path / "out" / "batchA" / "run_x"
    work = tmp_path / "work"
    rec = rerun_one(src, dest, work, Path("WINPRZM.exe"), runner=runner, work_name=WORK_NAME, **kw)
    return src, dest, work, rec


def test_rerun_one_success(tmp_path):
    runner = FakeRunner(zts_bytes=1000)
    src, dest, work, rec = _one(tmp_path, runner)
    assert rec["status"] == "ok", rec
    assert rec["run"] == "run_x" and rec["batch"] == "batchA"
    assert rec["zts_bytes"] == 1000 and rec["note"] == ""
    assert sorted(p.name for p in dest.iterdir()) == sorted(
        ["Run 1-1_123.inp", "focusprzm_weather.met", RUN_FILE, "RUN X.ZTS", "RUN X.OUT"])
    assert (dest / "Run 1-1_123.inp").read_bytes() == patch_inp(inp_bytes())
    assert (dest / "focusprzm_weather.met").read_bytes() == (src / "focusprzm_weather.met").read_bytes()
    assert (dest / RUN_FILE).read_bytes() == patch_run(RUN_TEXT, WORK_NAME)
    assert runner.run_files == [patch_run(RUN_TEXT, WORK_NAME)]
    assert runner.calls == [work]
    assert is_done(dest)
    # the source folder is not touched
    assert (src / "Run 1-1_123.inp").read_bytes() == inp_bytes()
    assert (src / RUN_FILE).read_bytes() == RUN_TEXT


def test_rerun_one_passes_settings_through(tmp_path):
    _, dest, _, rec = _one(tmp_path, FakeRunner(), henry=None, moisture_ref="0.5")
    assert rec["status"] == "ok"
    s = read_settings((dest / "Run 1-1_123.inp").read_bytes())
    assert s["henry"] == pytest.approx(0.03) and s["moisture_ref"] == pytest.approx(0.5)


def test_rerun_one_runner_writes_nothing(tmp_path):
    _, dest, _, rec = _one(tmp_path, FakeRunner(write=False))
    assert rec["status"] == "failed"
    assert "no result files" in rec["note"]
    assert not dest.exists()


def test_rerun_one_timeout(tmp_path):
    runner = FakeRunner(exc=subprocess.TimeoutExpired(cmd="WINPRZM.exe", timeout=5))
    _, dest, _, rec = _one(tmp_path, runner, timeout=5)
    assert rec["status"] == "timeout"
    assert "5 s" in rec["note"]
    assert not dest.exists()


def test_rerun_one_tiny_zts_is_empty(tmp_path):
    _, dest, _, rec = _one(tmp_path, FakeRunner(zts_bytes=100))
    assert rec["status"] == "empty"
    assert rec["zts_bytes"] == 100
    assert not is_done(dest)


def test_rerun_one_bad_inp_is_failed(tmp_path):
    src = make_folder(tmp_path / "runs")
    (src / "Run 1-1_123.inp").write_bytes(b"not an inp\r\n")
    runner = FakeRunner()
    rec = rerun_one(src, tmp_path / "out", tmp_path / "work", Path("x.exe"), runner=runner, work_name=WORK_NAME)
    assert rec["status"] == "failed" and "Soil Series" in rec["note"]
    assert runner.calls == []


def test_rerun_one_long_work_path_without_work_name_fails(tmp_path):
    src = make_folder(tmp_path / "runs")
    work = tmp_path / ("w" * MAX_PATH_CHARS)
    runner = FakeRunner()
    rec = rerun_one(src, tmp_path / "out", work, Path("x.exe"), runner=runner)
    assert rec["status"] == "failed" and "too long" in rec["note"]
    assert runner.calls == []


def test_rerun_one_cleans_work_folder_but_keeps_exe(tmp_path):
    work = tmp_path / "work"
    (work / "output").mkdir(parents=True)
    (work / "output" / "OLD.ZTS").write_bytes(b"Z" * 1000)
    (work / "output" / "OLD.OUT").write_bytes(b"old")
    (work / "stale.inp").write_bytes(b"old inp")
    (work / "leftover.txt").write_bytes(b"old")
    (work / "subdir").mkdir()
    (work / "WINPRZM.exe").write_bytes(b"MZ fake program")
    (work / "helper.EXE").write_bytes(b"MZ")

    # a runner that writes nothing must not pick up the old results
    _, dest, _, rec = _one(tmp_path, FakeRunner(write=False))
    assert rec["status"] == "failed"
    assert not dest.exists()
    names = {p.name for p in work.iterdir()}
    assert names == {"WINPRZM.exe", "helper.EXE", "output", "Run 1-1_123.inp", "focusprzm_weather.met", RUN_FILE}
    assert list((work / "output").iterdir()) == []
    assert (work / "WINPRZM.exe").read_bytes() == b"MZ fake program"


# --------------------------------------------------------------------------- #
# rerun_all
# --------------------------------------------------------------------------- #
@pytest.fixture
def tree(tmp_path, monkeypatch):
    """root/batchA/run_1..3 and root/batchB/run_4; cwd = tmp_path so work_root 'rr' is short."""
    monkeypatch.chdir(tmp_path)
    root = tmp_path / "root"
    for batch, run in [("batchA", "run_1"), ("batchA", "run_2"), ("batchA", "run_3"), ("batchB", "run_4")]:
        make_folder(root, batch, run)
    make_folder(root, "batchB", "run_no_met", met=False)
    return root


def _read_log(out: Path) -> list[dict]:
    with open(out / "rerun_log.csv", newline="") as fh:
        return list(csv.DictReader(fh))


def test_rerun_all_layout_log_and_settings(tree, tmp_path):
    out = tmp_path / "out"
    runner = FakeRunner()
    recs = rerun_all(tree, out, "WINPRZM.exe", "rr", workers=2, runner=runner)
    assert len(recs) == 4 and {r["status"] for r in recs} == {"ok"}, recs
    for batch, run in [("batchA", "run_1"), ("batchA", "run_2"), ("batchA", "run_3"), ("batchB", "run_4")]:
        d = out / batch / run
        assert is_done(d)
        assert (d / "Run 1-1_123.inp").read_bytes() == patch_inp(inp_bytes())
    assert not (out / "batchB" / "run_no_met").exists()
    rows = _read_log(out)
    assert sorted((r["batch"], r["run"]) for r in rows) == [
        ("batchA", "run_1"), ("batchA", "run_2"), ("batchA", "run_3"), ("batchB", "run_4")]
    assert all(r["status"] == "ok" and r["zts_bytes"] == "1000" for r in rows)
    settings = (out / "rerun_settings.txt").read_text()
    assert f"henry={HENRY_FIXED}" in settings
    assert f"moisture_ref={MOISTURE_REF_FIXED}" in settings
    assert f"source={tree.resolve()}" in settings
    assert {p.name for p in (tmp_path / "rr").iterdir()} == {"w0", "w1"}


def test_rerun_all_second_call_skips_finished(tree, tmp_path):
    out = tmp_path / "out"
    first = FakeRunner()
    rerun_all(tree, out, "WINPRZM.exe", "rr", workers=2, runner=first)
    assert len(first.calls) == 4
    second = FakeRunner()
    assert rerun_all(tree, out, "WINPRZM.exe", "rr", workers=2, runner=second) == []
    assert second.calls == []
    assert len(_read_log(out)) == 4                              # appended, header only once


def test_rerun_all_reruns_failed_and_empty(tree, tmp_path):
    out = tmp_path / "out"
    rerun_all(tree, out, "WINPRZM.exe", "rr", workers=1, runner=FakeRunner(zts_bytes=50))
    again = FakeRunner()
    recs = rerun_all(tree, out, "WINPRZM.exe", "rr", workers=1, runner=again)
    assert len(again.calls) == 4 and {r["status"] for r in recs} == {"ok"}
    rows = _read_log(out)
    assert [r["status"] for r in rows] == ["empty"] * 4 + ["ok"] * 4


def test_rerun_all_limit(tree, tmp_path):
    out = tmp_path / "out"
    runner = FakeRunner()
    recs = rerun_all(tree, out, "WINPRZM.exe", "rr", workers=2, limit=2, runner=runner)
    assert len(recs) == 2 and len(runner.calls) == 2
    assert sorted(r["run"] for r in recs) == ["run_1", "run_2"]         # first folders in sorted order
    # limit counts the first N folders, finished or not (applied before skipping done ones)
    again = FakeRunner()
    assert rerun_all(tree, out, "WINPRZM.exe", "rr", workers=2, limit=2, runner=again) == []
    assert again.calls == []
    more = FakeRunner()
    assert len(rerun_all(tree, out, "WINPRZM.exe", "rr", workers=2, limit=3, runner=more)) == 1


def test_rerun_all_workers_never_share_a_work_folder(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    root = tmp_path / "root"
    for i in range(8):
        make_folder(root, "batchA", f"run_{i}")
    runner = FakeRunner(delay=0.05)
    recs = rerun_all(root, tmp_path / "out", "WINPRZM.exe", "rr", workers=3, runner=runner)
    assert len(recs) == 8 and {r["status"] for r in recs} == {"ok"}
    assert runner.overlaps == []
    assert runner.max_active >= 2                               # really ran in parallel
    assert len(set(runner.calls)) <= 3
    assert {p.name for p in (tmp_path / "rr").iterdir()} == {"w0", "w1", "w2"}


def test_rerun_all_long_work_root_fails_every_folder(tree, tmp_path):
    # rerun_all gives rerun_one no work_name, so the real work path goes into 'Run 1.run'
    # and must be short (MAX_PATH_CHARS); a long work_root fails every folder.
    long_root = tmp_path / ("x" * MAX_PATH_CHARS)
    runner = FakeRunner()
    recs = rerun_all(tree, tmp_path / "out", "WINPRZM.exe", long_root, workers=1, runner=runner)
    assert len(recs) == 4
    assert {r["status"] for r in recs} == {"failed"}
    assert all("too long" in r["note"] for r in recs)
    assert runner.calls == []


@pytest.mark.skipif(os.name == "nt", reason="checks the non-Windows guard")
def test_rerun_all_default_runner_needs_windows(tmp_path):
    with pytest.raises(RuntimeError, match="Windows"):
        rerun_all(tmp_path / "missing", tmp_path / "out", tmp_path / "WINPRZM.exe")
    assert not (tmp_path / "out").exists()


# --------------------------------------------------------------------------- #
# Guards added after review
# --------------------------------------------------------------------------- #
def test_patch_inp_rejects_non_numeric_value():
    with pytest.raises(RerunError):
        patch_inp(inp_bytes(), henry="abc")
    with pytest.raises(RerunError):
        patch_inp(inp_bytes(), moisture_ref="x")


def test_patch_inp_rejects_short_henry_line():
    lines = PRE_LINES + CHEM_LINES + POST_LINES
    lines = list(lines)
    lines[SOIL + 2] = "    43000.3"
    with pytest.raises(RerunError):
        patch_inp(inp_bytes(lines))


def test_rerun_one_any_runner_error_is_a_failed_record(tmp_path):
    def crash(work, exe, timeout):
        raise RuntimeError("crash")
    _, dest, _, rec = _one(tmp_path, crash)
    assert rec["status"] == "failed" and "crash" in rec["note"]
    assert not dest.exists()


def test_rerun_all_checks_settings_before_starting(tree, tmp_path):
    runner = FakeRunner()
    with pytest.raises(RerunError):
        rerun_all(tree, tmp_path / "out", "WINPRZM.exe", "rr", henry="abc", runner=runner)
    with pytest.raises(RerunError):
        rerun_all(tree, tmp_path / "out", "WINPRZM.exe", "rr", henry="0.370E-06", runner=runner)   # 9 characters
    assert runner.calls == []


def test_rerun_all_refuses_to_mix_settings_in_one_output_folder(tree, tmp_path):
    out = tmp_path / "out"
    rerun_all(tree, out, "WINPRZM.exe", "rr", limit=1, runner=FakeRunner())
    other = FakeRunner()
    with pytest.raises(RerunError):
        rerun_all(tree, out, "WINPRZM.exe", "rr", henry="0.00E+00", runner=other)
    assert other.calls == []
    assert len(rerun_all(tree, out, "WINPRZM.exe", "rr", limit=2, runner=FakeRunner())) == 1   # same settings: continues
