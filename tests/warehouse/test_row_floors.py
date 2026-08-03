"""Row-count floors per table. A bad nflverse drop or refresh should trip
these before anything downstream notices. Floors are deliberately below the
fixture's trimmed counts so both real and fixture DBs pass."""

import pytest

pytestmark = pytest.mark.warehouse

FLOORS = {
    "games": 500,
    "schedules": 500,
    "play_by_play": 40_000,  # >= one full season (fixture carries exactly one)
    "players": 3_000,  # fixture filters to ids present in sliced stats
    "stadiums": 60,
    "game_venues": 500,
    "team_home_venues": 60,
    "game_weather_parsed": 200,  # >= ~one season of weather strings
}


@pytest.mark.parametrize("table,floor", sorted(FLOORS.items()))
def test_floor(warehouse_conn, table, floor):
    n = warehouse_conn.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
    assert n >= floor, f"{table}: {n} rows < floor {floor}"


def test_pbp_no_tiny_seasons(warehouse_conn):
    bad = warehouse_conn.execute("""
        SELECT season, count(*) FROM play_by_play
        GROUP BY season HAVING count(*) < 40000 ORDER BY season
    """).fetchall()
    assert not bad, f"suspiciously small pbp seasons: {bad}"
