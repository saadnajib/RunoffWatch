"""Where each data set lives. `python -m runoffwatch --dataset <name> ...` picks one.

corrected  the re-runs with the two corrected settings (made with `rerun`); the main data set
delivered  the simulations as delivered (wrong Henry constant and reference moisture); kept to
           show how the fault was found
varied     copies of the corrected runs with varied spray dates and doses (made with
           `rerun --variants`); its feature table also holds the corrected runs, which are the
           same fields sprayed on 1 March with the delivered dose

dosecheck  a test only, never for training: copies of some fields with a dose the models have
           not seen (0.6 kg/ha) and new spray dates, made with `--dataset dosecheck rerun`.
           The frozen models are scored on it with `check`. Fields and weather are NOT new.

Keys: `features_from` lists the interim folders that go into the feature table;
`fields_interim` is the interim folder that has one run per field (for the long run).
"""

DATASETS = {
    "corrected": {
        "runs": "data/raw/runs_fixed",
        "interim": "data/interim_fixed",
        "features": "data/processed/features_fixed.parquet",
        "models": "models",
        "results": "docs/results",
        "figures": "docs/figures",
        "france_out": "data/processed/france_field_years_fixed.parquet",
        "trust": "balance",
        "features_from": ["data/interim_fixed"],
        "fields_interim": "data/interim_fixed",
    },
    "delivered": {
        "runs": "data/raw/runs",
        "interim": "data/interim",
        "features": "data/processed/features.parquet",
        "models": "models/delivered",
        "results": "docs/results/delivered",
        "figures": "docs/figures/delivered",
        "france_out": "data/processed/france_field_years.parquet",
        "trust": "envelope",
        "features_from": ["data/interim"],
        "fields_interim": "data/interim",
    },
    "varied": {
        "runs": "data/raw/runs_varied",
        "interim": "data/interim_varied",
        "features": "data/processed/features_varied.parquet",
        "models": "models/varied",
        "results": "docs/results/varied",
        "figures": "docs/figures/varied",
        "france_out": "data/processed/france_field_years_varied.parquet",
        "trust": "balance",
        "features_from": ["data/interim_fixed", "data/interim_varied"],
        "fields_interim": "data/interim_fixed",
    },
    "dosecheck": {
        "runs": "data/raw/runs_dosecheck",
        "interim": "data/interim_dosecheck",
        "features": "data/processed/features_dosecheck.parquet",
        "models": "models/varied",                      # the frozen models that are tested; never written
        "results": "docs/results/varied/dose_check",
        "figures": "docs/figures/varied/dose_check",
        "france_out": "data/processed/france_field_years_dosecheck.parquet",
        "trust": "balance",
        "features_from": ["data/interim_dosecheck"],
        "fields_interim": "data/interim_fixed",
        "test_only": True,                              # train, lstm, design and france are refused
        "compare_with": "docs/results/varied/cv_summary.json",
        "what_is_new": "The dose (0.6 kg/ha, between the trained doses) and the spray dates. The fields, their "
                       "weather files and the years 1990-1999 were all in the training data, so this is a test of "
                       "the dose only, not an independent test.",
        # what `rerun` does for this data set unless told otherwise: one copy of 500 fields spread over
        # all fields, one dose, and a seed other than the training runs' so that the spray dates differ
        "rerun": {"variants": 1, "doses": "0.60", "seed": 2, "sample": 500},
    },
}

DEFAULT_DATASET = "corrected"
