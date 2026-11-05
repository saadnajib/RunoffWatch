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
  processed/
    features.parquet                        (one row per rain day; step 4, not built yet)
```

Expected size: archives ~350 MB, unpacked runs ~8 GB, daily parquet ~1 GB.
