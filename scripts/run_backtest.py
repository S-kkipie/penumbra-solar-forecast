"""Build the modelling tables, run the rolling-origin backtest for both NWP lead settings,
score everything and train the final models.

    python scripts/run_backtest.py
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pandas as pd  # noqa: E402

from penumbra import backtest, config, dataset, evaluate  # noqa: E402
from penumbra.features import model_feature_columns  # noqa: E402
from penumbra.model import QuantileForecaster, daylight  # noqa: E402

REPORTS = config.ROOT / "reports"


def train_final(df: pd.DataFrame, name: str, with_elia: bool) -> QuantileForecaster:
    """Production model: all history, last 60 days held out for conformal calibration."""
    d = df[df["cf"].notna() & df["ghi_ens"].notna() & daylight(df)]
    if with_elia:
        d = d[d["elia_da11_cf"].notna()]
    cut = d.index.max() - pd.Timedelta(days=backtest.CALIB_DAYS)
    f = QuantileForecaster(model_feature_columns(d, with_elia=with_elia), base="elia_da11_cf" if with_elia else None)
    f.fit(d[d.index < cut], d[d.index >= cut])
    f.save(config.MODELS_DIR, name)
    return f


def main() -> None:
    REPORTS.mkdir(exist_ok=True)
    config.DATA_PROCESSED.mkdir(parents=True, exist_ok=True)
    elia_hourly = dataset.load_elia_hourly()
    summary = {}
    for lead in (2, 1):
        t0 = time.time()
        print(f"== lead {lead}: building table")
        df = dataset.build_table(lead, elia_hourly)
        df.to_parquet(config.DATA_PROCESSED / f"table_lead{lead}.parquet")
        if lead == 2:
            (REPORTS / "data_quality.json").write_text(json.dumps(dataset.quality_report(df), indent=1))
        print(f"== lead {lead}: backtest ({len(df):,} hours)")
        pred = backtest.run(df, ablations=(lead == 2))
        pred.to_parquet(config.DATA_PROCESSED / f"backtest_lead{lead}.parquet")
        report = evaluate.full_report(pred)
        (REPORTS / f"metrics_lead{lead}.json").write_text(json.dumps(report, indent=1, default=float))
        pt = pd.DataFrame(report["point"]).set_index("key")
        print(pt[["method", "nMAE_pct_cap", "nRMSE_pct_cap", "MAE_MW", "skill_vs_elia_da11_pct"]].round(3).to_string())
        print(pd.DataFrame(report["interval"]).set_index("key").round(3).to_string())
        summary[f"lead{lead}"] = {"seconds": round(time.time() - t0, 1)}

        pen = train_final(df, f"lead{lead}_penumbra", with_elia=False)
        train_final(df, f"lead{lead}_hybrid", with_elia=True)
        imp = pen.feature_importance()
        (REPORTS / f"feature_importance_lead{lead}.json").write_text(imp.round(5).to_json(indent=1))
    (REPORTS / "run_summary.json").write_text(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
