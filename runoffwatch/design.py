"""
Generate a designed experiment of new PRZM runs for the xOffFieldSoilRisk /
RunOffPrzm workstation (nothing is submitted, everything is written to disk).

In the ~4,000 existing simulations pesticide, dose and spray date never vary, so
a surrogate model cannot learn their effect. This module builds:

* a design table (one row per new run, `make_design`),
* one `.xrun` parameter file per run (`render_xrun`),
* the weather CSVs those runs reference (MARS-style daily CSV),
* 7z task archives of about 1000 `.xrun` files plus their weather CSVs
  (`write_design`), in the flat layout the workstation expects.

Two groups of runs:

``main``     every factor sampled independently and uniformly: soil (+ slope) of
             an existing run, weather file (from a fixed subset), application
             date, application rate, DT50, Koc. Henry constant fixed.
``control``  existing runs repeated exactly as originally simulated (03-01,
             2400 g/ha, DT50 41.68 d, Koc 377.5, own soil, own weather) except
             the Henry constant and the reference soil moisture (both corrected).
             Half of them are runs that became numerically
             unstable, half stable ones: does the Henry constant 0.03 cause the
             breakdown?

Units in the `.xrun`: ApplicationRate g/ha, DT50 days, Koc L/kg, soil horizon
thicknesses cm, bulk density g/cm3, organic MATERIAL %, sand/silt %, slope %.
"""

from __future__ import annotations

import logging
import re
import shutil
from collections.abc import Mapping, Sequence
from datetime import date, timedelta
from pathlib import Path
from xml.etree import ElementTree as ET
from xml.sax.saxutils import escape

import numpy as np
import pandas as pd

from .przm_io import read_met
from .rerun import HENRY_FIXED, MOISTURE_REF_FIXED

log = logging.getLogger("runoffwatch")

# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #
OC_TO_OM = 1.724                        # organic matter = organic carbon * 1.724
XRUN_THICKNESSES = (30, 30, 40)         # cm; existing h1+h2 (10+20 cm) are one 30 cm horizon
SOURCE_HORIZONS = (1, 3, 4)             # run_quality horizons that give the 3 xrun horizons

APP_RATES_GHA = (600, 1200, 2400)
DT50_DAYS = (10, 30, 41.68, 90, 180)
KOC_VALUES = (30, 100, 377.5, 1000, 3000)
# Corrected settings, same values as `rerun` uses for the re-runs (one source of truth).
HENRY_DEFAULT = float(HENRY_FIXED)              # 3.7e-7, dimensionless
MOISTURE_REF_DEFAULT = float(MOISTURE_REF_FIXED)  # 1 = field capacity (the delivered runs used 100)

ORIGINAL = dict(app_date="03-01", app_rate_gha=2400, dt50_d=41.68, koc=377.5, henry=0.03, moisture_ref=100)

SIM_START = "1990-01-01"
SIM_END = "1999-12-31"

WEATHER_COLUMNS = ["YEAR", "MONTH", "DAY", "GRID_NO", "PRECIPITATION", "ET0",
                   "TEMPERATURE_AVG", "WINDSPEED", "RADIATION"]
RECONSTRUCTED = "reconstructed_from_met"
ORIGINAL_WEATHER = "original"

MET_FILE = "focusprzm_weather.met"

APP_WINDOW_NOTE = ("The model configuration on the workstation currently fixes the application window to "
                   "03-01; varying `ApplicationWindows` only works if the configuration reads it from the "
                   "run file ($(ApplicationWindows)).")


def _parse_mmdd(s: str) -> date:
    if not isinstance(s, str) or not re.fullmatch(r"\d{2}-\d{2}", s):
        raise ValueError(f"Bad date {s!r}: expected 'MM-DD'")
    try:
        return date(2001, int(s[:2]), int(s[3:]))       # non-leap year: 02-29 is rejected
    except ValueError as e:
        raise ValueError(f"Bad date {s!r}: {e}") from None


def default_app_dates(start: str = "01-04", step_days: int = 14) -> tuple[str, ...]:
    """Every `step_days` days through one (non-leap) year, starting at `start` (MM-DD)."""
    d0 = _parse_mmdd(start)
    out, d = [], d0
    while d.year == d0.year:
        out.append(f"{d:%m-%d}")
        d += timedelta(days=step_days)
    return tuple(out)


APP_DATES = default_app_dates()          # 26 dates: 01-04, 01-18, ..., 12-20

# Fixed (non-varied) xrun parameters, values from the RunOffPrzm template.
_FIXED = {
    "Model_AdsorptionMethod": "aged",
    "Model_SoilTemperatureSimulation": "true",
    "FreundlichExponent": "0.957",
    "Substance_PlantUptakeFactor": "0",
    "Substance_PesticideDissipationRateOfFoliage": "10",
    "Substance_FoliarWashOffCoefficient": "0.5",
    "Substance_VapourPressure": "0.0001",
    "Substance_MolecularWeight": "304",
    "Substance_WaterSolubility": "60",
    "Substance_TemperatureAtWhichMeasured": "293",
    "SprayApplication_PrzmApplicationMethod": "foliar",
    "SprayApplication_IncorporationDepth": "5",
    "CropParameters_Crops": "Cereals,Winter|OffCrop",
    "CropParameters_PanEvaporationFactors": "0.84 0.84",
    "CropParameters_CanopyInterceptions": "0.15 0.15",
    "CropParameters_MaximumCoverages": "90 90",
    "CropParameters_MaximumHeights": "110 110",
    "CropParameters_MaximumRootingDepths": "130 130",
    "CropParameters_Fallows": "0.9 0.9",
    "CropParameters_Cropping": "0.2 0.2",
    "CropParameters_Residues": "0.4 0.4",
    "CropParameters_EmergenceDates": "12-11|12-11",
    "CropParameters_MaturationDates": "10-06|10-06",
    "CropParameters_HarvestDates": "31-07|31-07",
    "CropParameters_FallowDates": "01-11|01-11",
    "CropParameters_WaterMitigations": "0 -0.086",
    "CropParameters_SedimentMitigations": "0 -0.153",
}

# Element order of the xrun template. None = value comes from the design row.
_XRUN_ORDER = [
    "Project", "SimID", "Weather", "SimulationStart", "SimulationEnd",
    "Model_AdsorptionMethod", "Model_SoilTemperatureSimulation",
    "Substance", "DT50", "KocSoil", "FreundlichExponent",
    "Substance_PlantUptakeFactor", "Substance_PesticideDissipationRateOfFoliage",
    "Substance_FoliarWashOffCoefficient", "Substance_HenryConstant", "Substance_VapourPressure",
    "Substance_MolecularWeight", "Substance_WaterSolubility", "Substance_TemperatureAtWhichMeasured",
    "Substance_ReferenceMoistureForDT50Soil",
    "ApplicationRate", "ApplicationWindows",
    "SprayApplication_PrzmApplicationMethod", "SprayApplication_IncorporationDepth",
    "Fields_Slope", "Fields_SoilHorizonThicknesses", "Fields_SoilHorizonBulkDensities",
    "Fields_SoilHorizonOrganicMaterialContents", "Fields_SoilHorizonSandFractions",
    "Fields_SoilHorizonSiltFractions",
    "CropParameters_Crops", "CropParameters_PanEvaporationFactors", "CropParameters_CanopyInterceptions",
    "CropParameters_MaximumCoverages", "CropParameters_MaximumHeights", "CropParameters_MaximumRootingDepths",
    "CropParameters_Fallows", "CropParameters_Cropping", "CropParameters_Residues",
    "CropParameters_EmergenceDates", "CropParameters_MaturationDates", "CropParameters_HarvestDates",
    "CropParameters_FallowDates", "CropParameters_WaterMitigations", "CropParameters_SedimentMitigations",
]


# --------------------------------------------------------------------------- #
# Small helpers
# --------------------------------------------------------------------------- #
def fmt_num(x) -> str:
    """Compact decimal: 2400 -> '2400', 41.68 -> '41.68', 2.0688 -> '2.0688' (no e-notation)."""
    x = float(x)
    if not np.isfinite(x):
        raise ValueError(f"Not a finite number: {x}")
    if x.is_integer() and abs(x) < 1e15:
        return str(int(x))
    return np.format_float_positional(round(x, 6), trim="-")


def fmt_henry(x) -> str:
    """Henry constant: shortest round-trip representation, e-notation allowed ('2.4e-07', '0.03')."""
    x = float(x)
    if not np.isfinite(x):
        raise ValueError(f"Not a finite Henry constant: {x}")
    return repr(x)


def substance_label(dt50: float, koc: float) -> str:
    """Generic substance name, e.g. 'S_dt50-30_koc-100' (no real product names)."""
    return f"S_dt50-{fmt_num(dt50)}_koc-{fmt_num(koc)}"


def _as_bool(v) -> bool | None:
    if isinstance(v, (bool, np.bool_)):
        return bool(v)
    if isinstance(v, str) and v.strip().lower() in ("true", "false"):
        return v.strip().lower() == "true"
    if isinstance(v, (int, float, np.integer, np.floating)) and not pd.isna(v):
        return bool(v)
    return None


def _check_positive(name: str, values) -> tuple:
    values = tuple(values)
    if not values:
        raise ValueError(f"{name}: no values given")
    for v in values:
        try:
            ok = np.isfinite(float(v)) and float(v) > 0
        except (TypeError, ValueError):
            ok = False
        if not ok:
            raise ValueError(f"{name}: values must be positive numbers, got {v!r}")
    return values


def eligible_runs(run_quality: pd.DataFrame) -> pd.DataFrame:
    """Rows of run_quality usable as soil / control sources (clean_until and usle_k present)."""
    rq = run_quality
    if "run" in rq.columns:
        rq = rq.set_index("run")
    rq = rq.copy()
    rq.index.name = "run"
    need = ["clean_until", "usle_k", "slope_pct", "met_hash", "batch", "unstable"]
    for h in SOURCE_HORIZONS:
        need += [f"h{h}_bd", f"h{h}_oc", f"h{h}_sand", f"h{h}_clay"]
    missing = [c for c in need if c not in rq.columns]
    if missing:
        raise ValueError(f"run_quality is missing columns: {missing}")
    rq = rq[rq["clean_until"].notna() & rq["usle_k"].notna()]
    soil_cols = [c for c in need if c.startswith("h")] + ["slope_pct", "met_hash", "batch"]
    rq = rq[rq[soil_cols].notna().all(axis=1)]
    rq = rq.sort_index()
    if "h2_oc" in rq.columns:
        props = ["bd", "oc", "sand", "clay"]
        differ = np.zeros(len(rq), dtype=bool)
        for p in props:
            if f"h2_{p}" in rq.columns:
                differ |= ~np.isclose(rq[f"h1_{p}"].astype(float), rq[f"h2_{p}"].astype(float))
        if differ.any():
            log.warning("%d eligible runs have different properties in horizons 1 and 2; "
                        "the xrun uses horizon 1 for the top 30 cm", int(differ.sum()))
    return rq


def soil_fields(row: pd.Series | Mapping) -> dict:
    """xrun soil fields of one existing run: 3 horizons (30/30/40 cm) from h1, h3, h4."""
    out = {"slope_pct": float(row["slope_pct"])}
    for i, h in enumerate(SOURCE_HORIZONS, start=1):
        sand, clay = float(row[f"h{h}_sand"]), float(row[f"h{h}_clay"])
        out[f"thick_{i}"] = XRUN_THICKNESSES[i - 1]
        out[f"bd_{i}"] = float(row[f"h{h}_bd"])
        out[f"om_{i}"] = round(float(row[f"h{h}_oc"]) * OC_TO_OM, 6)
        out[f"sand_{i}"] = sand
        out[f"silt_{i}"] = max(0.0, round(100.0 - sand - clay, 6))
    return out


def _resolve_weather(met_hash: str, weather_dir) -> Path | None:
    """Original MARS CSV for a weather id, or None."""
    if weather_dir is None:
        return None
    if isinstance(weather_dir, Mapping):
        p = weather_dir.get(met_hash, weather_dir.get(f"{met_hash}.csv"))
        return Path(p) if p is not None else None
    p = Path(weather_dir) / f"{met_hash}.csv"
    return p if p.is_file() else None


# --------------------------------------------------------------------------- #
# Design
# --------------------------------------------------------------------------- #
def make_design(run_quality: pd.DataFrame, n: int, seed: int = 0, *,
                n_controls: int = 200, n_weather: int = 40,
                app_dates: Sequence[str] = APP_DATES,
                app_rates: Sequence[float] = APP_RATES_GHA,
                dt50s: Sequence[float] = DT50_DAYS,
                kocs: Sequence[float] = KOC_VALUES,
                henry: float = HENRY_DEFAULT,
                moisture_ref: float = MOISTURE_REF_DEFAULT,
                sim_start: str = SIM_START, sim_end: str = SIM_END,
                weather_dir: str | Path | Mapping | None = None) -> pd.DataFrame:
    """Build the run table of a designed experiment (deterministic for a given seed).

    Parameters
    ----------
    run_quality : table with one row per existing run (index or column ``run``);
        rows with ``clean_until`` and ``usle_k`` present are eligible.
    n : number of ``main`` runs (>= 1). Each factor is sampled independently and
        uniformly with ``numpy.random.default_rng(seed)``: soil of a random
        eligible run, a weather file from a subset of ``n_weather`` files chosen
        once per design, application date, rate (g/ha), DT50 (d) and Koc.
    n_controls : number of ``control`` runs: eligible runs repeated as originally
        simulated (03-01, 2400 g/ha, DT50 41.68, Koc 377.5, own soil and weather)
        except the Henry constant. Stratified half unstable / half stable as far
        as available.
    henry : Henry constant used in ALL new runs (dimensionless). The default is
        ``rerun.HENRY_FIXED`` (0.37E-06), the corrected value also used for the
        re-runs; published values for Flufenacet give 2.4e-7 to 5.3e-7. The
        original runs used 0.03.
    moisture_ref : reference soil moisture for the DT50 (written as
        ``Substance_ReferenceMoistureForDT50Soil``) in ALL new runs. The default
        is ``rerun.MOISTURE_REF_FIXED`` (1 = field capacity, as this PRZM program
        reads it); the original runs used 100.
    weather_dir : optional folder of original MARS CSVs named ``<met_hash>.csv``
        or a mapping met_hash -> path; only used to fill ``weather_source``.

    Returns a DataFrame with one row per new run (``run_id`` run_000001, ...).
    """
    if not isinstance(n, (int, np.integer)) or isinstance(n, bool) or n < 1:
        raise ValueError(f"n must be an integer >= 1, got {n!r}")
    if not isinstance(n_controls, (int, np.integer)) or n_controls < 0:
        raise ValueError(f"n_controls must be an integer >= 0, got {n_controls!r}")
    if not isinstance(n_weather, (int, np.integer)) or n_weather < 1:
        raise ValueError(f"n_weather must be an integer >= 1, got {n_weather!r}")
    app_dates = tuple(app_dates)
    if not app_dates:
        raise ValueError("app_dates: no dates given")
    for d in app_dates:
        _parse_mmdd(d)
    app_rates = _check_positive("app_rates", app_rates)
    dt50s = _check_positive("dt50s", dt50s)
    kocs = _check_positive("kocs", kocs)
    _check_positive("henry", [henry])
    _check_positive("moisture_ref", [moisture_ref])
    t0, t1 = pd.Timestamp(sim_start), pd.Timestamp(sim_end)
    if t1 < t0:
        raise ValueError(f"sim_end {sim_end} is before sim_start {sim_start}")

    rq = eligible_runs(run_quality)
    if rq.empty:
        raise ValueError("No eligible runs (need clean_until and usle_k not null)")
    if n_controls > len(rq):
        raise ValueError(f"n_controls={n_controls} > {len(rq)} eligible runs")

    rng = np.random.default_rng(seed)
    runs = rq.index.to_numpy()

    # Weather subset (once per design); weather_run = first run with that file.
    first_run_of_hash = rq.reset_index().groupby("met_hash")["run"].first()
    hashes = np.array(sorted(first_run_of_hash.index))
    k = min(int(n_weather), len(hashes))
    if k < n_weather:
        log.warning("Only %d distinct weather files available (n_weather=%d)", k, n_weather)
    subset = np.sort(rng.choice(hashes, size=k, replace=False))

    soil_idx = rng.integers(0, len(runs), size=n)
    w_idx = rng.integers(0, k, size=n)
    d_idx = rng.integers(0, len(app_dates), size=n)
    r_idx = rng.integers(0, len(app_rates), size=n)
    t_idx = rng.integers(0, len(dt50s), size=n)
    k_idx = rng.integers(0, len(kocs), size=n)

    rows = []
    for i in range(n):
        src = runs[soil_idx[i]]
        mh = subset[w_idx[i]]
        wrun = first_run_of_hash[mh]
        dt50, koc = float(dt50s[t_idx[i]]), float(kocs[k_idx[i]])
        rows.append(dict(group="main", source_run=src, source_unstable=_as_bool(rq.at[src, "unstable"]),
                         met_hash=mh, weather_run=wrun, weather_batch=rq.at[wrun, "batch"],
                         app_date=app_dates[d_idx[i]], app_rate_gha=float(app_rates[r_idx[i]]),
                         dt50_d=dt50, koc=koc, **soil_fields(rq.loc[src])))

    # Control group: stratified by `unstable`, without replacement.
    if n_controls:
        flag = rq["unstable"].map(_as_bool)
        unstable_runs = runs[(flag == True).to_numpy()]            # noqa: E712
        stable_runs = runs[(flag == False).to_numpy()]             # noqa: E712
        want_u = n_controls // 2 + (n_controls % 2)
        n_u = min(want_u, len(unstable_runs))
        n_s = min(n_controls - n_u, len(stable_runs))
        n_u = min(n_controls - n_s, len(unstable_runs))            # refill from the other stratum
        if n_u + n_s < n_controls:
            raise ValueError(f"Only {n_u + n_s} eligible runs with a known `unstable` flag "
                             f"for n_controls={n_controls}")
        if n_u != want_u:
            log.warning("Control group: %d unstable / %d stable runs (wanted half/half)", n_u, n_s)
        chosen = list(np.sort(rng.choice(unstable_runs, size=n_u, replace=False))) if n_u else []
        chosen += list(np.sort(rng.choice(stable_runs, size=n_s, replace=False))) if n_s else []
        for src in chosen:
            r = rq.loc[src]
            rows.append(dict(group="control", source_run=src, source_unstable=_as_bool(r["unstable"]),
                             met_hash=r["met_hash"], weather_run=src, weather_batch=r["batch"],
                             app_date=ORIGINAL["app_date"], app_rate_gha=float(ORIGINAL["app_rate_gha"]),
                             dt50_d=float(ORIGINAL["dt50_d"]), koc=float(ORIGINAL["koc"]),
                             **soil_fields(r)))

    design = pd.DataFrame(rows)
    design.insert(0, "run_id", [f"run_{i:06d}" for i in range(1, len(design) + 1)])
    design["henry"] = float(henry)
    design["moisture_ref"] = float(moisture_ref)
    design["substance"] = [substance_label(a, b) for a, b in zip(design["dt50_d"], design["koc"])]
    design["source_batch"] = design["source_run"].map(rq["batch"])
    design["weather_file"] = design["met_hash"].astype(str) + ".csv"
    design["sim_start"] = f"{t0:%Y-%m-%d}"
    design["sim_end"] = f"{t1:%Y-%m-%d}"
    design["weather_source"] = [ORIGINAL_WEATHER if _resolve_weather(h, weather_dir) else RECONSTRUCTED
                                for h in design["met_hash"]]
    first = ["run_id", "group", "source_run", "source_batch", "source_unstable", "met_hash", "weather_file",
             "weather_run", "weather_batch", "weather_source", "app_date", "app_rate_gha", "dt50_d", "koc",
             "henry", "moisture_ref", "substance", "sim_start", "sim_end", "slope_pct"]
    return design[first + [c for c in design.columns if c not in first]]


# --------------------------------------------------------------------------- #
# xrun files
# --------------------------------------------------------------------------- #
def _horizon_list(row, prefix: str) -> str:
    return " ".join(fmt_num(row[f"{prefix}_{i}"]) for i in range(1, len(XRUN_THICKNESSES) + 1))


def xrun_values(row: pd.Series | Mapping) -> dict[str, str]:
    """Parameter name -> text for one design row (template order)."""
    _parse_mmdd(row["app_date"])
    varying = {
        "Project": r"{Model}\scenario\schematic-100x100",
        "SimID": "{SimId}",
        "Weather": "{Exp}\\" + str(row["weather_file"]),
        "SimulationStart": str(row.get("sim_start", SIM_START)),
        "SimulationEnd": str(row.get("sim_end", SIM_END)),
        "Substance": str(row["substance"]),
        "DT50": fmt_num(row["dt50_d"]),
        "KocSoil": fmt_num(row["koc"]),
        "Substance_HenryConstant": fmt_henry(row["henry"]),
        "Substance_ReferenceMoistureForDT50Soil": fmt_num(row.get("moisture_ref", MOISTURE_REF_DEFAULT)),
        "ApplicationRate": fmt_num(row["app_rate_gha"]),
        "ApplicationWindows": f"{row['app_date']} to {row['app_date']}",
        "Fields_Slope": fmt_num(row["slope_pct"]),
        "Fields_SoilHorizonThicknesses": _horizon_list(row, "thick"),
        "Fields_SoilHorizonBulkDensities": _horizon_list(row, "bd"),
        "Fields_SoilHorizonOrganicMaterialContents": _horizon_list(row, "om"),
        "Fields_SoilHorizonSandFractions": _horizon_list(row, "sand"),
        "Fields_SoilHorizonSiltFractions": _horizon_list(row, "silt"),
    }
    return {k: varying[k] if k in varying else _FIXED[k] for k in _XRUN_ORDER}


def render_xrun(row: pd.Series | Mapping) -> str:
    """XML text of the `.xrun` of one design row. Macros {Model}, {SimId}, {Exp} stay literal."""
    lines = ['<?xml version="1.0" encoding="utf-8"?>', "<Parameters>"]
    lines += [f"    <{k}>{escape(v)}</{k}>" for k, v in xrun_values(row).items()]
    lines.append("</Parameters>")
    return "\n".join(lines) + "\n"


def parse_xrun(text: str | bytes) -> dict[str, str]:
    """Read an `.xrun` back into {parameter: text}."""
    if isinstance(text, str):
        text = text.encode("utf-8")
    root = ET.fromstring(text)
    if root.tag != "Parameters":
        raise ValueError(f"Root element is <{root.tag}>, expected <Parameters>")
    return {child.tag: (child.text or "") for child in root}


# --------------------------------------------------------------------------- #
# Weather CSVs
# --------------------------------------------------------------------------- #
def met_to_weather_csv(met_path: str | Path, out_path: str | Path,
                       sim_start: str = SIM_START, sim_end: str = SIM_END) -> int:
    """Reconstruct a MARS-style weather CSV from a PRZM `.met` (returns number of days).

    PRECIPITATION mm, ET0 mm (= PRZM pan evaporation, NOT a true ET0), TEMPERATURE_AVG C,
    WINDSPEED m/s, RADIATION kJ/m2/day (= MJ * 1000), GRID_NO 0.
    Raises ValueError if the `.met` does not cover every day of the simulation period.
    """
    met = read_met(met_path)
    days = pd.date_range(sim_start, sim_end, freq="D")
    missing = days.difference(met.index)
    if len(missing):
        raise ValueError(f"{met_path}: weather does not cover {sim_start}..{sim_end} "
                         f"({len(missing)} days missing, first {missing[0]:%Y-%m-%d})")
    m = met.loc[days]
    df = pd.DataFrame({
        "YEAR": days.year, "MONTH": days.month, "DAY": days.day, "GRID_NO": 0,
        "PRECIPITATION": m["rain_mm"].round(3).to_numpy(),
        "ET0": m["pan_evap_mm"].round(3).to_numpy(),
        "TEMPERATURE_AVG": m["temp_c"].round(3).to_numpy(),
        "WINDSPEED": m["wind_ms"].round(4).to_numpy(),
        "RADIATION": (m["solar_mj"] * 1000).round(2).to_numpy(),
    }, columns=WEATHER_COLUMNS)
    df.to_csv(out_path, index=False)
    return len(df)


def _check_original_weather(path: Path) -> None:
    header = path.open(encoding="utf-8-sig").readline().strip().split(",")
    header = [h.strip().upper() for h in header]
    if header[:len(WEATHER_COLUMNS)] != WEATHER_COLUMNS:
        log.warning("%s: header %s differs from the expected %s", path, header, WEATHER_COLUMNS)


# --------------------------------------------------------------------------- #
# Summary / README
# --------------------------------------------------------------------------- #
def _counts(s: pd.Series) -> dict:
    return {(fmt_num(k) if isinstance(k, (int, float, np.number)) else str(k)): int(v)
            for k, v in s.value_counts().sort_index().items()}


def summarize_design(design: pd.DataFrame) -> dict:
    """Counts per factor level (main group) plus control-group and weather facts."""
    main = design[design["group"] == "main"]
    ctrl = design[design["group"] == "control"]
    return {
        "n_runs": int(len(design)),
        "n_main": int(len(main)),
        "n_control": int(len(ctrl)),
        "henry": sorted({float(h) for h in design["henry"]}),
        "moisture_ref": sorted({float(m) for m in design.get("moisture_ref", [MOISTURE_REF_DEFAULT])}),
        "n_weather_files": int(design["weather_file"].nunique()),
        "n_weather_files_main": int(main["weather_file"].nunique()),
        "n_source_soils_main": int(main["source_run"].nunique()),
        "weather_source": _counts(design["weather_source"]) if "weather_source" in design else {},
        "main_levels": {f: _counts(main[f]) for f in ("app_date", "app_rate_gha", "dt50_d", "koc")},
        "control_unstable": {str(k): int(v) for k, v in
                             ctrl["source_unstable"].astype(str).value_counts().sort_index().items()},
    }


def readme_text(design: pd.DataFrame, summary: dict | None = None, n_archives: int | None = None) -> str:
    s = summary or summarize_design(design)
    lv = s["main_levels"]

    def levels(d: dict) -> str:
        return ", ".join(f"{k} ({v})" for k, v in d.items())

    henry = ", ".join(fmt_henry(h) for h in s["henry"])
    moisture = ", ".join(fmt_num(m) for m in s.get("moisture_ref", [MOISTURE_REF_DEFAULT]))
    sim = f"{design['sim_start'].iloc[0]} to {design['sim_end'].iloc[0]}" if "sim_start" in design else ""
    out = [
        "RunoffWatch designed experiment",
        "===============================",
        "",
        "What this is",
        "------------",
        "New PRZM runoff simulations for the xOffFieldSoilRisk / RunOffPrzm workstation. In the existing",
        "simulations the pesticide, dose and spray date never vary, so their effect on runoff cannot be",
        "learned from them. This design varies them on purpose. Nothing has been submitted yet.",
        "",
        f"Runs: {s['n_runs']} in total = {s['n_main']} main + {s['n_control']} control.",
        f"Simulation period: {sim}." if sim else "",
        f"Henry constant in all new runs: {henry} (the original simulations used 0.03).",
        f"Reference soil moisture for the DT50 in all new runs: {moisture} (1 = field capacity; the original",
        "simulations used 100). Both are the corrected settings also used for the local re-runs and",
        "should be confirmed by the model owners.",
        "",
        "Main group",
        "----------",
        "Each factor was drawn independently and uniformly at random (seeded, reproducible):",
        f"* soil and slope: copied from {s['n_source_soils_main']} different existing runs;",
        f"* weather: {s['n_weather_files_main']} weather files (a subset chosen once, to keep archives small);",
        f"* application date (MM-DD): {levels(lv['app_date'])};",
        f"* application rate (g/ha): {levels(lv['app_rate_gha'])};",
        f"* DT50 (days): {levels(lv['dt50_d'])};",
        f"* Koc (L/kg): {levels(lv['koc'])}.",
        "Numbers in brackets are how many runs use each level. Substance names are generic labels",
        "(S_dt50-<DT50>_koc-<Koc>), not real products.",
        "",
        "Control group",
        "-------------",
        "Existing runs repeated exactly as originally simulated (application 03-01, 2400 g/ha, DT50 41.68 d,",
        "Koc 377.5, their own soil and their own weather) except the Henry constant and the reference soil",
        "moisture. About half come from runs",
        f"that became numerically unstable, half from stable runs ({s['control_unstable']}). Purpose: test whether",
        "the Henry constant 0.03 of the original runs caused the numerical breakdown.",
        "",
        "Weather",
        "-------",
    ]
    ws = s.get("weather_source", {})
    if ws.get(RECONSTRUCTED):
        out += [f"{ws[RECONSTRUCTED]} runs use weather RECONSTRUCTED from the PRZM .met files of the existing runs",
                "(rain, pan evaporation written as ET0, temperature, wind, radiation MJ*1000 -> kJ/m2/day).",
                "Values may differ from the original MARS files (ET0 vs. pan evaporation, rounding).",
                "Replace them with the original MARS weather files if these are available."]
    if ws.get(ORIGINAL_WEATHER):
        out.append(f"{ws[ORIGINAL_WEATHER]} runs use original MARS weather files.")
    out += [
        "",
        "Files",
        "-----",
        "design.csv    one row per run (factors, source run, soil as written to the run file)",
        "xrun/         one .xrun parameter file per run",
        "weather/      the weather CSVs referenced by the runs",
        "tasks/        7z task archives for the workstation" + (f" ({n_archives})" if n_archives else ""),
        "",
        "Important",
        "---------",
        APP_WINDOW_NOTE,
        "",
    ]
    return "\n".join(line for line in out if line is not None)


# --------------------------------------------------------------------------- #
# Writing
# --------------------------------------------------------------------------- #
_OUTPUTS = ("design.csv", "README.txt", "xrun", "weather", "tasks")


def write_design(design: pd.DataFrame, out_dir: str | Path, runs_root: str | Path = "data/raw/runs",
                 weather_dir: str | Path | Mapping | None = None, batch_size: int = 1000,
                 name: str = "rw", overwrite: bool = False) -> dict:
    """Write design.csv, README.txt, xrun/, weather/ and tasks/<name>_batch_NNN.7z to `out_dir`.

    Weather: original MARS CSVs from `weather_dir` (folder of `<met_hash>.csv` or a
    mapping met_hash -> path) are preferred; otherwise the CSV is reconstructed from
    `<runs_root>/<weather_batch>/<weather_run>/focusprzm_weather.met`.
    Each archive holds at most `batch_size` xrun files plus exactly the weather CSVs
    they reference, all in the archive root.
    """
    import py7zr

    if batch_size < 1:
        raise ValueError(f"batch_size must be >= 1, got {batch_size}")
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", name):
        raise ValueError(f"Archive name prefix {name!r} may only contain letters, digits, '_', '-', '.'")
    if design.empty:
        raise ValueError("Empty design")
    if design["run_id"].duplicated().any():
        raise ValueError("Duplicate run_id in design")
    out_dir = Path(out_dir)
    if out_dir.exists() and any(out_dir.iterdir()):
        if not overwrite:
            raise FileExistsError(f"{out_dir} is not empty (pass overwrite=True to replace the design files)")
        for item in _OUTPUTS:
            p = out_dir / item
            if p.is_dir():
                shutil.rmtree(p)
            elif p.exists():
                p.unlink()
    xrun_dir, weather_out, tasks_dir = out_dir / "xrun", out_dir / "weather", out_dir / "tasks"
    for d in (xrun_dir, weather_out, tasks_dir):
        d.mkdir(parents=True, exist_ok=True)

    design = design.copy()
    sim_start = str(design["sim_start"].iloc[0]) if "sim_start" in design else SIM_START
    sim_end = str(design["sim_end"].iloc[0]) if "sim_end" in design else SIM_END
    if "sim_start" in design and (design["sim_start"].nunique() > 1 or design["sim_end"].nunique() > 1):
        raise ValueError("All runs of a design must share one simulation period")

    # Weather files (one per distinct weather_file)
    sources = {}
    first = design.drop_duplicates("weather_file")
    for _, r in first.iterrows():
        target = weather_out / r["weather_file"]
        orig = _resolve_weather(r["met_hash"], weather_dir)
        if orig is not None:
            if not orig.is_file():
                raise FileNotFoundError(f"Weather file for {r['met_hash']} not found: {orig}")
            _check_original_weather(orig)
            shutil.copyfile(orig, target)
            sources[r["weather_file"]] = ORIGINAL_WEATHER
        else:
            met = Path(runs_root) / str(r["weather_batch"]) / str(r["weather_run"]) / MET_FILE
            met_to_weather_csv(met, target, sim_start, sim_end)
            sources[r["weather_file"]] = RECONSTRUCTED
    design["weather_source"] = design["weather_file"].map(sources)
    n_rec = sum(v == RECONSTRUCTED for v in sources.values())
    if n_rec:
        log.warning("%d of %d weather files were RECONSTRUCTED from PRZM .met files (ET0 = pan evaporation, "
                    "rounding may differ from the original MARS files)", n_rec, len(sources))

    # xrun files
    for _, r in design.iterrows():
        (xrun_dir / f"{r['run_id']}.xrun").write_text(render_xrun(r), encoding="utf-8")

    # Archives
    archives = []
    for b, start in enumerate(range(0, len(design), batch_size), start=1):
        chunk = design.iloc[start:start + batch_size]
        path = tasks_dir / f"{name}_batch_{b:03d}.7z"
        with py7zr.SevenZipFile(path, "w") as z:
            for rid in chunk["run_id"]:
                z.write(xrun_dir / f"{rid}.xrun", arcname=f"{rid}.xrun")
            for wf in sorted(chunk["weather_file"].unique()):
                z.write(weather_out / wf, arcname=wf)
        archives.append({"path": str(path), "n_xrun": int(len(chunk)),
                         "n_weather": int(chunk["weather_file"].nunique()),
                         "size_bytes": path.stat().st_size,
                         "first_run": chunk["run_id"].iloc[0], "last_run": chunk["run_id"].iloc[-1]})

    design.to_csv(out_dir / "design.csv", index=False)
    summary = summarize_design(design)
    (out_dir / "README.txt").write_text(readme_text(design, summary, len(archives)), encoding="utf-8")
    log.info("Design written to %s: %d runs, %d weather files, %d archives",
             out_dir, len(design), len(sources), len(archives))
    return {
        "out_dir": str(out_dir),
        "design_csv": str(out_dir / "design.csv"),
        "readme": str(out_dir / "README.txt"),
        "n_runs": int(len(design)),
        "n_xrun": int(len(design)),
        "n_weather_files": len(sources),
        "n_weather_reconstructed": n_rec,
        "n_archives": len(archives),
        "archives": archives,
        "total_archive_bytes": int(sum(a["size_bytes"] for a in archives)),
        "summary": summary,
    }
