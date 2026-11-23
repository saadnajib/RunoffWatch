"""Where each data set lives. `python -m runoffwatch --dataset <name> ...` picks one.

corrected  the re-runs with the two corrected settings (made with `rerun`); the main data set
delivered  the simulations as delivered (wrong Henry constant and reference moisture); kept to
           show how the fault was found
varied     copies of the corrected runs with varied spray dates and doses (made with
           `rerun --variants`); its feature table also holds the corrected runs, which are the
           same fields sprayed on 1 March with the delivered dose

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
}

DEFAULT_DATASET = "corrected"
