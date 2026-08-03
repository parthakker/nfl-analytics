"""`nfl` — one front door for every maintenance script.

The scripts in scripts/ remain the source of truth (Task Scheduler points at
them directly); this dispatcher just forwards, so `nfl refresh --full` and
`python scripts/refresh_data.py --full` are identical.
"""

import argparse
import runpy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent

COMMANDS = {
    "refresh": (
        "scripts/refresh_data.py",
        "Download nflverse data + rebuild (--full, --bootstrap, --no-rebuild)",
    ),
    "rebuild": ("scripts/build_warehouse.py", "Rebuild raw tables from data/"),
    "views": ("scripts/build_views.py", "Rebuild derived views + sanity checks"),
    "audit": ("scripts/data_audit.py", "Data completeness audit -> docs/data_audit.md"),
    "smoke": ("scripts/smoke_test.py", "Hit every API endpoint, require real data"),
    "weather": ("scripts/fetch_weather.py", "Open-Meteo forecasts (--backfill for history)"),
    "train": ("scripts/train_model.py", "Train + validate the (paused) prediction model"),
    "news": ("scripts/poll_news.py", "One news poll cycle -> news.duckdb"),
    "kalshi": ("scripts/snapshot_kalshi.py", "One Kalshi snapshot -> kalshi.duckdb"),
    "fixture": ("scripts/make_fixture.py", "Build tests/fixtures/*.duckdb from the real DBs"),
}


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="nfl",
        description="NFL analytics warehouse maintenance",
        epilog="Extra arguments are passed through to the underlying script.",
    )
    sub = parser.add_subparsers(dest="command", metavar="command")
    for name, (_, help_text) in COMMANDS.items():
        s = sub.add_parser(name, help=help_text, add_help=False)
        s.add_argument("rest", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return 2
    script = ROOT / COMMANDS[args.command][0]
    sys.argv = [str(script), *args.rest]
    try:
        runpy.run_path(str(script), run_name="__main__")
    except SystemExit as e:
        return int(e.code or 0)
    return 0


if __name__ == "__main__":
    sys.exit(main())
