# RunoffWatch

RunoffWatch analyzes how rainfall intensity and timing trigger pesticide spikes in rivers. It links hourly weather data with water quality measurements to identify likely runoff-driven contamination windows.

## What it provides

- **Spike detection** with robust z-scores (`detect_pesticide_spikes`)
- **Rainfall-to-spike lag estimation** (`estimate_rainfall_lags`)
- **Lag summary statistics** (`summarize_lags`)
- **CSV loader** for hourly weather + water-quality inputs (`load_hourly_observations`)

## Quick example

```python
from runoffwatch import (
    detect_pesticide_spikes,
    estimate_rainfall_lags,
    load_hourly_observations,
)

observations = load_hourly_observations(
    weather_csv_path="weather_hourly.csv",
    water_quality_csv_path="water_quality_hourly.csv",
)

spikes = detect_pesticide_spikes(observations, z_threshold=2.5, min_value=0.5)
lags = estimate_rainfall_lags(observations, spikes, rainfall_threshold_mm=5.0, max_lag_hours=72)

for lag in lags:
    print(lag)
```

Both CSV files should include the same hourly `timestamp` values (`%Y-%m-%d %H:%M:%S` by default).
