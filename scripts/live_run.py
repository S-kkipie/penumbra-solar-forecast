"""Daily job (GitHub Actions): issue tomorrow's forecast, score past days, refresh dashboard data.

    python scripts/live_run.py [--force]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from penumbra import live  # noqa: E402

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true", help="re-issue tomorrow even if already logged")
    s = live.run(force=ap.parse_args().force)
    print(json.dumps(s["track_record"], indent=1))
