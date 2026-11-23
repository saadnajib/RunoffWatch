"""Where each data set lives. `python -m runoffwatch --dataset <name> ...` picks one.

corrected  the re-runs with the two corrected settings (made with `rerun`); the main data set
delivered  the simulations as delivered (wrong Henry constant and reference moisture); kept to
           show how the fault was found
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
    },
}

DEFAULT_DATASET = "corrected"
