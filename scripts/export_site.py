"""Compile backtest results into the JSON files the static dashboard reads.

    python scripts/export_site.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from penumbra import config, evaluate, impact  # noqa: E402

REPORTS = config.ROOT / "reports"
LIMITATIONS = ("Limits: national aggregate only; Elia's 'measured' series is itself an upscaled estimate; "
               "curtailment at negative prices is not modelled; live inputs are fresher than the strict backtest.")


def _r(x, d=1):
    return None if x is None or (isinstance(x, float) and np.isnan(x)) else round(float(x), d)


def days_payload(pred: pd.DataFrame) -> dict:
    pred = pred.copy()
    mw = lambda c: pred[c] * pred["capacity"]  # noqa: E731
    local_date = pred.index.tz_convert("Europe/Brussels").strftime("%Y-%m-%d")
    pred["date"] = local_date
    for c in ["y", "elia_da11", "pen_q50", "hyb_q10", "hyb_q50", "hyb_q90"]:
        pred[c + "_mw"] = mw(c)
    days = {}
    for d, g in pred.groupby("date"):
        if len(g) < 23:
            continue
        days[d] = {
            "t": [t.isoformat() for t in g.index],
            "y": [_r(v, 0) for v in g["y_mw"]], "elia": [_r(v, 0) for v in g["elia_da11_mw"]],
            "pen": [_r(v, 0) for v in g["pen_q50_mw"]], "q10": [_r(v, 0) for v in g["hyb_q10_mw"]],
            "q50": [_r(v, 0) for v in g["hyb_q50_mw"]], "q90": [_r(v, 0) for v in g["hyb_q90_mw"]],
            "day": [bool(e > -2) for e in g["elevation"]],
        }
    ev = evaluate.evaluation_set(pred)
    ev = ev.assign(date=ev.index.tz_convert("Europe/Brussels").strftime("%Y-%m-%d"))
    daily = ev.groupby("date").apply(lambda g: pd.Series({
        "elia": np.mean(np.abs(g["elia_da11"] - g["y"]) * g["capacity"]),
        "hyb": np.mean(np.abs(g["hyb_q50"] - g["y"]) * g["capacity"]),
        "energy": (g["y"] * g["capacity"]).sum(),
        "width": ((g["hyb_q90"] - g["hyb_q10"]) * g["capacity"]).mean(),
    }), include_groups=False)
    daily = daily[daily.index.isin(days)]
    chips = [
        {"label": "Elia's worst day", "date": daily["elia"].idxmax()},
        {"label": "Our worst day", "date": daily["hyb"].idxmax()},
        {"label": "Biggest gain vs Elia", "date": (daily["elia"] - daily["hyb"]).idxmax()},
        {"label": "Sunniest day", "date": daily["energy"].idxmax()},
        {"label": "Most uncertain day", "date": daily["width"].idxmax()},
    ]
    dates = sorted(days)
    return {"dates": dates, "days": days, "chips": chips, "default": chips[2]["date"]}


def main() -> None:
    out = {"generated_at": pd.Timestamp.now("UTC").isoformat(), "leads": {}, "limitations": LIMITATIONS}
    for lead in (2, 1):
        out["leads"][str(lead)] = json.loads((REPORTS / f"metrics_lead{lead}.json").read_text())
    out["data_quality"] = json.loads((REPORTS / "data_quality.json").read_text())
    imp = json.loads((REPORTS / "feature_importance_lead2.json").read_text())
    out["feature_importance"] = [{"feature": k, "gain": v} for k, v in list(imp.items())[:15]]

    pred = pd.read_parquet(config.DATA_PROCESSED / "backtest_lead2.parquet")
    res = impact.compute(evaluate.evaluation_set(pred))
    res_opt = impact.compute(evaluate.evaluation_set(pd.read_parquet(config.DATA_PROCESSED / "backtest_lead1.parquet")))
    interval = {r["key"]: r for r in out["leads"]["2"]["interval"]}
    out["impact"] = impact.tiles(res, res_opt, interval, out["data_quality"]["capacity_mw_last"])
    (REPORTS / "impact.json").write_text(json.dumps(res, indent=1))
    (REPORTS / "impact_optimistic.json").write_text(json.dumps(res_opt, indent=1))

    config.SITE_DATA.mkdir(parents=True, exist_ok=True)
    (config.SITE_DATA / "backtest.json").write_text(json.dumps(out, default=float, separators=(",", ":")))
    (config.SITE_DATA / "days.json").write_text(json.dumps(days_payload(pred), separators=(",", ":")))
    print("site data written:", sorted(p.name for p in config.SITE_DATA.glob("*.json")))
    print(json.dumps(out["impact"]["tiles"], indent=1))


if __name__ == "__main__":
    main()
