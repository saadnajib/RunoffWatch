"""Re-run PRZM on your own Windows computer with corrected chemical settings.

Why this exists
---------------
Two settings in the delivered simulations turned out to be wrong (shown with
small test runs, see docs/DATA_REPORT.md, "Local re-runs"):

1. Henry constant 0.03: makes 65-80 % of every dose evaporate and makes the
   numbers of many runs explode. Flufenacet is about 100,000 times less
   volatile.
2. Reference soil moisture 100: this PRZM program works with moisture as a
   fraction (1 = field capacity), so 100 makes the pesticide decay about 25
   times too slowly and it piles up in the soil year after year.

`rerun_all` copies each run folder that has input files, changes these two
numbers, starts WINPRZM.exe on it and stores the result in the same folder
layout as the original data, so every other command of this package can be
pointed at the new folder.

PRZM details that matter here
-----------------------------
* The .inp file has fixed columns and Windows line endings. Only the wanted
  characters are replaced; everything else is kept byte for byte.
* 'Run 1.run' holds two absolute paths (input and output). They must be
  short (the delivered ones have 34 characters), so the work folder has to be
  something like C:\\Temp\\rr.
* WINPRZM.exe looks for the .run file in the folder it is started from.
"""

from __future__ import annotations

import csv
import logging
import os
import re
import shutil
import subprocess
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Callable

log = logging.getLogger(__name__)

HENRY_FIXED = "0.37E-06"      # dimensionless; published values for Flufenacet give 2.4e-7 to 5.3e-7
MOISTURE_REF_FIXED = "1"      # 1 = field capacity in this program
MAX_PATH_CHARS = 60           # PRZM reads the paths in fixed-width fields
RUN_FILE = "Run 1.run"
_PATH_LINE = re.compile(rb"^(  PATH {2,})(\S+)(\r?)$", re.M)


ERROR_BOX_TITLE = "Fortran"   # title of the message box PRZM shows when a calculation fails
SKIP_NEXT_TIME = {"przm_error"}   # outcomes that will not change when the same folder is run again


class RerunError(ValueError):
    """An input file does not look the way this module expects."""


class PrzmError(RuntimeError):
    """PRZM itself reported a calculation error for this field."""


# --------------------------------------------------------------------------- #
# 1. Editing the two input files
# --------------------------------------------------------------------------- #
def _fixed(line: bytes, start: int, end: int, text: str) -> bytes:
    """Replace columns start..end of a fixed-width line with right-aligned text."""
    if len(text) > end - start:
        raise RerunError(f"{text!r} does not fit into {end - start} columns")
    return line[:start] + text.rjust(end - start).encode() + line[end:]


def _number(text: str) -> None:
    try:
        float(text)
    except (TypeError, ValueError):
        raise RerunError(f"not a number: {text!r}") from None


def _chem_lines(lines: list[bytes]) -> int:
    for i, l in enumerate(lines):
        if l.startswith(b"Soil Series"):
            return i
    raise RerunError("no 'Soil Series' line in the .inp file")


def read_settings(raw: bytes) -> dict:
    """Henry constant, Q10 and the moisture-correction settings of an .inp file."""
    lines = raw.split(b"\r\n") if b"\r\n" in raw else raw.split(b"\n")
    soil = _chem_lines(lines)
    try:
        q = lines[soil + 6].split()
        m = lines[soil + 7].split()
        return {"henry": float(lines[soil + 2][8:16]), "q10": float(q[0]), "q10_base_temp": float(q[1]),
                "moisture_flag": int(m[0]), "moisture_exp": float(m[1]), "moisture_ref": float(m[2])}
    except (IndexError, ValueError) as e:
        raise RerunError(f"unexpected chemical block in the .inp file: {e}") from e


def patch_inp(raw: bytes, henry: str | None = HENRY_FIXED, moisture_ref: str | None = MOISTURE_REF_FIXED) -> bytes:
    """Return the .inp content with a new Henry constant and/or reference moisture.

    `None` leaves a value as it is. Nothing else in the file changes.
    """
    nl = b"\r\n" if b"\r\n" in raw else b"\n"
    lines = raw.split(nl)
    soil = _chem_lines(lines)
    read_settings(raw)                                   # fails early if the layout is not the known one
    if henry is not None:
        _number(henry)
        if len(lines[soil + 2]) < 16:
            raise RerunError("Henry line is shorter than 16 columns")
        lines[soil + 2] = _fixed(lines[soil + 2], 8, 16, henry)
    if moisture_ref is not None:
        _number(moisture_ref)
        if len(lines[soil + 7]) < 24:
            raise RerunError("moisture line is shorter than 24 columns")
        lines[soil + 7] = _fixed(lines[soil + 7], 16, 24, moisture_ref)
    return nl.join(lines)


def patch_run(raw: bytes, work_dir: str) -> bytes:
    """Point the input and output paths of a 'Run 1.run' file at work_dir (Windows path)."""
    base = work_dir.rstrip("\\/") + "\\"
    out = base + "output\\"
    if len(out) > MAX_PATH_CHARS or " " in base:
        raise RerunError(f"work folder too long or contains a space: {base!r} (use something like C:\\Temp\\rr)")
    found = [m for m in _PATH_LINE.finditer(raw)]
    if len(found) != 2:
        raise RerunError(f"expected 2 filled PATH lines in the .run file, found {len(found)}")
    (a, b) = found
    return (raw[:a.start(2)] + base.encode() + raw[a.end(2):b.start(2)] + out.encode() + raw[b.end(2):])


# --------------------------------------------------------------------------- #
# 2. Running one folder
# --------------------------------------------------------------------------- #
def _by_suffix(folder: Path) -> dict[str, Path]:
    return {p.suffix.lower(): p for p in folder.iterdir() if p.is_file()}


def has_inputs(folder: Path) -> bool:
    f = _by_suffix(folder)
    return ".inp" in f and ".met" in f and (folder / RUN_FILE).is_file()


def find_inputs(runs_root: str | Path) -> list[Path]:
    """All run folders below runs_root that hold .inp, .met and 'Run 1.run'."""
    root = Path(runs_root)
    out = sorted({p.parent for p in root.rglob(RUN_FILE) if has_inputs(p.parent)})
    if not out:
        raise FileNotFoundError(f"no run folders with input files under {root}")
    return out


def _empty(work: Path, tries: int = 5) -> None:
    """Remove everything from the work folder except the program. Windows sometimes keeps a
    file locked for a moment after PRZM ends, so a failed delete is tried again."""
    for attempt in range(tries):
        try:
            for p in work.iterdir() if work.is_dir() else []:
                if p.is_dir():
                    shutil.rmtree(p)
                elif p.suffix.lower() != ".exe":
                    p.unlink()
            return
        except OSError:
            if attempt == tries - 1:
                raise
            time.sleep(0.3)


def _error_box_open(pid: int) -> bool:
    """Windows only: does this process show a window titled 'Fortran'?

    When a calculation inside PRZM fails (for example a NaN reaches EXP or LOG), the program does
    not end. It shows a message box with the title 'Fortran' and waits for a click on OK. Without
    this check a failing run would block until somebody clicks, once for every failing field.
    """
    if os.name != "nt":
        return False
    try:
        import ctypes
        from ctypes import wintypes
        user32 = ctypes.windll.user32
        user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
        user32.IsWindowVisible.argtypes = [wintypes.HWND]
        user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
        found = []

        def each(hwnd, _lparam):
            owner = wintypes.DWORD(0)
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(owner))
            if owner.value == pid and user32.IsWindowVisible(hwnd):
                title = ctypes.create_unicode_buffer(128)
                user32.GetWindowTextW(hwnd, title, 128)
                if title.value.strip() == ERROR_BOX_TITLE:
                    found.append(hwnd)
            return True

        callback = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)(each)
        user32.EnumWindows(callback, 0)
        return bool(found)
    except Exception:                 # the check is a convenience; the time limit still applies
        return False


def run_winprzm(work: Path, exe: Path, timeout: float, poll: float = 0.25) -> None:
    """Start WINPRZM.exe in `work` and wait for it.

    Stops the program and raises PrzmError as soon as it shows a calculation-error box, and raises
    subprocess.TimeoutExpired when it runs longer than `timeout` seconds.
    """
    proc = subprocess.Popen([str(exe)], cwd=work, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL)
    t0 = time.time()
    try:
        while proc.poll() is None:
            if time.time() - t0 > timeout:
                raise subprocess.TimeoutExpired(str(exe), timeout)
            if _error_box_open(proc.pid):
                raise PrzmError("PRZM stopped with a calculation error (error box 'Fortran')")
            time.sleep(poll)
    finally:
        if proc.poll() is None:
            proc.kill()
        proc.wait()


def is_done(dest: Path) -> bool:
    f = _by_suffix(dest) if dest.is_dir() else {}
    return ".zts" in f and ".out" in f and f[".zts"].stat().st_size > 400


def rerun_one(src: Path, dest: Path, work: Path, exe: Path, *, henry: str | None = HENRY_FIXED,
              moisture_ref: str | None = MOISTURE_REF_FIXED, timeout: float = 120,
              runner: Callable[[Path, Path, float], None] = run_winprzm, work_name: str | None = None) -> dict:
    """Re-run one folder. Returns a small record for the log."""
    t0 = time.time()
    rec = {"run": src.name, "batch": src.parent.name, "status": "ok", "seconds": 0.0, "zts_bytes": 0, "note": ""}
    try:
        files = _by_suffix(src)
        inp, met = files[".inp"], files[".met"]
        _empty(work)
        (work / "output").mkdir(parents=True, exist_ok=True)
        (work / inp.name).write_bytes(patch_inp(inp.read_bytes(), henry, moisture_ref))
        shutil.copyfile(met, work / met.name)
        (work / RUN_FILE).write_bytes(patch_run((src / RUN_FILE).read_bytes(), work_name or str(work)))
        runner(work, exe, timeout)
        produced = _by_suffix(work / "output")
        if ".zts" not in produced or ".out" not in produced:
            raise RerunError("PRZM wrote no result files")
        dest.mkdir(parents=True, exist_ok=True)
        for p in (work / inp.name, work / met.name, work / RUN_FILE, produced[".zts"], produced[".out"]):
            shutil.copyfile(p, dest / p.name)
        rec["zts_bytes"] = produced[".zts"].stat().st_size
        if rec["zts_bytes"] <= 400:
            rec["status"] = "empty"
    except subprocess.TimeoutExpired:
        rec.update(status="timeout", note=f"stopped after {timeout:.0f} s")
    except PrzmError as e:
        rec.update(status="przm_error", note=str(e)[:200])
    except Exception as e:                      # one bad folder must not stop the other runs
        rec.update(status="failed", note=f"{type(e).__name__}: {e}"[:200])
    rec["seconds"] = round(time.time() - t0, 1)
    return rec


# --------------------------------------------------------------------------- #
# 3. Running everything
# --------------------------------------------------------------------------- #
def _last_status(log_path: Path, wanted: set[str]) -> set[str]:
    """Names of the runs whose most recent line in the log has one of the wanted outcomes."""
    if not log_path.exists():
        return set()
    last = {}
    with open(log_path, newline="") as fh:
        for row in csv.DictReader(fh):
            last[row.get("run")] = row.get("status")
    return {run for run, status in last.items() if status in wanted}


def rerun_all(runs_root: str | Path, out_root: str | Path, exe: str | Path, work_root: str | Path = r"C:\Temp\rr", *,
              henry: str | None = HENRY_FIXED, moisture_ref: str | None = MOISTURE_REF_FIXED, workers: int = 4,
              limit: int | None = None, timeout: float = 120, retry_failed: bool = False,
              runner: Callable[[Path, Path, float], None] = run_winprzm) -> list[dict]:
    """Re-run every folder with input files. Folders that are already done are skipped,
    so the command can be stopped and started again. Folders for which PRZM itself reported a
    calculation error are also skipped the next time, unless `retry_failed` is set.

    The log is written to <out_root>/rerun_log.csv.
    """
    exe, out_root, work_root = Path(exe), Path(out_root), Path(work_root)
    for value, width in ((henry, 8), (moisture_ref, 8)):
        if value is not None:
            _number(value)
            _fixed(b" " * width, 0, width, value)
    if runner is run_winprzm:
        if os.name != "nt":
            raise RuntimeError("WINPRZM.exe only runs on Windows. Run this command on your Windows computer.")
        if not exe.is_file():
            raise FileNotFoundError(f"PRZM program not found: {exe}")
        work_root = work_root.resolve()
        patch_run(b"  PATH   a\r\n  PATH   b\r\n", str(work_root / f"w{max(1, workers) - 1}"))   # path short enough?
    todo = [(s, out_root / s.parent.name / s.name) for s in find_inputs(runs_root)][:limit]
    out_root.mkdir(parents=True, exist_ok=True)
    log_path = out_root / "rerun_log.csv"
    known_bad = set() if retry_failed else _last_status(log_path, SKIP_NEXT_TIME)
    not_done = [(s, d) for s, d in todo if not is_done(d)]
    pending = [(s, d) for s, d in not_done if s.name not in known_bad]
    log.info("%d folders with inputs, %d already done, %d failed in PRZM before (skipped), %d to run",
             len(todo), len(todo) - len(not_done), len(not_done) - len(pending), len(pending))
    settings = f"henry={henry}\nmoisture_ref={moisture_ref}\n"
    note = out_root / "rerun_settings.txt"
    if note.exists() and not note.read_text().startswith(settings):
        raise RerunError(f"{out_root} already holds results made with other settings "
                         f"({' '.join(note.read_text().split()[:2])}). Choose another output folder.")
    note.write_text(settings + f"source={Path(runs_root).resolve()}\n")

    free = [work_root / f"w{i}" for i in range(max(1, workers))]
    for w in free:
        w.mkdir(parents=True, exist_ok=True)
    if runner is run_winprzm:                 # PRZM is started from a copy inside its work folder
        for w in free:
            shutil.copyfile(exe, w / exe.name)
    lock = threading.Lock()

    def job(src: Path, dest: Path) -> dict:
        with lock:
            w = free.pop()
        try:
            own = w / exe.name if runner is run_winprzm else exe
            return rerun_one(src, dest, w, own, henry=henry, moisture_ref=moisture_ref, timeout=timeout, runner=runner)
        finally:
            with lock:
                free.append(w)

    records, t0 = [], time.time()
    new_file = not log_path.exists()
    with open(log_path, "a", newline="") as fh, ThreadPoolExecutor(max_workers=len(free)) as pool:
        wr = csv.DictWriter(fh, fieldnames=["run", "batch", "status", "seconds", "zts_bytes", "note"])
        if new_file:
            wr.writeheader()
        for n, fut in enumerate(as_completed([pool.submit(job, s, d) for s, d in pending]), 1):
            rec = fut.result()
            records.append(rec); wr.writerow(rec); fh.flush()
            if rec["status"] != "ok":
                log.warning("%s: %s %s", rec["run"], rec["status"], rec["note"])
            if n % 50 == 0 or n == len(pending):
                rate = (time.time() - t0) / n
                log.info("%d of %d done, about %.0f minutes left", n, len(pending), rate * (len(pending) - n) / 60)
    return records
