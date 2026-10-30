"""Download additional archived NWP models (DMI HARMONIE, ECCC GEM, ECMWF AIFS) for both leads."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import pandas as pd
from penumbra import config, weather

EXTRA = {"dmi": "dmi_seamless", "gem": "gem_seamless", "aifs": "ecmwf_aifs025_single"}
end = sys.argv[1] if len(sys.argv) > 1 else pd.Timestamp.now("UTC").strftime("%Y-%m-%d")
for lead in (2, 1):
    wx = weather.fetch_previous_runs(config.START, end, lead=lead, models=EXTRA)
    wx.to_parquet(config.DATA_RAW / f"nwp_lead{lead}_extra.parquet", index=False)
    print("saved", lead, len(wx), flush=True)
