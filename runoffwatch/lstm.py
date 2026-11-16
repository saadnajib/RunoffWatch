"""
A second surrogate of PRZM: a sequence model (LSTM), for comparison with the
gradient-boosted trees in models.py.

Why try it: PRZM is a day-by-day simulation with memory (soil water, pesticide
left in the soil). The tree surrogate gets that memory through hand-made
features ("rain in the previous 7 days", "rain since spraying"). An LSTM reads
the daily weather itself and has to learn the memory on its own. Published
surrogates of similar models mostly use LSTMs (see docs/RELATED_WORK.md).

One training sample = one run x one application year: the 59 days before
1 March (warm-up, so the network can build up a soil-moisture state) plus the
366 days after. Inputs per day: rain, temperature, evaporation, curve number,
curve-number runoff, days since spraying, and the run's soil settings.
Outputs per day: water runoff and pesticide loss.

The split is the same as for the tree models (models.split_rows): test =
test weather files in the application years 1992 and 1996; 1994 decides when
to stop training. Scores are computed on exactly the same rain-day rows, so
the two surrogates can be compared number by number.

Needs PyTorch (`pip install -e ".[lstm]"`). CPU is enough: about 20 minutes.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path

import numpy as np
import pandas as pd

from .features import HIGH_LOSS_GHA, curve_number_runoff, curve_number_today
from .models import TEST_APP_YEARS, VAL_APP_YEARS, _loss_scores, _regression_scores, split_by_weather
from .przm_inp import SOIL_FEATURES

log = logging.getLogger("runoffwatch")

WARMUP = 59                    # 1 January -> 1 March
LENGTH = WARMUP + 366          # days per sample
DYNAMIC = ["rain", "temp", "evap", "cn_today", "cn_runoff", "days_since_app"]
LOSS_SCALE = 10.0              # pesticide target = log1p(LOSS_SCALE * g/ha)


# --------------------------------------------------------------------------- #
# Data
# --------------------------------------------------------------------------- #
def run_sequences(daily: pd.DataFrame, cn: tuple, clean_until: pd.Timestamp, app_years: list[int]):
    """Cut one run's daily table into one sample per application year.

    Returns (X [n, LENGTH, 6], Y [n, LENGTH, 2], mask [n, LENGTH, 2], meta rows).
    mask[..., 0] = runoff target is valid, mask[..., 1] = pesticide target is trusted.
    """
    idx = daily.index
    rain = daily["rain_mm"].to_numpy(float)
    cn_today = curve_number_today(idx, cn)
    dsa = daily["days_since_app"].fillna(400.0).to_numpy(float)
    dyn = np.stack([np.log1p(rain), daily["temp_c"].to_numpy(float) / 10.0,
                    daily["pan_evap_mm"].to_numpy(float) / 5.0, cn_today / 100.0,
                    np.log1p(curve_number_runoff(rain, cn_today)), np.minimum(dsa, 400.0) / 365.0], axis=1)
    tgt = np.stack([np.log1p(daily["runoff_mm"].to_numpy(float)),
                    np.log1p(LOSS_SCALE * daily["pest_runoff_gha"].clip(lower=0).to_numpy(float))], axis=1)
    X, Y, M, meta = [], [], [], []
    for y in app_years:
        start = pd.Timestamp(year=y, month=3, day=1) - pd.Timedelta(days=WARMUP)
        i0 = idx.searchsorted(start)
        if i0 >= len(idx) or idx[i0] != start:
            continue
        n = min(LENGTH, len(idx) - i0)
        if n < WARMUP + 200:                 # run crashed early in this year
            continue
        x = np.zeros((LENGTH, len(DYNAMIC)), np.float32); t = np.zeros((LENGTH, 2), np.float32)
        m = np.zeros((LENGTH, 2), np.float32)
        x[:n], t[:n] = dyn[i0:i0 + n], tgt[i0:i0 + n]
        dates = idx[i0:i0 + n]
        m[WARMUP:n, 0] = 1.0
        m[WARMUP:n, 1] = (dates[WARMUP:] < clean_until).astype(np.float32)
        X.append(x); Y.append(t); M.append(m); meta.append((y, start, n))
    return X, Y, M, meta


def build_dataset(interim: str | Path = "data/interim", limit: int | None = None) -> dict:
    """All samples of all readable runs, plus which split each belongs to."""
    interim = Path(interim)
    rq = pd.read_csv(interim / "run_quality.csv", index_col="run", parse_dates=["clean_until"])
    rq = rq[rq["clean_until"].notna() & rq["usle_k"].notna()]
    runs = list(rq.index)[:limit]
    files = split_by_weather(rq.loc[runs, "met_hash"])
    soil = rq.loc[runs, SOIL_FEATURES].astype(float)
    train_runs = files.index[files == "train"]
    mu, sd = soil.loc[train_runs].mean(), soil.loc[train_runs].std().replace(0, 1.0)
    soil_z = ((soil - mu) / sd).clip(-5, 5).astype(np.float32)

    X, Y, M, S, rows = [], [], [], [], []
    for i, run in enumerate(runs, start=1):
        daily = pd.read_parquet(interim / "daily" / f"{run}.parquet",
                                columns=["rain_mm", "temp_c", "pan_evap_mm", "runoff_mm", "pest_runoff_gha", "days_since_app"])
        cn = tuple(rq.at[run, f"cn_{k}"] for k in range(1, 5))
        years = list(range(daily.index[0].year, daily.index[-1].year))
        x, y, m, meta = run_sequences(daily, cn, rq.at[run, "clean_until"], years)
        for xi, yi, mi, (yr, start, n) in zip(x, y, m, meta):
            X.append(xi); Y.append(yi); M.append(mi); S.append(soil_z.loc[run].to_numpy())
            f = files[run]
            split = ("test" if f == "test" and yr in TEST_APP_YEARS else
                     "val" if f != "test" and yr in VAL_APP_YEARS else
                     "train" if f == "train" and yr not in TEST_APP_YEARS + VAL_APP_YEARS else "unused")
            rows.append({"run": run, "app_year": yr, "start": start, "n_days": n, "split": split})
        if i % 1000 == 0 or i == len(runs):
            log.info("lstm data: %d / %d runs", i, len(runs))
    return {"X": np.stack(X), "Y": np.stack(Y), "M": np.stack(M), "S": np.stack(S).astype(np.float32),
            "meta": pd.DataFrame(rows), "soil_mean": mu.to_dict(), "soil_std": sd.to_dict()}


# --------------------------------------------------------------------------- #
# Model
# --------------------------------------------------------------------------- #
def _torch():
    try:
        import torch
    except ImportError as e:                                   # pragma: no cover
        raise ImportError('The LSTM surrogate needs PyTorch: pip install -e ".[lstm]"') from e
    return torch


def make_model(n_static: int, hidden: int = 64):
    torch = _torch()

    class Surrogate(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self.lstm = torch.nn.LSTM(len(DYNAMIC) + n_static, hidden, batch_first=True)
            self.head = torch.nn.Sequential(torch.nn.Linear(hidden, 32), torch.nn.ReLU(), torch.nn.Linear(32, 2))

        def forward(self, x, s):
            z = torch.cat([x, s[:, None, :].expand(-1, x.shape[1], -1)], dim=2)
            out, _ = self.lstm(z)
            return torch.nn.functional.softplus(self.head(out))     # both targets are >= 0

    return Surrogate()


def _masked_mse(pred, target, mask, pest_weight: float):
    err = (pred - target) ** 2 * mask
    return err[..., 0].sum() / mask[..., 0].sum().clamp(min=1) + \
        pest_weight * err[..., 1].sum() / mask[..., 1].sum().clamp(min=1)


def fit(data: dict, epochs: int = 20, batch: int = 256, hidden: int = 64, lr: float = 2e-3,
        patience: int = 4, pest_weight: float = 3.0, seed: int = 0, threads: int | None = None):
    """Train with early stopping on the validation year. Returns (model, history)."""
    torch = _torch()
    torch.manual_seed(seed)
    if threads:
        torch.set_num_threads(threads)
    meta = data["meta"]
    tens = {k: torch.from_numpy(data[k]) for k in ("X", "Y", "M", "S")}
    tr = np.flatnonzero(meta["split"].to_numpy() == "train")
    va = np.flatnonzero(meta["split"].to_numpy() == "val")
    if len(tr) == 0 or len(va) == 0:
        raise ValueError("need training and validation samples (check the years and weather files in the data)")
    model = make_model(data["S"].shape[1], hidden)
    opt = torch.optim.Adam(model.parameters(), lr=lr)
    rng = np.random.default_rng(seed)
    best, best_state, bad, history = np.inf, None, 0, []

    def val_loss() -> float:
        model.eval(); tot, n = 0.0, 0
        with torch.no_grad():
            for i in range(0, len(va), 1024):
                b = va[i:i + 1024]
                tot += float(_masked_mse(model(tens["X"][b], tens["S"][b]), tens["Y"][b], tens["M"][b], pest_weight)) * len(b)
                n += len(b)
        return tot / n

    for epoch in range(1, epochs + 1):
        t0 = time.perf_counter(); model.train()
        order = rng.permutation(tr)
        for i in range(0, len(order), batch):
            b = order[i:i + batch]
            opt.zero_grad()
            loss = _masked_mse(model(tens["X"][b], tens["S"][b]), tens["Y"][b], tens["M"][b], pest_weight)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            opt.step()
        v = val_loss(); history.append(v)
        log.info("lstm epoch %d: validation loss %.5f (%.0f s)", epoch, v, time.perf_counter() - t0)
        if v < best - 1e-6:
            best, bad = v, 0
            best_state = {k: w.clone() for k, w in model.state_dict().items()}
        else:
            bad += 1
            if bad >= patience:
                break
    model.load_state_dict(best_state)
    return model, history


def predict_rows(model, data: dict, split: str = "test") -> pd.DataFrame:
    """Daily predictions (after the warm-up) for all samples of one split, in plain units."""
    torch = _torch()
    meta = data["meta"]
    sel = np.flatnonzero(meta["split"].to_numpy() == split)
    model.eval(); parts = []
    with torch.no_grad():
        for i in range(0, len(sel), 1024):
            b = sel[i:i + 1024]
            p = model(torch.from_numpy(data["X"][b]), torch.from_numpy(data["S"][b])).numpy()
            for j, k in enumerate(b):
                n = int(meta.at[k, "n_days"])
                dates = pd.date_range(meta.at[k, "start"] + pd.Timedelta(days=WARMUP), periods=n - WARMUP)
                parts.append(pd.DataFrame({"run": meta.at[k, "run"], "date": dates,
                                           "runoff_lstm": np.expm1(p[j, WARMUP:n, 0]),
                                           "loss_lstm": np.expm1(p[j, WARMUP:n, 1]) / LOSS_SCALE}))
    return pd.concat(parts, ignore_index=True)


# --------------------------------------------------------------------------- #
# Driver: train, compare with the tree surrogate on identical rows
# --------------------------------------------------------------------------- #
def train_and_compare(interim: str | Path = "data/interim", features_path: str | Path = "data/processed/features.parquet",
                      model_dir: str | Path = "models", results: str | Path = "docs/results",
                      figures: str | Path = "docs/figures", epochs: int = 20, limit: int | None = None,
                      threads: int | None = None) -> dict:
    from sklearn.metrics import average_precision_score

    from .features import CONC_FEATURES, RUNOFF_FEATURES
    from .models import fit_conc, fit_runoff, split_rows

    t0 = time.perf_counter()
    data = build_dataset(interim, limit)
    counts = data["meta"]["split"].value_counts().to_dict()
    log.info("lstm samples: %s", counts)
    model, history = fit(data, epochs=epochs, threads=threads)
    train_seconds = time.perf_counter() - t0
    pred = predict_rows(model, data, "test")

    # the tree surrogate, trained on the same split, scored on the same rows
    t = pd.read_parquet(features_path)
    if limit:
        t = t[t["run"].isin(set(data["meta"]["run"]))]
    t["split"] = split_rows(t["met_hash"], t["date"])
    tr, va, te = (t[t["split"] == s] for s in ("train", "val", "test"))
    runoff, conc = fit_runoff(tr, va), fit_conc(tr, va)
    te = te.copy()
    te["run"] = te["run"].astype(str)
    te["runoff_trees"] = runoff.predict(te[RUNOFF_FEATURES])
    te["loss_trees"] = te["runoff_trees"] * conc.predict(te[CONC_FEATURES])
    te = te.merge(pred, on=["run", "date"], how="inner")
    tc = te[te["pest_clean"]]
    pos = tc["high_loss"].to_numpy()

    def block(runoff_col, loss_col):
        hit = (tc[loss_col] >= HIGH_LOSS_GHA).to_numpy()
        return {"runoff": _regression_scores(te["runoff_mm"], te[runoff_col], te["run"]),
                "loss": _loss_scores(tc, loss_col),
                "high_loss_pr_auc": float(average_precision_score(pos, tc[loss_col])) if pos.any() else None,
                "alarm_precision": float(pos[hit].mean()) if hit.any() else None,
                "alarm_recall": float(hit[pos].mean()) if pos.any() else None}

    out = {"test_app_years": list(TEST_APP_YEARS), "rows_compared": int(len(te)),
           "rows_with_trusted_pesticide": int(len(tc)), "high_loss_days": int(pos.sum()),
           "samples": counts, "epochs_run": len(history), "validation_loss_by_epoch": [round(h, 5) for h in history],
           "train_minutes": round(train_seconds / 60, 1),
           "parameters": int(sum(p.numel() for p in model.parameters())),
           "lstm": block("runoff_lstm", "loss_lstm"), "trees": block("runoff_trees", "loss_trees")}
    results = Path(results); results.mkdir(parents=True, exist_ok=True)
    (results / "lstm_vs_trees.json").write_text(json.dumps(out, indent=2))
    torch = _torch()
    Path(model_dir).mkdir(parents=True, exist_ok=True)
    torch.save({"state": model.state_dict(), "soil_mean": data["soil_mean"], "soil_std": data["soil_std"],
                "dynamic": DYNAMIC, "soil_features": SOIL_FEATURES}, Path(model_dir) / "lstm.pt")
    from .figures import lstm_figure
    lstm_figure(te, tc, out, Path(figures))
    return out
