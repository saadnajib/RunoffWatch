"""
What-if tool: "given this weather, what happens if I spray on day X?"

Uses the trained surrogate (runoff model x concentration model). No PRZM run is needed.

LIMITS - the tool can only answer what the training simulations cover:

* one pesticide (Flufenacet), one dose (2400 g/ha), one crop (winter cereals),
  always sprayed on 1 March. Other products, doses or crops need new PRZM runs.
* spray dates are therefore only meaningful in late winter / early spring;
  `check_inputs` warns outside February-April. Even inside that window, moving the
  spray day is an extrapolation: in training, "days since spraying" and the calendar
  date always moved together.
* soil settings are checked one by one against the training range. Combinations that
  never occur together in the training runs are not detected.
* it reproduces PRZM, a model. It was not checked against field measurements.
"""

from __future__ import annotations

import warnings
from pathlib import Path

import numpy as np
import pandas as pd

from .features import MIN_RAIN_MM, weather_features
from .models import load_models
from .przm_inp import SOIL_FEATURES

# Median field of the training runs (close to the standard FOCUS R1 soil).
DEFAULT_SOIL = {
    "usle_k": 0.34, "usle_ls": 0.33, "slope_pct": 2.0, "cn_2": 81.0,
    "h1_bd": 1.40, "h1_fc": 0.27, "h1_wp": 0.117, "h1_oc": 1.0, "h1_kd": 3.775,
    "h1_sand": 39.0, "h1_clay": 21.0, "h3_bd": 1.35, "h3_oc": 0.4,
}
# The four curve-number sets in the training runs, keyed by the growing-season value (cn_2).
CN_SETS = {73: (73, 73, 79, 86), 77: (77, 77, 82, 88), 81: (81, 81, 86, 91), 84: (84, 84, 89, 94)}
KOC = 377.5                 # sorption of the pesticide per unit organic carbon: Kd = KOC * OC% / 100
# Mean pan evaporation per month (mm/day) in the project weather files; used when a forecast has none.
MONTHLY_EVAP_MM = [0.65, 1.02, 1.80, 2.72, 3.34, 4.10, 4.43, 3.71, 2.68, 1.53, 0.86, 0.61]


def soil_settings(**changes) -> dict:
    """DEFAULT_SOIL with changes. Setting h1_oc also sets h1_kd (they are tied through KOC)."""
    soil = {**DEFAULT_SOIL, **changes}
    unknown = set(soil) - set(SOIL_FEATURES)
    if unknown:
        raise ValueError(f"unknown soil settings: {sorted(unknown)}")
    if "h1_oc" in changes and "h1_kd" not in changes:
        soil["h1_kd"] = KOC * soil["h1_oc"] / 100
    if soil["cn_2"] not in CN_SETS:
        raise ValueError(f"cn_2 must be one of {sorted(CN_SETS)} (the curve numbers present in the training runs)")
    return soil


def prepare_weather(weather: pd.DataFrame) -> pd.DataFrame:
    """Check a daily weather table and fill in evaporation if it is missing."""
    w = weather.copy()
    if "date" in w.columns:
        w = w.set_index(pd.to_datetime(w["date"])).drop(columns="date")
    w.index = pd.to_datetime(w.index)
    w = w.sort_index()
    missing = {"rain_mm", "temp_c"} - set(w.columns)
    if missing:
        raise ValueError(f"weather table needs columns {sorted(missing)}")
    if (w.index[-1] - w.index[0]).days != len(w) - 1:
        raise ValueError("weather table must have exactly one row per day, without gaps")
    if w[["rain_mm", "temp_c"]].isna().any().any() or (w["rain_mm"] < 0).any():
        raise ValueError("rain_mm and temp_c must be filled in, and rain cannot be negative")
    if "pan_evap_mm" not in w.columns:
        w["pan_evap_mm"] = np.array(MONTHLY_EVAP_MM)[w.index.month - 1]
    return w


def check_inputs(weather: pd.DataFrame, soil: dict, spray_date: pd.Timestamp, meta: dict) -> list[str]:
    """Plain-language warnings about asking the model something it has not seen."""
    notes = []
    if spray_date.month not in (2, 3, 4):
        notes.append("All training simulations sprayed on 1 March. A spray date outside February-April "
                     "is outside what the model has seen; treat the result as a guess.")
    if (spray_date - weather.index[0]).days < 30:
        notes.append("Less than 30 days of weather before the spray date: 'rain in the previous 30 days' "
                     "is incomplete, so soil wetness is underestimated.")
    ranges = meta["trained_on"]["feature_ranges"]
    for k, v in soil.items():
        lo, hi = ranges[k]
        if not lo <= v <= hi:
            notes.append(f"{k} = {v} is outside the range in the training runs ({lo:.3g} to {hi:.3g}).")
    return notes


def predict_days(weather: pd.DataFrame, spray_date, soil: dict | None = None, models: dict | None = None,
                 model_dir: str | Path = "models") -> pd.DataFrame:
    """Predicted runoff and pesticide loss for every day from the spray date on.

    weather: daily table (index or column `date`; rain_mm, temp_c, optional pan_evap_mm) that
             includes the spray date, ideally starting 30+ days before it.
    Returns one row per day: rain_mm, runoff_mm, loss_gha, high_loss_day (loss >= 1 g/ha).
    Notes about inputs the models have not seen are in `.attrs["notes"]` and raised as warnings.
    """
    models = models or load_models(model_dir)
    meta = models["meta"]
    soil = soil_settings(**(soil or {}))
    w = prepare_weather(weather)
    spray_date = pd.Timestamp(spray_date)
    if spray_date not in w.index:
        raise ValueError(f"spray date {spray_date.date()} is not inside the weather table")
    notes = check_inputs(w, soil, spray_date, meta)
    for note in notes:
        warnings.warn(note, stacklevel=2)

    f = weather_features(w, [spray_date], CN_SETS[int(soil["cn_2"])])
    for k, v in soil.items():
        f[k] = v
    f = f.loc[spray_date:]
    rainy = f["rain_mm"] >= MIN_RAIN_MM          # the models were trained on rain days only

    out = pd.DataFrame({"rain_mm": f["rain_mm"], "days_since_spraying": f["days_since_app"].astype(int)}, index=f.index)
    out["runoff_mm"] = 0.0
    out["loss_gha"] = 0.0
    if rainy.any():
        fr = f[rainy]
        runoff = models["runoff"].predict(fr[meta["runoff_features"]])
        conc = 10 ** models["conc"].predict(fr[meta["conc_features"]])
        out.loc[rainy, "runoff_mm"] = runoff
        out.loc[rainy, "loss_gha"] = runoff * np.where(conc > meta["conc_floor"] * 1.01, conc, 0.0)
    out["high_loss_day"] = out["loss_gha"] >= meta["high_loss_threshold_gha"]
    out.attrs["notes"] = notes
    return out


def compare_spray_days(weather: pd.DataFrame, candidates, horizon_days: int = 14, soil: dict | None = None,
                       models: dict | None = None, model_dir: str | Path = "models") -> pd.DataFrame:
    """For each candidate spray date: predicted pesticide loss in the following `horizon_days`.

    Lower is better. Only candidates whose whole window lies inside the weather table are
    ranked; a shorter window would look better only because it adds up fewer days.
    `.attrs["notes"]` lists every warning about inputs outside what the models have seen.
    """
    models = models or load_models(model_dir)
    w = prepare_weather(weather)
    rows, notes = [], []
    for c in pd.to_datetime(list(candidates)):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            days = predict_days(w, c, soil, models)
        notes += [n for n in days.attrs["notes"] if n not in notes]
        days = days.iloc[:horizon_days]
        worst = days["loss_gha"].idxmax()
        rows.append({
            "spray_date": c.date(),
            "days_covered": len(days),
            "rain_in_window_mm": round(float(days["rain_mm"].sum()), 1),
            "predicted_loss_gha": round(float(days["loss_gha"].sum()), 3),
            "loss_pct_of_dose": round(100 * float(days["loss_gha"].sum()) / 2400, 4),
            "high_loss_days": int(days["high_loss_day"].sum()),
            "worst_day": worst.date() if days["loss_gha"].max() > 0 else None,
            "worst_day_loss_gha": round(float(days["loss_gha"].max()), 3),
        })
    out = pd.DataFrame(rows)
    full = out["days_covered"] == horizon_days
    out["rank"] = out.loc[full, "predicted_loss_gha"].rank(method="min").astype("Int64").reindex(out.index)
    if not full.all():
        notes.append(f"{int((~full).sum())} candidate day(s) have fewer than {horizon_days} days of weather after "
                     "them and are not ranked.")
    out.attrs["notes"] = notes
    return out


def example_weather(start: str = "2026-01-20", days: int = 75, seed: int = 3) -> pd.DataFrame:
    """Made-up late-winter weather with a wet spell, for demos and tests (not real data)."""
    rng = np.random.default_rng(seed)
    idx = pd.date_range(start, periods=days, freq="D")
    rain = np.where(rng.random(days) < 0.35, rng.gamma(1.2, 4.0, days), 0.0).round(1)
    if days >= 52:                           # a storm front in the middle of March
        rain[48:52] = [14.0, 32.0, 21.0, 6.0]
    temp = (4 + 6 * np.linspace(0, 1, days) + rng.normal(0, 2, days)).round(1)
    return pd.DataFrame({"rain_mm": rain, "temp_c": temp}, index=idx.rename("date"))
