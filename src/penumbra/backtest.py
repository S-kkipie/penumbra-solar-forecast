"""Expanding-window, rolling-origin backtest (one model refit per test month).

For test month M every model is trained only on hours < M - 60 days, conformally
calibrated on [M - 60 days, M) and then frozen for the whole month. Nothing from month M
or later (targets, NWP, capacities) is ever seen during fitting.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import config
from .features import model_feature_columns
from .model import QuantileForecaster, climatology, daylight, fit_linear_baseline

CALIB_DAYS = 60


def test_months(df: pd.DataFrame) -> list[pd.Timestamp]:
    last = df.index.max().floor("D")
    return list(pd.date_range(pd.Timestamp(config.FIRST_TEST_MONTH + "-01", tz="UTC"), last, freq="MS"))


def run(df: pd.DataFrame, ablations: bool = False, verbose: bool = True) -> pd.DataFrame:
    df = df[df["cf"].notna() & df["ghi_ens"].notna()].copy()
    feats = model_feature_columns(df)
    feats_hybrid = model_feature_columns(df, with_elia=True)
    ablation_sets = {}
    if ablations:
        ablation_sets = {
            "abl_icon_only": _single_model_features(feats, "icon"),
            "abl_ecmwf_only": _single_model_features(feats, "ecmwf"),
            "abl_no_ai_model": [c for c in feats if not c.endswith("_aifs")],
            "abl_no_market_feats": [c for c in feats if c not in {"da_price_d1", "neg_hours_d1", "offday"}],
            "abl_no_uncertainty_feats": [c for c in feats if c not in
                                         {"ghi_ens_std", "kt_ens_std", "kt_ens_range", "cc_ens_std", "kt_spatial_std"}],
        }

    # Smart persistence: measured capacity factor 48 h earlier (D-2), last full day known at D-1 11:00.
    cf_series = df["cf"]
    persistence = cf_series.reindex(df.index - pd.Timedelta(hours=48)).to_numpy()

    rows = []
    for month in test_months(df):
        nxt = month + pd.offsets.MonthBegin(1)
        test = df[(df.index >= month) & (df.index < nxt)]
        if test.empty:
            continue
        hist = df[df.index < month]
        hist_day = hist[daylight(hist)]
        cut = month - pd.Timedelta(days=CALIB_DAYS)
        fit_set, calib_set = hist_day[hist_day.index < cut], hist_day[hist_day.index >= cut]

        out = pd.DataFrame(index=test.index)
        out["y"] = test["cf"]
        out["capacity"] = test["capacity_ex_ante"]
        out["measured"] = test["measured"]
        out["elevation"] = test["elevation"]
        out["kt_ens"] = test["kt_ens"]
        out["elia_da11"] = test["elia_da11_cf"]
        out["elia_da11_p10"] = test["elia_da11_p10_cf"]
        out["elia_da11_p90"] = test["elia_da11_p90_cf"]
        out["elia_da"] = test["elia_da_cf"]
        out["persistence"] = persistence[df.index.get_indexer(test.index)]
        out["climatology"] = climatology(hist)(test)
        out["linear_nwp"] = fit_linear_baseline(hist)(test)

        pen = QuantileForecaster(feats).fit(fit_set, calib_set)
        p = pen.predict(test)
        out[["pen_q10", "pen_q50", "pen_q90"]] = p.to_numpy()

        fit_h = fit_set[fit_set["elia_da11_cf"].notna()]
        cal_h = calib_set[calib_set["elia_da11_cf"].notna()]
        hyb = QuantileForecaster(feats_hybrid, base="elia_da11_cf").fit(fit_h, cal_h)
        ph = hyb.predict(test)
        out[["hyb_q10", "hyb_q50", "hyb_q90"]] = ph.to_numpy()

        for name, cols in ablation_sets.items():
            m = QuantileForecaster(cols, quantiles=(0.5,)).fit(fit_set)
            out[name] = m.predict(test).iloc[:, 0].to_numpy()

        out["test_month"] = month.strftime("%Y-%m")
        rows.append(out)
        if verbose:
            day = daylight(test)
            e_p = np.abs(out.loc[day, "pen_q50"] - out.loc[day, "y"]).mean()
            e_h = np.abs(out.loc[day, "hyb_q50"] - out.loc[day, "y"]).mean()
            e_e = np.abs(out.loc[day, "elia_da11"] - out.loc[day, "y"]).mean()
            print(f"  {month:%Y-%m}  train={len(fit_set):5d} calib={len(calib_set):4d}  "
                  f"MAE(cf) penumbra={e_p:.4f} hybrid={e_h:.4f} elia_da11={e_e:.4f}")
    return pd.concat(rows)


def _single_model_features(feats: list[str], model: str) -> list[str]:
    keep = []
    for c in feats:
        suffix = c.split("_")[-1]
        if suffix in config.NWP_MODELS:
            if suffix == model:
                keep.append(c)
        elif c in {"ghi_ens", "ghi_ens_std", "kt_ens", "kt_ens_std", "kt_ens_range", "cc_ens", "cc_ens_std",
                   "t2m_ens", "kt_spatial_std", "poa_s35", "poa_ew", "pr_trail", "da_price_d1", "neg_hours_d1", "offday"}:
            continue
        else:
            keep.append(c)
    return keep
