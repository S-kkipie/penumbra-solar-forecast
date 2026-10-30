"""Developer helper: rebuild one lead's table, run the backtest and print headline metrics."""
import sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import pandas as pd
from penumbra import backtest, dataset, evaluate

lead = int(sys.argv[1]) if len(sys.argv) > 1 else 2
abl = "--abl" in sys.argv
t = time.time()
df = dataset.build_table(lead)
df.to_parquet(f"data/processed/table_lead{lead}.parquet")
pred = backtest.run(df, ablations=abl, verbose=False)
pred.to_parquet(f"data/processed/backtest_lead{lead}.parquet")
rep = evaluate.full_report(pred)
pt = pd.DataFrame(rep["point"]).set_index("key")
print(pt[["nMAE_pct_cap", "nRMSE_pct_cap", "bias_pct_cap", "MAE_MW", "skill_vs_elia_da11_pct", "skill_rmse_vs_elia_da11_pct"]].round(3).to_string())
print(pd.DataFrame(rep["interval"]).set_index("key").drop(columns="method").round(3).to_string())
s = rep["significance"]
print({k: (round(v["dm_stat"], 2), round(v["p_value"], 4)) for k, v in s.items() if "elia" in k})
print(rep.get("ablations"))
print(f"{time.time() - t:.0f}s")
