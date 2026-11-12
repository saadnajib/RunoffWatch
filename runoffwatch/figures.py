"""Figures for the data report and the model report. One y-axis per panel, colours by role."""
from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

BLUE, ORANGE, INK, MUTED, GRID = "#2a78d6", "#eb6834", "#33322f", "#9a9890", "#e3e2dc"
AQUA = "#1baf7a"


def _style(ax, grid_axis="y"):
    ax.spines[["top", "right"]].set_visible(False)
    ax.spines[["left", "bottom"]].set_color(MUTED)
    ax.tick_params(colors=INK, labelsize=10)
    ax.grid(axis=grid_axis, color=GRID, lw=0.8)
    ax.set_axisbelow(True)


def _save(fig, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(path, dpi=140)
    plt.close(fig)


# --------------------------------------------------------------------------- #
# Data quality
# --------------------------------------------------------------------------- #
def quality_figures(rq: pd.DataFrame, envelope: pd.Series, events: pd.DataFrame,
                    decay: pd.DataFrame, out: Path) -> None:
    # 1. What is in the 9,977 folders
    labels = {"no_field": "No field in this cell\n(PRZM never started)", "no_output": "Inputs only,\nno results kept",
              "empty_output": "Empty result file", "has_output": "Results available"}
    counts = rq["status"].value_counts().reindex(list(labels)).fillna(0)
    fig, ax = plt.subplots(figsize=(8, 3.6))
    bars = ax.barh([labels[k] for k in counts.index], counts.values,
                   color=[MUTED, MUTED, MUTED, BLUE], height=0.6)
    for b, v in zip(bars, counts.values):
        ax.text(v + 40, b.get_y() + b.get_height() / 2, f"{int(v):,}", va="center", color=INK, fontsize=11)
    ax.invert_yaxis(); ax.set_xlabel("Run folders"); _style(ax, "x")
    ax.set_title("What the 9,977 run folders contain", loc="left", color=INK, fontsize=12)
    _save(fig, out / "q1_folder_status.png")

    # 2. Yearly soil decay, relative to the first year
    full = decay.dropna()
    rel = full.div(full.iloc[:, 0], axis=0)
    years = 1990 + np.arange(rel.shape[1])
    bad = rq["first_bad_app_year"].reindex(rel.index).notna()
    fig, ax = plt.subplots(figsize=(8, 4.2))
    for mask, color, name in [(~bad, BLUE, "never above envelope"), (bad, ORANGE, "above envelope at some point")]:
        r = rel[mask.values]
        if len(r):
            ax.fill_between(years, r.quantile(0.1), r.quantile(0.9), color=color, alpha=0.18, lw=0)
            ax.plot(years, r.median(), color=color, lw=2, label=f"Runs {name} (median, 10-90 % band)")
    ax.axhline(1, color=INK, lw=1, ls="--"); ax.text(years[-1], 1.25, "expected: about 1", ha="right", color=INK, fontsize=9)
    ax.set_yscale("log"); ax.set_ylabel("Yearly soil decay / decay in 1990"); ax.legend(frameon=False, fontsize=9, loc="upper left")
    ax.set_title("Same dose every year, yet 'pesticide decayed in soil' keeps growing", loc="left", color=INK, fontsize=12)
    _style(ax)
    _save(fig, out / "q2_soil_decay_growth.png")

    # 3. Envelope rule
    ev = events[events["days_since_app"].notna() & (events["pest_runoff_gha"] > 0)]
    ev = ev.sample(min(len(ev), 150_000), random_state=0)
    limit = envelope.to_numpy()[np.clip((ev["days_since_app"] // 15).astype(int), 0, len(envelope) - 1)]
    above = ev["loss_per_mm"] > limit
    fig, ax = plt.subplots(figsize=(8, 4.4))
    ax.scatter(ev.loc[~above, "days_since_app"], ev.loc[~above, "loss_per_mm"], s=2, color=BLUE, alpha=0.15,
               rasterized=True, label="Runoff day inside the envelope")
    ax.scatter(ev.loc[above, "days_since_app"], ev.loc[above, "loss_per_mm"].clip(upper=1e6), s=3, color=ORANGE,
               alpha=0.4, rasterized=True, label="Above the envelope (contaminated)")
    ax.step(envelope.index * 15, envelope.values, where="post", color=INK, lw=1.8, label="Envelope (limit)")
    ax.set_yscale("log"); ax.set_ylim(1e-6, 2e6)
    ax.set_xlabel("Days since spraying"); ax.set_ylabel("Pesticide lost per mm of runoff (g/ha per mm)")
    ax.legend(frameon=False, fontsize=9, loc="lower left", bbox_to_anchor=(0, 0.05), markerscale=4)
    ax.set_title("Healthy days fall with time since spraying; broken ones do not", loc="left", color=INK, fontsize=12)
    ax.text(0.01, 0.02, "values above 1e6 are drawn at 1e6", transform=ax.transAxes, color=MUTED, fontsize=8)
    _style(ax)
    _save(fig, out / "q3_envelope.png")

    # 4. Breakdown vs subsoil organic carbon
    d = rq[rq["clean_until"].notna() & rq["h3_oc"].notna()]
    grp = d["first_bad_app_year"].notna().groupby(pd.cut(d["h3_oc"], [-0.01, 0.3, 0.4, 0.5, 1.0, 100])).agg(["mean", "size"])
    names = ["0 - 0.3", "0.3 - 0.4", "0.4 - 0.5", "0.5 - 1", "over 1"]
    fig, ax = plt.subplots(figsize=(7, 4))
    bars = ax.bar(names, 100 * grp["mean"].values, color=ORANGE, width=0.6)
    for b, (m, n) in zip(bars, grp.values):
        ax.text(b.get_x() + b.get_width() / 2, 100 * m + 2, f"{100 * m:.0f} %\n({int(n)} runs)", ha="center", color=INK, fontsize=9)
    ax.set_ylim(0, 118); ax.set_xlabel("Organic carbon in the subsoil, 30-100 cm (%)"); ax.set_ylabel("Runs with broken pesticide results (%)")
    ax.set_title("Low organic carbon in the subsoil goes with the breakdown", loc="left", color=INK, fontsize=12)
    _style(ax)
    _save(fig, out / "q4_breakdown_vs_subsoil_oc.png")

    # 5. How much pesticide data stays usable, per application year
    d = rq[rq["clean_until"].notna()]
    yrs = np.arange(1990, 2000)
    simulated = [(pd.to_datetime(d["end"]) >= pd.Timestamp(y + 1, 2, 28)).sum() for y in yrs]
    clean = [(d["clean_until"] >= pd.Timestamp(y + 1, 3, 1)).sum() for y in yrs]
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.bar(yrs - 0.2, simulated, width=0.38, color=MUTED, label="Runs that simulated this year")
    ax.bar(yrs + 0.2, clean, width=0.38, color=BLUE, label="Runs with trusted pesticide results")
    ax.set_xticks(yrs); ax.set_xlabel("Application year (1 March - end of February)"); ax.set_ylabel("Runs")
    ax.legend(frameon=False, fontsize=9, loc="lower left")
    ax.set_title("Usable pesticide results shrink year by year", loc="left", color=INK, fontsize=12)
    _style(ax)
    _save(fig, out / "q5_clean_runs_per_year.png")


# --------------------------------------------------------------------------- #
# Models
# --------------------------------------------------------------------------- #
FEATURE_LABELS = {
    "rain_mm": "Rain today", "rain_prev1_mm": "Rain yesterday", "rain_prev2_3_mm": "Rain 2-3 days ago",
    "rain_7d_mm": "Rain in previous 7 days", "rain_14d_mm": "Rain in previous 14 days",
    "rain_30d_mm": "Rain in previous 30 days", "temp_c": "Temperature today", "temp_prev1_c": "Temperature yesterday",
    "temp_7d_c": "Mean temperature, previous 7 days", "evap_mm": "Evaporation today",
    "evap_7d_mm": "Evaporation, previous 7 days", "frozen_precip_30d_mm": "Snow proxy (frozen precipitation, 30 days)",
    "cn_today": "Curve number today (crop stage)", "cn_runoff_mm": "Runoff by the curve-number formula",
    "days_since_app": "Days since spraying", "rain_since_app_mm": "Rain since spraying",
    "heavy_rain_days_since_app": "Heavy-rain days since spraying", "temp_since_app_c": "Mean temperature since spraying",
    "rain_first3d_after_app_mm": "Rain in first 3 days after spraying", "usle_k": "Soil erodibility",
    "usle_ls": "Slope-length factor", "slope_pct": "Slope", "cn_2": "Curve number of the field",
    "h1_bd": "Topsoil bulk density", "h1_fc": "Topsoil field capacity", "h1_wp": "Topsoil wilting point",
    "h1_oc": "Topsoil organic carbon", "h1_kd": "Topsoil sorption (Kd)", "h1_sand": "Topsoil sand",
    "h1_clay": "Topsoil clay", "h3_bd": "Subsoil bulk density", "h3_oc": "Subsoil organic carbon",
}
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def model_figures(te, tc, scores, shap_rank, shap_sample, contrib, calendar, out: Path) -> None:
    from sklearn.metrics import average_precision_score, precision_recall_curve

    # m1 runoff: surrogate and baseline against PRZM
    s = te[(te["runoff_mm"] > 0) | (te["runoff_pred"] > 0.05) | (te["runoff_cn"] > 0.05)]
    s = s.sample(min(60_000, len(s)), random_state=0)
    fig, axes = plt.subplots(1, 2, figsize=(10, 4.6), sharex=True, sharey=True)
    for ax, col, title, color in [(axes[0], "runoff_cn", "Baseline: curve-number formula", MUTED),
                                  (axes[1], "runoff_pred", "Surrogate model", BLUE)]:
        ax.scatter(s["runoff_mm"], s[col], s=3, alpha=0.15, color=color, rasterized=True)
        lim = float(np.nanpercentile(s["runoff_mm"], 99.9))
        ax.plot([0, lim], [0, lim], color=INK, lw=1)
        ax.set_xlim(0, lim); ax.set_ylim(0, lim); ax.set_title(title, loc="left", color=INK, fontsize=11)
        ax.set_xlabel("PRZM runoff (mm/day)"); _style(ax, "both")
    axes[0].set_ylabel("Predicted runoff (mm/day)")
    fig.suptitle("Daily water runoff, test set (unseen weather files and unseen years)", x=0.01, ha="left", color=INK, fontsize=12)
    _save(fig, out / "m1_runoff_surrogate.png")

    # m2 pesticide loss
    e = tc[(tc["loss_gha"] > 1e-6) & (tc["loss_pred"] > 1e-6)]
    e = e.sample(min(60_000, len(e)), random_state=0)
    fig, ax = plt.subplots(figsize=(5.6, 5.2))
    ax.scatter(e["loss_gha"], e["loss_pred"], s=3, alpha=0.15, color=BLUE, rasterized=True)
    ax.plot([1e-6, 100], [1e-6, 100], color=INK, lw=1)
    ax.axvline(1.0, color=ORANGE, lw=1, ls="--"); ax.text(1.15, 2e-6, "high-loss\nday", color=ORANGE, fontsize=9)
    ax.set_xscale("log"); ax.set_yscale("log"); ax.set_xlim(1e-6, 100); ax.set_ylim(1e-6, 100)
    ax.set_xlabel("PRZM pesticide loss (g/ha per day)"); ax.set_ylabel("Surrogate (g/ha per day)")
    ax.set_title("Daily pesticide loss, test set", loc="left", color=INK, fontsize=12); _style(ax, "both")
    _save(fig, out / "m2_loss_surrogate.png")

    # m3 precision-recall
    y = tc["high_loss"].to_numpy()
    names = {"rain_today_rule": ("Rule: rain today", MUTED), "logistic_regression": ("Logistic regression", AQUA),
             "gradient_boosting": ("Gradient boosting", BLUE), "surrogate_predicted_loss": ("Surrogate (runoff x conc.)", ORANGE)}
    fig, ax = plt.subplots(figsize=(6.4, 4.6))
    for key, (label, color) in names.items():
        p, r, _ = precision_recall_curve(y, scores[key])
        ax.plot(r, p, color=color, lw=2, label=f"{label}  (PR-AUC {average_precision_score(y, scores[key]):.2f})")
    ax.axhline(y.mean(), color=INK, lw=1, ls=":"); ax.text(0.99, y.mean() + 0.015, "guessing", ha="right", color=INK, fontsize=9)
    ax.set_xlabel("Recall: share of high-loss days found"); ax.set_ylabel("Precision: share of alarms that are real")
    ax.set_xlim(0, 1); ax.set_ylim(0, 1.02); ax.legend(frameon=False, fontsize=9, loc="lower left")
    ax.set_title("Finding high-loss days, test set", loc="left", color=INK, fontsize=12); _style(ax, "both")
    _save(fig, out / "m3_high_loss_precision_recall.png")

    # m4 SHAP ranking
    top = shap_rank.head(12)[::-1]
    fig, ax = plt.subplots(figsize=(7.6, 4.8))
    ax.barh([FEATURE_LABELS.get(k, k) for k in top.index], top.values, color=BLUE, height=0.65)
    ax.set_xlabel("Mean |SHAP value| (influence on the high-loss prediction)")
    ax.set_title("What the classifier relies on most", loc="left", color=INK, fontsize=12); _style(ax, "x")
    _save(fig, out / "m4_shap_ranking.png")

    # m5 risk calendar by month
    bm = calendar["by_month"].reindex(range(1, 13)).fillna(0)
    fig, axes = plt.subplots(2, 1, figsize=(8, 5.6), sharex=True)
    x = np.arange(12)
    axes[0].bar(x, bm["high_loss_chance_pct_of_rain_days"], color=ORANGE, width=0.65)
    axes[0].set_ylabel("High-loss days\n(% of rain days)")
    axes[1].bar(x, bm["share_of_all_loss_pct"], color=BLUE, width=0.65)
    axes[1].set_xticks(x, MONTHS)
    axes[1].set_ylabel("Share of the year's\npesticide loss (%)")
    for ax in axes:
        _style(ax)
    axes[0].set_title("Risk calendar (spraying on 1 March; trusted simulation results)", loc="left", color=INK, fontsize=12)
    _save(fig, out / "m5_risk_calendar.png")

    # m6 risk by rain amount and time since spraying (one hue, light -> dark)
    g = calendar["by_rain_and_weeks"]
    fig, ax = plt.subplots(figsize=(7.4, 4.2))
    im = ax.imshow(np.ma.masked_invalid(g.to_numpy(float)), cmap="Blues", aspect="auto", vmin=0)
    ax.set_xticks(range(g.shape[1]), [str(c) for c in g.columns]); ax.set_yticks(range(g.shape[0]), [str(i) for i in g.index])
    vmax = np.nanmax(g.to_numpy(float))
    for i in range(g.shape[0]):
        for j in range(g.shape[1]):
            v = g.iat[i, j]
            ax.text(j, i, "few" if pd.isna(v) else (f"{v:.0f}" if v >= 10 else f"{v:.1f}"), ha="center", va="center",
                    fontsize=9, color=MUTED if pd.isna(v) else ("white" if v > 0.55 * vmax else INK))
    ax.set_xlabel("Rain today (mm)"); ax.set_ylabel("Time since spraying")
    ax.set_title("Chance of a high-loss day (%)", loc="left", color=INK, fontsize=12)
    fig.colorbar(im, ax=ax, fraction=0.04, pad=0.02)
    _save(fig, out / "m6_risk_rain_vs_time_since_spraying.png")
