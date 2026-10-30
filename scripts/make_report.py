"""Generate docs/EVALUATION.md and docs/figures/*.png from reports/*.json (single source of truth).

    python scripts/make_report.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

REPORTS, DOCS = ROOT / "reports", ROOT / "docs"
FIG = DOCS / "figures"
C = {"hyb": "#2a78d6", "pen": "#1baf7a", "elia": "#eb6834", "ink": "#0b0b0b", "muted": "#77756f", "grid": "#e7e5df"}
LABEL = {"persistence": "Persistence (D-2)", "climatology": "Climatology (month×hour)", "linear_nwp": "Linear NWP regression",
         "elia_da11": "Elia operational D-1 11h", "pen_q50": "**Penumbra** (weather only)", "hyb_q50": "**Penumbra Hybrid** (weather + Elia 11h)"}


def load(lead):
    return json.loads((REPORTS / f"metrics_lead{lead}.json").read_text())


def style(ax):
    ax.spines[["top", "right"]].set_visible(False)
    ax.spines[["left", "bottom"]].set_color(C["muted"])
    ax.tick_params(colors=C["muted"], labelsize=9)
    ax.grid(axis="y", color=C["grid"], linewidth=0.8)
    ax.set_axisbelow(True)


def fig_monthly(R):
    m = pd.DataFrame(R["by_month"])
    fig, ax = plt.subplots(figsize=(8, 3.2), dpi=160)
    for k, c, lab, ls in (("elia_da11", C["elia"], "Elia D-1 11h", "-"), ("pen_q50", C["pen"], "Penumbra (weather only)", "--"),
                          ("hyb_q50", C["hyb"], "Penumbra Hybrid", "-")):
        ax.plot(m["month"], m[k], color=c, lw=2, ls=ls, marker="o", ms=3.5, label=lab)
    style(ax)
    ax.set_ylabel("nMAE, % of capacity", color=C["muted"], fontsize=9)
    ax.tick_params(axis="x", rotation=60)
    ax.legend(frameon=False, fontsize=8, ncol=3, loc="upper right")
    fig.tight_layout()
    fig.savefig(FIG / "monthly_nmae.png")
    plt.close(fig)


def fig_coverage(R):
    r = pd.DataFrame(R["by_regime"])
    fig, ax = plt.subplots(figsize=(6, 2.6), dpi=160)
    y = range(len(r))
    ax.axvline(80, color=C["muted"], ls=":", lw=1)
    ax.scatter(r["elia_da11_coverage"], y, s=70, color=C["elia"], label="Elia P10–P90", zorder=3, edgecolor="white")
    ax.scatter(r["hyb_q50_coverage"], y, s=70, color=C["hyb"], label="Penumbra Hybrid", zorder=3, edgecolor="white")
    ax.set_yticks(list(y), [f"{a} ({n:,} h)" for a, n in zip(r["regime"], r["n_hours"])])
    ax.set_xlim(50, 100)
    style(ax)
    ax.grid(axis="x", color=C["grid"])
    ax.set_xlabel("% of hours inside the 80 % band (nominal 80 %)", color=C["muted"], fontsize=9)
    ax.legend(frameon=False, fontsize=8, loc="lower left")
    fig.tight_layout()
    fig.savefig(FIG / "coverage_by_regime.png")
    plt.close(fig)


def fig_day(date: str):
    d = json.loads((ROOT / "site" / "data" / "days.json").read_text())["days"][date]
    t = pd.to_datetime(d["t"]).tz_convert("Europe/Brussels")
    fig, ax = plt.subplots(figsize=(8, 3.4), dpi=160)
    ax.fill_between(t, d["q10"], d["q90"], color=C["hyb"], alpha=0.18, lw=0, label="80 % band")
    ax.plot(t, d["q50"], color=C["hyb"], lw=2, label="Penumbra Hybrid P50")
    ax.plot(t, d["elia"], color=C["elia"], lw=2, label="Elia D-1 11h")
    ax.plot(t, d["y"], color=C["ink"], lw=1.6, marker="o", ms=3, label="Measured")
    style(ax)
    ax.xaxis.set_major_formatter(matplotlib.dates.DateFormatter("%H:%M", tz=t.tz))
    ax.set_ylabel("MW", color=C["muted"], fontsize=9)
    ax.set_title(f"{date} (Brussels time)", fontsize=10, loc="left")
    ax.legend(frameon=False, fontsize=8, ncol=4, loc="upper left")
    fig.tight_layout()
    fig.savefig(FIG / "example_day.png")
    plt.close(fig)


def table(R):
    pt = {r["key"]: r for r in R["point"]}
    it = {r["key"]: r for r in R["interval"]}
    lines = ["| Method | nMAE % cap | nRMSE % cap | MAE MW | bias % cap | MAE skill vs Elia |",
             "|---|---:|---:|---:|---:|---:|"]
    for k in ("hyb_q50", "pen_q50", "elia_da11", "linear_nwp", "climatology", "persistence"):
        r = pt[k]
        sk = "—" if k == "elia_da11" else f"{r['skill_vs_elia_da11_pct']:+.1f} %"
        lines.append(f"| {LABEL[k]} | {r['nMAE_pct_cap']:.2f} | {r['nRMSE_pct_cap']:.2f} | {r['MAE_MW']:.0f} | {r['bias_pct_cap']:+.2f} | {sk} |")
    lines += ["", "| 80 % band | coverage % | mean width % cap | Winkler score | mean pinball (P10/50/90) |", "|---|---:|---:|---:|---:|"]
    for k in ("hyb_q50", "pen_q50", "elia_da11"):
        r = it[k]
        lines.append(f"| {LABEL[k]} | {r['coverage']:.1f} | {r['width']:.2f} | {r['winkler']:.2f} | {r['mean_pinball']:.3f} |")
    return "\n".join(lines)


def sig_table(R):
    lines = ["| Comparison (A vs B) | DM statistic | p-value | 95 % CI of nMAE(A) − nMAE(B), pp |", "|---|---:|---:|---:|"]
    names = {"hyb_q50": "Hybrid", "pen_q50": "Weather-only", "elia_da11": "Elia D-1 11h", "persistence": "Persistence", "linear_nwp": "Linear NWP"}
    for k, s in R["significance"].items():
        a, b = k.split("_vs_")
        p = "< 0.0001" if s["p_value"] < 1e-4 else f"{s['p_value']:.4f}"
        lo, hi = s["mae_diff_ci95_pct_cap"]
        lines.append(f"| {names[a]} vs {names[b]} | {s['dm_stat']:+.2f} | {p} | [{lo:+.2f}, {hi:+.2f}] |")
    return "\n".join(lines)


def main():
    FIG.mkdir(parents=True, exist_ok=True)
    R2, R1 = load(2), load(1)
    dq = json.loads((REPORTS / "data_quality.json").read_text())
    imp = json.loads((REPORTS / "impact.json").read_text())
    fi = json.loads((REPORTS / "feature_importance_lead2.json").read_text())
    days = json.loads((ROOT / "site" / "data" / "days.json").read_text())
    fig_monthly(R2)
    fig_coverage(R2)
    fig_day(days["default"])

    regime = pd.DataFrame(R2["by_regime"]).round(2)
    season = pd.DataFrame(R2["by_season"]).round(2)
    abl = R2.get("ablations", {})
    abl_lab = {"full_model": "Full weather-only model (8 NWP models, spread, POA, trailing ratio)",
               "abl_no_ai_model": "… without ECMWF AIFS (AI weather model)",
               "abl_no_uncertainty_feats": "… without multi-model spread / spatial dispersion",
               "abl_ecmwf_only": "ECMWF IFS only", "abl_icon_only": "ICON only"}
    m = imp["methods"]
    md = f"""# Evaluation report

*Generated by `scripts/make_report.py` from `reports/*.json` — every number below comes from the committed backtest outputs.*

## Protocol

* **Target:** hourly mean of Elia's upscaled measured PV output for Belgium (MW), expressed as capacity factor on the installed capacity known two days earlier.
* **Benchmark:** Elia's operational day-ahead forecast issued **D-1 at 11:00** (with its P10/P90 band), published in the same Elia dataset.
* **Backtest:** expanding window, one refit per month; test months {R2['by_month'][0]['month']} → {R2['by_month'][-1]['month']} ({R2['n_days']} days, {R2['n_hours']:,} daylight hours). For test month M the quantile models are trained on hours < M − 60 days, conformally calibrated on [M − 60 days, M), then frozen. A unit test (`tests/test_core.py::test_backtest_never_trains_on_test_month`) asserts this.
* **Identical sample:** every method is scored on exactly the same daylight hours (sun elevation > −2°, all forecasts present).
* **Hyperparameters:** fixed a priori (`src/penumbra/model.py::LGB_PARAMS`), never tuned on test months. One feature-design iteration (plane-of-array irradiance, off-day flag, trailing performance ratio, three extra NWP models) was made after the first backtest; it is disclosed here and its effect is visible in the ablation table.

### Two weather-input settings
| Setting | Weather input | Available at D-1 11:00? | Role |
|---|---|---|---|
| **Strict** (headline) | NWP runs issued **48 h** before each valid hour | Yes, for every hour of day D | conservative, leakage-free |
| **Optimistic** | NWP runs issued **24 h** before each valid hour | Only for night/early hours | upper bound on skill |

The live system uses the latest runs available at 10:30 UTC on D-1 (00Z/06Z cycles, 18–42 h old), so live skill should fall between the two settings — and the live track record measures it directly.

## Data quality (`reports/data_quality.json`)
* {dq['hours_with_target']:,} of {dq['hours_expected']:,} hours have a complete target ({dq['missing_target_pct']} % missing, never imputed); {dq['daylight_hours']:,} daylight hours.
* NWP gaps in daylight hours: {", ".join(f"{k} {v} %" for k, v in dq['nwp_missing_pct'].items())} (ECMWF AIFS archive starts 2025-03; handled natively by LightGBM).
* Elia D-1 11h forecast missing in {dq['elia_da11_missing_pct']} % of daylight hours.
* Installed PV capacity grew from {dq['capacity_mw_first']:,.0f} MW to {dq['capacity_mw_last']:,.0f} MW over the period → the model predicts capacity factor, not MW.
* Night hours with non-zero measured output: {dq['night_nonzero_hours']}.

## Results — strict setting (48 h-old weather runs)
{table(R2)}

### Statistical significance (strict)
{sig_table(R2)}

## Results — optimistic setting (24 h-old weather runs)
{table(R1)}

### Statistical significance (optimistic)
{sig_table(R1)}

## Where the errors are (strict)
By forecast sky regime (forecast clear-sky index; nMAE in % of capacity, coverage of the 80 % band in %):

{regime.to_markdown(index=False)}

By season:

{season.to_markdown(index=False)}

![Monthly nMAE](figures/monthly_nmae.png)

![Coverage by regime](figures/coverage_by_regime.png)

## Ablations (strict, weather-only median model, nMAE % of capacity)
| Variant | nMAE % cap |
|---|---:|
""" + "\n".join(f"| {abl_lab[k]} | {abl[k]:.3f} |" for k in abl_lab if k in abl) + f"""

Top features by gain (strict weather-only model): {", ".join(f"`{k}` ({100 * v:.1f} %)" for k, v in list(fi.items())[:8])}.

## Impact translation (strict, see `src/penumbra/impact.py`)
| Quantity | Elia D-1 11h | Penumbra Hybrid | Penumbra weather-only |
|---|---:|---:|---:|
| Absolute error energy, GWh/yr | {m['elia_da11']['abs_error_gwh_per_year']:,.0f} | {m['hyb_q50']['abs_error_gwh_per_year']:,.0f} | {m['pen_q50']['abs_error_gwh_per_year']:,.0f} |
| P99 hourly over-forecast, MW | {m['elia_da11']['p99_overforecast_mw']:,.0f} | {m['hyb_q50']['p99_overforecast_mw']:,.0f} | {m['pen_q50']['p99_overforecast_mw']:,.0f} |
| Imbalance cost of error, €/MWh produced | {m['elia_da11']['imbalance_cost_eur_per_mwh']:.2f} | {m['hyb_q50']['imbalance_cost_eur_per_mwh']:.2f} | {m['pen_q50']['imbalance_cost_eur_per_mwh']:.2f} |
| Imbalance cost of error, M€/yr (fleet) | {m['elia_da11']['imbalance_cost_meur_per_year']:.1f} | {m['hyb_q50']['imbalance_cost_meur_per_year']:.1f} | {m['pen_q50']['imbalance_cost_meur_per_year']:.1f} |

Assumptions: one balance-responsible party schedules the whole fleet day-ahead at the forecast and settles deviations at Elia's single imbalance price, as a price-taker. This is an illustration of the order of magnitude, not a market simulation.

## Example day
![Example day](figures/example_day.png)
"""
    (DOCS / "EVALUATION.md").write_text(md)
    print("wrote", DOCS / "EVALUATION.md")


if __name__ == "__main__":
    main()
