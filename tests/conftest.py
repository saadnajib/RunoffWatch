"""Shared fixtures: build small, synthetic but format-correct PRZM_SW run folders.

The files mimic what FOCUS PRZM_SW 3.x writes (column layout, units, header
lines), but every number here is made up. No real simulation data is used.

Raw units written to disk:
    .met : MMDDYY, precip cm/day, pan evap cm/day, temp C, wind cm/s, solar langley/day
    .ZTS : value_in_PRZM_unit * TSER scale factor from the .inp
           (PRCP/RUNF/INFL cm * 10 -> written value is mm,
            RFLX1/EFLX1 g/cm2 * 1e8 -> written value is g/ha,
            TPAP g/cm2 * 1.0, ESLS tonnes * 1e3)
"""

from __future__ import annotations

import os
import sys

# Keep LightGBM / OpenMP light in tests (must be set before lightgbm is imported).
os.environ.setdefault("OMP_NUM_THREADS", "2")
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Order of the variables in the .ZTS (same as the FOCUS template)
ZTS_VARS = ["RUNF", "ESLS", "PRCP", "INFL", "RFLX1", "EFLX1", "TPAP"]
DEFAULT_FACTORS = {"RUNF": "10.0", "ESLS": "1.E3", "PRCP": "10.0", "INFL": "10.0",
                   "RFLX1": "1.E8", "EFLX1": "1.E8", "TPAP": "1.0"}

STABLE_DECAY = [0.169, 0.310, 0.420, 0.470, 0.490, 0.500]
UNSTABLE_DECAY = [0.169, 0.310, 0.640, 1.90, 8.87, 82.1, 996.6, 7076.5]

APPLIED_G_PER_CM2 = 2.4e-5           # = 2400 g/ha (2.4 kg/ha)


def fortran_num(v: float) -> str:
    """Format like PRZM's ZTS output: '0.000' for zero, otherwise E notation."""
    if v == 0:
        return "0.000"
    if 0.1 <= abs(v) < 1000:
        return f"{v:.4g}"
    return f"{v:.4E}"


def met_line(date: pd.Timestamp, rain_cm, evap_cm, temp_c, wind_cms, solar_ly) -> str:
    return (f" {date:%m%d%y}  {rain_cm:9.4f} {evap_cm:9.4f} {temp_c:9.4f} "
            f"{wind_cms:9.4f} {solar_ly:9.4f}")


def zts_header(title: str = "Run 1", names=ZTS_VARS) -> list[str]:
    return [
        " TSRTIME SERIES OUTPUT FILES",
        f" TSR  {title}".ljust(90),
        " TSR                   " + "".join(f"{n:>14}" for n in names) + " ",
    ]


def zts_line(date: pd.Timestamp, values) -> str:
    return (f" TSR PRZ  {date.year:4d} {date.month:2d} {date.day:2d}     "
            + "".join(f"{fortran_num(v):>16}" for v in values) + "    ")


def write_inp(path: Path, factors: dict[str, str]) -> None:
    tser = [f"    {name:<7} TSER   0   0  {fac}" for name, fac in factors.items()]
    lines = [
        "Run 1",
        "                    Simulation Location: R1Crop: Synthetic",
        "    0.84    0.20       0      15       1       1",
        "  010390  0 2    5  2.40    1    0",
        "    WATR    YEAR      10    PEST    YEAR      10    CONC    YEAR      10   0",
        f"{len(tser):8d}    DAY ",
        *tser,
    ]
    path.write_text("\n".join(lines) + "\n")


DEFAULT_HORIZONS = [
    # thick_cm, bd, fc, wp, oc, kd, sand, clay   (made-up values)
    dict(thick=10, bd=1.410, fc=0.270, wp=0.117, oc=0.600, kd=2.265, sand=34, clay=18),
    dict(thick=20, bd=1.420, fc=0.260, wp=0.110, oc=0.550, kd=2.076, sand=35, clay=19),
    dict(thick=30, bd=1.430, fc=0.250, wp=0.105, oc=0.400, kd=1.510, sand=36, clay=20),
    dict(thick=40, bd=1.440, fc=0.240, wp=0.100, oc=0.300, kd=1.133, sand=37, clay=21),
]


def full_inp_lines(*, usle_k=0.34, usle_ls=0.11, usle_p=0.50, slope=2.5,
                   cn=(81, 81, 86, 91), pesticide="Synthocide", n_apps=10,
                   app_day=1, app_month=3, app_rate=2.40, app_rates=None,
                   henry_field="0.30E-01", decay=0.01663, horizons=None,
                   n_horizons=None, factors=None) -> list[str]:
    """The 73 lines of a PRZM 3 `.inp` in the layout xLandscape writes (all values made up).

    `n_horizons` overrides only the horizon-count line (to build broken files);
    `app_rates` gives one rate per application year.
    """
    horizons = DEFAULT_HORIZONS if horizons is None else horizons
    factors = DEFAULT_FACTORS if factors is None else factors
    rates = app_rates if app_rates is not None else [app_rate] * n_apps
    crop_years = [f"  1211{89 + i:02d}  1006{90 + i:02d}  3107{90 + i:02d}       1" for i in range(10)]
    lines = [
        "Run 1",
        "                    Simulation Location: R1Crop: Synthetic",
        "    0.84    0.20       0      15       1       1",
        "       4",
        f"{usle_k:8.2f}{usle_ls:8.2f}{usle_p:8.2f}    0.45               3{slope:8g}      20",
        "       1",
        "       1    0.15     100      90       3   0   0   0       0     110",
        "       1       4",
        "1211 1006 3107 0111",
        "0.20 0.20 0.40 0.90",
        "0.10 0.10 0.10 0.10",
        "".join(f"{c:5g}" for c in cn),
        f"{len(crop_years):8d}",
        *crop_years,
        "Chemical Input Data: ",
        f"{n_apps:8d}       1       0       0",
        f"{pesticide:<12}",
        *[f"  {app_day:02d}{app_month:02d}{90 + i:02d}  0 2    5  {rates[i]:.2f}    1    0" for i in range(n_apps)],
        "       0       1       0",
        "       0    0.07    0.50",
        "Soil Series:         R1",
        "     100           0   0   2   0   0   0   2   1   0",
        f"    4300{henry_field:>8}   22.70",
        "    0.92",
        " 0.18 0.18 0.18 0.18 0.18 0.18 0.18 0.18 0.18 0.18 0.18 0.18 0.96   10",
        "   10   10   10   10   10   10   10   10   10   10   10   10",
        "    2.20      20",
        "       2    0.70     100",
        f"{len(horizons) if n_horizons is None else n_horizons:8d}",
    ]
    for h, hz in enumerate(horizons, start=1):
        lines += [
            f"{h:8d}{hz['thick']:8g}{hz['bd']:8.3f}   0.270       0       0       0",
            f"        {decay:8.5f}{decay:8.5f}       0",
            f"        {5:8g}{hz['fc']:8.3f}{hz['wp']:8.3f}{hz['oc']:8.3f}{hz['kd']:8.3f}",
            f"        {10:8d}{hz['sand']:8g}{hz['clay']:8g}       0       0",
        ]
    lines += [
        "       0",
        "    WATR    YEAR      10    PEST    YEAR      10    CONC    YEAR      10   0",
        f"{len(factors):8d}    DAY ",
        *[f"    {name:<7} TSER   0   0  {fac}" for name, fac in factors.items()],
    ]
    return lines


def write_full_inp(path: Path, lines: list[str] | None = None, **kwargs) -> Path:
    """Write a full synthetic PRZM .inp (see full_inp_lines) and return its path."""
    path = Path(path)
    path.write_text("\n".join(lines if lines is not None else full_inp_lines(**kwargs)) + "\n")
    return path


def write_out(path: Path, decay: list[float]) -> None:
    lines = [" PRZM-3 OUTPUT (synthetic)", ""]
    for i, v in enumerate(decay):
        lines += [
            f" ANNUAL SUMMARY  YEAR {i + 1}",
            " PST",
            " PST TOTAL PLANT UPTAKE OF PESTICIDE        0.0000000    ",
            f" PST TOTAL SOIL DECAY OF PESTICIDE         {v:.8g}    ",
            " PST TOTAL EROSION OF PESTICIDE            0.88552383E-07",
            "",
        ]
    path.write_text("\n".join(lines) + "\n")


def write_log(path: Path, error: bool) -> None:
    lines = ["OK    Creating new X3dfStore at", "      C:\\synthetic\\store",
             "INFO  MC run start", "INFO  Running component Weather",
             "INFO  Component Weather finished"]
    if error:
        lines.append("ERROR 1: TIFFOpen:C:\\synthetic\\runoff_grd.tif: No such file or directory")
    lines.append("INFO  MC run finished")
    path.write_text("\n".join(lines) + "\n")


@dataclass
class SyntheticRun:
    folder: Path
    dates: pd.DatetimeIndex
    met: pd.DataFrame                     # raw .met values (cm, cm/s, ly)
    zts: pd.DataFrame                     # values as written to the .ZTS
    snow_idx: int | None = None
    files: dict[str, Path] = field(default_factory=dict)


def build_run(base: Path, *, name: str = "run_0000001_grid_000001", days: int = 60,
              start: str = "1990-01-01", unstable: bool = False, snow_day: bool = False,
              warm_mismatch: bool = False, log_error: bool = False,
              decay: list[float] | None = None, zts_days: int | None = None,
              app_days: tuple[int, ...] = (5,), runoff_gha: float = 0.38,
              write_out_file: bool = True, factors: dict[str, str] | None = None) -> SyntheticRun:
    folder = base / name
    folder.mkdir(parents=True)
    dates = pd.date_range(start, periods=days, freq="D")

    rain = [0.5 if i % 5 == 3 else (0.1 if i % 7 == 1 else 0.0) for i in range(days)]
    temp = [6.0 + (i % 4) for i in range(days)]
    snow_idx = None
    if snow_day:
        snow_idx = min(10, days - 1)
        rain[snow_idx] = 0.3
        temp[snow_idx] = -2.5
    met = pd.DataFrame({
        "rain_cm": rain,
        "evap_cm": [0.048] * days,
        "temp_c": temp,
        "wind_cms": [300.0 + 10 * (i % 3) for i in range(days)],
        "solar_ly": [250.0] * days,
    }, index=dates)
    met_file = folder / "focusprzm_weather.met"
    met_file.write_text("\n".join(met_line(d, *row) for d, row in zip(dates, met.itertuples(index=False))) + "\n")

    # Results PRZM would write (already multiplied by the TSER factors)
    prcp = [r * 10 for r in rain]                           # cm * factor 10 -> written value = mm
    if snow_idx is not None:
        prcp[snow_idx] = 0.0                                # snow is not in PRCP
    if warm_mismatch:
        warm_idx = 13
        assert temp[warm_idx] > 0
        prcp[warm_idx] += 3.0                               # 3 mm off on a warm day
    runf = [p * 0.1 if p >= 5 else 0.0 for p in prcp]
    rflx = [runoff_gha if p >= 5 else 0.0 for p in prcp]
    tpap = [APPLIED_G_PER_CM2 if i in app_days else 0.0 for i in range(days)]
    zts = pd.DataFrame({
        "RUNF": runf,
        "ESLS": [r * 0.1 for r in runf],
        "PRCP": prcp,
        "INFL": [p * 0.8 for p in prcp],
        "RFLX1": rflx,
        "EFLX1": [r * 1e-3 for r in rflx],
        "TPAP": tpap,
    }, index=dates)
    zts_rows = zts if zts_days is None else zts.iloc[:zts_days]

    zts_file = folder / "RUN 1-1_A1234567890.ZTS"
    zts_file.write_text("\n".join(zts_header() + [zts_line(d, row) for d, row in
                                                  zip(zts_rows.index, zts_rows[ZTS_VARS].itertuples(index=False))]) + "\n")

    inp_file = folder / "Run 1-1_a1234567890.inp"
    write_inp(inp_file, factors if factors is not None else DEFAULT_FACTORS)

    files = {"met": met_file, "zts": zts_file, "inp": inp_file}
    if write_out_file:
        out_file = folder / "RUN 1-1_A1234567890.OUT"
        write_out(out_file, decay if decay is not None else (UNSTABLE_DECAY if unstable else STABLE_DECAY))
        files["out"] = out_file
    (folder / "Run 1.run").write_text("PRZM                    ON\nVADOFT                  OFF\nENDRUN\n")
    write_log(folder / "mc.log", log_error)
    files["log"] = folder / "mc.log"
    return SyntheticRun(folder=folder, dates=dates, met=met, zts=zts, snow_idx=snow_idx, files=files)


@pytest.fixture
def make_run(tmp_path):
    """Factory: make_run(days=60, unstable=False, snow_day=False, log_error=False, ...)
    -> SyntheticRun. Each call creates a new folder under tmp_path."""
    counter = iter(range(1, 10_000))

    def _make(**kwargs) -> SyntheticRun:
        kwargs.setdefault("name", f"run_{next(counter):07d}_grid_000001")
        return build_run(tmp_path, **kwargs)

    return _make
