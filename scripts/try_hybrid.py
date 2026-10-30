"""Developer helper: compare hybrid formulations (direct vs residual) on an existing table."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import numpy as np, pandas as pd
from penumbra import backtest
from penumbra.features import model_feature_columns
from penumbra.model import QuantileForecaster, daylight

lead = int(sys.argv[1])
df = pd.read_parquet(f"data/processed/table_lead{lead}.parquet")
df = df[df["cf"].notna() & df["ghi_ens"].notna()]
feats = model_feature_columns(df, with_elia=True)
res = {"direct": [], "residual": [], "elia": []}
for month in backtest.test_months(df):
    nxt = month + pd.offsets.MonthBegin(1)
    test = df[(df.index >= month) & (df.index < nxt) & daylight(df)]
    test = test[test["elia_da11_cf"].notna()]
    hist = df[(df.index < month) & daylight(df) & df["elia_da11_cf"].notna()]
    cut = month - pd.Timedelta(days=60)
    for name, base in (("direct", None), ("residual", "elia_da11_cf")):
        m = QuantileForecaster(feats, base=base).fit(hist[hist.index < cut], hist[hist.index >= cut])
        p = m.predict(test)
        res[name].append(pd.DataFrame({"y": test["cf"], "q10": p["q10"], "q50": p["q50"], "q90": p["q90"]}))
    res["elia"].append(pd.DataFrame({"y": test["cf"], "q10": test["elia_da11_p10_cf"], "q50": test["elia_da11_cf"], "q90": test["elia_da11_p90_cf"]}))
for k, v in res.items():
    d = pd.concat(v)
    w = (d.q90 - d.q10); cov = ((d.y >= d.q10) & (d.y <= d.q90)).mean()
    wink = (w + 10 * ((d.q10 - d.y).clip(lower=0) + (d.y - d.q90).clip(lower=0))).mean()
    print(f"{k:9s} nMAE={100*np.mean(np.abs(d.q50-d.y)):.3f} cov={100*cov:.1f} width={100*w.mean():.2f} winkler={100*wink:.2f}")
