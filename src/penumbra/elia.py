"""Download Belgian PV generation and Elia's operational forecasts from Elia Open Data.

Elia publishes, per quarter-hour and per region, the upscaled measured PV output (MW),
the monitored installed capacity (MW) and several operational forecasts with P10/P90
bands. We keep the day-ahead forecast issued at D-1 11:00 local time
(``dayahead11h*``) as the primary benchmark, because its issuance time is explicit.
"""
from __future__ import annotations

import io
import time

import pandas as pd
import requests

from . import config

FIELDS_OLD = [
    "datetime", "region", "measured",
    "dayahead11hforecast", "dayahead11hconfidence10", "dayahead11hconfidence90",
    "dayaheadforecast", "dayaheadconfidence10", "dayaheadconfidence90",
    "monitoredcapacity",
]
RENAME = {
    "measured": "measured",
    "dayahead11hforecast": "elia_da11",
    "dayahead11hconfidence10": "elia_da11_p10",
    "dayahead11hconfidence90": "elia_da11_p90",
    "dayaheadforecast": "elia_da",
    "dayaheadconfidence10": "elia_da_p10",
    "dayaheadconfidence90": "elia_da_p90",
    "monitoredcapacity": "capacity",
}
REGIONS_OLD = ["Belgium", *config.PROVINCE_KEYS]


def _export_csv(dataset: str, select: list[str], where: str, retries: int = 4) -> pd.DataFrame:
    url = f"{config.ELIA_API}/{dataset}/exports/csv"
    params = {"select": ",".join(select), "where": where, "delimiter": ","}
    for attempt in range(retries):
        try:
            r = requests.get(url, params=params, timeout=300)
            r.raise_for_status()
            return pd.read_csv(io.StringIO(r.content.decode("utf-8-sig")))
        except (requests.RequestException, pd.errors.ParserError):
            if attempt == retries - 1:
                raise
            time.sleep(5 * (attempt + 1))
    raise RuntimeError("unreachable")


def _region_filter(regions: list[str]) -> str:
    return "region in (" + ",".join(f'"{r}"' for r in regions) + ")"


def fetch_ods032(start: str, end: str) -> pd.DataFrame:
    """Quarter-hourly history from the legacy dataset, chunked by quarter."""
    frames = []
    cache_dir = config.DATA_RAW / "elia_chunks"
    cache_dir.mkdir(parents=True, exist_ok=True)
    for lo, hi in _chunks(start, end, freq="3MS"):
        cache = cache_dir / f"ods032_{lo}_{hi}.parquet"
        if cache.exists():
            df = pd.read_parquet(cache)
        else:
            where = f'datetime >= "{lo}" and datetime < "{hi}" and {_region_filter(REGIONS_OLD)}'
            df = _export_csv(config.ELIA_HIST_DATASET, FIELDS_OLD, where)
            df.to_parquet(cache, index=False)
        frames.append(df)
        print(f"  elia ods032 {lo}..{hi}: {len(df):,} rows")
    return _normalise(pd.concat(frames, ignore_index=True))


def fetch_new_schema(dataset: str, start: str, end: str | None = None) -> pd.DataFrame:
    """ods209 (historical, new schema) or ods210 (near real-time). Keeps gridconnectiontype=Total."""
    measured_col = "measured_upscaled" if dataset == config.ELIA_HIST_NEW_DATASET else "measured"
    select = [f if f != "measured" else measured_col for f in FIELDS_OLD]
    regions_new = ["Belgium", *[p[1] for p in config.PROVINCES]]
    where = f'datetime >= "{start}" and gridconnectiontype = "Total" and {_region_filter(regions_new)}'
    if end:
        where += f' and datetime < "{end}"'
    df = _export_csv(dataset, select, where)
    df = df.rename(columns={measured_col: "measured"})
    df["region"] = df["region"].map(config.NEW_TO_OLD_REGION)
    return _normalise(df)


def _normalise(df: pd.DataFrame) -> pd.DataFrame:
    df = df.rename(columns=RENAME)
    df["datetime"] = pd.to_datetime(df["datetime"], utc=True)
    for c in df.columns.difference(["datetime", "region"]):
        if not pd.api.types.is_numeric_dtype(df[c]):  # ods209 stores numbers as text, decimal commas
            df[c] = pd.to_numeric(df[c].astype(str).str.replace(",", ".", regex=False), errors="coerce")
    return df.sort_values(["region", "datetime"]).reset_index(drop=True)


def _chunks(start: str, end: str, freq: str):
    edges = list(pd.date_range(start, end, freq=freq).strftime("%Y-%m-%d"))
    if not edges or edges[0] != start:
        edges = [start, *edges]
    if edges[-1] != end:
        edges.append(end)
    return list(zip(edges[:-1], edges[1:]))


def to_hourly(qh: pd.DataFrame) -> pd.DataFrame:
    """Average quarter-hours to hourly MW labelled by interval start (UTC).

    A value is kept only when all four quarter-hours are present; otherwise it is set to
    NaN rather than imputed, so every training/evaluation target is a real observation.
    """
    qh = qh.copy()
    qh["hour"] = qh["datetime"].dt.floor("h")
    value_cols = [c for c in RENAME.values() if c in qh.columns]
    g = qh.groupby(["region", "hour"])
    hourly = g[value_cols].mean().where(g[value_cols].count() == 4)
    hourly = hourly.dropna(how="all")
    return hourly.reset_index().rename(columns={"hour": "time"})


def fetch_all(start: str = config.START, nrt: bool = True) -> pd.DataFrame:
    """Full quarter-hourly history: ods032 up to its cut-off, ods209 after, ods210 for the last days."""
    cutoff = "2026-10-26"
    parts = [fetch_ods032(start, cutoff)]
    try:
        parts.append(fetch_new_schema(config.ELIA_HIST_NEW_DATASET, cutoff))
    except requests.RequestException as e:  # dataset may be briefly unavailable
        print("  ods209 unavailable:", e)
    if nrt:
        parts.append(fetch_new_schema(config.ELIA_NRT_DATASET, cutoff))
    return merge_sources(parts)


def merge_sources(parts: list[pd.DataFrame]) -> pd.DataFrame:
    """Merge overlapping Elia datasets, keeping per (region, quarter-hour) the most complete row.

    ods209 carries placeholder rows for future quarter-hours with everything but the 10-day
    forecast empty, so 'first source wins' would hide the populated near-real-time rows.
    Ties go to the earlier (more consolidated) source.
    """
    frames = []
    for priority, part in enumerate(parts):
        part = part.copy()
        part["_priority"] = priority
        frames.append(part)
    qh = pd.concat(frames, ignore_index=True)
    values = [c for c in RENAME.values() if c in qh.columns]
    qh["_filled"] = qh[values].notna().sum(axis=1)
    qh["_has_measured"] = qh["measured"].notna()
    qh = qh.sort_values(["region", "datetime", "_has_measured", "_filled", "_priority"],
                        ascending=[True, True, False, False, True])
    qh = qh.drop_duplicates(subset=["region", "datetime"], keep="first")
    return qh.drop(columns=["_priority", "_filled", "_has_measured"]).sort_values(["region", "datetime"]).reset_index(drop=True)
