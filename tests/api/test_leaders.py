"""Contract + regression tests for the family-based leaders API."""

import pytest

pytestmark = pytest.mark.api

FAMILIES = ["passing", "rushing", "receiving", "fantasy", "defense", "kicking"]


@pytest.mark.parametrize("family", FAMILIES)
def test_family_shape(client, family):
    d = client.get(f"/api/leaders?family={family}").json()
    assert set(d) >= {
        "family",
        "season",
        "season_type",
        "sort",
        "dir",
        "label",
        "qual",
        "qual_key",
        "limit",
        "seasons",
        "total_players",
        "qualified",
        "columns",
        "league_avg",
        "p10",
        "p90",
        "rows",
    }
    assert d["rows"], f"{family}: no rows"
    ids = [r["player_id"] for r in d["rows"]]
    assert len(ids) == len(set(ids)), "duplicate player_id in leaderboard"
    col_keys = {c["key"] for c in d["columns"]}
    for r in d["rows"][:3]:
        assert {"player_id", "player", "team", "games", "headshot"} <= set(r)
        assert col_keys <= set(r), "columns spec not subset of row keys"
        assert 0 < r["games"] <= 25


def test_position_filter(client):
    d = client.get("/api/leaders?family=fantasy&position=RB").json()
    assert d["rows"] and all(r["pos"] == "RB" for r in d["rows"])


def test_qual_semantics(client):
    lo = client.get("/api/leaders?family=passing&qual=0").json()
    hi = client.get("/api/leaders?family=passing&qual=200").json()
    assert hi["qualified"] < lo["qualified"]
    assert len(hi["rows"]) <= hi["qualified"]
    assert isinstance(hi["league_avg"].get("pass_yds"), (int, float))
    assert isinstance(hi["p90"].get("ypa"), (int, float))


def test_post_smaller_than_reg(client):
    reg = client.get("/api/leaders?family=rushing&season_type=REG").json()
    post = client.get("/api/leaders?family=rushing&season_type=POST").json()
    assert post["total_players"] <= reg["total_players"]


@pytest.mark.parametrize(
    "path",
    [
        "/api/leaders?family=bogus",
        "/api/leaders?family=passing&sort=drop_table",
        "/api/leaders?family=passing&season_type=BOTH",
        "/api/leaders?family=passing&position=DL",
        "/api/leaders?family=passing&dir=sideways",
        "/api/leaders?limit=30",
    ],
)
def test_bad_params_400(client, path):
    assert client.get(path).status_code == 400


def test_adrian_peterson_regression(client):
    """Two distinct 2007 Adrian Petersons must be two rows (the group-by-name
    bug credited CHI with a 30-game season)."""
    d = client.get("/api/leaders?family=rushing&season=2007&limit=100").json()
    if 2007 not in d["seasons"]:
        pytest.skip("2007 not in this DB slice (fixture)")
    aps = [r for r in d["rows"] if r["player"] == "Adrian Peterson"]
    assert len(aps) == 2
    assert len({r["player_id"] for r in aps}) == 2
    assert sorted(r["games"] for r in aps) == [14, 16]
    assert all(r["games"] < 30 for r in d["rows"])
    minn = next(r for r in aps if r["rush_yds"] == 1341)
    assert minn["team"] == "MIN"


def test_columns_carry_help_text(client):
    d = client.get("/api/leaders?family=fantasy").json()
    assert all(c.get("help") for c in d["columns"])


def test_position_aware_columns(client):
    qb = client.get("/api/leaders?family=fantasy&position=QB").json()
    qb_keys = [c["key"] for c in qb["columns"]]
    assert "pass_yds" in qb_keys and "tgt" not in qb_keys
    db = client.get("/api/leaders?family=defense&position=DB").json()
    assert [c["key"] for c in db["columns"]][1:3] == ["ints", "pd"]
    overall = client.get("/api/leaders?family=fantasy").json()
    assert [c["key"] for c in overall["columns"]][1] == "std"  # standard order


def test_games_never_exceed_weeks(client, max_season):
    d = client.get(f"/api/leaders?family=fantasy&season={max_season}&limit=100").json()
    assert all(r["games"] <= 22 for r in d["rows"])
