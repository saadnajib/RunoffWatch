"""
Readers for FOCUS PRZM_SW (PRZM 3.x) run folders, as produced by xLandscape /
xOffFieldSoilRisk Monte Carlo runs (one folder per run: *.met, *.inp, *.ZTS, ...).

Everything is converted to plain units:
    rain / evaporation / runoff / infiltration : mm per day
    wind                                       : m/s
    solar radiation                            : MJ/m2/day
    pesticide fluxes and applications          : g/ha per day
    eroded soil                                : as written by PRZM (tonnes) / factor

Units were checked against the summary table of the project weather data
(622 mm/yr, 12.5 C, wind 3.38 m/s, solar 11.85 MJ/m2/day).
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

import pandas as pd

log = logging.getLogger("runoffwatch")

LANGLEY_TO_MJ = 0.04184          # 1 ly = 1 cal/cm2 = 0.04184 MJ/m2
G_PER_CM2_TO_G_PER_HA = 1e8      # 1 ha = 1e8 cm2

# Raw PRZM unit of each time-series variable -> (converter to nice unit, nice name)
_ZTS_UNITS = {
    "PRCP": (lambda x: x * 10, "rain_mm"),
    "RUNF": (lambda x: x * 10, "runoff_mm"),
    "INFL": (lambda x: x * 10, "infiltration_mm"),
    "ESLS": (lambda x: x, "eroded_soil_t"),
    "RFLX1": (lambda x: x * G_PER_CM2_TO_G_PER_HA, "pest_runoff_gha"),
    "EFLX1": (lambda x: x * G_PER_CM2_TO_G_PER_HA, "pest_erosion_gha"),
    "TPAP": (lambda x: x * G_PER_CM2_TO_G_PER_HA, "applied_gha"),
}


def _one(folder: Path, pattern: str) -> Path:
    hits = [p for p in folder.iterdir() if p.is_file() and re.fullmatch(pattern, p.name, re.I)]
    if len(hits) != 1:
        raise FileNotFoundError(f"Expected exactly one file matching {pattern!r} in {folder}, found {len(hits)}")
    return hits[0]


def _two_digit_date(s: pd.Series) -> pd.Series:
    """PRZM writes MMDDYY. Years >= 50 -> 19xx, else 20xx."""
    s = s.astype(str).str.zfill(6)
    yy = s.str[4:6].astype(int)
    year = yy.where(yy >= 50, yy + 100) + 1900
    return pd.to_datetime(dict(year=year, month=s.str[0:2].astype(int), day=s.str[2:4].astype(int)))


def read_met(path: str | Path) -> pd.DataFrame:
    """Read a FOCUS PRZM daily weather file (.met)."""
    m = pd.read_csv(path, sep=r"\s+", header=None, dtype={0: str})
    if m.shape[1] < 6:
        raise ValueError(f"{path}: expected 6 columns (date, precip, pan evap, temp, wind, solar), got {m.shape[1]}")
    df = pd.DataFrame({
        "date": _two_digit_date(m[0]),
        "rain_mm": m[1] * 10,
        "pan_evap_mm": m[2] * 10,
        "temp_c": m[3],
        "wind_ms": m[4] / 100,
        "solar_mj": m[5] * LANGLEY_TO_MJ,
    }).set_index("date")
    if not df.index.is_monotonic_increasing or df.index.duplicated().any():
        raise ValueError(f"{path}: dates are not strictly increasing")
    gaps = pd.date_range(df.index[0], df.index[-1], freq="D").difference(df.index)
    if len(gaps):
        log.warning("%s: %d missing days, e.g. %s", path, len(gaps), list(gaps[:3]))
    if (df["rain_mm"] < 0).any():
        raise ValueError(f"{path}: negative rainfall")
    return df


def read_zts_scale_factors(inp_path: str | Path) -> dict[str, float]:
    """Read the output multipliers PRZM applies before writing the .ZTS
    (lines like 'RUNF    TSER   0   0  10.0' in the .inp file)."""
    factors = {}
    for line in Path(inp_path).read_text(errors="replace").splitlines():
        parts = line.split()
        if len(parts) >= 5 and parts[1] == "TSER":
            factors[parts[0]] = float(parts[-1])
    return factors


def read_zts(zts_path: str | Path, inp_path: str | Path | None = None) -> pd.DataFrame:
    """Read the daily PRZM time series (.ZTS) and convert to plain units."""
    lines = Path(zts_path).read_text(errors="replace").splitlines()
    header = next((l for l in lines[:10] if l.startswith(" TSR") and "RUNF" in l or "PRCP" in l), None)
    if header is None:
        raise ValueError(f"{zts_path}: no variable header line found")
    names = header.split()[1:]
    rows = [l.split() for l in lines if l.startswith(" TSR PRZ")]
    if not rows:
        raise ValueError(f"{zts_path}: no data rows")
    df = pd.DataFrame([r[2:] for r in rows], columns=["y", "m", "d", *names]).apply(pd.to_numeric)
    df.index = pd.to_datetime(dict(year=df.y, month=df.m, day=df.d))
    df.index.name = "date"
    df = df.drop(columns=["y", "m", "d"])

    factors = read_zts_scale_factors(inp_path) if inp_path else {}
    out = pd.DataFrame(index=df.index)
    for col in names:
        f = factors.get(col)
        if f is None:
            log.warning("%s: no scale factor for %s; values left as written", zts_path, col)
            out[col] = df[col]
            continue
        conv, nice = _ZTS_UNITS.get(col, (lambda x: x, col))
        out[nice] = conv(df[col] / f)
    return out


def read_soil_decay(out_path: str | Path) -> list[float]:
    """Yearly 'TOTAL SOIL DECAY OF PESTICIDE' values from a PRZM .OUT file."""
    return [float(l.split()[-1]) for l in Path(out_path).read_text(errors="replace").splitlines()
            if "TOTAL SOIL DECAY OF PESTICIDE" in l]


def check_soil_decay(out_path: str | Path, max_growth: float = 5.0) -> bool:
    """Detect numerical blow-up in a PRZM run.

    The .OUT file reports 'TOTAL SOIL DECAY OF PESTICIDE' once per year. With the
    same application every year this should level off. If it keeps growing by
    more than `max_growth` x per year, the pesticide results are not physical.
    Returns True if the run looks unstable.
    """
    vals = read_soil_decay(out_path)
    if len(vals) < 3:
        return False
    growth = [b / a for a, b in zip(vals[:-1], vals[1:]) if a > 0]
    unstable = sum(g > max_growth for g in growth) >= 2
    if unstable:
        log.error("%s: yearly soil decay grows %s - NUMERICAL BLOW-UP, pesticide results unusable",
                  Path(out_path).name, " -> ".join(f"{v:.3g}" for v in vals))
    return unstable


def read_run(folder: str | Path) -> pd.DataFrame:
    """Read one run folder and return ONE daily table: weather + model results.

    Also runs consistency checks:
      * rain in the .met file must equal PRCP in the .ZTS (same weather in and out)
      * per year, pesticide washed off must not exceed what was applied
      * the run log is scanned for ERROR lines
      * the .OUT file is checked for numerical blow-up (df.attrs["unstable"])

    Check results are kept in df.attrs (unstable, soil_decay, weather_mismatch_mm,
    mass_balance_ok, log_errors) so batch tools can record them per run.
    """
    folder = Path(folder)
    met = read_met(_one(folder, r".*\.met"))
    inp = _one(folder, r".*\.inp")
    zts = read_zts(_one(folder, r".*\.zts"), inp)

    df = met.join(zts.drop(columns=["rain_mm"], errors="ignore"), how="inner")
    if len(df) < 0.95 * len(met):
        log.warning("%s: weather and results overlap on only %d of %d days", folder.name, len(df), len(met))
    if "rain_mm" in zts:
        # PRZM stores rain on frozen days as snow (not in PRCP), so skip days <= 0 C.
        warm = met["temp_c"].reindex(zts.index) > 0
        diff = (met["rain_mm"].reindex(zts.index) - zts["rain_mm"])[warm].abs().max()
        df.attrs["weather_mismatch_mm"] = float(diff) if pd.notna(diff) else 0.0
        if diff > 0.05:
            log.warning("%s: rain in .met and .ZTS differ by up to %.2f mm on warm days - wrong weather file?",
                        folder.name, diff)
        df["snow_day"] = (met["temp_c"].reindex(df.index) <= 0) & (df["rain_mm"] > 0)

    if {"applied_gha", "pest_runoff_gha"} <= set(df):
        yearly = df[["applied_gha", "pest_runoff_gha"]].groupby(df.index.year).sum()
        cum = yearly.cumsum()
        bad = cum[cum["pest_runoff_gha"] > cum["applied_gha"]]
        df.attrs["mass_balance_ok"] = bad.empty
        if len(bad):
            log.warning("%s: cumulative pesticide runoff exceeds cumulative application in %s "
                        "- mass balance broken, check units/settings", folder.name, list(bad.index))

    out_files = [p for p in folder.iterdir() if p.suffix.lower() == ".out"]
    if out_files:
        df.attrs["unstable"] = check_soil_decay(out_files[0])
        df.attrs["soil_decay"] = read_soil_decay(out_files[0])

    logf = folder / "mc.log"
    if logf.exists():
        errs = [l.strip() for l in logf.read_text(errors="replace").splitlines() if "ERROR" in l]
        df.attrs["log_errors"] = errs
        if errs:
            log.warning("%s: %d ERROR line(s) in mc.log, first: %s", folder.name, len(errs), errs[0][:160])

    df.attrs["run"] = folder.name
    return df
