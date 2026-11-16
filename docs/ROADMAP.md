# RunoffWatch – Roadmap

Updated after the project presentation (4 Nov 2026), the first full run on
the real data (12 Nov 2026) and the second round of work (16 Nov 2026). Results so far: [DATA_REPORT.md](DATA_REPORT.md),
[MODEL_REPORT.md](MODEL_REPORT.md).

**What the supervisor asked for, and where it stands**

| Feedback from the presentation | Status |
|---|---|
| The surrogate model is what makes this project different; make it the core | First version trained and evaluated (Phase 4) |
| Frame it as a decision tool for farmers ("spray today or wait?") | Prototype works for spray-day comparison; product / dose comparison is **not possible with this data**; new runs are prepared (Phases 5 and 6) |
| Look into the extreme days and the odd decay numbers; ask Landau | Done: it is a numerical problem in the simulator, see DATA_REPORT.md. Questions for Landau are listed there |
| Check related work, find baselines to beat | First review in [RELATED_WORK.md](RELATED_WORK.md); two baselines implemented |
| Visualise the data | 11 figures in `docs/figures/` |

## Phase 0 – Repository setup ✅
Reader, tests, CI, data layout.

## Phase 1 – Get to know the data ✅
`extract`, `inventory`, `qc`. Answered: 3,958 usable runs (not 10,000); weather
and soil vary; pesticide, dose and spray date do not.

## Phase 2 – Task 1: which results can be trusted ✅ (first version)
`python -m runoffwatch audit`. Envelope rule per run and year, Isolation Forest
as a second opinion, analysis of which settings cause the breakdown.

Still to do:
- [ ] Send the questions in DATA_REPORT.md §4 to the Landau group (Sarah)
- [ ] Sarah reviews about 20 flagged and 20 unflagged runs by eye
- [ ] If Landau reruns the simulations without the volatilisation problem: rerun everything

## Phase 3 – Feature table ✅
`python -m runoffwatch features`. One row per rain day, 33 inputs, all from
weather, spray history and soil; nothing from PRZM output.

## Phase 4 – Tasks 2 + 3: surrogate and high-loss detection ✅ (first version)
`python -m runoffwatch train`. Two-stage surrogate (runoff x concentration),
high-loss classifier, baselines, SHAP ranking, risk calendar. Tested by leaving
out one year at a time, on weather files never used in training.

Still to do:
- [x] Leave-one-year-out evaluation (`train --cv`): scores now come with a range over nine years
- [x] Final models trained on all years
- [x] Underestimation of large losses reduced (concentration model now trained on amounts, not logarithms); not removed
- [x] Sequence model (LSTM) as a second surrogate, compared on the same test rows (`python -m runoffwatch lstm`)
- [ ] Year-by-year test for the LSTM (about 2 hours); if its lead holds, make it the main surrogate
- [ ] Look at the days where the surrogate is most wrong; are they special (snow, very long dry spells)?
- [ ] SHAP for the surrogate itself, not only for the classifier
- [ ] Sarah: do the driver ranking and the risk calendar make physical sense?

## Phase 5 – Farmer tool ✅ (prototype)
`streamlit run app.py` or `python -m runoffwatch whatif`. Compares candidate
spray days for a weather table and a soil.

Still to do:
- [ ] Feed real forecast weather (and Agri4Cast history for the 30 days before)
- [ ] Show uncertainty (for example a range from several forecast members)

## Phase 6 – New simulation runs (prepared, waiting for Landau)
`python -m runoffwatch design` writes the run files; see [NEW_RUNS_PLAN.md](NEW_RUNS_PLAN.md).
- [x] Generator for a designed experiment: spray date, dose, half-life and sorption varied; control
      group that changes only the Henry constant
- [ ] Agreement of the model owners; the spray date must be read from the run file on their side
- [ ] Submit, read the results with the existing pipeline, add dose / DT50 / Koc as model inputs
- [ ] Then the advisor can compare days, doses and substances

## Phase 6b – More weather (Agri4Cast)
- [x] The 695 weather files are Agri4Cast/MARS grid cells (confirmed by the project documentation)
- [ ] Run the surrogate on the 1979-2024 Agri4Cast weather for France from the project cloud:
      46 years of weather it has never seen

## Phase 7 – Report and presentation
- [ ] Report (Sarah: environmental part; Saad: methods)
- [x] Progress slides (16 Nov 2026): https://claude.ai/artifact/VzutykKbE1M1tja2ZrZHcj
- [ ] Final slides
- [ ] Verify the entries marked "[not verified]" in RELATED_WORK.md before citing them

## Open questions
- [ ] Answers from Landau (DATA_REPORT.md §4)
- [ ] Is "1 g/ha in one day" a sensible definition of a high-loss day? (Sarah)
- [ ] Course deadline
- [ ] New team member on the Kaiserslautern side?
