"""Create derived views/tables in nfl.duckdb for common analytical questions.

Everything here is derived from raw tables; safe to re-run (CREATE OR REPLACE).
Run:  python scripts/build_views.py
"""

import json
import sys
from pathlib import Path

import duckdb

DB = Path(__file__).resolve().parent.parent / "nfl.duckdb"
STADIUMS = Path(__file__).resolve().parent.parent / "data" / "stadiums.json"

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
    # one row per team per game: the workhorse for SoS, rest, travel, records.
    # travel_miles = haversine from the team's home venue THAT SEASON to the
    # game venue (home-base distance, not itinerary-chained; chaining is a
    # possible later add). rest_days_sched comes from schedules home/away_rest
    # (populated week 1 and cross-season, unlike the lag-computed rest_days).
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
               CASE WHEN s.is_home THEN sc.home_rest ELSE sc.away_rest END AS rest_days_sched,
               (CASE WHEN s.is_home THEN sc.home_rest ELSE sc.away_rest END >= 12
                AND s.week > 1) AS is_off_bye,
               (CASE WHEN s.is_home THEN sc.home_rest ELSE sc.away_rest END <= 5) AS short_week,
               hs.tz AS team_tz, gv.venue_tz AS game_tz,
               -- positive = traveling east (e.g. PT team playing in ET = +3)
               hs.et_offset - gv.venue_et_offset AS tz_shift_hours,
               gv.venue_id, gv.venue_name, gv.venue_country,
               gv.neutral_site, gv.is_international,
               CAST(round(haversine_miles(hs.lat, hs.lon, gv.lat, gv.lon)) AS INT)
                   AS travel_miles
        FROM sides s
        LEFT JOIN schedules sc ON sc.game_id = s.game_id
        LEFT JOIN game_venues gv ON gv.game_id = s.game_id
        LEFT JOIN team_home_venues thv ON thv.team = s.team AND thv.season = s.season
        LEFT JOIN stadiums hs ON hs.venue_id = thv.venue_id
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
    # coach vs coach head-to-head (spread_line is already team-perspective;
    # ATS counts exclude pushes, same convention as v_coach_seasons)
    "v_coach_matchups": """
        CREATE OR REPLACE VIEW v_coach_matchups AS
        SELECT coach, opp_coach, count(*) AS games, sum(win) AS wins,
               avg(points_for) AS avg_pf, avg(points_against) AS avg_pa,
               min(season) AS first_season, max(season) AS last_season,
               count(*) FILTER (WHERE spread_line IS NOT NULL
                                AND points_for - points_against <> spread_line) AS ats_games,
               count(*) FILTER (WHERE spread_line IS NOT NULL
                                AND points_for - points_against > spread_line) AS ats_wins,
               arg_max(game_id, game_date) AS last_meeting_game_id
        FROM v_team_games
        GROUP BY coach, opp_coach
    """,
    # team vs team, one row per completed game per direction (2 rows/game).
    # Source: schedules (1999+) so it works regardless of pbp backfill depth.
    # Teams are franchise-canonicalized (STL->LA, SD->LAC, OAK->LV) so series
    # merge across relocations; raw_team_code preserves the era code.
    # spread_line_team is flipped to team-perspective (positive = team favored).
    "v_matchup_games": """
        CREATE OR REPLACE VIEW v_matchup_games AS
        WITH sides AS (
            SELECT game_id, season, week, game_type, gameday::DATE AS game_date,
                   canon_team(home_team) AS team, canon_team(away_team) AS opponent,
                   home_team AS raw_team_code,
                   home_score AS team_score, away_score AS opp_score,
                   TRUE AS is_home, location, overtime,
                   spread_line AS spread_line_team, total_line,
                   home_coach AS team_coach, away_coach AS opp_coach,
                   home_qb_name AS team_qb, away_qb_name AS opp_qb, referee, roof
            FROM schedules WHERE result IS NOT NULL
            UNION ALL
            SELECT game_id, season, week, game_type, gameday::DATE,
                   canon_team(away_team), canon_team(home_team), away_team,
                   away_score, home_score, FALSE, location, overtime,
                   -spread_line, total_line, away_coach, home_coach,
                   away_qb_name, home_qb_name, referee, roof
            FROM schedules WHERE result IS NOT NULL
        )
        SELECT sd.game_id, sd.season, sd.week,
               CASE WHEN sd.game_type = 'REG' THEN 'REG' ELSE 'POST' END AS season_type,
               sd.game_type, sd.game_date, sd.team, sd.opponent, sd.raw_team_code,
               sd.team_score, sd.opp_score, sd.team_score - sd.opp_score AS margin,
               CAST(CASE WHEN sd.team_score > sd.opp_score THEN 1
                         WHEN sd.team_score < sd.opp_score THEN 0
                         ELSE 0.5 END AS DOUBLE) AS win,
               CASE WHEN sd.location = 'Neutral' THEN 'neutral'
                    WHEN sd.is_home THEN 'home' ELSE 'away' END AS site,
               gv.venue_id, gv.venue_name, gv.venue_country, sd.roof,
               sd.spread_line_team,
               CASE WHEN sd.spread_line_team IS NOT NULL
                    AND sd.team_score - sd.opp_score <> sd.spread_line_team
                    THEN (sd.team_score - sd.opp_score) > sd.spread_line_team END AS covered,
               sd.total_line,
               CASE WHEN sd.total_line IS NOT NULL
                    THEN (sd.team_score + sd.opp_score) > sd.total_line END AS went_over,
               sd.overtime::BOOLEAN AS overtime,
               sd.team_coach, sd.opp_coach, sd.team_qb, sd.opp_qb, sd.referee
        FROM sides sd
        LEFT JOIN game_venues gv ON gv.game_id = sd.game_id
    """,
    # all-time series per directional team pair. current_streak is signed:
    # +N = team has won last N meetings, -N = lost last N (ties break streaks).
    "v_team_matchups": """
        CREATE OR REPLACE VIEW v_team_matchups AS
        WITH g AS (
            SELECT *, row_number() OVER (PARTITION BY team, opponent
                                         ORDER BY game_date DESC, game_id DESC) AS rn
            FROM v_matchup_games
        ),
        lastval AS (
            SELECT team, opponent, win AS last_win FROM g WHERE rn = 1
        ),
        streaks AS (
            SELECT g.team, g.opponent,
                   coalesce(min(g.rn) FILTER (WHERE g.win <> l.last_win) - 1,
                            count(*)) AS streak_len,
                   any_value(l.last_win) AS last_win
            FROM g JOIN lastval l USING (team, opponent)
            GROUP BY g.team, g.opponent
        )
        SELECT m.team, m.opponent, count(*) AS games,
               count(*) FILTER (WHERE win = 1) AS wins,
               count(*) FILTER (WHERE win = 0) AS losses,
               count(*) FILTER (WHERE win = 0.5) AS ties,
               count(*) FILTER (WHERE site = 'home') AS home_games,
               count(*) FILTER (WHERE site = 'home' AND win = 1) AS home_wins,
               count(*) FILTER (WHERE site = 'away') AS away_games,
               count(*) FILTER (WHERE site = 'away' AND win = 1) AS away_wins,
               count(*) FILTER (WHERE site = 'neutral') AS neutral_games,
               count(*) FILTER (WHERE season_type = 'POST') AS post_games,
               count(*) FILTER (WHERE season_type = 'POST' AND win = 1) AS post_wins,
               round(avg(margin), 1) AS avg_margin,
               round(avg(team_score), 1) AS avg_pf,
               round(avg(opp_score), 1) AS avg_pa,
               round(avg(team_score + opp_score), 1) AS avg_total,
               count(*) FILTER (WHERE covered) AS ats_wins,
               count(*) FILTER (WHERE covered IS NOT NULL) AS ats_games,
               min(season) AS first_meeting_season,
               max(season) AS last_meeting_season,
               arg_max(game_id, game_date) AS last_meeting_game_id,
               max(game_date) AS last_meeting_date,
               any_value(CASE WHEN s.last_win = 1 THEN s.streak_len
                              WHEN s.last_win = 0 THEN -s.streak_len
                              ELSE 0 END) AS current_streak
        FROM v_matchup_games m
        JOIN streaks s USING (team, opponent)
        GROUP BY m.team, m.opponent
    """,
    # season travel totals per team (one-way home-base miles summed over all
    # games incl. home games, which contribute ~0)
    "v_team_travel_season": """
        CREATE OR REPLACE VIEW v_team_travel_season AS
        SELECT season, team, count(*) AS games,
               count(*) FILTER (WHERE NOT is_home) AS road_games,
               sum(travel_miles) AS total_travel_miles,
               CAST(round(avg(travel_miles) FILTER (WHERE NOT is_home)) AS INT)
                   AS avg_road_trip_miles,
               max(travel_miles) AS max_trip_miles,
               count(*) FILTER (WHERE is_international) AS international_games,
               sum(abs(tz_shift_hours)) AS total_tz_hours
        FROM v_team_games
        GROUP BY season, team
    """,
    # one weather answer per game, best source wins: dome -> constant; played
    # games -> pbp observation > open-meteo archive > schedules temp/wind;
    # upcoming games -> open-meteo forecast (fetch_weather.py, <16 days out)
    "v_game_weather": """
        CREATE OR REPLACE VIEW v_game_weather AS
        WITH eff AS (
            -- an open-air venue can't be closed: schedules.roof lies for
            -- neutral games (it carries the listed home team's roof), so the
            -- curated venue roof wins when the venue has no roof at all
            SELECT s.game_id, s.result, s.temp, s.wind,
                   CASE WHEN gv.venue_roof = 'outdoors' THEN 'outdoors'
                        WHEN gv.venue_roof = 'dome' THEN 'dome'
                        ELSE coalesce(s.roof, gv.venue_roof) END AS roof
            FROM schedules s
            LEFT JOIN game_venues gv ON gv.game_id = s.game_id
        )
        SELECT e.game_id,
               (e.roof IN ('dome', 'closed')) AS is_indoor,
               CASE
                 WHEN e.roof IN ('dome', 'closed') THEN 'indoor'
                 WHEN e.result IS NULL AND om.source = 'forecast' THEN 'forecast'
                 WHEN gw.temp_f IS NOT NULL THEN 'pbp'
                 WHEN om.source = 'archive' THEN 'openmeteo'
                 WHEN e.temp IS NOT NULL THEN 'schedules'
               END AS weather_source,
               CASE WHEN e.roof IN ('dome', 'closed') THEN 68
                    WHEN e.result IS NULL THEN om.temp_f
                    ELSE coalesce(gw.temp_f, om.temp_f, e.temp) END AS temp_f,
               CASE WHEN e.roof IN ('dome', 'closed') THEN 0
                    WHEN e.result IS NULL THEN om.wind_mph
                    ELSE coalesce(gw.wind_mph, om.wind_mph, e.wind) END AS wind_mph,
               coalesce(gw.humidity_pct, om.humidity_pct) AS humidity_pct,
               coalesce(gw.gust_mph, om.wind_gust_mph) AS gust_mph,
               gw.wind_dir, om.wind_dir_deg, om.precip_in, om.precip_prob_pct,
               om.snowfall_in, om.cloud_cover_pct, gw.sky, e.roof
        FROM eff e
        LEFT JOIN game_weather_parsed gw ON gw.game_id = e.game_id
        LEFT JOIN weather_openmeteo om ON om.game_id = e.game_id
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
    # officials (2015+) joined via games.old_game_id (99.86% match), coalesced
    # with schedules.referee to extend coverage back to 2007 (and the 4 COVID
    # reschedule games the officials join drops). Aggregate on ref_key:
    # official_id when known (2015+), normalized name otherwise (gotcha #10 —
    # name spellings vary, so pre-2015 name-keyed rows are best-effort).
    "v_referee_games": """
        CREATE OR REPLACE VIEW v_referee_games AS
        WITH pen AS (
            SELECT game_id,
                   count(*) FILTER (WHERE penalty = 1) AS penalties,
                   sum(penalty_yards) FILTER (WHERE penalty = 1) AS penalty_yards,
                   count(*) FILTER (WHERE penalty = 1 AND penalty_team = home_team) AS pen_home,
                   count(*) FILTER (WHERE penalty = 1 AND penalty_team = away_team) AS pen_away
            FROM play_by_play GROUP BY game_id
        ),
        refs AS (
            SELECT g.game_id,
                   coalesce(o.official_id::VARCHAR,
                            'name:' || upper(trim(s.referee))) AS ref_key,
                   o.official_id,
                   coalesce(o.official_name, s.referee) AS official_name
            FROM games g
            LEFT JOIN officials o ON o.game_id::VARCHAR = g.old_game_id::VARCHAR
                                 AND o.position = 'Referee'
            LEFT JOIN schedules s ON s.game_id = g.game_id
            WHERE coalesce(o.official_name, s.referee) IS NOT NULL
        )
        SELECT r.ref_key, r.official_id, r.official_name, g.game_id, g.season,
               g.week, g.season_type, p.penalties, p.penalty_yards,
               p.pen_home, p.pen_away, g.spread_line,
               g.home_score + g.away_score AS total_points, g.total_line,
               CASE WHEN g.total_line IS NOT NULL
                    THEN (g.home_score + g.away_score) > g.total_line END AS went_over,
               g.home_score > g.away_score AS home_won,
               CASE WHEN g.spread_line IS NOT NULL
                    AND g.home_score - g.away_score <> g.spread_line
                    THEN (g.home_score - g.away_score) > g.spread_line END AS home_covered
        FROM refs r
        JOIN games g ON g.game_id = r.game_id
        JOIN pen p ON p.game_id = g.game_id
    """,
    "v_referee_seasons": """
        CREATE OR REPLACE VIEW v_referee_seasons AS
        SELECT ref_key, any_value(official_id) AS official_id,
               any_value(official_name) AS name, season,
               count(*) AS games,
               round(avg(penalties), 2) AS pen_per_game,
               round(avg(penalty_yards), 1) AS pen_yds_per_game,
               round(avg(pen_home) - avg(pen_away), 2) AS home_pen_bias,
               round(avg(total_points), 1) AS avg_total_points,
               round(avg(CASE WHEN went_over THEN 1.0 WHEN went_over = false THEN 0.0 END), 3) AS over_rate,
               round(avg(home_won::int), 3) AS home_win_rate,
               round(avg(CASE WHEN home_covered THEN 1.0 WHEN home_covered = false THEN 0.0 END), 3) AS home_cover_rate
        FROM v_referee_games
        GROUP BY ref_key, season
    """,
    # referee x team history: what happens to THIS team with THIS crew chief.
    # ATS excludes pushes on both sides.
    "v_referee_team_splits": """
        CREATE OR REPLACE VIEW v_referee_team_splits AS
        WITH sides AS (
            SELECT rg.ref_key, rg.official_name, rg.season, g.home_team AS team,
                   rg.pen_home AS pen_on_team, rg.pen_away AS pen_on_opp,
                   g.home_score > g.away_score AS team_won,
                   rg.home_covered AS team_covered, rg.went_over
            FROM v_referee_games rg JOIN games g ON g.game_id = rg.game_id
            UNION ALL
            SELECT rg.ref_key, rg.official_name, rg.season, g.away_team,
                   rg.pen_away, rg.pen_home,
                   g.away_score > g.home_score,
                   CASE WHEN rg.spread_line IS NOT NULL
                        AND g.home_score - g.away_score <> rg.spread_line
                        THEN (g.home_score - g.away_score) < rg.spread_line END,
                   rg.went_over
            FROM v_referee_games rg JOIN games g ON g.game_id = rg.game_id
        )
        SELECT ref_key, any_value(official_name) AS official_name, team,
               count(*) AS games,
               count(*) FILTER (WHERE team_won) AS team_wins,
               round(avg(team_won::int), 3) AS team_win_pct,
               count(*) FILTER (WHERE team_covered) AS team_covers,
               count(*) FILTER (WHERE team_covered IS NOT NULL) AS ats_games,
               round(avg(pen_on_team), 2) AS pen_on_team_pg,
               round(avg(pen_on_team - pen_on_opp), 2) AS pen_diff_pg,
               round(avg(CASE WHEN went_over THEN 1.0 WHEN went_over = false THEN 0.0 END), 3) AS over_rate
        FROM sides
        GROUP BY ref_key, team
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


def load_stadiums(con: duckdb.DuckDBPyConnection) -> None:
    """Venue tables from hand-curated data/stadiums.json + derived game_venues.

    Resolution rule per game: hand override > (Neutral: name-alias match,
    else stadium_id match) > name fallback > home team's usual venue.
    """
    sj = json.loads(STADIUMS.read_text(encoding="utf-8"))
    con.execute("""
        CREATE OR REPLACE TABLE stadiums (
            venue_id VARCHAR PRIMARY KEY, name VARCHAR, city VARCHAR,
            state VARCHAR, country VARCHAR, lat DOUBLE, lon DOUBLE,
            tz VARCHAR, et_offset DOUBLE, roof VARCHAR, surface VARCHAR,
            first_season INT, last_season INT)
    """)
    con.executemany(
        "INSERT INTO stadiums VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        [[v["venue_id"], v["name"], v["city"], v["state"], v["country"],
          v["lat"], v["lon"], v["tz"], v["et_offset"], v["roof"], v["surface"],
          v["first_season"], v["last_season"]] for v in sj["venues"]])
    aliases = {}
    for v in sj["venues"]:
        for a in [v["name"], *v["aliases"]]:
            aliases[a.lower().strip()] = v["venue_id"]
    con.execute("CREATE OR REPLACE TABLE stadium_aliases (alias_lower VARCHAR PRIMARY KEY, venue_id VARCHAR)")
    con.executemany("INSERT INTO stadium_aliases VALUES (?,?)", list(aliases.items()))
    con.execute("CREATE OR REPLACE TABLE game_venue_overrides (game_id VARCHAR PRIMARY KEY, venue_id VARCHAR)")
    con.executemany("INSERT INTO game_venue_overrides VALUES (?,?)",
                    list(sj["game_overrides"].items()))
    con.execute("""
        CREATE OR REPLACE MACRO haversine_miles(lat1, lon1, lat2, lon2) AS
        3958.8 * 2 * asin(sqrt(
            pow(sin(radians(lat2 - lat1) / 2), 2) +
            cos(radians(lat1)) * cos(radians(lat2)) *
            pow(sin(radians(lon2 - lon1) / 2), 2)))
    """)
    # team-season home venue = modal venue of non-neutral home games
    con.execute("""
        CREATE OR REPLACE TABLE team_home_venues AS
        WITH resolved AS (
            SELECT s.season, canon_team(s.home_team) AS team,
                   coalesce(idm.venue_id, an.venue_id) AS venue_id
            FROM schedules s
            LEFT JOIN stadiums idm ON idm.venue_id = s.stadium_id
            LEFT JOIN stadium_aliases an ON an.alias_lower = lower(trim(s.stadium))
            WHERE s.location != 'Neutral'
              AND coalesce(idm.venue_id, an.venue_id) IS NOT NULL
        )
        SELECT team, season, mode(venue_id) AS venue_id, count(*) AS home_games
        FROM resolved GROUP BY team, season
    """)
    con.execute("""
        CREATE OR REPLACE TABLE game_venues AS
        WITH pick AS (
            SELECT s.game_id, s.location,
                   coalesce(ov.venue_id,
                            CASE WHEN s.location = 'Neutral'
                                 THEN coalesce(an.venue_id, idm.venue_id)
                                 ELSE coalesce(idm.venue_id, an.venue_id) END,
                            hv.venue_id) AS venue_id,
                   CASE WHEN ov.venue_id IS NOT NULL THEN 'override'
                        WHEN s.location = 'Neutral' AND an.venue_id IS NOT NULL THEN 'name'
                        WHEN s.location != 'Neutral' AND idm.venue_id IS NOT NULL THEN 'id'
                        WHEN coalesce(an.venue_id, idm.venue_id) IS NOT NULL THEN 'name'
                        WHEN hv.venue_id IS NOT NULL THEN 'fallback' END AS resolution
            FROM schedules s
            LEFT JOIN game_venue_overrides ov ON ov.game_id = s.game_id
            LEFT JOIN stadiums idm ON idm.venue_id = s.stadium_id
            LEFT JOIN stadium_aliases an ON an.alias_lower = lower(trim(s.stadium))
            LEFT JOIN team_home_venues hv ON hv.team = canon_team(s.home_team)
                                         AND hv.season = s.season
        )
        SELECT p.game_id, p.venue_id, p.resolution,
               (p.location = 'Neutral') AS neutral_site,
               st.name AS venue_name, st.city AS venue_city,
               st.country AS venue_country, st.lat, st.lon,
               st.tz AS venue_tz, st.et_offset AS venue_et_offset,
               st.roof AS venue_roof, st.surface AS venue_surface,
               (st.country != 'USA') AS is_international
        FROM pick p LEFT JOIN stadiums st ON st.venue_id = p.venue_id
    """)
    unresolved = con.execute(
        "SELECT count(*) FROM game_venues WHERE venue_id IS NULL").fetchone()[0]
    n = con.execute("SELECT count(*) FROM game_venues").fetchone()[0]
    print(f"  game_venues                  OK ({n:,} games, {unresolved} unresolved"
          + (" — WARNING: add aliases/overrides to data/stadiums.json!" if unresolved else ")"))


def parse_weather(con: duckdb.DuckDBPyConnection) -> None:
    """Structured weather from the pbp free-text `weather` column (one row per
    game, 2007+). Handles the indoor/empty variants and range winds."""
    con.execute(r"""
        CREATE OR REPLACE TABLE game_weather_parsed AS
        WITH raw AS (
            SELECT game_id, any_value(weather) AS weather_raw
            FROM play_by_play WHERE weather IS NOT NULL GROUP BY game_id
        )
        SELECT game_id, weather_raw,
               CASE WHEN weather_raw LIKE '%Temp:%'
                    THEN nullif(rtrim(regexp_extract(weather_raw, '^(.*?)\s*Temp:', 1), ', '), '')
                    ELSE nullif(rtrim(weather_raw, ', '), '') END AS sky,
               TRY_CAST(regexp_extract(weather_raw, 'Temp:\s*(\d+)', 1) AS INT) AS temp_f,
               TRY_CAST(regexp_extract(weather_raw, 'Humidity:\s*(\d+)', 1) AS INT) AS humidity_pct,
               nullif(trim(regexp_extract(weather_raw, 'Wind:\s*([A-Za-z][A-Za-z ]*?)\s+\d', 1)), '') AS wind_dir,
               TRY_CAST(regexp_extract(weather_raw, 'Wind:[^0-9]*(\d+)', 1) AS INT) AS wind_mph,
               TRY_CAST(regexp_extract(weather_raw, 'Wind:[^0-9]*\d+\s*-\s*(\d+)', 1) AS INT) AS wind_mph_high,
               TRY_CAST(regexp_extract(weather_raw, '[Gg]usts?[^0-9]*(\d+)', 1) AS INT) AS gust_mph,
               (weather_raw ILIKE '%indoor%' OR weather_raw ILIKE '%controlled climate%') AS is_indoor_note
        FROM raw
    """)
    n, t = con.execute("SELECT count(*), count(temp_f) FROM game_weather_parsed").fetchone()
    print(f"  game_weather_parsed          OK ({n:,} games, {t:,} with temp)")


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
    load_stadiums(con)
    parse_weather(con)
    # v_game_weather needs this table even before the first fetch_weather run
    con.execute("""
        CREATE TABLE IF NOT EXISTS weather_openmeteo (
            game_id VARCHAR, venue_id VARCHAR, kickoff_local VARCHAR,
            fetched_at VARCHAR, source VARCHAR, temp_f DOUBLE,
            feels_like_f DOUBLE, humidity_pct DOUBLE, wind_mph DOUBLE,
            wind_gust_mph DOUBLE, wind_dir_deg DOUBLE, precip_in DOUBLE,
            precip_prob_pct DOUBLE, snowfall_in DOUBLE, cloud_cover_pct DOUBLE,
            weather_code INT)
    """)
    failures = []
    for name, sql in VIEWS.items():
        try:
            con.execute(sql)
            n = con.execute(f"SELECT count(*) FROM {name}").fetchone()[0]
            print(f"  {name:28s} OK ({n:,} rows)")
        except Exception as e:
            failures.append(f"{name}: {e}")
    # travel sanity: BUF->SoFi ~2,190mi, NYG@NYJ ~0, MIA->Wembley ~4,414mi
    try:
        checks = con.execute("""
            SELECT
              (SELECT travel_miles FROM v_team_games
               WHERE team='BUF' AND venue_id='LAX01' AND NOT is_home LIMIT 1),
              (SELECT max(travel_miles) FROM v_team_games
               WHERE team='NYG' AND opponent='NYJ' AND NOT is_home),
              (SELECT travel_miles FROM v_team_games
               WHERE team='MIA' AND venue_id='LON00' LIMIT 1)
        """).fetchone()
        buf_sofi, nyg_nyj, mia_lon = checks
        ok = (buf_sofi and 2100 <= buf_sofi <= 2300 and (nyg_nyj or 0) < 20
              and mia_lon and 4300 <= mia_lon <= 4550)
        print(f"  travel sanity {'OK' if ok else 'FAILED'}: BUF->SoFi={buf_sofi}mi, "
              f"NYG@NYJ={nyg_nyj}mi, MIA@Wembley={mia_lon}mi")
        if not ok:
            failures.append("travel sanity check out of range")
    except Exception as e:
        failures.append(f"travel sanity: {e}")
    con.close()
    if failures:
        print("\nFAILURES:")
        for f in failures:
            print(f"  - {f}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(build())
