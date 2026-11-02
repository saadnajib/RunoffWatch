"""End-to-end demo on synthetic data with a KNOWN 36 h lag, to sanity-check the pipeline.

Run from repo root:  python -m examples.demo_synthetic
"""
import logging
from pathlib import Path

import numpy as np
import pandas as pd

from runoffwatch.pipeline import compare_spike_vs_normal, run
from runoffwatch.plots import plot_event_timeline, plot_lag_profile

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
rng = np.random.default_rng(0)
out = Path("examples/output"); out.mkdir(parents=True, exist_ok=True)

# Hourly weather: mostly dry, occasional storms
t = pd.date_range("2025-04-01", "2025-09-30 23:00", freq="h", tz="UTC")
storm = rng.random(len(t)) < 0.004
rain = np.zeros(len(t))
for i in np.flatnonzero(storm):
    rain[i:i + 6] += rng.gamma(2, 3, size=min(6, len(t) - i))
pd.DataFrame({"time": t, "precip_mm": rain.round(1),
              "temp_c": 15 + 8 * np.sin(np.arange(len(t)) * 2 * np.pi / 24) + rng.normal(0, 1, len(t)),
              "wind_ms": rng.gamma(2, 1.5, len(t))}).to_csv(out / "weather.csv", index=False)

# Daily pesticide samples at 09:00 UTC; concentration responds to rain 36 h earlier
days = pd.date_range("2025-04-01 09:00", "2025-09-30 09:00", freq="D", tz="UTC")
r = pd.Series(rain, index=t)
lagged = np.array([r.loc[d - pd.Timedelta(hours=48): d - pd.Timedelta(hours=24)].sum() for d in days])
conc = 0.02 + 0.01 * lagged + rng.lognormal(-5, 0.5, len(days))
vals = [f"<0.01" if c < 0.015 else round(c, 4) for c in conc]
pd.DataFrame({"sample_time": days, "site": "R1", "compound": "metolachlor",
              "concentration_ugL": vals}).to_csv(out / "pesticides.csv", index=False)

matched = run(out / "weather.csv", out / "pesticides.csv",
              spike_kwargs=dict(window="7D", factor=2.0, use_median=True, abs_floor=0.05))
matched.to_csv(out / "matched.csv", index=False)
print("\nSpike vs normal (medians):\n", compare_spike_vs_normal(matched).round(2))
w = pd.read_csv(out / "weather.csv", parse_dates=["time"]).set_index("time")
plot_event_timeline(w, matched, "R1", "metolachlor", "2025-06-01", "2025-07-15", out / "timeline.png")
plot_lag_profile(matched, out / "lag_profile.png")
print(f"\nWrote {out}/matched.csv, timeline.png, lag_profile.png")
