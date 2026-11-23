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
| [docs/NEW_RUNS_PLAN.md](docs/NEW_RUNS_PLAN.md) | Prepared experiment: new simulations with varied spray date, dose and substance |
| [docs/ROADMAP.md](docs/ROADMAP.md) | What is done and what is next |
| [Progress slides](https://claude.ai/artifact/VzutykKbE1M1tja2ZrZHcj) · [first pitch](https://claude.ai/artifact/Y82phRAgCapMtktvPri94c) | Presentations (private until shared by the owner) |

## Main results so far

> **Important, 23 Nov 2026:** test runs of PRZM on our own computer showed that two settings in the
> delivered simulations are wrong (the Henry constant and the reference soil moisture; see
> [docs/DATA_REPORT.md, section 6](docs/DATA_REPORT.md#6-local-re-runs-two-settings-are-wrong-23-nov-2026)).
> The pesticide numbers below were learned from the delivered data and will change once the
> simulations are redone with [`rerun`](#part-c-redo-the-simulations-with-corrected-settings-windows-only).
> The water results and the methods are not affected.

- The data: 9,977 real fields in France (a random sample of real pesticide applications), each
  with its own soil, slope and Agri4Cast weather. **3,958 runs contain results.** Pesticide, dose
  and spray date are the same in every run. The weather is labelled 1990-1999 but is really 2006-2015.
- The pesticide part of the simulator is **numerically broken in part of the runs**
  (fake pesticide mass, losses up to 1e34 g/ha): 30 % of the runs beyond doubt. A cautious
  plausibility rule keeps 73 % of the simulated run-years. The water part is sound.
- Tested by leaving out one year at a time (and weather files never used in training), the
  surrogate reproduces PRZM's daily runoff with R² 0.97 (curve-number formula alone: 0.92) and
  daily pesticide loss with R² 0.91 (0.75 to 0.97 depending on the year; simple baseline: 0.49).
  It finds high-loss days with PR-AUC 0.92: 91 % of its alarms are real, and it finds 76 % of
  the high-loss days. It underestimates total loss by about 8 %.
- It is a few hundred times faster than PRZM.
- Run on 45 years of real weather (1979-2023) for all fields, the surrogate shows that single
  years differ by a factor of ten, and that five years carry a quarter of all loss.
- A second surrogate, a small LSTM, matches the trees on daily pesticide loss and finds more
  high-loss days in a first test on two years; it still needs the year-by-year test.

Everything describes the PRZM model for Flufenacet at 2.4 kg/ha on winter cereals
sprayed on 1 March. It is not validated against measurements.

## How to run it, step by step

There are two ways to use this repository:

- **Part A: try it in 5 minutes.** No data needed. The trained models are already in the repository.
- **Part B: redo the whole project from the raw simulation data.** About 45 minutes, most of it waiting.

You need Python 3.10 or newer and Git. All commands are typed in a terminal
(on Windows: "PowerShell" or "Command Prompt").

### Part A: try it in 5 minutes

**Step 1. Download the repository.**

```bash
git clone https://github.com/saadnajib/RunoffWatch.git
```
```bash
cd RunoffWatch
```

**Step 2. Make a private Python environment** (keeps this project's packages apart from your others).

```bash
python -m venv .venv
```

Switch it on. On Windows:

```bash
.venv\Scripts\activate
```

On Mac or Linux:

```bash
source .venv/bin/activate
```

Your prompt now starts with `(.venv)`. Do this "switch on" step again each time you open a new terminal.

**Step 3. Install the project.** Takes 1-2 minutes.

```bash
pip install -e ".[dev,app]"
```

**Step 4. Check that it works.** This runs the automatic tests (about 15 seconds).

```bash
python -m pytest -q
```

You should see `204 passed, 1 skipped` (the skipped one needs PyTorch).

**Step 5. Ask the model a question.** This compares 7 possible spray days for a made-up weather example.

```bash
python -m runoffwatch whatif
```

You get a table with one row per spray day and the predicted pesticide loss
in the 14 days after it. Lower is better.

**Step 6. Open the app** (same thing, with sliders).

```bash
streamlit run app.py
```

Your browser opens the spray-day advisor. Stop it with `Ctrl+C` in the terminal.

**Optional: use your own weather.** Make a CSV file with the columns
`date, rain_mm, temp_c` (and `pan_evap_mm` if you have it), one row per day,
starting about 30 days before the first spray day. Then:

```bash
python -m runoffwatch whatif --weather my_weather.csv --first-day 2027-03-01 --candidates 7
```

### Part B: redo the whole project from the raw data

Do Part A, steps 1-3, first.

**Step 1. Get the data.** Download the ten `.7z` files (`run_000000_to_000999__....7z`
to `run_009000_to_009976__....7z`, 350 MB in total) from the project's Google Drive
folder and put them into the folder `data/raw/archives/` (create it if it does not
exist). Do not rename or unpack them. The data is never uploaded to GitHub.

**Step 2. Run the seven commands below, one after the other, in this order.**
Each one needs the results of the one before.

| # | Command | What it does | Time | What you get |
|---|---|---|---|---|
| 1 | `extract` | Unpacks the archives | 1 min | 9,977 run folders in `data/raw/runs/` (3.7 GB) |
| 2 | `inventory` | Finds what is different between the runs | 5 s | `data/interim/inventory_*.csv` |
| 3 | `qc` | Reads every run and does basic checks | 1 min | `data/interim/runs_qc.csv` and one daily table per run |
| 4 | `audit` | **Task 1:** decides which results can be trusted | 30 s | `data/interim/run_quality.csv`, figures `docs/figures/q*.png` |
| 5 | `features` | Builds the table the models learn from (one row per rain day) | 2 min | `data/processed/features.parquet` |
| 6 | `train` | **Tasks 2 and 3:** trains the emulator and the high-loss classifier | 2 min | `models/`, figures `docs/figures/m*.png`, `docs/results/model_metrics.json` |
| 7 | `train --cv` | Honest test: leaves out one year at a time | 25 min | `docs/results/cv_summary.json`, `cv_by_year.csv` |

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
```bash
python -m runoffwatch train --cv
```

Times are for a laptop with 4 cores. You need about 5 GB of free disk space.

**Optional extras** (need the steps above):

| Command | What it does | Time |
|---|---|---|
| `pip install -e ".[lstm]"` then `python -m runoffwatch lstm` | Trains a second surrogate, an LSTM neural network, and compares it with the tree surrogate on the same test data | 10-20 min |
| `python -m runoffwatch france` | Runs the surrogate on the 1979-2024 Agri4Cast weather for France (needs `france_weather_1979_2024.csv` in `data/raw/france_weather/`; pass it with `--weather`) | 8 min |
| `python -m runoffwatch design` | Writes run files for NEW simulations (varied spray date, dose, substance) into `data/design/`. Nothing is uploaded; see [docs/NEW_RUNS_PLAN.md](docs/NEW_RUNS_PLAN.md) | 1 min |

**Step 3. Look at the results.**

| The three project tasks | Where to look |
|---|---|
| **Task 1.** Find the broken simulations | [docs/DATA_REPORT.md](docs/DATA_REPORT.md), numbers in `docs/results/quality_summary.json` |
| **Task 2.** Predict high-loss days and explain them | [docs/MODEL_REPORT.md](docs/MODEL_REPORT.md), sections 3 and 4 |
| **Task 3.** Fast copy of the simulator (emulator) | [docs/MODEL_REPORT.md](docs/MODEL_REPORT.md), sections 1 to 3; try it with Part A, steps 5 and 6 |

Running Part B overwrites the models, figures and result files that came with
the repository. The numbers should come out the same as in the reports.

### Part C: redo the simulations with corrected settings (Windows only)

PRZM itself is a Windows program (`WINPRZM.exe`, in this year's project cloud folder). It needs
about 3 seconds per field, so all 6,958 fields with input files take roughly 1.5 hours with four
runs at a time.

1. Put the program at a short path without spaces, for example
   `C:\Temp\X3MZI0OQ2D67EUQHFZ\WINPRZM.exe`. PRZM cannot handle long paths.
2. Make sure the original runs are unpacked in `data/raw/runs/` (Part B, step 1).
3. Try 20 fields first:

```bash
python -m runoffwatch rerun --exe C:\Temp\X3MZI0OQ2D67EUQHFZ\WINPRZM.exe --limit 20
```

4. If that works, run all of them. The command skips fields that are already done, so you can stop
   it with Ctrl+C and start it again later:

```bash
python -m runoffwatch rerun --exe C:\Temp\X3MZI0OQ2D67EUQHFZ\WINPRZM.exe
```

The new results go to `data/raw/runs_fixed/` in the same layout as the originals, with a log in
`rerun_log.csv`. By default the Henry constant becomes `0.37E-06` and the reference soil moisture
`1`; `--henry keep` or `--moisture-ref keep` leaves one of them as delivered.

### If something goes wrong

| Message | What to do |
|---|---|
| `No module named runoffwatch` | The environment is not switched on (Part A, step 2), or step 3 was skipped |
| `No .7z or .zip archives in data/raw/archives` | The data files are not in that folder (Part B, step 1) |
| `No run folders ... under data/raw/runs` | Run `extract` first |
| `... runs_qc.csv` or `run_quality.csv` not found | A step was skipped; run the seven commands in order |
| `missing [...]. Run python -m runoffwatch train first` | The `models/` folder is empty; run `git checkout models` to get the shipped models back, or run `train` |
| `python` is not recognised (Windows) | Use `py` instead of `python` |

Other useful commands: `python -m runoffwatch --help` lists everything;
`python -m runoffwatch run data/raw/runs/<archive>/<run folder>` makes a
report for one single run.

## What is here

| Path | Purpose |
|---|---|
| `runoffwatch/przm_io.py`, `przm_inp.py` | Read PRZM run folders: daily results in plain units, field and soil settings |
| `runoffwatch/batch.py` | Unpack archives, inventory what differs between runs, quality-check every run |
| `runoffwatch/rerun.py` | Runs PRZM again on Windows with the two corrected settings |
| `runoffwatch/quality.py` | Task 1: which results can be trusted (envelope rule, Isolation Forest, causes) |
| `runoffwatch/features.py` | One row per rain day: weather, spray history and soil inputs |
| `runoffwatch/models.py` | Surrogate (runoff x concentration), high-loss classifier, baselines, evaluation |
| `runoffwatch/whatif.py`, `app.py` | Spray-day advisor: library, command line and Streamlit app |
| `runoffwatch/figures.py`, `report.py` | Figures and single-run report |
| `models/` | Trained models (LightGBM text files, 2 MB) |
| `docs/figures/`, `docs/results/` | Figures and result tables used in the reports |
| `runoffwatch/lstm.py` | Second surrogate: an LSTM, compared with the trees |
| `runoffwatch/longrun.py` | Surrogate on 45 years of Agri4Cast weather for France |
| `runoffwatch/design.py` | Generator for new simulation runs (run files and task archives) |
| `tests/` | 208 tests on synthetic run folders (no project data in git) |
| `runoffwatch/pipeline.py`, `plots.py`, `przm_spikes.py`, `examples/` | Earlier exploration code, kept for reference |

Code and documents were written with the help of an AI assistant (Claude).
