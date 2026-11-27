# RunoffWatch – full project handoff

Paste this whole file into a new chat with an AI assistant so it knows the
project. It is written to be read without any other context. State as of
27 November 2026 (first written 17 November 2026).

**How to use this with an assistant:** it cannot see the code or the data, only
this text. When you ask for code changes, paste the relevant file from the
repository as well. Numbers below marked "measured" come from running the code
on the full data; do not let an assistant change them from memory.

> **State on 26 Nov 2026 (dose check added 27 Nov): the high-loss limit is
> now a share of the dose, the app is simpler, 1991 is explained, the models
> are frozen.** No model
> was retrained; the new
> scores in 6.10 come from the saved held-out predictions of the
> year-by-year test.
> - **High-loss limit as a share of the dose** (section 6.10). A fixed limit
>   of 1 g/ha cannot hold across compounds. The app now counts a day as a
>   high-loss day when the field loses at least a chosen share of the dose.
>   It starts with 0.1 % (our own round number, not an official limit); the
>   user can choose 0.01 to 0.5 %. At 0.1 % on the varied data: 15,798
>   high-loss days, 91.6 % of alarms right, 91.9 % of high-loss days found,
>   and the same scores for every dose.
> - **Still on the fixed limit of 1 g/ha:** the classifier, the alarm
>   columns of the year-by-year tables, two figures and the high-loss-day
>   counts of the 45-year runs (6.10).
> - **Why 1991 is the weakest year of the 1-March-only models** (6.11): it
>   is the only year with heavy runoff on the spray day itself. A limit of
>   data with one fixed spray date, not a fault of the method.
> - **Loss is proportional to the dose** in PRZM's results (6.10).
> - **The app was redesigned** (7.1): five tabs, each answers one question
>   and names the project task it belongs to.
> - **Windows fix:** the app failed at start on Windows because of Windows
>   line ends in the model files. Fixed; `git pull` is enough (section 10).
> - **Dose box limited to the trained range** (7.1). The dose box in the app
>   now only takes doses the loaded models were trained on: 0.24 to 2.4 kg/ha
>   for the varied models. Before, it took 0.05 to 5.0 kg/ha and only warned.
> - **Honesty about the test** (6.3, limit 15 in section 12): there is no
>   untouched final test set, so the scores may be slightly optimistic.
> - **Models frozen** (6.12). `models/FROZEN.json` holds a fingerprint of
>   every saved model file in `models/`, `models/varied/` and
>   `models/delivered/`. `train` refuses to overwrite a frozen folder. A
>   later test on new runs is honest only if the models could not be
>   adjusted after seeing those runs.
> - **New command `check` and test-only data set `dosecheck`** (6.12,
>   section 10). `check` scores the frozen models on runs they were not
>   trained on. It trains nothing.
> - **The 0.6 kg/ha dose check was run on 27 Nov and passed** (6.12, 8.3):
>   runoff R² 0.988, pesticide loss R² 0.980 on 500 runs with a dose the
>   models never saw. It tests the dose only: fields and weather were known.
> - 594 tests pass (before: 576).
>
> *25 Nov 2026, late evening (kept for context):*
>
> **State on 25 Nov 2026, late evening: cause of the weak year 1990 found,
> warm-up rule added, rerun with the rule finished. All scores in this file
> are new, except where marked "before the warm-up rule".**
> - **Why 1990 was weak.** The first simulated year is a warm-up period. In
>   the PRZM input file the first crop cycle starts before the simulation
>   (emergence 12 Nov 1989; the simulation starts 1 Jan 1990). Until the
>   first emergence inside the simulation (12 Nov 1990) the crop state is
>   not the regular one. A spray in that time lands on the crop canopy in a
>   very different share, and runoff in Aug–Oct 1990 is lower than in other
>   years. So 1990 was not a fair test, and its rows also disturbed
>   training. This holds for all three data sets (section 6.9).
> - **New warm-up rule in the code** (section 5.2): rain days before
>   12 Nov 1990 are left out, and so are pesticide results of sprayings made
>   before that day. Application year 1990 then drops out of the
>   year-by-year test, which now has nine held-out years (1991–1999). 567
>   tests pass.
> - **Rerun finished** (25 Nov, late evening): feature table, training,
>   year-by-year test and 45-year run for 1 March and for 15 October on the
>   varied data set; the same steps (without the autumn run) on the corrected
>   1-March-only data set. The new scores are in the table below and in
>   sections 6.4 to 6.8. Not rerun: the delivered data (archived) and the
>   LSTM (6.5).
> - **What the rule changed:** on the varied data daily loss R² rose from
>   0.917 to 0.965, and autumn spraying from 0.90 to 0.962. 1998 rose from
>   0.883 to 0.966, because part of its old weakness came from the warm-up
>   rows (6.9).
> - **New 45-year run with spraying on 15 October:** autumn spraying loses
>   about 4 to 6 times more than 1 March spraying in the same weather, and
>   the worst years are different years (6.6).
> - **The 1 g/ha limit for a high-loss day will change:** the
>   environmental-science side answered that a fixed g/ha limit cannot hold
>   across compounds. Planned: a share of the dose, adjustable (section 13).
>   Done on 26 Nov (6.10). The alarm scores in the table below use the
>   fixed limit of 1 g/ha.
> - **The app was rewritten** with five tabs (7.1).
> - **Tried and rejected:** training the runoff model as a correction of the
>   curve-number formula (section 6.9). Keep the current model.
>
> *Earlier on 25 Nov 2026: other spray dates and doses are analysed.* The
> full run with varied spray dates and doses finished on the owner's PC
> (11,218 simulations; 11,209 usable, section 8.1). Every field got one
> spring copy (15 Feb to 30 Apr) and one autumn copy (1 Oct to 30 Nov), with
> 0.24, 1.20 or 2.40 kg/ha. All analysis steps ran on it; results are in
> `models/varied/`, `docs/results/varied/` and `docs/figures/varied/`
> (section 6.7). Year-by-year test with the warm-up rule (each of nine years,
> 1991–1999, held out once; the delivered column is the archived result from
> before the rule, nine years 1990–1998):
>
> | Score | Delivered (before the warm-up rule) | Corrected, 1 March only | Varied dates and doses |
> |---|---|---|---|
> | Runoff R² (range over years) | 0.97 | 0.986 (0.954–0.993) | 0.986 (0.954–0.993) |
> | Loss R² (range) | 0.91 (0.75–0.97) | 0.948 (0.867–0.986) | 0.965 (0.907–0.976) |
> | Total loss, predicted / true (range) | 0.92 (0.70–1.16) | 0.948 (0.831–1.086) | 0.985 (0.950–1.082) |
> | PR-AUC surrogate / classifier / rain rule | 0.92 / 0.81 / 0.06 | 0.965 / 0.954 / 0.108 | 0.973 / 0.975 / 0.106 |
> | Alarm precision / recall (recall range) | 91 % / 76 % (36–92 %) | 91.7 % / 88.0 % (80.1–97.7 %) | 92.6 % / 92.6 % (89.3–95.6 %) |
>
> The task with varied spray dates and doses is harder, yet with the rule it
> scores at least as well as the 1 March data: daily loss R² 0.965 against
> 0.948. Before the rule (ten years with 1990) the varied loss R² was 0.917
> (0.78–0.97). The weakest years are now 1993 on the varied data (loss R²
> 0.907) and 1991 on the 1 March data (0.867). **Spray-date finding
> (straight from PRZM):** autumn spraying loses about 2 to 8 times more of
> the dose than spring spraying (6.8). The cause is the
> crop calendar of the PRZM scenario: until the fixed emergence date (12 Nov)
> the field counts as stubble or fallow, with a high curve number, so far more rain runs
> off. The chemistry is the same in every window; so the step in mid-November
> is a scenario setting, not a law of nature (section 6.8). Next steps:
> section 13.
>
> *History (kept for context):*
>
> **What changed on 23 Nov 2026.** We ran the PRZM program (`WINPRZM.exe`) on
> the owner's own Windows PC (30 small test runs). It reproduces the delivered
> numbers exactly, and it showed that **two input settings in the delivered
> simulations are wrong**: the Henry constant (0.03, about 100,000 times too
> high for Flufenacet) and the reference soil moisture (100 where this program
> expects 1). Because of this, the delivered pesticide results were wrong in
> *all* runs, also in the ones that pass our plausibility check. **The results
> are now redone:** all fields were re-run locally with both settings
> corrected (5,609 fields with a full ten-year result), and all models were
> retrained and retested on the corrected data the same day. Section 6 shows
> the corrected numbers; the old ones are kept in `docs/results/delivered/`.
> The water results (rain, runoff) and the methods did not change. Details:
> section 5.
>
> **Also new on 23 Nov 2026: other spray dates and doses.** Until then every
> simulation was sprayed on 1 March with 2.4 kg/ha, so nothing could be said
> about another spray day or dose. The re-run tool can now make copies of
> every field with varied spray dates (spring and autumn) and three doses
> (section 8.1), and the feature table, the tree models and the advisor were
> adapted to use them (section 6.7). A trial of 20 runs worked. The full run
> (11,218 simulations) was started on the owner's PC on 23 Nov; it finished
> and was analysed on 25 Nov (box above).

---

## 1. Who and what

| | |
|---|---|
| Project name | RunoffWatch |
| Course | ETX8 Landscape-modelling project, RPTU Kaiserslautern-Landau, winter 2026/27 |
| Team | Saad Najib (Computer Science, Kaiserslautern): code, models, evaluation. Sarah (Environmental Science, Landau): model settings, interpretation, contact to the modelling group. A third member left in week 1; the supervisor allows recruiting a replacement. |
| Repository | https://github.com/saadnajib/RunoffWatch (Python package `runoffwatch`) |
| Slides | First pitch: https://claude.ai/artifact/Y82phRAgCapMtktvPri94c · Full progress update: https://claude.ai/artifact/VzutykKbE1M1tja2ZrZHcj · First progress presentation (13 slides, by task): https://claude.ai/artifact/QgnfhTxpd8avuscgakiGwz (all private until shared by the owner) |
| Written with | An AI coding assistant. Disclose this if asked who wrote the code. |

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
  xLandscape / xOffFieldSoilRisk. Since 23 Nov 2026 we can also run it
  ourselves on an ordinary Windows PC (section 8).
- **Surrogate / emulator / meta-model.** A machine-learning model trained on
  the simulator's inputs and outputs so that it gives nearly the same answer
  much faster. This is the core of the project. The supervisor said it is what
  makes this project different from the other groups, and the Landau side asked
  for one.
- **Scope decisions made by the supervisors:** focus on the field and its soil
  (not on rivers); daily time steps (as PRZM); the weather source is Agri4Cast.
- **Henry constant.** A pesticide setting that says how easily the substance
  evaporates from soil water into the air. The delivered value (0.03) is far
  too high and is one of the two causes of the data problem in section 5.
- **Reference soil moisture.** A setting of the decay calculation: in dry soil
  the pesticide decays more slowly, measured against this reference moisture.
  The delivered value (100) is the second cause (section 5).
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
7. **Surrogate on 45 years of real weather (17 Nov):** origin of the data
   corrected (real fields in France).
8. **Ran PRZM locally (23 Nov):** the program from the project cloud runs on
   the owner's Windows PC. 30 test runs found the two wrong settings (Henry
   constant and reference soil moisture). A `rerun` command was written to
   redo all simulations with corrected settings.
9. **Corrected data (23 Nov):** all folders with inputs re-run, quality
   check, retraining and both evaluations redone, reports rewritten with the
   corrected numbers.
10. **Varied spray dates and doses (23–25 Nov):** two extra copies of every
    corrected field were simulated on the owner's PC (11,218 runs) and
    analysed. The spray-date effect was traced to the crop calendar of the
    PRZM scenario (section 6.8).
11. **Warm-up year (25 Nov, evening):** the weak test year 1990 was traced
    to a warm-up period at the start of every run (the first crop cycle
    starts before the simulation). A warm-up rule now leaves that period
    out; a full rerun of training and tests was run the same evening and
    has finished (section 6.9). The app was rewritten (7.1).
12. **Share of the dose (26 Nov):** the high-loss limit in the app and in
    the alarm scores became a share of the dose, adjustable (6.10). The weak
    year 1991 of the 1-March-only models was explained (6.11). The app was
    redesigned (7.1), and a start failure on Windows was fixed (section 10).

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
| Simulated period | labelled 1 Jan 1990 – 31 Dec 1999, daily (3,652 days); the weather is really 2006–2015 (labels are 16 years off; exact match checked) |
| Different weather files | 695 (shared by 1 to 77 runs each); they are Agri4Cast/MARS grid cells |

**Files in one run folder:**

| File | Content |
|---|---|
| `focusprzm_weather.met` | Daily weather: rain, pan evaporation, temperature, wind, solar radiation (units cm, cm, °C, cm/s, langley) |
| `*.inp` | PRZM input: field, crop, soil layers, pesticide, application dates |
| `*.ZTS` | Daily results: runoff, eroded soil, rain, infiltration, pesticide lost in runoff, pesticide lost with eroded soil, amount applied |
| `*.OUT` | Long text report with yearly water and pesticide balances |
| `Run 1.run`, `mc.log` | Run definition and log |

**Where the runs come from (from the project cloud folder, 17 Nov 2026):** each run is a real
field in France: a random sample of 9,977 real pesticide applications. Soil comes from the
European soil database at the field, slope from an elevation map, weather from the field's
Agri4Cast grid cell (the number after `grid_` in the run name). The sample also lists the real
substances and doses applied to each field (215 substances), but the runs do not use them. The
cloud folder also contains the PRZM program itself (`WINPRZM.exe`) for this year's students, the
Agri4Cast table for France 1979–2024, and the working folders of 936 failed runs (all stopped in
the first simulated month).

**What changes between runs and what does not (measured):**

| Changes | Is the same in every run |
|---|---|
| Weather (695 files) | Pesticide: Flufenacet |
| Slope (0–25 %), soil erodibility, slope-length factor | Dose: 2.4 kg/ha = 2,400 g/ha |
| Curve number (4 sets: 73 / 77 / 81 / 84) | Spray date: 1 March, every year |
| Soil per layer: bulk density, field capacity, wilting point, organic carbon (0.2–39 %), sand, clay | Crop: winter cereals |
| Sorption Kd (only through organic carbon: Kd = 3.775 × OC) | Decay rate (half-life 41.7 days), Henry constant 0.03, reference soil moisture 100 (the last two are wrong, section 5.1) |

**Consequence:** a model can learn about weather and soil from this data. It
cannot learn anything about which pesticide, which dose or which spray date.
Also, "days since spraying" and "day of the year" are the same thing in this
data, so their effects cannot be separated. (The varied data set below fixes
this for spray date and dose, not for the pesticide.)

**Crop calendar (same in every field and year):** winter cereals, emergence
12 Nov, maturity 10 Jun, harvest 31 Jul. PRZM's curve number follows this
calendar. Most common set: 81 from 12 Nov, 86 from 31 Jul, 91 from 1 Nov to
11 Nov. This matters for the spray-date result (section 6.8).

**Crop cycles and how the spray reaches the soil (found 25 Nov, evening):**
- The `.inp` file lists the crop cycles (emergence, maturity, harvest). The
  **first cycle starts before the simulation**: emergence 12 Nov 1989, while
  the simulation starts 1 Jan 1990. Until the first emergence inside the
  simulation (12 Nov 1990) the crop state is not the regular one. So the
  first simulated year is a **warm-up period** with an irregular crop
  (section 6.9). All three data sets share the same crop lines.
- The **application method is "2" (foliar)**: part of the dose is
  intercepted by the crop canopy, in proportion to the canopy cover. The
  canopy grows linearly from emergence (12 Nov) to 90 % at maturity
  (10 Jun). So a 1 March spray lands 47 % on the crop. PRZM reports this
  share in the "FOLIAR APPLICATION" line of the yearly balance in the `.OUT`
  file.
- Pesticide on the canopy decays there (foliar decay rate 0.07 per day,
  half-life about 10 days) and is washed to the soil by rain.
- The surrogate has no canopy input. In years 2–10 the canopy share is fixed
  by the spray date, so the spray-date input carries it. In the warm-up year
  it is not (section 6.9).

**After the corrected re-run (23 Nov):** 5,609 fields have a full ten-year
result (on 740 weather files); 1,335 fields stop with a PRZM calculation error
and are missing; 13 input files are damaged.

**The varied data set (25 Nov):** each of the 5,609 corrected fields got two
more runs (one spring, one autumn spray window, a different random day in
each year, dose 0.24, 1.20 or 2.40 kg/ha; section 8.1). 11,218 runs arrived;
11,209 are readable with all ten years and all pass PRZM's balance check
(largest error 9.3e-7 kg/ha). 9 runs (5 fields, one batch) are unreadable
and left out.

The feature table holds the 5,609 corrected 1 March runs plus the 11,209
varied runs: 16,818 runs. With the warm-up rule it has 22,580,508 rain days
(`final_models` in `docs/results/varied/model_metrics.json`); before the rule
it had 24,589,483, because rain days before 12 Nov 1990 are now dropped. The
corrected data set alone has 7,530,883 rain days (6.1). Not refreshed (no
result file gives them): 23,654,303 rain days with trusted pesticide values
and 92,768 high-loss days (before the warm-up rule).

**Key facts about the losses (measured on the corrected simulations):**
- A "rain day" is a day with at least 1 mm of rain. About 13 % of rain days
  produce runoff.
- A "high-loss day" is defined as a day with at least 1 g/ha pesticide lost
  (0.04 % of the dose). With the warm-up rule such days are 0.30 % of the
  rain days in the monthly table `docs/results/risk_calendar_month.csv`
  (21,882 of 7,230,741; before the rule 0.32 %, 25,940 days; on the
  delivered data 0.17 %). This definition is ours. The environmental-science
  side answered that a fixed g/ha limit cannot hold across compounds. Since
  26 Nov the app uses a share of the dose instead (start value 0.1 %,
  adjustable); see 6.10. The numbers in this bullet use the fixed limit of
  1 g/ha.
- 52 % of the loss happens in March, i.e. in the first weeks after spraying,
  and 27 % in April (before the rule 58 % and 23 %; delivered data: 61 % in
  March).

---

## 5. The data problem (Task 1)

This section first tells how the problem was found (17 Nov state, kept as
history), then what the local test runs of 23 Nov showed (section 5.1).

**What is certain (read directly from the files):**
1. Some runs report impossible pesticide losses, up to 1.8e34 g/ha from a
   2,400 g/ha dose. 263 runs crash before 1999.
2. The yearly "total soil decay of pesticide" grows in almost every run
   (median factor 2.5 per year) although the same dose is applied every year.
3. In all 3,958 readable `.OUT` files the "GAS DIFFUSION" column of the yearly
   pesticide table is `NaN` from 1990 on. (Now known: this is only a printing
   problem in that column, not the fault; see 5.1.)
4. The fake pesticide mass starts in the deep soil and in part of the runs
   reaches the surface, where it corrupts the runoff losses.
5. The water side (rain → runoff) is not affected.

**Likely cause, as we saw it on 17 Nov (now confirmed by test runs, see
5.1):** the Henry constant 0.03. It is a
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

**Results (measured on the delivered data):** the rule finds the runs where
the numbers explode. Since 23 Nov we know that the runs it keeps are wrong too
(5.1), so "trusted" below means "plausible-looking", not "correct".

| | |
|---|---|
| Runs broken beyond doubt (50× above the limit or more) | 1,177 of 3,958 (30 %) |
| Runs flagged by the cautious rule (5×) | 1,966; at 10×: 1,648; at 1000×: 825 |
| Trusted pesticide data | 27,730 of 38,100 run-years (73 %) |
| Trusted water data | all 3,958 runs |
| Isolation Forest (unsupervised ML) on per-run summaries | flags 652 runs, finds only 52 % of the clearly broken ones. The physical rule is the better detector. |

**On the corrected data** the trust rule is PRZM's own balance check (a run is
used when its yearly balance error stays below 0.001 kg/ha; `audit --trust
balance`). All 5,609 full runs pass. The old plausibility rule would still flag
387 runs, but these are not faults (DATA_REPORT.md, section 6). Since
25 Nov (evening) the balance rule also sets a warm-up end per run (5.2).

### 5.2 Warm-up rule (added 25 Nov 2026, evening)

Why: the first simulated year is a warm-up period with an irregular crop
(section 4, crop cycles; evidence in 6.9). Its rows are not a fair test and
disturb training.

How it works in the code (merged on the branch; 567 tests passed then, 576
on 26 Nov):
- `przm_io.read_crop_emergences(inp)` reads the emergence dates of the crop
  cycles from the `.inp` file.
- `quality.warm_up_end(emergences, first_day)` gives the end of the warm-up:
  the first emergence inside the simulation.
- `build_run_quality` (the `audit` command) writes it as column `clean_from`
  into `run_quality.csv`. This happens only with trust rule `balance`. With
  `envelope` (the archived delivered-data analysis) the column stays empty.
- `quality_summary.json` has `runs_with_warm_up` and `warm_up_until`. For all
  5,609 corrected runs and all 11,209 varied runs the warm-up lasts until
  1990-11-12.
- `features.run_feature_rows(..., clean_from)`: rain days before
  `clean_from` are dropped from the feature table. Pesticide results of
  sprayings made before `clean_from` are not trusted (`pest_clean` False)
  for their whole season.
- `longrun.run_france`: the comparison with PRZM leaves out field-years that
  start before `clean_from`.
- Effect on the year-by-year test: application year 1990 has too few trusted
  rows left and drops out. The test now has nine held-out years
  (1991–1999).
- **Not adapted:** `lstm.py` still uses the warm-up period.

To use it on a data set: run `audit` again (it writes `clean_from`), then
`features`, `train`, `train --cv` and `france` (section 10). Older
`run_quality.csv` files without the column mean "no warm-up anywhere".

### 5.1 Local re-runs: two settings are wrong (23 Nov 2026)

`WINPRZM.exe` from this year's project cloud folder runs on an ordinary
Windows PC in about 3 seconds per field. Two small tests, 30 runs in total, on
six fields from the data set (three clearly broken, one that crashed, two that
pass our check; the two passing ones turned out to have identical inputs) plus
the example run that comes with the program. All numbers are in
`docs/results/local_rerun_tests.csv`; the full account is in
`docs/DATA_REPORT.md`, section 6.

**Test 1, Henry constant (21 runs; ten-year pesticide loss with runoff):**

| Field | Henry 0.03 (as delivered) | Henry 3.7e-7 | Henry 0 |
|---|---|---|---|
| broken 1 | 1.2e15 g/ha | 37 g/ha | 37 g/ha |
| broken 2 | 1.7e9 g/ha | 39 g/ha | 39 g/ha |
| broken 3 | 7.2e10 g/ha | 46 g/ha | 46 g/ha |
| crashed | stops on day 1,344 | all ten years, 174 g/ha | 174 g/ha |
| passes our check | 22 g/ha | 62 g/ha | 62 g/ha |
| program's example | 36 g/ha | 35 g/ha | 35 g/ha |

**Test 2, decay settings (9 runs, Henry already fixed, three fields):**

| Setting changed | Pesticide left in the soil after ten years | Ten-year loss with runoff (field that passes our check) |
|---|---|---|
| none (Henry fixed only) | 9.1 to 13.8 kg/ha | 62 g/ha |
| moisture correction switched off | 0.02 to 1.4 kg/ha | 30 g/ha |
| reference moisture 1 instead of 100 | 0.06 to 1.9 kg/ha | 33 g/ha |
| temperature correction switched off | 6.9 to 12.1 kg/ha | 62 g/ha |

(The higher end of each range is the program's example run, which decays 3.5
times more slowly.)

**What is now known:**
- **The local program gives exactly the delivered numbers** with Henry 0.03,
  including the crash on day 1,344. So the fault is in the inputs, not in the
  Landau workstation.
- **The Henry hypothesis is confirmed.** With a small Henry value every run
  finishes, and PRZM's own pesticide balance error drops from up to 1e19 to
  about 1e-7. A realistic value and zero give the same result. Published
  values for Flufenacet correspond to 2.4e-7 to 5.3e-7 in PRZM's units, so
  0.03 is about 100,000 times too high. The program's example run is labelled
  "Lindane" and uses the same 0.03, which suggests a template value.
- **A second wrong setting: the reference soil moisture.** The input says half
  the pesticide decays in 42 days, yet about four yearly doses are still in
  the soil after ten years. The decay rate is multiplied by
  (moisture / reference moisture)^0.7. The files give the reference as 100
  (meant as 100 % of field capacity), but this program works with moisture as
  a fraction (field capacity = 1). Then decay is 100^0.7 = about 25 times too
  slow. We cannot tell whether the input or the program is at fault; the
  practical fix is the same: reference moisture 1.
- **The runs that pass the plausibility check are affected too.** With Henry
  0.03, 65–80 % of every dose evaporates; with a realistic value almost
  nothing does and the runoff loss is about three times higher. In these runs
  two errors work against each other (too much evaporation, too little decay).
- **The `NaN` values are a printing problem**, not the fault: they stay in the
  "gas diffusion" column after the fix.
- **The water results stay valid.** Rain, runoff and infiltration do not depend
  on these settings (runoff totals are identical in all variants of a field).
- Corrected simulations can be made locally: 6,958 folders have input files
  (3,958 with results, 2,992 that stopped early, 8 with empty results); the
  input editor works on 6,945 of them (13 input files are damaged).

**Open questions for the model owner in Landau** (an email is drafted, not
sent; the contact goes through Sarah; updated 23 Nov; still unanswered on
25 Nov; the four most important are 1, 1b, 7 and 8):
1. Is Henry 0.03 intended for Flufenacet, or is it the template default? Our
   test runs show that it causes the broken numbers and that a realistic value
   removes them.
1b. Is the reference soil moisture of 100 read by this PRZM version as a
   fraction? With 100 the pesticide decays about 25 times too slowly in our
   tests; with 1 it behaves as expected.
2. May we submit our own runs?
3. Can the spray date be read from the run file? It is currently fixed to
   "03-01" in the model configuration.
4. Why do 2,992 runs stop within the first simulated month?
5. Can the error about a missing `..._runoff_grd.tif` in nearly every
   `mc.log` be ignored?
6. Why were the real substances and doses of the sampled fields not used, and
   is the 16-year shift of the weather labels intended?
7. Is 2.4 kg/ha the intended dose? It looks about ten times higher than
   usual field rates (unconfirmed, section 8.1).
8. Where do the zeros in the inputs of the 1,335 failing fields come from,
   and can they be filled?
9. (Added 25 Nov, evening.) The first crop cycle in the input files starts
   before the simulation (emergence 12 Nov 1989, start 1 Jan 1990). Is this
   intended, and is a warm-up year normally discarded (section 6.9)?

**Question to the environmental-science side, answered (25 Nov):** is the
1 g/ha limit for a "high-loss day" sensible? Answer: a fixed g/ha limit
cannot hold across compounds, because doses differ by a factor of 100 or
more. In our runs 1 g/ha is 0.42 %, 0.083 % and 0.042 % of the three doses
(0.24, 1.2 and 2.4 kg/ha). Consequence: the limit will become a share of
the dose and adjustable (section 13). Done on 26 Nov: the app and the alarm
scores now use a share of the dose (6.10). Runoff and loss-amount scores do not
depend on the limit; classifier and alarm scores do. Low-dose compounds (a
few g/ha) are outside the dose range of our runs (0.24–2.4 kg/ha).

---

## 6. The models (Tasks 2 and 3)

The numbers in 6.1 to 6.6 are from the corrected simulations (23 Nov 2026),
which are all sprayed on 1 March with 2.4 kg/ha (results in `docs/results/`,
kept for comparison). The delivered-data numbers are in
`docs/results/delivered/`; the main ones are compared in 6.4. The method was
then changed for varied spray dates and doses (6.7); the results on the
varied data set (25 Nov) are in 6.7 and 6.8 and in `docs/results/varied/`.
**What changed:** all numbers in 6.1 to 6.8 were recomputed with the warm-up
rule (5.2) on 25 Nov, late evening. Exceptions, marked where they appear:
the delivered data and the LSTM (6.5). Section 6.9 explains why the rule was
needed.

### 6.1 Feature table
One row per rain day per run: 7.53 million rows (7,530,883) with the warm-up
rule (8,200,903 before it). Rain days before 12 Nov 1990 are dropped, and
the rest of the 1990 spray season has no trusted pesticide value (5.2).
Delivered data: 5.67 million rows, of which only part was trusted. All inputs come from weather, spray history and soil; nothing from
PRZM's output.

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
  large trees) scored R² 0.90, *below* the plain formula (0.93; delivered
  data, runoff is unchanged in the corrected data). It had memorised storms
  by their date.
- Fix: remove calendar inputs, give the model the formula as an input, use
  small trees, and test by **leaving out one application year at a time**
  (1990–1999 on the corrected data; 1990–1998 on the delivered data, where the
  last year was never trusted), always on weather files never used in training.
  With the warm-up rule (5.2, 25 Nov evening) application year 1990 drops
  out, so the corrected and varied data sets have nine held-out years
  (1991–1999).
- Lesson: millions of rows, but only ten years of regional weather. With the
  warm-up rule all 5,155 high-loss days in the test data (nine years) fall on
  143 dates (before the rule, ten years: 6,066 on 158; delivered data: 1,619
  on 86).
- Three sets of models are trained: per held-out year (the honest score), one
  without 1992/1994/1996 (figures), and the final set on all years and files
  (saved in `models/`, or `models/varied/` for the varied data set, which the
  advisor prefers; cannot be tested itself).

**Which numbers come from which test.** Two evaluations are in the code, and
both are still used:

| Test | Command | Files | Gives |
|---|---|---|---|
| Year-by-year test: every year 1991–1999 is the test year once | `python -m runoffwatch train --cv` | `cv_summary.json`, `cv_by_year.csv`, figure m7 | The headline scores, and everything in the app tab "Is the copy right?" except the speed |
| Single fixed split: test = held-out weather files in the application years 1992 and 1996; year 1994 decides when to stop | `python -m runoffwatch train` | `model_metrics.json`, figures m1 to m6 | The comparison with logistic regression, the SHAP ranking of drivers, the LSTM comparison, the speed, and the "single split" result block (6.7) |

The years 1992 and 1996 of the single split are also test years of the
year-by-year test. So the single split is not an independent second test.

**Honesty statement.** There is no untouched final test set. The final models
cannot be tested themselves; their expected accuracy is the year-by-year
score. Choices such as the warm-up rule and the model settings were made after
seeing these scores, so the scores may be slightly optimistic. How much was
not measured. See limit 15 in section 12.

### 6.4 Results (measured on the corrected data with the warm-up rule; nine held-out years 1991–1999 pooled, range over the years in brackets)

Files: `docs/results/cv_summary.json` and `docs/results/cv_by_year.csv`.
1,637,018 rain days scored; 5,155 high-loss days on 143 dates.

| | Surrogate | Baseline |
|---|---|---|
| Water runoff, daily R² | 0.986 (0.954–0.993) | 0.940 (0.829–0.967), curve-number formula; beaten in all 9 years |
| Pesticide loss, daily R² | 0.948 (0.867–0.986) | −0.24 (−13.6 to 0.85) |
| Sum of all loss, surrogate / PRZM | 0.948 (0.831–1.086) | – |
| High-loss days, PR-AUC | 0.965 (0.920–0.992) | rain today 0.108; classifier 0.954 (0.924–0.987) |
| Alarm "predicted loss ≥ 1 g/ha" (fixed limit; share of the dose: 6.10) | 4,948 alarms, 91.7 % real, 88.0 % of high-loss days found (80.1–97.7 % by year) | – |
| Speed | about 0.01 s per 10-year run | PRZM: about 3.4 s (measured in the re-run) |

Delivered data vs corrected data (same test, headline numbers):

| | Delivered (9 years, before the warm-up rule) | Corrected (9 years, with the rule) | Corrected (10 years, before the rule) |
|---|---|---|---|
| Fields used | 3,958 | 5,609 | 5,609 |
| Pesticide loss, daily R² | 0.91 (0.75–0.97) | 0.948 (0.867–0.986) | 0.95 (0.89–0.99) |
| Sum of all loss, surrogate / PRZM | 0.92 (0.70–1.16) | 0.948 (0.831–1.086) | 0.99 (0.86–1.12) |
| PR-AUC surrogate / classifier / rain rule | 0.92 / 0.81 / 0.06 | 0.965 / 0.954 / 0.108 | 0.97 / 0.94 / 0.10 |
| Alarm: real / high-loss days found | 91 % / 76 % (36–92 %) | 91.7 % / 88.0 % (80.1–97.7 %) | 92 % / 90 % (81–97 %) |

Reading:
- Runoff is reproduced almost perfectly (and did not change with the correction).
- Pesticide loss depends less on the year than on the delivered data, but a
  year's score is still decided by a handful of storms (worst year 1991,
  R² 0.867).
- Over all nine years the total loss is 5 % too low (0.948); single years
  range from 17 % too low (1997) to 9 % too high (1995). Before the rule it
  was 0.99 over ten years. On the delivered data it was 8 % too low overall
  and 30 % too low in the worst year.
- An alarm can be trusted, and close to nine in ten high-loss days are found.
- The surrogate beats the classifier on PR-AUC in seven of the nine years
  (not in 1996 and 1997).

**Risk table** (`risk_by_rain_and_weeks_since_spraying.csv`): chance that a
rain day is a high-loss day. First week after spraying: 14 % at 10–20 mm
rain, 92 % at 20–30 mm, almost 100 % at 30–50 mm. Weeks 5–8: 54 % at
20–30 mm (delivered data: 13 %). Weeks 9–16: 12 %. Later: almost 0.

**Drivers (SHAP on the classifier, test years 1992 and 1996):** rain since
spraying, curve-number runoff of today's rain, days since spraying,
heavy-rain days since spraying, rain yesterday, rain today, temperature
today, topsoil organic carbon. SHAP shows what the model uses, and the model
copies PRZM. "Temperature yesterday", second on the delivered data, is not in
the top twelve.

### 6.5 Second surrogate: LSTM
- A small LSTM (23,906 parameters, PyTorch, about 11 minutes on a laptop CPU).
  One sample = one run × one application year: 59 warm-up days plus 366 days.
  Inputs per day: rain, temperature, evaporation, curve number, curve-number
  runoff, days since spraying, plus the soil settings. Outputs per day: runoff
  and pesticide loss.
- Compared with the trees on identical rows (test weather files, years 1992
  and 1996; 402,049 rain days, 913 high-loss days; corrected data):

| | Trees | LSTM |
|---|---|---|
| Runoff, daily R² | 0.98 | 0.97 |
| Pesticide loss, daily R² | 0.96 | 0.98 |
| Pesticide loss, R² of the logarithm (small losses) | 0.96 | 0.44 |
| Sum of loss, surrogate / PRZM | 1.03 | 0.92 |
| High-loss days, PR-AUC | 0.95 | 0.99 |
| Alarm: real / high-loss days found | 91 % / 89 % | 97.5 % / 90 % |

- The LSTM is better on daily loss, high-loss days and alarm precision; the
  trees are better on daily runoff, small losses and the total (the LSTM is
  8 % too low).
- **Caution:** one test on two years, one random seed, not the year-by-year
  test. The advisor still uses the trees.
- The LSTM is not adapted to the warm-up rule (5.2): it still uses the
  warm-up period of 1990.

---

### 6.6 The surrogate on 45 years of real weather
- `python -m runoffwatch france`: all 5,609 fields (740 grid cells) × application years
  1979–2023 (252,405 field-years) with the Agri4Cast weather of each field's grid cell, spraying
  on 1 March. All numbers below are from the models trained with the warm-up rule (5.2). The
  comparison with PRZM leaves out field-years that start before the warm-up end.
- **1 March models (corrected data, `docs/results/france_summary.json`):** mean predicted loss
  per field and year 1.84 g/ha (1979–2005), 2.12 (2006–2015), 2.86 (2016–2023). Worst years
  2022, 2020, 2013, 2001, 2006; worst year 2022 (4.91 g/ha, 3.0× the median year), best 1997
  (0.51 g/ha). The five worst years carry 22.8 % of all loss. Do not read a climate trend into
  this. Before the rule: 1.84 / 2.07 / 2.80.
- For 2006–2015 it matches PRZM's yearly totals (R² 0.986 runoff, 0.987 loss, sum 1.005),
  which is not a test because the models were trained on those years. For the other 35 years no
  PRZM result exists.
- **With the varied models (`docs/results/varied/france_summary.json`; still 1 March and
  2.4 kg/ha):** 1.86 / 2.11 / 2.90 g/ha for the same three periods (medians 0.69 / 0.83 /
  1.17). Worst years 2022 (4.65), 2020 (4.53), 2013 (4.28), 2001 (4.03), 1989 (3.94); worst
  year 2.87× the median year; the worst five hold 22.7 % of all loss. Agreement with PRZM in
  2006–2015 (not a test): 50,481 field-years, yearly runoff R² 0.986, loss R² 0.987, sum 1.006.
- **Autumn run (done 25 Nov, late evening):** the same varied models and 2.4 kg/ha, but
  spraying on 15 October every year:
  `python -m runoffwatch --dataset varied france --spray 15.10 --scenario autumn`. Results are
  in `docs/results/varied/autumn/` (`france_summary.json`, `france_by_year.csv`), figures in
  `docs/figures/varied/autumn/` (option `--scenario`, section 10). Comparison (varied models,
  mean loss in g/ha per field and year, median in brackets):

  | | Spraying 1 March | Spraying 15 October |
  |---|---|---|
  | 1979–2005 | 1.86 (0.69) | 9.70 (5.81) |
  | 2006–2015 | 2.11 (0.83) | 12.34 (8.06) |
  | 2016–2023 | 2.90 (1.17) | 12.76 (6.98) |
  | High-loss days per field-year (same periods; fixed limit of 1 g/ha) | 0.42 / 0.47 / 0.59 | 1.73 / 2.15 / 2.04 |
  | Five worst years | 2022, 2020, 2013, 2001, 1989 | 2019 (28.5), 2014 (22.1), 2023 (18.1), 1999 (18.0), 2000 (15.9) |
  | Worst year / median year | 2.87 | 2.83 |
  | Share of all loss in the worst five years | 22.7 % | 21.0 % |
  | Check against PRZM, 2006–2015 | yes (above) | none |

  Spraying on 15 October loses about 4 to 6 times more than spraying on 1 March in the same
  weather. The worst years are different years, most likely because other storms fall in the
  weeks after each spray date. The best autumn years are 1988 (2.8) and 1995 (3.3). No PRZM check exists
  for 15 October, because PRZM was never run with that fixed date.
- **Limit that stays:** 10.4 % of field-years (1 March run; 10.7 % in the 15 October run)
  contain a rain day heavier than 99.9 % of the training rain days (48 mm). The copy is
  weakest on such days (6.9).

### 6.7 Varied spray dates and doses: method (23 Nov) and results (25 Nov 2026)

The code works for runs with varied spray dates and doses (section 8.1).
Data set: section 4. Results: `docs/results/varied/`, figures
`docs/figures/varied/`, models `models/varied/`.

**Method changes:**

- **Two new inputs:** the day of the year of the last spraying and its dose
  (kg/ha). They go into the concentration model and the classifier. The
  spray day stands for the crop stage at spraying. Whether it lets the trees
  memorise storms again is checked by the leave-one-year-out test.
- **Loss per kilogram sprayed:** the concentration model now predicts the
  loss per mm of runoff and per kg/ha sprayed. The prediction is multiplied
  by the dose, so one model serves every dose. Models saved before this
  change still work; for another dose their result is scaled in proportion.
- **High-loss day:** unchanged, at least 1 g/ha lost in one day. (Since
  26 Nov the app and the alarm scores also use a share of the dose; see
  6.10. The scores in this section use the fixed limit of 1 g/ha.)
- **Runoff model:** rain and runoff are identical in all copies of a field,
  so it learns from one run per field.
- **Test split unchanged:** it stays date-based. A March-to-February year is
  held out, plus unseen weather files. So no storm is in both training and
  test, even when spray dates differ.
- **New outputs of `train`:** `loss_by_spray_date.csv` and the figure
  `m9_loss_by_spray_date.png`: the share of the dose lost in the year after
  spraying, by half-month of spraying, straight from PRZM; and
  `loss_after_spraying.csv` (first 30 days after spraying: rain, runoff,
  curve number, loss; section 6.8). `train --cv` adds scores per spray window
  and per dose.
- **Large table (25 Nov):** training and the year-by-year test were rewritten
  for 24.6 million rows. They no longer copy the table: they use row masks,
  each model gets only its own rows and columns, and `load_features()` reads
  the table without a second copy.
- **LSTM not adapted:** it refuses runs that are not sprayed on 1 March. Its
  numbers (6.5) are from the 1 March data; `models/lstm.pt` is unchanged.

**Results, year-by-year test** (`cv_summary.json`, `cv_by_year.csv`), with
the warm-up rule: nine held-out years (1991–1999), 4,815,867 rain days
scored, 19,654 high-loss days on 572 storm dates (before the rule, ten
years: 5,355,895 rain days, 21,222 high-loss days on 622 dates). Main scores
are in the box at the top. In short:
- The task is harder (any spray day, three doses), yet the scores are at
  least as good as on the 1 March data: daily loss R² 0.965 (simple baseline
  0.782), runoff 0.986 (formula 0.940), total ratio 0.985 (0.950–1.082).
  Before the rule daily loss R² was 0.917 (0.78–0.97).
- **Loss R² per year:**

  | Year | 1991 | 1992 | 1993 | 1994 | 1995 | 1996 | 1997 | 1998 | 1999 |
  |---|---|---|---|---|---|---|---|---|---|
  | With the rule | 0.973 | 0.955 | 0.907 | 0.954 | 0.974 | 0.972 | 0.972 | 0.966 | 0.976 |
  | Before the rule | 0.921 | 0.956 | 0.887 | 0.927 | 0.967 | 0.967 | 0.963 | 0.883 | 0.971 |

  Before the rule 1990 was also in the test, with 0.777; the simple
  baseline beat the surrogate there. That year was a warm-up year with an
  irregular crop, so it was not a fair test (6.9). Now the weakest year is
  1993 (loss R² 0.907, total over-predicted by 8 %; also the weakest year for
  runoff, 0.954). The surrogate beats the simple baseline in all nine years.
  1998 rose from 0.883 to 0.966 (6.9).
- **By spray window:** autumn loss R² 0.962, total ratio 0.988, alarm
  precision 92.8 %, recall 93.3 % (11,503 high-loss days). Spring 0.976,
  0.980, 92.4 %, 91.6 % (8,151). Before the rule autumn was clearly harder
  (0.90 against 0.97); now the gap is small.
- **By dose:** 0.24 kg/ha 0.963, 0.999, 89.9 %, 90.0 % (only 981 high-loss
  days); 1.2 kg/ha 0.965, 0.994, 92.3 %, 93.1 %; 2.4 kg/ha 0.965, 0.981,
  92.9 %, 92.5 %.
- The classifier ranks high-loss days as well as the surrogate (PR-AUC 0.975
  against 0.973; rain rule 0.106). On the 1 March data it is behind (0.954
  against 0.965).

**Results, single split** (test years 1992 and 1996, unseen weather files;
`model_metrics.json`; with the warm-up rule): runoff R² 0.981 (formula
0.928); loss R² 0.966, total ratio 0.989; with PRZM's true runoff the
chemistry stage alone has R² 0.991. PR-AUC: surrogate 0.971, classifier
0.970, logistic regression 0.799, rain rule 0.081. Alarm at the fixed limit of 1 g/ha: 3,819
alarms, 93.4 % precision, 91.0 % recall. SHAP ranking of the classifier:
rain since spraying, curve-number runoff, dose, days since spraying, rain
today, evaporation in the previous week, heavy-rain days since spraying,
topsoil organic carbon. Training uses 10,202,039 rain-day rows; the final
models are trained on all 22,580,508 rows (24.6 million before the rule).
Speed: about 0.06 s per ten-year run against about 3.4 s for PRZM (about 60
times faster).

### 6.8 What PRZM says about the spray date, and why (25 Nov 2026)

This is read directly from the simulations, not from a model. Mean share of
the dose lost in the season after spraying
(`docs/results/varied/loss_by_spray_date.csv`). The table is built from
trusted rows, so with the warm-up rule the sprayings before 12 Nov 1990 are
left out.

| Sprayed | Mean % of dose lost | 90th percentile | Before the rule: mean % |
|---|---|---|---|
| Feb 16–end | 0.080 | 0.19 | 0.09 |
| Mar 1–15 | 0.078 | 0.17 | 0.08 |
| Mar 16–end | 0.077 | 0.20 | 0.07 |
| Apr 1–15 | 0.086 | 0.22 | 0.08 |
| Apr 16–end | 0.104 | 0.28 | 0.10 |
| Oct 1–15 | 0.518 | 1.13 | 0.47 |
| Oct 16–end | 0.657 | 1.51 | 0.60 |
| Nov 1–15 | 0.409 | 1.07 | 0.39 |
| Nov 16–end | 0.191 | 0.41 | 0.19 |

Autumn spraying loses about 2 to 8 times more of the dose than spring
spraying (0.19–0.66 % against 0.08–0.10 %; before the rule "2 to 7 times").

**Why** (first 30 days after spraying, mean per season;
[`loss_after_spraying.csv`](results/varied/loss_after_spraying.csv)):
- One mm of runoff carries about the same share of the dose in every window
  (0.045–0.065 %). The chemistry does not differ.
- What differs is how much water runs off in the first month: 0.7–1.6 mm in
  spring, 9–10 mm in October, 2.9 mm in late November. Rain differs far less
  (47–66 mm in spring, 75–81 mm in autumn).
- The cause is the crop calendar of the PRZM scenario (section 4). Between
  harvest (31 Jul) and emergence (12 Nov) the field counts as stubble or
  fallow with a high curve number, so more rain becomes runoff. From 12 Nov,
  in every field and year, the curve number drops by 5 to 10 points and runoff
  falls by more than half with the same rain.
- So the result is: "spraying before the crop has emerged loses more than
  spraying after": about 2 to 3.4 times more than spraying in late November,
  just after emergence, and about 4 to 8 times more than spraying in spring
  (from the table above). The sharp step in mid-November is the fixed
  emergence date of the scenario, not a law of nature. In reality emergence
  differs by field and year. The surrogate copies this property of the
  scenario.
- An autumn herbicide in winter cereals is usually sprayed around sowing or
  emergence (general knowledge, to be confirmed by the team's environmental
  scientist), that is in the high-loss window. The 1 March date of the
  delivered data is in the low-loss window.
- After day 120 the loss is negligible in every window (under 0.005 % of the
  dose).

### 6.9 The weak test years 1990 and 1998, and a rejected experiment (25 Nov 2026, evening)

This section explains why the warm-up rule was added. Its 1990 and 1998
scores are from before the rule; the new scores are in 6.4 and 6.7.

**1990 (weakest year before the rule: daily loss R² 0.78, the simple
baseline 0.85).**
- 81 % of the squared error of 1990 is on two storm days, 17 and 21 Nov
  1990, in fields sprayed that autumn.
- Cause: 1990 is a warm-up year (section 4, crop cycles). The first crop
  cycle starts before the simulation, so until 12 Nov 1990 the crop state is
  not the regular one.
- Evidence from PRZM's own yearly balance ("FOLIAR APPLICATION" line of the
  `.OUT` file = share of the dose that lands on the crop canopy), sample of
  1,200 varied runs:

  | Sprayed | Year 1 | Years 2–10 |
  |---|---|---|
  | Autumn, before 12 Nov | 90 % (every run) | 0 % |
  | Autumn, from 12 Nov | 5 % | 4 % |
  | Spring (15 Feb–30 Apr) | 35 % | 57 % |

  For the 1 March runs: 26 % in year 1, 47 % in years 2–10 (150 runs). 47 %
  is exactly what the crop calendar gives (canopy grows linearly from
  emergence 12 Nov to 90 % at maturity 10 Jun).
- What this does: on the canopy the pesticide decays with a half-life of
  about 10 days and is washed to the soil by rain. So in year 1 an October
  spray behaves very differently: much higher loss if it rains on the spray
  day, lower loss afterwards. The surrogate cannot see this (no canopy
  input).
- Runoff is affected too. In Aug–Oct 1990 PRZM gives only about 55–65 % of
  the runoff that the curve-number formula with the regular crop calendar
  expects (other years mostly 80–130 %). The harvest switch of the curve
  number does not happen in year 1.
- Consequence: 1990 was not a fair test, and its rows also disturbed
  training. This applies to all data sets (delivered, corrected, varied),
  because all share the same crop lines. Fix: the warm-up rule (5.2).
  Whether the first cycle before the simulation start is intended, and
  whether a warm-up year is normally discarded, is a question for the model
  owner in Landau (section 13).

**1998 (second weakest before the rule: daily loss R² 0.883).** 75 % of its
squared error is one day, 3 Nov 1998, with up to 153 mm of rain in one
weather cell. The surrogate predicted 87 mm runoff where PRZM gives 136 mm.
Tree models cannot predict beyond the largest values they were trained on.
After the warm-up rows left training, 1998 loss R² rose from 0.883 to 0.966
(varied data). So part of the old weakness came from the warm-up rows. The
limit on extreme rain (80 mm and more) still stands (below).

**Experiment that did NOT help (do not repeat it):** train the runoff model
as a correction of the curve-number formula (LightGBM tweedie with
`init_score = log(curve-number runoff + 0.02)`). Nine held-out years
1991–1999, 1 March runs, warm-up left out:

| Runoff model | All days R² | Rain ≥ 48 mm (1,868 days) | Rain ≥ 80 mm (127 days) |
|---|---|---|---|
| Current (predicts runoff directly) | 0.986 | 0.954 | 0.75 |
| Correction of the formula | 0.981 | 0.929 | 0.74 |
| Curve-number formula alone | 0.940 | 0.897 | 0.85 |

- Decision: keep the current model.
- Known limit: on the 127 most extreme rain days the plain formula is better
  than the surrogate.
- By-product: with the warm-up left out, the current runoff model scores
  0.986 over nine years; weakest year 1993 (0.954).

### 6.10 High-loss limit as a share of the dose (26 Nov 2026)

**Why.** Until now a "high-loss day" was a day that loses 1 g/ha or more, a
fixed amount. The environmental-science side pointed out that a fixed g/ha
limit cannot hold across compounds, because doses differ by a factor of 100
or more. One gram per hectare is nothing for a herbicide sprayed at 1 to
3 kg/ha, and very serious for an insecticide sprayed at 5 to 10 g/ha. In our
own runs 1 g/ha is 0.42 %, 0.083 % and 0.042 % of the three doses 0.24, 1.2
and 2.4 kg/ha.

**New definition (used in the app).** A high-loss day is a day on which the
field loses at least a chosen share of the dose. The app starts with 0.1 %
(2.4 g/ha at 2.4 kg/ha, 0.24 g/ha at 0.24 kg/ha). The user can choose 0.01,
0.02, 0.05, 0.1, 0.2 or 0.5 %. 0.1 % is a starting value we chose, a round
number in the middle of the range. It is **not** an official or regulatory
limit. Which share is serious for which compound group is still open; the
environmental-science side is working on a classification by compound
group. Compounds sprayed at a few g/ha stay outside the dose range of the
runs (0.24 to 2.4 kg/ha).

**Scores.** No model was retrained. The alarm is "predicted loss of the copy
at or above the limit". It was scored again on the saved held-out
predictions of the year-by-year test (nine held-out years 1991–1999). File:
entry `alarm_by_share_of_dose` in `docs/results/varied/cv_summary.json` and
`docs/results/cv_summary.json` (per limit: all rows, `by_dose_kgha`,
`by_year`, `by_spray_window`).

Varied spray dates and doses (main result), 4,815,867 rain days:

| Limit (% of dose) | High-loss days (PRZM) | Alarms | Alarms that are right (precision) | High-loss days found (recall) | Precision, range over years | Recall, range over years |
|---|---|---|---|---|---|---|
| 0.01 | 63,255 | 63,223 | 94.2 % | 94.1 % | 92.0–96.4 % | 92.6–95.4 % |
| 0.02 | 46,494 | 46,134 | 94.1 % | 93.4 % | 91.9–95.6 % | 91.1–96.2 % |
| 0.05 | 27,297 | 27,262 | 93.1 % | 93.0 % | 90.7–96.2 % | 89.6–95.7 % |
| 0.1 (app start value) | 15,798 | 15,853 | 91.6 % | 91.9 % | 84.8–96.6 % | 87.9–96.3 % |
| 0.2 | 7,827 | 7,888 | 90.3 % | 91.0 % | 76.9–96.9 % | 87.8–95.3 % |
| 0.5 | 2,506 | 2,476 | 88.9 % | 87.8 % | 71.4–98.5 % | 83.1–90.8 % |

- At 0.1 %, by dose: 0.24 kg/ha 4,692 high-loss days, precision 91.7 %,
  recall 92.1 %; 1.2 kg/ha 4,865, 91.7 %, 91.7 %; 2.4 kg/ha 6,241, 91.4 %,
  91.9 %. So the scores are the same for every dose. With the old fixed
  limit of 1 g/ha the lowest dose had only 981 high-loss days.
- At 0.1 %, by spray season: autumn 11,488 high-loss days, precision 91.8 %,
  recall 92.3 %; spring 4,310, 90.8 %, 90.7 %.
- For comparison, the old fixed limit of 1 g/ha: 19,654 high-loss days,
  precision 92.6 %, recall 92.6 %.

Corrected 1-March-only runs (one dose 2.4 kg/ha, one spray date),
1,637,018 rain days:

| Limit (% of dose) | High-loss days | Alarms | Precision | Recall |
|---|---|---|---|---|
| 0.01 | 13,575 | 13,451 | 93.3 % | 92.5 % |
| 0.02 | 9,082 | 8,730 | 94.3 % | 90.6 % |
| 0.05 | 4,369 | 4,114 | 92.8 % | 87.4 % |
| 0.1 | 1,927 | 1,995 | 88.2 % | 91.3 % |
| 0.2 | 688 | 699 | 86.0 % | 87.4 % |
| 0.5 | 244 | 203 | 92.6 % | 77.0 % |

**Reading.**
- The stricter the limit (higher share), the fewer high-loss days there are
  and the more the scores vary between years.
- With a share of the dose every dose is treated alike, and the scores are
  the same for every dose.
- On the 1-March-only runs the rows for 0.2 % and 0.5 % are weak evidence:
  with so few high-loss days the per-year scores swing widely (some years
  hold almost no such day).

**Check: is the loss proportional to the dose?** In the held-out rows of the
varied runs the mean share of the dose lost per rain day is 0.001926 % at
0.24 kg/ha and 0.001923 % at 1.2 kg/ha (copy: 0.001925 % and 0.001912 %).
So PRZM's loss scales with the dose between these two doses, and a limit as
a share of the dose treats every dose alike. The 2.4 kg/ha group cannot be
compared directly: it also contains the 1-March-only runs, with another mix
of spray dates.

**What still uses the old fixed limit of 1 g/ha** (a limit of the current
state):
- The separate classifier model and its PR-AUC scores (0.975 on the varied
  data); it was trained with the 1 g/ha label. The alarm in the app does not
  use the classifier; it uses the predicted loss amount. With the fixed
  limit the two were equally good (PR-AUC 0.973 for the amount, 0.975 for
  the classifier), so the classifier adds little. Retraining it with a
  share-of-dose label is not done.
- `alarm_at_1_gha` in `cv_summary.json`, the alarm columns in
  `cv_by_year.csv`, and the figures `m3_high_loss_precision_recall.png` and
  `m7_scores_by_held_out_year.png`.
- "High-loss days per field-year" in the 45-year runs (`france_summary.json`,
  `france_by_year.csv`, table in 6.6). Those runs use one dose (2.4 kg/ha),
  where 1 g/ha is 0.042 % of the dose.
- The constant `HIGH_LOSS_GHA` in `runoffwatch/features.py` and the column
  `high_loss` in the feature table.
- Runoff scores and loss-amount scores (R², totals) never depended on the
  limit.

### 6.11 Why 1991 is the weakest year of the 1-March-only models (26 Nov 2026)

On the 1-March-only data 1991 has the lowest loss R² (0.867, 6.4). This was
checked on the held-out predictions of 1991 (175,095 rain days).

- 1991 is the only year with heavy runoff on the spray day itself
  (1 March 1991). In PRZM the loss per mm of runoff on the spray day is about
  0.56 g/ha per mm, against about 2.3 in days 1 to 7 after spraying (about a
  quarter). With 1991 held out, the model has almost no example of runoff on
  the spray day: all other years together have 580 such rain days with
  140 mm of runoff, against 1,886 rain days with 4,671 mm in 1991.
- 52 % of the squared error of 1991 sits on 1 March 1991. There the copy
  predicts 38 % too much loss (966 against 702 g/ha, summed over the test
  fields), although it gets the runoff water right (1,221 against 1,247 mm).
  So the error is in the pesticide concentration, as expected.
- Another 37 % sits on 7 March 1991. There the copy predicts too little loss
  (193 against 298 g/ha) and also too little runoff (102 against 139 mm).
  This is a different error: a rain day shortly after the storm.
- The two days together hold 89 % of the squared error of 1991. Without
  1 March the loss R² of 1991 is 0.914.
- The total over the year is right: predicted / PRZM = 1.006.
- The varied models do not have this weakness (loss R² for 1991: 0.973),
  because their spray dates are spread, so runoff on a spray day occurs in
  many training years.

Conclusion: this is a limit of data with one fixed spray date, not a fault
of the method.

### 6.12 Frozen models and the check on new runs (26 Nov 2026)

**What is frozen.** The file `models/FROZEN.json` holds a fingerprint
(SHA-256) of every saved model file and `meta.json` in three folders:
`models/` (1-March-only models), `models/varied/` (the models the app uses)
and `models/delivered/`. They were frozen on 26 Nov 2026; the files are
those of commit 3150b96 on main. Windows line ends are ignored when the
fingerprint is made, so it is the same on every computer.

**Why.** A test on runs that arrive later is only honest if the models
could not be adjusted after seeing those runs. The freeze makes that
checkable (limit 15 in section 12).

**What the freeze does in the code:**
- `python -m runoffwatch train` refuses to write into a frozen folder
  (message "The models in ... are frozen"). `train --cv` still works,
  because it saves no models.
- The new command `check` only scores models that are frozen and unchanged.
- A test in the test suite fails if a frozen model file in the repository
  changes.
- To train new models on purpose later: write to another folder with
  `--models <folder>`, or remove that folder from `models/FROZEN.json`
  deliberately, and say so in the documents.

**The command `check`.** `python -m runoffwatch --dataset dosecheck check`
scores the frozen models on runs they were not trained on. It trains
nothing. It writes `new_runs_check.json` and `new_runs_check_by_year.csv`
into the results folder and prints the scores next to the scores of the
year-by-year test. It also saves the predictions next to the feature table
(data, never committed). Scores: runoff R², pesticide loss R², total loss
copy / PRZM, and the alarm table by share of the dose; for all rows, per
year, per dose and per spray season.

**What the 0.6 kg/ha check is.** One extra copy of 500 fields (every k-th
field, so all batches take part), with a dose of 0.6 kg/ha and new random
spray dates inside the trained windows (seed 2 instead of 1). 0.6 kg/ha
lies between the trained doses 0.24 and 1.2 and was never seen by the
models. It tests the models in `models/varied/`. The data set is
`dosecheck` (section 10).

**What it is NOT.** The fields, their weather files and the years
1990–1999 were all in the training data. So it tests the dose only (does
the copy hold between the trained doses?). It is not an independent test.
That still needs new fields from the Landau group (section 13).

**Result (run on the project PC, recorded 27 Nov 2026).** All seven steps
of 8.3 ran without error. PRZM finished all 500 runs; all 500 were trusted
(4,915 of 4,915 run-years, 320 different weather files). The feature table
has 672,066 rain days, 630,398 of them with trusted pesticide results. The
models were the frozen ones in `models/varied/`.

| Score | New runs at 0.6 kg/ha | Year-by-year test (6.4) |
|---|---|---|
| Runoff R² | 0.988 | 0.986 |
| Pesticide loss R² | 0.980 | 0.965 |
| Total loss, copy / PRZM | 0.983 | 0.985 |

Alarms by share of the dose (alarms that are right / high-loss days found):

| Limit (% of dose) | High-loss days | New runs at 0.6 kg/ha | Year-by-year test (6.10) |
|---|---|---|---|
| 0.01 | 10,009 | 93 % / 96 % | 94 % / 94 % |
| 0.02 | 7,498 | 93 % / 96 % | 94 % / 93 % |
| 0.05 | 4,597 | 93 % / 95 % | 93 % / 93 % |
| 0.1 | 2,779 | 93 % / 93 % | 92 % / 92 % |
| 0.2 | 1,422 | 94 % / 92 % | 90 % / 91 % |
| 0.5 | 476 | 95 % / 90 % | 89 % / 88 % |

**How to read it.**
- The copy holds at a dose it never saw. At 0.6 kg/ha it is as close to
  PRZM as at the trained doses. So a dose between 0.24 and 2.4 kg/ha in the
  app is not a guess.
- The scores are a little higher than in the year-by-year test. That is
  not a sign of a better model. It is the sign of an easier test: the
  fields, their weather and the years were all in the training data. For
  comparison, the same command on the 1-March training runs themselves
  gives a pesticide loss R² of 0.984.
- So this result says nothing about new fields or new weather. The
  independent test still needs new fields from the Landau group
  (section 13).

**Year by year (checked 27 Nov 2026).** No year is weak. The fingerprint
stored in the result file is the frozen one, so the frozen models were used.

| Year | Rain days with trusted pesticide | Runoff R² | Pesticide loss R² | Total loss, copy / PRZM | Loss R² in the year-by-year test |
|---|---|---|---|---|---|
| 1990 | 4,210 | 0.989 | 0.995 | 1.006 | not a test year |
| 1991 | 50,623 | 0.991 | 0.990 | 0.989 | 0.973 |
| 1992 | 78,149 | 0.982 | 0.972 | 0.987 | 0.955 |
| 1993 | 73,222 | 0.980 | 0.954 | 1.058 | 0.907 |
| 1994 | 67,576 | 0.988 | 0.969 | 0.982 | 0.954 |
| 1995 | 61,743 | 0.994 | 0.982 | 0.961 | 0.974 |
| 1996 | 80,071 | 0.989 | 0.977 | 0.943 | 0.972 |
| 1997 | 86,577 | 0.986 | 0.976 | 1.020 | 0.972 |
| 1998 | 77,483 | 0.987 | 0.983 | 0.928 | 0.966 |
| 1999 | 50,744 | 0.991 | 0.980 | 1.019 | 0.976 |

- Pesticide loss R² lies between 0.954 and 0.995, runoff R² between 0.980
  and 0.994.
- 1990 holds only the sprayings made after the warm-up ended on 12 Nov 1990,
  so it is a small sample (24 high-loss days at the 0.1 % limit).
- 1993 is the lowest year here, as in the year-by-year test. The total is
  6 % too high in 1993 and 7 % too low in 1998. These years were in the
  training data, so this error does not come from unseen weather. It comes
  with a few storm days the copy does not match well.
- By spray season: autumn loss R² 0.979 (total 0.977), spring 0.983
  (total 1.015).
- Alarms at 0.1 % of the dose, per year: 87 % to 100 % of the alarms are
  right and 89 % to 100 % of the high-loss days are found. Spring has few
  high-loss days at the strictest limit (25 at 0.5 %), so that one number
  is weak evidence.

The result files are `new_runs_check.json` and
`new_runs_check_by_year.csv` in `docs/results/varied/dose_check/` (in the
repository since 27 Nov 2026).

---

## 7. The spray-day advisor (Task 4, prototype)

- `python -m runoffwatch whatif` (command line) and `streamlit run app.py`.
- Input: a daily weather table (`date, rain_mm, temp_c`, optional
  `pan_evap_mm`; about 30 days of history plus the forecast) and a soil.
- Output: for each candidate spray day, the predicted pesticide loss in the
  following 14 days, and the number of predicted high-loss days. Since
  26 Nov a high-loss day here is a day above a share of the dose (default
  0.1 %, 6.10). Only candidates with a full window are ranked.
- A dose can be given (`whatif --dose`, a box in the app). The app uses the
  models in `models/varied` when that folder exists (trained on varied spray
  dates and doses, 6.7); otherwise the 1 March models in `models/`, which
  know only 2.4 kg/ha. Since 26 Nov the dose box in the app only takes doses
  the loaded models were trained on (7.1).
- **Limits:** valid only for Flufenacet on winter cereals, inside the two
  spray windows the models were trained on (15 Feb–30 Apr, 1 Oct–30 Nov).
  The autumn effect comes from the fixed emergence date of the PRZM scenario
  (6.8). It cannot compare products. It has not been evaluated as a decision
  tool.

### 7.1 The app (rewritten 25 Nov, redesigned 26 Nov 2026)

**Aim of the redesign:** each tab answers one question and starts with the
answer. Detail is in fold-out boxes. Every tab names the project task it
belongs to. Five tabs:

| Tab | Project task | What it shows |
|---|---|---|
| 1. Pick a spray day | Task 4 (advisor) | Which spray day loses the least pesticide? The only tab that computes something new. |
| 2. Is the copy right? | Task 3 and Task 2 | Scores of the copy from the year-by-year test: amounts, warnings, speed. |
| 3. Spring or autumn? | Task 2 (explaining) | PRZM's own results: how much of the dose is lost by spray season. |
| 4. 45 years of weather | Task 3 put to use | The copy on 45 years of real French weather, spraying on 1 March or 15 October. |
| 5. About | overview | What this is, how to use each tab, the four tasks, limits. Task 1 has no tab of its own. |

**What is on each tab:**
- **Pick a spray day.** Left side, in three steps: Step 1 Weather (example
  or own CSV; the template download shows only when "Upload" is chosen);
  Step 2 Field (slope; how easily rain runs off, which is the curve number;
  fold-out "More soil settings"); Step 3 Spraying (dose; first day you could
  spray; the high-loss limit as a share of the dose, with the amount in g/ha
  written under it; fold-out "More options": number of candidate days, days
  to add up). Right side: a green box with the best and the worst day; a bar
  chart with one bar per candidate day, labelled "lowest" and "N days above
  the limit"; "What happens after one spray day" (rain and loss per day, with
  a dashed line at the limit when a day comes near it); fold-out "All
  numbers as a table".
- **The dose box (changed on 26 Nov 2026).** Step 3 has the box "Dose
  (kg/ha)". It is limited to the range of doses the loaded models were
  trained on. The range is read from the model file `meta.json` (entry
  `trained_on` -> `doses_kgha`); it is not written into the code. For the
  varied models this is 0.24 to 2.4 kg/ha (trained doses 0.24, 1.2 and 2.4).
  Before, the box took 0.05 to 5.0 kg/ha and only showed a warning outside
  the trained range.
  - The box starts at 2.4 kg/ha if that lies inside the range; otherwise at
    the highest trained dose. The step is 0.01, so each trained dose can be
    entered exactly.
  - A caption under the box says which dose range the models were trained
    on.
  - If the loaded models know only one dose (the 1-March-only models:
    2.4 kg/ha), the box is shown switched off at that dose, with a short line
    saying why. If the model file does not state the doses, the app treats
    it as 2.4 kg/ha only.
  - A spray day outside the trained windows can still be chosen. The app
    still warns then, and the result is a guess. The dose can no longer be
    outside the range.
  - Why adjustable and not fixed: the runs themselves have three doses;
    doses differ between compounds; and in PRZM the loss is proportional to
    the dose (6.10). So changing the dose does not change which spray day is
    best, only the amounts in g/ha.
  - Helper functions in `runoffwatch/appdata.py`: `trained_doses(meta)`,
    `default_dose(doses)`, `spray_limits(meta)` (wording updated).
- **Is the copy right?** Three blocks of cards. 1. Does it get the amounts
  right? (R² 0.99 for runoff water and 0.96 for pesticide loss; 99 % of the
  total loss found.) 2. Does it warn on the right days? (a limit picker;
  alarms that are right, high-loss days found, number of high-loss days in
  the test; at 0.1 %: 92 %, 92 %, 15,798.) 3. How fast is it? (0.06 s
  against about 3.4 s for PRZM, about 58 times faster.) Fold-outs: "Year by
  year", "By dose and by spray season", "How the test works". The limit
  picker here and the one in tab 1 are the same setting: changing one
  changes the other.
- **Spring or autumn?** PRZM's own results. Cards: sprayed in spring 0.08 %
  of the dose lost, sprayed in autumn 0.44 %, so autumn about 5 times more
  (means over half-months, weighted by the number of simulated seasons). A
  bar chart by half-month, and one sentence why (the crop emerges on 12 Nov
  in the simulator, 6.8). Fold-out "The evidence: the first 30 days after
  spraying" (three small charts).
- **45 years of weather.** Scenario buttons "Spraying on 1 March" and
  "Spraying on 15 October"; cards for the three periods; the worst five
  years; a chart per year with a band; both scenarios side by side; a
  fold-out map.
- **About.** What this is, how to use each tab, the four project tasks and
  where they are in the app, what a high-loss day is, limits, which models
  are loaded, and the numbers of the data check.

**How to use it (plain steps):**
1. Start the app (below) and open tab 1, "Pick a spray day".
2. Step 1: keep the example weather, or choose "Upload" and load your own
   CSV (the template download appears then).
3. Step 2: set the slope and how easily rain runs off.
4. Step 3: set the dose (only inside the trained range, start value
   2.4 kg/ha), the first day you could spray, and the high-loss limit as a
   share of the dose (start value 0.1 %).
5. Read the green box: it names the best and the worst spray day. The bar
   chart shows all candidate days.
6. To see how far the copy can be trusted, open tab 2. To see why autumn
   loses more, open tab 3.

- **Files:** `app.py` (the Streamlit page), `runoffwatch/appdata.py` (finds
  and reads the result files, formats numbers; plain Python, so it can be
  tested), `tests/test_app.py` (tests, also with missing or broken result
  files and without models).
- **Needs Python 3.10 or newer.** Start from the repository root:
  `pip install -e ".[app]"`, then `streamlit run app.py`.
- **Windows (fixed on 26 Nov 2026):** on Windows, Git may check text files
  out with Windows line ends (CRLF). The model files in `models/` are text
  files in which LightGBM finds the trees by counting bytes, so the app
  failed at start with many lines "Model format error, expect a tree here".
  Fixed twice over: the loader now removes Windows line ends before reading
  a model, and `.gitattributes` keeps the model files with Unix line ends.
  Anyone who cloned before the fix: `git pull` is enough.
- It reads the models and the result tables in the repository at run time
  (`models/`, `docs/results/`, `docs/figures/`). No simulation data is
  needed. When a result file is missing or half-written, the tab shows
  "Not available yet" instead of failing; reload the page later.
- **Checked in a browser (26 Nov 2026):** all five tabs at a width of 1400
  pixels, and the first two tabs at 520 pixels (the columns stack under each
  other, nothing runs off the side). Not checked on a real phone.
  `docs/figures/app_screenshot.png` shows the redesigned first tab.

---

## 8. New simulation runs

### 8.1 Running PRZM ourselves (works since 23 Nov 2026)

- `WINPRZM.exe` (from this year's project cloud folder) runs on an ordinary
  Windows PC in about 3 seconds per field. The local results match the
  delivered ones exactly.
- **By hand, for one run folder:**
  1. Put the program and the run files at a short path without spaces, for
     example `C:\Temp\X3MZI0OQ2D67EUQHFZ\`. A path of about 100 characters
     fails, because PRZM reads paths in fixed-width fields.
  2. In `Run 1.run`, change the two `PATH` lines (input folder and output
     folder) so they point at that folder.
  3. Start the program from that folder; in PowerShell type `.\WINPRZM.exe`
     (it looks for the `.run` file in the folder it is started from).
- **For many folders:** the `rerun` command does this automatically
  (section 10).
- Because of this, spray date, dose and substance settings (half-life,
  sorption, Henry constant) can now also be varied locally, by editing the
  `.inp` file of a run before starting PRZM (the `.inp` file holds the
  application dates and the pesticide settings).
- **Varied spray dates and doses (tool written 23 Nov 2026; a trial of 20 runs
  worked; the full run finished and was analysed by 25 Nov, see below):**
  `rerun --variants 2` makes two extra copies of every
  field. By default each copy gets one of two spray windows (15 Feb to 30 Apr,
  or 1 Oct to 30 Nov), one of three doses (0.24 / 1.20 / 2.40 kg/ha) and,
  inside its window, a different random spray day in each of the ten years.
  With two copies a field gets one spring and one autumn copy. The plan
  depends only on the seed, the field name and the copy number, so the same
  command always makes the same runs and can be stopped and restarted.
  Results go to `data/raw/runs_varied/` (folders `<field>__v1`, `<field>__v2`),
  the plan to `rerun_plan.csv`. Only fields with a finished result in
  `data/raw/runs_fixed/` are used (5,609), so two copies are 11,218 runs:
  about 2.6 hours (3.4 s per run, four at a time) and about 6.5 GB (the
  weather file is not copied again). Try `--limit 10` (20 runs) first.
  Half-life, sorption and other substance settings are not varied by this
  tool. The feature table, the tree models and the advisor were adapted to
  varied spray dates and doses on 23 Nov 2026 (section 6.7); the LSTM was not.
- **The full varied run (done):** 11,218 simulations received, 11,209
  readable and clean (section 4). 9 runs (5 fields, all in one batch) have a
  result file of full size (about 460 KB) that holds only zero bytes: the run
  on the PC was interrupted while they were written. They are left out (under
  0.1 %); those fields still have their 1 March run. **Lesson:** the re-run
  tool treated them as finished, because it only checked the file size.
  `rerun.is_done` now also rejects result files filled with zero bytes. When
  a run is interrupted, check the last files written, not only their size.
- **Unconfirmed:** the delivered dose of 2.4 kg/ha looks about ten times
  higher than usual field rates of flufenacet products (a few hundred grams
  per hectare). This is from general knowledge, not checked against a label
  or with the model owners. It is why 0.24 kg/ha is among the default doses.

### 8.2 Runs for the Landau workstation (prepared, NOT submitted)

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
    was meant to test the Henry hypothesis; the local test runs (5.1) have
    now done that on a small scale.
- **Before submitting:** permission from the model owner; the spray date must
  be read from the run file on their side; our weather CSVs are rebuilt from
  PRZM weather files and may differ from the originals. `design.py` now writes
  the same corrected settings as `rerun` (Henry 0.37E-06, reference soil
  moisture 1, taken from `rerun.py`); both are still our reading of the
  evidence and should be confirmed.
- With such runs (from Landau or made locally), dose, DT50 and Koc become
  model inputs and the advisor could compare days, doses and substances.

### 8.3 The 0.6 kg/ha dose check: how to run it

What the check is and is not: 6.12. Run these seven steps on the Windows
PC, from the repository root, in the environment `runoffwatch`, one after
the other:
```bash
python -m runoffwatch --dataset dosecheck rerun --exe C:\Temp\X3MZI0OQ2D67EUQHFZ\WINPRZM.exe
python -m runoffwatch --dataset dosecheck add-weather
python -m runoffwatch --dataset dosecheck inventory
python -m runoffwatch --dataset dosecheck qc
python -m runoffwatch --dataset dosecheck audit
python -m runoffwatch --dataset dosecheck features
python -m runoffwatch --dataset dosecheck check
```
1. `rerun` makes the 500 runs with 0.6 kg/ha in `data/raw/runs_dosecheck/`.
   About 7 minutes (3.4 s per run, four at a time).
2. `add-weather` puts each field's weather file into the new run folders.
3. `inventory` finds what differs between the new runs.
4. `qc` reads and checks every new run.
5. `audit` decides which results can be trusted.
6. `features` builds the feature table
   `data/processed/features_dosecheck.parquet`.
7. `check` scores the frozen models in `models/varied/` on these runs. It
   trains nothing.

Afterwards commit only the files in `docs/results/varied/dose_check/` (and
the figures in `docs/figures/varied/dose_check/`), never `data/`. The
result of the run of 27 Nov 2026 is in 6.12.

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
python -m pytest -q             # 594 passed (26 Nov, with PyTorch installed)
python -m runoffwatch whatif
streamlit run app.py
```

**Known problem on Windows (fixed on 26 Nov 2026):** if the app stops at
start with many lines "Model format error, expect a tree here", the model
files were checked out with Windows line ends (CRLF). The loader now removes
them, and `.gitattributes` keeps the model files with Unix line ends. A
clone from before the fix only needs `git pull` (details in 7.1).

Full pipeline from the raw data (put the ten archives in `data/raw/archives/`):

| # | Command | What it does | Time |
|---|---|---|---|
| 1 | `python -m runoffwatch extract` | Unpacks the archives | 1 min |
| 2 | `python -m runoffwatch inventory` | Finds what differs between runs | 5 s |
| 3 | `python -m runoffwatch qc` | Reads and checks every run | 1 min |
| 4 | `python -m runoffwatch audit` | Task 1: which results are trusted; with trust rule `balance` it also writes the warm-up end `clean_from` (5.2) | 30 s |
| 5 | `python -m runoffwatch features` | Builds the feature table | 2 min |
| 6 | `python -m runoffwatch train` | Trains surrogate and classifier, saves final models; since 26 Nov it refuses to write into a frozen folder (6.12) | 3 min (`varied`: 22 min, about 12 GB memory) |
| 7 | `python -m runoffwatch train --cv` | Leave-one-year-out evaluation; since 26 Nov it also saves the held-out predictions next to the feature table (see below) | 25–30 min (`varied`: 70 min) |
| – | `python -m runoffwatch lstm` (needs `pip install -e ".[lstm]"`) | LSTM vs trees | 12–20 min |
| – | `python -m runoffwatch france` | Surrogate on 45 years of France weather; `--spray DD.MM`, `--dose`, `--scenario NAME` (own sub-folder, see below) | 8 min (`varied`: 22 min) |
| – | `python -m runoffwatch design` | Run files for new simulations | 1 min |
| – | `python -m runoffwatch rerun --exe ...` (Windows only) | Runs PRZM again on every folder with inputs, with the two corrected settings; with `--variants N`, N extra copies per field with varied spray dates and dose (`--spray-windows`, `--doses`, `--seed`); `--sample N` uses only N fields, spread evenly over all fields | about 1.5 h for 6,958 folders, four at a time; `--variants 2`: about 2.6 h for 11,218 runs |
| – | `python -m runoffwatch --dataset dosecheck check` | Scores the frozen models on runs they were not trained on; trains nothing (6.12, 8.3). Options `--features`, `--models`, `--results` | not measured yet |

The `rerun` command, first as a test on 20 folders, then on all (it skips
folders that are already done, so it can be stopped with Ctrl+C and started
again):
```bash
python -m runoffwatch rerun --exe C:\Temp\X3MZI0OQ2D67EUQHFZ\WINPRZM.exe --limit 20
python -m runoffwatch rerun --exe C:\Temp\X3MZI0OQ2D67EUQHFZ\WINPRZM.exe
```
It copies each run folder from `data/raw/runs/`, sets the Henry constant to
`0.37E-06` and the reference soil moisture to `1` in the `.inp` file (changing
only those characters), points the two `PATH` lines of `Run 1.run` at a short
work folder (default `C:\Temp\rr`), starts `WINPRZM.exe` and stores the result
in `data/raw/runs_fixed/` in the same layout as the originals, with a log in
`rerun_log.csv`. `--henry keep` or `--moisture-ref keep` leaves one setting as
delivered. Afterwards the other commands are pointed at the new folder, for
example `python -m runoffwatch qc --runs data/raw/runs_fixed --out data/interim_fixed`.

For extra copies with varied spray dates and dose (section 8.1; done on
25 Nov for all fields), again first a test on 10 fields (20 runs):
```bash
python -m runoffwatch rerun --exe C:\Temp\X3MZI0OQ2D67EUQHFZ\WINPRZM.exe --variants 2 --limit 10
python -m runoffwatch rerun --exe C:\Temp\X3MZI0OQ2D67EUQHFZ\WINPRZM.exe --variants 2
```
Results go to `data/raw/runs_varied/`, the plan to `rerun_plan.csv`. Options:
`--variants` (copies per field), `--spray-windows` (default
`15.02-30.04,01.10-30.11`), `--doses` (default `0.24,1.20,2.40` kg/ha),
`--seed` (fixes the random spray dates), `--limit` (only the first N fields).

Analysing these runs (method in 6.7; all steps below ran on 25 Nov; see
also the README, Part B). There is a third data set, `varied`
(`python -m runoffwatch --dataset varied ...`). Its feature table is built
from the corrected runs (sprayed on 1 March) plus the copies with varied
spray dates and doses, so the corrected data set must be done first. Its
models, results and figures go to `models/varied/`, `docs/results/varied/`
and `docs/figures/varied/`, so nothing of the corrected data set is
overwritten. The result folders made by `rerun --variants` come without the
weather file; `add-weather` puts each field's weather file into them and must
run before `inventory`:
```bash
python -m runoffwatch add-weather
python -m runoffwatch --dataset varied inventory
python -m runoffwatch --dataset varied qc
python -m runoffwatch --dataset varied audit
python -m runoffwatch --dataset varied features
python -m runoffwatch --dataset varied train
python -m runoffwatch --dataset varied train --cv
python -m runoffwatch --dataset varied france
```
**Since 26 Nov the saved models are frozen (6.12).** The `train` lines here and
in the next block are what was run on 25 Nov. Today `train` stops with "The
models in ... are frozen". To train again, add `--models <another folder>`.

**Memory (learned on 25 Nov):** the varied feature table has 24.6 million
rows. Training needs about 12 GB and must start in a fresh process: running
the feature build and the training in one process ran out of memory on a
15 GB machine. Run `features`, `train`, `train --cv` and `france` as separate
commands (22 min, 70 min and 22 min for the last three). The run tables are
read in one piece (`low_memory=False`), because pandas failed on about 10,000
runs with a column of mixed types. **Also learned on 25 Nov (evening):** the
feature build for the varied set needs about 12 GB too. Running anything else
that uses memory at the same time got it killed. Run the heavy steps alone,
one after the other.

**Applying the warm-up rule (5.2) to a data set** (this is what the rerun of
25 Nov, evening, did; first the varied, then the corrected data set; it has
finished). The last line is the 45-year run with spraying on 15 October; its
results go to `docs/results/varied/autumn/` and its figures to
`docs/figures/varied/autumn/` (6.6):
```bash
python -m runoffwatch --dataset varied audit      # writes clean_from into run_quality.csv
python -m runoffwatch --dataset varied features
python -m runoffwatch --dataset varied train
python -m runoffwatch --dataset varied train --cv
python -m runoffwatch --dataset varied france
python -m runoffwatch --dataset varied france --spray 15.10 --scenario autumn
```
For the corrected data set run the same steps with `--dataset corrected`
(the default, so the option can be left out), without the autumn line.

New options: `whatif --dose` (kg/ha, default 2.4), `france --spray DD.MM
--dose` (spray day and dose of every year, default 01.03 and 2.4 kg/ha),
`france --scenario NAME` (25 Nov, evening: results and figures go to a
sub-folder `NAME` and the field-year table gets `_NAME` in its file name, so
a second spraying does not overwrite the standard run; only letters, digits,
`-` and `_`), and a dose field in the app. `lstm` refuses the `varied` data
set (not adapted) and does not use the warm-up rule.

**Share-of-dose limit (26 Nov 2026, section 6.10):**
- `python -m runoffwatch train --cv` (and with `--dataset varied`) now also
  saves the held-out predictions next to the feature table:
  `data/processed/features_varied_cv_predictions.parquet` and
  `data/processed/features_fixed_cv_predictions.parquet`. These are data
  files and are never committed.
- `models.rescore_alarms(predictions_path, results)` scores the alarm table
  again from these saved predictions, in seconds, without training.
- `models.alarm_by_share_of_dose(P)` gives the alarm scores per limit, now
  also per held-out year and per spray season. The limits are in
  `SHARE_OF_DOSE_LIMITS_PCT`; the start value is
  `DEFAULT_SHARE_OF_DOSE_PCT = 0.1`.
- `whatif.predict_days` and `whatif.compare_spray_days` take
  `high_loss_pct_of_dose` (default 0.1). The limit in g/ha is in
  `.attrs["high_loss_limit_gha"]` of the result of `predict_days`.

**Frozen models and the command `check` (26 Nov 2026, section 6.12):**
- `models/FROZEN.json` holds the SHA-256 fingerprint of every model file
  and `meta.json` in `models/`, `models/varied/` and `models/delivered/`.
  `train` refuses to write into a frozen folder; `train --cv` still works.
  To train new models on purpose, use `--models <folder>`, or remove the
  folder from `models/FROZEN.json` deliberately and say so in the
  documents.
- Functions in `models.py`: `fingerprint`, `write_frozen`, `frozen_state`,
  `score_new_runs`.
- A fourth data set, `dosecheck` (in `paths.py`), is test-only: `train`,
  `lstm`, `design` and `france` are refused for it. Folders: runs
  `data/raw/runs_dosecheck/`, interim `data/interim_dosecheck/`, feature
  table `data/processed/features_dosecheck.parquet`, results
  `docs/results/varied/dose_check/`, figures
  `docs/figures/varied/dose_check/`. It tests the models in
  `models/varied/`. Steps: 8.3.
- New option `rerun --sample N`: only N fields, spread evenly over all
  fields (every k-th field), so all batches take part.
- The same `check` command is meant for the new fields from the Landau
  group later. Build a feature table of the new runs only, then:
```bash
python -m runoffwatch check --features <table> --models models/varied --results <folder>
```

Modules (`runoffwatch/`):

| File | Purpose |
|---|---|
| `przm_io.py` | Reads `.met`, `.ZTS`, `.OUT`, `mc.log`; converts units; sanity checks; `read_crop_emergences(inp)` reads the emergence dates of the crop cycles |
| `przm_inp.py` | Reads field / soil / pesticide settings from `.inp` |
| `batch.py` | Unpack, inventory, quality-check all runs in parallel |
| `quality.py` | Envelope rule, balance rule, Isolation Forest, causes of the breakdown; `warm_up_end` and the `clean_from` column of `run_quality.csv` (5.2) |
| `features.py` | Feature table; `weather_features` is shared by training and the advisor; `run_feature_rows(..., clean_from)` drops the warm-up period |
| `models.py` | Surrogate, classifier, baselines, split, leave-one-year-out evaluation; `load_features()` reads the feature table without a second copy; `alarm_by_share_of_dose`, `rescore_alarms` (6.10); `fingerprint`, `write_frozen`, `frozen_state`, `score_new_runs` (frozen models and `check`, 6.12) |
| `lstm.py` | LSTM surrogate and comparison (not adapted to varied spray dates or the warm-up rule) |
| `whatif.py`, `../app.py` | Advisor library, command line, Streamlit app (five tabs, 7.1); high-loss limit as a share of the dose (`high_loss_pct_of_dose`) |
| `appdata.py` | Helpers for the app: finds and reads result files safely, formats numbers; since 26 Nov also small helpers for the limit text, alarm lookup, season means and short scenario names (tested in `tests/test_app.py`) |
| `design.py` | Generator for new simulation runs |
| `rerun.py` | Runs PRZM again on Windows with the two corrected settings (`rerun` command; `--sample N` since 26 Nov) |
| `paths.py` | Default folders of the four data sets (`corrected`, `delivered`, `varied`, `dosecheck`) |
| `longrun.py` | Surrogate on 45 years of Agri4Cast weather for France (`france` command); the comparison with PRZM leaves out field-years that start before `clean_from` |
| `figures.py`, `report.py` | Figures; single-run report |
| `pipeline.py`, `plots.py`, `przm_spikes.py`, `examples/` | Earlier exploration code |

Other folders: `models/` (trained LightGBM models, about 2 MB; corrected
1 March data), `models/varied/` (models of the varied data set, used by the
app when present), `models/FROZEN.json` (fingerprints of the frozen
models, 6.12), `docs/` (reports, figures, result tables; the subfolders
`delivered/` and `varied/` of `docs/results/` and `docs/figures/` hold the
other two data sets), `tests/` (synthetic run folders only), `data/` (local,
never committed).

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
2. One pesticide, one crop, one crop calendar (emergence always 12 Nov).
   Spray date and dose vary only in the varied data set: two windows
   (15 Feb–30 Apr, 1 Oct–30 Nov) and three doses. The spray-date effect
   follows the fixed emergence date of the scenario (6.8).
3. Field edge only; daily resolution.
4. The delivered pesticide results were wrong in all runs (two wrong input
   settings, section 5.1); all results are now from the corrected re-run.
   1,335 fields cannot be calculated by PRZM and are missing. All of them
   have a zero in their input file (a soil water or density value, the
   erodibility or the slope), which looks like missing soil or terrain data;
   no field without such a zero fails. So the sample is no longer a clean
   random sample of the real fields.
5. The total loss is close over all years (0.985 times PRZM's on the varied
   data, 0.948 on the 1 March data), but single unseen years are up to 17 %
   off (1997, 1 March data); about one high-loss day in ten is missed
   (recall 92.6 % on the varied data, 88.0 % on the 1 March data). Autumn
   spraying is slightly harder to predict than spring spraying (loss R²
   0.962 against 0.976).
6. Small effective sample: ten years of weather from one region, and with
   the warm-up rule only nine of them in the year-by-year test.
7. The LSTM result rests on one test on two years, and the LSTM is not
   adapted to varied spray dates or to the warm-up rule.
8. Extreme rain: tree models cannot predict beyond the largest values they
   were trained on. On the 127 rain days with at least 80 mm the plain
   curve-number formula is better than the surrogate (R² 0.85 against 0.75;
   6.9). In 1998 one storm (3 Nov, up to 153 mm) gave 87 mm predicted
   runoff where PRZM gives 136 mm.
9. The first simulated year is a warm-up with an irregular crop (6.9). It is
   left out by our rule; whether this is intended is not confirmed by the
   model owner in Landau. The surrogate has no canopy input; the spray date
   stands in for it.
10. Both corrections (Henry constant 0.37E-06, reference soil moisture 1) are
   the team's reading of the evidence from 30 test runs. The model owner in
   Landau has not confirmed them yet.
11. The Flufenacet Henry value was taken from search-result snippets of the
   PPDB and PubChem entries; the pages themselves could not be opened from our
   environment, so the value should be checked once more.
12. The limit for a "high-loss day" is our own choice. A fixed limit of
   1 g/ha cannot hold across compounds (section 5), so the app and the alarm
   scores now use a share of the dose (6.10). The start value of 0.1 % is not
   an official limit; which share is serious for which compound group is
   still open. The classifier, the alarm columns of `cv_by_year.csv`, two
   figures and the 45-year high-loss-day counts still use the fixed limit of
   1 g/ha. Runoff and loss-amount scores do not depend on the limit.
13. Low-dose compounds (a few g/ha) are outside the dose range of the runs
   (0.24–2.4 kg/ha). The dose box in the app is limited to the dose range the
   loaded models were trained on (7.1). A spray day outside the trained
   windows can still be chosen; the app warns, and the result is a guess.
14. 1991 is the weakest year of the 1-March-only models (loss R² 0.867),
   because it is the only year with heavy runoff on the spray day itself.
   This is a limit of data with one fixed spray date (6.11).
15. **There is no untouched final test set.** In the year-by-year test every
   year 1991–1999 was a test year once. The final models (the ones the app
   uses) are trained on all rows, so they cannot be tested themselves; their
   expected accuracy is the year-by-year score. Choices such as the warm-up
   rule and the model settings were made after seeing these scores. So the
   scores may be slightly optimistic. How much was not measured. What does
   protect the scores: in each round the test year and the weather files of
   the test fields were not used for training, and the year used to decide
   when to stop training was a different year from the test year. The single
   split (6.3) is not an independent second test, because its test years
   1992 and 1996 are also test years of the year-by-year test. Since
   26 Nov 2026 the models are frozen (6.12), so a later test on new runs is
   honest. The 0.6 kg/ha check tests the dose only; it does not replace an
   independent test with new fields.

---

## 13. Status and next steps

State on 26 Nov 2026 (share-of-dose limit in the app and in the scores;
app redesigned; models frozen).

Done: data audit; surrogate with honest evaluation; classifier, SHAP ranking,
risk table; advisor prototype; LSTM comparison; surrogate on 45 years of
weather; generator for new runs; related-work review; reports; two slide
decks. New since 17 Nov:
- PRZM runs locally on the owner's Windows PC (about 3 s per field).
- The cause of the broken numbers is found: two wrong input settings (Henry
  constant and reference soil moisture), shown with 30 test runs (5.1).
- The full re-run is done (23 Nov, 1.5 hours on the owner's PC): of 6,958
  folders with inputs, 5,610 finished (all 3,958 that had results before,
  plus 1,652 that had none), 1,335 stop with a PRZM calculation error, 13
  have damaged input files. The command stops a failing run by itself (log
  status `przm_error`).
- The corrected results are checked (PRZM's balance is exact in all 5,609
  full runs), the models are retrained and retested on the corrected data
  (both the leave-one-year-out test and the single split, the LSTM
  comparison and the 45-year run), and the reports are rewritten with the
  corrected numbers. The delivered-data results are kept in
  `docs/results/delivered/` and `docs/figures/delivered/`.
- Tool for varied spray dates and doses (`rerun --variants`, section 8.1)
  run on a 20-run trial with the real program. 18 runs finished and were
  checked: spray days and dose as planned, balance clean.
- Analysis side adapted to varied spray dates and doses (6.7, section 10)
  and smoke-tested end to end on those 18 runs plus base fields (23 Nov).
- **The full varied run is done and analysed (25 Nov):** 11,218 runs from
  the owner's PC transferred (one zip per batch folder, unpacked to
  `data/raw/runs_varied/<batch>/<field>__vN/`); 11,209 usable, 9 zero-filled
  files left out (8.1). Unpacking, checks, feature table, training,
  year-by-year test and 45-year run all ran (6.6, 6.7). The spray-date
  pattern is explained by the crop calendar of the scenario (6.8).
- Code made to handle the 24.6-million-row table, and `rerun.is_done` now
  rejects zero-filled result files (section 10, 8.1).
- **Done (25 Nov, evening): held-out year 1990 investigated.** Cause: the
  first simulated year is a warm-up with an irregular crop (the first crop
  cycle starts before the simulation), so 1990 was not a fair test (6.9).
  1998 is decided by one extreme storm (6.9). The warm-up rule is in the code
  (5.2; 567 tests passed then). Option `france --scenario` added. The runoff
  model as a correction of the curve-number formula was tried and rejected
  (6.9).
- **Done (25 Nov, late evening): rerun with the warm-up rule.** Feature
  table, training, year-by-year test and 45-year run for 1 March and for
  15 October on the varied data set; the same steps (without the autumn run)
  on the corrected 1-March-only data set. The year-by-year test has nine
  years (1991–1999). All scores in this file are updated (top box, 4, 6.4,
  6.6, 6.7, 6.8); the 15 October results are in
  `docs/results/varied/autumn/` (6.6).
- **App rewritten** with five tabs (7.1).
- **Answered by the environmental-science side:** a fixed g/ha limit for a
  high-loss day cannot hold across compounds (section 5).
- **Done (26 Nov): high-loss limit as a share of the dose** in the app
  (start value 0.1 %, adjustable) and in the alarm scores, for both data
  sets, overall, per dose, per held-out year and per spray season (6.10).
  No retraining was needed: the scores come from the saved held-out
  predictions (`rescore_alarms`, section 10).
- **Done (26 Nov): dose check.** PRZM's loss scales with the dose between
  0.24 and 1.2 kg/ha (6.10).
- **Done (26 Nov): weak year 1991** of the 1-March-only models explained
  (6.11).
- **Done (26 Nov): app redesigned** (7.1), and the start failure on Windows
  fixed (section 10).
- **Done (26 Nov): dose box limited to the trained range** (7.1), and the
  honesty statement about the test written down (6.3, limit 15 in
  section 12). 576 tests passed then.
- **Done (26 Nov): models frozen, `check` command ready** (6.12). The
  test-only data set `dosecheck` and `rerun --sample` were added, and the
  whole chain was rehearsed on 40 existing run folders. 594 tests pass.
- **Done (27 Nov): the 0.6 kg/ha dose check was run and passed** (6.12).
  It tests the dose only. The result files are in the repository and the
  per-year scores were checked: no weak year.

Next, in this order:
1. Look at the storm days behind the 1993 and 1998 totals (6.12): the copy
   is 6 % too high and 7 % too low there, also on runs whose fields and
   weather it knows.
2. Ask the Landau group for a small batch of new PRZM runs the models have
   never seen, as an independent test: for example a middle dose such as
   0.6 kg/ha and some new fields. This would give the first score on data
   that played no part in any choice (limit 15 in section 12). The models
   are frozen (6.12), and the same `check` command will score those runs
   (section 10).
3. The default dose in the app stays 2.4 kg/ha until the
   environmental-science side confirms the realistic dose for Flufenacet. A
   question about this has been put to them.
4. Which share of the dose is serious for which compound group. This is for
   the environmental-science side, which is working on a classification by
   compound group. 0.1 % is only our starting value.
5. The classifier still uses the fixed limit of 1 g/ha. Retrain it with a
   share-of-dose label, or drop it: with the fixed limit it was about as
   good as the predicted loss amount (PR-AUC 0.975 against 0.973), so it
   adds little (6.10).
6. The 45-year high-loss-day counts (6.6), the alarm columns of
   `cv_by_year.csv` and the figures `m3_high_loss_precision_recall.png` and
   `m7_scores_by_held_out_year.png` still use the fixed limit of 1 g/ha.
7. `docs/figures/app_screenshot.png` was renewed on 26 Nov 2026; make a new
   one after the next change of the app.
8. Ask the model owner in Landau (through the team member in Landau) whether
   the first crop cycle starting before the simulation is intended, and
   whether a warm-up year is normally discarded (6.9).
9. Ask the environmental-science side whether the fixed emergence date
   (12 Nov) and autumn spraying before emergence are realistic use. The
   spray-date result and the 15 October run depend on it (6.6, 6.8).
10. Extreme rain days: on the 127 days with at least 80 mm the plain formula
   beats the surrogate (6.9). The "correction of the formula" idea did not
   help; another approach is still open.
11. LSTM: adapt it to varied spray dates and doses and to the warm-up rule,
   or drop it. Until then its numbers (6.5) are from the 1 March data and
   include the warm-up period.
12. Other questions for the model owner in Landau (section 5): the Henry
   constant, the reference soil moisture, whether 2.4 kg/ha is the intended
   dose (it looks about ten times higher than usual field rates,
   unconfirmed, section 8.1), and where the zeros in the inputs of the 1,335
   failing fields come from (and whether they can be filled).
13. Rewrite the reports with the spray-date and dose results and the warm-up
   rule.
14. Presentation 2, with the corrected and the varied numbers (with the
   warm-up rule). It should also
   correct the statement from the first progress presentation that 73 % of
   the data can be trusted: the plausibility check kept 73 % of the
   run-years, but those were wrong too.
15. Before any submission of new runs to Landau: confirm the corrected settings
   that `design.py` now writes (Henry 0.37E-06, reference soil moisture 1; 8.2).

Still open from before:
- Check a sample of the 45-year predictions against PRZM runs on the same
  weather.
- Team member in Landau: check whether the new driver ranking (now with dose
  in third place, 6.7) makes physical sense.
- Verify the related-work entries; write the report; final slides.
- Unknown: the course deadline.

---

## 14. Glossary

| Term | Meaning |
|---|---|
| Runoff | Water flowing off the soil surface after rain |
| Pesticide loss | Pesticide leaving the field with runoff water, in g/ha per day |
| Rain day | Day with at least 1 mm rain |
| High-loss day | In the app and the alarm scores since 26 Nov: day on which the field loses at least a chosen share of the dose (start value 0.1 %, adjustable; 6.10). Before, and still in the classifier and some result files: at least 1 g/ha (fixed limit) |
| Application year | 1 March to end of February (in the delivered and corrected data spraying is on 1 March; the year-by-year test uses these years for every data set) |
| Emergence date | Day the crop comes up in the PRZM scenario; fixed at 12 Nov for every field and year. Before it the curve number is higher (more runoff) |
| Warm-up period / `clean_from` | Start of every run until the first crop emergence inside the simulation (1 Jan to 12 Nov 1990), because the first crop cycle starts before the simulation. Left out by the warm-up rule (5.2); `clean_from` is its end date in `run_quality.csv` |
| Foliar application / canopy interception | Application method "2" in the input files: part of the dose lands on the crop canopy, in proportion to canopy cover (47 % for a 1 March spray). There it decays (half-life about 10 days) or is washed to the soil by rain |
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
| Henry constant | How easily the pesticide moves from soil water into the air; PRZM uses it as a dimensionless number. Delivered: 0.03 (wrong); corrected: 0.37E-06 |
| Reference soil moisture / moisture correction | PRZM slows decay in dry soil: rate × (moisture / reference moisture)^0.7. Delivered reference: 100 (wrong for this program, which counts field capacity as 1); corrected: 1 |
| Frozen models | Saved models whose files may no longer change; their fingerprints are in `models/FROZEN.json`. `train` refuses to overwrite them, so a later test on new runs is honest (6.12) |
| rerun | Our command that runs PRZM again on all folders with inputs, with the two corrected settings (`python -m runoffwatch rerun`) |
| Plausibility check / envelope rule | Our rule that removes run-years with impossible pesticide losses (section 5) |
