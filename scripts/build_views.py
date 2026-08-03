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
               fantasy_points, fantasy_points_ppr
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
               fantasy_points, fantasy_points_ppr
        FROM player_stats_week_v2
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
