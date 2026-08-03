import pytest

pytestmark = pytest.mark.warehouse


def test_player_weekly_no_season_gaps(warehouse_conn):
    """The 2024→2025 v2 seam must not leave a hole in the compat view."""
    seasons = [r[0] for r in warehouse_conn.execute("""
        SELECT DISTINCT season FROM v_player_stats_week_all ORDER BY season
    """).fetchall()]
    if not seasons:
        pytest.skip("no player stats in this DB slice")
    expected = list(range(min(seasons), max(seasons) + 1))
    assert seasons == expected, f"gaps: {sorted(set(expected) - set(seasons))}"


def test_games_no_season_gaps(warehouse_conn):
    seasons = [r[0] for r in warehouse_conn.execute(
        "SELECT DISTINCT season FROM games ORDER BY season").fetchall()]
    expected = list(range(min(seasons), max(seasons) + 1))
    assert seasons == expected


def test_half_ppr_identity(warehouse_conn):
    """fantasy_points_half_ppr must sit exactly between standard and PPR."""
    bad = warehouse_conn.execute("""
        SELECT count(*) FROM v_player_stats_week_all
        WHERE fantasy_points IS NOT NULL AND fantasy_points_ppr IS NOT NULL
          AND abs(fantasy_points_half_ppr - (fantasy_points + fantasy_points_ppr) / 2) > 0.01
    """).fetchone()[0]
    assert bad == 0
