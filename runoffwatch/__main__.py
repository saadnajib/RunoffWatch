"""Command line: python -m runoffwatch [--dataset corrected|delivered] <command> ...

Two data sets (see runoffwatch/paths.py):
  corrected  (default) the re-runs with the two corrected settings, in data/raw/runs_fixed/;
             results in data/interim_fixed/, data/processed/*_fixed.parquet, models/, docs/results/,
             docs/figures/; audit trusts a run when PRZM's own balance error is small
  delivered  the simulations as delivered, in data/raw/runs/ (two wrong settings);
             results in data/interim/, data/processed/, models/delivered/, docs/results/delivered/,
             docs/figures/delivered/; audit uses the envelope rule
A path given on the command line always wins over the data set's default.

Commands (run in this order):
  extract    unpack the .7z archives          -> data/raw/runs/ (always the delivered data)
  rerun      run PRZM again on your Windows PC with the two corrected settings -> data/raw/runs_fixed/
             with --variants N: N extra copies per field with varied spray dates and dose -> data/raw/runs_varied/
  inventory  what differs between the runs?   -> <interim>/inventory_*.csv
  qc         quality-check every run          -> <interim>/runs_qc.csv (+ daily parquet)
  audit      Task 1: which results are trusted -> <interim>/run_quality.csv, <results>, <figures>
  features   one row per rain day             -> <features> parquet
  train      Tasks 2+3: surrogate + classifier -> <models>, <results>, <figures>
  lstm       second surrogate (LSTM) compared with the trees (needs PyTorch)
  france     surrogate on 46 years of Agri4Cast weather for France -> <results>/france_*.csv
  whatif     spray-day comparison from a weather file (uses the trained surrogate in <models>)
  design     run files for new simulations (spray date, dose, substance); nothing is uploaded
  run        analyse a single run folder (tables + plots)
"""

import argparse
import logging
from pathlib import Path

from .paths import DATASETS, DEFAULT_DATASET

# per sub-command: argument name -> key in paths.DATASETS. Arguments left at None are filled from the
# chosen data set. The keys without a command-line option are only set on the namespace.
DATASET_ARGS = {
    "inventory": {"runs": "runs", "out": "interim"},
    "qc": {"runs": "runs", "out": "interim"},
    "audit": {"runs": "runs", "interim": "interim", "trust": "trust", "results": "results", "figures": "figures"},
    "features": {"interim": "features_from", "out": "features"},
    "train": {"features": "features", "models": "models", "results": "results", "figures": "figures"},
    "lstm": {"interim": "interim", "features": "features", "models": "models", "results": "results",
             "figures": "figures"},
    "design": {"interim": "interim", "runs": "runs"},
    "france": {"interim": "fields_interim", "features": "features", "models": "models", "out": "france_out",
               "results": "results", "figures": "figures"},
    "whatif": {"models": "models"},
}
DS = " (default: from --dataset)"


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="runoffwatch", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("-v", "--verbose", action="store_true", help="show every per-run warning")
    p.add_argument("--dataset", choices=sorted(DATASETS), default=DEFAULT_DATASET,
                   help="which simulations to work on (default: %(default)s); paths given explicitly still win")
    sub = p.add_subparsers(dest="cmd", required=True)

    e = sub.add_parser("extract", help="unpack archives")
    e.add_argument("--archives", default="data/raw/archives")
    e.add_argument("--out", default="data/raw/runs")

    i = sub.add_parser("inventory", help="find what differs between runs")
    i.add_argument("--runs", default=None, help="run folders" + DS)
    i.add_argument("--out", default=None, help="interim folder" + DS)

    q = sub.add_parser("qc", help="quality-check every run")
    q.add_argument("--runs", default=None, help="run folders" + DS)
    q.add_argument("--out", default=None, help="interim folder" + DS)
    q.add_argument("--no-daily", action="store_true", help="skip writing daily parquet files")
    q.add_argument("--workers", type=int, default=4)
    q.add_argument("--limit", type=int, help="only the first N runs (for a quick test)")

    au = sub.add_parser("audit", help="Task 1: which results can be trusted? (needs inventory + qc)")
    au.add_argument("--runs", default=None, help="run folders" + DS)
    au.add_argument("--interim", default=None, help="interim folder" + DS)
    au.add_argument("--trust", choices=["envelope", "balance"], default=None,
                    help="rule that decides which pesticide results are trusted" + DS)

    fe = sub.add_parser("features", help="build the feature table (needs audit)")
    fe.add_argument("--interim", default=None, nargs="+", help="one or more interim folders" + DS)
    fe.add_argument("--out", default=None, help="feature table" + DS)

    tr = sub.add_parser("train", help="Tasks 2+3: train and evaluate surrogate and classifier")
    tr.add_argument("--features", default=None, help="feature table" + DS)
    tr.add_argument("--models", default=None, help="model folder" + DS)
    tr.add_argument("--rounds", type=int, default=1500)
    tr.add_argument("--cv", action="store_true",
                    help="instead of training the final models: leave-one-year-out evaluation (slow)")

    ls = sub.add_parser("lstm", help="train an LSTM surrogate and compare it with the tree surrogate (needs PyTorch)")
    ls.add_argument("--interim", default=None, help="interim folder" + DS)
    ls.add_argument("--features", default=None, help="feature table" + DS)
    ls.add_argument("--epochs", type=int, default=20)
    ls.add_argument("--limit", type=int, help="only the first N runs (quick test)")

    de = sub.add_parser("design", help="write run files for NEW simulations (nothing is uploaded)")
    de.add_argument("--n", type=int, default=2000, help="number of new runs with varied spray date, dose and substance")
    de.add_argument("--controls", type=int, default=200, help="existing runs repeated with only the Henry constant changed")
    de.add_argument("--henry", type=float, default=None, help="Henry constant for all new runs (default: see design.py)")
    de.add_argument("--seed", type=int, default=1)
    de.add_argument("--name", default="rw_exp1", help="prefix of the task archives; must be new for every submission")
    de.add_argument("--out", default="data/design/exp1")
    de.add_argument("--interim", default=None, help="interim folder with run_quality.csv" + DS)
    de.add_argument("--runs", default=None, help="run folders to copy from" + DS)
    de.add_argument("--weather-dir", help="folder with the original MARS weather CSVs (<met_hash>.csv), if you have them")
    de.add_argument("--overwrite", action="store_true")

    fr = sub.add_parser("france", help="run the surrogate on the 1979-2024 Agri4Cast weather for France")
    fr.add_argument("--weather", default="data/raw/france_weather/france_weather.parquet",
                    help="the Agri4Cast table (france_weather_1979_2024.csv, or a parquet copy)")
    fr.add_argument("--limit", type=int, help="only the first N fields (quick test)")
    fr.add_argument("--spray", default="01.03", help="spray day of every year, day.month (default: 01.03)")
    fr.add_argument("--dose", type=float, default=None, help="dose in kg/ha (default: 2.4)")

    wi = sub.add_parser("whatif", help="compare spray days for a weather table")
    wi.add_argument("--weather", help="CSV with date, rain_mm, temp_c[, pan_evap_mm]; omit for a made-up example")
    wi.add_argument("--first-day", help="first candidate spray day (YYYY-MM-DD); default: day 31 of the table")
    wi.add_argument("--candidates", type=int, default=7, help="number of consecutive candidate days")
    wi.add_argument("--horizon", type=int, default=14, help="days after spraying to add up")
    wi.add_argument("--models", default=None, help="model folder" + DS)
    wi.add_argument("--dose", type=float, default=2.4, help="dose in kg/ha (default: 2.4)")

    aw = sub.add_parser("add-weather", help="put each field's weather file into result folders that came without it")
    aw.add_argument("--runs", default="data/raw/runs_varied", help="result folders made by `rerun --variants`")
    aw.add_argument("--source", default="data/raw/runs", help="the original run folders, which hold the weather files")

    rr = sub.add_parser("rerun", help="run PRZM again on Windows with corrected Henry constant and moisture setting")
    rr.add_argument("--exe", required=True, help=r"path to WINPRZM.exe, e.g. C:\Temp\X3MZI0OQ2D67EUQHFZ\WINPRZM.exe")
    rr.add_argument("--runs", default="data/raw/runs", help="folder with the original run folders")
    rr.add_argument("--out", default=None,
                    help="where the new results go (default: data/raw/runs_fixed, or data/raw/runs_varied with --variants)")
    rr.add_argument("--work", default=r"C:\Temp\rr", help="short scratch folder; PRZM cannot handle long paths")
    rr.add_argument("--henry", default=None, help="Henry constant, at most 8 characters (default: 0.37E-06); 'keep' = unchanged")
    rr.add_argument("--moisture-ref", default=None, help="reference soil moisture (default: 1); 'keep' = unchanged")
    rr.add_argument("--workers", type=int, default=4, help="PRZM runs at the same time")
    rr.add_argument("--limit", type=int, help="only the first N folders (for a quick test)")
    rr.add_argument("--retry-failed", action="store_true", help="also retry folders where PRZM reported an error last time")
    rr.add_argument("--variants", type=int, default=0,
                    help="extra copies per field with varied spray dates and dose (0 = plain re-run)")
    rr.add_argument("--spray-windows", default=None,
                    help="spray windows for the copies, day.month-day.month, comma separated (default: 15.02-30.04,01.10-30.11)")
    rr.add_argument("--doses", default=None, help="doses in kg/ha for the copies, comma separated (default: 0.24,1.20,2.40)")
    rr.add_argument("--seed", type=int, default=1, help="number that fixes the random spray dates")
    rr.add_argument("--fields-from", default=None,
                    help="only fields with a finished result in this folder (default with --variants: data/raw/runs_fixed if it exists)")

    r = sub.add_parser("run", help="analyse one run folder")
    r.add_argument("folder")
    r.add_argument("--out", default="reports")

    return p


RERUN_OUT = "data/raw/runs_fixed"            # plain re-run: one corrected run per field
RERUN_VARIED_OUT = "data/raw/runs_varied"    # re-run with --variants: varied spray dates and dose


def resolve_paths(a: argparse.Namespace) -> argparse.Namespace:
    """Fill every path left at None with the chosen data set's default (in place; also returned)."""
    paths = DATASETS[a.dataset]
    for arg, key in DATASET_ARGS.get(a.cmd, {}).items():
        if getattr(a, arg, None) is None:
            setattr(a, arg, paths[key])
    if a.cmd == "rerun":           # always starts from the delivered folder; the target depends on the kind of re-run
        if a.out is None:
            a.out = RERUN_VARIED_OUT if a.variants else RERUN_OUT
        if a.variants and a.fields_from is None and Path(RERUN_OUT).is_dir():
            a.fields_from = RERUN_OUT
    return a


def parse_args(argv=None) -> argparse.Namespace:
    return resolve_paths(build_parser().parse_args(argv))


def main(argv=None) -> int:
    a = parse_args(argv)
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
        split = lambda text, default: default if text is None else tuple(x.strip() for x in text.split(",") if x.strip())
        recs = rerun.rerun_all(a.runs, a.out, a.exe, a.work, henry=pick(a.henry, rerun.HENRY_FIXED),
                               moisture_ref=pick(a.moisture_ref, rerun.MOISTURE_REF_FIXED), workers=a.workers, limit=a.limit,
                               retry_failed=a.retry_failed, variants=a.variants,
                               windows=split(a.spray_windows, rerun.DEFAULT_WINDOWS),
                               doses=split(a.doses, rerun.DEFAULT_DOSES), seed=a.seed, fields_from=a.fields_from)
        if a.variants:
            print(f"spray plan: {Path(a.out) / 'rerun_plan.csv'}")
        counts = {}
        for rec in recs:
            counts[rec["status"]] = counts.get(rec["status"], 0) + 1
        print(f"\nruns started now: {len(recs)} {counts}")
        print(f"results in {a.out} | log: {Path(a.out) / 'rerun_log.csv'}")
        print("ok = finished | przm_error = PRZM cannot calculate this field | empty, failed, timeout = see the log")
    elif a.cmd == "audit":
        from .quality import audit
        s = audit(a.runs, a.interim, results=a.results, figures=a.figures, trust=a.trust)
        print(f"\nfolders: {s['folders']} {s['status_counts']}")
        print(f"readable runs: {s['readable_runs']} | above the envelope: {s['envelope_rule_bad_runs']} | "
              f"balance error above tolerance: {s['runs_with_balance_error_above_tolerance']}")
        print(f"trust rule: {s['trust_rule']} | trusted runs: {s['trusted_runs']} | "
              f"trusted pesticide data: {s['clean_run_years']:.0f} of {s['total_run_years']:.0f} run-years")
        print(f"details: {Path(a.interim) / 'run_quality.csv'}, {Path(a.results) / 'quality_summary.json'}, "
              f"{Path(a.figures) / 'q*.png'}")
    elif a.cmd == "add-weather":
        n = batch.add_weather(a.runs, a.source)
        print(f"weather file added to {n} result folders under {a.runs}")
    elif a.cmd == "features":
        from .features import build_feature_table
        t = build_feature_table(a.interim, a.out)
        print(f"\n{len(t):,} rain-day rows written to {a.out}")
    elif a.cmd == "train":
        import json
        from .models import train_all, yearly_cv
        if a.cv:
            print(json.dumps(yearly_cv(a.features, results=a.results, figures=a.figures, rounds=a.rounds), indent=2))
            print(f"per year: {Path(a.results) / 'cv_by_year.csv'} | "
                  f"figure: {Path(a.figures) / 'm7_scores_by_held_out_year.png'}")
            return 0
        m = train_all(a.features, a.models, results=a.results, figures=a.figures, rounds=a.rounds)
        print(json.dumps({k: m[k] for k in ("split", "runoff", "loss", "high_loss")}, indent=2))
        print(f"models in {a.models} | metrics in {Path(a.results) / 'model_metrics.json'} | "
              f"figures in {Path(a.figures) / 'm*.png'}")
    elif a.cmd == "lstm":
        import json
        from .lstm import train_and_compare
        m = train_and_compare(a.interim, a.features, model_dir=a.models, results=a.results, figures=a.figures,
                              epochs=a.epochs, limit=a.limit)
        print(json.dumps({k: m[k] for k in ("rows_compared", "epochs_run", "train_minutes", "lstm", "trees")}, indent=2))
        print(f"details: {Path(a.results) / 'lstm_vs_trees.json'} | figure: {Path(a.figures) / 'm8_lstm_vs_trees.png'}")
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
        day, month = (int(x) for x in a.spray.split("."))
        extra = {} if a.dose is None else {"rate_kgha": a.dose}
        m = run_france(a.weather, interim=a.interim, features_path=a.features, model_dir=a.models, out_path=a.out,
                       results=a.results, figures=a.figures, limit=a.limit, app_day=day, app_month=month, **extra)
        print(json.dumps(m, indent=2))
        res, fig = Path(a.results), Path(a.figures)
        print(f"per year: {res / 'france_by_year.csv'} | per grid cell: {res / 'france_by_grid.csv'} | "
              f"figures: {fig / 'f1_france_by_year.png'}, {fig / 'f2_france_map.png'} | field-years: {a.out}")
    elif a.cmd == "whatif":
        import pandas as pd
        from .whatif import compare_spray_days, example_weather, prepare_weather
        w = prepare_weather(pd.read_csv(a.weather) if a.weather else example_weather())
        first = pd.Timestamp(a.first_day) if a.first_day else w.index[min(30, len(w) - 2)]
        cands = [d for d in pd.date_range(first, periods=a.candidates) if d in w.index]
        table = compare_spray_days(w, cands, a.horizon, model_dir=a.models, rate_kgha=a.dose)
        print(table.to_string(index=False))
        ranked = table[table["rank"].notna()].sort_values("predicted_loss_gha")
        if len(ranked):
            best = ranked.iloc[0]
            print(f"\nLowest predicted loss: spray on {best.spray_date} ({best.predicted_loss_gha} g/ha in {a.horizon} days).")
        for note in table.attrs["notes"]:
            print("NOTE:", note)
        print(f"Dose: {a.dose:g} kg/ha. Valid only for Flufenacet on winter cereals, and for spray dates and doses "
              "like those in the training runs (see docs/MODEL_REPORT.md).")
    elif a.cmd == "run":
        from .report import analyze_run
        analyze_run(a.folder, a.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
