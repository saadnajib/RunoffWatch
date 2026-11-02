import unittest
from datetime import datetime, timedelta

from runoffwatch import (
    HourlyObservation,
    detect_pesticide_spikes,
    estimate_rainfall_lags,
    summarize_lags,
)


def _build_observations() -> list[HourlyObservation]:
    start = datetime(2026, 5, 1, 0, 0, 0)
    pesticide = [0.2, 0.21, 0.22, 0.18, 0.19, 0.2, 1.2, 0.23, 0.2, 1.0]
    rainfall = [0.0, 3.0, 0.0, 6.0, 2.0, 0.0, 0.0, 4.0, 8.0, 0.0]
    return [
        HourlyObservation(
            timestamp=start + timedelta(hours=index),
            rainfall_mm=rainfall[index],
            pesticide_ug_l=pesticide[index],
        )
        for index in range(len(pesticide))
    ]


class RunoffWatchTests(unittest.TestCase):
    def test_detect_pesticide_spikes_identifies_high_outliers(self) -> None:
        observations = _build_observations()

        spikes = detect_pesticide_spikes(observations, z_threshold=2.0, min_value=0.9)

        spike_hours = [int((item.timestamp - observations[0].timestamp).total_seconds() // 3600) for item in spikes]
        self.assertEqual(spike_hours, [6, 9])

    def test_estimate_rainfall_lags_pairs_spikes_with_prior_storms(self) -> None:
        observations = _build_observations()
        spikes = detect_pesticide_spikes(observations, z_threshold=2.0, min_value=0.9)

        lags = estimate_rainfall_lags(observations, spikes, rainfall_threshold_mm=5.0, max_lag_hours=12)

        self.assertEqual([item.lag_hours for item in lags], [3, 1])
        summary = summarize_lags(lags)
        self.assertEqual(summary, {"count": 2, "min_hours": 1, "median_hours": 2.0, "max_hours": 3})

    def test_estimate_rainfall_lags_returns_empty_when_no_triggering_rain(self) -> None:
        observations = _build_observations()
        spikes = detect_pesticide_spikes(observations, z_threshold=2.0, min_value=0.9)

        lags = estimate_rainfall_lags(observations, spikes, rainfall_threshold_mm=20.0, max_lag_hours=12)

        self.assertEqual(lags, [])


if __name__ == "__main__":
    unittest.main()
