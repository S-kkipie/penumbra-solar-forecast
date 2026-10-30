"""Download every raw input used by the project into data/raw/ (re-runnable, ~15 min).

    python scripts/download.py [--only elia,weather,prices]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from penumbra import config, elia, prices, weather  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="elia,weather,prices")
    ap.add_argument("--end", default=None, help="exclusive end date for the NWP archive (default: today)")
    args = ap.parse_args()
    parts = set(args.only.split(","))
    config.DATA_RAW.mkdir(parents=True, exist_ok=True)
    end = args.end or pd.Timestamp.now("UTC").strftime("%Y-%m-%d")

    if "elia" in parts:
        print("Elia PV history ...")
        qh = elia.fetch_all(config.START)
        qh.to_parquet(config.DATA_RAW / "elia_pv_qh.parquet", index=False)
        print(f"  saved {len(qh):,} quarter-hour rows")

    if "prices" in parts:
        print("Day-ahead prices ...")
        prices.fetch_day_ahead(config.START, end).to_parquet(config.DATA_RAW / "da_prices.parquet", index=False)
        print("Imbalance prices ...")
        prices.fetch_imbalance().to_parquet(config.DATA_RAW / "imbalance.parquet", index=False)

    if "weather" in parts:
        for lead in (2, 1):
            print(f"Open-Meteo archived NWP, lead {lead} day(s) ...")
            wx = weather.fetch_previous_runs(config.START, end, lead=lead)
            wx.to_parquet(config.DATA_RAW / f"nwp_lead{lead}.parquet", index=False)
            print(f"  saved {len(wx):,} rows")


if __name__ == "__main__":
    main()
