"""Regression guards for CLAUDE.md gotcha #1: season tables mix REG, POST and
combined REG+POST rows — any consumer that forgets to filter double-counts."""

import pytest

pytestmark = pytest.mark.warehouse


def test_player_season_has_the_three_types(warehouse_conn):
    types = {r[0] for r in warehouse_conn.execute(
        "SELECT DISTINCT season_type FROM player_stats_season").fetchall()}
    assert "REG" in types and "REG+POST" in types


def test_weekly_view_never_has_combined_rows(warehouse_conn):
    """v_player_stats_week_all is weekly grain — a REG+POST row appearing here
    would mean the v2 union regressed."""
    n = warehouse_conn.execute("""
        SELECT count(*) FROM v_player_stats_week_all
        WHERE season_type NOT IN ('REG', 'POST')""").fetchone()[0]
    assert n == 0


def test_v2_seam_no_overlap(warehouse_conn):
    """Old tables stop at 2024, v2 starts at 2025 — overlap would double-count
    in the compat view."""
    overlap = warehouse_conn.execute("""
        SELECT count(*) FROM (
            SELECT season FROM player_stats_week WHERE season >= 2025
            UNION ALL
            SELECT season FROM player_stats_week_v2 WHERE season <= 2024)
    """).fetchone()[0]
    assert overlap == 0
