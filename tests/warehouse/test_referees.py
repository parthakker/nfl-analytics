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
    lo = warehouse_conn.execute("SELECT min(season) FROM v_referee_games").fetchone()[0]
    assert lo < 2015


def test_every_game_has_a_ref(warehouse_conn):
    """Within the seasons pbp covers, virtually every game gets a head ref."""
    floor = _pbp_floor(warehouse_conn)
    total = warehouse_conn.execute(
        "SELECT count(*) FROM games WHERE season >= ?", [floor]
    ).fetchone()[0]
    reffed = warehouse_conn.execute("SELECT count(*) FROM v_referee_games").fetchone()[0]
    assert reffed / total > 0.99


def test_ref_key_never_null(warehouse_conn):
    n = warehouse_conn.execute(
        "SELECT count(*) FROM v_referee_games WHERE ref_key IS NULL"
    ).fetchone()[0]
    assert n == 0


def test_one_row_per_referee_not_per_id(warehouse_conn):
    """Regression: ref_key used to be official_id, which is NULL before 2015
    and was REISSUED by nflverse in 2023. That split one human into several
    rows — Ed Hochuli appeared twice (256 games 1999-2014 and 50 games
    2015-2017) and Jerome Boger showed up twice on the Refs page. The key is
    now the canonical name, so each referee is exactly one row."""
    dupes = warehouse_conn.execute("""
        SELECT upper(trim(official_name)) AS nm, count(DISTINCT ref_key) AS keys
        FROM v_referee_games GROUP BY 1 HAVING keys > 1
    """).fetchall()
    assert dupes == [], f"referee spread across multiple keys: {dupes}"

    # A key MAY cover two spellings (Brad / Bradley Rogers) — but only when
    # nflverse itself says they are one person, i.e. they share an official_id.
    # Anything else would be two humans merged into one row.
    merged = warehouse_conn.execute("""
        SELECT ref_key FROM v_referee_games
        WHERE official_id IS NOT NULL
        GROUP BY 1 HAVING count(DISTINCT upper(trim(official_name)))
                       > count(DISTINCT official_id)
                     AND count(DISTINCT official_id) > 1
    """).fetchall()
    assert merged == [], f"distinct officials merged under one key: {merged}"


def test_ref_career_survives_the_2015_seam(warehouse_conn):
    """A referee who worked either side of the officials-table floor must have
    ONE row spanning both eras, not one per source."""
    if _pbp_floor(warehouse_conn) >= 2015:
        pytest.skip("pbp slice starts post-2015 (fixture DB)")
    spans = warehouse_conn.execute("""
        SELECT count(*) FROM (
            SELECT ref_key FROM v_referee_games
            GROUP BY 1 HAVING min(season) < 2015 AND max(season) >= 2015)
    """).fetchone()[0]
    assert spans > 0, "no referee career crosses 2015 — the keys are still split"


def test_team_splits_two_teams_per_ref_game(warehouse_conn):
    """v_referee_team_splits explodes each ref-game to both teams — totals
    must be exactly 2x."""
    a = warehouse_conn.execute("SELECT sum(games) FROM v_referee_team_splits").fetchone()[0]
    b = warehouse_conn.execute("SELECT count(*) FROM v_referee_games").fetchone()[0]
    assert a == 2 * b
