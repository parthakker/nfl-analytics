"""Invariants for v_redzone_usage_week — per player-week red zone usage
derived straight from pbp (yardline_100 <= 20, pass/run plays, attributed to
coalesce(rusher_id, receiver_id))."""

import pytest

pytestmark = pytest.mark.warehouse


def test_grain_keys_non_null_and_unique(warehouse_conn):
    bad = warehouse_conn.execute("""
        SELECT count(*) FROM v_redzone_usage_week
        WHERE season IS NULL OR week IS NULL OR team IS NULL OR player_id IS NULL
    """).fetchone()[0]
    assert bad == 0
    dups = warehouse_conn.execute("""
        SELECT count(*) FROM (
            SELECT season, week, team, player_id
            FROM v_redzone_usage_week
            GROUP BY ALL HAVING count(*) > 1)
    """).fetchone()[0]
    assert dups == 0


def test_counts_non_negative_and_bounded(warehouse_conn):
    """Every source play carries a rusher or receiver, so each row must have
    at least one touch and can never show more TDs than touches."""
    bad = warehouse_conn.execute("""
        SELECT count(*) FROM v_redzone_usage_week
        WHERE rz_carries < 0 OR rz_targets < 0 OR rz_tds < 0
           OR rz_carries + rz_targets = 0
           OR rz_tds > rz_carries + rz_targets
    """).fetchone()[0]
    assert bad == 0


def test_usage_share_within_unit_interval(warehouse_conn):
    """A player's share of his team-week red zone touches is a rate in [0, 1]."""
    bad = warehouse_conn.execute("""
        WITH tot AS (
            SELECT season, week, team,
                   sum(rz_carries + rz_targets) AS team_touches
            FROM v_redzone_usage_week GROUP BY ALL)
        SELECT count(*)
        FROM v_redzone_usage_week v JOIN tot USING (season, week, team)
        WHERE (v.rz_carries + v.rz_targets) / tot.team_touches::double
              NOT BETWEEN 0 AND 1
    """).fetchone()[0]
    assert bad == 0


def test_seasons_track_pbp_coverage(warehouse_conn, max_season):
    """Pure pbp derivative: every pbp season has red zone plays, so the view's
    season span must equal pbp's — a shrunk span means a broken filter."""
    lo, hi = warehouse_conn.execute(
        "SELECT min(season), max(season) FROM v_redzone_usage_week"
    ).fetchone()
    if lo is None:
        pytest.skip("empty slice")
    assert lo >= 1999
    assert hi <= max_season
    pbp_lo, pbp_hi = warehouse_conn.execute(
        "SELECT min(season), max(season) FROM play_by_play"
    ).fetchone()
    assert (lo, hi) == (pbp_lo, pbp_hi)
