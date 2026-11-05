# RunoffWatch – Roadmap

Step-by-step plan. Each phase ends with something we can show.
"High-loss day" = a day with an unusually large amount of pesticide leaving
the field (currently: top 10 % of all days with any loss; to be agreed with Sarah).

## Phase 0 – Repository setup ✅

- [x] Reader for one PRZM run folder, with sanity checks (`runoffwatch/przm_io.py`)
- [x] Single-run analysis and plots (`python -m runoffwatch run <folder>`)
- [x] Batch tools: `extract`, `inventory`, `qc` (`runoffwatch/batch.py`)
- [x] Installable package (`pip install -e ".[dev]"`), tests, CI on GitHub
- [x] Data folder layout (`data/README.md`); data never goes into git

## Phase 1 – Get to know the data (week 1)

1. Download the 10 `.7z` archives from the Drive into `data/raw/archives/`.
2. `python -m runoffwatch extract`
3. `python -m runoffwatch inventory` → **what differs between the runs?**
   - one weather file for all runs → the model can only learn the effect of *field settings*
   - many weather files → it can learn the effect of *weather* too
   - check whether the **spraying date** varies (needed for any "when to spray" advice)
4. `python -m runoffwatch qc` → how many runs are unstable, have log errors, broken mass balance.
5. Meet Sarah: go through the inventory and QC results; agree on the high-loss definition.

**Output:** a one-page data report: what varies, how many runs are usable.

## Phase 2 – Task 1: find broken runs automatically (week 2)

1. Per-run features from `runs_qc.csv` and the yearly soil-decay series (growth rate, last-year value, loss/applied ratio, ...).
2. Physical rules first (they are explainable): blow-up, mass balance, weather mismatch.
3. Isolation Forest on the per-run features to find runs that are odd in ways the rules miss.
4. Sarah reviews ~20 flagged and ~20 unflagged runs: is "odd" really "wrong"?

**Output:** `clean_runs.csv` + a short report on broken runs (useful for the whole project group).

## Phase 3 – Feature table (week 3)

1. One row per rain day (≥ 1 mm) per clean run: rain today, last 1–3 days, last 7 days, days since spraying, month, temperature, field settings that vary (from the inventory).
2. Label: high-loss day yes/no (classification) and loss in g/ha (regression).
3. Check how often runoff happens on dry days (snowmelt) before dropping dry days.
4. **Split train/test by run, not by row.** Rows from the same run are near-copies; a row split would give falsely good scores.

**Output:** `data/processed/features.parquet` (~14 million rows).

## Phase 4 – Task 2: predict high-loss days (weeks 4–6)

1. Baseline: logistic regression.
2. Main model: gradient-boosted trees (LightGBM).
3. Metrics: precision, recall, PR-AUC on unseen runs (not accuracy: high-loss days are ~1 % of rain days).
4. SHAP: ranking of drivers; check with Sarah that it makes physical sense.
5. Risk calendar: high-loss risk by month and condition.

**Output:** model, driver ranking, risk calendar, plots for the report.

## Phase 5 – Task 3: emulator (weeks 7–8, if time allows)

1. Regression model for daily pesticide loss from the same daily inputs.
2. Validate on runs the model has never seen.
3. Run it with Agri4Cast weather for other regions / recent years.

**Output:** emulator + a risk map or table for other places/years.

## Phase 6 – Farmer app prototype (stretch goal)

A small demo (e.g. Streamlit): enter a weather forecast and a planned spraying date → risk of high loss.
Only possible if Phase 1 shows that the spraying date varies between runs;
otherwise the app can show *risky days after spraying*, but not *when to spray*.
It also needs forecast weather as input, not past weather.

## Phase 7 – Report and presentation (week 9)

Report (Sarah leads the environmental part, Saad the methods), final slides, tagged code release.

## Open questions

- [ ] What differs between the 9,977 runs? (Phase 1, `inventory`)
- [ ] How many runs are numerically broken? (Phase 1, `qc`)
- [ ] Is the `runoff_grd.tif` error in `mc.log` in every run? (Phase 1, `qc` → `n_log_errors`)
- [ ] Definition of a high-loss day (with Sarah)
- [ ] Course deadline
