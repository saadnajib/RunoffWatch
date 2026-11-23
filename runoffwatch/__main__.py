"""Command line: python -m runoffwatch <command> ...

Commands (run in this order):
  extract    unpack the .7z archives          -> data/raw/runs/
  inventory  what differs between the runs?   -> data/interim/inventory_*.csv
  qc         quality-check every run          -> data/interim/runs_qc.csv (+ daily parquet)
  audit      Task 1: which results are trusted -> data/interim/run_quality.csv, docs/figures
  features   one row per rain day             -> data/processed/features.parquet
  train      Tasks 2+3: surrogate + classifier -> models/, docs/results, docs/figures
  lstm       second surrogate (LSTM) compared with the trees (needs PyTorch)
  france     surrogate on 46 years of Agri4Cast weather for France -> docs/results/france_*.csv
  whatif     spray-day comparison from a weather file (uses the trained surrogate)
  design     run files for new simulations (spray date, dose, substance); nothing is uploaded
  rerun      run PRZM again on your Windows PC with the two corrected settings -> data/raw/runs_fixed/
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

    ls = sub.add_parser("lstm", help="train an LSTM surrogate and compare it with the tree surrogate (needs PyTorch)")
    ls.add_argument("--interim", default="data/interim")
    ls.add_argument("--features", default="data/processed/features.parquet")
    ls.add_argument("--epochs", type=int, default=20)
    ls.add_argument("--limit", type=int, help="only the first N runs (quick test)")

    de = sub.add_parser("design", help="write run files for NEW simulations (nothing is uploaded)")
    de.add_argument("--n", type=int, default=2000, help="number of new runs with varied spray date, dose and substance")
    de.add_argument("--controls", type=int, default=200, help="existing runs repeated with only the Henry constant changed")
    de.add_argument("--henry", type=float, default=None, help="Henry constant for all new runs (default: see design.py)")
    de.add_argument("--seed", type=int, default=1)
    de.add_argument("--name", default="rw_exp1", help="prefix of the task archives; must be new for every submission")
    de.add_argument("--out", default="data/design/exp1")
    de.add_argument("--interim", default="data/interim")
    de.add_argument("--runs", default="data/raw/runs")
    de.add_argument("--weather-dir", help="folder with the original MARS weather CSVs (<met_hash>.csv), if you have them")
    de.add_argument("--overwrite", action="store_true")

    fr = sub.add_parser("france", help="run the surrogate on the 1979-2024 Agri4Cast weather for France")
    fr.add_argument("--weather", default="data/raw/france_weather/france_weather.parquet",
                    help="the Agri4Cast table (france_weather_1979_2024.csv, or a parquet copy)")
    fr.add_argument("--limit", type=int, help="only the first N fields (quick test)")

    wi = sub.add_parser("whatif", help="compare spray days for a weather table")
    wi.add_argument("--weather", help="CSV with date, rain_mm, temp_c[, pan_evap_mm]; omit for a made-up example")
    wi.add_argument("--first-day", help="first candidate spray day (YYYY-MM-DD); default: day 31 of the table")
    wi.add_argument("--candidates", type=int, default=7, help="number of consecutive candidate days")
    wi.add_argument("--horizon", type=int, default=14, help="days after spraying to add up")
    wi.add_argument("--models", default="models")

    rr = sub.add_parser("rerun", help="run PRZM again on Windows with corrected Henry constant and moisture setting")
    rr.add_argument("--exe", required=True, help=r"path to WINPRZM.exe, e.g. C:\Temp\X3MZI0OQ2D67EUQHFZ\WINPRZM.exe")
    rr.add_argument("--runs", default="data/raw/runs", help="folder with the original run folders")
    rr.add_argument("--out", default="data/raw/runs_fixed", help="where the new results go (same layout as --runs)")
    rr.add_argument("--work", default=r"C:\Temp\rr", help="short scratch folder; PRZM cannot handle long paths")
    rr.add_argument("--henry", default=None, help="Henry constant, at most 8 characters (default: 0.37E-06); 'keep' = unchanged")
    rr.add_argument("--moisture-ref", default=None, help="reference soil moisture (default: 1); 'keep' = unchanged")
    rr.add_argument("--workers", type=int, default=4, help="PRZM runs at the same time")
    rr.add_argument("--limit", type=int, help="only the first N folders (for a quick test)")

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
    elif a.cmd == "rerun":
        from . import rerun
        pick = lambda v, default: default if v is None else (None if v == "keep" else v)
        recs = rerun.rerun_all(a.runs, a.out, a.exe, a.work, henry=pick(a.henry, rerun.HENRY_FIXED),
                               moisture_ref=pick(a.moisture_ref, rerun.MOISTURE_REF_FIXED), workers=a.workers, limit=a.limit)
        counts = {}
        for rec in recs:
            counts[rec["status"]] = counts.get(rec["status"], 0) + 1
        print(f"\nruns started now: {len(recs)} {counts}")
        print(f"results in {a.out} | log: {Path(a.out) / 'rerun_log.csv'}")
        print(f"next: python -m runoffwatch qc --runs {a.out} --out data/interim_fixed")
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
    elif a.cmd == "lstm":
        import json
        from .lstm import train_and_compare
        m = train_and_compare(a.interim, a.features, epochs=a.epochs, limit=a.limit)
        print(json.dumps({k: m[k] for k in ("rows_compared", "epochs_run", "train_minutes", "lstm", "trees")}, indent=2))
        print("details: docs/results/lstm_vs_trees.json | figure: docs/figures/m8_lstm_vs_trees.png")
    elif a.cmd == "design":
        import pandas as pd
        from . import design as dz
        rq = pd.read_csv(Path(a.interim) / "run_quality.csv", index_col="run", dtype={"met_hash": str})
        kw = {} if a.henry is None else {"henry": a.henry}
        d = dz.make_design(rq, a.n, a.seed, n_controls=a.controls, weather_dir=a.weather_dir, **kw)
        info = dz.write_design(d, a.out, a.runs, a.weather_dir, name=a.name, overwrite=a.overwrite)
        print(dz.readme_text(d, n_archives=len(info["archives"])))
        print(f"written to {a.out}: {len(d)} run files, {len(info['archives'])} task archive(s). Nothing was uploaded.")
    elif a.cmd == "france":
        import json
        from .longrun import run_france
        m = run_france(a.weather, limit=a.limit)
        print(json.dumps(m, indent=2))
        print("per year: docs/results/france_by_year.csv | per grid cell: docs/results/france_by_grid.csv | "
              "figures: docs/figures/f1_france_by_year.png, f2_france_map.png")
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
