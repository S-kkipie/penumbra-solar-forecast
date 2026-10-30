"""Assemble the hourly modelling table from the raw downloads."""
from __future__ import annotations

import pandas as pd

from . import config, elia, features


def load_elia_hourly() -> pd.DataFrame:
    qh = pd.read_parquet(config.DATA_RAW / "elia_pv_qh.parquet")
    return elia.to_hourly(qh)


def build_table(lead: int, elia_hourly: pd.DataFrame | None = None) -> pd.DataFrame:
    elia_hourly = load_elia_hourly() if elia_hourly is None else elia_hourly
    nwp = pd.read_parquet(config.DATA_RAW / f"nwp_lead{lead}.parquet")
    extra = config.DATA_RAW / f"nwp_lead{lead}_extra.parquet"
    if extra.exists():
        nwp = pd.concat([nwp, pd.read_parquet(extra)], ignore_index=True)
    weights = features.capacity_weights(elia_hourly)
    X = features.build_features(nwp, weights)
    df = features.add_target(X, elia_hourly)
    prices = config.DATA_RAW / "da_prices.parquet"
    if prices.exists():
        df = features.add_market_features(df, pd.read_parquet(prices))
    df = df[df.index >= pd.Timestamp(config.START, tz="UTC")]
    return df


def quality_report(df: pd.DataFrame) -> dict:
    """Data-quality facts reported in the README / dashboard."""
    day = df[df["elevation"] > -2]
    full_index = pd.date_range(df.index.min(), df.index.max(), freq="h", tz="UTC")
    nwp_cols = [c for c in df.columns if c.startswith("ghi_") and c.split("_")[-1] in config.NWP_MODELS]
    return {
        "first_hour": str(df.index.min()), "last_hour": str(df.index.max()),
        "hours_expected": len(full_index), "hours_with_target": int(df["cf"].notna().sum()),
        "daylight_hours": int(len(day)),
        "missing_target_pct": round(100 * (1 - df["cf"].notna().sum() / len(full_index)), 3),
        "nwp_missing_pct": {c.split("_")[-1]: round(100 * day[c].isna().mean(), 2) for c in nwp_cols},
        "elia_da11_missing_pct": round(100 * day["elia_da11"].isna().mean(), 2),
        "capacity_mw_first": round(float(df["capacity_ex_ante"].iloc[0]), 1),
        "capacity_mw_last": round(float(df["capacity_ex_ante"].iloc[-1]), 1),
        "cf_max": round(float(df["cf"].max()), 3),
        "night_nonzero_hours": int(((df["elevation"] < -6) & (df["measured"] > 1)).sum()),
    }
