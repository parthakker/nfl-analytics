"""Central paths and settings. Env vars > .env file > defaults."""

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent

# load .env once, without overriding real env vars
_env_file = ROOT / ".env"
if _env_file.exists():
    for line in _env_file.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())

NFL_DB = Path(os.environ.get("NFL_DB", ROOT / "nfl.duckdb"))
KALSHI_DB = Path(os.environ.get("KALSHI_DB", ROOT / "kalshi.duckdb"))
NEWS_DB = Path(os.environ.get("NEWS_DB", ROOT / "news.duckdb"))
DATA_DIR = ROOT / "data"
LOGS_DIR = ROOT / "logs"
DOCS_DIR = ROOT / "docs"

KALSHI_API = "https://external-api.kalshi.com/trade-api/v2"
SLEEPER_API = "https://api.sleeper.app/v1"
SLEEPER_LEAGUE_ID = os.environ.get("SLEEPER_LEAGUE_ID", "")

NFLVERSE_RELEASE = "https://github.com/nflverse/nflverse-data/releases/download"
NFLDATA_GAMES_URL = "https://github.com/nflverse/nfldata/raw/master/data/games.csv"

