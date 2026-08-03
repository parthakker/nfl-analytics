import pytest

pytestmark = pytest.mark.warehouse


def test_all_games_resolve_to_a_venue(warehouse_conn):
    n = warehouse_conn.execute(
        "SELECT count(*) FROM game_venues WHERE venue_id IS NULL").fetchone()[0]
    assert n == 0, "unresolved venues — add aliases/overrides to data/stadiums.json"


def test_2025_international_overrides_hold(warehouse_conn):
    """nflverse recorded home US stadiums for the 2025 internationals; the
    game_overrides in stadiums.json pin the real venues. Regression-guard the
    Dublin one."""
    row = warehouse_conn.execute("""
        SELECT venue_id, venue_country FROM game_venues
        WHERE game_id = '2025_04_MIN_PIT'""").fetchone()
    if row is None:
        pytest.skip("2025_04_MIN_PIT not in this DB slice")
    assert row[0] == "IRE00" and row[1] == "Ireland"


def test_neutral_games_flagged(warehouse_conn):
    n = warehouse_conn.execute("""
        SELECT count(*) FROM game_venues gv JOIN schedules s USING (game_id)
        WHERE s.location = 'Neutral' AND NOT gv.neutral_site""").fetchone()[0]
    assert n == 0


def test_alias_map_has_no_dangling_venues(warehouse_conn):
    n = warehouse_conn.execute("""
        SELECT count(*) FROM stadium_aliases a
        LEFT JOIN stadiums s ON s.venue_id = a.venue_id
        WHERE s.venue_id IS NULL""").fetchone()[0]
    assert n == 0
