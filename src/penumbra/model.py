"""Penumbra forecaster: multi-NWP gradient-boosted quantile regression + Mondrian conformal calibration.

* Target: capacity factor (measured MW / installed MW known ex ante), daylight hours only.
* Three LightGBM quantile models (P10, P50, P90) with monotone non-crossing post-processing.
* Split-conformal quantile regression (CQR, Romano et al. 2019), applied separately per
  solar-elevation regime ("Mondrian"), so the 80 % band is calibrated at dawn/dusk as
  well as at noon instead of only on average.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd

from . import config

LGB_PARAMS = dict(
    n_estimators=700, learning_rate=0.03, num_leaves=31, min_child_samples=40,
    subsample=0.8, subsample_freq=1, colsample_bytree=0.8, reg_lambda=1.0, verbose=-1,
)
ELEVATION_BINS = [-90, 10, 25, 90]   # low sun / mid / high sun regimes for Mondrian CQR
DAYLIGHT_MIN_ELEVATION = -2.0


def daylight(df: pd.DataFrame) -> pd.Series:
    return df["elevation"] > DAYLIGHT_MIN_ELEVATION


@dataclass
class QuantileForecaster:
    features: list[str]
    quantiles: tuple[float, ...] = config.QUANTILES
    alpha: float = 1 - config.NOMINAL_COVERAGE
    base: str | None = None  # if set, learn quantiles of (cf - base): residual correction of a reference forecast
    models: dict[float, lgb.Booster] = field(default_factory=dict)
    cqr_offsets: dict[int, float] = field(default_factory=dict)

    def fit(self, train: pd.DataFrame, calib: pd.DataFrame | None = None) -> "QuantileForecaster":
        X, y = train[self.features], train["cf"].clip(0, 1.2)
        if self.base:
            y = y - train[self.base]
        for q in self.quantiles:
            m = lgb.LGBMRegressor(objective="quantile", alpha=q, **LGB_PARAMS)
            m.fit(X, y)
            self.models[q] = m.booster_
        if calib is not None and len(calib):
            self._calibrate(calib)
        return self

    def _raw(self, df: pd.DataFrame) -> pd.DataFrame:
        X = df[self.features].astype(float)
        pred = np.column_stack([self.models[q].predict(X) for q in self.quantiles])
        if self.base:
            pred = pred + df[self.base].to_numpy()[:, None]
        pred = np.sort(pred, axis=1).clip(0, None)  # non-crossing quantiles, non-negative output
        return pd.DataFrame(pred, index=df.index, columns=[f"q{int(q * 100)}" for q in self.quantiles])

    def _regime(self, df: pd.DataFrame) -> np.ndarray:
        return np.digitize(df["elevation"].to_numpy(), ELEVATION_BINS[1:-1])

    def _calibrate(self, calib: pd.DataFrame) -> None:
        raw = self._raw(calib)
        y = calib["cf"].to_numpy()
        lo, hi = raw.iloc[:, 0].to_numpy(), raw.iloc[:, -1].to_numpy()
        scores = np.maximum(lo - y, y - hi)
        regime = self._regime(calib)
        for r in np.unique(regime):
            s = scores[regime == r]
            n = len(s)
            level = min(1.0, np.ceil((n + 1) * (1 - self.alpha)) / n)
            self.cqr_offsets[int(r)] = float(np.quantile(s, level, method="higher"))

    def predict(self, df: pd.DataFrame) -> pd.DataFrame:
        out = self._raw(df)
        lo_col, hi_col = out.columns[0], out.columns[-1]
        if self.cqr_offsets:
            off = pd.Series(self._regime(df), index=df.index).map(self.cqr_offsets).fillna(0).to_numpy()
            out[lo_col] = (out[lo_col] - off).clip(lower=0)
            out[hi_col] = out[hi_col] + off
        mid = out.columns[len(out.columns) // 2]
        out[lo_col] = np.minimum(out[lo_col], out[mid])
        out[hi_col] = np.maximum(out[hi_col], out[mid])
        night = ~daylight(df)
        out.loc[night, :] = 0.0
        return out

    def feature_importance(self) -> pd.Series:
        b = self.models[0.5]
        imp = pd.Series(b.feature_importance(importance_type="gain"), index=self.features)
        return (imp / imp.sum()).sort_values(ascending=False)

    def save(self, directory: Path, name: str) -> None:
        directory.mkdir(parents=True, exist_ok=True)
        for q, b in self.models.items():
            b.save_model(str(directory / f"{name}_q{int(q * 100)}.txt"))
        meta = {"features": self.features, "quantiles": list(self.quantiles), "alpha": self.alpha, "base": self.base,
                "cqr_offsets": {str(k): v for k, v in self.cqr_offsets.items()}}
        (directory / f"{name}_meta.json").write_text(json.dumps(meta, indent=1))

    @classmethod
    def load(cls, directory: Path, name: str) -> "QuantileForecaster":
        meta = json.loads((directory / f"{name}_meta.json").read_text())
        obj = cls(meta["features"], tuple(meta["quantiles"]), meta["alpha"], meta.get("base"))
        obj.models = {q: lgb.Booster(model_file=str(directory / f"{name}_q{int(q * 100)}.txt")) for q in obj.quantiles}
        obj.cqr_offsets = {int(k): v for k, v in meta["cqr_offsets"].items()}
        return obj


def fit_linear_baseline(train: pd.DataFrame):
    """'Physics + regression' baseline: CF ~ a*GHI_ens + b*GHI_ens*cos(zenith) + c."""
    tr = train[daylight(train)]
    A = np.column_stack([tr["ghi_ens"], tr["ghi_ens"] * tr["cos_zenith"], np.ones(len(tr))])
    coef, *_ = np.linalg.lstsq(A, tr["cf"].to_numpy(), rcond=None)

    def predict(df: pd.DataFrame) -> np.ndarray:
        B = np.column_stack([df["ghi_ens"], df["ghi_ens"] * df["cos_zenith"], np.ones(len(df))])
        return np.where(daylight(df), (B @ coef).clip(0, None), 0.0)

    return predict


def climatology(train: pd.DataFrame):
    """Mean capacity factor per (month, UTC hour) from training data."""
    key = [train.index.month, train.index.hour]
    table = train.groupby(key)["cf"].mean()

    def predict(df: pd.DataFrame) -> np.ndarray:
        idx = pd.MultiIndex.from_arrays([df.index.month, df.index.hour])
        return table.reindex(idx).fillna(0).to_numpy()

    return predict
