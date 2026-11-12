# RunoffWatch

A fast machine-learning **surrogate of the PRZM pesticide model**: from daily
weather and soil it predicts how much pesticide is washed off a field after
spraying, and a small **spray-day advisor** uses it to compare spray days.

Course project, ETX8 Landscape modelling, RPTU Kaiserslautern-Landau.

| Read this | For |
|---|---|
| [docs/DATA_REPORT.md](docs/DATA_REPORT.md) | What the simulation data contains and which part can be trusted |
| [docs/MODEL_REPORT.md](docs/MODEL_REPORT.md) | Models, evaluation, drivers, risk calendar, limits |
| [docs/RELATED_WORK.md](docs/RELATED_WORK.md) | Existing tools and surrogates, baselines |
| [docs/PROJECT_SCOPE.md](docs/PROJECT_SCOPE.md) | Scope and research questions |
| [docs/ROADMAP.md](docs/ROADMAP.md) | What is done and what is next |

## Main results so far

- Of 9,977 run folders, **3,958 contain results**. Weather (695 files) and soil vary;
  pesticide, dose and spray date are the same in every run.
- The pesticide part of the simulator is **numerically broken in part of the runs**
  (fake pesticide mass, losses up to 1e34 g/ha). A physical plausibility rule keeps
  73 % of the simulated run-years. The water part is sound.
- On weather files **and years** kept out of training, the surrogate reproduces PRZM's
  daily runoff with R² 0.98 (curve-number formula alone: 0.93) and daily pesticide loss
  with R² 0.94, and it finds high-loss days with PR-AUC 0.91. It underestimates total
  loss by about 17 %.
- It is a few hundred times faster than PRZM.

Everything describes the PRZM model for Flufenacet at 2.4 kg/ha on winter cereals
sprayed on 1 March. It is not validated against measurements.

## Install

```bash
pip install -e ".[dev]"
```

## Try the advisor (models are included in the repository)

```bash
python -m runoffwatch whatif
```
```bash
pip install -e ".[app]"
```
```bash
streamlit run app.py
```

Use your own weather: a CSV with the columns `date, rain_mm, temp_c` (optional
`pan_evap_mm`), one row per day, starting about 30 days before the first spray day.

```bash
python -m runoffwatch whatif --weather my_weather.csv --first-day 2027-03-01 --candidates 7
```

## Reproduce everything from the raw data

Put the ten `.7z` archives from the project Drive into `data/raw/archives/`
(data is never committed), then:

```bash
python -m runoffwatch extract
```
```bash
python -m runoffwatch inventory
```
```bash
python -m runoffwatch qc
```
```bash
python -m runoffwatch audit
```
```bash
python -m runoffwatch features
```
```bash
python -m runoffwatch train
```

About 10 minutes in total on 4 cores, 5 GB of disk. Tests:

```bash
python -m pytest -q
```

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
| `runoffwatch/przm_io.py`, `przm_inp.py` | Read PRZM run folders: daily results in plain units, field and soil settings |
| `runoffwatch/batch.py` | Unpack archives, inventory what differs between runs, quality-check every run |
| `runoffwatch/quality.py` | Task 1: which results can be trusted (envelope rule, Isolation Forest, causes) |
| `runoffwatch/features.py` | One row per rain day: weather, spray history and soil inputs |
| `runoffwatch/models.py` | Surrogate (runoff x concentration), high-loss classifier, baselines, evaluation |
| `runoffwatch/whatif.py`, `app.py` | Spray-day advisor: library, command line and Streamlit app |
| `runoffwatch/figures.py`, `report.py` | Figures and single-run report |
| `models/` | Trained models (LightGBM text files, 2 MB) |
| `docs/figures/`, `docs/results/` | Figures and result tables used in the reports |
| `tests/` | 161 tests on synthetic run folders (no project data in git) |
| `runoffwatch/pipeline.py`, `plots.py`, `przm_spikes.py`, `examples/` | Earlier exploration code, kept for reference |

Code and documents were written with the help of an AI assistant (Claude).
