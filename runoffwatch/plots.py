"""Diagnostic plots. Stacked panels with a shared time axis - never a dual y-axis."""
from __future__ import annotations

import matplotlib.pyplot as plt
import pandas as pd

RAIN = "#2a78d6"      # blue  - precipitation
CONC = "#52514e"      # neutral ink - concentration line
SPIKE = "#eb6834"     # orange - detected spikes
NORMAL = "#9a9890"


def plot_event_timeline(weather, matched, site, compound, start=None, end=None, path=None):
    """Hourly rain (top) over concentration + baseline + spikes (bottom)."""
    d = matched[(matched.site == site) & (matched.compound == compound)]
    w = weather
    if start is not None:
        w, d = w.loc[start:], d[d.time >= pd.Timestamp(start, tz="UTC")]
    if end is not None:
        w, d = w.loc[:end], d[d.time <= pd.Timestamp(end, tz="UTC")]
    fig, (ax1, ax2) = plt.subplots(2, 1, sharex=True, figsize=(12, 6),
                                   gridspec_kw={"height_ratios": [1, 2]})
    ax1.bar(w.index, w["precip_mm"], width=1 / 24, color=RAIN)
    ax1.set_ylabel("Rain (mm/h)")
    ax1.invert_yaxis()  # hyetograph convention: rain hangs from the top
    ax2.plot(d.time, d.value, color=CONC, lw=1.5, marker="o", ms=3, label="Concentration")
    ax2.plot(d.time, d.baseline, color=NORMAL, lw=1, ls="--", label="Trailing baseline")
    s = d[d.is_spike]
    ax2.scatter(s.time, s.value, s=60, color=SPIKE, zorder=3, label="Spike")
    ax2.set_ylabel(f"{compound} (µg/L)")
    ax2.legend(frameon=False, loc="upper left")
    for ax in (ax1, ax2):
        ax.spines[["top", "right"]].set_visible(False)
        ax.grid(axis="y", alpha=0.2)
    fig.suptitle(f"{site} - {compound}", x=0.01, ha="left")
    fig.tight_layout()
    if path:
        fig.savefig(path, dpi=130)
    return fig


def plot_lag_profile(matched, path=None):
    """Median rain per lag bin, spikes vs normal samples - where the signal sits in time."""
    ok = matched[matched.weather_ok & matched.baseline.notna()]
    bins = [c for c in ok.columns if c.startswith("rain_") and c.count("_") == 3
            and not c.startswith("rain_0_72")]
    med = ok.groupby("is_spike")[bins].median().T
    fig, ax = plt.subplots(figsize=(7, 4))
    x = range(len(bins))
    ax.bar([i - 0.2 for i in x], med.get(False, 0), width=0.38, color=NORMAL, label="Normal samples")
    ax.bar([i + 0.2 for i in x], med.get(True, 0), width=0.38, color=SPIKE, label="Spike samples")
    ax.set_xticks(list(x), [b.replace("rain_", "").replace("_mm", "").replace("_", "–") for b in bins])
    ax.set_xlabel("Hours before sample")
    ax.set_ylabel("Median rainfall (mm)")
    ax.legend(frameon=False)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    if path:
        fig.savefig(path, dpi=130)
    return fig
