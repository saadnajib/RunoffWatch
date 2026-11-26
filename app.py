"""
RunoffWatch - interface to the whole project (Streamlit).

Start from the repository root with:

    streamlit run app.py

Five tabs, each answering one question: which spray day loses least (the advisor), is the copy of
PRZM right, spring or autumn spraying, 45 years of French weather, and about/limits. Each tab
starts with the answer; the detail is in fold-out boxes. A "high-loss day" is a day that loses at
least a chosen share of the dose (not a fixed amount in g/ha). The app reads the models in `models/`
and the result files in `docs/results/` (and `docs/figures/`) at run time; a missing or half-written
result file shows a short "not available yet" note. The simulation data itself is not needed. The
numbers come from a machine-learning copy (surrogate) of the PRZM model, not from field measurements.
"""

from __future__ import annotations

import warnings
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

from runoffwatch import appdata as ad
from runoffwatch.models import DEFAULT_SHARE_OF_DOSE_PCT, MODEL_FILES, SHARE_OF_DOSE_LIMITS_PCT
from runoffwatch.whatif import (CN_SETS, compare_spray_days, example_weather, load_models, predict_days,
                                prepare_weather, soil_settings)

st.set_page_config(page_title="RunoffWatch", layout="wide")
SET = ad.model_set()
EXAMPLE_FIRST_DAY = "2026-03-06"     # with the example weather: candidates before, during and after a storm
NOT_YET = "Not available yet: {what} is missing or being rewritten. Reload the page later."
TABS = ["Pick a spray day", "Is the copy right?", "Spring or autumn?", "45 years of weather", "About"]
LIMIT_KEYS = ("limit_advisor", "limit_quality")      # the same high-loss limit, shown in two tabs


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
                "seq": ["#0f4a96", "#cce3fd"], "line": "#e6e6e6"}
    return {"cat": ["#257de0", "#f47230", "#00b894", "#f2a600"], "muted": "#b4b4b4",
            "seq": ["#cce3fd", "#0e3d7e"], "line": "#333333"}


def show(chart):
    st.altair_chart(chart, width="stretch")


def intro(question: str, how: str, task: str):
    """Top of a tab: the question it answers, how to read it, and the project task it belongs to."""
    st.markdown(f"#### {question}")
    st.caption(f"{how} Project task: {task}.")


def _copy_limit(src: str, dst: str):
    st.session_state[dst] = st.session_state[src]


def limit_picker(key: str, label: str) -> float:
    """The high-loss limit as a share of the dose. Two tabs show it; changing one changes the other."""
    other = next(k for k in LIMIT_KEYS if k != key)
    if st.session_state.get(key) not in SHARE_OF_DOSE_LIMITS_PCT:
        start = st.session_state.get(other, DEFAULT_SHARE_OF_DOSE_PCT)
        st.session_state[key] = start if start in SHARE_OF_DOSE_LIMITS_PCT else DEFAULT_SHARE_OF_DOSE_PCT
    return st.select_slider(label, options=list(SHARE_OF_DOSE_LIMITS_PCT), key=key, format_func=ad.fmt_pct_small,
                            on_change=_copy_limit, args=(key, other))


# --------------------------------------------------------------------------- #
# Tab 1: pick a spray day
# --------------------------------------------------------------------------- #
def step_weather():
    with st.container(border=True):
        st.markdown("##### Step 1 · Weather")
        source = st.radio("Weather source", ["Example weather (made up)", "Upload my own CSV"],
                          horizontal=True, label_visibility="collapsed")
        raw = example_weather()
        if source.startswith("Upload"):
            st.download_button("Download a template CSV", ad.weather_template(prepare_weather(example_weather())),
                               file_name="weather_template.csv", mime="text/csv")
            st.caption("Columns: `date, rain_mm, temp_c`, optional `pan_evap_mm`. One row per day: "
                       "about 30 days before the first spray day, then the forecast.")
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
        show(alt.Chart(rain, height=120).mark_bar(color=colors()["cat"][0], cornerRadiusEnd=2).encode(
            x=alt.X("date:T", title=None), y=alt.Y("rain_mm:Q", title="Rain (mm/day)"),
            tooltip=[alt.Tooltip("date:T", title="Day"), alt.Tooltip("rain_mm:Q", title="Rain (mm)")]))
        st.caption(f"{len(weather)} days, {ad.fmt_day(weather.index[0])} to {ad.fmt_day(weather.index[-1])}; "
                   f"{weather['rain_mm'].sum():.0f} mm of rain in total.")
        return weather, source.startswith("Example")


def step_field() -> dict:
    with st.container(border=True):
        st.markdown("##### Step 2 · Field")
        slope = st.slider("Slope (%)", 0.0, 25.0, 2.0, 0.5)
        numbers = sorted(CN_SETS)
        ends = {numbers[0]: f"{numbers[0]} · soil soaks rain up", numbers[-1]: f"{numbers[-1]} · rain runs off"}
        cn = st.select_slider("How easily rain runs off (curve number)", options=numbers, value=81,
                              format_func=lambda v: ends.get(v, str(v)))
        with st.expander("More soil settings"):
            oc = st.slider("Organic carbon in topsoil (%)", 0.2, 5.0, 1.0, 0.1)
            sand = st.slider("Sand in topsoil (%)", 10, 89, 39)
            clay = st.slider("Clay in topsoil (%)", 5, 60, 21)
            st.caption("The other soil properties stay at a typical field of the training runs.")
    return soil_settings(slope_pct=slope, h1_oc=oc, h1_sand=float(sand), h1_clay=float(clay), cn_2=float(cn))


def step_spraying(weather, example: bool):
    with st.container(border=True):
        st.markdown("##### Step 3 · Spraying")
        if weather is None:
            st.caption("Choose the weather first.")
            return None
        dose = st.number_input("Dose (kg/ha)", min_value=0.05, max_value=5.0, value=2.4, step=0.05)
        first_ok, last_ok = weather.index[min(30, len(weather) - 2)].date(), weather.index[-2].date()
        if example and pd.Timestamp(EXAMPLE_FIRST_DAY) in weather.index[:-1]:
            first_ok = pd.Timestamp(EXAMPLE_FIRST_DAY).date()     # days before and after the storm in March
        start = st.date_input("First day you could spray", value=first_ok, min_value=weather.index[0].date(),
                              max_value=last_ok)
        limit = limit_picker(LIMIT_KEYS[0], "Flag a day that loses at least this share of the dose")
        st.caption(f"You spray {1000 * dose:,.0f} g/ha, so a day is flagged from "
                   f"{ad.fmt_gha(ad.limit_gha(limit, dose))} lost in one day.")
        with st.expander("More options"):
            n = st.slider("Number of candidate days", 1, 14, 10)
            horizon = st.slider("Days to add up after spraying", 3, 30, 14,
                                help="The loss is summed over this many days, starting on the spray day.")
    candidates = [d for d in pd.date_range(start, periods=n) if d in weather.index[:-1]]
    return {"dose": dose, "candidates": candidates, "horizon": horizon, "limit": limit}


def loss_bar_chart(table: pd.DataFrame):
    """Predicted loss per candidate day as horizontal bars; the lowest day(s) and flagged days are labelled."""
    c = colors()
    df = table.copy()
    df["day"] = df["spray_date"].map(lambda d: f"{pd.Timestamp(d):%a} {pd.Timestamp(d).day} {pd.Timestamp(d):%b}")
    df["kind"] = ["Not ranked" if pd.isna(r) else "Lowest loss" if r == 1 else "Other days" for r in df["rank"]]
    flags = df["high_loss_days"].map(ad.flag_text)
    df["mark"] = ["  " + ", ".join(t for t in (("lowest" if k == "Lowest loss" else ""), f) if t)
                  for k, f in zip(df["kind"], flags)]
    df["rank_text"] = ad.rank_labels(df["rank"])
    kinds = [k for k in ["Lowest loss", "Other days", "Not ranked"] if k in set(df["kind"])]
    shades = {"Lowest loss": c["cat"][1], "Other days": c["cat"][0], "Not ranked": c["muted"]}
    y = alt.Y("day:N", sort=list(df["day"]), title="Spray day", axis=alt.Axis(labelLimit=200))
    top = float(df["predicted_loss_gha"].max())
    room = alt.Scale(domain=[0, 1.3 * top]) if top > 0 else alt.Scale()       # room for the labels at the bar ends
    bars = alt.Chart(df).mark_bar(cornerRadiusEnd=4, height=18).encode(
        y=y, x=alt.X("predicted_loss_gha:Q", title="Predicted loss (g/ha)", scale=room),
        color=alt.Color("kind:N", title=None, scale=alt.Scale(domain=kinds, range=[shades[k] for k in kinds]),
                        legend=alt.Legend(orient="top", labelLimit=300)),
        tooltip=[alt.Tooltip("day:N", title="Spray day"), alt.Tooltip("rank_text:N", title="Rank"),
                 alt.Tooltip("predicted_loss_gha:Q", title="Predicted loss (g/ha)", format=".3f"),
                 alt.Tooltip("rain_in_window_mm:Q", title="Rain in window (mm)", format=".1f"),
                 alt.Tooltip("high_loss_days:Q", title="Days above the limit")])
    text = alt.Chart(df).mark_text(align="left", dx=4, limit=220, color=c["line"]).encode(   # readable in both themes
        y=y, x="predicted_loss_gha:Q", text="mark:N")
    # Streamlit fits legend and axis inside the height, so they are added to 30 px per bar
    return (bars + text).properties(height=120 + 30 * len(df))


def day_by_day(weather, table, soil, models, plan, best_date):
    dose, horizon, limit = plan["dose"], plan["horizon"], plan["limit"]
    st.markdown("##### What happens after one spray day")
    options = list(table["spray_date"])
    pick = st.selectbox("Spray day to look at", options, index=options.index(best_date), format_func=ad.fmt_day)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        days = predict_days(weather, pd.Timestamp(pick), soil, models, rate_kgha=dose,
                            high_loss_pct_of_dose=limit).iloc[:horizon]
    days = days.rename_axis("date").reset_index()
    days["day"] = days["date"].map(lambda d: f"{d.day} {d:%b}")
    c = colors()
    limit_gha = ad.limit_gha(limit, dose)
    x = alt.X("day:N", sort=list(days["day"]), title=None, axis=alt.Axis(labelAngle=0, labelOverlap="greedy"))
    tips = [alt.Tooltip("date:T", title="Day", format="%a %d %b"), alt.Tooltip("rain_mm:Q", title="Rain (mm)"),
            alt.Tooltip("runoff_mm:Q", title="Runoff (mm)", format=".2f"),
            alt.Tooltip("loss_gha:Q", title="Loss (g/ha)", format=".3f")]
    st.markdown("**Rain (mm per day)**")
    show(alt.Chart(days, height=140).mark_bar(color=c["cat"][0], cornerRadiusEnd=3).encode(
        x=x, y=alt.Y("rain_mm:Q", title=None), tooltip=tips))
    st.markdown("**Predicted pesticide loss (g/ha per day)**")
    loss = alt.Chart(days, height=140).mark_bar(color=c["cat"][1], cornerRadiusEnd=3).encode(
        x=x, y=alt.Y("loss_gha:Q", title=None), tooltip=tips)
    near = days["loss_gha"].max() >= 0.25 * limit_gha        # else the line would squash the bars
    if near:
        rule = pd.DataFrame({"limit": [limit_gha], "label": [f"limit: {ad.fmt_gha(limit_gha)}"]})
        line = alt.Chart(rule).mark_rule(strokeDash=[6, 4], strokeWidth=1.5, color=c["line"]).encode(y="limit:Q")
        label = alt.Chart(rule).mark_text(align="right", dx=-4, dy=-7, color=c["line"]).encode(
            y="limit:Q", x=alt.value("width"), text="label:N")
        loss = loss + line + label
    show(loss)
    flagged = int(days["high_loss_day"].sum())
    st.caption(f"Over these {len(days)} days: {days['rain_mm'].sum():.0f} mm of rain, "
               f"{days['runoff_mm'].sum():.1f} mm of it runs off, carrying {ad.fmt_gha(days['loss_gha'].sum())}. "
               + (f"{flagged} day{'s' if flagged != 1 else ''} reach{'es' if flagged == 1 else ''} the limit "
                  f"of {ad.limit_text(limit, dose)}." if near else
                  f"No day comes near the limit of {ad.limit_text(limit, dose)}.")
               + " Only rain days can lose pesticide.")


def show_result(weather, soil, plan, models):
    st.markdown("##### Result")
    if weather is None or plan is None:
        st.info("The result appears here once the weather is chosen.")
        return
    if not plan["candidates"]:
        st.warning("No candidate day lies inside the weather table.")
        return
    dose, horizon, limit = plan["dose"], plan["horizon"], plan["limit"]
    table = compare_spray_days(weather, plan["candidates"], horizon, soil, models, rate_kgha=dose,
                               high_loss_pct_of_dose=limit)
    for note in table.attrs["notes"]:
        st.warning(note)
    ranked = table[table["rank"].notna()].sort_values("predicted_loss_gha")
    if ranked.empty:
        st.warning("No candidate day has a full window of weather after it. "
                   "Add fewer days after spraying, or add forecast days.")
        return
    st.success(ad.headline(ranked, horizon))
    best = ranked.iloc[0]
    st.caption(f"g/ha = grams of pesticide washed off one hectare with runoff water. You spray "
               f"{1000 * dose:,.0f} g/ha, so the lowest result is {ad.fmt_pct_small(best.loss_pct_of_dose)} of the dose.")
    show(loss_bar_chart(table))
    st.caption("A shorter bar is better. \"Days above the limit\": days that lose at least "
               f"{ad.limit_text(limit, dose)} in one day. Days with the same loss share a rank. "
               "Grey bars are not ranked: the weather table ends before their window does.")
    day_by_day(weather, table, soil, models, plan, best.spray_date)
    with st.expander("All numbers as a table"):
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
            "high_loss_days": st.column_config.NumberColumn("Days above the limit"),
            "worst_day": "Worst day",
            "worst_day_loss_gha": st.column_config.NumberColumn("Loss on worst day (g/ha)", format="%.3f"),
            "days_covered": st.column_config.NumberColumn("Days covered")})
    st.info(ad.CAUTION)


def tab_advisor(models, error):
    intro("Which spray day loses the least pesticide?",
          "Go through the three steps on the left. The answer appears on the right and changes as you move a control.",
          "4, the spray-day advisor")
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
            "- The limit for a flagged day is a share of the dose that you choose. Which share is serious depends "
            "on the compound; no value here is an official limit.\n"
            "- \"Loss\" is pesticide leaving the field edge with runoff water. What reaches a stream is not modelled.\n"
            "- The sliders change one soil property at a time. Real soils change several together; unusual "
            "combinations are not covered by the training runs.\n"
            "- On years it has not seen, the model can miss extreme storms.\n"
            "- A weather forecast is uncertain; so is everything computed from it.")


# --------------------------------------------------------------------------- #
# Tab 2: is the copy right?
# --------------------------------------------------------------------------- #
def year_range(values, fmt) -> str | None:
    """'Range over the test years: a to b.' from a list of numbers (None entries are skipped)."""
    v = [ad.number(x) for x in values]
    v = [x for x in v if x is not None]
    return f"Range over the test years: {fmt(min(v))} to {fmt(max(v))}." if v else None


def card(col, label, value, text, extra=None):
    with col:
        st.metric(label, value, border=True)
        st.caption(text + (f" {extra}" if extra else ""))


def tab_quality():
    res = SET["results"]
    cv, by_year = jsn(res / "cv_summary.json"), csv(res / "cv_by_year.csv", required=("test_year",))
    intro("How close is the copy to PRZM?",
          "We hid one year at a time from the copy, then compared its answers with PRZM's for that year.",
          "3, the fast copy, and 2, high-loss days")
    share = lambda v: ad.fmt_pct(v, 0, share=True)  # noqa: E731
    col_range = lambda key, fmt: (year_range(by_year[key], fmt)  # noqa: E731
                                  if by_year is not None and key in by_year.columns else None)
    limit, alarm = None, None
    if cv is None:
        st.info(NOT_YET.format(what="`cv_summary.json`"))
    else:
        pooled = cv.get("pooled", {})
        st.markdown("##### 1. Does it get the amounts right?")
        a, b, c = st.columns(3)
        card(a, "Runoff water", ad.fmt_r2(pooled.get("runoff_r2")),
             "Score from 0 to 1 (R²). 1 = the same as PRZM on every day.", col_range("runoff_r2", ad.fmt_r2))
        card(b, "Pesticide loss", ad.fmt_r2(pooled.get("loss_r2")),
             "The same score for the daily pesticide loss.", col_range("loss_r2", ad.fmt_r2))
        card(c, "Total loss found", share(pooled.get("loss_total_pred_over_true")),
             "All test days added up: the copy's total as a share of PRZM's total.",
             col_range("loss_total_pred_over_true", share))

        st.markdown("##### 2. Does it warn on the right days?")
        pick, note = st.columns([1, 2], gap="large")
        with pick:
            limit = limit_picker(LIMIT_KEYS[1], "A high-loss day loses at least this share of the dose")
        alarm = ad.alarm_scores(cv, limit)
        note.caption(f"That is {ad.fmt_gha(ad.limit_gha(limit, 2.4))} in one day at a dose of 2.4 kg/ha, and "
                     f"{ad.fmt_gha(ad.limit_gha(limit, 0.24))} at 0.24 kg/ha. The limit follows the dose because "
                     "the same amount in g/ha is harmless for one compound and serious for another. "
                     "Which share is serious depends on the compound; no value here is an official limit.")
        if alarm is None:
            st.info(NOT_YET.format(what="the alarm table by share of the dose in `cv_summary.json`"))
        else:
            per_year = list((alarm.get("by_year") or {}).values())
            a, b, c = st.columns(3)
            card(a, "Alarms that are right", share(alarm.get("precision")),
                 "When the copy warns of a high-loss day, how often PRZM agrees.",
                 year_range([ad.dig(y, "precision") for y in per_year], share))
            card(b, "High-loss days found", share(alarm.get("recall")),
                 "Of PRZM's high-loss days, how many the copy warns of.",
                 year_range([ad.dig(y, "recall") for y in per_year], share))
            card(c, "High-loss days in the test", ad.fmt_int(alarm.get("high_loss_days")),
                 f"Days on which PRZM lost at least {ad.fmt_pct_small(limit)} of the dose; "
                 f"the copy raised {ad.fmt_int(alarm.get('alarms'))} alarms.")

    st.markdown("##### 3. How fast is it?")
    secs = ad.number(ad.dig(jsn(res / "model_metrics.json"), "speed", "surrogate_seconds_per_10_year_run"))
    a, b, c = st.columns(3)
    card(a, "The copy", f"{secs:.2f} s" if secs is not None else "n/a", "One field over ten years of weather.")
    card(b, "PRZM", "about 3.4 s", "The same run in the simulator.")
    if secs:
        card(c, "Speed-up", f"about {3.4 / secs:,.0f} times", "PRZM's time divided by the copy's time.")

    # --- detail, folded away ---
    series = {"runoff_r2": "Runoff water (R²)", "loss_r2": "Pesticide loss (R²)"}
    parts = []
    if by_year is not None:
        for key, name in series.items():
            if key in by_year.columns:
                parts.append(pd.DataFrame({"year": by_year["test_year"].astype(str), "score": name,
                                           "value": pd.to_numeric(by_year[key], errors="coerce")}))
    for key, name in [("precision", "Alarms that are right"), ("recall", "High-loss days found")]:
        years = ad.dig(alarm, "by_year") or {}
        if years:
            parts.append(pd.DataFrame({"year": [str(y) for y in years], "score": name,
                                       "value": [ad.number(ad.dig(v, key)) for v in years.values()]}))
    with st.expander("Year by year"):
        long = pd.concat(parts).dropna() if parts else pd.DataFrame()
        if long.empty:
            st.info(NOT_YET.format(what="`cv_by_year.csv`"))
        else:
            names = list(dict.fromkeys(long["score"]))
            low = ad.axis_floor(long["value"].min())
            show(alt.Chart(long, height=300).mark_line(point=alt.OverlayMarkDef(size=50), strokeWidth=2)
                 .encode(x=alt.X("year:O", title="Year that was hidden from the copy", axis=alt.Axis(labelAngle=0)),
                         y=alt.Y("value:Q", title="Score (1 = perfect)",
                                 scale=alt.Scale(domain=[low, 1], nice=False, zero=False)),
                         color=alt.Color("score:N", title=None, sort=names,
                                         scale=alt.Scale(domain=names, range=colors()["cat"][:len(names)]),
                                         legend=alt.Legend(orient="top", labelLimit=300)),
                         tooltip=[alt.Tooltip("year:O", title="Year"), alt.Tooltip("score:N", title="Score"),
                                  alt.Tooltip("value:Q", title="Value", format=".3f")]))
            st.caption("A year holds only a handful of storms, so the scores differ between years."
                       + (f" The vertical axis runs from {low:g} to 1, not from 0, so small differences "
                          "look larger than they are." if low > 0 else ""))

    groups = [("by_spray_window", "By spray season", lambda k: k[:1].upper() + k[1:]),
              ("by_dose_kgha", "By dose", lambda k: f"{k} kg/ha ({1000 * float(k):,.0f} g/ha)")]
    if cv is not None and any(isinstance(cv.get(k), dict) for k, *_ in groups):
        with st.expander("By dose and by spray season"):
            for col, (key, title, name) in zip(st.columns(2), groups):
                part = cv.get(key)
                if not isinstance(part, dict):
                    continue
                rows = []
                for k, v in part.items():
                    try:
                        label = name(k)
                    except ValueError:
                        label = k
                    hit = ad.dig(alarm, key, k)
                    rows.append({"Group": label, "Rain days": ad.fmt_int(ad.dig(v, "rows")),
                                 "Pesticide loss (R²)": ad.fmt_r2(ad.dig(v, "loss_r2")),
                                 "High-loss days": ad.fmt_int(ad.dig(hit, "high_loss_days")),
                                 "Alarms right": share(ad.dig(hit, "precision")),
                                 "High-loss days found": share(ad.dig(hit, "recall"))})
                with col:
                    st.markdown(f"**{title}**")
                    st.dataframe(pd.DataFrame(rows), hide_index=True)
            if limit is not None:
                st.caption(f"High-loss days and alarms use the limit chosen above ({ad.fmt_pct_small(limit)} of the dose).")

    with st.expander("How the test works"):
        years = [int(y) for y in ad.dig(cv, "held_out_years", default=[]) if ad.number(y) is not None]
        if years:
            st.markdown(
                f"Each of the {len(years)} years {min(years)}-{max(years)} was hidden once. The models learned "
                "from the other years. The weather files of the test fields were never used in training. "
                f"The test covers {ad.number(ad.dig(cv, 'rows_scored')) or 0:,.0f} rain days of single fields.")
        else:
            st.info(NOT_YET.format(what="`cv_summary.json`"))
        fig = SET["figures"] / "m2_loss_surrogate.png"
        if fig.is_file():
            st.image(str(fig), caption="Predicted against simulated pesticide loss (figure from the model report)")


# --------------------------------------------------------------------------- #
# Tab 3: spring or autumn?
# --------------------------------------------------------------------------- #
def tab_spray_date():
    res = SET["results"]
    intro("Does it matter when in the year you spray?",
          "These are PRZM's own results for all simulated fields and years, not predictions of the copy.",
          "2, explaining high losses")
    by_date = csv(res / "loss_by_spray_date.csv", required=("sprayed",), numeric=("mean_pct_of_dose_lost",))
    if by_date is None:
        st.info(NOT_YET.format(what="`loss_by_spray_date.csv`"))
    else:
        df = by_date[by_date["sprayed"] != "02 Feb 1-15"].sort_values("sprayed").copy()
        df["half"], df["season"] = df["sprayed"].map(ad.half_month), df["sprayed"].map(ad.season)
        seasons = list(dict.fromkeys(df["season"]))
        means = ad.season_means(df)
        spring, autumn = means.get("Spring (Feb-Apr)"), means.get("Autumn (Oct-Nov)")
        if spring and autumn and spring["mean"] > 0:
            pct = lambda v: f"{v:.2f}%"  # noqa: E731
            between = lambda m: f"Between {pct(m['low'])} and {pct(m['high'])}, depending on the half-month."  # noqa: E731
            a, b, c = st.columns(3)
            card(a, "Sprayed in spring", pct(spring["mean"]) + " of the dose",
                 "Mean share of the dose lost in the season after spraying.", between(spring))
            card(b, "Sprayed in autumn", pct(autumn["mean"]) + " of the dose",
                 "Mean share of the dose lost in the season after spraying.", between(autumn))
            card(c, "Autumn compared with spring", f"about {autumn['mean'] / spring['mean']:.0f} times more",
                 "Mean share lost after autumn spraying divided by the mean after spring spraying.")
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
        st.caption("A higher bar means more pesticide washed off. Each bar: the mean over all simulated fields "
                   "and years sprayed in that half-month.")
    st.markdown("**Why?** In the simulator the crop emerges on 12 November. Before that the field counts as "
                "stubble and more of the rain runs off. So the step in mid-November is a setting of the simulated "
                "scenario, not a law of nature.")

    after = csv(res / "loss_after_spraying.csv", required=("sprayed", "days_after_spraying"),
                numeric=("rain_mm", "runoff_mm", "pct_of_dose_per_mm_runoff"))
    with st.expander("The evidence: the first 30 days after spraying"):
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
            "- **What differs is how much water runs off in the first month** (chart 2).")


# --------------------------------------------------------------------------- #
# Tab 4: 45 years of weather
# --------------------------------------------------------------------------- #
def yearly(folder: Path):
    return csv(folder / "france_by_year.csv", required=("app_year",), numeric=("app_year", "loss_gha_mean"))


def tab_france():
    res = SET["results"]
    intro("What would 45 years of real weather have done?",
          "The copy was run on the weather of 1979-2024 for every field of the study, all over France. "
          "PRZM would need hours for this.", "3, the fast copy put to use")
    folders = ad.find_scenarios(res)
    if not folders:
        st.info(NOT_YET.format(what="`france_by_year.csv`"))
        return
    summaries = {f: jsn(f / "france_summary.json") for f in folders}
    labels = {ad.scenario_short(summaries[f], f): f for f in folders}
    if len(labels) < len(folders):                     # two scenarios with the same spray day: use the long names
        labels = {ad.scenario_label(f, summaries[f], res): f for f in folders}
    choice = st.radio("Scenario", list(labels), horizontal=True) if len(labels) > 1 else next(iter(labels))
    folder, summary = labels[choice], summaries[labels[choice]]
    fields = ad.dig(summary, "fields")
    st.markdown(f"This run assumes every field is **{ad.spraying_text(ad.dig(summary, 'spraying'))}**, every year"
                + (f" ({int(fields):,} fields)." if ad.number(fields) else "."))

    periods = ad.dig(summary, "by_period")
    if isinstance(periods, dict) and periods:
        periods = dict(sorted(periods.items(), key=lambda kv: ad.first_year(kv[0])))    # oldest period first
        for col, (name, p) in zip(st.columns(len(periods)), periods.items()):
            n, rain = ad.number(ad.dig(p, "years")), ad.number(ad.dig(p, "rain_mm_mean"))
            card(col, name[:1].upper() + name[1:], ad.fmt_gha(ad.dig(p, "loss_gha_mean")),
                 "Mean loss per field and year" + (f" over {n:.0f} years" if n else "")
                 + (f"; {rain:.0f} mm of rain a year." if rain else "."))
    elif summary is None:
        st.info(NOT_YET.format(what="`france_summary.json`"))
    worst = ad.dig(summary, "worst_years_by_mean_loss")
    if isinstance(worst, dict) and worst:
        st.markdown("**Worst five years** (mean loss per field): "
                    + ", ".join(f"{y} ({ad.fmt_gha(v)})" for y, v in list(worst.items())[:5]) + ".")

    c = colors()
    by_year = yearly(folder)
    if by_year is None:
        st.info(NOT_YET.format(what="`france_by_year.csv`"))
    else:
        st.markdown("##### Pesticide loss per field, year by year")
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
        st.caption("A peak is a year with heavy rain soon after spraying. Shaded band: 8 in 10 fields fall inside "
                   "it. The mean is above the median because a few fields lose a lot.")

    if len(folders) >= 2:
        st.markdown("##### The scenarios side by side")
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
            show(alt.Chart(both, height=280).mark_line(strokeWidth=2, point=alt.OverlayMarkDef(size=30)).encode(
                x=alt.X("app_year:Q", title="Year of spraying", axis=alt.Axis(format="d"), scale=span),
                y=alt.Y("loss_gha_mean:Q", title="Mean loss per field (g/ha)"),
                color=alt.Color("scenario:N", title=None, scale=alt.Scale(domain=names, range=c["cat"][:len(names)]),
                                legend=alt.Legend(orient="top", labelLimit=400)),
                tooltip=[alt.Tooltip("app_year:Q", title="Year", format="d"), "scenario:N",
                         alt.Tooltip("loss_gha_mean:Q", title="g/ha", format=".2f")]))
            mean = both.groupby("scenario", sort=False)["loss_gha_mean"].mean()
            st.caption("Mean over all years: " + "; ".join(f"{k}: {ad.fmt_gha(v)}" for k, v in mean.items()) + ".")

    grid = csv(folder / "france_by_grid.csv", numeric=("LONGITUDE", "LATITUDE", "loss_gha_per_year"))
    with st.expander("Map: where the loss is highest"):
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
            st.caption("Each dot is a 25 km weather cell; a darker dot means more pesticide lost per field and year "
                       f"({choice}).")


# --------------------------------------------------------------------------- #
# Tab 5: about
# --------------------------------------------------------------------------- #
def tab_about(models):
    st.markdown(f"""
#### What this is
PRZM is a simulator that computes how much pesticide washes off a field with rain.
RunoffWatch is a machine-learning copy of it: it gives almost the same answers in a fraction of the time.
It learned from thousands of PRZM runs for real fields in France.

#### How to use this app
| Tab | The question it answers | What you do |
|---|---|---|
| {TABS[0]} | Which spray day loses the least pesticide? | Set weather, field and dose; read the green box and the bars |
| {TABS[1]} | How close is the copy to PRZM? | Read the cards; move the high-loss limit |
| {TABS[2]} | Does it matter when in the year you spray? | Read the cards and the bar chart |
| {TABS[3]} | What would 45 years of real weather have done? | Choose the spray day of the scenario |

Only the first tab computes something new. The other tabs show results that were computed before.

#### The four project tasks
| Task | What it does | Where in the app |
|---|---|---|
| 1. Data check | Find the simulations that are broken and keep only trusted ones | This tab (numbers below) |
| 2. High-loss days | Warn of days that lose a large share of the dose, and explain them | "{TABS[1]}" (alarms), "{TABS[2]}" |
| 3. Fast copy of PRZM | Predict daily runoff and pesticide loss | "{TABS[1]}", "{TABS[3]}" |
| 4. Spray-day advisor | Compare candidate spray days for one field | "{TABS[0]}" |

#### What is a high-loss day?
A day on which the field loses at least a chosen share of the dose, {ad.fmt_pct_small(DEFAULT_SHARE_OF_DOSE_PCT)} to start with.
The limit follows the dose because doses differ a lot between compounds: one gram per hectare is nothing for a
herbicide sprayed at kilograms per hectare, and serious for an insecticide sprayed at a few grams.
Which share is serious depends on the compound. No value in this app is an official limit.

#### Limits
- One substance (Flufenacet) and one crop (winter cereals).
- A fixed crop calendar: the crop emerges on 12 Nov every year.
- Only the spray windows and doses the models have seen (below). Compounds sprayed at a few grams per hectare
  are outside that range.
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
    st.markdown("A fast machine-learning copy of the pesticide-runoff simulator PRZM. "
                "Each tab answers one question; start with the first.")
    models, error = get_models()
    tabs = st.tabs(TABS)
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
