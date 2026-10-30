"""Turn raw NWP + Elia data into an hourly, leakage-free design matrix for the national fleet.

Time convention: every row is an hourly interval labelled by its start, in UTC.
Open-Meteo radiation is the mean over the *preceding* hour, so the value labelled
H+1 describes the interval [H, H+1); instantaneous fields (cloud cover, temperature)
are averaged between H and H+1.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pvlib

from . import config

RADIATION_VARS = ["shortwave_radiation", "direct_radiation"]
INSTANT_VARS = ["cloud_cover", "temperature_2m"]
SHORT = {"shortwave_radiation": "ghi", "direct_radiation": "dir", "cloud_cover": "cc", "temperature_2m": "t2m"}


def align_nwp(nwp: pd.DataFrame) -> pd.DataFrame:
    """Re-label NWP fields so that ``time`` is the start of the hour they describe."""
    nwp = nwp.sort_values(["model", "province", "time"]).copy()
    out = nwp[["model", "province", "time"]].copy()
    g = nwp.groupby(["model", "province"], sort=False)
    for v in RADIATION_VARS:
        out[v] = g[v].shift(-1)                      # value at H+1 = mean over [H, H+1)
    for v in INSTANT_VARS:
        out[v] = 0.5 * (nwp[v] + g[v].shift(-1))     # trapezoid between H and H+1
    return out


def capacity_weights(elia_hourly: pd.DataFrame) -> pd.DataFrame:
    """Daily province weights = share of monitored PV capacity (slow-moving, known ex ante).

    The weight for day D uses the capacity reported on day D-2, so it never peeks.
    """
    cap = elia_hourly[elia_hourly["region"].isin(config.PROVINCE_KEYS)].copy()
    cap["date"] = cap["time"].dt.floor("D")
    daily = cap.groupby(["date", "region"])["capacity"].last().unstack()
    daily = daily.reindex(pd.date_range(daily.index.min(), daily.index.max() + pd.Timedelta(days=30), freq="D", tz="UTC"))
    daily = daily.ffill().shift(2).bfill()
    return daily.div(daily.sum(axis=1), axis=0)


def solar_geometry(times: pd.DatetimeIndex) -> pd.DataFrame:
    """Solar position and clear-sky GHI at the interval midpoint for Belgium's centroid."""
    mid = times + pd.Timedelta(minutes=30)
    loc = pvlib.location.Location(config.BE_LAT, config.BE_LON, altitude=100)
    sp = loc.get_solarposition(mid)
    cs = loc.get_clearsky(mid, model="ineichen", solar_position=sp)
    doy = mid.day_of_year.to_numpy()
    return pd.DataFrame({
        "elevation": sp["apparent_elevation"].to_numpy(),
        "azimuth": sp["azimuth"].to_numpy(),
        "cos_zenith": np.cos(np.radians(sp["apparent_zenith"].to_numpy())).clip(0, None),
        "ghi_cs": cs["ghi"].to_numpy(),
        "doy_sin": np.sin(2 * np.pi * doy / 365.25),
        "doy_cos": np.cos(2 * np.pi * doy / 365.25),
        "hour": mid.hour.to_numpy() + mid.minute.to_numpy() / 60,
    }, index=times)


def build_features(nwp: pd.DataFrame, weights: pd.DataFrame) -> pd.DataFrame:
    """National feature table indexed by hourly ``time``."""
    nwp = align_nwp(nwp)
    nwp["date"] = nwp["time"].dt.floor("D")
    w = weights.stack().rename("w").reset_index().rename(columns={"level_0": "date", "level_1": "province"})
    w.columns = ["date", "province", "w"]
    nwp = nwp.merge(w, on=["date", "province"], how="left")
    nwp["w"] = nwp["w"].fillna(1 / len(config.PROVINCE_KEYS))

    # Capacity-weighted national value per model and variable
    vars_ = RADIATION_VARS + INSTANT_VARS
    weighted = nwp[vars_].mul(nwp["w"], axis=0)
    weighted[["model", "time"]] = nwp[["model", "time"]]
    wsum = nwp[vars_].notna().mul(nwp["w"], axis=0)
    wsum[["model", "time"]] = nwp[["model", "time"]]
    num = weighted.groupby(["time", "model"])[vars_].sum(min_count=1)
    den = wsum.groupby(["time", "model"])[vars_].sum()
    nat = (num / den.replace(0, np.nan)).unstack("model")
    nat.columns = [f"{SHORT[v]}_{m}" for v, m in nat.columns]

    geo = solar_geometry(nat.index)
    X = pd.concat([geo, nat], axis=1)
    models = list(config.NWP_MODELS)
    ens = config.ENSEMBLE_MODELS
    ghi_cols = [f"ghi_{m}" for m in ens if f"ghi_{m}" in X]
    csd = X["ghi_cs"].clip(lower=25)
    for m in models:
        if f"ghi_{m}" in X:
            X[f"kt_{m}"] = (X[f"ghi_{m}"] / csd).clip(0, 1.5)
            X[f"dfrac_{m}"] = (X[f"dir_{m}"] / X[f"ghi_{m}"].clip(lower=1)).clip(0, 1)
    kt_cols = [f"kt_{m}" for m in ens if f"kt_{m}" in X]
    cc_cols = [f"cc_{m}" for m in ens if f"cc_{m}" in X]
    X["ghi_ens"] = X[ghi_cols].mean(axis=1)
    X["ghi_ens_std"] = X[ghi_cols].std(axis=1)
    X["kt_ens"] = X[kt_cols].mean(axis=1)
    X["kt_ens_std"] = X[kt_cols].std(axis=1)
    X["kt_ens_range"] = X[kt_cols].max(axis=1) - X[kt_cols].min(axis=1)
    X["cc_ens"] = X[cc_cols].mean(axis=1)
    X["cc_ens_std"] = X[cc_cols].std(axis=1)
    X["t2m_ens"] = X[[f"t2m_{m}" for m in ens if f"t2m_{m}" in X]].mean(axis=1)

    # Spatial heterogeneity: how differently provinces are forecast (ensemble mean kt)
    prov = nwp[nwp["model"].isin(ens)].groupby(["time", "province"])["shortwave_radiation"].mean().unstack()
    prov_kt = prov.div(X["ghi_cs"].clip(lower=25), axis=0).clip(0, 1.5)
    X["kt_spatial_std"] = prov_kt.std(axis=1)
    X = pd.concat([X, plane_of_array(X)], axis=1)
    X["offday"] = offday(X.index)
    X.index.name = "time"
    return X


def plane_of_array(X: pd.DataFrame) -> pd.DataFrame:
    """Transpose the ensemble-mean irradiance onto typical Belgian module planes.

    Residential PV in Belgium is mostly south-facing around 35 deg with a growing share of
    flat east-west commercial roofs; a tree model cannot derive this geometry itself.
    """
    zen = 90 - X["elevation"].clip(lower=0.5)
    dir_cols = [f"dir_{m}" for m in config.ENSEMBLE_MODELS if f"dir_{m}" in X]
    dhi_dir = X[dir_cols].mean(axis=1).clip(lower=0)
    ghi = X["ghi_ens"].clip(lower=0)
    dni = (dhi_dir / np.cos(np.radians(zen)).clip(lower=0.087)).clip(upper=1100)
    dhi = (ghi - dhi_dir).clip(lower=0)
    out = {}
    for name, tilt, az in (("poa_s35", 35, 180), ("poa_e15", 15, 90), ("poa_w15", 15, 270)):
        poa = pvlib.irradiance.get_total_irradiance(tilt, az, zen, X["azimuth"], dni, ghi, dhi, albedo=0.2,
                                                    model="isotropic")
        out[name] = poa["poa_global"].fillna(0).clip(lower=0)
    o = pd.DataFrame(out, index=X.index)
    o["poa_ew"] = 0.5 * (o.pop("poa_e15") + o.pop("poa_w15"))
    return o


# Belgian public holidays (fixed + Easter-based), 2024-2027
_EASTER = {2024: "2024-03-31", 2025: "2025-04-20", 2026: "2026-04-05", 2027: "2027-03-28"}


def belgian_holidays() -> set:
    days = set()
    for y, e in _EASTER.items():
        e = pd.Timestamp(e)
        days |= {e + pd.Timedelta(days=d) for d in (1, 39, 50)}
        days |= {pd.Timestamp(f"{y}-{md}") for md in ("01-01", "05-01", "07-21", "08-15", "11-01", "11-11", "12-25")}
    return {d.date() for d in days}


def offday(index: pd.DatetimeIndex) -> np.ndarray:
    """Weekend or public holiday in Brussels: low demand -> negative prices -> PV curtailment."""
    local = index.tz_convert("Europe/Brussels")
    hol = belgian_holidays()
    return ((local.dayofweek >= 5) | np.isin(local.date, list(hol))).astype(int)


def add_target(X: pd.DataFrame, elia_hourly: pd.DataFrame) -> pd.DataFrame:
    """Join national measured output, capacity and Elia's forecasts; express as capacity factor."""
    be = elia_hourly[elia_hourly["region"] == "Belgium"].set_index("time")
    cols = ["measured", "capacity", "elia_da11", "elia_da11_p10", "elia_da11_p90", "elia_da", "elia_da_p10", "elia_da_p90"]
    df = X.join(be[cols], how="inner")
    # Capacity known ex ante: use the value reported two days earlier.
    cap_daily = be["capacity"].resample("D").last().ffill().shift(2)
    df["capacity_ex_ante"] = cap_daily.reindex(df.index.floor("D")).to_numpy()
    df["capacity_ex_ante"] = df["capacity_ex_ante"].fillna(df["capacity"])
    df["cf"] = df["measured"] / df["capacity_ex_ante"]
    for c in ["elia_da11", "elia_da11_p10", "elia_da11_p90", "elia_da", "elia_da_p10", "elia_da_p90"]:
        df[f"{c}_cf"] = df[c] / df["capacity_ex_ante"]
    df = df.join(trailing_ratios(df))
    return df


def trailing_ratios(df: pd.DataFrame, window_days: int = 14, lag_days: int = 2) -> pd.DataFrame:
    """Adaptive performance ratios from the last ``window_days`` complete days ending D-``lag_days``.

    * pr_trail: measured CF / NWP-ensemble irradiance -> tracks drift in fleet performance
      (capacity estimate errors, soiling, snow, growing curtailment) and NWP bias.
    * elia_ratio_trail: measured / Elia's 11h forecast -> Elia's recent bias (hybrid only).
    Only data from days <= D-2 are used, all of which is published before D-1 11:00.
    """
    d = df[df["elevation"] > 5]
    day = d.index.floor("D")
    daily = pd.DataFrame({
        "cf": d["cf"].groupby(day).sum(min_count=6),
        "ghi": (d["ghi_ens"] / 1000).where(d["cf"].notna()).groupby(day).sum(min_count=6),
        "elia": d["elia_da11_cf"].where(d["cf"].notna()).groupby(day).sum(min_count=6),
    })
    full = pd.date_range(daily.index.min(), df.index.max().floor("D"), freq="D", tz="UTC")
    daily = daily.reindex(full)
    roll = daily.rolling(window_days, min_periods=window_days // 2).sum().shift(lag_days)
    out = pd.DataFrame({"pr_trail": roll["cf"] / roll["ghi"], "elia_ratio_trail": roll["cf"] / roll["elia"]})
    return out.reindex(df.index.floor("D")).set_axis(df.index)


def add_market_features(df: pd.DataFrame, da_prices: pd.DataFrame) -> pd.DataFrame:
    """Yesterday's day-ahead prices (known since D-2 ~13:00 CET, i.e. before D-1 11:00).

    Negative prices make large PV plants curtail; negative-price regimes persist from one
    day to the next (sunny, windy, low-demand spells), so D-1 prices are an ex-ante proxy
    for tomorrow's curtailment risk.
    """
    p = da_prices.set_index("time")["da_price"].sort_index()
    p = p[~p.index.duplicated()]
    prev = p.reindex(df.index - pd.Timedelta(hours=24)).to_numpy()
    out = df.copy()
    out["da_price_d1"] = prev
    # Count negative hours over the previous *local* delivery day, i.e. one whole auction
    # result published at D-2 ~13:00 CET.
    neg = (p < 0).astype(float).where(p.notna())
    local_day = neg.index.tz_convert("Europe/Brussels").date
    daily_neg = neg.groupby(local_day).sum(min_count=20)
    prev_day = (df.index.tz_convert("Europe/Brussels").normalize() - pd.Timedelta(days=1)).date
    out["neg_hours_d1"] = pd.Series(daily_neg).reindex(prev_day).to_numpy()
    return out


def model_feature_columns(df: pd.DataFrame, with_elia: bool = False) -> list[str]:
    base = ["elevation", "azimuth", "cos_zenith", "ghi_cs", "doy_sin", "doy_cos", "hour",
            "ghi_ens", "ghi_ens_std", "kt_ens", "kt_ens_std", "kt_ens_range", "cc_ens", "cc_ens_std",
            "t2m_ens", "kt_spatial_std", "poa_s35", "poa_ew", "offday", "pr_trail", "da_price_d1", "neg_hours_d1"]
    per_model = [c for c in df.columns if c.split("_")[0] in {"ghi", "dir", "cc", "t2m", "kt", "dfrac"}
                 and c.split("_")[-1] in config.NWP_MODELS]
    cols = base + per_model
    if with_elia:
        cols += ["elia_da11_cf", "elia_da11_p10_cf", "elia_da11_p90_cf", "elia_ratio_trail"]
    return [c for c in dict.fromkeys(cols) if c in df.columns]
