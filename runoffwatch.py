from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime
from statistics import mean, median
from typing import Iterable, Sequence


@dataclass(frozen=True)
class HourlyObservation:
    timestamp: datetime
    rainfall_mm: float
    pesticide_ug_l: float


@dataclass(frozen=True)
class SpikeEvent:
    timestamp: datetime
    pesticide_ug_l: float
    score: float


@dataclass(frozen=True)
class LagResult:
    spike_time: datetime
    rain_time: datetime
    lag_hours: int
    rain_mm: float
    pesticide_ug_l: float


def load_hourly_observations(
    weather_csv_path: str,
    water_quality_csv_path: str,
    *,
    timestamp_column: str = "timestamp",
    rainfall_column: str = "rainfall_mm",
    pesticide_column: str = "pesticide_ug_l",
    time_format: str = "%Y-%m-%d %H:%M:%S",
) -> list[HourlyObservation]:
    weather_by_time: dict[datetime, float] = {}

    with open(weather_csv_path, newline="", encoding="utf-8") as weather_file:
        for row in csv.DictReader(weather_file):
            timestamp = datetime.strptime(row[timestamp_column], time_format)
            weather_by_time[timestamp] = float(row[rainfall_column])

    observations: list[HourlyObservation] = []
    with open(water_quality_csv_path, newline="", encoding="utf-8") as water_file:
        for row in csv.DictReader(water_file):
            timestamp = datetime.strptime(row[timestamp_column], time_format)
            if timestamp not in weather_by_time:
                continue
            observations.append(
                HourlyObservation(
                    timestamp=timestamp,
                    rainfall_mm=weather_by_time[timestamp],
                    pesticide_ug_l=float(row[pesticide_column]),
                )
            )

    observations.sort(key=lambda item: item.timestamp)
    return observations


def detect_pesticide_spikes(
    observations: Sequence[HourlyObservation],
    *,
    z_threshold: float = 2.5,
    min_value: float | None = None,
) -> list[SpikeEvent]:
    if not observations:
        return []

    values = [item.pesticide_ug_l for item in observations]
    center = median(values)
    abs_deviations = [abs(value - center) for value in values]
    mad = median(abs_deviations)

    spikes: list[SpikeEvent] = []
    if mad == 0:
        avg = mean(values)
        variance = sum((value - avg) ** 2 for value in values) / max(len(values), 1)
        std = variance ** 0.5
        if std == 0:
            return []
        for item in observations:
            score = (item.pesticide_ug_l - avg) / std
            if score >= z_threshold and (min_value is None or item.pesticide_ug_l >= min_value):
                spikes.append(SpikeEvent(item.timestamp, item.pesticide_ug_l, score))
        return spikes

    for item in observations:
        score = 0.6745 * (item.pesticide_ug_l - center) / mad
        if score >= z_threshold and (min_value is None or item.pesticide_ug_l >= min_value):
            spikes.append(SpikeEvent(item.timestamp, item.pesticide_ug_l, score))

    return spikes


def estimate_rainfall_lags(
    observations: Sequence[HourlyObservation],
    spikes: Sequence[SpikeEvent],
    *,
    rainfall_threshold_mm: float = 5.0,
    max_lag_hours: int = 72,
) -> list[LagResult]:
    if not observations or not spikes:
        return []

    rainfall_events = [item for item in observations if item.rainfall_mm >= rainfall_threshold_mm]
    results: list[LagResult] = []

    for spike in spikes:
        candidates: list[HourlyObservation] = []
        for rain_event in rainfall_events:
            if rain_event.timestamp > spike.timestamp:
                continue
            lag_hours = int((spike.timestamp - rain_event.timestamp).total_seconds() // 3600)
            if 0 <= lag_hours <= max_lag_hours:
                candidates.append(rain_event)

        if not candidates:
            continue

        trigger = max(candidates, key=lambda event: (event.rainfall_mm, event.timestamp))
        lag_hours = int((spike.timestamp - trigger.timestamp).total_seconds() // 3600)
        results.append(
            LagResult(
                spike_time=spike.timestamp,
                rain_time=trigger.timestamp,
                lag_hours=lag_hours,
                rain_mm=trigger.rainfall_mm,
                pesticide_ug_l=spike.pesticide_ug_l,
            )
        )

    return sorted(results, key=lambda item: item.spike_time)


def summarize_lags(lags: Iterable[LagResult]) -> dict[str, float | int | None]:
    lag_list = list(lags)
    if not lag_list:
        return {"count": 0, "min_hours": None, "median_hours": None, "max_hours": None}

    ordered = sorted(item.lag_hours for item in lag_list)
    middle = len(ordered) // 2
    median_hours = (
        float(ordered[middle])
        if len(ordered) % 2 == 1
        else (ordered[middle - 1] + ordered[middle]) / 2
    )
    return {
        "count": len(ordered),
        "min_hours": ordered[0],
        "median_hours": median_hours,
        "max_hours": ordered[-1],
    }
