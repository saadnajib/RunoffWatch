# RunoffWatch – full project handoff

Paste this whole file into a new chat with an AI assistant so it knows the
project. It is written to be read without any other context. State as of
17 November 2026.

**How to use this with an assistant:** it cannot see the code or the data, only
this text. When you ask for code changes, paste the relevant file from the
repository as well. Numbers below marked "measured" come from running the code
on the full data; do not let an assistant change them from memory.

---

## 1. Who and what

| | |
|---|---|
| Project name | RunoffWatch |
| Course | ETX8 Landscape-modelling project, RPTU Kaiserslautern-Landau, winter 2026/27 |
| Team | Saad Najib (Computer Science, Kaiserslautern): code, models, evaluation. Sarah (Environmental Science, Landau): model settings, interpretation, contact to the modelling group. A third member left in week 1; the supervisor allows recruiting a replacement. |
| Repository | https://github.com/saadnajib/RunoffWatch (Python package `runoffwatch`) |
| Slides | First pitch: https://claude.ai/artifact/Y82phRAgCapMtktvPri94c · Progress update: https://claude.ai/artifact/VzutykKbE1M1tja2ZrZHcj (both private until shared by the owner) |
| Written with | An AI coding assistant (Claude). Disclose this if asked who wrote the code. |

**One-sentence summary:** we build a fast machine-learning *surrogate* (a
copy) of the PRZM pesticide model that predicts, from daily weather and soil,
how much pesticide is washed off a field after spraying, and a small
"spray-day advisor" that uses it.

---

## 2. Background in plain words

- **The process.** A farmer sprays a pesticide. Later a heavy rain produces
  water running off the soil surface ("runoff"). That water carries pesticide
  off the field.
- **PRZM.** The official EU simulation model for this (FOCUS PRZM, version 3).
  It calculates day by day, for one field, how much water and pesticide leave
  the field. It runs only on Windows, takes a few seconds per 10-year run, and
  is operated by the modelling group in Landau inside a framework called
  xLandscape / xOffFieldSoilRisk.
- **Surrogate / emulator / meta-model.** A machine-learning model trained on
  the simulator's inputs and outputs so that it gives nearly the same answer
  much faster. This is the core of the project. The supervisor said it is what
  makes this project different from the other groups, and the Landau side asked
  for one.
- **Scope decisions made by the supervisors:** focus on the field and its soil
  (not on rivers); daily time steps (as PRZM); the weather source is Agri4Cast.
- **Henry constant.** A pesticide setting that says how easily the substance
  evaporates. It matters for the data problem in section 5.
- **Curve number (CN).** A textbook formula (SCS curve number) that turns
  daily rain into runoff. PRZM uses it internally and adjusts it for soil
  moisture.

---

## 3. History of the project (why things are the way they are)

1. **First idea:** link hourly weather to measured pesticide spikes in rivers.
   Dropped: there are no river measurements, only simulations.
2. **Supervisor in Landau:** focus on runoff from the soil, daily weather,
   Agri4Cast as weather source.
3. **Pitch (4 Nov 2026)** with three machine-learning tasks: (1) find broken
   simulations, (2) predict "high-loss day or not" and explain it, (3) build an
   emulator.
4. **Feedback at the pitch:** the idea resembles the other groups'; the
   surrogate is the differentiator; make it useful for farmers ("spray today
   or tomorrow?", "pesticide A or B?"); check related work and baselines; ask
   Landau whether the odd numbers are a bug.
5. **First full run on the data (12 Nov):** data audit, surrogate, classifier,
   advisor prototype. An independent review found the test was too easy; the
   evaluation was redone by leaving out one year at a time.
6. **Second round (16 Nov):** final models on all years, smaller bias, an LSTM
   as second surrogate, a generator for new simulation runs, new slides.

---

## 4. The data

**Source:** ten `.7z` archives (350 MB) from the Landau project cloud, folder
"results". They are *simulation* results, not measurements. The data is not in
the GitHub repository.

**Measured facts:**

| | |
|---|---|
| Run folders | 9,977 |
| ... with PRZM results | 3,958 readable (+ 8 with an empty result file) |
| ... with inputs but no results | 2,992 |
| ... with only a log file (PRZM never started for that grid cell) | 3,019 |
| Simulated period | 1 Jan 1990 – 31 Dec 1999, daily (3,652 days) |
| Different weather files | 695 (shared by 1 to 77 runs each); they are Agri4Cast/MARS grid cells |

**Files in one run folder:**

| File | Content |
|---|---|
| `focusprzm_weather.met` | Daily weather: rain, pan evaporation, temperature, wind, solar radiation (units cm, cm, °C, cm/s, langley) |
| `*.inp` | PRZM input: field, crop, soil layers, pesticide, application dates |
| `*.ZTS` | Daily results: runoff, eroded soil, rain, infiltration, pesticide lost in runoff, pesticide lost with eroded soil, amount applied |
| `*.OUT` | Long text report with yearly water and pesticide balances |
| `Run 1.run`, `mc.log` | Run definition and log |

**What changes between runs and what does not (measured):**

| Changes | Is the same in every run |
|---|---|
| Weather (695 files) | Pesticide: Flufenacet |
| Slope (0–25 %), soil erodibility, slope-length factor | Dose: 2.4 kg/ha = 2,400 g/ha |
| Curve number (4 sets: 73 / 77 / 81 / 84) | Spray date: 1 March, every year |
| Soil per layer: bulk density, field capacity, wilting point, organic carbon (0.2–39 %), sand, clay | Crop: winter cereals |
| Sorption Kd (only through organic carbon: Kd = 3.775 × OC) | Decay rate (half-life 41.7 days), Henry constant 0.03 |

**Consequence:** a model can learn about weather and soil from this data. It
cannot learn anything about which pesticide, which dose or which spray date.
Also, "days since spraying" and "day of the year" are the same thing in this
data, so their effects cannot be separated.

**Key facts about the losses (measured, trusted data only):**
- A "rain day" is a day with at least 1 mm of rain. About 13 % of rain days
  produce runoff.
- A "high-loss day" is defined as a day with at least 1 g/ha pesticide lost
  (0.04 % of the dose). Such days are 0.17 % of rain days and carry 55 % of all
  pesticide loss. This definition is ours and should be confirmed by Sarah.
- 61 % of the loss happens in March, i.e. in the first weeks after spraying.

---

## 5. The data problem (Task 1)

**What is certain (read directly from the files):**
1. Some runs report impossible pesticide losses, up to 1.8e34 g/ha from a
   2,400 g/ha dose. 263 runs crash before 1999.
2. The yearly "total soil decay of pesticide" grows in almost every run
   (median factor 2.5 per year) although the same dose is applied every year.
3. In all 3,958 readable `.OUT` files the "GAS DIFFUSION" column of the yearly
   pesticide table is `NaN` from 1990 on.
4. The fake pesticide mass starts in the deep soil and in part of the runs
   reaches the surface, where it corrupts the runoff losses.
5. The water side (rain → runoff) is not affected.

**Likely cause (hypothesis, not proven):** the Henry constant 0.03. It is a
high value, the broken numbers are in the gas-diffusion part, and the same
value appears in the template run file for a different pesticide, so it was
probably never chosen for Flufenacet. Runs with little organic carbon in the
subsoil break far more often (68 % clearly broken at 0–0.3 % organic carbon,
0 % above 1 %).

**How we decide what to trust ("envelope rule"), per run and per year:**
- On a runoff day, "pesticide lost per mm of runoff" must fall with the days
  since spraying, because the pesticide decays.
- The upper limit for each "days since spraying" is learned from 1990 (99th
  percentile per 15-day bin, forced to be non-increasing, times 5).
- The first day a run goes above the limit marks its first bad application
  year (application years run 1 March – end of February). The year before is
  dropped too, and the last simulated year is never trusted.

**Results (measured):**

| | |
|---|---|
| Runs broken beyond doubt (50× above the limit or more) | 1,177 of 3,958 (30 %) |
| Runs flagged by the cautious rule (5×) | 1,966; at 10×: 1,648; at 1000×: 825 |
| Trusted pesticide data | 27,730 of 38,100 run-years (73 %) |
| Trusted water data | all 3,958 runs |
| Isolation Forest (unsupervised ML) on per-run summaries | flags 652 runs, finds only 52 % of the clearly broken ones. The physical rule is the better detector. |

**Open questions for the model owner in Landau** (an email is drafted, not
sent; the contact goes through Sarah):
1. Is Henry 0.03 intended for Flufenacet or a template default?
2. May we submit our own runs?
3. Can the spray date be read from the run file? It is currently fixed to
   "03-01" in the model configuration.
4. Why do 2,992 folders have inputs but no results?
5. Can the error about a missing `..._runoff_grd.tif` in nearly every
   `mc.log` be ignored?

---

## 6. The models (Tasks 2 and 3)

### 6.1 Feature table
One row per rain day per run: 5.67 million rows, 4.19 million of them with
trusted pesticide results. All inputs come from weather, spray history and
soil; nothing from PRZM's output.

- **Weather inputs:** rain today, yesterday, 2–3 days ago, in the previous 7 /
  14 / 30 days; temperature today, yesterday, mean of previous 7 days;
  evaporation today and previous 7 days; a snow proxy (precipitation on
  freezing days in the last 30 days); the curve number in force today; the
  textbook curve-number runoff for today's rain.
- **History since spraying:** days since spraying, rain since spraying, number
  of heavy-rain days since spraying, mean temperature since spraying, rain in
  the first 3 days after spraying.
- **Soil / field:** erodibility, slope-length factor, slope, curve number,
  topsoil bulk density, field capacity, wilting point, organic carbon, Kd,
  sand, clay; subsoil bulk density and organic carbon.
- **Deliberately no calendar input** (day of year, month): see 6.3.

### 6.2 The surrogate: two stages
```
runoff model          weather + soil                 -> mm of water running off
concentration model   history since spraying + soil  -> g/ha of pesticide per mm of runoff
pesticide loss = runoff x concentration
```
- Both are gradient-boosted trees (LightGBM), small trees on purpose.
- Runoff model: Tweedie objective; trained on all runs. It is
  "physics-informed": the textbook curve-number runoff is an input, so the
  model only learns PRZM's soil-moisture correction.
- Concentration model: trained only on trusted run-years, on the amount itself
  (Tweedie objective, each day weighted by its runoff). An earlier version was
  trained on the logarithm and underestimated large losses.
- A separate **high-loss classifier** (LightGBM, yes/no) exists for comparison
  and for the driver ranking (SHAP values).
- **Baselines:** curve-number formula alone (runoff); "decay formula ×
  curve-number runoff" (pesticide loss); "rain today" and logistic regression
  (high-loss days).

### 6.3 The evaluation, and the mistake that shaped it
- First test: hold out 20 % of the weather files. Scores were near-perfect.
- Check: for 97 % of the test weather files a training file exists with daily
  rain more than 90 % correlated. The files are neighbouring grid cells of the
  same decade with the same storms on the same days. The test was too easy.
- On truly unseen years, the first runoff model (with calendar inputs and
  large trees) scored R² 0.90, *below* the plain formula (0.93). It had
  memorised storms by their date.
- Fix: remove calendar inputs, give the model the formula as an input, use
  small trees, and test by **leaving out one application year at a time**
  (1990–1998), always on weather files never used in training.
- Lesson: millions of rows, but only ten years of regional weather. All 1,619
  high-loss days in the test data fall on 86 dates.
- Three sets of models are trained: per held-out year (the honest score), one
  without 1992/1994/1996 (figures), and the final set on all years and files
  (saved in `models/`, used by the advisor; cannot be tested itself).

### 6.4 Results (measured; nine held-out years pooled, range over the years in brackets)

| | Surrogate | Baseline |
|---|---|---|
| Water runoff, daily R² | 0.97 (0.92–0.99) | 0.92 (0.83–0.97), curve-number formula; beaten in all 9 years |
| Pesticide loss, daily R² | 0.91 (0.75–0.97) | 0.49 (0.24–0.63) |
| Sum of all loss, surrogate / PRZM | 0.92 (0.70–1.16) | – |
| High-loss days, PR-AUC | 0.92 (0.79–0.98) | rain today 0.06; classifier 0.81 (0.50–0.99) |
| Alarm "predicted loss ≥ 1 g/ha" | 1,341 alarms, 91 % real, 76 % of high-loss days found (36–92 % by year) | – |
| Speed | about 0.01 s per 10-year run | PRZM: 2–4 s |

Reading:
- Runoff is reproduced almost perfectly.
- Pesticide loss is harder and depends on the year, because a year's score is
  decided by a handful of storms.
- Total loss is underestimated by about 8 % (30 % in the worst year, 1991).
  Before the change to amount-based training it was 15 % and R² was 0.87.
- An alarm can be trusted; no alarm does not mean no risk.

**Risk table (trusted simulation results):** chance that a rain day is a
high-loss day. First week after spraying: 22 % at 10–20 mm rain, 93 % at
20–30 mm, 100 % at 30–50 mm. Weeks 5–8: 13 % at 20–30 mm. Later: almost 0.

**Drivers (SHAP on the classifier, test years 1992 and 1996):** curve-number
runoff of today's rain, temperature yesterday, days since spraying, rain
today, evaporation in the previous week. SHAP shows what the model uses, and
the model copies PRZM; "temperature yesterday" still needs an environmental
explanation.

### 6.5 Second surrogate: LSTM
- A small LSTM (24,000 parameters, PyTorch, about 12 minutes on a laptop CPU).
  One sample = one run × one application year: 59 warm-up days plus 366 days.
  Inputs per day: rain, temperature, evaporation, curve number, curve-number
  runoff, days since spraying, plus the soil settings. Outputs per day: runoff
  and pesticide loss.
- Compared with the trees on identical rows (test weather files, years 1992
  and 1996; 278,370 rain days, 288 high-loss days):

| | Trees | LSTM |
|---|---|---|
| Runoff, daily R² | 0.98 | 0.98 |
| Pesticide loss, daily R² | 0.93 | 0.94 |
| Pesticide loss, R² of the logarithm (small losses) | 0.85 | 0.68 |
| Sum of loss, surrogate / PRZM | 0.89 | 1.05 |
| High-loss days, PR-AUC | 0.91 | 0.97 |
| High-loss days found by the alarm | 78 % | 90 % |

- **Caution:** one test on two years, one random seed. Stopped after 25 epochs
  instead of 44 the same LSTM scored only 0.79. It has not had the nine-year
  test (about two hours). The advisor still uses the trees.

---

## 7. The spray-day advisor (Task 4, prototype)

- `python -m runoffwatch whatif` (command line) and `streamlit run app.py`.
- Input: a daily weather table (`date, rain_mm, temp_c`, optional
  `pan_evap_mm`; about 30 days of history plus the forecast) and a soil.
- Output: for each candidate spray day, the predicted pesticide loss in the
  following 14 days, and the number of predicted high-loss days. Only
  candidates with a full window are ranked.
- **Limits:** valid only for Flufenacet, 2,400 g/ha, winter cereals, sprayed
  in late winter / early spring. Moving the spray day is itself an
  extrapolation. It cannot compare products or doses. It has not been
  evaluated as a decision tool.

---

## 8. New simulation runs (prepared, NOT submitted)

- Each PRZM run is defined by a small XML file (`.xrun`) with about 30
  settings. Batches of about 1,000 are submitted as a 7z archive together with
  weather CSVs; a Windows workstation in Landau runs them.
- `python -m runoffwatch design` writes such an experiment to disk:
  - **Main group (default 2,000 runs):** spray date (26 dates, every 14 days),
    dose (600 / 1,200 / 2,400 g/ha), half-life DT50 (10 / 30 / 41.68 / 90 /
    180 days), sorption Koc (30 / 100 / 377.5 / 1,000 / 3,000), soil copied
    from an existing run, one of 40 weather files; each drawn at random and
    independently.
  - **Control group (default 200 runs):** existing runs repeated with only the
    Henry constant changed (half from broken runs, half from sound ones). This
    tests the Henry hypothesis.
- **Before submitting:** permission from the model owner; the spray date must
  be read from the run file on their side; the Henry value (default 2.4e-7) is
  an estimate to confirm; our weather CSVs are rebuilt from PRZM weather files
  and may differ from the originals.
- With such runs, dose, DT50 and Koc become model inputs and the advisor could
  compare days, doses and substances.

---

## 9. Other things known about the Landau side

- The project cloud also holds a folder from the previous year's group
  ("Meta-Modelling"): technical documentation of the run pipeline, a parameter
  plan, plots, and `france_weather_1979_2024.csv` (907 MB, Agri4Cast weather
  for France). Resharing of that folder is switched off by its owner, so
  permission should be asked before copying files out of it.
- That earlier group set up the run pipeline and planned parameter variations;
  it did not build a surrogate.
- A Python port of the US model PRZM5 exists in the course material. It is a
  different model version and cannot read these runs.

---

## 10. The code

Install and try (no data needed, trained models are in the repository):
```bash
git clone https://github.com/saadnajib/RunoffWatch.git
cd RunoffWatch
python -m venv .venv
.venv\Scripts\activate          # Windows; on Mac/Linux: source .venv/bin/activate
pip install -e ".[dev,app]"
python -m pytest -q             # 199 passed, 1 skipped (203 with PyTorch)
python -m runoffwatch whatif
streamlit run app.py
```

Full pipeline from the raw data (put the ten archives in `data/raw/archives/`):

| # | Command | What it does | Time |
|---|---|---|---|
| 1 | `python -m runoffwatch extract` | Unpacks the archives | 1 min |
| 2 | `python -m runoffwatch inventory` | Finds what differs between runs | 5 s |
| 3 | `python -m runoffwatch qc` | Reads and checks every run | 1 min |
| 4 | `python -m runoffwatch audit` | Task 1: which results are trusted | 30 s |
| 5 | `python -m runoffwatch features` | Builds the feature table | 2 min |
| 6 | `python -m runoffwatch train` | Trains surrogate and classifier, saves final models | 3 min |
| 7 | `python -m runoffwatch train --cv` | Leave-one-year-out evaluation | 25–30 min |
| – | `python -m runoffwatch lstm` (needs `pip install -e ".[lstm]"`) | LSTM vs trees | 12–20 min |
| – | `python -m runoffwatch design` | Run files for new simulations | 1 min |

Modules (`runoffwatch/`):

| File | Purpose |
|---|---|
| `przm_io.py` | Reads `.met`, `.ZTS`, `.OUT`, `mc.log`; converts units; sanity checks |
| `przm_inp.py` | Reads field / soil / pesticide settings from `.inp` |
| `batch.py` | Unpack, inventory, quality-check all runs in parallel |
| `quality.py` | Envelope rule, Isolation Forest, causes of the breakdown |
| `features.py` | Feature table; `weather_features` is shared by training and the advisor |
| `models.py` | Surrogate, classifier, baselines, split, leave-one-year-out evaluation |
| `lstm.py` | LSTM surrogate and comparison |
| `whatif.py`, `../app.py` | Advisor library, command line, Streamlit app |
| `design.py` | Generator for new simulation runs |
| `figures.py`, `report.py` | Figures; single-run report |
| `pipeline.py`, `plots.py`, `przm_spikes.py`, `examples/` | Earlier exploration code |

Other folders: `models/` (trained LightGBM models, about 2 MB), `docs/`
(reports, figures, result tables), `tests/` (synthetic run folders only),
`data/` (local, never committed).

Reports in `docs/`: `DATA_REPORT.md`, `MODEL_REPORT.md`, `RELATED_WORK.md`,
`PROJECT_SCOPE.md`, `ROADMAP.md`, `NEW_RUNS_PLAN.md`.

---

## 11. Related work (short; details and sources in `docs/RELATED_WORK.md`)

- Farmer tools that forecast runoff risk exist, for example the Runoff Risk
  Advisory Forecast in Wisconsin and other US states, and a Danish tool based
  on simulations plus machine learning. No German tool for pesticide runoff
  risk was found.
- Surrogates ("metamodels") of pesticide and hydrology models exist (for
  PEARL, MACRO, SWAT, mostly neural networks / LSTMs). No published
  machine-learning surrogate of PRZM was found.
- The review was compiled from search results and abstracts. Entries marked
  "[not verified]" must be checked before citing.

---

## 12. Limits to state openly

1. The surrogate copies a model. Nothing was compared with measurements.
2. One pesticide, one dose, one crop, one spray date.
3. Field edge only; daily resolution.
4. About 27 % of the pesticide run-years are unusable because of the simulator
   problem; some slight contamination may remain in the kept data.
5. Large losses are underestimated (8 % overall, more in years with extreme
   storms); a quarter of the high-loss days are missed.
6. Small effective sample: ten years of weather from one region.
7. The LSTM result rests on one test.

---

## 13. Status and next steps

Done: data audit; surrogate with honest evaluation; classifier, SHAP ranking,
risk table; advisor prototype; LSTM comparison; generator for new runs;
related-work review; reports; two slide decks.

Open, in order of value:
1. Send the questions to the model owner (through Sarah).
2. Year-by-year test for the LSTM; if its lead holds, make it the main
   surrogate.
3. If permitted: submit the control group and the new runs; retrain with
   dose, DT50 and Koc as inputs.
4. If permitted: run the surrogate on the 1979–2024 France weather.
5. Sarah: confirm the high-loss definition; check whether the driver ranking
   makes physical sense; review flagged runs by eye.
6. Verify the related-work entries; write the report; final slides.
7. Unknown: the course deadline.

---

## 14. Glossary

| Term | Meaning |
|---|---|
| Runoff | Water flowing off the soil surface after rain |
| Pesticide loss | Pesticide leaving the field with runoff water, in g/ha per day |
| Rain day | Day with at least 1 mm rain |
| High-loss day | Day with at least 1 g/ha pesticide loss |
| Application year | 1 March to end of February (spraying is on 1 March) |
| Run | One PRZM simulation: one field, ten years |
| Surrogate / emulator | ML model that imitates the simulator |
| R² | 1 = perfect copy, 0 = no better than predicting the average |
| PR-AUC | Quality of ranking rare events, 0 to 1; guessing gives about 0.002 here |
| Precision / recall | Share of alarms that are real / share of real events found |
| Leave-one-year-out | Train without one year, test on it, repeat for every year |
| SHAP | Method that shows how much each input pushed a prediction |
| LSTM | Neural network that reads a sequence step by step and keeps a memory |
| DT50 | Half-life of the pesticide in soil, in days |
| Koc / Kd | How strongly the pesticide sticks to soil (Kd = Koc × organic carbon) |
| Agri4Cast / MARS | EU daily weather grid (25 km cells) from the Joint Research Centre |
