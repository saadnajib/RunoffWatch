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

Varying the spray date and the dose
-----------------------------------
In the delivered data every field is sprayed on 1 March with 2.4 kg/ha, so a model cannot learn
what another spray day or another dose would do. With `variants > 0`, `rerun_all` makes several
extra copies of each field. Each copy gets its own dose and, for every simulated year, its own
spray date drawn from one time window (for example 15 Feb to 30 Apr). The draw depends only on
the seed, the field name and the copy number, so the same command always makes the same runs.

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
import datetime as dt
import logging
import os
import re
import shutil
import subprocess
import threading
import time
import zlib
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

log = logging.getLogger(__name__)

HENRY_FIXED = "0.37E-06"      # dimensionless; published values for Flufenacet give 2.4e-7 to 5.3e-7
MOISTURE_REF_FIXED = "1"      # 1 = field capacity in this program
MAX_PATH_CHARS = 60           # PRZM reads the paths in fixed-width fields
RUN_FILE = "Run 1.run"
_PATH_LINE = re.compile(rb"^(  PATH {2,})(\S+)(\r?)$", re.M)


DEFAULT_WINDOWS = ("15.02-30.04", "01.10-30.11")   # spray windows, day.month-day.month
DEFAULT_DOSES = ("0.24", "1.20", "2.40")            # kg/ha
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
        value = float(text)
    except (TypeError, ValueError):
        raise RerunError(f"not a number: {text!r}") from None
    if value != value or value in (float("inf"), float("-inf")):
        raise RerunError(f"not a usable number: {text!r}")


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


def _application_lines(lines: list[bytes]) -> tuple[int, int]:
    """(index of the first application line, number of applications) in an .inp file."""
    for i, l in enumerate(lines):
        if l.startswith(b"Chemical Input Data"):
            try:
                n = int(lines[i + 1].split()[0])
            except (IndexError, ValueError):
                raise RerunError("cannot read the number of applications") from None
            first = i + 3
            for a in lines[first:first + n]:
                if len(a) < 24 or not a[2:8].isdigit():
                    raise RerunError(f"unexpected application line: {a!r}")
                _number(a[18:24].decode())
            if len(lines[first:first + n]) != n:
                raise RerunError("the .inp file ends inside the application block")
            return first, n
    raise RerunError("no 'Chemical Input Data' line in the .inp file")


def read_applications(raw: bytes) -> list[dict]:
    """Day, month, two-digit year and dose (kg/ha) of every application in an .inp file."""
    lines = raw.split(b"\r\n") if b"\r\n" in raw else raw.split(b"\n")
    first, n = _application_lines(lines)
    return [{"day": int(a[2:4]), "month": int(a[4:6]), "year": int(a[6:8]), "rate_kgha": float(a[18:24])}
            for a in lines[first:first + n]]


def patch_applications(raw: bytes, dates: list[tuple[int, int]] | None = None, rate: str | None = None) -> bytes:
    """Return the .inp content with new spray dates and/or a new dose.

    dates: one (day, month) per application, in the order of the file (one per simulated year);
           a list with a single entry is used for every year. The year of each line is kept.
    rate:  dose in kg/ha as text, at most 6 characters (for example "1.20").
    `None` leaves a value as it is. Nothing else in the file changes.
    """
    nl = b"\r\n" if b"\r\n" in raw else b"\n"
    lines = raw.split(nl)
    first, n = _application_lines(lines)
    if dates is not None:
        if len(dates) == 1:
            dates = list(dates) * n
        if len(dates) != n:
            raise RerunError(f"{len(dates)} spray dates given for {n} applications")
        for k, (day, month) in enumerate(dates):
            year = 1900 + int(lines[first + k][6:8])
            try:
                dt.date(year, int(month), int(day))
            except (TypeError, ValueError):
                raise RerunError(f"not a date: day {day}, month {month}, year {year}") from None
            lines[first + k] = lines[first + k][:2] + f"{int(day):02d}{int(month):02d}".encode() + lines[first + k][6:]
    if rate is not None:
        _number(rate)
        if float(rate) <= 0:
            raise RerunError(f"dose must be above zero, not {rate!r}")
        for k in range(n):
            lines[first + k] = _fixed(lines[first + k], 18, 24, rate)
    return nl.join(lines)


def parse_window(text: str) -> tuple[int, int]:
    """'15.02-30.04' -> (first, last) as day numbers of a year without 29 February."""
    try:
        a, b = text.strip().split("-")
        (d1, m1), (d2, m2) = (tuple(int(x) for x in part.split(".")) for part in (a, b))
        first, last = (dt.date(2001, m, d).timetuple().tm_yday for d, m in ((d1, m1), (d2, m2)))
    except (ValueError, TypeError):
        raise RerunError(f"spray window must look like 15.02-30.04 (day.month-day.month), not {text!r}") from None
    if last < first:
        raise RerunError(f"spray window {text!r} ends before it starts (windows across New Year are not supported)")
    return first, last


@dataclass(frozen=True)
class Variant:
    """One extra copy of a field: its name ending, spray window, dose and one spray date per year."""
    suffix: str
    window: str
    rate: str
    dates: tuple[tuple[int, int], ...]


def make_variants(run_name: str, n_years: int, variants: int, windows=DEFAULT_WINDOWS, doses=DEFAULT_DOSES,
                  seed: int = 1) -> list[Variant]:
    """The spray plan of one field. Depends only on the arguments, never on what was run before.

    Each copy gets one window and one dose (both walk through the lists, starting at a point that
    differs from field to field) and, inside its window, a different random spray day every year.
    """
    import random

    if not windows or not doses:
        raise RerunError("at least one spray window and one dose are needed")
    spans = [parse_window(w) for w in windows]
    for d in doses:
        _number(d)
        _fixed(b" " * 6, 0, 6, d)
        if float(d) <= 0:
            raise RerunError(f"dose must be above zero, not {d!r}")
    out = []
    start = zlib.crc32(f"{seed}|{run_name}".encode())
    for k in range(1, variants + 1):
        rng = random.Random(zlib.crc32(f"{seed}|{run_name}|{k}".encode()))
        w = (start + k) % len(spans)
        dose = doses[(start // len(spans) + k) % len(doses)]
        days = [rng.randint(*spans[w]) for _ in range(n_years)]
        dates = tuple(((dt.date(2001, 1, 1) + dt.timedelta(days=d - 1)).day,
                       (dt.date(2001, 1, 1) + dt.timedelta(days=d - 1)).month) for d in days)
        out.append(Variant(f"__v{k}", windows[w], dose, dates))
    return out


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
    """Does dest hold a result? A .ZTS file of more than 400 bytes and an .OUT file.

    A run stopped while the result was being copied can leave a .ZTS file of full size that holds
    only zero bytes; such a file does not count.
    """
    f = _by_suffix(dest) if dest.is_dir() else {}
    if not (".zts" in f and ".out" in f and f[".zts"].stat().st_size > 400):
        return False
    with open(f[".zts"], "rb") as fh:
        head = fh.read(4096)
    return head.strip(b"\x00") != b""


def full_results(root: str | Path) -> set[str]:
    """Names of the result folders under root that hold a full-length result.

    A run that stops after a few days still leaves a small result file. All full runs of one data
    set have result files of practically the same size, so "full" means at least 90 % of the
    typical (median) size.
    """
    sizes = {}
    for p in Path(root).glob("*/*"):
        if p.is_dir() and is_done(p):
            sizes[p.name] = _by_suffix(p)[".zts"].stat().st_size
    if not sizes:
        return set()
    ordered = sorted(sizes.values())
    typical = ordered[len(ordered) // 2]
    return {name for name, size in sizes.items() if size >= 0.9 * typical}


def rerun_one(src: Path, dest: Path, work: Path, exe: Path, *, henry: str | None = HENRY_FIXED,
              moisture_ref: str | None = MOISTURE_REF_FIXED, timeout: float = 120,
              runner: Callable[[Path, Path, float], None] = run_winprzm, work_name: str | None = None,
              variant: Variant | None = None, copy_weather: bool = True) -> dict:
    """Re-run one folder. Returns a small record for the log.

    variant: also change the spray dates and the dose (see make_variants).
    copy_weather: store the weather file next to the results (it is identical to the one in `src`).
    """
    t0 = time.time()
    rec = {"run": dest.name, "batch": src.parent.name, "status": "ok", "seconds": 0.0, "zts_bytes": 0, "note": ""}
    try:
        files = _by_suffix(src)
        inp, met = files[".inp"], files[".met"]
        _empty(work)
        (work / "output").mkdir(parents=True, exist_ok=True)
        content = patch_inp(inp.read_bytes(), henry, moisture_ref)
        if variant is not None:
            content = patch_applications(content, list(variant.dates), variant.rate)
        (work / inp.name).write_bytes(content)
        shutil.copyfile(met, work / met.name)
        (work / RUN_FILE).write_bytes(patch_run((src / RUN_FILE).read_bytes(), work_name or str(work)))
        runner(work, exe, timeout)
        produced = _by_suffix(work / "output")
        if ".zts" not in produced or ".out" not in produced:
            raise RerunError("PRZM wrote no result files")
        dest.mkdir(parents=True, exist_ok=True)
        keep = [work / inp.name, work / RUN_FILE, produced[".zts"], produced[".out"]]
        for p in keep + ([work / met.name] if copy_weather else []):
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
              variants: int = 0, windows=DEFAULT_WINDOWS, doses=DEFAULT_DOSES, seed: int = 1,
              fields_from: str | Path | None = None, copy_weather: bool | None = None,
              runner: Callable[[Path, Path, float], None] = run_winprzm) -> list[dict]:
    """Re-run every folder with input files. Folders that are already done are skipped,
    so the command can be stopped and started again. Folders for which PRZM itself reported a
    calculation error are also skipped the next time, unless `retry_failed` is set.

    variants: 0 = one run per field, spray date and dose as delivered. Above 0 = that many extra
        copies per field with varied spray dates and dose (see make_variants); the folders are
        named <field>__v1, <field>__v2, ... and the plan is written to <out_root>/rerun_plan.csv.
    fields_from: a folder of finished results (for example data/raw/runs_fixed); only fields that
        have a full result there are used. Saves the time for fields PRZM cannot calculate.
    copy_weather: store a copy of the weather file with every result. Default: yes for plain
        re-runs, no for varied ones (it is the same file as in `runs_root` and takes a lot of room).

    The log is written to <out_root>/rerun_log.csv.
    """
    exe, out_root, work_root = Path(exe), Path(out_root), Path(work_root)
    if variants < 0:
        raise RerunError("variants must be 0 or more")
    windows, doses = tuple(windows), tuple(doses)
    if variants:
        make_variants("check", 1, 1, windows, doses, seed)          # fails early on a bad window or dose
    if copy_weather is None:
        copy_weather = variants == 0
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
    sources = find_inputs(runs_root)
    if fields_from is not None:
        good = full_results(fields_from)
        if not good:
            raise FileNotFoundError(f"no finished results under {fields_from}")
        sources = [s for s in sources if s.name in good]
    sources = sources[:limit]
    plan: dict[Path, Variant | None] = {}
    todo = []
    for s in sources:
        if not variants:
            todo.append((s, out_root / s.parent.name / s.name)); plan[todo[-1][1]] = None
            continue
        try:
            n_years = len(read_applications(_by_suffix(s)[".inp"].read_bytes()))
        except (RerunError, KeyError, OSError):
            n_years = 0                       # rerun_one reports the damaged input file
        for v in make_variants(s.name, max(n_years, 1), variants, windows, doses, seed):
            todo.append((s, out_root / s.parent.name / (s.name + v.suffix))); plan[todo[-1][1]] = v
    out_root.mkdir(parents=True, exist_ok=True)
    log_path = out_root / "rerun_log.csv"
    known_bad = set() if retry_failed else _last_status(log_path, SKIP_NEXT_TIME)
    not_done = [(s, d) for s, d in todo if not is_done(d)]
    pending = [(s, d) for s, d in not_done if d.name not in known_bad]
    log.info("%d folders with inputs, %d already done, %d failed in PRZM before (skipped), %d to run",
             len(todo), len(todo) - len(not_done), len(not_done) - len(pending), len(pending))
    settings = f"henry={henry}\nmoisture_ref={moisture_ref}\n"
    if variants:
        settings += f"variants={variants}\nwindows={','.join(windows)}\ndoses={','.join(doses)}\nseed={seed}\n"
    note = out_root / "rerun_settings.txt"
    if note.exists():
        before = "".join(l for l in note.read_text().splitlines(keepends=True) if not l.startswith("source="))
        if before != settings:
            raise RerunError(f"{out_root} already holds results made with other settings "
                             f"({' '.join(before.split())}). Choose another output folder.")
    note.write_text(settings + f"source={Path(runs_root).resolve()}\n")
    if variants:
        with open(out_root / "rerun_plan.csv", "w", newline="") as fh:
            wr = csv.writer(fh)
            wr.writerow(["run", "field", "batch", "window", "dose_kgha", "spray_dates_day.month"])
            for (src_dir, dest_dir) in todo:
                v = plan[dest_dir]
                wr.writerow([dest_dir.name, src_dir.name, src_dir.parent.name, v.window, v.rate,
                             " ".join(f"{a:02d}.{b:02d}" for a, b in v.dates)])

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
            return rerun_one(src, dest, w, own, henry=henry, moisture_ref=moisture_ref, timeout=timeout, runner=runner,
                             variant=plan[dest], copy_weather=copy_weather)
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
