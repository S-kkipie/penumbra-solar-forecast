import numpy as np
import pandas as pd
import pytest

from penumbra import backtest, features, metrics
from penumbra.model import QuantileForecaster


def test_pinball_is_half_mae_at_median():
    y = np.array([0.0, 1.0, 2.0, 3.0])
    q = np.array([1.0, 1.0, 1.0, 1.0])
    assert metrics.pinball(y, q, 0.5) == pytest.approx(0.5 * metrics.mae(y, q))


def test_interval_scores_coverage_and_winkler():
    s = metrics.interval_scores([0.5, 2.0], [0.0, 0.0], [1.0, 1.0], alpha=0.2)
    assert s["coverage"] == 0.5
    assert s["width"] == 1.0
    # second point misses by 1.0 -> penalty 2/0.2 * 1 = 10
    assert s["winkler"] == pytest.approx((1 + 11) / 2)


def test_diebold_mariano_detects_better_model():
    idx = pd.date_range("2025-01-01", periods=24 * 120, freq="h", tz="UTC")
    rng = np.random.default_rng(0)
    good, bad = rng.normal(0, 1, len(idx)), rng.normal(0, 2, len(idx))
    res = metrics.diebold_mariano(good, bad, idx)
    assert res["dm_stat"] < 0 and res["p_value"] < 1e-6


def test_radiation_is_relabelled_to_interval_start():
    t = pd.date_range("2025-06-01", periods=3, freq="h", tz="UTC")
    nwp = pd.DataFrame({"model": "icon", "province": "Brussels", "time": t,
                        "shortwave_radiation": [10.0, 20.0, 30.0], "direct_radiation": [1.0, 2.0, 3.0],
                        "cloud_cover": [0.0, 50.0, 100.0], "temperature_2m": [10.0, 12.0, 14.0]})
    out = features.align_nwp(nwp)
    # interval [00:00, 01:00) takes the radiation labelled 01:00 (mean over the preceding hour)
    assert out.loc[0, "shortwave_radiation"] == 20.0
    assert out.loc[0, "cloud_cover"] == 25.0


def test_solar_geometry_is_physical():
    t = pd.DatetimeIndex(["2025-06-21 11:00", "2025-12-21 11:00", "2025-06-21 23:00"], tz="UTC")
    g = features.solar_geometry(t)
    assert g["elevation"].iloc[0] > 60          # midsummer noon in Belgium ~62.6 deg
    assert 10 < g["elevation"].iloc[1] < 18     # midwinter noon ~16 deg
    assert g["ghi_cs"].iloc[2] == 0             # night


def _synthetic_table(days=500, seed=1):
    idx = pd.date_range("2024-04-01", periods=24 * days, freq="h", tz="UTC")
    geo = features.solar_geometry(idx)
    rng = np.random.default_rng(seed)
    kt = rng.uniform(0.1, 1.0, len(idx))
    df = geo.copy()
    df["ghi_ens"] = geo["ghi_cs"] * kt
    df["kt_ens"] = kt
    df["cf"] = (0.0009 * df["ghi_ens"] + rng.normal(0, 0.02, len(idx))).clip(0)
    return df


def test_quantile_forecaster_is_calibrated_on_synthetic_data():
    df = _synthetic_table()
    day = df[df["elevation"] > -2]
    tr, cal, te = day.iloc[:4000], day.iloc[4000:5500], day.iloc[5500:]
    f = QuantileForecaster(["elevation", "ghi_cs", "ghi_ens", "kt_ens"]).fit(tr, cal)
    p = f.predict(te)
    cov = ((te["cf"] >= p["q10"]) & (te["cf"] <= p["q90"])).mean()
    assert 0.72 < cov < 0.9
    assert (p["q10"] <= p["q50"]).all() and (p["q50"] <= p["q90"]).all()


def test_backtest_never_trains_on_test_month(monkeypatch):
    seen = []
    orig_fit = QuantileForecaster.fit

    def spy(self, train, calib=None):
        seen.append((train.index.max(), None if calib is None else calib.index.max()))
        return orig_fit(self, train, calib)

    monkeypatch.setattr(QuantileForecaster, "fit", spy)
    df = _synthetic_table(days=430)
    for c in ["capacity_ex_ante", "measured"]:
        df[c] = 1.0
    for c in ["elia_da11_cf", "elia_da11_p10_cf", "elia_da11_p90_cf", "elia_da_cf"]:
        df[c] = df["cf"]
    monkeypatch.setattr(backtest.config, "FIRST_TEST_MONTH", "2025-05")
    pred = backtest.run(df, verbose=False)
    months = sorted(pred["test_month"].unique())
    assert months
    for (train_max, calib_max), month in zip(seen[::2], months):
        start = pd.Timestamp(month + "-01", tz="UTC")
        assert train_max < start - pd.Timedelta(days=backtest.CALIB_DAYS)
        assert calib_max < start


def test_market_features_only_use_previous_delivery_day():
    t = pd.date_range("2025-06-01", "2025-06-04", freq="h", tz="UTC", inclusive="left")
    prices = pd.DataFrame({"time": t, "da_price": np.where(t.day == 2, -10.0, 50.0)})
    df = pd.DataFrame(index=t)
    out = features.add_market_features(df, prices)
    local = out.index.tz_convert("Europe/Brussels")
    # Local day June 3 must see the negative hours of local June 2 (whose UTC hours are all on June 2,
    # except the first two, which fall on June 1 22:00/23:00 UTC with positive prices).
    june3 = out[(local.day == 3) & (local.hour == 12)]
    assert june3["neg_hours_d1"].iloc[0] == 22
    assert june3["da_price_d1"].iloc[0] == -10.0
    # Nothing from the target day itself is used: local June 2 sees June 1 prices (all positive).
    june2 = out[(local.day == 2) & (local.hour == 12)]
    assert june2["neg_hours_d1"].iloc[0] == 0
