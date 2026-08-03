"""Test bootstrap. ORDER MATTERS: DB env vars must be set before anything
imports nfl_analytics.config (module-level Path constants).

Tiers:
  unit/      — no database, always runs
  warehouse/ — @pytest.mark.warehouse, needs nfl.duckdb (real or fixture)
  api/       — @pytest.mark.api, TestClient over the FastAPI app (needs DB)

Locally the real DBs at the repo root are used (that's the point — invariant
tests validate the actual warehouse). CI sets NFL_TEST_USE_FIXTURE=1 to run
against the committed fixtures in tests/fixtures/.
"""

import os
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"

if os.environ.get("NFL_TEST_USE_FIXTURE") == "1":
    os.environ["NFL_DB"] = str(FIXTURE_DIR / "nfl_fixture.duckdb")
    os.environ["KALSHI_DB"] = str(FIXTURE_DIR / "kalshi_fixture.duckdb")
    os.environ["NEWS_DB"] = str(FIXTURE_DIR / "news_fixture.duckdb")

sys.path.insert(0, str(REPO_ROOT))          # for `import web.api.main`
sys.path.insert(0, str(REPO_ROOT / "src"))  # for `import nfl_analytics`


def _nfl_db_path() -> Path:
    from nfl_analytics import config
    return config.NFL_DB


def pytest_collection_modifyitems(config, items):
    if _nfl_db_path().exists():
        return
    skip = pytest.mark.skip(reason=f"no warehouse at {_nfl_db_path()} "
                                   "(set NFL_TEST_USE_FIXTURE=1 or build the DB)")
    for item in items:
        if "warehouse" in item.keywords or "api" in item.keywords:
            item.add_marker(skip)


@pytest.fixture(scope="session")
def warehouse_conn():
    import duckdb
    con = duckdb.connect(str(_nfl_db_path()), read_only=True)
    yield con
    con.close()


@pytest.fixture(scope="session")
def client():
    from fastapi.testclient import TestClient
    from web.api.main import app
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="session")
def max_season(warehouse_conn) -> int:
    """Latest completed-data season — use instead of hardcoding 2025."""
    return warehouse_conn.execute(
        "SELECT max(season) FROM games").fetchone()[0]
