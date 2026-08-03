import pytest

pytestmark = pytest.mark.warehouse


def _pbp_floor(con) -> int:
    return con.execute("SELECT min(season) FROM play_by_play").fetchone()[0]


def test_ref_coverage_spans_pre_2015(warehouse_conn):
    """schedules.referee coalesce extends head-ref data below the officials
    floor (2015). Only checkable when the DB carries pre-2015 pbp (the CI
    fixture is sliced to recent seasons)."""
    if _pbp_floor(warehouse_conn) >= 2015:
        pytest.skip("pbp slice starts post-2015 (fixture DB)")
    lo = warehouse_conn.execute(
        "SELECT min(season) FROM v_referee_games").fetchone()[0]
    assert lo < 2015


def test_every_game_has_a_ref(warehouse_conn):
    """Within the seasons pbp covers, virtually every game gets a head ref."""
    floor = _pbp_floor(warehouse_conn)
    total = warehouse_conn.execute(
        "SELECT count(*) FROM games WHERE season >= ?", [floor]).fetchone()[0]
    reffed = warehouse_conn.execute("SELECT count(*) FROM v_referee_games").fetchone()[0]
    assert reffed / total > 0.99


def test_ref_key_never_null(warehouse_conn):
    n = warehouse_conn.execute(
        "SELECT count(*) FROM v_referee_games WHERE ref_key IS NULL").fetchone()[0]
    assert n == 0


def test_team_splits_two_teams_per_ref_game(warehouse_conn):
    """v_referee_team_splits explodes each ref-game to both teams — totals
    must be exactly 2x."""
    a = warehouse_conn.execute(
        "SELECT sum(games) FROM v_referee_team_splits").fetchone()[0]
    b = warehouse_conn.execute("SELECT count(*) FROM v_referee_games").fetchone()[0]
    assert a == 2 * b
