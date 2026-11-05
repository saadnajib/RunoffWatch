"""
Spike analysis for daily PRZM model output.

Model output is different from river samples: on most days pesticide runoff is
exactly 0, so "2x the 7-day rolling mean" does not work (the baseline is 0).
Here a spike is a day whose pesticide runoff is in the top part of all days
WITH runoff (default: top 10%), optionally above an absolute floor.

Every rain day is kept - with or without a spike - so we can answer both
"when do spikes happen" and "when does rain NOT cause a spike".

Note: PRZM produces runoff on the SAME day as the rain. A multi-day lag in a
river comes from transport downstream, which this field model does not include.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def daily_features(df: pd.DataFrame, antecedent_days: int = 7) -> pd.DataFrame:
    """Add the weather/timing features used to explain spikes."""
    out = df.copy()
    r = out["rain_mm"]
    out["rain_prev1_mm"] = r.shift(1)
    out["rain_prev2_3_mm"] = r.shift(2) + r.shift(3)
    # Rain in the days before (not including today) = how wet the soil already is.
    out[f"antecedent_{antecedent_days}d_mm"] = r.shift(1).rolling(antecedent_days).sum()

    # Days since the most recent pesticide application (NaN before the first one).
    if "applied_gha" in out:
        app_dates = out.index.where(out["applied_gha"] > 0)
        last_app = pd.Series(app_dates, index=out.index).ffill()
        out["days_since_app"] = (out.index - last_app).dt.days
    out["month"] = out.index.month
    return out


def flag_spikes(df: pd.DataFrame, col: str = "pest_runoff_gha",
                top_fraction: float = 0.10, abs_floor: float | None = None) -> pd.DataFrame:
    """Mark spike days. Threshold = (1 - top_fraction) quantile of non-zero days."""
    out = df.copy()
    nonzero = out.loc[out[col] > 0, col]
    out["is_runoff_event"] = out[col] > 0
    if nonzero.empty:
        out["is_spike"] = False
        out.attrs["spike_threshold"] = np.nan
        return out
    thr = nonzero.quantile(1 - top_fraction)
    if abs_floor is not None:
        thr = max(thr, abs_floor)
    out["is_spike"] = out[col] >= thr
    out.attrs["spike_threshold"] = float(thr)
    return out


def spike_probability(df: pd.DataFrame, by: str, bins) -> pd.DataFrame:
    """Chance of a spike for rain days, grouped by one feature.

    Only rain days (>= 1 mm) are used: the question is 'given it rains, when
    does it cause a spike?'.
    """
    rainy = df[df["rain_mm"] >= 1].copy()
    rainy["group"] = pd.cut(rainy[by], bins=bins, include_lowest=True)
    g = rainy.groupby("group", observed=False)
    return pd.DataFrame({
        "rain_days": g.size(),
        "runoff_days": g["is_runoff_event"].sum(),
        "spike_days": g["is_spike"].sum(),
        "spike_chance_%": (100 * g["is_spike"].mean()).round(1),
        "total_pest_runoff_gha": g["pest_runoff_gha"].sum().round(2),
    })


def summarize(df: pd.DataFrame) -> dict:
    """Headline numbers for one run."""
    f = df["pest_runoff_gha"]
    top5 = f.nlargest(5).sum() / f.sum() if f.sum() > 0 else np.nan
    return {
        "days": len(df),
        "rain_days_>=1mm": int((df["rain_mm"] >= 1).sum()),
        "runoff_days": int((df["runoff_mm"] > 0).sum()),
        "pesticide_runoff_days": int((f > 0).sum()),
        "spike_days": int(df["is_spike"].sum()),
        "spike_threshold_gha": round(df.attrs.get("spike_threshold", np.nan), 3),
        "applied_total_gha": round(df["applied_gha"].sum(), 1) if "applied_gha" in df else np.nan,
        "pest_runoff_total_gha": round(f.sum(), 2),
        "share_in_top5_days_%": round(100 * top5, 1),
    }
