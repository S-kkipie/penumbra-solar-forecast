"""Archived and live numerical weather prediction (NWP) inputs from Open-Meteo.

Training must only use information that existed when the forecast would have been
issued. Open-Meteo's Previous Runs API exposes, for every valid hour, the value that a
model predicted exactly 24 h (``_previous_day1``) or 48 h (``_previous_day2``) earlier.

* ``lead=2`` (48 h old runs) is strictly available before Elia's D-1 11:00 issuance for
  every hour of day D -> conservative, leakage-free setting used for the headline numbers.
* ``lead=1`` (24 h old runs) is slightly fresher than what is available at D-1 11:00 for
  afternoon hours -> optimistic bound, used for the live model and as a sensitivity check.
"""
from __future__ import annotations

import time

import pandas as pd
import requests

from . import config


def _get(url: str, params: dict, retries: int = 6) -> list[dict]:
    for attempt in range(retries):
        r = requests.get(url, params=params, timeout=180)
        if r.status_code == 429:  # minutely/hourly fair-use limit
            time.sleep(60 * (attempt + 1))
            continue
        r.raise_for_status()
        data = r.json()
        return data if isinstance(data, list) else [data]
    raise RuntimeError(f"Open-Meteo rate limit not cleared after {retries} retries")


def _frame_from_response(responses: list[dict], suffix: str, model_key: str) -> pd.DataFrame:
    frames = []
    for prov, resp in zip(config.PROVINCE_KEYS, responses):
        h = resp["hourly"]
        df = pd.DataFrame({"time": pd.to_datetime(h["time"], utc=True)})
        for v in config.NWP_VARS:
            df[v] = h.get(f"{v}{suffix}")
        df["province"] = prov
        frames.append(df)
    out = pd.concat(frames, ignore_index=True)
    out["model"] = model_key
    return out


def fetch_previous_runs(start: str, end: str, lead: int, models: dict[str, str] | None = None) -> pd.DataFrame:
    """Archived forecasts at a fixed lead (in days) for all provinces and models."""
    models = models or config.NWP_MODELS
    suffix = f"_previous_day{lead}"
    lats = ",".join(str(p[2]) for p in config.PROVINCES)
    lons = ",".join(str(p[3]) for p in config.PROVINCES)
    edges = list(pd.date_range(start, end, freq="4MS").strftime("%Y-%m-%d"))
    edges = sorted(set([start, *edges, end]))
    frames = []
    for key, model in models.items():
        for lo, hi in zip(edges[:-1], edges[1:]):
            hi_incl = (pd.Timestamp(hi) - pd.Timedelta(days=1)).strftime("%Y-%m-%d")
            params = {
                "latitude": lats, "longitude": lons, "models": model, "timezone": "GMT",
                "hourly": ",".join(f"{v}{suffix}" for v in config.NWP_VARS),
                "start_date": lo, "end_date": hi_incl,
            }
            frames.append(_frame_from_response(_get(config.OPENMETEO_PREVIOUS_RUNS, params), suffix, key))
            print(f"  open-meteo {key} lead={lead} {lo}..{hi_incl}")
            time.sleep(8)
    return pd.concat(frames, ignore_index=True)


def fetch_live(forecast_days: int = 3, past_days: int = 1, models: dict[str, str] | None = None) -> pd.DataFrame:
    """Latest operational runs (what an operator actually has at issuance time)."""
    models = models or config.NWP_MODELS
    lats = ",".join(str(p[2]) for p in config.PROVINCES)
    lons = ",".join(str(p[3]) for p in config.PROVINCES)
    frames = []
    for key, model in models.items():
        params = {
            "latitude": lats, "longitude": lons, "models": model, "timezone": "GMT",
            "hourly": ",".join(config.NWP_VARS),
            "forecast_days": forecast_days, "past_days": past_days,
        }
        frames.append(_frame_from_response(_get(config.OPENMETEO_FORECAST, params), "", key))
    return pd.concat(frames, ignore_index=True)
