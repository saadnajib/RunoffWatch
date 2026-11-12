"""
Read the field / soil / pesticide settings of one run from its PRZM 3 `.inp` file.

The `.inp` files written by xLandscape all share one layout (73 lines), so the
values are read by position, anchored on two marker lines ("Chemical Input
Data" and "Soil Series") so that a shifted or different file is rejected
instead of being read wrongly.

Only settings that matter for runoff are returned. Names follow the PRZM
manual where one exists (USLEK, CN, BD, THEFC, ...), in lower case.
"""

from __future__ import annotations

from pathlib import Path

N_HORIZONS = 4


class InpFormatError(ValueError):
    """The .inp file does not have the layout this reader expects."""


def _floats(line: str) -> list[float]:
    return [float(x) for x in line.split()]


def parse_inp(path: str | Path) -> dict:
    """Return a flat dict of run settings.

    Field (erosion / hydrology):
        usle_k, usle_ls, usle_p   USLE soil erodibility, slope-length and practice factors
        slope_pct                 field slope in %
        cn_1..cn_4                SCS curve number for the 4 crop periods of the year
    Soil, per horizon h = 1..4 (depths 0-10, 10-30, 30-60, 60-100 cm in these runs):
        h{h}_thick_cm, h{h}_bd (bulk density g/cm3), h{h}_fc, h{h}_wp (field capacity,
        wilting point, cm3/cm3), h{h}_oc (organic carbon %), h{h}_kd (sorption, cm3/g),
        h{h}_sand, h{h}_clay (%)
    Pesticide:
        pesticide, app_rate_kgha, app_day, app_month, n_apps, henry (dimensionless),
        decay_rate_per_day (dissolved phase, horizon 1)
    """
    lines = Path(path).read_text(errors="replace").splitlines()
    try:
        chem = next(i for i, l in enumerate(lines) if l.startswith("Chemical Input Data"))
        soil = next(i for i, l in enumerate(lines) if l.startswith("Soil Series"))
    except StopIteration:
        raise InpFormatError(f"{path}: marker lines not found (not a PRZM .inp, or run did not start)")

    try:
        out: dict = {}
        # --- field block: record with USLEK USLELS USLEP AFIELD IREG SLP HL --------
        f = _floats(lines[4])
        if len(f) != 7:
            raise InpFormatError(f"{path}: line 5 should have 7 numbers, has {len(f)}")
        out.update(usle_k=f[0], usle_ls=f[1], usle_p=f[2], slope_pct=f[5])
        cn = _floats(lines[11])
        if len(cn) != 4 or not all(30 <= c <= 100 for c in cn):
            raise InpFormatError(f"{path}: line 12 is not 4 curve numbers: {lines[11]!r}")
        out.update({f"cn_{i + 1}": c for i, c in enumerate(cn)})

        # --- pesticide block ---------------------------------------------------
        n_apps = int(lines[chem + 1].split()[0])
        out["pesticide"] = lines[chem + 2].strip()
        apps = [lines[chem + 3 + i].split() for i in range(n_apps)]
        first = apps[0]
        out.update(n_apps=n_apps, app_day=int(first[0][0:2]), app_month=int(first[0][2:4]),
                   app_rate_kgha=float(first[4]))
        if len({(a[0][:4], a[4]) for a in apps}) != 1:
            out["app_varies_between_years"] = True

        # --- volatilisation: 'DAIR HENRYK ENPY' in fixed 8-character columns ---
        vol = lines[soil + 2]
        out["henry"] = float(vol[8:16])

        # --- soil horizons -------------------------------------------------------
        n_hor = int(lines[soil + 8].split()[0])
        if n_hor != N_HORIZONS:
            raise InpFormatError(f"{path}: expected {N_HORIZONS} soil horizons, found {n_hor}")
        for h in range(N_HORIZONS):
            base = soil + 9 + 4 * h
            a, b, c, d = (_floats(lines[base + k]) for k in range(4))
            if int(a[0]) != h + 1:
                raise InpFormatError(f"{path}: horizon {h + 1} not where expected")
            p = f"h{h + 1}_"
            out.update({p + "thick_cm": a[1], p + "bd": a[2], p + "fc": c[1], p + "wp": c[2],
                        p + "oc": c[3], p + "kd": c[4], p + "sand": d[1], p + "clay": d[2]})
            if h == 0:
                out["decay_rate_per_day"] = b[0]
    except (IndexError, ValueError) as e:
        if isinstance(e, InpFormatError):
            raise
        raise InpFormatError(f"{path}: unexpected layout ({e})")
    return out


# Settings that actually differ between runs in the project data set and are
# therefore useful as model inputs. (Curve numbers move together, so one is kept.)
SOIL_FEATURES = [
    "usle_k", "usle_ls", "slope_pct", "cn_2",
    "h1_bd", "h1_fc", "h1_wp", "h1_oc", "h1_kd", "h1_sand", "h1_clay",
    "h3_bd", "h3_oc",
]
