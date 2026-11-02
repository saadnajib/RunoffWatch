"""
RunoffWatch core pipeline
=========================

Load hourly weather + sparse river pesticide samples, detect concentration
spikes, and attach the antecedent weather window to EVERY sample (spikes and
non-spikes), so that "which weather precedes a spike" can be compared against
"which weather precedes a normal sample".

Design decisions worth knowing before you trust the output:

* All timestamps are converted to UTC. Weather APIs usually deliver UTC; lab
  sample sheets are usually local time. Mixing them silently shifts every lag
  by your UTC offset (1-2 h in Europe, more elsewhere).
* The spike baseline is a *trailing* window that EXCLUDES the current sample
  (closed="left"). Including the sample in its own baseline makes large spikes
  harder to detect (the spike inflates the mean it is compared to).
* Values below the limit of detection/quantification ("<0.01", "n.d.") are kept
  and flagged as censored, then substituted with LOD/2. Dropping them biases the
  baseline upward and hides spikes rising out of a clean background.
* The weather window is split into lag bins (0-24 h, 24-48 h, 48-72 h) instead
  of one 24-72 h sum, so the lag can be estimated rather than assumed.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

import numpy as np
import pandas as pd

log = logging.getLogger("runoffwatch")


class DataQualityError(ValueError):
    """Raised when input data is unusable (not merely imperfect)."""


# --------------------------------------------------------------------------- #
# Loading
# --------------------------------------------------------------------------- #
def _read_any(path: str | Path) -> pd.DataFrame:
    """Read CSV / Excel / Parquet based on extension."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Input file not found: {path}")
    suffix = path.suffix.lower()
    if suffix in {".csv", ".txt"}:
        return pd.read_csv(path)
    if suffix in {".xlsx", ".xls"}:
        return pd.read_excel(path)
    if suffix == ".parquet":
        return pd.read_parquet(path)
    raise ValueError(f"Unsupported file type '{suffix}' for {path}")


def _to_utc(series: pd.Series, source_tz: str | None, name: str) -> pd.Series:
    """Parse datetimes and convert to tz-aware UTC.

    source_tz: IANA zone of naive timestamps (e.g. "Europe/Berlin"). Ignored if
    the timestamps already carry an offset. If None and the data is naive, we
    assume UTC but WARN, because that assumption is often wrong for lab data.
    """
    ts = pd.to_datetime(series, errors="coerce", utc=False)
    n_bad = int(ts.isna().sum() - series.isna().sum())
    if n_bad:
        log.warning("%s: %d timestamps could not be parsed and were dropped", name, n_bad)
    if ts.dt.tz is None:
        if source_tz is None:
            log.warning(
                "%s: timestamps are timezone-naive; assuming UTC. Pass source_tz "
                "if they are local time, or every lag will be off by the UTC offset.",
                name,
            )
            source_tz = "UTC"
        # DST: ambiguous autumn hour -> NaT rather than silently guessing.
        ts = ts.dt.tz_localize(source_tz, ambiguous="NaT", nonexistent="shift_forward")
    return ts.dt.tz_convert("UTC")


def load_weather(
    path: str | Path,
    time_col: str = "time",
    precip_col: str = "precip_mm",
    temp_col: str | None = "temp_c",
    wind_col: str | None = "wind_ms",
    source_tz: str | None = None,
    max_gap_hours: int = 6,
) -> pd.DataFrame:
    """Load hourly weather and return a regular hourly UTC-indexed frame.

    Output columns: precip_mm, temp_c, wind_ms (if provided), precip_missing.
    Short gaps (<= max_gap_hours) in temperature/wind are interpolated.
    Precipitation gaps are NEVER filled with 0 or interpolated - a missing
    hour during a storm is not a dry hour - they stay NaN and are flagged.
    """
    df = _read_any(path)
    rename = {time_col: "time", precip_col: "precip_mm"}
    if temp_col:
        rename[temp_col] = "temp_c"
    if wind_col:
        rename[wind_col] = "wind_ms"
    missing = [c for c in rename if c not in df.columns]
    if missing:
        raise DataQualityError(f"Weather file missing columns {missing}; has {list(df.columns)}")
    df = df[list(rename)].rename(columns=rename)

    df["time"] = _to_utc(df["time"], source_tz, "weather")
    df = df.dropna(subset=["time"])

    for c in df.columns.drop("time"):
        df[c] = pd.to_numeric(df[c], errors="coerce")

    # Physical plausibility checks
    neg = (df["precip_mm"] < 0).sum()
    if neg:
        log.warning("weather: %d negative precipitation values set to NaN", neg)
        df.loc[df["precip_mm"] < 0, "precip_mm"] = np.nan
    extreme = (df["precip_mm"] > 150).sum()  # > 150 mm/h is beyond world records for most regions
    if extreme:
        log.warning("weather: %d hours with > 150 mm/h - check units (mm vs 0.1 mm vs inches)", extreme)
    if "temp_c" in df and ((df["temp_c"] < -60) | (df["temp_c"] > 60)).any():
        log.warning("weather: temperatures outside [-60, 60] C - check units (Kelvin? Fahrenheit?)")

    # Duplicate timestamps (common when merging station exports)
    dups = df["time"].duplicated().sum()
    if dups:
        log.warning("weather: %d duplicate timestamps; keeping the mean", dups)
    df = df.groupby("time").mean().sort_index()

    # Force a regular hourly grid so window sums are well-defined.
    # Sub-hourly data is summed (precip) / averaged (others) up to hourly.
    agg = {"precip_mm": lambda s: s.sum(min_count=1)}
    agg.update({c: "mean" for c in df.columns if c != "precip_mm"})
    df = df.resample("1h").agg(agg)

    df["precip_missing"] = df["precip_mm"].isna()
    frac_missing = df["precip_missing"].mean()
    if frac_missing > 0.05:
        log.warning("weather: %.1f%% of hourly precipitation is missing", 100 * frac_missing)

    for c in ("temp_c", "wind_ms"):
        if c in df:
            df[c] = df[c].interpolate(limit=max_gap_hours, limit_area="inside")
    return df


_CENSORED = re.compile(r"^\s*<\s*([0-9.eE+-]+)\s*$")


def load_pesticides(
    path: str | Path,
    time_col: str = "sample_time",
    value_col: str = "concentration_ugL",
    site_col: str | None = "site",
    compound_col: str | None = "compound",
    lod_col: str | None = None,
    source_tz: str | None = None,
    sample_time_convention: str = "end",
    composite_hours: float = 0,
) -> pd.DataFrame:
    """Load pesticide measurements in long format (one row per sample x compound).

    Handles censored values like "<0.01" and "n.d."/"<LOD" (needs lod_col).

    sample_time_convention / composite_hours: a 24 h composite sample labelled
    with its *start* time actually integrates runoff over the following day.
    We always align on the END of the sampling period, so the weather window
    "preceding" the sample is correct. Set composite_hours=24 (or 168 for
    weekly composites) and convention="start" if your timestamps are starts.
    """
    df = _read_any(path)
    cols = {time_col: "time", value_col: "raw_value"}
    if site_col:
        cols[site_col] = "site"
    if compound_col:
        cols[compound_col] = "compound"
    if lod_col:
        cols[lod_col] = "lod"
    missing = [c for c in cols if c not in df.columns]
    if missing:
        raise DataQualityError(f"Pesticide file missing columns {missing}; has {list(df.columns)}")
    df = df[list(cols)].rename(columns=cols)
    if "site" not in df:
        df["site"] = "site_1"
    if "compound" not in df:
        df["compound"] = "total"

    df["time"] = _to_utc(df["time"], source_tz, "pesticides")
    df = df.dropna(subset=["time"])
    if sample_time_convention == "start":
        df["time"] = df["time"] + pd.Timedelta(hours=composite_hours)
    elif sample_time_convention != "end":
        raise ValueError("sample_time_convention must be 'start' or 'end'")

    # --- censored values -------------------------------------------------
    raw = df["raw_value"].astype(str).str.strip()
    m = raw.str.extract(_CENSORED, expand=False)
    df["censored"] = m.notna() | raw.str.lower().isin({"n.d.", "nd", "<lod", "<loq", "bdl"})
    value = pd.to_numeric(raw, errors="coerce")
    lod = pd.to_numeric(m, errors="coerce")
    if "lod" in df:
        lod = lod.fillna(pd.to_numeric(df["lod"], errors="coerce"))
    df["value"] = value.where(~df["censored"], lod / 2)  # LOD/2 substitution

    unresolved = df["censored"] & df["value"].isna()
    if unresolved.any():
        log.warning("pesticides: %d censored values without an LOD - dropped", unresolved.sum())
    bad = df["value"].isna() & ~df["censored"] & df["raw_value"].notna()
    if bad.any():
        examples = df.loc[bad, "raw_value"].astype(str).unique()[:5]
        log.warning("pesticides: %d non-numeric values dropped, e.g. %s", bad.sum(), list(examples))
    df = df.dropna(subset=["value"])

    if (df["value"] < 0).any():
        raise DataQualityError("Negative concentrations found - check the export.")
    if df["censored"].mean() > 0.8:
        log.warning("pesticides: >80%% of values are censored; spike detection will be unreliable")

    # Same site/compound/time twice -> lab replicates; average them.
    df = (
        df.groupby(["site", "compound", "time"], as_index=False)
        .agg(value=("value", "mean"), censored=("censored", "all"))
        .sort_values(["site", "compound", "time"])
        .reset_index(drop=True)
    )
    return df


# --------------------------------------------------------------------------- #
# Alignment checks
# --------------------------------------------------------------------------- #
def check_overlap(weather: pd.DataFrame, pest: pd.DataFrame, lookback_hours: int = 72) -> None:
    """Fail loudly if the two datasets don't overlap; warn on partial coverage."""
    w0, w1 = weather.index.min(), weather.index.max()
    p0, p1 = pest["time"].min(), pest["time"].max()
    log.info("weather %s -> %s | pesticides %s -> %s", w0, w1, p0, p1)
    covered = (pest["time"] - pd.Timedelta(hours=lookback_hours) >= w0) & (pest["time"] <= w1)
    if not covered.any():
        raise DataQualityError("No pesticide sample has a full weather look-back window.")
    if (~covered).any():
        log.warning(
            "%d of %d samples lack full %d h weather coverage; their weather "
            "features will be NaN", (~covered).sum(), len(pest), lookback_hours,
        )


def sampling_interval_report(pest: pd.DataFrame) -> pd.DataFrame:
    """Median spacing between samples per site/compound.

    If the median interval is >= 3 days, a 24-72 h lag CANNOT be resolved from
    this data alone: the sample may be taken 1 h or 6 days after the storm.
    """
    rep = (
        pest.groupby(["site", "compound"])["time"]
        .apply(lambda t: t.diff().median())
        .rename("median_interval")
        .reset_index()
    )
    rep["n_samples"] = pest.groupby(["site", "compound"]).size().values
    coarse = rep[rep["median_interval"] >= pd.Timedelta(days=3)]
    if len(coarse):
        log.warning(
            "%d site/compound series are sampled every >= 3 days. Lag estimates "
            "for them are bounded by the sampling interval, not by hydrology.",
            len(coarse),
        )
    return rep


# --------------------------------------------------------------------------- #
# Spike detection
# --------------------------------------------------------------------------- #
def detect_spikes(
    pest: pd.DataFrame,
    window: str = "7D",
    factor: float = 2.0,
    min_periods: int = 3,
    abs_floor: float | None = None,
    use_median: bool = False,
) -> pd.DataFrame:
    """Flag samples whose value > factor x trailing baseline.

    window: time-based window ("7D", "30D"). It is per site/compound and
        EXCLUDES the current sample. With weekly data a 7D window holds ~1
        prior sample -> baseline undefined (min_periods not met). Use "28D" or
        more for weekly series.
    abs_floor: optional minimum concentration for a spike (e.g. the LOQ or
        the 0.1 ug/L EU drinking-water limit). Prevents "0.002 -> 0.005" from
        counting as a spike when the baseline is near zero.
    use_median: rolling median is more robust than the mean when earlier
        spikes sit inside the window and inflate the baseline.
    """
    def _per_group(g: pd.DataFrame) -> pd.DataFrame:
        s = g.set_index("time")["value"]
        roll = s.rolling(window, closed="left", min_periods=min_periods)
        base = roll.median() if use_median else roll.mean()
        g = g.copy()
        g["baseline"] = base.to_numpy()
        g["ratio"] = g["value"] / g["baseline"].replace(0, np.nan)
        return g

    out = pd.concat(
        [_per_group(g) for _, g in pest.groupby(["site", "compound"], sort=False)],
        ignore_index=True,
    )
    out["is_spike"] = (out["ratio"] > factor) & ~out["censored"]
    if abs_floor is not None:
        out["is_spike"] &= out["value"] >= abs_floor

    no_base = out["baseline"].isna().mean()
    if no_base > 0.3:
        log.warning(
            "%.0f%% of samples have no baseline (fewer than %d prior samples in %s). "
            "Widen `window` or lower `min_periods`.", 100 * no_base, min_periods, window,
        )
    log.info("detected %d spikes in %d samples", int(out["is_spike"].sum()), len(out))
    return out


# --------------------------------------------------------------------------- #
# Weather matching
# --------------------------------------------------------------------------- #
def weather_features(
    weather: pd.DataFrame,
    t_end: pd.Timestamp,
    lag_bins_h: tuple[int, ...] = (0, 24, 48, 72),
    rain_threshold_mm: float = 1.0,
    antecedent_days: int = 7,
    max_missing_frac: float = 0.1,
) -> dict:
    """Summarise weather in the hours before t_end.

    Returns rainfall per lag bin, peak intensity, lag of peak intensity, hours
    since last rain, and antecedent rainfall (a soil-wetness proxy: the same
    storm on saturated soil produces far more runoff).
    """
    max_lag = lag_bins_h[-1]
    win = weather.loc[t_end - pd.Timedelta(hours=max_lag): t_end - pd.Timedelta(hours=1)]
    feats: dict = {}
    if len(win) < max_lag * (1 - max_missing_frac) or win["precip_missing"].mean() > max_missing_frac:
        return {"weather_ok": False}
    feats["weather_ok"] = True

    p = win["precip_mm"]
    hours_before = ((t_end - p.index) / pd.Timedelta(hours=1)).to_numpy()
    for lo, hi in zip(lag_bins_h[:-1], lag_bins_h[1:]):
        mask = (hours_before > lo) & (hours_before <= hi)
        feats[f"rain_{lo}_{hi}h_mm"] = float(np.nansum(p.to_numpy()[mask]))
    feats[f"rain_0_{max_lag}h_mm"] = float(p.sum())
    feats["max_intensity_mmh"] = float(p.max())
    feats["hours_before_peak_rain"] = float(hours_before[int(np.nanargmax(p.to_numpy()))]) if p.max() > 0 else np.nan
    wet = hours_before[p.to_numpy() >= rain_threshold_mm]
    feats["hours_since_rain"] = float(wet.min()) if wet.size else np.nan  # NaN = dry > max_lag h

    ante = weather.loc[t_end - pd.Timedelta(hours=max_lag + 24 * antecedent_days):
                       t_end - pd.Timedelta(hours=max_lag + 1), "precip_mm"]
    feats[f"antecedent_{antecedent_days}d_mm"] = float(ante.sum()) if len(ante) else np.nan

    if "temp_c" in win:
        feats["mean_temp_c"] = float(win["temp_c"].mean())
    if "wind_ms" in win:
        # Spray drift is a non-runoff pathway; high wind + no rain spikes point to drift.
        feats["max_wind_ms"] = float(win["wind_ms"].max())
    return feats


def match_weather(samples: pd.DataFrame, weather: pd.DataFrame, **kwargs) -> pd.DataFrame:
    """Attach weather features to every sample (not only spikes).

    Keeping non-spike samples is deliberate: they are the control group. A
    claim like "spikes follow > 20 mm rain" means nothing until you know how
    often > 20 mm rain is followed by NO spike.
    """
    feats = [weather_features(weather, t, **kwargs) for t in samples["time"]]
    out = pd.concat([samples.reset_index(drop=True), pd.DataFrame(feats)], axis=1)
    n_bad = (~out["weather_ok"]).sum()
    if n_bad:
        log.warning("%d samples have incomplete weather windows (weather_ok=False)", n_bad)
    return out


def compare_spike_vs_normal(matched: pd.DataFrame) -> pd.DataFrame:
    """Median weather features for spikes vs non-spikes - first look at signal."""
    ok = matched[matched["weather_ok"] & matched["baseline"].notna()]
    cols = [c for c in ok.columns if c.startswith(("rain_", "max_", "hours_", "antecedent_", "mean_temp"))]
    return ok.groupby("is_spike")[cols].median().T.rename(columns={False: "normal", True: "spike"})


# --------------------------------------------------------------------------- #
# Convenience runner
# --------------------------------------------------------------------------- #
def run(weather_path, pesticide_path, weather_kwargs=None, pest_kwargs=None,
        spike_kwargs=None, feature_kwargs=None) -> pd.DataFrame:
    weather = load_weather(weather_path, **(weather_kwargs or {}))
    pest = load_pesticides(pesticide_path, **(pest_kwargs or {}))
    feature_kwargs = feature_kwargs or {}
    check_overlap(weather, pest, lookback_hours=feature_kwargs.get("lag_bins_h", (0, 24, 48, 72))[-1])
    log.info("\n%s", sampling_interval_report(pest).to_string(index=False))
    spikes = detect_spikes(pest, **(spike_kwargs or {}))
    return match_weather(spikes, weather, **feature_kwargs)
