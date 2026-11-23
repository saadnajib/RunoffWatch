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

YEARS = list(range(90, 100))
APP_LINES = [f"  0103{yy:02d}  0 2    5  2.40    1    0" for yy in YEARS]   # 1 March, 2.40 kg/ha
PRE_LINES = [
    "Run 1",
    "                    Simulation Location: R1Crop: Synthetic",
    "    0.84    0.20       0      15       1       1",
    "Chemical Input Data: ",
    "      10       1       0       0",
    "Synthocide  ",
    *APP_LINES,
    "       0    0.07    0.50",
]
APP = PRE_LINES.index("Chemical Input Data: ") + 3   # index of the first application line
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
def _one(tmp_path, runner, *, dest_name: str = "run_x", **kw):
    src = make_folder(tmp_path / "runs")
    dest = tmp_path / "out" / "batchA" / dest_name
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


# --------------------------------------------------------------------------- #
# PRZM's own errors, the real runner loop, and skipping known failures
# --------------------------------------------------------------------------- #
from runoffwatch.rerun import PrzmError, run_winprzm, _last_status   # noqa: E402
import runoffwatch.rerun as rerun_module                               # noqa: E402

posix_only = pytest.mark.skipif(os.name == "nt", reason="uses a shell script as stand-in program")


def _script(path: Path, body: str) -> Path:
    path.write_text("#!/bin/sh\n" + body + "\n")
    path.chmod(0o755)
    return path


def test_rerun_one_przm_error_gets_its_own_status(tmp_path):
    def boxed(work, exe, timeout):
        raise PrzmError("calculation error")
    _, dest, _, rec = _one(tmp_path, boxed)
    assert rec["status"] == "przm_error" and "calculation" in rec["note"]
    assert not dest.exists()


@posix_only
def test_run_winprzm_waits_for_the_program(tmp_path):
    exe = _script(tmp_path / "prog", "mkdir -p output && echo done > output/x.ZTS")
    run_winprzm(tmp_path, exe, timeout=10, poll=0.01)
    assert (tmp_path / "output" / "x.ZTS").read_text().strip() == "done"       # started inside the work folder


@posix_only
def test_run_winprzm_stops_a_program_that_runs_too_long(tmp_path):
    exe = _script(tmp_path / "prog", "sleep 30")
    t0 = time.time()
    with pytest.raises(subprocess.TimeoutExpired):
        run_winprzm(tmp_path, exe, timeout=0.3, poll=0.05)
    assert time.time() - t0 < 5


@posix_only
def test_run_winprzm_stops_the_program_when_an_error_box_shows(tmp_path, monkeypatch):
    exe = _script(tmp_path / "prog", "sleep 30")
    seen = []
    monkeypatch.setattr(rerun_module, "_error_box_open", lambda pid: seen.append(pid) or True)
    t0 = time.time()
    with pytest.raises(PrzmError):
        run_winprzm(tmp_path, exe, timeout=20, poll=0.05)
    assert time.time() - t0 < 5 and len(seen) == 1


def test_error_box_check_is_harmless_off_windows():
    if os.name != "nt":
        assert rerun_module._error_box_open(os.getpid()) is False


def test_last_status_uses_the_most_recent_line(tmp_path):
    log = tmp_path / "rerun_log.csv"
    assert _last_status(log, {"przm_error"}) == set()
    log.write_text("run,batch,status,seconds,zts_bytes,note\n"
                   "a,b,przm_error,1,0,x\n" "c,b,przm_error,1,0,x\n" "c,b,ok,3,999,\n" "d,b,empty,1,0,\n")
    assert _last_status(log, {"przm_error"}) == {"a"}


def test_rerun_all_skips_fields_przm_could_not_calculate(tree, tmp_path):
    out = tmp_path / "out"

    def boxed(work, exe, timeout):
        raise PrzmError("calculation error")

    first = rerun_all(tree, out, "WINPRZM.exe", "rr", workers=1, runner=boxed)
    assert {r["status"] for r in first} == {"przm_error"} and len(first) == 4
    again = FakeRunner()
    assert rerun_all(tree, out, "WINPRZM.exe", "rr", workers=1, runner=again) == []          # all skipped
    assert again.calls == []
    retried = rerun_all(tree, out, "WINPRZM.exe", "rr", workers=1, retry_failed=True, runner=again)
    assert len(retried) == 4 and {r["status"] for r in retried} == {"ok"}


# --------------------------------------------------------------------------- #
# Spray dates and doses: read_applications / patch_applications
# --------------------------------------------------------------------------- #
from runoffwatch.rerun import (DEFAULT_DOSES, DEFAULT_WINDOWS, Variant, make_variants,   # noqa: E402
                               parse_window, patch_applications, read_applications)

DATES10 = [(d, m) for d, m in [(15, 2), (20, 2), (1, 3), (5, 3), (10, 3), (31, 3), (1, 4), (15, 4), (28, 2), (30, 4)]]


def test_inp_helper_has_ten_applications_before_soil_series():
    lines = inp_bytes().split(CRLF)
    assert lines[APP - 3] == b"Chemical Input Data: "
    assert APP + 10 < SOIL and lines[SOIL].startswith(b"Soil Series")


def test_read_applications_values():
    apps = read_applications(inp_bytes())
    assert len(apps) == 10
    assert [a["year"] for a in apps] == YEARS
    assert all(a["day"] == 1 and a["month"] == 3 for a in apps)
    assert all(a["rate_kgha"] == pytest.approx(2.4) for a in apps)
    assert read_applications(inp_bytes().replace(CRLF, b"\n")) == apps


def test_patch_applications_changes_only_the_application_lines():
    raw = inp_bytes()
    new = patch_applications(raw, DATES10, "1.20")
    assert len(new) == len(raw)
    old_lines, new_lines = raw.split(CRLF), new.split(CRLF)
    assert len(new_lines) == len(old_lines) and new.count(CRLF) == raw.count(CRLF)
    assert b"\n" not in new.replace(CRLF, b"")
    changed = [i for i, (a, b) in enumerate(zip(old_lines, new_lines)) if a != b]
    assert changed == list(range(APP, APP + 10))
    assert new_lines[APP] == b"  150290  0 2    5  1.20    1    0"
    apps = read_applications(new)
    assert [(a["day"], a["month"]) for a in apps] == DATES10
    assert [a["year"] for a in apps] == YEARS
    assert all(a["rate_kgha"] == pytest.approx(1.2) for a in apps)
    assert read_settings(new) == read_settings(raw)


def test_patch_applications_keeps_lf_files_lf():
    raw = inp_bytes().replace(CRLF, b"\n")
    new = patch_applications(raw, DATES10, "0.24")
    assert b"\r" not in new and len(new) == len(raw)
    assert read_applications(new)[0]["rate_kgha"] == pytest.approx(0.24)


def test_patch_applications_single_date_for_every_year():
    apps = read_applications(patch_applications(inp_bytes(), [(15, 4)]))
    assert [(a["day"], a["month"], a["year"]) for a in apps] == [(15, 4, y) for y in YEARS]
    assert all(a["rate_kgha"] == pytest.approx(2.4) for a in apps)      # dose untouched


def test_patch_applications_none_changes_nothing():
    raw = inp_bytes()
    assert patch_applications(raw) == raw
    assert patch_applications(raw, None, None) == raw
    only_rate = patch_applications(raw, rate="0.5")
    assert [(a["day"], a["month"]) for a in read_applications(only_rate)] == [(1, 3)] * 10


@pytest.mark.parametrize("dates", [DATES10[:9], DATES10 + [(1, 3)], [(1, 3), (2, 3)], []])
def test_patch_applications_wrong_number_of_dates(dates):
    with pytest.raises(RerunError):
        patch_applications(inp_bytes(), dates)


@pytest.mark.parametrize("date", [(31, 2), (29, 2), (0, 3), (1, 13), (31, 4)])
def test_patch_applications_impossible_date(date):
    with pytest.raises(RerunError, match="not a date"):
        patch_applications(inp_bytes(), [date])


def test_patch_applications_accepts_29_february_only_in_leap_years():
    dates = [(1, 3)] * 10
    dates[YEARS.index(92)] = (29, 2)                  # 1992 is a leap year
    assert read_applications(patch_applications(inp_bytes(), dates))[2]["day"] == 29


@pytest.mark.parametrize("rate", ["abc", "", "0", "0.00", "-1", "1234567", "12.3456"])
def test_patch_applications_bad_dose(rate):
    with pytest.raises(RerunError):
        patch_applications(inp_bytes(), rate=rate)


@pytest.mark.parametrize("rate", ["nan", "inf"])
def test_patch_applications_rejects_non_finite_dose(rate):
    with pytest.raises(RerunError):
        patch_applications(inp_bytes(), rate=rate)


def test_patch_applications_without_block():
    lines = [l for l in PRE_LINES + CHEM_LINES + POST_LINES if not l.startswith("Chemical Input Data")]
    with pytest.raises(RerunError, match="Chemical Input Data"):
        patch_applications(inp_bytes(lines), [(1, 3)])
    with pytest.raises(RerunError, match="Chemical Input Data"):
        read_applications(inp_bytes(lines))


def test_patch_applications_damaged_block():
    lines = PRE_LINES + CHEM_LINES + POST_LINES
    bad = list(lines); bad[APP + 4] = "  xx0394  0 2    5  2.40    1    0"
    with pytest.raises(RerunError, match="application line"):
        read_applications(inp_bytes(bad))
    truncated = lines[:APP + 4]
    with pytest.raises(RerunError):
        read_applications(inp_bytes(truncated))


def test_patch_inp_and_patch_applications_commute():
    raw = inp_bytes()
    a = patch_applications(patch_inp(raw), DATES10, "0.24")
    b = patch_inp(patch_applications(raw, DATES10, "0.24"))
    assert a == b
    assert read_settings(a)["henry"] == pytest.approx(float(HENRY_FIXED))
    assert read_applications(a)[0]["day"] == 15


# --------------------------------------------------------------------------- #
# parse_window / make_variants
# --------------------------------------------------------------------------- #
def test_parse_window_day_numbers():
    assert parse_window("15.02-30.04") == (46, 120)
    assert parse_window("01.10-30.11") == (274, 334)
    assert parse_window(" 01.01-31.12 ") == (1, 365)
    assert parse_window("01.03-01.03") == (60, 60)                  # single day


@pytest.mark.parametrize("text", ["", "abc", "15.02", "15/02-30/04", "32.01-05.02", "15.13-01.12",
                                  "29.02-01.03", "15.02-30.04-01.05", "15.02.2020-30.04", "a.b-c.d"])
def test_parse_window_bad_text(text):
    with pytest.raises(RerunError, match="15.02-30.04"):
        parse_window(text)


def test_parse_window_ending_before_start():
    with pytest.raises(RerunError, match="ends before"):
        parse_window("30.04-15.02")
    with pytest.raises(RerunError, match="ends before"):
        parse_window("01.12-31.01")


def test_make_variants_is_reproducible():
    a = make_variants("run_7", 10, 4, seed=3)
    assert a == make_variants("run_7", 10, 4, seed=3)
    assert all(isinstance(v, Variant) for v in a)
    with pytest.raises(Exception):
        a[0].rate = "9"                                           # frozen
    assert make_variants("run_7", 10, 4, seed=4) != a
    assert make_variants("run_8", 10, 4, seed=3) != a
    assert make_variants("run_7", 10, 0) == []


def test_make_variants_dates_inside_window_and_real_in_every_year():
    import datetime as dt
    for name in [f"field_{i}" for i in range(40)]:
        for v in make_variants(name, 10, 3):
            assert v.window in DEFAULT_WINDOWS and v.rate in DEFAULT_DOSES
            assert len(v.dates) == 10
            first, last = parse_window(v.window)
            for day, month in v.dates:
                assert (day, month) != (29, 2)
                assert first <= dt.date(2001, month, day).timetuple().tm_yday <= last
                for year in range(1990, 2000):
                    dt.date(year, month, day)                       # raises if not a real date
            assert read_applications(patch_applications(inp_bytes(), list(v.dates), v.rate))[0]["day"] == v.dates[0][0]


def test_make_variants_suffixes_and_one_date_per_year():
    vs = make_variants("f", 7, 5)
    assert [v.suffix for v in vs] == ["__v1", "__v2", "__v3", "__v4", "__v5"]
    assert all(len(v.dates) == 7 for v in vs)
    assert len({v.dates for v in vs}) == 5                          # different draws per copy


def test_make_variants_dates_vary_between_years():
    vs = make_variants("f", 10, 3, windows=("15.02-30.04",))
    assert all(len(set(v.dates)) > 1 for v in vs)
    single = make_variants("f", 10, 2, windows=("10.03-10.03",))
    assert all(set(v.dates) == {(10, 3)} for v in single)


def test_make_variants_two_windows_two_copies_cover_both():
    for name in [f"field_{i}" for i in range(30)]:
        assert {v.window for v in make_variants(name, 10, 2)} == set(DEFAULT_WINDOWS)


def test_make_variants_doses_used_about_equally():
    from collections import Counter
    count = Counter(v.rate for i in range(600) for v in make_variants(f"field_{i}", 2, 1))
    assert set(count) == set(DEFAULT_DOSES)
    assert all(150 <= c <= 250 for c in count.values()), count
    wins = Counter(v.window for i in range(600) for v in make_variants(f"field_{i}", 2, 1))
    assert all(240 <= c <= 360 for c in wins.values()), wins


@pytest.mark.parametrize("kw", [dict(windows=("15.02-30.04", "bad")), dict(windows=("30.04-15.02",)),
                                dict(doses=("abc",)), dict(doses=("1234567",)), dict(doses=("1.2", "x"))])
def test_make_variants_bad_window_or_dose(kw):
    with pytest.raises(RerunError):
        make_variants("f", 10, 2, **kw)


def test_make_variants_rejects_zero_dose():
    with pytest.raises(RerunError):
        make_variants("f", 10, 2, doses=("0",))


@pytest.mark.parametrize("kw", [dict(windows=()), dict(doses=())])
def test_make_variants_empty_lists_raise_rerun_error(kw):
    with pytest.raises(RerunError):
        make_variants("f", 10, 2, **kw)


# --------------------------------------------------------------------------- #
# rerun_one with a variant
# --------------------------------------------------------------------------- #
def test_rerun_one_with_variant(tmp_path):
    v = make_variants("run_x", 10, 1, seed=5)[0]
    _, dest, _, rec = _one(tmp_path, FakeRunner(), dest_name="run_x__v1", variant=v)
    assert rec["status"] == "ok", rec
    assert rec["run"] == "run_x__v1" == dest.name and rec["batch"] == "batchA"
    stored = (dest / "Run 1-1_123.inp").read_bytes()
    apps = read_applications(stored)
    assert tuple((a["day"], a["month"]) for a in apps) == v.dates
    assert all(a["rate_kgha"] == pytest.approx(float(v.rate)) for a in apps)
    assert [a["year"] for a in apps] == YEARS
    s = read_settings(stored)
    assert s["henry"] == pytest.approx(float(HENRY_FIXED))
    assert s["moisture_ref"] == pytest.approx(float(MOISTURE_REF_FIXED))
    assert stored == patch_applications(patch_inp(inp_bytes()), list(v.dates), v.rate)
    assert (dest / "focusprzm_weather.met").exists()                # copy_weather defaults to True here


def test_rerun_one_without_weather_copy(tmp_path):
    runner = FakeRunner()
    _, dest, work, rec = _one(tmp_path, runner, copy_weather=False)
    assert rec["status"] == "ok"
    assert sorted(p.name for p in dest.iterdir()) == sorted(["Run 1-1_123.inp", RUN_FILE, "RUN X.ZTS", "RUN X.OUT"])
    assert is_done(dest)
    assert (work / "focusprzm_weather.met").exists()               # PRZM still had its weather file


def test_rerun_one_variant_on_inp_without_application_block_fails(tmp_path):
    src = make_folder(tmp_path / "runs")
    lines = [l for l in PRE_LINES + CHEM_LINES + POST_LINES if not l.startswith("Chemical Input Data")]
    (src / "Run 1-1_123.inp").write_bytes(inp_bytes(lines))
    runner = FakeRunner()
    v = make_variants("run_x", 10, 1)[0]
    rec = rerun_one(src, tmp_path / "out" / "run_x__v1", tmp_path / "work", Path("x.exe"), runner=runner,
                    work_name=WORK_NAME, variant=v)
    assert rec["status"] == "failed" and "Chemical Input Data" in rec["note"]
    assert rec["run"] == "run_x__v1" and runner.calls == []


# --------------------------------------------------------------------------- #
# rerun_all with variants
# --------------------------------------------------------------------------- #
FIELDS = [("batchA", "run_1"), ("batchA", "run_2"), ("batchA", "run_3"), ("batchB", "run_4")]


def _read_plan(out: Path) -> list[dict]:
    with open(out / "rerun_plan.csv", newline="") as fh:
        return list(csv.DictReader(fh))


def test_rerun_all_variants_layout_plan_and_settings(tree, tmp_path):
    out = tmp_path / "out"
    runner = FakeRunner()
    recs = rerun_all(tree, out, "WINPRZM.exe", "rr", workers=2, variants=3, seed=7, runner=runner)
    assert len(recs) == 12 and {r["status"] for r in recs} == {"ok"}, recs
    want = sorted(f"{run}__v{k}" for _, run in FIELDS for k in (1, 2, 3))
    assert sorted(r["run"] for r in recs) == want
    for batch, run in FIELDS:
        assert not (out / batch / run).exists()
        assert sorted(p.name for p in (out / batch).iterdir() if p.name.startswith(run)) == [
            f"{run}__v1", f"{run}__v2", f"{run}__v3"]
    plan = _read_plan(out)
    assert len(plan) == 12 and sorted(p["run"] for p in plan) == want
    for p in plan:
        d = out / p["batch"] / p["run"]
        assert p["run"].startswith(p["field"] + "__v")
        apps = read_applications((d / "Run 1-1_123.inp").read_bytes())
        assert " ".join(f"{a['day']:02d}.{a['month']:02d}" for a in apps) == p["spray_dates_day.month"]
        assert all(a["rate_kgha"] == pytest.approx(float(p["dose_kgha"])) for a in apps)
        assert p["window"] in DEFAULT_WINDOWS and p["dose_kgha"] in DEFAULT_DOSES
        k = int(p["run"].rsplit("__v", 1)[1])
        v = make_variants(p["field"], 10, 3, seed=7)[k - 1]
        assert (p["window"], p["dose_kgha"]) == (v.window, v.rate)
        assert not (d / "focusprzm_weather.met").exists()             # default: no weather copy with variants
    settings = (out / "rerun_settings.txt").read_text()
    for line in ["variants=3", f"windows={','.join(DEFAULT_WINDOWS)}", f"doses={','.join(DEFAULT_DOSES)}", "seed=7",
                 f"henry={HENRY_FIXED}", f"moisture_ref={MOISTURE_REF_FIXED}"]:
        assert line in settings.splitlines()
    assert sorted(r["run"] for r in _read_log(out)) == want


def test_rerun_all_variants_second_call_does_nothing(tree, tmp_path):
    out = tmp_path / "out"
    rerun_all(tree, out, "WINPRZM.exe", "rr", variants=2, runner=FakeRunner())
    plan = (out / "rerun_plan.csv").read_bytes()
    again = FakeRunner()
    assert rerun_all(tree, out, "WINPRZM.exe", "rr", variants=2, runner=again) == []
    assert again.calls == []
    assert (out / "rerun_plan.csv").read_bytes() == plan
    assert len(_read_log(out)) == 8


@pytest.mark.parametrize("kw", [dict(windows=("01.03-31.03",)), dict(doses=("1.00",)), dict(seed=2),
                                dict(variants=3)])
def test_rerun_all_variants_refuse_other_plan_in_same_folder(tree, tmp_path, kw):
    out = tmp_path / "out"
    rerun_all(tree, out, "WINPRZM.exe", "rr", variants=2, limit=1, runner=FakeRunner())
    other = FakeRunner()
    args = dict(variants=2) | kw
    with pytest.raises(RerunError, match="other settings"):
        rerun_all(tree, out, "WINPRZM.exe", "rr", runner=other, **args)
    assert other.calls == []


def test_rerun_all_plain_run_refused_in_varied_folder(tree, tmp_path):
    out = tmp_path / "out"
    rerun_all(tree, out, "WINPRZM.exe", "rr", variants=2, limit=1, runner=FakeRunner())
    other = FakeRunner()
    with pytest.raises(RerunError):
        rerun_all(tree, out, "WINPRZM.exe", "rr", runner=other)
    assert other.calls == []


def test_rerun_all_varied_run_refused_in_plain_folder(tree, tmp_path):
    out = tmp_path / "out"
    rerun_all(tree, out, "WINPRZM.exe", "rr", limit=1, runner=FakeRunner())
    other = FakeRunner()
    with pytest.raises(RerunError):
        rerun_all(tree, out, "WINPRZM.exe", "rr", variants=2, runner=other)
    assert other.calls == []


def _finished(root: Path, batch: str, run: str, zts: int = 1000) -> Path:
    d = root / batch / run
    d.mkdir(parents=True)
    (d / "R.ZTS").write_bytes(b"Z" * zts)
    (d / "R.OUT").write_bytes(b"out")
    return d


def test_rerun_all_fields_from(tree, tmp_path):
    fixed = tmp_path / "fixed"
    _finished(fixed, "batchA", "run_1")
    _finished(fixed, "batchB", "run_4")
    _finished(fixed, "batchA", "run_2", zts=100)                     # not finished
    out = tmp_path / "out"
    recs = rerun_all(tree, out, "WINPRZM.exe", "rr", variants=2, fields_from=fixed, runner=FakeRunner())
    assert sorted(r["run"] for r in recs) == ["run_1__v1", "run_1__v2", "run_4__v1", "run_4__v2"]
    assert sorted(p["field"] for p in _read_plan(out)) == ["run_1", "run_1", "run_4", "run_4"]


def test_rerun_all_fields_from_without_results(tree, tmp_path):
    empty = tmp_path / "fixed"
    _finished(empty, "batchA", "run_1", zts=10)
    runner = FakeRunner()
    with pytest.raises(FileNotFoundError):
        rerun_all(tree, tmp_path / "out", "WINPRZM.exe", "rr", variants=2, fields_from=empty, runner=runner)
    with pytest.raises(FileNotFoundError):
        rerun_all(tree, tmp_path / "out", "WINPRZM.exe", "rr", variants=2, fields_from=tmp_path / "missing",
                  runner=runner)
    assert runner.calls == []


def test_rerun_all_limit_counts_fields_not_copies(tree, tmp_path):
    runner = FakeRunner()
    recs = rerun_all(tree, tmp_path / "out", "WINPRZM.exe", "rr", variants=3, limit=2, runner=runner)
    assert len(recs) == 6 and len(runner.calls) == 6
    assert sorted(r["run"] for r in recs) == sorted(f"run_{i}__v{k}" for i in (1, 2) for k in (1, 2, 3))
    assert len(_read_plan(tmp_path / "out")) == 6


def test_rerun_all_copy_weather_defaults_and_override(tree, tmp_path):
    rerun_all(tree, tmp_path / "plain", "WINPRZM.exe", "rr", limit=1, runner=FakeRunner())
    assert (tmp_path / "plain" / "batchA" / "run_1" / "focusprzm_weather.met").exists()
    rerun_all(tree, tmp_path / "varied", "WINPRZM.exe", "rr", variants=1, limit=1, runner=FakeRunner())
    assert not (tmp_path / "varied" / "batchA" / "run_1__v1" / "focusprzm_weather.met").exists()
    rerun_all(tree, tmp_path / "varied_met", "WINPRZM.exe", "rr", variants=1, limit=1, copy_weather=True,
              runner=FakeRunner())
    assert (tmp_path / "varied_met" / "batchA" / "run_1__v1" / "focusprzm_weather.met").exists()
    rerun_all(tree, tmp_path / "plain_nomet", "WINPRZM.exe", "rr", limit=1, copy_weather=False, runner=FakeRunner())
    assert not (tmp_path / "plain_nomet" / "batchA" / "run_1" / "focusprzm_weather.met").exists()


@pytest.mark.parametrize("kw", [dict(variants=-1), dict(variants=2, windows=("bad",)),
                                dict(variants=2, doses=("abc",))])
def test_rerun_all_bad_variant_arguments_raise_before_any_run(tree, tmp_path, kw):
    runner = FakeRunner()
    with pytest.raises(RerunError):
        rerun_all(tree, tmp_path / "out", "WINPRZM.exe", "rr", runner=runner, **kw)
    assert runner.calls == [] and not (tmp_path / "out").exists()


def test_rerun_all_variants_damaged_field_does_not_stop_others(tree, tmp_path):
    (tree / "batchA" / "run_2" / "Run 1-1_123.inp").write_bytes(b"not an inp\r\n")
    out = tmp_path / "out"
    recs = rerun_all(tree, out, "WINPRZM.exe", "rr", workers=2, variants=2, runner=FakeRunner())
    by_run = {r["run"]: r["status"] for r in recs}
    assert len(recs) == 8
    assert by_run["run_2__v1"] == by_run["run_2__v2"] == "failed"
    assert {s for r, s in by_run.items() if not r.startswith("run_2")} == {"ok"}
    assert len(_read_plan(out)) == 8


def test_rerun_all_variants_field_without_application_block(tree, tmp_path):
    lines = [l for l in PRE_LINES + CHEM_LINES + POST_LINES if not l.startswith("Chemical Input Data")]
    (tree / "batchA" / "run_3" / "Run 1-1_123.inp").write_bytes(inp_bytes(lines))
    recs = rerun_all(tree, tmp_path / "out", "WINPRZM.exe", "rr", variants=1, runner=FakeRunner())
    by_run = {r["run"]: r for r in recs}
    assert by_run["run_3__v1"]["status"] == "failed" and "Chemical Input Data" in by_run["run_3__v1"]["note"]
    assert sum(r["status"] == "ok" for r in recs) == 3
