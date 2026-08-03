"""Create derived views/tables in nfl.duckdb for common analytical questions.

Everything here is derived from raw tables; safe to re-run (CREATE OR REPLACE).
Run:  python scripts/build_views.py
"""

import sys
from pathlib import Path

import duckdb

DB = Path(__file__).resolve().parent.parent / "nfl.duckdb"

# Home-stadium timezone per team code (code era matters: STL=Central, LA=Pacific).
# Limitation: international games (London/Munich/Mexico City) keep the home
# team's timezone here; use games.stadium to special-case if it matters.
TEAM_TZ = {
    "ARI": "MST", "ATL": "ET", "BAL": "ET", "BUF": "ET", "CAR": "ET",
    "CHI": "CT", "CIN": "ET", "CLE": "ET", "DAL": "CT", "DEN": "MT",
    "DET": "ET", "GB": "CT", "HOU": "CT", "IND": "ET", "JAX": "ET",
    "KC": "CT", "LA": "PT", "LAC": "PT", "LV": "PT", "MIA": "ET",
    "MIN": "CT", "NE": "ET", "NO": "CT", "NYG": "ET", "NYJ": "ET",
    "PHI": "ET", "PIT": "ET", "SEA": "PT", "SF": "PT", "TB": "ET",
    "TEN": "CT", "WAS": "ET",
    # relocated-era codes
    "SD": "PT", "OAK": "PT", "STL": "CT", "JAC": "ET", "LAR": "PT",
}
TZ_OFFSET = {"ET": 0, "CT": 1, "MT": 2, "MST": 2, "PT": 3}  # hours behind ET

# Every non-canonical team code observed anywhere in the warehouse, mapped to
# the current nflverse code. Sources: injuries (OAK/SD/STL), ngs (LAR),
# advstats_season_pass (LVR), draft_picks (PFR codes incl. pre-2000 era).
# pbp/player_stats/team_stats are already canonical.
TEAM_ALIASES = {
    "SD": "LAC", "SDG": "LAC",
    "OAK": "LV", "LVR": "LV", "RAI": "LV",
    "STL": "LA", "LAR": "LA", "RAM": "LA",
    "JAC": "JAX", "PHO": "ARI",
    "GNB": "GB", "KAN": "KC", "NOR": "NO", "NWE": "NE",
    "SFO": "SF", "TAM": "TB",
}

VIEWS = {
    # one row per team per game: the workhorse for SoS, rest, travel, records
    "v_team_games": """
        CREATE OR REPLACE VIEW v_team_games AS
        WITH sides AS (
            SELECT game_id, old_game_id, season, week, season_type, game_date,
                   start_time, home_team AS team, away_team AS opponent,
                   home_coach AS coach, away_coach AS opp_coach,
                   home_score AS points_for, away_score AS points_against,
                   TRUE AS is_home, roof, surface, temp, wind, stadium, div_game,
                   spread_line, total_line
            FROM games
            UNION ALL
            SELECT game_id, old_game_id, season, week, season_type, game_date,
                   start_time, away_team, home_team,
                   away_coach, home_coach,
                   away_score, home_score,
                   FALSE, roof, surface, temp, wind, stadium, div_game,
                   -spread_line, total_line
            FROM games
        )
        SELECT s.*,
               CASE WHEN points_for > points_against THEN 1
                    WHEN points_for < points_against THEN 0
                    ELSE 0.5 END AS win,
               s.game_date - lag(s.game_date) OVER
                   (PARTITION BY s.team, s.season ORDER BY s.game_date) AS rest_days,
               tt.tz AS team_tz, vt.tz AS game_tz,
               -- positive = traveling east (e.g. PT team playing in ET = +3)
               tt.offset_behind_et - vt.offset_behind_et AS tz_shift_hours
        FROM sides s
        LEFT JOIN team_timezones tt ON tt.team = s.team
        LEFT JOIN team_timezones vt
               ON vt.team = CASE WHEN s.is_home THEN s.team ELSE s.opponent END
    """,
    # traditional SoS: average final win% of opponents faced (regular season)
    "v_strength_of_schedule": """
        CREATE OR REPLACE VIEW v_strength_of_schedule AS
        WITH records AS (
            SELECT season, team, avg(win) AS win_pct
            FROM v_team_games WHERE season_type = 'REG'
            GROUP BY season, team
        )
        SELECT g.season, g.team,
               avg(r.win_pct) AS opp_avg_win_pct,
               count(*) AS games
        FROM v_team_games g
        JOIN records r ON r.season = g.season AND r.team = g.opponent
        WHERE g.season_type = 'REG'
        GROUP BY g.season, g.team
    """,
    # EPA-based team strength by season (better SoS ingredient than win%)
    "v_team_epa_season": """
        CREATE OR REPLACE VIEW v_team_epa_season AS
        SELECT season, posteam AS team,
               avg(epa) FILTER (WHERE pass = 1) AS off_pass_epa,
               avg(epa) FILTER (WHERE rush = 1) AS off_rush_epa,
               avg(epa) AS off_epa,
               count(*) AS plays
        FROM play_by_play
        WHERE season_type = 'REG' AND posteam IS NOT NULL
          AND play_type IN ('pass', 'run')
        GROUP BY season, posteam
    """,
    "v_team_def_epa_season": """
        CREATE OR REPLACE VIEW v_team_def_epa_season AS
        SELECT season, defteam AS team,
               avg(epa) FILTER (WHERE pass = 1) AS def_pass_epa,
               avg(epa) FILTER (WHERE rush = 1) AS def_rush_epa,
               avg(epa) AS def_epa,
               count(*) AS plays
        FROM play_by_play
        WHERE season_type = 'REG' AND defteam IS NOT NULL
          AND play_type IN ('pass', 'run')
        GROUP BY season, defteam
    """,
    # coach vs coach head-to-head
    "v_coach_matchups": """
        CREATE OR REPLACE VIEW v_coach_matchups AS
        SELECT coach, opp_coach, count(*) AS games, sum(win) AS wins,
               avg(points_for) AS avg_pf, avg(points_against) AS avg_pa,
               min(season) AS first_season, max(season) AS last_season
        FROM v_team_games
        GROUP BY coach, opp_coach
    """,
    # all-era weekly offense stats: pre-2025 table + v2 table mapped onto the
    # old column names (v2 renamed recent_team->team, interceptions->passing_
    # interceptions, sacks->sacks_suffered, sack_yards->sack_yards_lost and
    # dropped dakota). Use this view, not the raw tables, for cross-era queries.
    "v_player_stats_week_all": """
        CREATE OR REPLACE VIEW v_player_stats_week_all AS
        SELECT player_id, player_display_name, position, position_group,
               recent_team, season, week, season_type, opponent_team,
               completions, attempts, passing_yards, passing_tds, interceptions,
               sacks, sack_yards, passing_air_yards, passing_yards_after_catch,
               passing_first_downs, passing_epa, pacr,
               carries, rushing_yards, rushing_tds, rushing_fumbles,
               rushing_fumbles_lost, rushing_first_downs, rushing_epa,
               receptions, targets, receiving_yards, receiving_tds,
               receiving_fumbles, receiving_fumbles_lost, receiving_air_yards,
               receiving_yards_after_catch, receiving_first_downs, receiving_epa,
               racr, target_share, air_yards_share, wopr,
               fantasy_points, fantasy_points_ppr,
               fantasy_points_ppr - 0.5 * receptions AS fantasy_points_half_ppr
        FROM player_stats_week
        UNION ALL
        SELECT player_id, player_display_name, position, position_group,
               team AS recent_team, season, week, season_type, opponent_team,
               completions, attempts, passing_yards, passing_tds,
               passing_interceptions AS interceptions,
               sacks_suffered AS sacks, sack_yards_lost AS sack_yards,
               passing_air_yards, passing_yards_after_catch,
               passing_first_downs, passing_epa, pacr,
               carries, rushing_yards, rushing_tds, rushing_fumbles,
               rushing_fumbles_lost, rushing_first_downs, rushing_epa,
               receptions, targets, receiving_yards, receiving_tds,
               receiving_fumbles, receiving_fumbles_lost, receiving_air_yards,
               receiving_yards_after_catch, receiving_first_downs, receiving_epa,
               racr, target_share, air_yards_share, wopr,
               fantasy_points, fantasy_points_ppr,
               fantasy_points_ppr - 0.5 * receptions AS fantasy_points_half_ppr
        FROM player_stats_week_v2
    """,
    # coach x season x team: records incl. playoffs and against-the-spread.
    # v_team_games.spread_line is already team-perspective (positive = favored).
    "v_coach_seasons": """
        CREATE OR REPLACE VIEW v_coach_seasons AS
        SELECT coach, season, team,
               count(*) FILTER (WHERE season_type = 'REG') AS reg_games,
               sum(win) FILTER (WHERE season_type = 'REG')::int AS reg_wins,
               count(*) FILTER (WHERE season_type = 'POST') AS post_games,
               sum(win) FILTER (WHERE season_type = 'POST')::int AS post_wins,
               round(avg(points_for), 1) AS ppg,
               round(avg(points_against), 1) AS papg,
               count(*) FILTER (WHERE spread_line IS NOT NULL
                                AND points_for - points_against <> spread_line) AS ats_games,
               count(*) FILTER (WHERE spread_line IS NOT NULL
                                AND points_for - points_against > spread_line) AS ats_wins
        FROM v_team_games WHERE coach IS NOT NULL
        GROUP BY coach, season, team
    """,
    # coach x season tendencies from pbp: the scheme fingerprint.
    # 4th-down "go territory": 4th & <=2, own 40 to opp 5, first 3 quarters,
    # game within reach (wp .1-.9) — rbsdm-style aggressiveness.
    "v_coach_tendencies": """
        CREATE OR REPLACE VIEW v_coach_tendencies AS
        WITH plays AS (
            SELECT CASE WHEN p.posteam = g.home_team THEN g.home_coach
                        ELSE g.away_coach END AS coach,
                   CASE WHEN p.defteam = g.home_team THEN g.home_coach
                        ELSE g.away_coach END AS def_coach,
                   p.*
            FROM play_by_play p JOIN games g USING (game_id)
            WHERE p.posteam IS NOT NULL
        )
        SELECT coach, season,
               round(avg(pass - xpass) FILTER (
                     WHERE down <= 2 AND qtr <= 3 AND xpass IS NOT NULL
                       AND play_type IN ('pass','run')), 4) AS proe,
               round(avg(shotgun::int) FILTER (WHERE play_type IN ('pass','run')), 3) AS shotgun_rate,
               round(avg(no_huddle::int) FILTER (WHERE play_type IN ('pass','run')), 3) AS no_huddle_rate,
               round(avg(CASE WHEN air_yards >= 20 THEN 1.0 ELSE 0.0 END)
                     FILTER (WHERE play_type = 'pass' AND air_yards IS NOT NULL), 3) AS deep_shot_rate,
               round(count(*) FILTER (WHERE play_type IN ('pass','run'))
                     / count(DISTINCT game_id)::double, 1) AS plays_per_game,
               count(*) FILTER (WHERE down = 4 AND ydstogo <= 2
                                AND yardline_100 BETWEEN 5 AND 60 AND qtr <= 3
                                AND wp BETWEEN 0.1 AND 0.9
                                AND play_type IN ('pass','run','punt','field_goal')) AS go_situations,
               count(*) FILTER (WHERE down = 4 AND ydstogo <= 2
                                AND yardline_100 BETWEEN 5 AND 60 AND qtr <= 3
                                AND wp BETWEEN 0.1 AND 0.9
                                AND play_type IN ('pass','run')) AS go_attempts
        FROM plays
        GROUP BY coach, season
    """,
    "v_coach_def_tendencies": """
        CREATE OR REPLACE VIEW v_coach_def_tendencies AS
        SELECT CASE WHEN p.defteam = g.home_team THEN g.home_coach
                    ELSE g.away_coach END AS coach,
               p.season,
               round(avg(p.epa) FILTER (WHERE p.pass = 1), 4) AS def_pass_epa,
               round(avg(p.epa) FILTER (WHERE p.rush = 1), 4) AS def_rush_epa,
               round(avg(p.sack::double) FILTER (WHERE p.pass = 1), 3) AS sack_rate,
               round(avg((coalesce(p.interception,0) + coalesce(p.fumble_lost,0))::double), 3) AS takeaway_rate,
               round(avg(CASE WHEN p.rushing_yards <= 0 THEN 1.0 ELSE 0.0 END)
                     FILTER (WHERE p.rush = 1 AND p.rushing_yards IS NOT NULL), 3) AS run_stuff_rate
        FROM play_by_play p JOIN games g USING (game_id)
        WHERE p.defteam IS NOT NULL AND p.play_type IN ('pass','run')
        GROUP BY 1, 2
    """,
    # head referee x game: penalties (from pbp), totals, spread results.
    # officials.game_id is numeric = games.old_game_id (99.86% match).
    "v_referee_games": """
        CREATE OR REPLACE VIEW v_referee_games AS
        WITH pen AS (
            SELECT game_id,
                   count(*) FILTER (WHERE penalty = 1) AS penalties,
                   sum(penalty_yards) FILTER (WHERE penalty = 1) AS penalty_yards,
                   count(*) FILTER (WHERE penalty = 1 AND penalty_team = home_team) AS pen_home,
                   count(*) FILTER (WHERE penalty = 1 AND penalty_team = away_team) AS pen_away
            FROM play_by_play GROUP BY game_id
        )
        SELECT o.official_id, o.official_name, g.game_id, g.season, g.week,
               g.season_type, p.penalties, p.penalty_yards, p.pen_home, p.pen_away,
               g.home_score + g.away_score AS total_points, g.total_line,
               CASE WHEN g.total_line IS NOT NULL
                    THEN (g.home_score + g.away_score) > g.total_line END AS went_over,
               g.home_score > g.away_score AS home_won,
               CASE WHEN g.spread_line IS NOT NULL
                    THEN (g.home_score - g.away_score) > g.spread_line END AS home_covered
        FROM officials o
        JOIN games g ON g.old_game_id::VARCHAR = o.game_id::VARCHAR
        JOIN pen p ON p.game_id = g.game_id
        WHERE o.position = 'Referee'
    """,
    "v_referee_seasons": """
        CREATE OR REPLACE VIEW v_referee_seasons AS
        SELECT official_id, any_value(official_name) AS name, season,
               count(*) AS games,
               round(avg(penalties), 2) AS pen_per_game,
               round(avg(penalty_yards), 1) AS pen_yds_per_game,
               round(avg(pen_home) - avg(pen_away), 2) AS home_pen_bias,
               round(avg(total_points), 1) AS avg_total_points,
               round(avg(CASE WHEN went_over THEN 1.0 WHEN went_over = false THEN 0.0 END), 3) AS over_rate,
               round(avg(home_won::int), 3) AS home_win_rate,
               round(avg(CASE WHEN home_covered THEN 1.0 WHEN home_covered = false THEN 0.0 END), 3) AS home_cover_rate
        FROM v_referee_games
        GROUP BY official_id, season
    """,
    # per-player-week red zone usage from pbp
    "v_redzone_usage_week": """
        CREATE OR REPLACE VIEW v_redzone_usage_week AS
        SELECT season, week, posteam AS team,
               coalesce(rusher_id, receiver_id) AS player_id,
               count(*) FILTER (WHERE rusher_id IS NOT NULL) AS rz_carries,
               count(*) FILTER (WHERE receiver_id IS NOT NULL) AS rz_targets,
               count(*) FILTER (WHERE touchdown = 1) AS rz_tds
        FROM play_by_play
        WHERE yardline_100 <= 20 AND play_type IN ('pass', 'run')
          AND coalesce(rusher_id, receiver_id) IS NOT NULL
        GROUP BY season, week, posteam, coalesce(rusher_id, receiver_id)
    """,
}


def build() -> int:
    con = duckdb.connect(str(DB))
    con.execute("CREATE OR REPLACE TABLE team_timezones AS SELECT * FROM (VALUES "
                + ", ".join(f"('{t}', '{tz}', {TZ_OFFSET[tz]})" for t, tz in TEAM_TZ.items())
                + ") AS t(team, tz, offset_behind_et)")
    con.execute("CREATE OR REPLACE TABLE team_aliases AS SELECT * FROM (VALUES "
                + ", ".join(f"('{a}', '{c}')" for a, c in TEAM_ALIASES.items())
                + ") AS t(alias, canonical)")
    # canon_team('OAK') -> 'LV'; pass-through for already-canonical codes
    con.execute("""
        CREATE OR REPLACE MACRO canon_team(t) AS
        coalesce((SELECT canonical FROM team_aliases WHERE alias = t), t)
    """)
    failures = []
    for name, sql in VIEWS.items():
        try:
            con.execute(sql)
            n = con.execute(f"SELECT count(*) FROM {name}").fetchone()[0]
            print(f"  {name:28s} OK ({n:,} rows)")
        except Exception as e:
            failures.append(f"{name}: {e}")
    con.close()
    if failures:
        print("\nFAILURES:")
        for f in failures:
            print(f"  - {f}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(build())
