# data/

Nothing in this folder is committed to git except this file.

```
data/
  raw/
    archives/   the 10 .7z files from the project Drive (run_000000_to_000999__*.7z, ...)
    runs/       unpacked run folders        <- python -m runoffwatch extract
  interim/
    inventory_runs.csv                      <- python -m runoffwatch inventory
    inventory_varying_inp_lines.csv
    runs_qc.csv                             <- python -m runoffwatch qc
    daily/<run>.parquet                     (one daily table per run)
    run_quality.csv                         <- python -m runoffwatch audit
  processed/
    features.parquet                        <- python -m runoffwatch features
```

Size: archives 350 MB, unpacked runs 3.7 GB, daily parquet 0.5 GB, features 0.15 GB.
