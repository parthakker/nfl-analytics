"""Snapshot all open Kalshi NFL markets into kalshi.duckdb.

Run:  python scripts/snapshot_kalshi.py
Scheduled every 6h by Task Scheduler (see CLAUDE.md / Automation).
"""

import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from nfl_analytics.kalshi import snapshot  # noqa: E402


def main() -> int:
    try:
        res = snapshot()
        line = (f"{datetime.now().isoformat()} kalshi snapshot: "
                f"markets={res['markets_snapshotted']} "
                f"total_rows={res['snapshot_rows_total']}")
        rc = 0
    except Exception as e:
        line = f"{datetime.now().isoformat()} kalshi snapshot FAILED: {e}"
        rc = 1
    print(line)
    logs = ROOT / "logs"
    logs.mkdir(exist_ok=True)
    with open(logs / "kalshi.log", "a", encoding="utf-8") as f:
        f.write(line + "\n")
    return rc


if __name__ == "__main__":
    sys.exit(main())
