"""Travel invariants — a typo'd stadium coordinate silently corrupts every
travel number, so known distances are pinned here (mirrors build_views'
inline sanity check, but runs on every pytest)."""

import pytest

pytestmark = pytest.mark.warehouse


def _one(con, sql):
    row = con.execute(sql).fetchone()
    return row[0] if row else None


def test_buf_to_sofi(warehouse_conn):
    d = _one(warehouse_conn, """
        SELECT travel_miles FROM v_team_games
        WHERE team='BUF' AND venue_id='LAX01' AND NOT is_home LIMIT 1""")
    if d is None:
        pytest.skip("no BUF@SoFi game in this DB slice")
    assert 2100 <= d <= 2300


def test_shared_stadium_is_zero(warehouse_conn):
    d = _one(warehouse_conn, """
        SELECT max(travel_miles) FROM v_team_games
        WHERE team='NYG' AND opponent='NYJ' AND NOT is_home""")
    if d is None:
        pytest.skip("no NYG@NYJ game in this DB slice")
    assert d < 20


def test_no_negative_or_absurd_distances(warehouse_conn):
    bad = _one(warehouse_conn, """
        SELECT count(*) FROM v_team_games
        WHERE travel_miles < 0 OR travel_miles > 12000""")
    assert bad == 0


def test_home_games_near_zero_travel(warehouse_conn):
    """Non-neutral home games should be ~0 miles (same venue), allowing
    interim-venue seasons a little slack."""
    p95 = _one(warehouse_conn, """
        SELECT quantile_cont(travel_miles, 0.95) FROM v_team_games
        WHERE is_home AND NOT neutral_site""")
    assert p95 is not None and p95 <= 30


def test_stadium_coords_plausible(warehouse_conn):
    bad = _one(warehouse_conn, """
        SELECT count(*) FROM stadiums
        WHERE (country = 'USA' AND (lat NOT BETWEEN 24 AND 65 OR lon NOT BETWEEN -160 AND -66))
           OR lat IS NULL OR lon IS NULL""")
    assert bad == 0
