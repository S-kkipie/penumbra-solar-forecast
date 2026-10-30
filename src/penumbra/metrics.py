"""Deterministic, probabilistic and statistical-significance metrics."""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats


def mae(y, p) -> float:
    return float(np.mean(np.abs(np.asarray(y) - np.asarray(p))))


def rmse(y, p) -> float:
    return float(np.sqrt(np.mean((np.asarray(y) - np.asarray(p)) ** 2)))


def bias(y, p) -> float:
    return float(np.mean(np.asarray(p) - np.asarray(y)))


def pinball(y, q, tau: float) -> float:
    y, q = np.asarray(y), np.asarray(q)
    d = y - q
    return float(np.mean(np.maximum(tau * d, (tau - 1) * d)))


def interval_scores(y, lo, hi, alpha: float = 0.2) -> dict[str, float]:
    """Coverage, mean width and Winkler (interval) score of a central (1-alpha) band."""
    y, lo, hi = map(np.asarray, (y, lo, hi))
    width = hi - lo
    below, above = y < lo, y > hi
    winkler = width + (2 / alpha) * ((lo - y) * below + (y - hi) * above)
    return {"coverage": float(np.mean(~below & ~above)), "width": float(np.mean(width)),
            "winkler": float(np.mean(winkler))}


def skill(score_model: float, score_ref: float) -> float:
    """Skill score in % (positive = better than reference)."""
    return float(100 * (1 - score_model / score_ref))


def diebold_mariano(err_a, err_b, index: pd.DatetimeIndex, power: int = 1) -> dict[str, float]:
    """DM test on daily-aggregated loss differentials (|e|^power), HAC variance (Newey-West).

    Aggregating to days removes intra-day autocorrelation; the Newey-West lag handles
    weather persistence across days. Negative statistic => model A has lower loss.
    """
    d = pd.Series(np.abs(err_a) ** power - np.abs(err_b) ** power, index=index)
    daily = d.groupby(index.floor("D")).mean().dropna().to_numpy()
    n = len(daily)
    dbar = daily.mean()
    lag = int(np.floor(n ** (1 / 3)))
    dc = daily - dbar
    gamma0 = np.dot(dc, dc) / n
    var = gamma0 + 2 * sum((1 - k / (lag + 1)) * np.dot(dc[k:], dc[:-k]) / n for k in range(1, lag + 1))
    stat = dbar / np.sqrt(var / n)
    return {"dm_stat": float(stat), "p_value": float(2 * stats.norm.sf(abs(stat))), "n_days": n}


def block_bootstrap_ci(err_a, err_b, index: pd.DatetimeIndex, n_boot: int = 2000, block_days: int = 7,
                       seed: int = 0) -> tuple[float, float]:
    """95 % CI of MAE(A) - MAE(B) by moving-block bootstrap over days."""
    d = pd.Series(np.abs(err_a) - np.abs(err_b), index=index)
    daily = d.groupby(index.floor("D")).agg(["sum", "count"])
    s, c = daily["sum"].to_numpy(), daily["count"].to_numpy()
    n = len(s)
    rng = np.random.default_rng(seed)
    n_blocks = int(np.ceil(n / block_days))
    out = np.empty(n_boot)
    for b in range(n_boot):
        starts = rng.integers(0, n - block_days + 1, n_blocks)
        idx = (starts[:, None] + np.arange(block_days)).ravel()[:n]
        out[b] = s[idx].sum() / c[idx].sum()
    return float(np.percentile(out, 2.5)), float(np.percentile(out, 97.5))
