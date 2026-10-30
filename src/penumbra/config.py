"""Static configuration: data sources, regions, NWP models and the evaluation protocol."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA_RAW = ROOT / "data" / "raw"
DATA_PROCESSED = ROOT / "data" / "processed"
SITE_DATA = ROOT / "site" / "data"
MODELS_DIR = ROOT / "models"

# --- Elia Open Data (Belgian TSO), Elia Open Data Licence -----------------------------
ELIA_API = "https://opendata.elia.be/api/explore/v2.1/catalog/datasets"
ELIA_HIST_DATASET = "ods032"      # 15-min PV estimate + forecasts, 2020-10 .. 2026-10-26
ELIA_HIST_NEW_DATASET = "ods209"  # same measure, new schema, from 2026-10-26 onwards
ELIA_NRT_DATASET = "ods210"       # near real-time (rolling window incl. next days' forecasts)
ELIA_IMBALANCE_DATASET = "ods134"  # quarter-hour imbalance prices since 2024-05-22

# Belgian provinces: (name in ods032, name in ods209/ods210, approx. centroid lat, lon)
PROVINCES = [
    ("Antwerp", "Antwerpen", 51.20, 4.65),
    ("Limburg", "Limburg", 50.98, 5.40),
    ("East-Flanders", "OostVlaanderen", 51.03, 3.80),
    ("West-Flanders", "WestVlaanderen", 51.03, 3.05),
    ("Flemish-Brabant", "VlaamsBrabant", 50.88, 4.60),
    ("Brussels", "Brussel", 50.84, 4.37),
    ("Walloon-Brabant", "BrabantWallon", 50.67, 4.58),
    ("Hainaut", "Hainaut", 50.48, 3.95),
    ("Namur", "Namur", 50.32, 4.85),
    ("Liège", "Liege", 50.52, 5.65),
    ("Luxembourg", "Luxembourg", 49.96, 5.48),
]
PROVINCE_KEYS = [p[0] for p in PROVINCES]
NEW_TO_OLD_REGION = {p[1]: p[0] for p in PROVINCES} | {"Belgium": "Belgium"}

# Belgium centroid, used for solar geometry of the national fleet
BE_LAT, BE_LON = 50.64, 4.67

# --- Open-Meteo NWP archive (Previous Runs API) and live Forecast API ----------------
OPENMETEO_PREVIOUS_RUNS = "https://previous-runs-api.open-meteo.com/v1/forecast"
OPENMETEO_FORECAST = "https://api.open-meteo.com/v1/forecast"
NWP_MODELS = {
    "icon": "icon_seamless",          # DWD ICON (EU/D2 nests)
    "gfs": "gfs_seamless",            # NOAA GFS
    "mf": "meteofrance_seamless",     # Météo-France ARPEGE/AROME
    "ecmwf": "ecmwf_ifs025",          # ECMWF IFS 0.25°
    "knmi": "knmi_seamless",          # KNMI HARMONIE-AROME
    "dmi": "dmi_seamless",            # DMI HARMONIE (DINI domain)
    "gem": "gem_seamless",            # ECCC GEM (Canada)
    "aifs": "ecmwf_aifs025_single",   # ECMWF AIFS: machine-learned global model (archive from 2025-03)
}
# Models with a complete archive since START -> used for multi-model mean/spread features.
# AIFS enters only through its own per-model features (LightGBM handles its earlier gap).
ENSEMBLE_MODELS = ["icon", "gfs", "mf", "ecmwf", "knmi", "dmi", "gem"]
NWP_VARS = ["shortwave_radiation", "direct_radiation", "cloud_cover", "temperature_2m"]

# --- Evaluation protocol -----------------------------------------------------------------
# All archived NWP models are complete from this date (ECMWF/KNMI archive starts ~2024-03/04).
START = "2024-04-01"
# First month evaluated out-of-sample; every later month is predicted by a model trained
# only on data strictly before that month (expanding-window, rolling-origin backtest).
FIRST_TEST_MONTH = "2025-04"
QUANTILES = (0.1, 0.5, 0.9)
NOMINAL_COVERAGE = 0.8
