"""
RunoffWatch - interface to the whole project (Streamlit).

Start from the repository root with:

    streamlit run app.py

Five tabs: compare spray days (the advisor), how good the copy of PRZM is, what the simulations
say about the spray date, 45 years of French weather, and about/limits. The app reads the models
in `models/` and the result files in `docs/results/` (and `docs/figures/`) at run time; a missing
or half-written result file shows a short "not available yet" note. The simulation data itself is
not needed. The numbers come from a machine-learning copy (surrogate) of the PRZM model, not from
field measurements.
"""

from __future__ import annotations

import warnings
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

from runoffwatch import appdata as ad
from runoffwatch.models import MODEL_FILES
from runoffwatch.whatif import (CN_SETS, compare_spray_days, example_weather, load_models, predict_days,
                                prepare_weather, soil_settings)

st.set_page_config(page_title="RunoffWatch", layout="wide")
SET = ad.model_set()
EXAMPLE_FIRST_DAY = "2026-03-06"     # with the example weather: candidates before, during and after a storm
NOT_YET = "Not available yet: {what} is missing or being rewritten. Reload the page later."
SCORES = {"runoff_r2": "Runoff R²", "loss_r2": "Pesticide loss R²",
          "alarm_precision": "Alarms that are right", "alarm_recall": "High-loss days found"}


# --------------------------------------------------------------------------- #
# Cached reading (the file's modification time is part of the key)
# --------------------------------------------------------------------------- #
@st.cache_data(show_spinner=False)
def _csv(path: str, stamp, required: tuple, numeric: tuple):
    return ad.read_csv(path, required, numeric)


@st.cache_data(show_spinner=False)
def _json(path: str, stamp):
    return ad.read_json(path)


def csv(path, required=(), numeric=()):
    return _csv(str(path), ad.mtime(path), tuple(required), tuple(numeric))


def jsn(path):
    return _json(str(path), ad.mtime(path))


@st.cache_resource(show_spinner="Loading the models ...")
def _models(model_dir: str, stamp):
    return load_models(model_dir)


def get_models():
    """(models, None) or (None, error text)."""
    d = SET["models"]
    try:
        return _models(str(d), tuple(ad.mtime(d / f) for f in [*MODEL_FILES.values(), "meta.json"])), None
    except Exception as e:  # missing or half-written model file
        return None, f"The models in `{d}` could not be loaded ({e})."


def colors() -> dict:
    """Chart colours, stepped for the light or the dark theme (validated categorical slots 1-4)."""
    try:
        dark = st.context.theme.type == "dark"
    except Exception:
        dark = False
    if dark:
        return {"cat": ["#338ced", "#e76624", "#00a888", "#d28e05"], "muted": "#6b6b6b",
                "seq": ["#0f4a96", "#cce3fd"]}
    return {"cat": ["#257de0", "#f47230", "#00b894", "#f2a600"], "muted": "#b4b4b4",
            "seq": ["#cce3fd", "#0e3d7e"]}


def show(chart):
    st.altair_chart(chart, width="stretch")


# --------------------------------------------------------------------------- #
# Tab 1: compare spray days
# --------------------------------------------------------------------------- #
def step_weather():
    with st.container(border=True):
        st.markdown("#### Step 1 · Weather")
        source = st.radio("Weather source", ["Example weather (made up)", "Upload my own CSV"],
                          horizontal=True, label_visibility="collapsed")
        st.download_button("Download a template CSV", ad.weather_template(prepare_weather(example_weather())),
                           file_name="weather_template.csv", mime="text/csv")
        st.caption("Columns: `date, rain_mm, temp_c`, optional `pan_evap_mm`. One row per day: "
                   "about 30 days before the first spray day, then the forecast.")
        raw = example_weather()
        if source.startswith("Upload"):
            up = st.file_uploader("Daily weather CSV", type="csv")
            if up is None:
                st.info("Upload a file to continue, or switch to the example.")
                return None, False
            raw = pd.read_csv(up)
        try:
            weather = prepare_weather(raw)
        except Exception as e:  # tell the reader what is wrong with the file
            st.error(f"Could not use this weather file: {e}")
            return None, False
        rain = weather["rain_mm"].rename_axis("date").reset_index()
        show(alt.Chart(rain, height=130).mark_bar(color=colors()["cat"][0], cornerRadiusEnd=2).encode(
            x=alt.X("date:T", title=None), y=alt.Y("rain_mm:Q", title="Rain (mm/day)"),
            tooltip=[alt.Tooltip("date:T", title="Day"), alt.Tooltip("rain_mm:Q", title="Rain (mm)")]))
        st.caption(f"{len(weather)} days, {ad.fmt_day(weather.index[0])} to {ad.fmt_day(weather.index[-1])}; "
                   f"{weather['rain_mm'].sum():.0f} mm of rain in total.")
        return weather, source.startswith("Example")


def step_field() -> dict:
    with st.container(border=True):
        st.markdown("#### Step 2 · Field")
        slope = st.slider("Slope (%)", 0.0, 25.0, 2.0, 0.5)
        cn = st.select_slider("Runoff tendency (curve number)", options=sorted(CN_SETS), value=81,
                              help="73 = soil takes up water well, 84 = water runs off easily")
        st.caption("Curve number: how easily rain runs off. 73 = soil soaks it up, 84 = it runs off easily.")
        with st.expander("More soil settings"):
            oc = st.slider("Organic carbon in topsoil (%)", 0.2, 5.0, 1.0, 0.1)
            sand = st.slider("Sand in topsoil (%)", 10, 89, 39)
            clay = st.slider("Clay in topsoil (%)", 5, 60, 21)
            st.caption("The other soil properties stay at a typical field of the training runs.")
    return soil_settings(slope_pct=slope, h1_oc=oc, h1_sand=float(sand), h1_clay=float(clay), cn_2=float(cn))


def step_spraying(weather, example: bool):
    with st.container(border=True):
        st.markdown("#### Step 3 · Spraying")
        if weather is None:
            st.caption("Choose the weather first.")
            return None
        dose = st.number_input("Dose (kg/ha)", min_value=0.05, max_value=5.0, value=2.4, step=0.05)
        st.caption(f"{1000 * dose:,.0f} g of pesticide per hectare.")
        first_ok, last_ok = weather.index[min(30, len(weather) - 2)].date(), weather.index[-2].date()
        if example and pd.Timestamp(EXAMPLE_FIRST_DAY) in weather.index[:-1]:
            first_ok = pd.Timestamp(EXAMPLE_FIRST_DAY).date()     # days before and after the storm in March
        start = st.date_input("First candidate day", value=first_ok, min_value=weather.index[0].date(),
                              max_value=last_ok)
        n = st.slider("Number of candidate days", 1, 14, 10)
        horizon = st.slider("Days to add up after spraying", 3, 30, 14,
                            help="The loss is summed over this many days, starting on the spray day.")
    candidates = [d for d in pd.date_range(start, periods=n) if d in weather.index[:-1]]
    return {"dose": dose, "candidates": candidates, "horizon": horizon}


def loss_bar_chart(table: pd.DataFrame):
    """Predicted loss per candidate day as horizontal bars; the lowest day(s) highlighted."""
    c = colors()
    df = table.copy()
    df["day"] = df["spray_date"].map(lambda d: f"{pd.Timestamp(d):%a} {pd.Timestamp(d).day} {pd.Timestamp(d):%b}")
    df["kind"] = ["Not ranked" if pd.isna(r) else "Lowest" if r == 1 else "Other days" for r in df["rank"]]
    df["mark"] = df["kind"].map({"Lowest": "  lowest"}).fillna("")
    df["rank_text"] = ad.rank_labels(df["rank"])
    kinds = [k for k in ["Lowest", "Other days", "Not ranked"] if k in set(df["kind"])]
    shades = {"Lowest": c["cat"][1], "Other days": c["cat"][0], "Not ranked": c["muted"]}
    y = alt.Y("day:N", sort=list(df["day"]), title=None, axis=alt.Axis(labelLimit=200))
    bars = alt.Chart(df, height=max(140, 30 * len(df))).mark_bar(cornerRadiusEnd=4, height=18).encode(
        y=y, x=alt.X("predicted_loss_gha:Q", title="Predicted loss (g/ha)"),
        color=alt.Color("kind:N", title=None, scale=alt.Scale(domain=kinds, range=[shades[k] for k in kinds]),
                        legend=alt.Legend(orient="top", labelLimit=300)),
        tooltip=[alt.Tooltip("day:N", title="Spray day"), alt.Tooltip("rank_text:N", title="Rank"),
                 alt.Tooltip("predicted_loss_gha:Q", title="Predicted loss (g/ha)", format=".3f"),
                 alt.Tooltip("rain_in_window_mm:Q", title="Rain in window (mm)", format=".1f")])
    text = alt.Chart(df).mark_text(align="left", dx=4).encode(y=y, x="predicted_loss_gha:Q", text="mark:N")
    return bars + text


def day_by_day(weather, table, soil, models, dose, horizon, best_date):
    st.markdown("##### Day by day")
    options = list(table["spray_date"])
    pick = st.selectbox("Spray day to look at", options, index=options.index(best_date), format_func=ad.fmt_day)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        days = predict_days(weather, pd.Timestamp(pick), soil, models, rate_kgha=dose).iloc[:horizon]
    days = days.rename_axis("date").reset_index()
    days["day"] = days["date"].map(lambda d: f"{d.day} {d:%b}")
    c = colors()
    x = alt.X("day:N", sort=list(days["day"]), title=None, axis=alt.Axis(labelAngle=0, labelOverlap="greedy"))
    tips = [alt.Tooltip("date:T", title="Day", format="%a %d %b"), alt.Tooltip("rain_mm:Q", title="Rain (mm)"),
            alt.Tooltip("runoff_mm:Q", title="Runoff (mm)", format=".2f"),
            alt.Tooltip("loss_gha:Q", title="Loss (g/ha)", format=".3f")]
    for col, title, colour in [("rain_mm", "Rain (mm per day)", c["cat"][0]),
                               ("loss_gha", "Predicted pesticide loss (g/ha per day)", c["cat"][1])]:
        st.markdown(f"**{title}**")
        show(alt.Chart(days, height=150).mark_bar(color=colour, cornerRadiusEnd=3).encode(
            x=x, y=alt.Y(f"{col}:Q", title=None), tooltip=tips))
    st.caption(f"Over these {len(days)} days: {days['rain_mm'].sum():.0f} mm of rain, "
               f"{days['runoff_mm'].sum():.1f} mm of it runs off, carrying {ad.fmt_gha(days['loss_gha'].sum())}. "
               "Only rain days can lose pesticide.")


def show_result(weather, soil, plan, models):
    st.markdown("#### Result")
    if weather is None or plan is None:
        st.info("The result appears here once the weather is chosen.")
        return
    if not plan["candidates"]:
        st.warning("No candidate day lies inside the weather table.")
        return
    dose, horizon = plan["dose"], plan["horizon"]
    table = compare_spray_days(weather, plan["candidates"], horizon, soil, models, rate_kgha=dose)
    for note in table.attrs["notes"]:
        st.warning(note)
    ranked = table[table["rank"].notna()].sort_values("predicted_loss_gha")
    if ranked.empty:
        st.warning("No candidate day has a full window of weather after it. "
                   "Add fewer days after spraying, or add forecast days.")
        return
    st.markdown(ad.headline(ranked, horizon))
    best = ranked.iloc[0]
    st.caption(f"g/ha = grams of pesticide washed off one hectare with runoff water. You spray "
               f"{1000 * dose:,.0f} g/ha, so the lowest result is {ad.fmt_pct_small(best.loss_pct_of_dose)} of the dose.")
    show(loss_bar_chart(table))
    st.caption("Days with the same predicted loss share a rank (marked \"tie\"). Grey bars are not ranked: "
               "the weather table ends before their window does.")
    view = table.assign(spray_date=table["spray_date"].map(ad.fmt_day), rank=ad.rank_labels(table["rank"]),
                        loss_pct_of_dose=table["loss_pct_of_dose"].map(ad.fmt_pct_small),
                        worst_day=table["worst_day"].map(lambda d: ad.fmt_day(d) if d else "none"))
    st.dataframe(view, hide_index=True, column_order=[
        "rank", "spray_date", "predicted_loss_gha", "loss_pct_of_dose", "rain_in_window_mm", "high_loss_days",
        "worst_day", "worst_day_loss_gha", "days_covered"], column_config={
        "rank": "Rank (1 = best)",
        "spray_date": "Spray day",
        "predicted_loss_gha": st.column_config.NumberColumn("Predicted loss (g/ha)", format="%.3f"),
        "loss_pct_of_dose": "Loss (share of dose)",
        "rain_in_window_mm": st.column_config.NumberColumn("Rain (mm)", format="%.1f"),
        "high_loss_days": st.column_config.NumberColumn("Days with 1 g/ha or more"),
        "worst_day": "Worst day",
        "worst_day_loss_gha": st.column_config.NumberColumn("Loss on worst day (g/ha)", format="%.3f"),
        "days_covered": st.column_config.NumberColumn("Days covered")})
    day_by_day(weather, table, soil, models, dose, horizon, best.spray_date)
    st.info(ad.CAUTION)


def tab_advisor(models, error):
    st.caption("Pick the weather, the field and the spraying; the app predicts how much pesticide "
               "each candidate spray day would lose with runoff water.")
    if models is None:
        st.error(error)
        return
    left, right = st.columns([2, 3], gap="large")
    with left:
        weather, example = step_weather()
        soil = step_field()
        plan = step_spraying(weather, example)
    with right:
        show_result(weather, soil, plan, models)
    with st.expander("Limits: read before trusting a number"):
        st.markdown(
            "- The model learned from **PRZM simulations**, not from field measurements. It tells you what PRZM "
            "would say.\n"
            "- All simulations are for **one herbicide (Flufenacet) on winter cereals**. Other products and crops "
            "are **not covered**.\n" + ad.spray_limits(models["meta"]) +
            "  The app warns above the result when your spray day or dose is outside what the models have seen.\n"
            "- \"Loss\" is pesticide leaving the field edge with runoff water. What reaches a stream is not modelled.\n"
            "- The sliders change one soil property at a time. Real soils change several together; unusual "
            "combinations are not covered by the training runs.\n"
            "- On years it has not seen, the model can miss extreme storms.\n"
            "- A weather forecast is uncertain; so is everything computed from it.")


# --------------------------------------------------------------------------- #
# Tab 2: how good is the copy?
# --------------------------------------------------------------------------- #
def score_range(cv, by_year, key):
    lo_hi = ad.dig(cv, "range_over_years", key)
    if isinstance(lo_hi, list) and len(lo_hi) == 2 and all(ad.number(v) is not None for v in lo_hi):
        return lo_hi
    if by_year is not None and key in by_year.columns and by_year[key].notna().any():
        return [by_year[key].min(), by_year[key].max()]
    return None


def tab_quality():
    res = SET["results"]
    cv, by_year = jsn(res / "cv_summary.json"), csv(res / "cv_by_year.csv", required=("test_year",))
    st.caption("We trained the copy on some years and compared it with PRZM on years it never saw.")
    if cv is None:
        st.info(NOT_YET.format(what="`cv_summary.json`"))
    else:
        pooled = cv.get("pooled", {})
        cards = [
            ("runoff_r2", "Runoff R²", ad.fmt_r2(pooled.get("runoff_r2")), ad.fmt_r2,
             "How well daily runoff water matches PRZM. R²: 1 means perfect, 0 means no better than always "
             "guessing the average."),
            ("loss_r2", "Pesticide loss R²", ad.fmt_r2(pooled.get("loss_r2")), ad.fmt_r2,
             "The same score for the daily pesticide loss (g/ha)."),
            ("alarm_precision", "Alarms that are right",
             ad.fmt_pct(ad.dig(pooled, "alarm_at_1_gha", "precision"), 0, share=True),
             lambda v: ad.fmt_pct(v, 0, share=True),
             "When the copy warns of a high-loss day (1 g/ha or more), how often PRZM agrees (precision)."),
            ("alarm_recall", "High-loss days found",
             ad.fmt_pct(ad.dig(pooled, "alarm_at_1_gha", "recall"), 0, share=True),
             lambda v: ad.fmt_pct(v, 0, share=True),
             "Of PRZM's high-loss days, how many the copy warns of (recall)."),
        ]
        for col, (key, label, value, fmt, text) in zip(st.columns(4), cards):
            with col:
                st.metric(label, value, border=True)
                st.caption(text)
                r = score_range(cv, by_year, key)
                if r:
                    st.caption(f"Range over the held-out years: {fmt(r[0])} to {fmt(r[1])}.")
        years = [int(y) for y in cv.get("held_out_years", []) if ad.number(y) is not None]
        if years:
            st.markdown(
                f"**How the test works.** Each of the {len(years)} years {min(years)}-{max(years)} was held out once: "
                "the models learned from the other years, and the weather files of the test fields were never used "
                f"in training. The test covers {ad.number(cv.get('rows_scored')) or 0:,.0f} field-days with rain and "
                f"{ad.number(cv.get('high_loss_days')) or 0:,.0f} high-loss days.")

    score_cols = [k for k in SCORES if by_year is not None and k in by_year.columns]
    if score_cols:
        long = by_year.melt(id_vars="test_year", value_vars=score_cols, var_name="score", value_name="value")
        long["value"] = pd.to_numeric(long["value"], errors="coerce")
        long["score"] = long["score"].map(SCORES)
        names = [SCORES[k] for k in score_cols]
        long = long.dropna()
        low = ad.axis_floor(long["value"].min())
        st.markdown("##### Scores per held-out year")
        show(alt.Chart(long, height=300).mark_line(point=alt.OverlayMarkDef(size=50), strokeWidth=2)
             .encode(x=alt.X("test_year:O", title="Held-out year", axis=alt.Axis(labelAngle=0)),
                     y=alt.Y("value:Q", title="Score (1 = perfect)",
                             scale=alt.Scale(domain=[low, 1], nice=False, zero=False)),
                     color=alt.Color("score:N", title=None, sort=names,
                                     scale=alt.Scale(domain=names, range=colors()["cat"][:len(names)]),
                                     legend=alt.Legend(orient="top")),
                     tooltip=[alt.Tooltip("test_year:O", title="Year"), alt.Tooltip("score:N", title="Score"),
                              alt.Tooltip("value:Q", title="Value", format=".3f")]))
        if low > 0:
            st.caption(f"The vertical axis runs from {low:g} to 1, not from 0, so small differences between "
                       "years look larger than they are.")
    elif cv is not None:
        st.info(NOT_YET.format(what="`cv_by_year.csv`"))

    groups = [("by_spray_window", "By spray window", lambda k: k),
              ("by_dose_kgha", "By dose", lambda k: f"{k} kg/ha ({1000 * float(k):,.0f} g/ha)")]
    if cv is not None and any(isinstance(cv.get(k), dict) for k, *_ in groups):
        cols = st.columns(2)
        for col, (key, title, name) in zip(cols, groups):
            part = cv.get(key)
            if not isinstance(part, dict):
                continue
            rows = []
            for k, v in part.items():
                try:
                    label = name(k)
                except ValueError:
                    label = k
                rows.append({"Group": label, "Field-days": ad.fmt_int(ad.dig(v, "rows")),
                             "High-loss days": ad.fmt_int(ad.dig(v, "high_loss_days")),
                             "Loss R²": ad.fmt_r2(ad.dig(v, "loss_r2")),
                             "Alarms right": ad.fmt_pct(ad.dig(v, "alarm_precision"), 0, share=True),
                             "High-loss days found": ad.fmt_pct(ad.dig(v, "alarm_recall"), 0, share=True)})
            with col:
                st.markdown(f"##### {title}")
                st.dataframe(pd.DataFrame(rows), hide_index=True)

    st.markdown("##### Speed")
    secs = ad.number(ad.dig(jsn(res / "model_metrics.json"), "speed", "surrogate_seconds_per_10_year_run"))
    a, b, _ = st.columns([1, 1, 2])
    a.metric("The copy", f"{secs:.2f} s" if secs is not None else "n/a", border=True)
    a.caption("Seconds for one field over ten years of weather.")
    b.metric("PRZM", "about 3.4 s", border=True)
    b.caption(f"The same run in the simulator: the copy is about {3.4 / secs:,.0f} times faster." if secs
              else "The same run in the simulator.")

    figs = [(SET["figures"] / f, cap) for f, cap in [
        ("m2_loss_surrogate.png", "Predicted against simulated pesticide loss"),
        ("m3_high_loss_precision_recall.png", "Finding high-loss days: precision and recall")]]
    figs = [(p, cap) for p, cap in figs if p.is_file()]
    if figs:
        with st.expander("Figures from the model report"):
            for p, cap in figs:
                st.image(str(p), caption=cap)


# --------------------------------------------------------------------------- #
# Tab 3: spray date
# --------------------------------------------------------------------------- #
def tab_spray_date():
    res = SET["results"]
    st.caption("What the PRZM simulations themselves say about when the field was sprayed.")
    by_date = csv(res / "loss_by_spray_date.csv", required=("sprayed",), numeric=("mean_pct_of_dose_lost",))
    if by_date is None:
        st.info(NOT_YET.format(what="`loss_by_spray_date.csv`"))
    else:
        df = by_date[by_date["sprayed"] != "02 Feb 1-15"].sort_values("sprayed").copy()
        df["half"], df["season"] = df["sprayed"].map(ad.half_month), df["sprayed"].map(ad.season)
        seasons = list(dict.fromkeys(df["season"]))
        tips = [alt.Tooltip("half:N", title="Sprayed"),
                alt.Tooltip("mean_pct_of_dose_lost:Q", title="Mean % of dose lost", format=".3f")]
        tips += [alt.Tooltip(f"{c}:Q", title=t, format=f) for c, t, f in
                 [("seasons", "Simulated seasons", ","), ("mean_loss_gha", "Mean loss (g/ha)", ".2f")] if c in df]
        st.markdown("##### Share of the dose lost, by half-month of spraying")
        show(alt.Chart(df, height=280).mark_bar(cornerRadiusEnd=4).encode(
            x=alt.X("half:N", sort=list(df["half"]), title="Sprayed in", axis=alt.Axis(labelAngle=0)),
            y=alt.Y("mean_pct_of_dose_lost:Q", title="Mean share of the dose lost (%)"),
            color=alt.Color("season:N", title=None, scale=alt.Scale(domain=seasons, range=colors()["cat"][:len(seasons)]),
                            legend=alt.Legend(orient="top")),
            tooltip=tips))
        st.caption("Each bar: the mean over all simulated fields and years sprayed in that half-month, "
                   "over the whole season after spraying.")

    after = csv(res / "loss_after_spraying.csv", required=("sprayed", "days_after_spraying"),
                numeric=("rain_mm", "runoff_mm", "pct_of_dose_per_mm_runoff"))
    st.markdown("##### The first 30 days after spraying")
    if after is None:
        st.info(NOT_YET.format(what="`loss_after_spraying.csv`"))
        return
    first = after[(after["days_after_spraying"].astype(str) == "0-30") & (after["sprayed"] != "02 Feb 1-15")]
    first = first.sort_values("sprayed").assign(half=lambda d: d["sprayed"].map(ad.half_month))
    if first.empty:
        st.info(NOT_YET.format(what="the 0-30 day rows"))
        return
    first["season"] = first["sprayed"].map(ad.season)
    seasons = list(dict.fromkeys(first["season"]))
    colour = alt.Color("season:N", title=None, legend=None,
                       scale=alt.Scale(domain=seasons, range=colors()["cat"][:len(seasons)]))
    parts = [("rain_mm", "1. Rain in the first 30 days (mm)", ".0f"),
             ("runoff_mm", "2. Water that runs off in the first 30 days (mm)", ".1f"),
             ("pct_of_dose_per_mm_runoff", "3. Share of the dose lost per mm of runoff (%)", ".3f")]
    for k, title, fmt in parts:     # three measures with different units: three charts, one under the other
        st.markdown(f"**{title}**")
        show(alt.Chart(first, height=150).mark_bar(cornerRadiusEnd=3).encode(
            x=alt.X("half:N", sort=list(first["half"]), title=None, axis=alt.Axis(labelAngle=0, labelLimit=120)),
            y=alt.Y(f"{k}:Q", title=None, axis=alt.Axis(format=fmt, tickCount=4)), color=colour,
            tooltip=[alt.Tooltip("half:N", title="Sprayed"), alt.Tooltip(f"{k}:Q", title=title, format=fmt)]))
    st.caption("Blue: spring spraying, orange: autumn spraying (as in the chart above).")
    st.markdown(
        "- **One millimetre of runoff carries about the same share of the dose whenever you spray** (chart 3).\n"
        "- **What differs is how much water runs off in the first month** (chart 2).\n"
        "- That follows the crop calendar of the simulator: before the crop emerges on 12 Nov, the field counts "
        "as stubble and more of the rain runs off.\n"
        "- So the step in mid-November is a setting of the simulated scenario, not a law of nature.")


# --------------------------------------------------------------------------- #
# Tab 4: 45 years of French weather
# --------------------------------------------------------------------------- #
def yearly(folder: Path):
    return csv(folder / "france_by_year.csv", required=("app_year",), numeric=("app_year", "loss_gha_mean"))


def tab_france():
    res = SET["results"]
    st.caption("The copy run on the weather of 1979-2024 for every field of the study, all over France.")
    folders = ad.find_scenarios(res)
    if not folders:
        st.info(NOT_YET.format(what="`france_by_year.csv`"))
        return
    summaries = {f: jsn(f / "france_summary.json") for f in folders}
    labels = {ad.scenario_label(f, summaries[f], res): f for f in folders}
    choice = st.selectbox("Scenario", list(labels)) if len(labels) > 1 else next(iter(labels))
    folder, summary = labels[choice], summaries[labels[choice]]
    fields = ad.dig(summary, "fields")
    st.markdown(f"This run assumes every field is **{ad.spraying_text(ad.dig(summary, 'spraying'))}**, every year"
                + (f" ({int(fields):,} fields)." if ad.number(fields) else "."))

    c = colors()
    by_year = yearly(folder)
    if by_year is None:
        st.info(NOT_YET.format(what="`france_by_year.csv`"))
    else:
        st.markdown("##### Pesticide loss per field and year")
        layers = []
        years = alt.Scale(domain=[by_year["app_year"].min(), by_year["app_year"].max()], nice=False, zero=False)
        if {"loss_gha_p10", "loss_gha_p90"} <= set(by_year.columns):
            layers.append(alt.Chart(by_year).mark_area(opacity=0.2, color=c["cat"][0]).encode(
                x=alt.X("app_year:Q", scale=years), y="loss_gha_p10:Q", y2="loss_gha_p90:Q"))
        lines = [k for k in ("loss_gha_mean", "loss_gha_median") if k in by_year.columns]
        names = {"loss_gha_mean": "Mean over fields", "loss_gha_median": "Median field"}
        long = by_year.melt(id_vars="app_year", value_vars=lines, var_name="series", value_name="gha")
        long["series"] = long["series"].map(names)
        long["gha"] = pd.to_numeric(long["gha"], errors="coerce")
        layers.append(alt.Chart(long.dropna()).mark_line(strokeWidth=2, point=alt.OverlayMarkDef(size=30)).encode(
            x=alt.X("app_year:Q", title="Year of spraying", axis=alt.Axis(format="d"), scale=years),
            y=alt.Y("gha:Q", title="Loss in the year after spraying (g/ha)"),
            color=alt.Color("series:N", title=None, scale=alt.Scale(domain=list(names.values()), range=c["cat"][:2]),
                            legend=alt.Legend(orient="top")),
            tooltip=[alt.Tooltip("app_year:Q", title="Year", format="d"), alt.Tooltip("series:N", title=""),
                     alt.Tooltip("gha:Q", title="g/ha", format=".2f")]))
        show(alt.layer(*layers).properties(height=320))
        st.caption("Shaded band: 8 in 10 fields fall inside it (10th to 90th percentile). "
                   "The mean is above the median because a few fields lose a lot.")

    worst = ad.dig(summary, "worst_years_by_mean_loss")
    if isinstance(worst, dict) and worst:
        st.markdown("**Worst five years** (mean loss per field): "
                    + ", ".join(f"{y} ({ad.fmt_gha(v)})" for y, v in list(worst.items())[:5]) + ".")
    periods = ad.dig(summary, "by_period")
    if isinstance(periods, dict) and periods:
        periods = dict(sorted(periods.items(), key=lambda kv: ad.first_year(kv[0])))    # oldest period first
        for col, (name, p) in zip(st.columns(len(periods)), periods.items()):
            col.metric(name[:1].upper() + name[1:], ad.fmt_gha(ad.dig(p, "loss_gha_mean")), border=True)
            n, rain = ad.number(ad.dig(p, "years")), ad.number(ad.dig(p, "rain_mm_mean"))
            col.caption("Mean loss per field and year" + (f" over {n:.0f} years" if n else "")
                        + (f"; {rain:.0f} mm of rain a year." if rain else "."))
    elif summary is None:
        st.info(NOT_YET.format(what="`france_summary.json`"))

    grid = csv(folder / "france_by_grid.csv", numeric=("LONGITUDE", "LATITUDE", "loss_gha_per_year"))
    st.markdown("##### Where the loss is highest")
    if grid is None:
        st.info(NOT_YET.format(what="`france_by_grid.csv`"))
    else:
        tips = [alt.Tooltip("loss_gha_per_year:Q", title="Loss (g/ha per year)", format=".2f")]
        tips += [alt.Tooltip(f"{k}:Q", title=t, format=",.0f") for k, t in
                 [("fields", "Fields"), ("rain_mm_per_year", "Rain (mm per year)")] if k in grid.columns]
        show(alt.Chart(grid, height=520).mark_circle(size=40, opacity=0.9).encode(
            longitude="LONGITUDE:Q", latitude="LATITUDE:Q",
            color=alt.Color("loss_gha_per_year:Q", title="g/ha per year", scale=alt.Scale(range=c["seq"])),
            tooltip=tips).project(type="mercator"))
        st.caption("Each dot is a 25 km weather cell; the colour is the mean pesticide loss per field and year.")

    if len(folders) >= 2:
        with st.expander("Compare the scenarios", expanded=True):
            rows = []
            for name, f in labels.items():
                d = yearly(f)
                if d is not None:
                    rows.append(d[["app_year", "loss_gha_mean"]].assign(scenario=name))
            if len(rows) < 2:
                st.info(NOT_YET.format(what="a second `france_by_year.csv`"))
            else:
                both = pd.concat(rows)
                names = list(dict.fromkeys(both["scenario"]))
                span = alt.Scale(domain=[both["app_year"].min(), both["app_year"].max()], nice=False, zero=False)
                show(alt.Chart(both, height=300).mark_line(strokeWidth=2, point=alt.OverlayMarkDef(size=30)).encode(
                    x=alt.X("app_year:Q", title="Year of spraying", axis=alt.Axis(format="d"), scale=span),
                    y=alt.Y("loss_gha_mean:Q", title="Mean loss per field (g/ha)"),
                    color=alt.Color("scenario:N", title=None, scale=alt.Scale(domain=names, range=c["cat"][:len(names)]),
                                    legend=alt.Legend(orient="top", labelLimit=400, direction="vertical")),
                    tooltip=[alt.Tooltip("app_year:Q", title="Year", format="d"), "scenario:N",
                             alt.Tooltip("loss_gha_mean:Q", title="g/ha", format=".2f")]))
                st.dataframe(both.groupby("scenario", sort=False)["loss_gha_mean"].mean().map(ad.fmt_gha)
                             .rename("Mean over all years").rename_axis("Scenario").reset_index(), hide_index=True)


# --------------------------------------------------------------------------- #
# Tab 5: about and limits
# --------------------------------------------------------------------------- #
def tab_about(models):
    st.markdown("""
#### What this is
PRZM is a simulator that computes how much pesticide washes off a field with rain.
RunoffWatch is a machine-learning copy of it: it gives almost the same answers in a fraction of the time.
It learned from thousands of PRZM runs for real fields in France.
With it you can compare spray days in seconds, or run 45 years of weather for every field.

#### The four project tasks
| Task | What it does | Where in the app |
|---|---|---|
| 1. Data check | Find the simulations that are broken and keep only trusted ones | This tab (numbers below) |
| 2. Fast copy of PRZM | Predict daily runoff and pesticide loss | "How good is the copy?", "45 years of French weather" |
| 3. High-loss days | Warn of days that lose 1 g/ha or more | "How good is the copy?" (alarms) |
| 4. Spray-day advisor | Compare candidate spray days for one field | "Compare spray days" |

#### Limits
- One substance (Flufenacet) and one crop (winter cereals).
- A fixed crop calendar: the crop emerges on 12 Nov every year.
- Only the spray windows and doses the models have seen (below).
- Weak on the most extreme rain days (80 mm or more in a day).
- Some settings of the simulator are still to be confirmed by the model owner in Landau.
- The advisor was not tested as a decision tool with farmers or advisers.
- Everything copies a model; nothing here is a field measurement.
""")
    st.markdown("#### Loaded models")
    st.markdown(f"Model set: **{SET['name']}**, from `{SET['models']}`; results from `{SET['results']}`.")
    if models is None:
        st.info("The models are not loaded, so their training range is not shown.")
    else:
        on = ad.dig(models["meta"], "trained_on", default={}) or {}
        st.markdown(f"Trained on: {on.get('application', 'not stated')}.\n" + ad.spray_limits(models["meta"]))
    q = jsn(SET["results"] / "quality_summary.json")
    trusted, folders = ad.number(ad.dig(q, "trusted_runs")), ad.number(ad.dig(q, "folders"))
    if trusted and folders:
        st.markdown(f"Data check (task 1): {trusted:,.0f} of {folders:,.0f} simulated fields were trusted and used.")


# --------------------------------------------------------------------------- #
# Page
# --------------------------------------------------------------------------- #
def main():
    st.title("RunoffWatch")
    st.markdown("A fast machine-learning copy of the pesticide-runoff simulator PRZM: "
                "try spray days, see how good the copy is, and explore 45 years of French weather.")
    models, error = get_models()
    tabs = st.tabs(["Compare spray days", "How good is the copy?", "Spray date", "45 years of French weather",
                    "About and limits"])
    with tabs[0]:
        tab_advisor(models, error)
    with tabs[1]:
        tab_quality()
    with tabs[2]:
        tab_spray_date()
    with tabs[3]:
        tab_france()
    with tabs[4]:
        tab_about(models)


main()
