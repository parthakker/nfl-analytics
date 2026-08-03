"""Poll ESPN news + injuries into news.duckdb. Safe to run any time.

Run:  python scripts/poll_news.py
Scheduled every 6h by Task Scheduler (see CLAUDE.md / Automation).
"""

import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from nfl_analytics.news import poll  # noqa: E402


def main() -> int:
    try:
        res = poll()
        line = (f"{datetime.now().isoformat()} news poll: "
                f"fetched={res['fetched']} new={res['new_rows']} "
                f"total={res['stored_total']} "
                f"gsis_matched={res['tags_resolved_to_gsis']}/{res['player_tags']}")
        rc = 0
    except Exception as e:
        line = f"{datetime.now().isoformat()} news poll FAILED: {e}"
        rc = 1
    print(line)
    logs = ROOT / "logs"
    logs.mkdir(exist_ok=True)
    with open(logs / "news.log", "a", encoding="utf-8") as f:
        f.write(line + "\n")
    return rc


if __name__ == "__main__":
    sys.exit(main())
