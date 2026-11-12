"""
RunoffWatch - spray-day advisor (prototype).

Start with:   streamlit run app.py

Upload a daily weather table (past weeks + forecast) or use the example, pick
candidate spray days and a soil, and compare the predicted pesticide loss.
The numbers come from a machine-learning surrogate of the PRZM model, not from
field measurements. See the "Limits" box in the app.
"""

import warnings

import pandas as pd
import streamlit as st

from runoffwatch.whatif import (CN_SETS, check_inputs, compare_spray_days, example_weather, load_models,
                                predict_days, prepare_weather, soil_settings)

st.set_page_config(page_title="RunoffWatch spray-day advisor", layout="wide")
st.title("RunoffWatch: spray-day advisor")
st.caption("Prototype. Predicts how much pesticide would be washed off the field after spraying, "
           "using a machine-learning surrogate of the PRZM model.")


@st.cache_resource
def _models():
    return load_models("models")


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

for note in check_inputs(weather, soil, pd.Timestamp(candidates[0]), models["meta"]):
    st.warning(note)

table = compare_spray_days(weather, candidates, horizon, soil, models)
best = table.sort_values("predicted_loss_gha").iloc[0]
worst = table.sort_values("predicted_loss_gha").iloc[-1]
m1, m2, m3 = st.columns(3)
m1.metric("Lowest predicted loss", f"{best.predicted_loss_gha:.2f} g/ha")
m1.caption(f"if sprayed on {best.spray_date}")
m2.metric("Highest predicted loss", f"{worst.predicted_loss_gha:.2f} g/ha")
m2.caption(f"if sprayed on {worst.spray_date}")
m3.metric("Difference", f"{worst.predicted_loss_gha - best.predicted_loss_gha:.2f} g/ha")
m3.caption("the dose is 2400 g/ha")

st.subheader(f"Predicted pesticide loss in the {horizon} days after spraying")
chart = table.assign(day=table["spray_date"].map(lambda d: d.strftime("%Y-%m-%d (%a)"))).set_index("day")
st.bar_chart(chart["predicted_loss_gha"], y_label="g/ha", x_label="Spray day")
st.dataframe(table.rename(columns={
    "spray_date": "Spray day", "rain_in_window_mm": "Rain in window (mm)", "predicted_loss_gha": "Predicted loss (g/ha)",
    "loss_pct_of_dose": "Loss (% of dose)", "chance_of_high_loss_day": "Chance of a high-loss day",
    "worst_day": "Worst day", "worst_day_loss_gha": "Loss on worst day (g/ha)", "rank": "Rank (1 = best)",
    "days_covered": "Days covered"}), hide_index=True, use_container_width=True)
if table["days_covered"].min() < horizon:
    st.info("Some candidate days have fewer forecast days than the window; their totals cover fewer days.")

pick = st.selectbox("Show day-by-day detail for spray day", [c.date() for c in candidates])
with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    days = predict_days(weather, pd.Timestamp(pick), soil, models).iloc[:horizon]
d1, d2 = st.columns(2)
days.index = days.index.strftime("%Y-%m-%d")
d1.caption("Rain (mm per day)"); d1.bar_chart(days["rain_mm"])
d2.caption("Predicted pesticide loss (g/ha per day)"); d2.bar_chart(days["loss_gha"])

with st.expander("Limits: read before trusting a number", expanded=True):
    st.markdown("""
- The model learned from **PRZM simulations**, not from field measurements. It tells you what PRZM would say.
- All simulations used **one herbicide (Flufenacet), one dose (2400 g/ha), winter cereals, sprayed on 1 March**.
  Other products, doses, crops or seasons are **not covered**.
- "Loss" is pesticide leaving the field edge with runoff water. What reaches a stream is not modelled.
- A weather forecast is uncertain; so is everything computed from it.
""")
