# RunoffWatch – Project Scope

**Course:** ETX8 Landscape-modelling project, RPTU Kaiserslautern-Landau, winter 2026/27
**Team:** Saad Najib (Computer Science) · Sarah [surname] (Environmental Science)
**Slides:** https://claude.ai/artifact/Y82phRAgCapMtktvPri94c
**Version:** 2, after the project presentation on 4 Nov 2026 and the first run on the full data

## One-sentence summary

We build a fast machine-learning surrogate of the PRZM pesticide model that
predicts, from daily weather and soil, how much pesticide is washed off a field
after spraying, and we use it for a spray-day advisor prototype.

## What changed after the presentation

| Feedback | Decision |
|---|---|
| The idea looks like the other two groups'. What is different? | The **surrogate model** is now the core of the project, not a bonus. The Landau side asked for one, and no published ML surrogate of PRZM was found (RELATED_WORK.md). |
| Make it useful for a farmer: "spray today or tomorrow?" | A what-if tool on top of the surrogate (prototype exists). |
| Could it also compare pesticide A with B, or doses? | **Not with the current data**: every run uses the same pesticide, dose and spray date. It needs new PRZM runs (requested from Landau). |
| The extreme days and decay numbers: bug or real? | Checked on all runs: it is a numerical problem in the simulator (DATA_REPORT.md). Data quality control became Task 1. |
| Check related work and baselines | RELATED_WORK.md; two baselines are implemented and compared. |

## Research questions

1. **Trust:** which simulation results are physically plausible, and can that be decided automatically?
2. **Surrogate:** how well can a machine-learning model reproduce PRZM's daily runoff and pesticide loss
   for weather and years it has never seen, and how much faster is it?
3. **Drivers:** which weather and soil conditions turn a rain day into a high-loss day, and when in the
   year is the risk highest?
4. **Use:** can the surrogate support a simple decision, such as choosing the spray day within a weather forecast?

## Data

About 10,000 run folders of the FOCUS PRZM model from the project cloud, of
which 3,958 contain results: 10 years (1990-1999) of daily weather, field and
soil settings, and daily runoff and pesticide loss. 695 different weather
files; slope and soil vary; pesticide (Flufenacet), dose (2.4 kg/ha), crop
(winter cereals) and spray date (1 March) are the same in every run.
Details and quality problems: [DATA_REPORT.md](DATA_REPORT.md).

## Tasks

### Task 1 – Data quality audit (done, first version)
Physical plausibility rule per run and year ("envelope rule"), Isolation
Forest as a machine-learning second opinion, and an analysis of which run
settings cause the breakdown. Output: a trusted subset and a list of
questions for the model owners.

### Task 2 – Surrogate of PRZM (core; first version done)
Two stages that follow the physics:

    runoff model          weather + soil                 -> mm of water running off
    concentration model   history since spraying + soil  -> g/ha of pesticide per mm runoff
    pesticide loss = runoff x concentration

Physics-informed: the textbook curve-number runoff is an input, so the model
only learns PRZM's soil-moisture correction. Compared against the curve-number
formula alone and a simple decay formula. Tested on weather files **and** years
kept out of training.

### Task 3 – High-loss days and their drivers (first version done)
Classifier for days with at least 1 g/ha pesticide loss; comparison with a
rain rule, logistic regression and the surrogate; SHAP ranking of the drivers;
risk calendar by month and by rain amount x time since spraying.

### Task 4 – Spray-day advisor (prototype done)
Streamlit app and command line: for a weather table and a soil, compare the
predicted loss for several candidate spray days.

### Task 5 – Extensions (if time allows)
Agri4Cast weather for other regions and years; a sequence model (LSTM) as a
second surrogate; new PRZM runs with varied spray date, dose and pesticide.

## Team roles

| Saad (Computer Science) | Sarah (Environmental Science) |
|---|---|
| Pipeline, quality audit, models, app | Contact with the Landau modelling group; questions in DATA_REPORT.md |
| Evaluation design, baselines | Does the driver ranking / risk calendar make physical sense? |
| Figures, repository, reproducibility | Literature; environmental interpretation; definition of "high-loss day" |

A third team member on the Kaiserslautern side may join (approved by the supervisor).

## Limits

- **Simulations, not measurements.** The surrogate reproduces PRZM. Nothing here was checked against field data.
- **One pesticide, one dose, one crop, one spray date.** Results hold for Flufenacet at 2.4 kg/ha on winter
  cereals sprayed on 1 March. The advisor is only meaningful for spraying in late winter / early spring.
- **Field edge only.** What happens in streams is out of scope (agreed with the supervisor).
- **Daily resolution.** As in PRZM.
- **Part of the pesticide results is unusable** because of a numerical problem in the simulator; about
  73 % of the simulated run-years are kept.
- **Ten years of regional weather.** The 695 weather files share the same storms, so there are far fewer
  independent weather events than rows. Scores differ noticeably from one held-out year to another.

## Deliverables

1. Data report with trusted subset and questions for the model owners
2. Surrogate model with evaluation against baselines
3. Driver ranking and risk calendar
4. Spray-day advisor prototype
5. Report, slides and re-runnable code in this repository
