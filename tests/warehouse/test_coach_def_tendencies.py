"""Invariants for v_coach_def_tendencies — coach x season defensive rates
from pbp (pass/run plays, coach resolved from games.home/away_coach by
defteam).

The view applies NO attempt minimums (an interim coach with a handful of
games appears), so the bounds below are wide enough for small samples but
still catch a broken join or a rate computed on the wrong denominator.
Real-DB extremes observed at build time: sack_rate <= .105, takeaway_rate
<= .048, run_stuff_rate .10-.35, |EPA/play| < .51.
"""

import pytest

pytestmark = pytest.mark.warehouse


def test_grain_coach_season_unique_and_non_null(warehouse_conn):
    nulls = warehouse_conn.execute("""
        SELECT count(*) FROM v_coach_def_tendencies
        WHERE coach IS NULL OR season IS NULL
    """).fetchone()[0]
    assert nulls == 0
    dups = warehouse_conn.execute("""
        SELECT count(*) FROM (
            SELECT coach, season FROM v_coach_def_tendencies
            GROUP BY ALL HAVING count(*) > 1)
    """).fetchone()[0]
    assert dups == 0


def test_rates_within_plausible_bounds(warehouse_conn):
    bad = warehouse_conn.execute("""
        SELECT count(*) FROM v_coach_def_tendencies
        WHERE sack_rate NOT BETWEEN 0 AND 0.25
           OR takeaway_rate NOT BETWEEN 0 AND 0.2
           OR run_stuff_rate NOT BETWEEN 0 AND 0.6
           OR def_pass_epa NOT BETWEEN -1 AND 1
           OR def_rush_epa NOT BETWEEN -1 AND 1
    """).fetchone()[0]
    assert bad == 0


def test_league_mean_def_pass_epa_sane(warehouse_conn):
    """Averaged over all coaches in a season, allowed pass EPA/play must sit
    near the league passing rate (slightly positive in the modern era) — a
    sign flip or an offense/defense mixup lands far outside this band."""
    bad = warehouse_conn.execute("""
        SELECT count(*) FROM (
            SELECT season, avg(def_pass_epa) AS m
            FROM v_coach_def_tendencies GROUP BY season)
        WHERE m NOT BETWEEN -0.15 AND 0.25
    """).fetchone()[0]
    assert bad == 0


def test_every_season_has_full_coach_slate(warehouse_conn, max_season):
    """Each season should show roughly one defensive line per team (31 teams
    1999-2001, 32 after, plus interim splits)."""
    lo, hi, min_coaches = warehouse_conn.execute("""
        SELECT min(season), max(season), min(c) FROM (
            SELECT season, count(DISTINCT coach) AS c
            FROM v_coach_def_tendencies GROUP BY season)
    """).fetchone()
    if lo is None:
        pytest.skip("empty slice")
    assert lo >= 1999
    assert hi <= max_season
    assert min_coaches >= 30
