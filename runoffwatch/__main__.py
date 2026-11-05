"""Command line: python -m runoffwatch <command> ...

Commands (run in this order):
  extract    unpack the .7z archives          -> data/raw/runs/
  inventory  what differs between the runs?   -> data/interim/inventory_*.csv
  qc         quality-check every run          -> data/interim/runs_qc.csv (+ daily parquet)
  run        analyse a single run folder (tables + plots)
"""

import argparse
import logging
from pathlib import Path


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="runoffwatch", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("-v", "--verbose", action="store_true", help="show every per-run warning")
    sub = p.add_subparsers(dest="cmd", required=True)

    e = sub.add_parser("extract", help="unpack archives")
    e.add_argument("--archives", default="data/raw/archives")
    e.add_argument("--out", default="data/raw/runs")

    i = sub.add_parser("inventory", help="find what differs between runs")
    i.add_argument("--runs", default="data/raw/runs")
    i.add_argument("--out", default="data/interim")

    q = sub.add_parser("qc", help="quality-check every run")
    q.add_argument("--runs", default="data/raw/runs")
    q.add_argument("--out", default="data/interim")
    q.add_argument("--no-daily", action="store_true", help="skip writing daily parquet files")
    q.add_argument("--workers", type=int, default=4)
    q.add_argument("--limit", type=int, help="only the first N runs (for a quick test)")

    r = sub.add_parser("run", help="analyse one run folder")
    r.add_argument("folder")
    r.add_argument("--out", default="reports")

    a = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    from . import batch

    if a.cmd == "extract":
        for d in batch.extract_archives(a.archives, a.out):
            print(d)
    elif a.cmd == "inventory":
        per_run, varying = batch.inventory(batch.find_runs(a.runs))
        out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
        per_run.to_csv(out / "inventory_runs.csv", index=False)
        varying.to_csv(out / "inventory_varying_inp_lines.csv", index=False)
        print(f"\nruns: {len(per_run)}")
        print(f"distinct weather files: {per_run['met_hash'].nunique()}")
        print(f"distinct .inp files:    {per_run['inp_hash'].nunique()}")
        print(f".inp lines that vary:   {len(varying)}")
        if len(varying):
            print(varying.head(20).to_string(index=False))
    elif a.cmd == "qc":
        runs = batch.find_runs(a.runs)[: a.limit]
        out = Path(a.out)
        qc = batch.qc_all(runs, out / "runs_qc.csv", None if a.no_daily else out / "daily", a.workers,
                          quiet=not a.verbose)
        ok = qc[qc["read_ok"]]
        print(f"\nruns checked: {len(qc)} | read errors: {(~qc['read_ok']).sum()} | "
              f"unstable: {int(ok['unstable'].sum())} | with log errors: {int((ok['n_log_errors'] > 0).sum())}")
        print(f"summary written to {out / 'runs_qc.csv'}")
    elif a.cmd == "run":
        from .report import analyze_run
        analyze_run(a.folder, a.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
