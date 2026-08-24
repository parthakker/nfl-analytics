"""Invariants for the betting-rules facts frames against the real warehouse
(or the CI fixture — sliced tables make some checks skip themselves)."""

import pytest

from nfl_analytics import rules as R

pytestmark = pytest.mark.warehouse


@pytest.fixture(scope="module")
def hist(warehouse_conn):
    return R.build_facts_history(warehouse_conn)


def test_row_count_matches_completed_schedules(warehouse_conn, hist):
    n = warehouse_conn.execute(
        "SELECT count(*) FROM schedules WHERE result IS NOT NULL"
    ).fetchone()[0]
    assert len(hist) == n
    assert hist["game_id"].is_unique


def test_spread_and_total_populated_every_season(hist):
    """Closing spread/total are complete 1999+ (verified: 100% in schedules)."""
    by_season = hist.groupby("season")[["spread_line", "total_line"]].apply(
        lambda d: d.notna().mean()
    )
    assert (by_season["spread_line"] > 0.99).all(), by_season["spread_line"].idxmin()
    assert (by_season["total_line"] > 0.99).all()


def test_moneyline_coverage_starts_2006(hist):
    if int(hist["season"].min()) > 2005:
        pytest.skip("DB slice starts after 2005")
    with_ml = hist[hist["home_moneyline"].notna()]
    assert int(with_ml["season"].min()) == 2006
    # and it is genuinely absent before, not just sparse
    assert hist[hist["season"] < 2006]["home_moneyline"].isna().all()


def test_live_only_columns_are_all_nan_in_history(hist):
    for col in sorted(R.LIVE_ONLY_FIELDS):
        assert col in hist.columns
        assert hist[col].isna().all(), f"{col} leaked into the history frame"


def test_ref_asof_join_is_strictly_prior_season(warehouse_conn, hist):
    """A game must see its referee's career THROUGH THE PRIOR SEASON only.
    Sample refs whose career extends past a game's season and assert the
    row's ref_games equals the prior-season sum (< full career)."""
    n_seasons = warehouse_conn.execute(
        "SELECT count(DISTINCT season) FROM v_referee_seasons"
    ).fetchone()[0]
    if n_seasons < 2:
        pytest.skip("fixture slice has a single ref season — no as-of horizon")
    samples = warehouse_conn.execute(
        """
        WITH careers AS (
            SELECT ref_key, sum(games) AS career_games, max(season) AS last_season
            FROM v_referee_seasons GROUP BY ref_key
        )
        SELECT rg.game_id, rg.ref_key, rg.season, c.career_games,
               (SELECT sum(r.games) FROM v_referee_seasons r
                WHERE r.ref_key = rg.ref_key AND r.season < rg.season) AS prior_games
        FROM v_referee_games rg
        JOIN careers c USING (ref_key)
        WHERE c.last_season > rg.season          -- career extends past this game
          AND rg.season > (SELECT min(season) FROM v_referee_seasons
                           WHERE ref_key = rg.ref_key)  -- has a prior-season line
        ORDER BY rg.season, rg.game_id LIMIT 5
        """
    ).fetchall()
    assert samples, "no sampleable ref careers"
    by_game = hist.set_index("game_id")
    for game_id, ref_key, _season, career_games, prior_games in samples:
        got = by_game.at[game_id, "ref_games"]
        assert got == prior_games, f"{game_id} ({ref_key}): {got} != prior {prior_games}"
        assert got < career_games, f"{game_id} ({ref_key}): as-of join saw the future"


def test_weather_and_indoor_flags(hist):
    assert hist["wx_is_indoor"].notna().all()
    # the wind-under seed rule must have real historical support
    windy = hist[(hist["wx_wind_mph"] >= 15) & (~hist["wx_is_indoor"].astype(bool))]
    assert len(windy) > 0


def test_live_facts_frame_builds_for_an_upcoming_week(warehouse_conn):
    """Upcoming games are not in games/pbp — the facts SQL must still produce
    rest/travel/tz for them (schedules + venue tables path)."""
    row = warehouse_conn.execute(
        """
        SELECT season, min(week) FROM schedules WHERE result IS NULL GROUP BY season
        ORDER BY season LIMIT 1
        """
    ).fetchone()
    if row is None:
        pytest.skip("no upcoming games on the schedule")
    season, week = int(row[0]), int(row[1])
    df = R.build_facts(warehouse_conn, season, week)
    assert len(df) > 0
    assert df["home_travel_miles"].notna().any()
    assert df["away_tz_shift_hours"].notna().any()
    assert set(R.LIVE_ONLY_FIELDS) <= set(df.columns)
