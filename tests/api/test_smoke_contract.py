"""The scripts/smoke_test.py CHECKS, run in-process via TestClient (no server).

The smoke script stays the scheduler's live-HTTP tripwire; this port catches
the same regressions at development time. Checks that depend on live/current
data (kalshi snapshots, news feeds) are relaxed under the fixture DB.
"""

import os

import pytest

from tests.helpers import load_smoke_checks

pytestmark = pytest.mark.api

CHECKS = load_smoke_checks()

# under the trimmed fixture DBs these predicates are too strict — presence of
# the key with ANY list is enough there
FIXTURE_RELAXED = {
    "/api/referees?min_games=100",  # one-season slice: nobody reaches 100 games
    "/api/markets?kind=game",
    "/api/betting/board?week=1",
    "/api/news?limit=5",
    "/api/news/search?q=injury",
    "/api/news?category=injury&limit=5",
    "/api/teams/DET/news",
}
ON_FIXTURE = os.environ.get("NFL_TEST_USE_FIXTURE") == "1"


@pytest.mark.parametrize("path", sorted(CHECKS))
def test_endpoint(client, path):
    r = client.get(path)
    assert r.status_code == 200, f"{path}: HTTP {r.status_code} {r.text[:120]}"
    js = r.json()
    if ON_FIXTURE and path in FIXTURE_RELAXED:
        assert isinstance(js, dict) and js, f"{path}: empty payload"
    else:
        assert CHECKS[path](js), f"{path}: data check failed: {r.text[:160]}"
