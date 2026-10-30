"""Translate forecast error into grid and market quantities (illustrative, stated assumptions).

1. Error energy: total |forecast - measured| MWh per year.
2. Reserve need: 99th / 99.9th percentile of hourly *over-forecast* (shortfall that must be
   covered by upward balancing reserve).
3. Imbalance settlement: a balance-responsible party that sells the whole fleet day-ahead
   at the forecast and settles deviations at Elia's single imbalance price pays, per hour,
   (measured - forecast) * (P_day_ahead - P_imbalance). Summed over the year this is the
   cost (or gain) attributable to forecast error, as a price-taker.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import config


def compute(ev: pd.DataFrame, methods=("elia_da11", "pen_q50", "hyb_q50")) -> dict:
    years = (ev.index.max() - ev.index.min()).days / 365.25
    out = {"years": years, "methods": {}}
    prices = _load_prices()
    evp = ev.join(prices, how="left")
    has_p = evp["da_price"].notna() & evp["imb_price"].notna()
    for m in methods:
        err_mw = (ev[m] - ev["y"]) * ev["capacity"]           # forecast - measured, MW == MWh per hour
        shortfall = err_mw.clip(lower=0)
        dev = -err_mw[has_p]                                   # measured - scheduled
        cost = (dev * (evp.loc[has_p, "da_price"] - evp.loc[has_p, "imb_price"])).sum()
        energy = (ev.loc[has_p, "y"] * ev.loc[has_p, "capacity"]).sum()
        out["methods"][m] = {
            "abs_error_gwh_per_year": float(np.abs(err_mw).sum() / 1000 / years),
            "p99_overforecast_mw": float(np.percentile(shortfall, 99)),
            "p999_overforecast_mw": float(np.percentile(shortfall, 99.9)),
            "imbalance_cost_eur_per_mwh": float(cost / energy) if energy else None,
            "imbalance_cost_meur_per_year": float(cost / 1e6 / (has_p.sum() / len(ev)) / years),
            "priced_hours": int(has_p.sum()),
        }
    return out


def _load_prices() -> pd.DataFrame:
    try:
        da = pd.read_parquet(config.DATA_RAW / "da_prices.parquet").set_index("time")
        imb = pd.read_parquet(config.DATA_RAW / "imbalance.parquet").set_index("time")
        return da.join(imb, how="inner")[["da_price", "imb_price"]]
    except FileNotFoundError:
        return pd.DataFrame(columns=["da_price", "imb_price"])


def tiles(res: dict, res_opt: dict, interval: dict, capacity_mw: float,
          ref: str = "elia_da11", ours: str = "hyb_q50") -> dict:
    """Dashboard tiles. ``res``: strict setting; ``res_opt``: optimistic setting; ``interval``: strict band stats."""
    r, o = res["methods"][ref], res["methods"][ours]
    band_mw = (interval[ref]["width"] - interval[ours]["width"]) / 100 * capacity_mw
    d_cost = r["imbalance_cost_meur_per_year"] - o["imbalance_cost_meur_per_year"]
    ro, oo = res_opt["methods"][ref], res_opt["methods"][ours]
    d_energy_opt = ro["abs_error_gwh_per_year"] - oo["abs_error_gwh_per_year"]
    t = [
        {"value": f"{band_mw:,.0f}", "unit": "MW", "label": "narrower average 80 % band, same coverage",
         "sub": f"at today's {capacity_mw / 1000:,.1f} GW: less reserve held for the same risk"},
        {"value": f"{o['imbalance_cost_eur_per_mwh']:,.2f}", "unit": "€/MWh",
         "label": "imbalance cost of forecast error (Hybrid)", "sub": f"Elia's forecast: {r['imbalance_cost_eur_per_mwh']:,.2f} €/MWh"},
        {"value": f"{d_cost:,.1f}", "unit": "M€/yr", "label": "lower imbalance settlement, whole fleet",
         "sub": "price-taker illustration, strict setting"},
        {"value": f"{d_energy_opt:,.0f}", "unit": "GWh/yr", "label": "less error energy with fresher weather runs",
         "sub": f"{oo['abs_error_gwh_per_year']:,.0f} vs {ro['abs_error_gwh_per_year']:,.0f} GWh/yr (24 h-old runs)"},
    ]
    tail = o["p99_overforecast_mw"] - r["p99_overforecast_mw"]
    notes = ("Assumptions: one balance-responsible party schedules the whole Belgian PV fleet day-ahead at the "
             "forecast and settles deviations at Elia's single imbalance price (hourly mean of quarter-hours); "
             "prices are taken as given, although real imbalance prices react to fleet-wide forecast errors. "
             f"Priced hours: {o['priced_hours']:,} (imbalance prices published from 2024-05-22). "
             f"Honest caveat: in the strict setting the Hybrid's 99th-percentile hourly over-forecast is {tail:+,.0f} MW "
             "versus Elia's, concentrated in negative-price hours when PV is curtailed — the main open problem.")
    return {"tiles": t, "notes": notes, "raw": res, "raw_optimistic": res_opt}
