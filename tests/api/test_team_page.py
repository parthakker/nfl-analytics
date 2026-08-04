"""Contract tests for the team page endpoints (overview/results/roster)."""

import pytest

pytestmark = pytest.mark.api


@pytest.fixture(scope="module")
def ov(client):
    r = client.get("/api/teams/KC/overview")
    assert r.status_code == 200
    return r.json()


def test_overview_shape(ov):
    assert set(ov) >= {
        "code",
        "season",
        "division",
        "div_rank",
        "header",
        "staff",
        "leaders",
        "standings",
        "epa",
        "travel",
        "franchise",
        "injuries",
    }
    assert ov["division"] == "AFC West"
    assert 1 <= ov["div_rank"] <= 4
    assert ov["staff"]["head_coach"] and ov["staff"]["oc"]["name"]
    assert ov["staff"]["offense_scheme"]["knowledge"]


def test_overview_leaders(ov):
    assert len(ov["leaders"]) == 5
    for ld in ov["leaders"]:
        assert ld.get("player_id") and ld.get("name") and ld.get("value", 0) > 0


def test_overview_standings_and_epa(ov):
    assert len(ov["standings"]) == 4
    assert any(r["team"] == "KC" for r in ov["standings"])
    if ov["epa"]:
        for k in ("off_rank", "def_rank", "pass_rank", "rush_rank"):
            assert 1 <= ov["epa"][k] <= 32


def test_overview_franchise(ov):
    assert ov["franchise"], "franchise strip empty"
    for f in ov["franchise"]:
        assert f["w"] + f["l"] + f["t"] >= 16 or f["season"] >= 2021  # 16/17-game eras


def test_tb_staff_special_case(client):
    d = client.get("/api/teams/TB/overview").json()
    assert d["staff"]["dc"] is None
    assert d["staff"]["oc"]["name"]


def test_results_record_to_date_invariant(client):
    d = client.get("/api/teams/PIT/results?season=2016").json()
    reg = [r for r in d["rows"] if r["season_type"] == "REG"]
    last = reg[-1]
    assert (last["w_td"], last["l_td"]) == (d["summary"]["w"], d["summary"]["l"])
    # monotonic cumulative records
    for a, b in zip(reg, reg[1:], strict=False):
        assert b["w_td"] >= a["w_td"] and b["l_td"] >= a["l_td"]
    assert all(r["game_id"] for r in d["rows"])


def test_results_ats_consistency(client):
    d = client.get("/api/teams/KC/results?season=2024").json()
    covered = sum(1 for r in d["rows"] if r["covered"] is True)
    assert covered == d["summary"]["ats_w"]


def test_roster_historical(client):
    d = client.get("/api/teams/PIT/roster?season=2016").json()
    if 2016 not in d.get("seasons", []):
        pytest.skip("2016 rosters not in this DB slice (fixture)")
    names = {p["name"] for p in d["players"]}
    assert "Antonio Brown" in names
    ab = next(p for p in d["players"] if p["name"] == "Antonio Brown")
    assert ab["gsis"]
    assert d["seasons"] and min(d["seasons"]) <= 2005


def test_unknown_team_404(client):
    assert client.get("/api/teams/NOPE/overview").status_code == 404
    assert client.get("/api/teams/NOPE/results").status_code == 404
