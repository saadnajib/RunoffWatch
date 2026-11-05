# RunoffWatch

Machine learning on ~10,000 PRZM pesticide simulations to learn **when rain
washes pesticide off the soil of a field, and when it does not**. Field-level,
daily resolution; rivers are out of scope.

- **Plan, step by step:** [docs/ROADMAP.md](docs/ROADMAP.md)
- **Project scope:** [docs/PROJECT_SCOPE.md](docs/PROJECT_SCOPE.md)
- **Presentation:** https://claude.ai/artifact/Y82phRAgCapMtktvPri94c
- Course: ETX8 Landscape-modelling project, RPTU Kaiserslautern-Landau

## Install

```bash
pip install -e ".[dev]"
```

Add `ml` for the machine-learning phases: `pip install -e ".[dev,ml]"`.

## Use

Put the `.7z` archives in `data/raw/archives/`, then run the steps in order:

```bash
python -m runoffwatch extract
```
```bash
python -m runoffwatch inventory
```
```bash
python -m runoffwatch qc
```

Analyse a single run folder (tables + two plots in `reports/`):

```bash
python -m runoffwatch run data/raw/runs/<archive>/<run folder>
```

Run the tests:

```bash
python -m pytest -q
```

## What is here

| Path | Purpose |
|---|---|
| `runoffwatch/przm_io.py` | Reads one FOCUS PRZM run folder (`.met`, `.inp`, `.ZTS`, `.OUT`, `mc.log`) into a daily table in plain units, with sanity checks |
| `runoffwatch/przm_spikes.py` | Daily features (antecedent rain, days since spraying) and high-loss-day flags (`is_spike` in code) |
| `runoffwatch/batch.py` | Unpack archives, inventory what differs between runs, quality-check all runs |
| `runoffwatch/report.py` | Report for one run: tables and plots |
| `runoffwatch/__main__.py` | Command line (`extract`, `inventory`, `qc`, `run`) |
| `tests/` | Tests on small synthetic run folders (no real data in git) |
| `data/` | Local data folders, not in git; see `data/README.md` |
| `runoffwatch/pipeline.py`, `plots.py`, `examples/demo_synthetic.py` | Earlier pipeline for *measured* river data; out of scope now, kept for reference |

## Status

Phase 0 (setup) is done. Next is Phase 1: download the archives and run
`extract`, `inventory` and `qc`. The one run checked so far failed the
stability check (yearly soil decay grows from 0.17 to 1.3 million).
