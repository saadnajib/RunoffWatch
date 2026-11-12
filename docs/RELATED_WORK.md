# Related Work

Short review of tools, models and data related to RunoffWatch: an ML surrogate of
FOCUS PRZM_SW that predicts daily pesticide runoff loss, classifies high-loss days
(with SHAP explanations), and supports a "spray today or wait?" decision.

Sources were found by web search (Nov 2026), mostly checked at abstract or
landing-page level, not full text. "[not verified]" marks unconfirmed details.

## 1. Decision-support tools for application timing (runoff risk)

**1.1 Runoff Risk Advisory Forecast (RRAF), Wisconsin.** Run by the Wisconsin
Department of Agriculture (DATCP) together with the NOAA National Weather Service
(North Central River Forecast Center). Inputs: forecast rain and temperature,
snow and soil moisture. Method: a *process model* (NWS SAC-HTET flood-forecast
model). Output: daily runoff-risk map on a ~2 km grid, a few days ahead (~10 days
for snowmelt), telling farmers *when* to spread manure/fertiliser. Advisory only;
water quantity, not nutrient or chemical loads.
- https://www.manureadvisorysystem.wi.gov/pages/telling_me
- NOAA technical report (title, year [not verified]): https://repository.library.noaa.gov/view/noaa/6914/noaa_6914_DS1.pdf

**1.2 Great Lakes Runoff Risk tools (NOAA National Water Model).** Led by NOAA NWS
with partners (e.g. CIGLR, Univ. of Michigan); used in several states (e.g. MI,
OH, WI, MN [current list not verified]). Uses the National Water Model
(WRF-Hydro) plus statistical bias correction with edge-of-field and USGS data.
NCAR hosts a retrospective "Runoff Risk V3.0 Hydrometeorological Dataset"
(2008–2017). Target is water runoff for manure/fertiliser timing, not pesticides.
- https://ciglr.seas.umich.edu/research-story/agricultural-decision-support
- https://gdex.ucar.edu/datasets/d010113

**1.3 Hu et al. (2021) and Ford et al. (2022), hybrid runoff-event prediction.**
Hu et al., "Edge-of-field runoff prediction by a hybrid modeling approach using
causal inference", *Environmental Research Communications* (2021). They combine
National Water Model variables with a statistical model (Directed Information for
feature selection + XGBoost) to predict whether a daily edge-of-field runoff event
happens and how severe, in 13 Great Lakes domains. Ford et al. (2022, *Geophysical
Research Letters*, title [not verified]) extend this to a regional 1 km daily risk
product. This is the closest ML analogue to our "high-loss day" classifier, but
trained on measured runoff, not on a pesticide model.
- https://iopscience.iop.org/article/10.1088/2515-7620/ac0d0a
- Ford et al.: https://udspace.udel.edu/items/dd2a2085-3e6f-4c33-a489-e210599a94f6

**1.4 WIN-PST (Windows Pesticide Screening Tool), USDA NRCS.** A US screening tool
that ranks pesticide loss potential (leaching, solution runoff, adsorbed runoff)
from *soil and pesticide properties* (plus rainfall probability, method, rate).
Method: rule/index-based ranking (Low ... High), no daily weather, no crop type;
used in NRCS standard 595 to choose mitigation. It answers "is this pesticide on
this soil risky?", not "is today risky?".
- https://www.nrcs.usda.gov/resources/tech-tools/windows-pesticide-screening-tool-win-pst

**1.5 TOPPS runoff BMP materials (CropLife Europe / ECPA).** TOPPS (Train the
Operators to Prevent Point Source pollution) manuals guide an advisor through a
field *diagnosis* (soil, slope, distance to water, flow paths) that leads to
mitigation measures (buffer strips, tramlines, soil cover). Static and
qualitative, not forecast-based. We did not find the "Prowadis" tool itself
[not verified].
- TOPPS BMP advisor booklet, runoff (2021): https://croplifeeurope.eu/wp-content/uploads/2023/12/TOPPS_BMP_advisor_booklet_runoff_2021.pdf
- TOPPS runoff field manual (2013): https://www.gutelandwirtschaftlichepraxis.ch/fileadmin/gewaesserschutz-ProtectionDesEaux/documents/TOPPS_2013_runoff_field_manual.pdf

**1.6 Comber et al. (2019), live pesticide runoff risk (UK).** "A Generic Approach
for Live Prediction of the Risk of Agricultural Field Runoff and Delivery to
Watercourses", *Frontiers in Sustainable Food Systems* 3:42,
doi:10.3389/fsufs.2019.00042 (University of Leeds, NERC-funded). Live and forecast
rainfall from open APIs is combined with soil and land-use data; runoff is
computed with a *curve-number meta-model*; output is runoff and pesticide delivery
risk on a 1 km² grid (case studies: acid herbicides, metaldehyde). This is very
close to our decision-support idea, but uses a simple CN rule, not a regulatory
pesticide fate model.
- https://www.frontiersin.org/article/10.3389/fsufs.2019.00042/full

**1.7 RAINPROOF (University of Copenhagen).** A "digital water protection advisory
tool for drained soils": many Daisy model simulations (~2.6 million application
days, generated weather for Copenhagen, Elde (NL), Chemnitz (DE)) were used to
train *ML models that pick the safest application day*. Reported: ~80% accuracy
in picking the safest day with accurate weather and field data, but the actual
risk reduction was only 3–11% (46–86% of the achievable reduction). Closest
existing work to ours (simulator -> ML -> spray-day advice), but for drainage
with Daisy, not runoff with FOCUS PRZM. Paper title/authors and journal
(*Computers and Electronics in Agriculture*, 2022) [not verified].
- https://daisy.ku.dk/projects-and-collaboration/projects/rainproof/
- https://researchprofiles.ku.dk/en/publications/can-information-on-past-and-near-future-weather-and-field-conditi/

**1.8 Other related tools (short).**
- Syngenta + James Hutton Institute + SEPA run-off app (Scotland): static
  field risk score from soil/practice inputs (date [not verified]).
  https://www.hutton.ac.uk/print/node/15450
- Germany: DWD agrometeorology (ISABEL) and ZEPP/ISIP give weather-based disease
  and pest forecasts; we found **no German tool forecasting pesticide runoff
  risk** for a spray decision.
  https://www.landwirtschaft.sachsen.de/download/2_16_Boettcher_DWD.pdf

## 2. Surrogates / metamodels of pesticide fate and hydrological models

**2.1 MetaPEARL — Tiktak et al. (2006).** Tiktak, Boesten, van der Linden,
Vanclooster, "Mapping ground water vulnerability to pesticide leaching with a
process-based metamodel of EuroPEARL", *J. Environ. Qual.* 35(4):1213–1226,
doi:10.2134/jeq2005.0377. A simple analytical/regression metamodel calibrated on
~60,000 EuroPEARL runs (56 pesticides); target is the 80th percentile annual
leaching concentration at 1 m. It explains >90% of the model variance with four
spatial attributes. Classic example of "metamodel of a FOCUS model" — but yearly
leaching, not daily runoff.
- https://research.dial.uclouvain.be/handle/2078.5/135620

**2.2 MACRO neural-network metamodel — Stenemo et al. (2007).** Stenemo, Lindahl,
Gärdenäs, Jarvis, "Meta-modeling of the pesticide fate model MACRO for groundwater
exposure assessments using artificial neural networks", *J. Contaminant Hydrology*
93(1–4):270–283. Inputs: soil texture, organic carbon, pesticide half-life and
Koc; target: 80th percentile yearly concentration at 1 m (20-year runs). Best was
a two-hidden-layer feed-forward net that first classifies into three leaching
classes, then uses smaller nets per class. DOI [not verified].
- https://research.slu.se/sv/publications/meta-modeling-of-the-pesticide-fate-model-macro-for-groundwater-e/

**2.3 Nolan et al. (2012), neural-network metamodels of RZWQM.** "Verifiable
metamodels for nitrate losses to drains and groundwater in the Corn Belt, USA",
*Environ. Sci. Technol.* 46(2):901–908, doi:10.1021/es202875e. Neural nets
emulate the Root Zone Water Quality Model from fertiliser N, weather and soil
inputs; R² = 0.986 vs. the process model, but only r = 0.47 vs. measured
groundwater: a good fit to the simulator is not a good fit to reality.
- https://pubs.usgs.gov/publication/70032658

**2.4 Khandelwal et al. (2020), physics-guided LSTM emulator of SWAT.** "Physics
Guided Machine Learning Methods for Hydrology", arXiv:2012.02854. An LSTM
architecture coupled with SWAT, pre-trained on a 200-year synthetic SWAT run, with
separate LSTMs for intermediate states/fluxes (e.g. soil water, snow) to predict
daily streamflow. Shows that daily-sequence emulation of a process model works and
that adding intermediate states helps.
- https://arxiv.org/abs/2012.02854

**2.5 Other emulator notes.**
- Duong et al. (2025, *Water Resources Management*, title and exact link
  [not verified]) trained LSTMs on SWAT output (NSE > 0.91), but the LSTM made
  streamflow without rain (fails a mass-balance test). Lesson: test plausibility.
  https://ideas.repec.org/a/spr/waterr/v39y2025i11d10.1007_s11269-025-04231-5.html
- We found **no published ML emulator of PRZM / FOCUS PRZM_SW for daily runoff
  loss**. This is a gap (see Section 5).

## 3. Data-driven prediction of pesticide concentrations and events

**3.1 German small-stream monitoring (Kleingewässermonitoring, KgM).**
Liess et al. (2021), "Pesticides are the dominant stressors for vulnerable insects
in lowland streams", *Water Research*, doi:10.1016/j.watres.2021.117262. Regulatory
acceptable concentrations were exceeded in ~80% of monitored agricultural streams.
Halbach et al. (2021), "Small streams–large concentrations?", *Water Research* 203,
117535 (103 streams, 76 pesticides, 2018–2019): rainfall raises concentrations
about 10x, and automatic event samples after rain show much higher peaks than grab
samples. This motivates our focus on *event days*: risk is concentrated in a few
rain-driven runoff days. A later IEAM re-analysis questions some conclusions.
- https://www.umweltbundesamt.de/en/press/pressinformation/wherever-spraying-takes-place-streams-are-damaged
- Halbach et al. PubMed: https://pesquisa.bvsalud.org/bvsms/resource/pt/mdl-34403843
- Re-analysis: https://academic.oup.com/ieam/article/21/4/739/8090142

**3.2 Trajanov et al. (2018), ML on imbalanced pesticide pollution data.**
"Modeling the risk of water pollution by pesticides from imbalanced data",
*Environ. Sci. Pollut. Res.* 25(19):18781–18792, doi:10.1007/s11356-018-2099-7.
Data-mining models predict risky events in field-drain outflow from French field
trials; pollution events are rare, so they use cost-sensitive learning and
imbalance-aware metrics. Same problem as our "high-loss day" class imbalance.
- https://agris.fao.org/search/en/records/65df95a47c7033e84bee43a7

**3.3 Other data-driven examples.** Hu et al. (2021, entry 1.3) use XGBoost for
daily runoff events. A USGS study (2023) compared regression surrogate models
(e.g. SEAWAVE-Q) for pesticide concentrations at six rivers from streamflow and
sensor data [authors/report number not verified].
https://www.usgs.gov/publications/comparison-surrogate-models-estimate-pesticide-concentrations-six-us-geological-survey

## 4. Simulators and data used in this project

**4.1 PRZM-3.** Suárez, L.A. (2005), "PRZM-3, A Model for Predicting Pesticide and
Nitrogen Fate in the Crop Root and Unsaturated Soil Zones: Users Manual for Release
3.12.2", US EPA, EPA/600/R-05/111 (builds on earlier work by Carousel, Imhoff,
Hummel, Cheplick, Donigian). PRZM is a 1-D daily-step model; surface runoff uses
the USDA SCS curve number method and erosion a USLE variant (MUSLE family).
Successor: PRZM5 (Young & Fry, EPA, 2020).
- https://webarchive.library.unt.edu/eot2008/20081110044059/http:/www.epa.gov/athens/publications/reports/Suarez600R05111PRZM3.pdf

**4.2 SCS / NRCS curve number.** USDA NRCS National Engineering Handbook Part 630,
Chapter 10 "Estimation of Direct Runoff from Storm Rainfall" (2004 edition;
original Mockus 1964). Runoff Q = (P − 0.2S)² / (P + 0.8S) for P > 0.2S, with
S = 25400/CN − 254 (mm). This gives a cheap physical baseline for our model.
- https://mail.irrigationtoolbox.com/NEH/Part630_Hydrology/H_210_630_10.pdf

**4.3 FOCUS surface water scenarios.** FOCUS (2001), "FOCUS Surface Water Scenarios
in the EU Evaluation Process under 91/414/EEC", SANCO/4802/2001-rev.2. Ten
scenarios: D1–D6 (drainage, MACRO) and R1–R4 (runoff, PRZM), with TOXSWA for the
water body. R1 Weiherbach (DE, silt loam), R2 Porto (PT, sandy loam), R3 Bologna
(IT, clay loam), R4 Roujan (FR, sandy clay loam). EFSA (2020, "repair action",
EFSA Journal 18(6):e06119) recommended 20-year runs instead of 12/16 months.
- https://esdac.jrc.ec.europa.eu/projects/surface-water
- https://pmc.ncbi.nlm.nih.gov/articles/PMC7448096

**4.4 xLandscape / xOffFieldSoilRisk.** xLandscape is an open-source *modular
framework* (not a model) for landscape-scale pesticide exposure/effect models
(contacts include T. Schad, S. Bub, J. Heinrich); models include xAquaticRisk,
xOffFieldSoilRisk (xSR), xPollinator. We found no peer-reviewed paper on the
framework itself, only GitHub docs and SETAC training material.
- https://xlandscape.github.io/xOffFieldSoilRisk/
- https://xlandscape.github.io/SETAC-Training/

**4.5 JRC Agri4Cast / MARS meteorological database.** Daily weather from stations,
interpolated to a 25 x 25 km grid for the EU and neighbours, from 1979 (some JRC
pages say 1975 [not verified which is right]) to the last full year. Variables
include min/max/mean temperature, precipitation, wind speed at 10 m, vapour
pressure, global radiation and potential evapotranspiration (full EU variable
list [not verified]). Free after registration; CSV plus a grid shapefile
(EPSG:3035).
- https://agri4cast.jrc.ec.europa.eu/DataPortal/Index.aspx
- https://data.jrc.ec.europa.eu/dataset/jrc-marsop4-7-weather_obs_grid_2019

## 5. What already exists vs. what is new in our project

**Already exists (be honest):**
- Farmer runoff-risk forecasts *do exist*: operational RRAF tools in US states,
  and a UK proof of concept (Comber et al.). But they predict *water* runoff for
  manure/fertiliser, or use a simple CN rule; not tied to EU regulatory models.
- ML emulators of pesticide fate models exist (MetaPEARL, MACRO-ANN), but they
  predict *yearly leaching percentiles*, not daily runoff.
- "Simulator -> ML -> best spray day" exists for drainage (RAINPROOF / Daisy),
  with the honest result that real risk reduction was small (3–11%).

**What is new / the gap we fill:**
1. A *daily* ML surrogate of **FOCUS PRZM_SW**, the EU regulatory runoff model
   (we found no published PRZM emulator).
2. Pesticide-specific: inputs include pesticide properties (Koc, DT50, rate,
   timing), soil and crop, so it supports *what-if* questions across
   pesticide/soil/crop combinations, not just "will water run off?".
3. Explainability (SHAP) of high-loss days, linked to event-driven peaks seen in
   German small-stream monitoring.
4. Fast enough for interactive "spray today vs. wait N days" comparisons using a
   forecast, which running PRZM inside xLandscape is not.

**Limits to state clearly:** the surrogate learns PRZM, not reality (see Nolan et
al. 2012); FOCUS scenarios are a few sites; benefit of timing advice may be small
(RAINPROOF).

## 6. Baselines we could compare against

Ground truth for the surrogate: **PRZM_SW output itself** (held-out runs, held-out
years, and ideally held-out scenarios/pesticides to test generalisation).

Simple baselines (cheap, easy to explain):
1. **Rain-threshold rule**: high-risk if forecast rain > X mm in the next 1–3 days
   (the FOCUS PAT calculator avoids days with >2 mm rain in a 5-day window, per
   https://www.york.ac.uk/media/environment/documents/pesticides2017/posterpresentations/B-30.pdf).
2. **Curve-number rule**: compute daily runoff Q with SCS-CN from rain and the
   scenario CN; predict loss ~ Q x (pesticide mass on soil surface).
3. **Persistence / climatology**: yesterday's loss, or the mean loss for that
   day-of-year and scenario.
4. **Linear / logistic regression** on the same features (regression for loss,
   logistic for high-loss day).
5. **Stronger ML**: gradient boosting (XGBoost/LightGBM, as in Hu et al.) vs. our
   main model; optionally an LSTM over the weather sequence.

Metrics used in the emulator / hydrology literature:
- Regression: **NSE** (Nash–Sutcliffe efficiency), **R²**, **RMSE**, MAE, and
  bias / total-mass error; also on log-transformed loss because of many zeros.
- Event classification: precision, recall, F1, PR-AUC (better than ROC-AUC for
  rare events), and hit rate on the top-N loss days.
- Decision value: loss avoided by following the advice vs. random/fixed timing,
  as a share of the achievable reduction (as in RAINPROOF).
- Plausibility: zero rain -> near-zero loss; no loss before first application.
