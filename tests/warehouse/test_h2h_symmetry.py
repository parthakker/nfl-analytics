import pytest

pytestmark = pytest.mark.warehouse


def test_wlt_sums_to_games(warehouse_conn):
    n = warehouse_conn.execute(
        "SELECT count(*) FROM v_team_matchups WHERE wins + losses + ties != games"
    ).fetchone()[0]
    assert n == 0


def test_mirror_symmetry(warehouse_conn):
    bad = warehouse_conn.execute("""
        SELECT count(*) FROM v_team_matchups a
        JOIN v_team_matchups b ON a.team = b.opponent AND a.opponent = b.team
        WHERE a.games != b.games OR a.wins != b.losses
    """).fetchone()[0]
    assert bad == 0


def test_every_pair_has_mirror(warehouse_conn):
    orphans = warehouse_conn.execute("""
        SELECT count(*) FROM v_team_matchups a
        LEFT JOIN v_team_matchups b ON a.team = b.opponent AND a.opponent = b.team
        WHERE b.team IS NULL
    """).fetchone()[0]
    assert orphans == 0


def test_matchup_games_two_rows_per_game(warehouse_conn):
    bad = warehouse_conn.execute("""
        SELECT count(*) FROM (
            SELECT game_id, count(*) c FROM v_matchup_games GROUP BY game_id
            HAVING c != 2)
    """).fetchone()[0]
    assert bad == 0
