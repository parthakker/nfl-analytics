"""Invariants for the cross-era defense/kicking compat views."""

import pytest

pytestmark = pytest.mark.warehouse


def _seasons(con, view):
    return [
        r[0] for r in con.execute(f"SELECT DISTINCT season FROM {view} ORDER BY season").fetchall()
    ]


@pytest.mark.parametrize("view", ["v_player_stats_def_week_all", "v_player_stats_kicking_week_all"])
def test_no_season_gaps(warehouse_conn, view):
    seasons = _seasons(warehouse_conn, view)
    if not seasons:
        pytest.skip("empty slice")
    assert seasons == list(range(min(seasons), max(seasons) + 1))


def test_v1_tackles_identity(warehouse_conn):
    """def_tackles == solo + with_assist held on 100% of v1 rows when the view
    was built — regression-guard it."""
    bad = warehouse_conn.execute("""
        SELECT count(*) FROM player_stats_def_week
        WHERE def_tackles IS NOT NULL
          AND def_tackles != coalesce(def_tackles_solo,0) + coalesce(def_tackles_with_assist,0)
    """).fetchone()[0]
    assert bad == 0


def test_v2_row_explosion_guard(warehouse_conn):
    """The v2 arm filters out rostered-but-inactive players; if that filter
    regresses, the latest season balloons."""
    sizes = dict(
        warehouse_conn.execute("""
        SELECT season, count(*) FROM v_player_stats_def_week_all
        GROUP BY season ORDER BY season DESC LIMIT 2
    """).fetchall()
    )
    if len(sizes) < 2:
        pytest.skip("need two seasons")
    (s_new, n_new), (s_prev, n_prev) = sorted(sizes.items(), reverse=True)
    assert n_new < 3 * n_prev, f"{s_new} has {n_new} rows vs {s_prev} {n_prev}"


def test_no_negative_defense_stats(warehouse_conn):
    bad = warehouse_conn.execute("""
        SELECT count(*) FROM v_player_stats_def_week_all
        WHERE def_tackles < 0 OR def_sacks < 0 OR def_interceptions < 0
    """).fetchone()[0]
    assert bad == 0


def test_kicking_made_lte_att(warehouse_conn):
    bad = warehouse_conn.execute("""
        SELECT count(*) FROM v_player_stats_kicking_week_all
        WHERE fg_made > fg_att OR pat_made > pat_att
    """).fetchone()[0]
    assert bad == 0
