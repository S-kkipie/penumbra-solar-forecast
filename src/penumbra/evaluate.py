"""Score backtest predictions: headline table, breakdowns, calibration and significance."""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import metrics as M

POINT_METHODS = {
    "persistence": "Persistence (D-2)",
    "climatology": "Climatology (month x hour)",
    "linear_nwp": "Linear NWP regression",
    "elia_da11": "Elia operational D-1 11h",
    "pen_q50": "Penumbra (NWP only)",
    "hyb_q50": "Penumbra Hybrid (NWP + Elia)",
}
INTERVALS = {
    "elia_da11": ("elia_da11_p10", "elia_da11_p90"),
    "pen_q50": ("pen_q10", "pen_q90"),
    "hyb_q50": ("hyb_q10", "hyb_q90"),
}


def evaluation_set(pred: pd.DataFrame) -> pd.DataFrame:
    """Daylight hours where every method has a value -> identical sample for all methods."""
    cols = list(POINT_METHODS) + [c for pair in INTERVALS.values() for c in pair]
    ev = pred[(pred["elevation"] > -2) & pred["y"].notna()].dropna(subset=cols)
    return ev


def sky_regime(ev: pd.DataFrame) -> pd.Series:
    """Weather regime from the *forecast* clear-sky index (known ex ante)."""
    return pd.cut(ev["kt_ens"], [-np.inf, 0.35, 0.65, np.inf], labels=["overcast", "variable", "clear"])


def point_table(ev: pd.DataFrame) -> pd.DataFrame:
    rows = []
    mean_cf = ev["y"].mean()
    for col, label in POINT_METHODS.items():
        err_mw = (ev[col] - ev["y"]) * ev["capacity"]
        rows.append({
            "method": label, "key": col,
            "nMAE_pct_cap": 100 * M.mae(ev["y"], ev[col]),
            "nRMSE_pct_cap": 100 * M.rmse(ev["y"], ev[col]),
            "rMAE_pct_mean": 100 * M.mae(ev["y"], ev[col]) / mean_cf,
            "bias_pct_cap": 100 * M.bias(ev["y"], ev[col]),
            "MAE_MW": float(np.mean(np.abs(err_mw))),
            "RMSE_MW": float(np.sqrt(np.mean(err_mw ** 2))),
            "P99_abs_err_MW": float(np.percentile(np.abs(err_mw), 99)),
        })
    t = pd.DataFrame(rows).set_index("key")
    for ref in ("persistence", "elia_da11"):
        t[f"skill_vs_{ref}_pct"] = [M.skill(m, t.loc[ref, "nMAE_pct_cap"]) for m in t["nMAE_pct_cap"]]
    t["skill_rmse_vs_elia_da11_pct"] = [M.skill(m, t.loc["elia_da11", "nRMSE_pct_cap"]) for m in t["nRMSE_pct_cap"]]
    return t


def interval_table(ev: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for col, (lo, hi) in INTERVALS.items():
        s = M.interval_scores(ev["y"], ev[lo], ev[hi], alpha=0.2)
        q = {0.1: ev[lo], 0.5: ev[col], 0.9: ev[hi]}
        s["mean_pinball"] = float(np.mean([M.pinball(ev["y"], v, t) for t, v in q.items()]))
        s["method"] = POINT_METHODS[col]
        rows.append({"key": col, **s})
    t = pd.DataFrame(rows).set_index("key")
    t[["coverage", "width", "winkler", "mean_pinball"]] *= [100, 100, 100, 100]
    return t


def significance(ev: pd.DataFrame) -> dict:
    out = {}
    for a in ("pen_q50", "hyb_q50"):
        for b in ("elia_da11", "persistence", "linear_nwp"):
            ea, eb = ev[a] - ev["y"], ev[b] - ev["y"]
            dm = M.diebold_mariano(ea, eb, ev.index)
            lo, hi = M.block_bootstrap_ci(ea, eb, ev.index)
            out[f"{a}_vs_{b}"] = {**dm, "mae_diff_ci95_pct_cap": [100 * lo, 100 * hi]}
    return out


def breakdown(ev: pd.DataFrame, by: pd.Series, methods=("elia_da11", "pen_q50", "hyb_q50")) -> pd.DataFrame:
    g = ev.groupby(by, observed=True)
    res = {m: g.apply(lambda d, m=m: 100 * M.mae(d["y"], d[m]), include_groups=False) for m in methods}
    res["n_hours"] = g.size()
    for m, (lo, hi) in INTERVALS.items():
        if m in methods:
            res[f"{m}_coverage"] = g.apply(
                lambda d, lo=lo, hi=hi: 100 * float(((d["y"] >= d[lo]) & (d["y"] <= d[hi])).mean()), include_groups=False)
    return pd.DataFrame(res)


def reliability(ev: pd.DataFrame, key: str = "hyb_q50") -> list[dict]:
    """Observed frequency below each predicted quantile (ideal = nominal level)."""
    lo, hi = INTERVALS[key]
    return [{"nominal": t, "observed": float((ev["y"] <= ev[c]).mean())} for t, c in ((0.1, lo), (0.5, key), (0.9, hi))]


def full_report(pred: pd.DataFrame) -> dict:
    ev = evaluation_set(pred)
    by_month = breakdown(ev, ev.index.strftime("%Y-%m"))
    by_regime = breakdown(ev, sky_regime(ev))
    by_hour = breakdown(ev, ev.index.hour)
    season = ev.index.month.map({12: "DJF", 1: "DJF", 2: "DJF", 3: "MAM", 4: "MAM", 5: "MAM",
                                 6: "JJA", 7: "JJA", 8: "JJA", 9: "SON", 10: "SON", 11: "SON"})
    by_season = breakdown(ev, pd.Series(season, index=ev.index))
    report = {
        "n_hours": int(len(ev)), "n_days": int(ev.index.floor("D").nunique()),
        "period": [str(ev.index.min()), str(ev.index.max())],
        "point": point_table(ev).reset_index().to_dict(orient="records"),
        "interval": interval_table(ev).reset_index().to_dict(orient="records"),
        "significance": significance(ev),
        "by_month": by_month.reset_index(names="month").to_dict(orient="records"),
        "by_regime": by_regime.reset_index(names="regime").to_dict(orient="records"),
        "by_hour": by_hour.reset_index(names="hour_utc").to_dict(orient="records"),
        "by_season": by_season.reset_index(names="season").to_dict(orient="records"),
        "reliability_hybrid": reliability(ev, "hyb_q50"),
        "reliability_penumbra": reliability(ev, "pen_q50"),
        "reliability_elia": reliability(ev, "elia_da11"),
    }
    abl = [c for c in pred.columns if c.startswith("abl_")]
    if abl:
        ev2 = pred.loc[ev.index]
        report["ablations"] = {c: 100 * M.mae(ev2["y"], ev2[c]) for c in abl} | {
            "full_model": 100 * M.mae(ev["y"], ev["pen_q50"])}
    return report
