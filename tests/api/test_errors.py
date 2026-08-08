from pathlib import Path

import pytest

pytestmark = pytest.mark.api


@pytest.mark.parametrize(
    "path",
    [
        "/api/matchup/2024_99_XXX_YYY",
        "/api/matchup/h2h/KC/NOPE",
        "/api/knowledge/not-a-chapter",
        "/api/knowledge/..%2F..%2Fsecrets",
        "/api/teams/NOPE",
        "/api/coaches/Zzz%20Nobody",
        "/api/referees/999999",
    ],
)
def test_unknowns_are_404(client, path):
    assert client.get(path).status_code == 404


def test_h2h_rejects_bad_params(client):
    assert client.get("/api/matchup/h2h/KC/LV?season_type=BOTH").status_code == 400
    assert client.get("/api/matchup/h2h/KC/LV?site=moon").status_code == 400


def test_leaders_rejects_unknown_family(client):
    r = client.get("/api/leaders?family=definitely_not_a_family")
    assert r.status_code == 400


def test_news_missing_store_is_clean_503(client, monkeypatch):
    # db.read_conn skips the ATTACH when the file is absent, so the newsdb
    # query fails — that must be a clean 503, never a raw traceback
    import nfl_analytics.db as db

    monkeypatch.setattr(db, "NEWS_DB", Path("definitely_missing.duckdb"))
    r = client.get("/api/news")
    assert r.status_code == 503
    assert r.json() == {"items": [], "error": "news store unavailable"}
