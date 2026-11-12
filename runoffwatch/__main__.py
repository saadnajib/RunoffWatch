"""Command line: python -m runoffwatch <command> ...

Commands (run in this order):
  extract    unpack the .7z archives          -> data/raw/runs/
  inventory  what differs between the runs?   -> data/interim/inventory_*.csv
  qc         quality-check every run          -> data/interim/runs_qc.csv (+ daily parquet)
  audit      Task 1: which results are trusted -> data/interim/run_quality.csv, docs/figures
  features   one row per rain day             -> data/processed/features.parquet
  train      Tasks 2+3: surrogate + classifier -> models/, docs/results, docs/figures
  whatif     spray-day comparison from a weather file (uses the trained surrogate)
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

    au = sub.add_parser("audit", help="Task 1: which results can be trusted? (needs inventory + qc)")
    au.add_argument("--runs", default="data/raw/runs")
    au.add_argument("--interim", default="data/interim")

    fe = sub.add_parser("features", help="build the feature table (needs audit)")
    fe.add_argument("--interim", default="data/interim")
    fe.add_argument("--out", default="data/processed/features.parquet")

    tr = sub.add_parser("train", help="Tasks 2+3: train and evaluate surrogate and classifier")
    tr.add_argument("--features", default="data/processed/features.parquet")
    tr.add_argument("--models", default="models")
    tr.add_argument("--rounds", type=int, default=1500)
    tr.add_argument("--cv", action="store_true",
                    help="instead of training the final models: leave-one-year-out evaluation (slow)")

    wi = sub.add_parser("whatif", help="compare spray days for a weather table")
    wi.add_argument("--weather", help="CSV with date, rain_mm, temp_c[, pan_evap_mm]; omit for a made-up example")
    wi.add_argument("--first-day", help="first candidate spray day (YYYY-MM-DD); default: day 31 of the table")
    wi.add_argument("--candidates", type=int, default=7, help="number of consecutive candidate days")
    wi.add_argument("--horizon", type=int, default=14, help="days after spraying to add up")
    wi.add_argument("--models", default="models")

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
    elif a.cmd == "audit":
        from .quality import audit
        s = audit(a.runs, a.interim)
        print(f"\nfolders: {s['folders']} {s['status_counts']}")
        print(f"readable runs: {s['readable_runs']} | with broken pesticide years: {s['envelope_rule_bad_runs']}")
        print(f"trusted pesticide data: {s['clean_run_years']:.0f} of {s['total_run_years']:.0f} run-years")
        print("details: data/interim/run_quality.csv, docs/results/quality_summary.json, docs/figures/q*.png")
    elif a.cmd == "features":
        from .features import build_feature_table
        t = build_feature_table(a.interim, a.out)
        print(f"\n{len(t):,} rain-day rows written to {a.out}")
    elif a.cmd == "train":
        import json
        from .models import train_all, yearly_cv
        if a.cv:
            print(json.dumps(yearly_cv(a.features, rounds=a.rounds), indent=2))
            print("per year: docs/results/cv_by_year.csv | figure: docs/figures/m7_scores_by_held_out_year.png")
            return 0
        m = train_all(a.features, a.models, rounds=a.rounds)
        print(json.dumps({k: m[k] for k in ("split", "runoff", "loss", "high_loss")}, indent=2))
        print("models in", a.models, "| metrics in docs/results/model_metrics.json | figures in docs/figures/m*.png")
    elif a.cmd == "whatif":
        import pandas as pd
        from .whatif import compare_spray_days, example_weather, prepare_weather
        w = prepare_weather(pd.read_csv(a.weather) if a.weather else example_weather())
        first = pd.Timestamp(a.first_day) if a.first_day else w.index[min(30, len(w) - 2)]
        cands = [d for d in pd.date_range(first, periods=a.candidates) if d in w.index]
        table = compare_spray_days(w, cands, a.horizon, model_dir=a.models)
        print(table.to_string(index=False))
        ranked = table[table["rank"].notna()].sort_values("predicted_loss_gha")
        if len(ranked):
            best = ranked.iloc[0]
            print(f"\nLowest predicted loss: spray on {best.spray_date} ({best.predicted_loss_gha} g/ha in {a.horizon} days).")
        for note in table.attrs["notes"]:
            print("NOTE:", note)
        print("Valid only for Flufenacet, 2400 g/ha, winter cereals, sprayed around 1 March (see docs/MODEL_REPORT.md).")
    elif a.cmd == "run":
        from .report import analyze_run
        analyze_run(a.folder, a.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
