"""
RunoffWatch - spray-day advisor (prototype).

Start with:   streamlit run app.py

Upload a daily weather table (past weeks + forecast) or use the example, pick
candidate spray days and a soil, and compare the predicted pesticide loss.
The numbers come from a machine-learning surrogate of the PRZM model, not from
field measurements. See the "Limits" box in the app.
"""

import warnings
from pathlib import Path

import pandas as pd
import streamlit as st

from runoffwatch.whatif import (CN_SETS, compare_spray_days, example_weather, load_models, predict_days,
                                prepare_weather, soil_settings)

st.set_page_config(page_title="RunoffWatch spray-day advisor", layout="wide")
st.title("RunoffWatch: spray-day advisor")
st.caption("Prototype. Predicts how much pesticide would be washed off the field after spraying, "
           "using a machine-learning surrogate of the PRZM model.")


@st.cache_resource
def _models():
    # models trained on runs with varied spray dates and doses, if they are there
    return load_models("models/varied" if Path("models/varied/meta.json").exists() else "models")


def _spray_windows(days) -> str:
    """Spray days of the year as date ranges, e.g. '15 Feb-30 Apr and 1 Oct-30 Nov'.

    The same date is one day later in a leap year (after February), so a range starts with the
    date of a common year and ends with the date of a leap year.
    """
    days = sorted(int(d) for d in days)
    groups, start = [], days[0]
    for a, b in zip(days, days[1:] + [None]):
        if b is None or b - a > 3:
            groups.append((start, a)); start = b
    def text(d, year):
        t = pd.Timestamp(year=year, month=1, day=1) + pd.Timedelta(days=d - 1)
        return f"{t.day} {t:%b}"

    parts = [text(a, 2001) if text(a, 2001) == text(b, 2000) else f"{text(a, 2001)}-{text(b, 2000)}"
             for a, b in groups]
    return " and ".join(parts)


def _spray_limits(meta: dict) -> str:
    """The 'Limits' lines about spray date and dose, true for the models that were loaded."""
    on = meta["trained_on"]
    days = on.get("spray_days_seen") or [60, 61]
    doses = [1000 * float(d) for d in on.get("doses_kgha") or [2.4]]
    if len(days) <= 2 and len(doses) == 1:           # models that only know the delivered runs
        return (f"- These models only know **spraying on {_spray_windows(days)} with {doses[0]:.0f} g/ha**. "
                "Another dose is scaled in proportion, and another spray day is a guess.\n"
                "- In those runs \"days since spraying\" and the calendar date move together, so the model "
                "cannot tell them apart. Moving the spray day is new to it.\n")
    return (f"- These models learned from runs sprayed **{_spray_windows(days)}**, with doses of "
            f"**{min(doses):.0f} to {max(doses):.0f} g/ha**. A spray day or dose outside these is a guess.\n")


try:
    models = _models()
except FileNotFoundError as e:
    st.error(f"{e}")
    st.stop()

with st.sidebar:
    st.header("Weather")
    up = st.file_uploader("Daily weather CSV (date, rain_mm, temp_c, optional pan_evap_mm)", type="csv")
    st.caption("Include about 30 days before the first spray day and the forecast after it. "
               "Without a file, a made-up example is used.")
    st.header("Field")
    slope = st.slider("Slope (%)", 0.0, 25.0, 2.0, 0.5)
    oc = st.slider("Organic carbon in topsoil (%)", 0.2, 5.0, 1.0, 0.1)
    sand = st.slider("Sand in topsoil (%)", 10, 89, 39)
    clay = st.slider("Clay in topsoil (%)", 5, 60, 21)
    cn = st.select_slider("Runoff tendency (curve number)", options=sorted(CN_SETS), value=81,
                          help="73 = soil takes up water well, 84 = water runs off easily")
    horizon = st.slider("Days after spraying to look at", 3, 30, 14)
    dose = st.number_input("Dose (kg/ha)", min_value=0.05, max_value=5.0, value=2.4, step=0.05)

try:
    weather = prepare_weather(pd.read_csv(up) if up else example_weather())
except Exception as e:  # show the reader what is wrong with the file
    st.error(f"Could not use this weather file: {e}")
    st.stop()
soil = soil_settings(slope_pct=slope, h1_oc=oc, h1_sand=float(sand), h1_clay=float(clay), cn_2=float(cn))

first_ok = weather.index[min(30, len(weather) - 2)].date()
last_ok = weather.index[-2].date()
c1, c2 = st.columns(2)
start = c1.date_input("First possible spray day", value=first_ok, min_value=weather.index[0].date(), max_value=last_ok)
n = c2.slider("Number of candidate days", 1, 14, 7)
candidates = [d for d in pd.date_range(start, periods=n) if d in weather.index[:-1]]
if not candidates:
    st.warning("No candidate day lies inside the weather table.")
    st.stop()

table = compare_spray_days(weather, candidates, horizon, soil, models, rate_kgha=dose)
for note in table.attrs["notes"]:
    st.warning(note)
ranked = table[table["rank"].notna()].sort_values("predicted_loss_gha")
if ranked.empty:
    st.warning("No candidate day has a full window of weather after it. Shorten the window or add forecast days.")
    st.stop()
best, worst = ranked.iloc[0], ranked.iloc[-1]
m1, m2, m3 = st.columns(3)
m1.metric("Lowest predicted loss", f"{best.predicted_loss_gha:.2f} g/ha")
m1.caption(f"if sprayed on {best.spray_date}")
m2.metric("Highest predicted loss", f"{worst.predicted_loss_gha:.2f} g/ha")
m2.caption(f"if sprayed on {worst.spray_date}")
m3.metric("Difference", f"{worst.predicted_loss_gha - best.predicted_loss_gha:.2f} g/ha")
m3.caption(f"the dose is {1000 * dose:.0f} g/ha")

st.subheader(f"Predicted pesticide loss in the {horizon} days after spraying")
chart = table.assign(day=table["spray_date"].map(lambda d: d.strftime("%Y-%m-%d (%a)"))).set_index("day")
st.bar_chart(chart["predicted_loss_gha"], y_label="g/ha", x_label="Spray day")
st.dataframe(table.rename(columns={
    "spray_date": "Spray day", "rain_in_window_mm": "Rain in window (mm)", "predicted_loss_gha": "Predicted loss (g/ha)",
    "loss_pct_of_dose": "Loss (% of dose)", "high_loss_days": "Days with loss of 1 g/ha or more",
    "worst_day": "Worst day", "worst_day_loss_gha": "Loss on worst day (g/ha)", "rank": "Rank (1 = best)",
    "days_covered": "Days covered"}), hide_index=True, use_container_width=True)

pick = st.selectbox("Show day-by-day detail for spray day", [c.date() for c in candidates])
with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    days = predict_days(weather, pd.Timestamp(pick), soil, models, rate_kgha=dose).iloc[:horizon]
d1, d2 = st.columns(2)
days.index = days.index.strftime("%Y-%m-%d")
d1.caption("Rain (mm per day)"); d1.bar_chart(days["rain_mm"])
d2.caption("Predicted pesticide loss (g/ha per day)"); d2.bar_chart(days["loss_gha"])

with st.expander("Limits: read before trusting a number", expanded=True):
    st.markdown("""
- The model learned from **PRZM simulations**, not from field measurements. It tells you what PRZM would say.
- All simulations are for **one herbicide (Flufenacet) on winter cereals**. Other products and crops are **not covered**.
""" + _spray_limits(models["meta"]) + """\
  The app warns above the table when your spray day or dose is outside what the models have seen.
- "Loss" is pesticide leaving the field edge with runoff water. What reaches a stream is not modelled.
- The sliders change one soil property at a time. Real soils change several together; unusual
  combinations are not covered by the training runs.
- On years it has not seen, the model underestimates total loss and can miss extreme storms.
- A weather forecast is uncertain; so is everything computed from it.
""")
