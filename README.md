# RunoffWatch

Machine learning on ~10,000 pesticide-runoff simulations to learn **when rain
washes pesticide off the soil of a field, and when it does not**. Field-level,
daily resolution; rivers are out of scope.

- **Project scope:** [docs/PROJECT_SCOPE.md](docs/PROJECT_SCOPE.md)
- **Presentation:** https://claude.ai/artifact/Y82phRAgCapMtktvPri94c
- Course: ETX8 Landscape-modelling project, RPTU Kaiserslautern-Landau

## What is here

| Path | Purpose |
|---|---|
| `runoffwatch/przm_io.py` | Reads one FOCUS PRZM run folder (`.met`, `.inp`, `.ZTS`, `.OUT`, `mc.log`) into a daily table in plain units, with sanity checks (weather in vs. out, mass balance, log errors, numerical blow-up) |
| `runoffwatch/przm_spikes.py` | Flags spike days and reports spike chance by rain amount, days since spraying and soil wetness |
| `runoffwatch/pipeline.py` | General pipeline for *measured* data: hourly weather + sparse river samples, rolling-baseline spikes, 0–72 h lag bins |
| `runoffwatch/plots.py` | Diagnostic plots |
| `examples/analyze_przm_run.py` | Analyse one simulation run |
| `examples/demo_synthetic.py` | End-to-end demo of the measured-data pipeline on synthetic data |

## Quick start

```bash
pip install -r requirements.txt
```

Analyse one simulation run (writes a daily CSV and plots to `examples/output/`):

```bash
python -m examples.analyze_przm_run path/to/run_0000140_grid_086080
```

Run the synthetic demo of the measured-data pipeline:

```bash
python -m examples.demo_synthetic
```

## Status

The reader and single-run analysis work and have been tested on one real run.
That run failed the stability check (yearly soil decay grows from 0.17 to
1.3 million), so finding broken runs automatically is the project's first task.
