"""Response-shape contracts for the matchup/h2h/knowledge endpoints — the UI
type interfaces depend on these keys existing."""

import pytest

pytestmark = pytest.mark.api


@pytest.fixture(scope="module")
def any_final_game(client, max_season):
    r = client.get(f"/api/schedule?season={max_season}")
    games = [g for g in r.json()["games"] if g["away_score"] is not None]
    if not games:
        pytest.skip("no completed games in DB slice")
    return games[0]["game_id"]


def test_matchup_shape(client, any_final_game):
    d = client.get(f"/api/matchup/{any_final_game}").json()
    assert set(d) >= {
        "game",
        "venue",
        "teams",
        "coach_h2h",
        "referee",
        "weather",
        "market",
        "injuries",
        "series",
    }
    for side in ("away", "home"):
        t = d["teams"][side]
        assert set(t) >= {
            "code",
            "record",
            "rest_days",
            "travel_miles",
            "tz_shift_hours",
            "form_last5",
            "epa",
        }
        assert set(t["record"]) == {"w", "l", "t"}
    assert d["game"]["final"] is True


def test_h2h_shape_and_filters(client):
    d = client.get("/api/matchup/h2h/KC/LV").json()
    assert set(d) >= {"teams", "summary", "streak", "splits", "games"}
    assert d["summary"]["games"] == len(d["games"])
    post = client.get("/api/matchup/h2h/KC/LV?season_type=POST").json()
    assert post["summary"]["games"] <= d["summary"]["games"]
    assert all(g["season_type"] == "POST" for g in post["games"])


def test_h2h_relocation_merge(client):
    """OAK-era games must appear under LV (canon_team)."""
    d = client.get("/api/matchup/h2h/KC/LV").json()
    assert d["summary"]["first_season"] <= 2019  # predates the Vegas move


def test_knowledge_chapter_navigation(client):
    chapters = client.get("/api/knowledge").json()["chapters"]
    assert len(chapters) >= 10
    first = client.get(f"/api/knowledge/{chapters[0]['slug']}").json()
    assert first["prev"] is None and first["next"]["slug"] == chapters[1]["slug"]
    assert first["markdown"].lstrip().startswith("#")
