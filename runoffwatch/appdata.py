"""
Helpers for the Streamlit app (`app.py`): find the result files, read them safely, format numbers.

Everything here is plain Python (no Streamlit), so it can be unit-tested. The result files can be
missing, half-written or have other columns while a training job rewrites them: every reader then
returns None, and the app shows a short "not available yet" note instead of failing.
"""

from __future__ import annotations

import json
import math
import re
from pathlib import Path

import pandas as pd

from .paths import DATASETS

CAUTION = ("These numbers copy the simulator PRZM with one crop (winter cereals) and a fixed crop "
           "calendar. They are not field measurements.")
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
MONTH_NAMES = ["January", "February", "March", "April", "May", "June", "July", "August",
               "September", "October", "November", "December"]


# --------------------------------------------------------------------------- #
# Where things are
# --------------------------------------------------------------------------- #
def model_set(root: str | Path = ".") -> dict:
    """The model set the app uses: the varied one if `models/varied/meta.json` exists, else the standard one.

    Returns paths (relative to `root`) and a short name: {"name", "models", "results", "figures"}.
    """
    root = Path(root)
    if (root / "models/varied/meta.json").exists():
        return {"name": "varied", "models": root / "models/varied", "results": root / "docs/results/varied",
                "figures": root / "docs/figures/varied"}
    return {"name": "standard", "models": root / "models", "results": root / "docs/results",
            "figures": root / "docs/figures"}


def mtime(path: str | Path) -> float | None:
    """Modification time of a file (part of the cache key, so a changed file is read again); None if missing."""
    try:
        return Path(path).stat().st_mtime
    except OSError:
        return None


def find_scenarios(results_dir: str | Path) -> list[Path]:
    """Folders with a 45-year run (`france_by_year.csv`): the results folder itself, then its sub-folders.

    Sub-folders that hold the results of another data set (e.g. `docs/results/varied` seen from
    `docs/results`) are not scenarios of this one and are left out.
    """
    results_dir = Path(results_dir)
    other_sets = {Path(d["results"]).resolve() for d in DATASETS.values()} - {results_dir.resolve()}
    out = [results_dir] if (results_dir / "france_by_year.csv").is_file() else []
    if results_dir.is_dir():
        for sub in sorted(p for p in results_dir.iterdir() if p.is_dir()):
            if sub.resolve() not in other_sets and (sub / "france_by_year.csv").is_file():
                out.append(sub)
    return out


# --------------------------------------------------------------------------- #
# Reading files safely
# --------------------------------------------------------------------------- #
def read_json(path: str | Path) -> dict | None:
    """A JSON file as a dict, or None if it is missing, half-written or not an object."""
    try:
        data = json.loads(Path(path).read_text())
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def read_csv(path: str | Path, required: tuple[str, ...] = (), numeric: tuple[str, ...] = ()) -> pd.DataFrame | None:
    """A CSV file, or None if it is missing, unreadable, empty or lacks a `required` column.

    Columns in `numeric` are turned into numbers (bad cells become NaN) and rows where any of them
    is NaN are dropped, so a half-written last line does no harm. Extra columns are kept.
    """
    try:
        df = pd.read_csv(path)
    except (OSError, ValueError, pd.errors.ParserError, pd.errors.EmptyDataError):
        return None
    if df.empty or any(c not in df.columns for c in (*required, *numeric)):
        return None
    for c in numeric:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    if numeric:
        df = df.dropna(subset=list(numeric))
    return None if df.empty else df.reset_index(drop=True)


def dig(data, *keys, default=None):
    """data[k1][k2]... or `default` when a key is missing or a level is not a dict."""
    for k in keys:
        if not isinstance(data, dict) or k not in data:
            return default
        data = data[k]
    return data


def number(x) -> float | None:
    """x as a finite float, or None."""
    try:
        x = float(x)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


# --------------------------------------------------------------------------- #
# Formatting
# --------------------------------------------------------------------------- #
def fmt_gha(x, unit: bool = True) -> str:
    """g/ha with sensible decimals: 1234 -> '1,234', 12.3 -> '12.3', 1.234 -> '1.23', 0.0042 -> '0.004'."""
    x = number(x)
    if x is None:
        return "n/a"
    a = abs(x)
    if a >= 100:
        s = f"{x:,.0f}"
    elif a >= 10:
        s = f"{x:.1f}"
    elif a >= 0.1 or a == 0:
        s = f"{x:.2f}"
    elif a >= 0.001:
        s = f"{x:.3f}"
    else:
        s = "less than 0.001"
    return f"{s} g/ha" if unit else s


def fmt_pct(x, decimals: int = 1, share: bool = False) -> str:
    """A percentage with 0-1 decimals. With share=True, x is a share (0.92 -> '92%')."""
    x = number(x)
    if x is None:
        return "n/a"
    return f"{100 * x if share else x:.{decimals}f}%"


def fmt_pct_small(x) -> str:
    """A small percentage of the dose: one decimal, or two significant digits below 0.1% (0.078 -> '0.078%')."""
    x = number(x)
    if x is None:
        return "n/a"
    return f"{x:.1f}%" if abs(x) >= 0.1 or x == 0 else f"{x:.2g}%"


def fmt_r2(x) -> str:
    x = number(x)
    return "n/a" if x is None else f"{x:.2f}"


def fmt_day(d) -> str:
    """A date as 'Tue 3 Mar 2026'."""
    t = pd.Timestamp(d)
    return f"{t:%a} {t.day} {t:%b %Y}"


def spraying_text(spraying: dict | None) -> str:
    """`{"day": 1, "month": 3, "rate_kgha": 2.4}` -> 'sprayed on 1 March with 2.4 kg/ha (2,400 g/ha)'."""
    day, month, rate = (number(dig(spraying, k)) for k in ("day", "month", "rate_kgha"))
    if day is None or month is None or not 1 <= month <= 12:
        return "spraying not stated"
    text = f"sprayed on {day:.0f} {MONTH_NAMES[int(month) - 1]}"
    return text + (f" with {rate:g} kg/ha ({1000 * rate:,.0f} g/ha)" if rate is not None else "")


def scenario_label(folder: Path, summary: dict | None, results_dir: Path) -> str:
    """Name of a 45-year scenario for the selector, from its `france_summary.json`."""
    spraying = dig(summary, "spraying")
    base = "Standard run" if Path(folder) == Path(results_dir) else f"Scenario '{Path(folder).name}'"
    return f"{base}: {spraying_text(spraying)}" if spraying else base


# --------------------------------------------------------------------------- #
# Spray windows and the advisor text
# --------------------------------------------------------------------------- #
def spray_windows(days) -> str:
    """Spray days of the year as date ranges, e.g. '15 Feb-30 Apr and 1 Oct-30 Nov'.

    The same date is one day later in a leap year (after February), so a range starts with the
    date of a common year and ends with the date of a leap year.
    """
    days = sorted(int(d) for d in days)
    if not days:
        return "no spray days"
    groups, start = [], days[0]
    for a, b in zip(days, days[1:] + [None]):
        if b is None or b - a > 3:
            groups.append((start, a))
            start = b

    def text(d, year):
        t = pd.Timestamp(year=year, month=1, day=1) + pd.Timedelta(days=d - 1)
        return f"{t.day} {t:%b}"

    return " and ".join(text(a, 2001) if text(a, 2001) == text(b, 2000) else f"{text(a, 2001)}-{text(b, 2000)}"
                        for a, b in groups)


def spray_limits(meta: dict) -> str:
    """The 'Limits' lines about spray date and dose, true for the models that were loaded."""
    on = dig(meta, "trained_on", default={}) or {}
    days = on.get("spray_days_seen") or [60, 61]
    doses = [1000 * float(d) for d in on.get("doses_kgha") or [2.4]]
    if len(days) <= 2 and len(doses) == 1:           # models that only know the delivered runs
        return (f"- These models only know **spraying on {spray_windows(days)} with {doses[0]:,.0f} g/ha**. "
                "Another dose is scaled in proportion, and another spray day is a guess.\n"
                "- In those runs \"days since spraying\" and the calendar date move together, so the model "
                "cannot tell them apart. Moving the spray day is new to it.\n")
    return (f"- These models learned from runs sprayed **{spray_windows(days)}**, with doses of "
            f"**{min(doses):,.0f} to {max(doses):,.0f} g/ha**. A spray day or dose outside these is a guess.\n")


def headline(ranked: pd.DataFrame, horizon: int) -> str:
    """The advisor's result in one sentence. `ranked`: ranked rows of `compare_spray_days`."""
    r = ranked.sort_values("predicted_loss_gha")
    best, worst = r.iloc[0], r.iloc[-1]
    text = (f"Lowest predicted loss: spraying on **{fmt_day(best.spray_date)}**: "
            f"**{fmt_gha(best.predicted_loss_gha)}** in the following {horizon} days.")
    if len(r) > 1:
        text += f" Highest: spraying on **{fmt_day(worst.spray_date)}**: **{fmt_gha(worst.predicted_loss_gha)}**."
    return text


def weather_template(weather: pd.DataFrame) -> str:
    """CSV text in the upload format (date, rain_mm, temp_c, pan_evap_mm) from a daily weather table."""
    w = weather.copy()
    w.index = pd.to_datetime(w.index).strftime("%Y-%m-%d")
    cols = [c for c in ("rain_mm", "temp_c", "pan_evap_mm") if c in w.columns]
    return w[cols].rename_axis("date").reset_index().to_csv(index=False)


def half_month(label: str) -> str:
    """'03 Mar 1-15' -> 'Mar 1-15', '02 Feb 16-end' -> 'Feb 16-end' (the leading number only sorts)."""
    parts = str(label).split(" ", 1)
    return parts[1] if len(parts) == 2 and parts[0].isdigit() else str(label)


def first_year(text: str) -> int:
    """The first four-digit year in a text ('before (1979-2005)' -> 1979), or 9999 if there is none."""
    m = re.search(r"(1[89]|20)\d\d", str(text))
    return int(m.group(0)) if m else 9999


def season(label: str) -> str:
    """'03 Mar 1-15' -> 'Spring (Feb-Apr)', '10 Oct 1-15' -> 'Autumn (Oct-Nov)'."""
    head = str(label).split(" ", 1)[0]
    if head.isdigit():
        return "Autumn (Oct-Nov)" if int(head) >= 8 else "Spring (Feb-Apr)"
    return "Other"
