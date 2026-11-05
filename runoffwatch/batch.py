"""
Batch tools for the full set of ~10,000 PRZM runs.

Three steps, each writes its result to disk so it only has to run once:

1. extract_archives  .7z archives -> one folder per run   (data/raw/runs/)
2. inventory         what differs between runs?           (data/interim/inventory_*.csv)
3. qc_all            quality check + daily tables per run (data/interim/runs_qc.csv,
                                                           data/interim/daily/<run>.parquet)

`inventory` answers the project's first open question: do the runs differ in
weather, in field settings, or in both? It hashes every weather file and
compares the .inp files line by line.
"""

from __future__ import annotations

import hashlib
import logging
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import pandas as pd

from .przm_io import read_run
from .przm_spikes import daily_features, flag_spikes

log = logging.getLogger("runoffwatch")


# --------------------------------------------------------------------------- #
# 1. Archives
# --------------------------------------------------------------------------- #
def extract_archives(archive_dir: str | Path, out_dir: str | Path) -> list[Path]:
    """Unpack every .7z/.zip in archive_dir into out_dir/<archive name>/.

    An archive is skipped only if its last unpack finished (a `.unpacked`
    marker file exists), so an interrupted unpack is redone on the next call.
    """
    import zipfile

    archive_dir, out_dir = Path(archive_dir), Path(out_dir)
    archives = sorted(p for p in archive_dir.iterdir() if p.suffix.lower() in {".7z", ".zip"})
    if not archives:
        raise FileNotFoundError(f"No .7z or .zip archives in {archive_dir}")
    done = []
    for arc in archives:
        target = out_dir / arc.stem
        marker = target / ".unpacked"
        if marker.exists():
            log.info("skip %s (already unpacked)", arc.name)
            done.append(target)
            continue
        target.mkdir(parents=True, exist_ok=True)
        log.info("unpacking %s -> %s", arc.name, target)
        if arc.suffix.lower() == ".7z":
            import py7zr  # optional dependency, only needed for .7z
            with py7zr.SevenZipFile(arc, "r") as z:
                _check_member_names(z.getnames(), arc)
                z.extractall(target)
        else:
            with zipfile.ZipFile(arc) as z:
                _check_member_names(z.namelist(), arc)
                z.extractall(target)
        marker.write_text(arc.name)
        done.append(target)
    return done


def _check_member_names(names: list[str], arc: Path) -> None:
    """Refuse archives with absolute paths or '..' (they could write outside the target)."""
    for n in names:
        p = Path(n)
        if p.is_absolute() or ".." in p.parts:
            raise ValueError(f"{arc.name}: unsafe path inside archive: {n!r}")


def find_runs(root: str | Path) -> list[Path]:
    """All run folders below root (a run folder is one that holds a .ZTS file)."""
    root = Path(root)
    runs = sorted({p.parent for p in root.rglob("*") if p.is_file() and p.suffix.lower() == ".zts"})
    if not runs:
        raise FileNotFoundError(f"No run folders (with a .ZTS file) under {root}")
    return runs


# --------------------------------------------------------------------------- #
# 2. Inventory: what differs between runs?
# --------------------------------------------------------------------------- #
def _sha1(path: Path) -> str:
    return hashlib.sha1(path.read_bytes()).hexdigest()[:12]


def _first(folder: Path, suffix: str) -> Path | None:
    hits = [p for p in folder.iterdir() if p.is_file() and p.suffix.lower() == suffix]
    return hits[0] if len(hits) == 1 else None


def inventory(runs: list[Path]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (per-run table, varying .inp lines).

    per-run table: run, batch, met_hash, inp_hash, n_inp_lines
    varying lines: line_no, n_distinct, example values, count of the most common value

    How to read it:
      * met_hash has 1 distinct value  -> all runs share the same weather
      * varying lines is empty         -> all runs share the same field settings
    """
    rows, lines_by_no = [], defaultdict(Counter)
    for run in runs:
        met, inp = _first(run, ".met"), _first(run, ".inp")
        row = {"run": run.name, "batch": run.parent.name,
               "met_hash": _sha1(met) if met else None,
               "inp_hash": None, "n_inp_lines": None}
        if inp:
            text = inp.read_text(errors="replace").splitlines()
            row["inp_hash"] = hashlib.sha1("\n".join(text).encode()).hexdigest()[:12]
            row["n_inp_lines"] = len(text)
            for i, line in enumerate(text, start=1):
                lines_by_no[i][line.rstrip()] += 1
        rows.append(row)
    per_run = pd.DataFrame(rows)

    varying = []
    for i, counts in sorted(lines_by_no.items()):
        if len(counts) > 1:
            common, n_common = counts.most_common(1)[0]
            varying.append({"line_no": i, "n_distinct": len(counts),
                            "most_common": common.strip(), "n_most_common": n_common,
                            "examples": " | ".join(v.strip() for v in list(counts)[:3])})
    varying = pd.DataFrame(varying, columns=["line_no", "n_distinct", "most_common", "n_most_common", "examples"])

    n = len(per_run)
    log.info("inventory: %d runs | %d distinct weather files | %d distinct .inp files | %d varying .inp lines",
             n, per_run["met_hash"].nunique(), per_run["inp_hash"].nunique(), len(varying))
    return per_run, varying


# --------------------------------------------------------------------------- #
# 3. Quality check of every run
# --------------------------------------------------------------------------- #
def qc_run(run: Path, daily_dir: Path | None = None) -> dict:
    """Read one run, return one summary row; optionally save its daily table."""
    row: dict = {"run": run.name, "batch": run.parent.name, "read_ok": False}
    try:
        df = flag_spikes(daily_features(read_run(run)))
    except Exception as e:  # one bad run must not stop 10,000
        row["error"] = f"{type(e).__name__}: {e}"[:300]
        return row

    decay = df.attrs.get("soil_decay", [])
    growth = [b / a for a, b in zip(decay[:-1], decay[1:]) if a > 0]
    row.update({
        "read_ok": True,
        "n_days": len(df),
        "start": df.index.min().date(), "end": df.index.max().date(),
        "unstable": bool(df.attrs.get("unstable", False)),
        "max_decay_growth": max(growth) if growth else None,
        "last_year_decay": decay[-1] if decay else None,
        "mass_balance_ok": df.attrs.get("mass_balance_ok"),
        "weather_mismatch_mm": df.attrs.get("weather_mismatch_mm"),
        "n_log_errors": len(df.attrs.get("log_errors", [])),
        "rain_total_mm": round(df["rain_mm"].sum(), 1),
        "runoff_days": int((df.get("runoff_mm", 0) > 0).sum()),
        "applied_total_gha": round(df["applied_gha"].sum(), 2) if "applied_gha" in df else None,
        "loss_total_gha": round(df["pest_runoff_gha"].sum(), 3) if "pest_runoff_gha" in df else None,
        "high_loss_days": int(df["is_spike"].sum()) if "is_spike" in df else None,
    })
    if daily_dir is not None:
        daily_dir.mkdir(parents=True, exist_ok=True)
        df.attrs = {}  # parquet cannot store arbitrary attrs
        df.to_parquet(daily_dir / f"{run.name}.parquet")
    return row


def _silence_worker() -> None:
    """Per-run warnings would flood the screen; their results go to the CSV instead.
    Done in an initializer because Windows workers do not inherit log settings."""
    logging.getLogger("runoffwatch").setLevel(logging.CRITICAL)


def qc_all(runs: list[Path], out_csv: str | Path, daily_dir: str | Path | None = None,
           workers: int = 4, quiet: bool = True) -> pd.DataFrame:
    """Quality-check all runs in parallel and write one summary CSV."""
    daily_dir = Path(daily_dir) if daily_dir else None
    rows = []
    with ProcessPoolExecutor(max_workers=workers, initializer=_silence_worker if quiet else None) as pool:
        futures = {pool.submit(qc_run, r, daily_dir): r for r in runs}
        for i, fut in enumerate(as_completed(futures), start=1):
            rows.append(fut.result())
            if i % 500 == 0 or i == len(runs):
                log.info("qc: %d / %d runs", i, len(runs))
    out = pd.DataFrame(rows).sort_values("run").reset_index(drop=True)
    Path(out_csv).parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(out_csv, index=False)

    ok = out[out["read_ok"]]
    log.info("qc: %d runs read, %d failed to read, %d unstable (%.1f%%), %d with log errors",
             len(ok), (~out["read_ok"]).sum(), ok["unstable"].sum(),
             100 * ok["unstable"].mean() if len(ok) else 0, (ok["n_log_errors"] > 0).sum())
    return out
