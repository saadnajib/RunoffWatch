"""
Feature table: one row per rain day (rain >= 1 mm) per run.

The same function, `weather_features`, builds the model inputs for training
(from PRZM run folders) and for the what-if tool (from a weather forecast), so
both always see identically defined features.

Every feature uses only today's weather and the past, never the future, and
never a PRZM output. (Today's rain counts as known: in use it is the forecast.) That is what lets the surrogate replace PRZM.

Three feature groups:

    WEATHER   rain today and before, temperature, evaporation, season
    HISTORY   time and weather since the last spraying (drives how much
              pesticide is still at the soil surface)
    SOIL      field and soil settings of the run (przm_inp.SOIL_FEATURES)
"""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import pandas as pd

from .przm_inp import SOIL_FEATURES

log = logging.getLogger("runoffwatch")

MIN_RAIN_MM = 1.0          # a "rain day"
HIGH_LOSS_GHA = 1.0        # a "high-loss day": >= 1 g/ha lost in one day (0.04 % of the 2400 g/ha dose)

WEATHER_FEATURES = [
    "rain_mm", "rain_prev1_mm", "rain_prev2_3_mm", "rain_7d_mm", "rain_14d_mm", "rain_30d_mm",
    "temp_c", "temp_prev1_c", "temp_7d_c", "evap_mm", "evap_7d_mm", "frozen_precip_30d_mm",
    "cn_today", "cn_runoff_mm",
]
HISTORY_FEATURES = [
    "days_since_app", "rain_since_app_mm", "heavy_rain_days_since_app", "temp_since_app_c",
    "rain_first3d_after_app_mm",
]
RUNOFF_FEATURES = WEATHER_FEATURES + SOIL_FEATURES                      # hydrology model
CONC_FEATURES = HISTORY_FEATURES + [f for f in WEATHER_FEATURES if f != "cn_today"] + SOIL_FEATURES
CLASSIFIER_FEATURES = HISTORY_FEATURES + WEATHER_FEATURES + SOIL_FEATURES

# Two design decisions that came out of testing on years the models had never seen:
#
# * No calendar feature (day of year, month). The weather files are neighbouring grid
#   cells of one decade, so "date" identifies a storm; with a calendar feature the trees
#   memorised storms and failed on new years. The crop calendar is still present through
#   cn_today, and the time since spraying through days_since_app. Note that in this data
#   set days_since_app IS the calendar (spraying is always on 1 March), so the models
#   cannot tell "time since spraying" from "time of year".
# * cn_runoff_mm, the textbook curve-number runoff for today's rain, is given to the
#   models as an input. PRZM itself computes runoff with a curve number that it adjusts
#   for soil moisture, so the models only have to learn that adjustment (a physics-
#   informed, "hybrid" surrogate).

# Crop periods of the FOCUS R1 winter-cereals scenario: (day, month) each curve number starts to apply.
CN_PERIOD_STARTS = [(12, 11), (10, 6), (31, 7), (1, 11)]


def curve_number_today(dates: pd.DatetimeIndex, cn: tuple[float, float, float, float]) -> np.ndarray:
    """Curve number in force on each date (PRZM switches it at 4 fixed dates per year)."""
    md = dates.month * 100 + dates.day
    out = np.full(len(dates), cn[0], dtype=float)           # 12 Nov -> 9 Jun (wraps over new year)
    out[(md >= 610) & (md < 731)] = cn[1]
    out[(md >= 731) & (md < 1101)] = cn[2]
    out[(md >= 1101) & (md < 1112)] = cn[3]
    return out


def curve_number_runoff(rain_mm, cn) -> np.ndarray:
    """Textbook SCS curve-number runoff (mm) with a fixed curve number - no soil-moisture memory."""
    p, cn = np.asarray(rain_mm, dtype=float), np.asarray(cn, dtype=float)
    s = 25400.0 / cn - 254.0
    return np.where(p > 0.2 * s, (p - 0.2 * s) ** 2 / (p + 0.8 * s), 0.0)


def weather_features(daily: pd.DataFrame, app_dates, cn: tuple[float, float, float, float] | None = None) -> pd.DataFrame:
    """Add all WEATHER and HISTORY features to a daily table.

    daily: one row per calendar day (DatetimeIndex, no gaps) with rain_mm, temp_c, pan_evap_mm.
    app_dates: spraying dates. Days before the first one get NaN history features.
    cn: the four curve numbers of the field (for cn_today); None leaves cn_today NaN.
    """
    need = {"rain_mm", "temp_c", "pan_evap_mm"}
    if not need <= set(daily.columns):
        raise ValueError(f"daily table needs columns {sorted(need)}")
    if not daily.index.is_monotonic_increasing or (daily.index[-1] - daily.index[0]).days != len(daily) - 1:
        raise ValueError("daily table must have one row per day, in order, without gaps")

    f = pd.DataFrame(index=daily.index)
    r, t, e = daily["rain_mm"].astype(float), daily["temp_c"].astype(float), daily["pan_evap_mm"].astype(float)
    prev = r.shift(1)
    f["rain_mm"] = r
    f["rain_prev1_mm"] = prev
    f["rain_prev2_3_mm"] = r.shift(2) + r.shift(3)
    for n in (7, 14, 30):
        f[f"rain_{n}d_mm"] = prev.rolling(n, min_periods=1).sum()
    f["temp_c"] = t
    f["temp_prev1_c"] = t.shift(1)
    f["temp_7d_c"] = t.shift(1).rolling(7, min_periods=1).mean()
    f["evap_mm"] = e
    f["evap_7d_mm"] = e.shift(1).rolling(7, min_periods=1).sum()
    f["frozen_precip_30d_mm"] = r.where(t <= 0, 0.0).shift(1).rolling(30, min_periods=1).sum()   # snow-pack proxy
    f["cn_today"] = curve_number_today(daily.index, cn) if cn is not None else np.nan
    f["cn_runoff_mm"] = curve_number_runoff(r, f["cn_today"]) if cn is not None else np.nan

    # --- history since the last spraying ------------------------------------
    app_dates = pd.DatetimeIndex(sorted(pd.to_datetime(list(app_dates))))
    is_app = daily.index.isin(app_dates)
    cycle = np.cumsum(is_app)                                   # 0 before the first spraying
    last_app = pd.Series(daily.index.where(is_app), index=daily.index).ffill()
    f["days_since_app"] = (daily.index - last_app).dt.days.to_numpy(dtype=float)

    def since_app(x: pd.Series) -> pd.Series:
        """Sum of x from the spraying day up to and including yesterday."""
        return x.groupby(cycle).cumsum().sub(x)

    f["rain_since_app_mm"] = since_app(r)
    f["heavy_rain_days_since_app"] = since_app((r >= 10).astype(float))
    n_days = f["days_since_app"].clip(lower=1)
    f["temp_since_app_c"] = (since_app(t) / n_days).where(f["days_since_app"] > 0, t)
    first3 = r.where(f["days_since_app"].between(0, 2), 0.0).groupby(cycle).cumsum()
    f["rain_first3d_after_app_mm"] = first3
    f.loc[cycle == 0, HISTORY_FEATURES] = np.nan
    return f


def run_feature_rows(daily: pd.DataFrame, params: dict, clean_until: pd.Timestamp | None) -> pd.DataFrame:
    """Rain-day rows of one run: features + targets + the 'pesticide results trusted' flag."""
    cn = tuple(params[f"cn_{i}"] for i in range(1, 5))
    app_dates = daily.index[daily["applied_gha"] > 0]
    f = weather_features(daily, app_dates, cn)
    for c in SOIL_FEATURES:
        f[c] = params[c]
    f["runoff_mm"] = daily["runoff_mm"]
    f["loss_gha"] = daily["pest_runoff_gha"]
    f["pest_clean"] = (f["days_since_app"].notna() & (daily.index < clean_until)) if clean_until is not None else False
    f = f[f.index >= daily.index[0] + pd.Timedelta(days=3)]     # the first 3 days have no rain history
    return f[f["rain_mm"] >= MIN_RAIN_MM]


def build_feature_table(interim: str | Path = "data/interim", out: str | Path = "data/processed/features.parquet",
                        limit: int | None = None) -> pd.DataFrame:
    """Build the table for all readable runs. Needs `qc` and `audit` output in `interim`."""
    interim = Path(interim)
    rq = pd.read_csv(interim / "run_quality.csv", index_col="run", parse_dates=["clean_until"])
    rq = rq[rq["clean_until"].notna() & rq["usle_k"].notna()]
    runs = list(rq.index)[:limit]
    parts = []
    for i, run in enumerate(runs, start=1):
        daily = pd.read_parquet(interim / "daily" / f"{run}.parquet",
                                columns=["rain_mm", "temp_c", "pan_evap_mm", "runoff_mm", "pest_runoff_gha", "applied_gha"])
        rows = run_feature_rows(daily, rq.loc[run].to_dict(), rq.at[run, "clean_until"])
        num = rows.select_dtypes("number").columns
        rows[num] = rows[num].astype("float32")
        parts.append(rows.assign(run=run, met_hash=rq.at[run, "met_hash"]).rename_axis("date").reset_index())
        if i % 1000 == 0 or i == len(runs):
            log.info("features: %d / %d runs", i, len(runs))
    table = pd.concat(parts, ignore_index=True)
    table["run"] = table["run"].astype("category")
    table["met_hash"] = table["met_hash"].astype("category")
    table["high_loss"] = table["loss_gha"] >= HIGH_LOSS_GHA
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    table.to_parquet(out, index=False)
    log.info("features: %d rain-day rows, %d with trusted pesticide results, %d high-loss days among them",
             len(table), int(table["pest_clean"].sum()), int((table["high_loss"] & table["pest_clean"]).sum()))
    return table
