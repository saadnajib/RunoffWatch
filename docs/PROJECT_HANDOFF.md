# RunoffWatch – full project handoff

Paste this whole file into a new chat with an AI assistant so it knows the
project. It is written to be read without any other context. State as of
25 November 2026, late evening (first written 17 November 2026).

**How to use this with an assistant:** it cannot see the code or the data, only
this text. When you ask for code changes, paste the relevant file from the
repository as well. Numbers below marked "measured" come from running the code
on the full data; do not let an assistant change them from memory.

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
>   year-by-year test, which now has nine held-out years (1991–1999). 565
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
  side answered that a fixed g/ha limit cannot hold across compounds; it
  will become a share of the dose (section 13).
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

How it works in the code (merged on the branch; 565 tests pass):
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
the dose and adjustable (section 13). Runoff and loss-amount scores do not
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

### 6.4 Results (measured on the corrected data with the warm-up rule; nine held-out years 1991–1999 pooled, range over the years in brackets)

Files: `docs/results/cv_summary.json` and `docs/results/cv_by_year.csv`.
1,637,018 rain days scored; 5,155 high-loss days on 143 dates.

| | Surrogate | Baseline |
|---|---|---|
| Water runoff, daily R² | 0.986 (0.954–0.993) | 0.940 (0.829–0.967), curve-number formula; beaten in all 9 years |
| Pesticide loss, daily R² | 0.948 (0.867–0.986) | −0.24 (−13.6 to 0.85) |
| Sum of all loss, surrogate / PRZM | 0.948 (0.831–1.086) | – |
| High-loss days, PR-AUC | 0.965 (0.920–0.992) | rain today 0.108; classifier 0.954 (0.924–0.987) |
| Alarm "predicted loss ≥ 1 g/ha" | 4,948 alarms, 91.7 % real, 88.0 % of high-loss days found (80.1–97.7 % by year) | – |
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
  | High-loss days per field-year (same periods) | 0.42 / 0.47 / 0.59 | 1.73 / 2.15 / 2.04 |
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
- **High-loss day:** unchanged, at least 1 g/ha lost in one day.
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
0.970, logistic regression 0.799, rain rule 0.081. Alarm at 1 g/ha: 3,819
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

---

## 7. The spray-day advisor (Task 4, prototype)

- `python -m runoffwatch whatif` (command line) and `streamlit run app.py`.
- Input: a daily weather table (`date, rain_mm, temp_c`, optional
  `pan_evap_mm`; about 30 days of history plus the forecast) and a soil.
- Output: for each candidate spray day, the predicted pesticide loss in the
  following 14 days, and the number of predicted high-loss days. Only
  candidates with a full window are ranked.
- A dose can be given (`whatif --dose`, a field in the app). The app uses the
  models in `models/varied` when that folder exists (trained on varied spray
  dates and doses, 6.7); otherwise the 1 March models in `models/`, which scale
  another dose in proportion, and a note says so.
- **Limits:** valid only for Flufenacet on winter cereals, inside the two
  spray windows the models were trained on (15 Feb–30 Apr, 1 Oct–30 Nov).
  The autumn effect comes from the fixed emergence date of the PRZM scenario
  (6.8). It cannot compare products. It has not been evaluated as a decision
  tool.

### 7.1 The app (rewritten 25 Nov 2026)

- **Five tabs:** Compare spray days (the advisor above); How good is the
  copy?; Spray date; 45 years of French weather (choose 1 March or
  15 October, or compare both); About and limits.
- **Files:** `app.py` (the Streamlit page), `runoffwatch/appdata.py` (finds
  and reads the result files, formats numbers; plain Python, so it can be
  tested), `tests/test_app.py` (tests, also with missing or broken result
  files and without models).
- **Needs Python 3.10 or newer.** Start from the repository root:
  `pip install -e ".[app]"`, then `streamlit run app.py`.
- It reads the models and the result tables in the repository at run time
  (`models/`, `docs/results/`, `docs/figures/`). No simulation data is
  needed. When a result file is missing or half-written, the tab shows
  "Not available yet" instead of failing; reload the page later.
- **Not verified:** the page layout in a narrow browser window (for example
  on a phone). `docs/figures/app_screenshot.png` still shows the old app; do
  not use it for the new one.

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
python -m pytest -q             # 565 passed (25 Nov, with PyTorch installed)
python -m runoffwatch whatif
streamlit run app.py
```

Full pipeline from the raw data (put the ten archives in `data/raw/archives/`):

| # | Command | What it does | Time |
|---|---|---|---|
| 1 | `python -m runoffwatch extract` | Unpacks the archives | 1 min |
| 2 | `python -m runoffwatch inventory` | Finds what differs between runs | 5 s |
| 3 | `python -m runoffwatch qc` | Reads and checks every run | 1 min |
| 4 | `python -m runoffwatch audit` | Task 1: which results are trusted; with trust rule `balance` it also writes the warm-up end `clean_from` (5.2) | 30 s |
| 5 | `python -m runoffwatch features` | Builds the feature table | 2 min |
| 6 | `python -m runoffwatch train` | Trains surrogate and classifier, saves final models | 3 min (`varied`: 22 min, about 12 GB memory) |
| 7 | `python -m runoffwatch train --cv` | Leave-one-year-out evaluation | 25–30 min (`varied`: 70 min) |
| – | `python -m runoffwatch lstm` (needs `pip install -e ".[lstm]"`) | LSTM vs trees | 12–20 min |
| – | `python -m runoffwatch france` | Surrogate on 45 years of France weather; `--spray DD.MM`, `--dose`, `--scenario NAME` (own sub-folder, see below) | 8 min (`varied`: 22 min) |
| – | `python -m runoffwatch design` | Run files for new simulations | 1 min |
| – | `python -m runoffwatch rerun --exe ...` (Windows only) | Runs PRZM again on every folder with inputs, with the two corrected settings; with `--variants N`, N extra copies per field with varied spray dates and dose (`--spray-windows`, `--doses`, `--seed`) | about 1.5 h for 6,958 folders, four at a time; `--variants 2`: about 2.6 h for 11,218 runs |

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

Modules (`runoffwatch/`):

| File | Purpose |
|---|---|
| `przm_io.py` | Reads `.met`, `.ZTS`, `.OUT`, `mc.log`; converts units; sanity checks; `read_crop_emergences(inp)` reads the emergence dates of the crop cycles |
| `przm_inp.py` | Reads field / soil / pesticide settings from `.inp` |
| `batch.py` | Unpack, inventory, quality-check all runs in parallel |
| `quality.py` | Envelope rule, balance rule, Isolation Forest, causes of the breakdown; `warm_up_end` and the `clean_from` column of `run_quality.csv` (5.2) |
| `features.py` | Feature table; `weather_features` is shared by training and the advisor; `run_feature_rows(..., clean_from)` drops the warm-up period |
| `models.py` | Surrogate, classifier, baselines, split, leave-one-year-out evaluation; `load_features()` reads the feature table without a second copy |
| `lstm.py` | LSTM surrogate and comparison (not adapted to varied spray dates or the warm-up rule) |
| `whatif.py`, `../app.py` | Advisor library, command line, Streamlit app (five tabs, 7.1) |
| `appdata.py` | Helpers for the app: finds and reads result files safely, formats numbers (tested in `tests/test_app.py`) |
| `design.py` | Generator for new simulation runs |
| `rerun.py` | Runs PRZM again on Windows with the two corrected settings (`rerun` command) |
| `longrun.py` | Surrogate on 45 years of Agri4Cast weather for France (`france` command); the comparison with PRZM leaves out field-years that start before `clean_from` |
| `figures.py`, `report.py` | Figures; single-run report |
| `pipeline.py`, `plots.py`, `przm_spikes.py`, `examples/` | Earlier exploration code |

Other folders: `models/` (trained LightGBM models, about 2 MB; corrected
1 March data), `models/varied/` (models of the varied data set, used by the
app when present), `docs/` (reports, figures, result tables; the subfolders
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
12. The 1 g/ha limit for a "high-loss day" is our own choice. The
   environmental-science side answered that a fixed g/ha limit cannot hold
   across compounds (section 5). It will become a share of the dose. The
   classifier and alarm scores depend on the limit; runoff and loss-amount
   scores do not.
13. Low-dose compounds (a few g/ha) are outside the dose range of the runs
   (0.24–2.4 kg/ha).

---

## 13. Status and next steps

State on 25 Nov 2026, late evening (rerun with the warm-up rule finished).

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
  (5.2; 565 tests pass now). Option `france --scenario` added. The runoff
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

Next, in this order:
1. Change the high-loss limit from a fixed 1 g/ha to a share of the dose,
   and make it adjustable. Reason: doses of different compounds differ by a
   factor of 100 or more, so a fixed g/ha limit cannot hold across compounds.
   In our runs 1 g/ha is 0.42 %, 0.083 % and 0.042 % of the three doses.
   Runoff and loss-amount scores do not change; classifier and alarm scores
   do.
2. Score the alarm (precision, recall) at several share-of-dose limits, on
   the varied data set, overall and per dose.
3. Check that the loss scales with the dose: the surrogate assumes loss per
   kg sprayed (6.7). Compare the three doses in PRZM's own results.
4. Ask the model owner in Landau (through the team member in Landau) whether
   the first crop cycle starting before the simulation is intended, and
   whether a warm-up year is normally discarded (6.9).
5. Ask the environmental-science side whether the fixed emergence date
   (12 Nov) and autumn spraying before emergence are realistic use. The
   spray-date result and the 15 October run depend on it (6.6, 6.8).
6. Extreme rain days: on the 127 days with at least 80 mm the plain formula
   beats the surrogate (6.9). The "correction of the formula" idea did not
   help; another approach is still open.
7. LSTM: adapt it to varied spray dates and doses and to the warm-up rule,
   or drop it. Until then its numbers (6.5) are from the 1 March data and
   include the warm-up period.
8. Other questions for the model owner in Landau (section 5): the Henry
   constant, the reference soil moisture, whether 2.4 kg/ha is the intended
   dose (it looks about ten times higher than usual field rates,
   unconfirmed, section 8.1), and where the zeros in the inputs of the 1,335
   failing fields come from (and whether they can be filled).
9. Rewrite the reports with the spray-date and dose results and the warm-up
   rule.
10. Presentation 2, with the corrected and the varied numbers (with the
   warm-up rule). It should also
   correct the statement from the first progress presentation that 73 % of
   the data can be trusted: the plausibility check kept 73 % of the
   run-years, but those were wrong too.
11. Before any submission of new runs to Landau: confirm the corrected settings
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
| High-loss day | Day with at least 1 g/ha pesticide loss (to become a share of the dose, section 13) |
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
| rerun | Our command that runs PRZM again on all folders with inputs, with the two corrected settings (`python -m runoffwatch rerun`) |
| Plausibility check / envelope rule | Our rule that removes run-years with impossible pesticide losses (section 5) |
