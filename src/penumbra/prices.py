"""Market prices used only for the economic impact analysis (never as model inputs).

* Day-ahead prices, Belgian bidding zone: Energy-Charts API (Fraunhofer ISE),
  CC BY 4.0, data from Bundesnetzagentur | SMARD.de.
* Imbalance prices per quarter-hour: Elia Open Data (ods134, from 2024-05-22).
"""
from __future__ import annotations

import time

import pandas as pd
import requests

from . import config
from .elia import _export_csv

ENERGY_CHARTS = "https://api.energy-charts.info/price"


def fetch_day_ahead(start: str, end: str) -> pd.DataFrame:
    frames = []
    lo, stop = pd.Timestamp(start), pd.Timestamp(end)
    while lo <= stop:
        hi = min(lo + pd.DateOffset(months=3) - pd.Timedelta(days=1), stop)
        params = {"bzn": "BE", "start": lo.strftime("%Y-%m-%d"), "end": hi.strftime("%Y-%m-%d")}
        lo = hi + pd.Timedelta(days=1)
        for attempt in range(6):
            r = requests.get(ENERGY_CHARTS, params=params, timeout=120)
            if r.status_code != 429:
                break
            time.sleep(30 * (attempt + 1))  # fair-use limit of the free API
        r.raise_for_status()
        d = r.json()
        frames.append(pd.DataFrame({
            "datetime": pd.to_datetime(d["unix_seconds"], unit="s", utc=True),
            "da_price": d["price"],
        }))
        time.sleep(5)
    df = pd.concat(frames, ignore_index=True).drop_duplicates("datetime")
    # Since 2025-10-01 the day-ahead market clears per quarter-hour: average to hours.
    df["time"] = df["datetime"].dt.floor("h")
    return df.groupby("time", as_index=False)["da_price"].mean()


def fetch_imbalance(start: str = "2024-05-22", end: str | None = None) -> pd.DataFrame:
    where = f'datetime >= "{start}"' + (f' and datetime < "{end}"' if end else "")
    df = _export_csv(config.ELIA_IMBALANCE_DATASET, ["datetime", "systemimbalance", "imbalanceprice"], where)
    df["datetime"] = pd.to_datetime(df["datetime"], utc=True)
    df["time"] = df["datetime"].dt.floor("h")
    g = df.groupby("time")
    out = g[["imbalanceprice", "systemimbalance"]].mean()
    out = out[g["imbalanceprice"].count() == 4]
    return out.reset_index().rename(columns={"imbalanceprice": "imb_price", "systemimbalance": "sys_imbalance"})
