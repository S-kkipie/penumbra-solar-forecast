"""Daily operational run: issue tomorrow's forecast before the day-ahead gate and score past days.

The forecast log is append-only: once a target day has been issued it is never
rewritten, and the git history of ``site/data/live/forecast_log.json`` timestamps every
issuance. This gives a genuinely out-of-sample, publicly verifiable track record.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import numpy as np
import pandas as pd

from . import config, elia, features, prices, weather
from .model import QuantileForecaster

TZ = "Europe/Brussels"
LIVE_DIR = Path(os.environ.get("PENUMBRA_LIVE_DIR", config.SITE_DATA / "live"))
# Before this UTC hour we wait for Elia's 11:00 forecast (Hybrid); from it on, weather-only is
# issued as a fallback so a forecast always exists before the 12:00 CET gate closure.
FALLBACK_FROM_UTC_HOUR = 11
LOG_PATH = LIVE_DIR / "forecast_log.json"
SUMMARY_PATH = LIVE_DIR / "live.json"


def _load_log() -> dict:
    return json.loads(LOG_PATH.read_text()) if LOG_PATH.exists() else {}


def _recent_elia(now: pd.Timestamp, days: int = 16) -> pd.DataFrame:
    start = (now - pd.Timedelta(days=days)).strftime("%Y-%m-%d")
    parts = []
    for ds in (config.ELIA_HIST_NEW_DATASET, config.ELIA_NRT_DATASET):
        try:
            parts.append(elia.fetch_new_schema(ds, start))
        except Exception as e:  # noqa: BLE001 - one source down must not stop the run
            print(f"  {ds} unavailable: {e}")
    return elia.to_hourly(elia.merge_sources(parts))


def _mw(x) -> float | None:
    return None if x is None or (isinstance(x, float) and np.isnan(x)) else round(float(x), 1)


def issue_forecast(now: pd.Timestamp, elia_hourly: pd.DataFrame, log: dict, force: bool = False) -> str | None:
    target = (now.tz_convert(TZ).normalize() + pd.Timedelta(days=1))
    key = target.strftime("%Y-%m-%d")
    if key in log and not force:
        print(f"  forecast for {key} already issued at {log[key]['issued_at_utc']} (immutable)")
        return None
    start, end = target.tz_convert("UTC"), (target + pd.Timedelta(days=1)).tz_convert("UTC")

    nwp = weather.fetch_live(forecast_days=3, past_days=1)
    X = features.build_features(nwp, features.capacity_weights(elia_hourly))
    df = features.add_target(X, elia_hourly)
    da = prices.fetch_day_ahead((now - pd.Timedelta(days=4)).strftime("%Y-%m-%d"), now.strftime("%Y-%m-%d"))
    df = features.add_market_features(df, da)
    day = df[(df.index >= start) & (df.index < end)]
    if len(day) < 23:
        raise RuntimeError(f"only {len(day)} hourly rows available for {key}")

    use_hybrid = day.loc[day["elevation"] > -2, "elia_da11_cf"].notna().all()
    if not use_hybrid and now.hour < FALLBACK_FROM_UTC_HOUR and not force:
        print(f"  Elia's 11h forecast for {key} not published yet; waiting for a later slot")
        return None
    name = "lead1_hybrid" if use_hybrid else "lead1_penumbra"
    model = QuantileForecaster.load(config.MODELS_DIR, name)
    q = model.predict(day).mul(day["capacity_ex_ante"], axis=0)

    hours = [{
        "t": t.isoformat(), "q10": _mw(q.loc[t, "q10"]), "q50": _mw(q.loc[t, "q50"]), "q90": _mw(q.loc[t, "q90"]),
        "elia_da11": _mw(day.loc[t, "elia_da11"]), "elia_p10": _mw(day.loc[t, "elia_da11_p10"]),
        "elia_p90": _mw(day.loc[t, "elia_da11_p90"]), "elev": round(float(day.loc[t, "elevation"]), 1),
    } for t in day.index]
    log[key] = {
        "target_date": key, "issued_at_utc": now.strftime("%Y-%m-%dT%H:%M:%SZ"), "model": name,
        "capacity_mw": _mw(day["capacity_ex_ante"].iloc[0]), "hours": hours,
        "energy_mwh": {"q50": round(float(q["q50"].sum()), 0),
                       "elia_da11": round(float(day["elia_da11"].sum()), 0) if use_hybrid else None},
    }
    print(f"  issued {key} with {name}: {log[key]['energy_mwh']}")
    return key


def score_past(log: dict, elia_hourly: pd.DataFrame, today_local: pd.Timestamp) -> None:
    be = elia_hourly[elia_hourly["region"] == "Belgium"].set_index("time")["measured"]
    for key, rec in log.items():
        if rec.get("score", {}).get("complete") or pd.Timestamp(key, tz=TZ) >= today_local:
            continue
        rows = []
        for h in rec["hours"]:
            t = pd.Timestamp(h["t"])
            h["actual"] = _mw(be.get(t, np.nan))
            if h["elev"] > -2:
                rows.append(h)
        have = [h for h in rows if h["actual"] is not None]
        if not have:
            continue
        a = np.array([h["actual"] for h in have])
        p = np.array([h["q50"] for h in have])
        lo, hi = np.array([h["q10"] for h in have]), np.array([h["q90"] for h in have])
        sc = {"complete": len(have) == len(rows), "n_hours": len(have),
              "mae_penumbra_mw": round(float(np.mean(np.abs(p - a))), 1),
              "coverage_80": round(float(np.mean((a >= lo) & (a <= hi))), 3),
              "energy_actual_mwh": round(float(a.sum()), 0)}
        e = [h["elia_da11"] for h in have]
        if all(v is not None for v in e):
            sc["mae_elia_da11_mw"] = round(float(np.mean(np.abs(np.array(e) - a))), 1)
        rec["score"] = sc


def summarise(log: dict) -> dict:
    scored = [r for r in log.values() if r.get("score", {}).get("complete")]
    both = [r for r in scored if "mae_elia_da11_mw" in r["score"]]
    out = {"n_days_scored": len(scored), "n_days_issued": len(log)}
    if both:
        mp = float(np.mean([r["score"]["mae_penumbra_mw"] for r in both]))
        me = float(np.mean([r["score"]["mae_elia_da11_mw"] for r in both]))
        out |= {"mae_penumbra_mw": round(mp, 1), "mae_elia_da11_mw": round(me, 1),
                "skill_vs_elia_pct": round(100 * (1 - mp / me), 1),
                "coverage_80": round(float(np.mean([r["score"]["coverage_80"] for r in scored])), 3),
                "days_better_than_elia": sum(r["score"]["mae_penumbra_mw"] < r["score"]["mae_elia_da11_mw"] for r in both)}
    return out


def run(now: pd.Timestamp | None = None, force: bool = False) -> dict:
    now = now or pd.Timestamp.now("UTC")
    LIVE_DIR.mkdir(parents=True, exist_ok=True)
    log = _load_log()
    elia_hourly = _recent_elia(now)
    issued = issue_forecast(now, elia_hourly, log, force=force)
    score_past(log, elia_hourly, now.tz_convert(TZ).normalize())
    log = dict(sorted(log.items()))
    LOG_PATH.write_text(json.dumps(log, indent=None, separators=(",", ":")))
    latest = log[max(log)] if log else None
    summary = {"updated_at_utc": now.strftime("%Y-%m-%dT%H:%M:%SZ"), "issued_now": issued,
               "latest": latest, "track_record": summarise(log),
               "days": [{"date": k, "issued_at_utc": v["issued_at_utc"], "model": v["model"], **v.get("score", {})}
                        for k, v in log.items()]}
    SUMMARY_PATH.write_text(json.dumps(summary, indent=None, separators=(",", ":")))
    return summary
