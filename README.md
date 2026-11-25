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

> **Current state, 25 Nov 2026:** the models are now trained on simulations with **varied spray
> dates and doses**. Every field with a corrected result got two more PRZM runs, one sprayed in
> spring (15 Feb - 30 Apr) and one in autumn (1 Oct - 30 Nov), with 0.24, 1.20 or 2.40 kg/ha. The
> earlier models, trained on the corrected runs that are all sprayed on 1 March with 2.4 kg/ha,
> are kept for comparison. Details: [docs/MODEL_REPORT.md, section 4](docs/MODEL_REPORT.md#4-results-with-varied-spray-dates-and-doses).
>
> **23 Nov 2026:** two settings in the delivered simulations were wrong (the Henry constant and
> the reference soil moisture), which made the pesticide numbers wrong in every run; all fields
> were re-run with [`rerun`](#step-2-redo-the-simulations-with-corrected-settings-windows-only)
> ([docs/DATA_REPORT.md, section 6](docs/DATA_REPORT.md#6-local-re-runs-two-settings-are-wrong-23-nov-2026)).
> The old results are kept in `docs/results/delivered/` and `docs/figures/delivered/`; an
> old-vs-new table is at the top of [docs/MODEL_REPORT.md](docs/MODEL_REPORT.md).

- The data: 9,977 real fields in France (a random sample of real pesticide applications), each
  with its own soil, slope and Agri4Cast weather. After the corrected re-run **5,609 fields have a
  full ten-year result** (3,958 as delivered); 1,335 cannot be calculated by PRZM. The weather is
  labelled 1990-1999 but is really 2006-2015.
- With the varied runs the models learn from 16,818 runs (the 5,609 runs sprayed on 1 March plus
  11,209 runs with varied spray dates and doses): 24.6 million rain days. The pesticide is
  Flufenacet in every run, and the crop is always winter cereals with the same crop calendar.
- In the delivered simulations the pesticide numbers were broken (losses up to 1e34 g/ha) and,
  as the re-runs showed, wrong in all runs. In the corrected runs PRZM's own pesticide balance is
  exact, so all runs are used. The water part did not change.
- Tested by leaving out one year at a time (ten years, and weather files never used in training):

  | | **Varied dates and doses** | Corrected, 1 March only |
  |---|---|---|
  | Runoff, daily R² (curve-number formula alone: 0.94) | **0.98** | 0.98 |
  | Pesticide loss, daily R² (range over years) | **0.92** (0.78-0.97) | 0.95 (0.89-0.99) |
  | Sum of all loss, surrogate / PRZM (range over years) | **0.98** (0.90-1.18) | 0.99 (0.86-1.12) |
  | High-loss days, PR-AUC | **0.97** | 0.97 |
  | Alarms that are real / high-loss days found | **92 % / 92 %** | 92 % / 90 % |

  The harder task costs a little accuracy on daily loss. In one year (1990) a simple formula
  beats the surrogate; we do not know why yet.
- **Spray date (read straight from PRZM).** Spraying in autumn loses 2 to 7 times more of the dose
  than spraying in spring. The chemistry per millimetre of runoff is the same; the difference is how
  much water runs off in the first month. That comes from PRZM's fixed crop calendar: until the
  crop emerges on 12 Nov (the same date in every field and year) much more rain becomes runoff.
  So the sharp step in mid-November is a property of the PRZM scenario, not of nature
  ([docs/MODEL_REPORT.md](docs/MODEL_REPORT.md#what-przm-says-about-the-spray-date-and-why)).
- It is about 70 times faster than PRZM (0.05 s against 3.4 s for ten years of one field; the
  1-March models: 0.03 s).
- Run on 45 years of real weather (1979-2023) for all fields, sprayed on 1 March, the surrogate
  shows that the worst year has 2.8 times the loss of the median year, and that five years carry
  23 % of all loss (1-March models; the new models give the same five worst years).
- A second surrogate, a small LSTM, beats the trees on daily pesticide loss and on finding
  high-loss days in a first test on two years (1-March data), but is much less exact on small
  losses and puts the total 8 % too low; it still needs the year-by-year test and does not handle
  varied spray dates yet.

Everything describes the PRZM model for Flufenacet on winter cereals, sprayed between 15 Feb and
30 Apr or between 1 Oct and 30 Nov with 0.24 to 2.4 kg/ha. It is not validated against
measurements.

## How to run it, step by step

There are two ways to use this repository:

- **Part A: try it in 5 minutes.** No data needed. The trained models are already in the repository.
- **Part B: redo the whole project from the raw simulation data**, with the corrected simulations.
  Roughly 2-3 hours, most of it waiting for PRZM on a Windows PC.
- **Part C: the delivered data.** The same steps on the simulations as delivered, which is how the
  fault was found.

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

You should see `521 passed, 1 skipped` (the skipped one needs PyTorch; with PyTorch installed it is `522 passed`).

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

Add `--dose 1.2` to give the dose in kg/ha (default 2.4); the app has a dose field too.

### Part B: from the raw data to the corrected results

Do Part A, steps 1-3, first.

The commands below work on the **corrected** simulations unless you say otherwise. They read
`data/raw/runs_fixed/` and write to `data/interim_fixed/`, `data/processed/features_fixed.parquet`,
`models/`, `docs/results/` and `docs/figures/`. A path you give yourself (for example `--runs`)
always wins.

**Step 1. Get the data.** Download the ten `.7z` files (`run_000000_to_000999__....7z`
to `run_009000_to_009976__....7z`, 350 MB in total) from the project's Google Drive
folder and put them into the folder `data/raw/archives/` (create it if it does not
exist). Do not rename or unpack them. The data is never uploaded to GitHub. Then unpack them:

```bash
python -m runoffwatch extract
```

You get 9,977 run folders in `data/raw/runs/` (about 3.7 GB). These are the delivered simulations.

#### Step 2. Redo the simulations with corrected settings (Windows only)

PRZM itself is a Windows program (`WINPRZM.exe`, in this year's project cloud folder). It needs
about 3 seconds per field, so all 6,958 fields with input files take roughly 1.5 hours with four
runs at a time.

1. Put the program at a short path without spaces, for example
   `C:\Temp\X3MZI0OQ2D67EUQHFZ\WINPRZM.exe`. PRZM cannot handle long paths.
2. Make sure the original runs are unpacked in `data/raw/runs/` (step 1).
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
`rerun_log.csv`. In the log, `ok` means the field finished. `przm_error` means PRZM itself could
not calculate the field: it shows an error box titled "Fortran", and the command then stops that
run and goes on, so nobody has to click. These fields are skipped on the next start; add
`--retry-failed` to try them again. Most of them are fields that gave no results in the delivered
data either. By default the Henry constant becomes `0.37E-06` and the reference soil moisture
`1`; `--henry keep` or `--moisture-ref keep` leaves one of them as delivered.

**Optional: runs with other spray dates and doses.** In all delivered runs every field is sprayed
on 1 March with 2.4 kg/ha, so the models cannot say anything about another spray day or another
dose. `rerun --variants N` makes N extra copies of every field, each with a varied spray date and
dose. By default each copy gets one of two spray windows (15 Feb to 30 Apr, or 1 Oct to 30 Nov),
one of three doses (0.24, 1.20 or 2.40 kg/ha) and, inside its window, a different random spray day
in each of the ten simulated years. With two copies, a field gets one spring and one autumn copy.

A trial with 10 fields (20 runs) worked with the real PRZM program, and on 25 Nov 2026 the full
set (11,218 runs) was made and analysed (docs/MODEL_REPORT.md, section 4). Try 10 fields first:

```bash
python -m runoffwatch rerun --exe C:\Temp\X3MZI0OQ2D67EUQHFZ\WINPRZM.exe --variants 2 --limit 10
```

If that works, run all of them:

```bash
python -m runoffwatch rerun --exe C:\Temp\X3MZI0OQ2D67EUQHFZ\WINPRZM.exe --variants 2
```

The results go to `data/raw/runs_varied/`, in folders named `<field>__v1`, `<field>__v2`. The
spray plan of every copy (window, dose, spray dates) is written to `rerun_plan.csv` in the same
folder. Only fields that already have a finished result in `data/raw/runs_fixed/` are used
(5,609 fields), so two copies are 11,218 runs: about 2.6 hours at 3.4 seconds per run with four at
a time, and about 6.5 GB of results (the weather file is not copied again). The plan depends only
on the seed, the field name and the copy number, so the same command always makes the same runs,
and it can be stopped and started again. Other choices: `--spray-windows 15.02-30.04,01.10-30.11`,
`--doses 0.24,1.20,2.40`, `--seed 1`.

**Analysing the runs with varied spray dates and doses.** The analysis side can now handle these
runs. The models get two more inputs: the day of the year of the last spraying and its dose. Do
step 3 below for the corrected data first, because this data set also uses its results. Then run
these commands in this order.

The result folders made by `rerun --variants` come without the weather file. This command puts
each field's weather file into them. It must run before `inventory`:

```bash
python -m runoffwatch add-weather
```

Then the usual steps, with `--dataset varied`:

```bash
python -m runoffwatch --dataset varied inventory
```
```bash
python -m runoffwatch --dataset varied qc
```
```bash
python -m runoffwatch --dataset varied audit
```
```bash
python -m runoffwatch --dataset varied features
```
```bash
python -m runoffwatch --dataset varied train
```
```bash
python -m runoffwatch --dataset varied train --cv
```

Optional, the 45-year run with the new models:

```bash
python -m runoffwatch --dataset varied france
```

Run `train`, `train --cv` and `france` as **separate commands**, one after the other, not in one
go: this data set is large, and each step needs about 12 GB of memory. `train` takes about
22 minutes, `train --cv` about 70 minutes (measured on the project PC).

The feature table holds the corrected runs (sprayed on 1 March) plus the copies with varied spray
dates and doses. Models go to `models/varied/`, results to `docs/results/varied/` and figures to
`docs/figures/varied/`, so nothing of the corrected data set is overwritten. `train` also writes
`loss_by_spray_date.csv` and the figure `m9_loss_by_spray_date.png`: the share of the dose lost in
the year after spraying, by half-month of spraying, straight from PRZM. `train --cv` adds scores
per spray window and per dose. The LSTM comparison is not adapted: it refuses runs that are not
sprayed on 1 March. The app (`streamlit run app.py`) uses the models in `models/varied/`
when that folder is there, and otherwise the 1-March models in `models/`. On the command line,
`python -m runoffwatch --dataset varied whatif` uses the models in `models/varied/`.

Unconfirmed: the delivered dose of 2.4 kg/ha looks about ten times higher than usual field rates
of flufenacet products (a few hundred grams per hectare). This comes from general knowledge and
has not been checked against a product label or with the model owners. It is the reason
0.24 kg/ha is among the default doses.

The next steps also work on Mac or Linux: copy the folder `data/raw/runs_fixed/` there.

**Step 3. Run the six commands below, one after the other, in this order.**
Each one needs the results of the one before.

| # | Command | What it does | What you get |
|---|---|---|---|
| 1 | `inventory` | Finds what is different between the runs | `data/interim_fixed/inventory_*.csv` |
| 2 | `qc` | Reads every run and does basic checks | `data/interim_fixed/runs_qc.csv` and one daily table per run |
| 3 | `audit` | **Task 1:** decides which results can be trusted (here: PRZM's own balance error must stay small) | `data/interim_fixed/run_quality.csv`, `docs/results/quality_summary.json`, figures `docs/figures/q*.png` |
| 4 | `features` | Builds the table the models learn from (one row per rain day) | `data/processed/features_fixed.parquet` |
| 5 | `train` | **Tasks 2 and 3:** trains the emulator and the high-loss classifier | `models/`, figures `docs/figures/m*.png`, `docs/results/model_metrics.json` |
| 6 | `train --cv` | Honest test: leaves out one year at a time (the slow one) | `docs/results/cv_summary.json`, `cv_by_year.csv` |

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

On the delivered data these six steps took about 30 minutes on a laptop with 4 cores, most of it
`train --cv`. The corrected data has more fields with results, so expect somewhat longer. One data
set needs about 5 GB of free disk space (measured on the delivered data); both need about twice that.

**Optional extras** (need the steps above; times are approximate, measured on the delivered data):

| Command | What it does | Time |
|---|---|---|
| `pip install -e ".[lstm]"` then `python -m runoffwatch lstm` | Trains a second surrogate, an LSTM neural network, and compares it with the tree surrogate on the same test data | about 10-20 min |
| `python -m runoffwatch france` | Runs the surrogate on the 1979-2024 Agri4Cast weather for France (needs `france_weather_1979_2024.csv` in `data/raw/france_weather/`; pass it with `--weather`). `--spray DD.MM` and `--dose` set the spray day and dose of every year (default 01.03 and 2.4 kg/ha) | about 8 min |
| `python -m runoffwatch design` | Writes run files for NEW simulations (varied spray date, dose, substance) into `data/design/`. Nothing is uploaded; see [docs/NEW_RUNS_PLAN.md](docs/NEW_RUNS_PLAN.md) | about 1 min |

**Step 4. Look at the results.**

| The three project tasks | Where to look |
|---|---|
| **Task 1.** Find the broken simulations | [docs/DATA_REPORT.md](docs/DATA_REPORT.md), numbers in `docs/results/quality_summary.json` |
| **Task 2.** Predict high-loss days and explain them | [docs/MODEL_REPORT.md](docs/MODEL_REPORT.md), sections 3 to 5 |
| **Task 3.** Fast copy of the simulator (emulator) | [docs/MODEL_REPORT.md](docs/MODEL_REPORT.md), sections 1 to 4; try it with Part A, steps 5 and 6 |

Running Part B overwrites the models, figures and result files that came with the repository
(`models/`, `docs/results/`, `docs/figures/`). The reports were written with exactly those files,
so small differences after your own run are normal.

### Part C: the delivered data (how the fault was found)

The same steps work on the simulations as delivered. Put `--dataset delivered` right after
`python -m runoffwatch`, before the command. Do Part B, step 1 first (`extract` always unpacks the
delivered data; no re-run is needed).

```bash
python -m runoffwatch --dataset delivered inventory
```
```bash
python -m runoffwatch --dataset delivered qc
```
```bash
python -m runoffwatch --dataset delivered audit
```
```bash
python -m runoffwatch --dataset delivered features
```
```bash
python -m runoffwatch --dataset delivered train
```
```bash
python -m runoffwatch --dataset delivered train --cv
```

These read `data/raw/runs/` and use `data/interim/` and `data/processed/features.parquet` on the
way. `audit` uses the plausibility rule (the "envelope") that found the broken runs. The results
live in `docs/results/delivered/`, `docs/figures/delivered/` and `models/delivered/`, so they never
overwrite the corrected ones. The extras take the same option, for example
`python -m runoffwatch --dataset delivered whatif` uses the models in `models/delivered/`.

### If something goes wrong

| Message | What to do |
|---|---|
| `No module named runoffwatch` | The environment is not switched on (Part A, step 2), or step 3 was skipped |
| `No .7z or .zip archives in data/raw/archives` | The data files are not in that folder (Part B, step 1) |
| `No run folders ... under data/raw/runs_fixed` | Run `rerun` first (Part B, step 2), or add `--dataset delivered` to work on the delivered data |
| `No run folders ... under data/raw/runs` | Run `extract` first |
| `... runs_qc.csv` or `run_quality.csv` not found | A step was skipped, or you mixed data sets; run the commands of Part B, step 3 in order, all with or all without `--dataset delivered` |
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
| `tests/` | 522 tests on synthetic run folders (no project data in git) |
| `runoffwatch/pipeline.py`, `plots.py`, `przm_spikes.py`, `examples/` | Earlier exploration code, kept for reference |

Code and documents were written with the help of an AI assistant (Claude).
