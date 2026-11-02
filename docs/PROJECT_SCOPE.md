# RunoffWatch – Project Scope

**Course:** ETX8 Landscape-modelling project, RPTU Kaiserslautern-Landau, winter 2026/27
**Team:** Saad Najib (Computer Science) · Sarah [surname] (Environmental Science)
**Slides:** https://claude.ai/artifact/Y82phRAgCapMtktvPri94c

## One-sentence summary

We use machine learning on about 10,000 pesticide-runoff simulations to learn
when rain turns into a pollution spike, and when it does not.

## The problem

A farmer sprays a pesticide on a field. Later, a heavy rain produces surface
runoff, and the water carries pesticide into the nearest stream. Most of the
pesticide that reaches a stream in a year arrives on only a handful of days.
The hard part is knowing which days.

## Research question

Given that it rains today, can a computer predict whether pesticide will be
washed off the field, and how much?

1. **When?** How much rain, how soon after spraying, in which season.
2. **When not?** Which heavy-rain days stay harmless, and why.
3. **How much?** Can a fast model estimate the amount without running the full
   simulation?

## Data

| | |
|---|---|
| Source | FOCUS PRZM simulation runs from the project cloud (xLandscape / xOffFieldSoilRisk) |
| Size | 9,977 runs × 10 years (1990–1999) of daily values ≈ 36 million field-days |
| Inputs per run | daily weather (rain, temperature, wind, sunshine, evaporation); field settings (crop, soil, pesticide, spraying date) |
| Outputs per run | daily water runoff, eroded soil, pesticide washed off the field |

The simulator is the official EU model for pesticide runoff. The data are
simulations, not river measurements (see Limits).

### What a first look at one run shows

- 1,412 rain days in 10 years, but only 152 produced any runoff.
- 85 % of the pesticide lost in 10 years left the field on just 5 days.
- Under 5 mm of daily rain, runoff never happens; over 20 mm, it always
  happens; between 5 and 15 mm the answer is "sometimes". That zone is where
  machine learning is needed.
- The run is **numerically broken**: yearly soil decay grows from 0.17 to
  1.3 million while the same dose is sprayed every year. Its pesticide results
  are unusable. Nobody knows yet how many of the 9,977 runs share this problem.

## Machine-learning tasks

### Task 1 – Find broken simulations automatically (unsupervised)

Anomaly detection (e.g. Isolation Forest) on each run's yearly summaries, plus
physical sanity rules such as "pesticide lost may not exceed pesticide
applied". Output: a clean list of trustworthy runs and a report on how many
were broken and why. Done first, because every later result depends on it.

### Task 2 – Predict "spike or no spike" for every rain day (supervised classification)

- **Features:** rain today and the last 3 days, rain in the previous week (soil
  wetness), days since spraying, month, temperature, field settings.
- **Models:** logistic regression as baseline, then gradient-boosted trees
  (XGBoost / LightGBM).
- **Explanation:** SHAP values, so every prediction comes with its reasons.
- **Output:** spike risk per day, ranking of the weather drivers, a seasonal
  "risk calendar".
- **Metric:** precision and recall for the rare spike days, not plain accuracy.

### Task 3 – A fast emulator of the simulator (supervised regression, stretch goal)

Train a regression model (gradient boosting or a small neural network) to
predict how much pesticide leaves the field from the same inputs the simulator
uses. The simulator needs ~4 s per run; the emulator answers in milliseconds,
so thousands of what-if scenarios become possible (stronger storms, later
spraying, different field settings). Metric: agreement with the simulator on
unseen runs.

## Workflow

Raw runs → quality check (Task 1) → feature table (one row per rain day) →
models (Tasks 2, 3) → answers (drivers, risk calendar, what-ifs).

Already built: a Python package (`runoffwatch/`) that reads one run folder,
converts units, runs sanity checks and flags spike days. It found the broken
run on its first use.

Tools: Python, pandas, scikit-learn, XGBoost/LightGBM, SHAP, matplotlib.

## Team roles

| Saad (Computer Science) | Sarah (Environmental Science) |
|---|---|
| Pipeline that reads and checks all runs | Meaning of the simulator settings |
| Feature table and the three ML models | Judging whether results make physical sense |
| Explainability and the risk calendar | Literature on runoff, pesticide fate, monitoring |
| Plots, repository, reproducibility | Environmental interpretation, written report |

## Plan

| Phase | Weeks | Work | Output |
|---|---|---|---|
| 1 | 1–2 | Read all runs, build the quality check (Task 1) | Clean data set, report on broken runs |
| 2 | 3–5 | Feature table, baseline classifier, boosted trees (Task 2) | Spike-risk model with precision/recall |
| 3 | 6–7 | Explain the model, risk calendar, interpretation | Ranked drivers, risk calendar, draft report |
| 4 | 8–9 | Emulator if time allows (Task 3), final report | Final report, code, presentation |

Phases 1–2 are the core and will be finished in any case. Weeks are
placeholders until the course deadline is known: [deadline].

## Limits

**Can:** show which weather and timing conditions lead to runoff spikes in the
official EU model; give a daily spike risk and a seasonal risk calendar; clean
up a large simulation data set for the whole group; answer what-if questions
quickly (if the emulator is built).

**Cannot:** prove what happens in a real river (simulations, not
measurements); resolve hours (the model works in whole days and puts runoff on
the same day as the rain); describe how pesticide travels downstream.

**Possible extension:** compare the model's "dangerous conditions" with
measured stream data (e.g. small-stream monitoring work in Landau) to test
whether the simulator matches reality.

## Deliverables

1. Clean data set with broken runs found automatically
2. Spike-risk model with the weather drivers ranked
3. Seasonal risk calendar
4. Report and re-runnable code in this repository
