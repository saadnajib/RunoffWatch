"""Analysis report for ONE run folder: summary, risk tables and two plots."""
from __future__ import annotations

import logging
from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # no screen needed
import matplotlib.pyplot as plt

from .przm_io import read_run
from .przm_spikes import daily_features, flag_spikes, spike_probability, summarize

log = logging.getLogger("runoffwatch")

RAIN, INK, MUTED, HIGHLIGHT = "#2a78d6", "#52514e", "#9a9890", "#eb6834"


def analyze_run(folder: str | Path, out_dir: str | Path = "reports") -> dict:
    """Print the summary and risk tables; write <run>_daily.csv and two PNGs to out_dir."""
    run = Path(folder)
    out = Path(out_dir); out.mkdir(parents=True, exist_ok=True)

    df = flag_spikes(daily_features(read_run(run)))
    unstable = bool(df.attrs.get("unstable"))
    df.to_csv(out / f"{run.name}_daily.csv")
    if unstable:
        print("\n!!! This run failed the stability check - treat pesticide numbers as INVALID.\n")

    summary = summarize(df)
    print("\n== Summary"); [print(f"  {k:26s}{v}") for k, v in summary.items()]
    rain_tbl = spike_probability(df, "rain_mm", [1, 5, 10, 15, 20, 40])
    print("\n== Given it rains: chance of a high-loss day by daily rain\n", rain_tbl.to_string())
    print("\n== By days since spraying\n",
          spike_probability(df, "days_since_app", [0, 30, 60, 120, 180, 240, 370]).to_string())
    print("\n== By soil wetness (rain in previous 7 days)\n",
          spike_probability(df, "antecedent_7d_mm", [0, 5, 15, 30, 200]).to_string())

    # Timeline: rain / water runoff / pesticide loss. Separate axes, shared time (no dual axis).
    fig, ax = plt.subplots(3, 1, sharex=True, figsize=(12, 7), gridspec_kw={"height_ratios": [1, 1, 1.4]})
    ax[0].bar(df.index, df.rain_mm, width=1, color=RAIN); ax[0].set_ylabel("Rain\n(mm/day)"); ax[0].invert_yaxis()
    ax[1].bar(df.index, df.runoff_mm, width=1, color=INK); ax[1].set_ylabel("Water runoff\n(mm/day)")
    ax[2].bar(df.index, df.pest_runoff_gha, width=2, color=MUTED)
    s = df[df.is_spike]
    ax[2].scatter(s.index, s.pest_runoff_gha, color=HIGHLIGHT, s=25, zorder=3, label="High-loss day")
    ax[2].set_yscale("symlog", linthresh=0.1); ax[2].set_ylabel("Pesticide loss\n(g/ha/day)")
    ax[2].legend(frameon=False)
    for a in ax:
        a.spines[["top", "right"]].set_visible(False)
    fig.suptitle(run.name + ("  [UNSTABLE RUN]" if unstable else ""), x=0.01, ha="left")
    fig.tight_layout(); fig.savefig(out / f"{run.name}_timeline.png", dpi=130); plt.close(fig)

    fig, a = plt.subplots(figsize=(7, 4))
    a.bar([str(i) for i in rain_tbl.index], 100 * rain_tbl.runoff_days / rain_tbl.rain_days, color=RAIN)
    a.set_xlabel("Daily rain (mm)"); a.set_ylabel("Rain days with runoff (%)")
    a.spines[["top", "right"]].set_visible(False)
    fig.tight_layout(); fig.savefig(out / f"{run.name}_rain_bins.png", dpi=130); plt.close(fig)

    print(f"\nWrote {run.name}_daily.csv and two plots to {out}/")
    return summary
