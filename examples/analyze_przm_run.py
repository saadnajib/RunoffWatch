"""Spike analysis for ONE FOCUS PRZM run folder.

Run from repo root:
    python -m examples.analyze_przm_run path/to/run_0000140_grid_086080
Writes <run>_daily.csv, <run>_timeline.png, <run>_rain_bins.png to examples/output/.
"""
import logging
import sys
from pathlib import Path

import matplotlib.pyplot as plt

from runoffwatch.przm_io import read_run
from runoffwatch.przm_spikes import daily_features, flag_spikes, spike_probability, summarize

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
if len(sys.argv) != 2:
    sys.exit(__doc__)
run = Path(sys.argv[1])
out = Path("examples/output"); out.mkdir(parents=True, exist_ok=True)

df = flag_spikes(daily_features(read_run(run)))
df.to_csv(out / f"{run.name}_daily.csv")
if df.attrs.get("unstable"):
    print("\n!!! This run failed the stability check - treat pesticide numbers as INVALID.\n")

print("\n== Summary"); [print(f"  {k:26s}{v}") for k, v in summarize(df).items()]
rain_tbl = spike_probability(df, "rain_mm", [1, 5, 10, 15, 20, 40])
print("\n== Given it rains: chance of a spike by daily rain\n", rain_tbl.to_string())
print("\n== By days since spraying\n", spike_probability(df, "days_since_app", [0, 30, 60, 120, 180, 240, 370]).to_string())
print("\n== By soil wetness (rain in previous 7 days)\n", spike_probability(df, "antecedent_7d_mm", [0, 5, 15, 30, 200]).to_string())

# Timeline: rain (top) / water runoff (middle) / pesticide runoff (bottom). Separate axes, shared time.
fig, ax = plt.subplots(3, 1, sharex=True, figsize=(12, 7), gridspec_kw={"height_ratios": [1, 1, 1.4]})
ax[0].bar(df.index, df.rain_mm, width=1, color="#2a78d6"); ax[0].set_ylabel("Rain\n(mm/day)"); ax[0].invert_yaxis()
ax[1].bar(df.index, df.runoff_mm, width=1, color="#52514e"); ax[1].set_ylabel("Water runoff\n(mm/day)")
ax[2].bar(df.index, df.pest_runoff_gha, width=2, color="#9a9890")
s = df[df.is_spike]; ax[2].scatter(s.index, s.pest_runoff_gha, color="#eb6834", s=25, zorder=3, label="Spike day")
ax[2].set_yscale("symlog", linthresh=0.1); ax[2].set_ylabel("Pesticide runoff\n(g/ha/day)"); ax[2].legend(frameon=False)
for a in ax: a.spines[["top", "right"]].set_visible(False)
fig.suptitle(run.name + ("  [UNSTABLE RUN]" if df.attrs.get("unstable") else ""), x=0.01, ha="left")
fig.tight_layout(); fig.savefig(out / f"{run.name}_timeline.png", dpi=130)

fig, a = plt.subplots(figsize=(7, 4))
labels = [str(i) for i in rain_tbl.index]
a.bar(labels, 100 * rain_tbl.runoff_days / rain_tbl.rain_days, color="#2a78d6")
a.set_xlabel("Daily rain (mm)"); a.set_ylabel("Rain days with runoff (%)")
a.spines[["top", "right"]].set_visible(False); fig.tight_layout(); fig.savefig(out / f"{run.name}_rain_bins.png", dpi=130)
print(f"\nWrote outputs to {out}/")
