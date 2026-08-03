"""Matchup center: the ESPN-style H2H card, but with full history.

Two endpoints:
  /api/matchup/{game_id}      — everything about one game (past OR upcoming):
                                travel, rest, refs, coach h2h, weather, market,
                                injuries, all-time series.
  /api/matchup/h2h/{a}/{b}    — free-form all-time series explorer (1999+).

Everything is assembled from schedules-derived views (v_matchup_games,
v_team_matchups, game_venues) so upcoming games — which never appear in the
pbp-derived `games` table — get the full card too.
"""

from fastapi import APIRouter, HTTPException

from ..deps import read_conn, rows_to_dicts, teams_meta

router = APIRouter()

SITES = {"a_home", "b_home", "neutral"}


def _team(code: str) -> str:
    code = code.upper()
    if code not in teams_meta.TEAMS:
        raise HTTPException(404, f"unknown team {code}")
    return code


def _side(con, team: str, season: int, game_id: str, rest, coach, qb) -> dict:
    """One team's card: record, rest flags, travel, form, EPA."""
    rec = rows_to_dicts(
        con,
        """
        SELECT count(*) FILTER (WHERE win = 1)::int AS w,
               count(*) FILTER (WHERE win = 0)::int AS l,
               count(*) FILTER (WHERE win = 0.5)::int AS t
        FROM v_matchup_games WHERE team = ? AND season = ? AND season_type = 'REG'
          AND game_date < (SELECT gameday FROM schedules WHERE game_id = ?)
    """,
        [team, season, game_id],
    )[0]
    travel = rows_to_dicts(
        con,
        """
        SELECT CAST(round(haversine_miles(hs.lat, hs.lon, gv.lat, gv.lon)) AS INT)
                   AS travel_miles,
               hs.et_offset - gv.venue_et_offset AS tz_shift_hours
        FROM game_venues gv
        JOIN team_home_venues thv ON thv.team = ? AND thv.season = ?
        JOIN stadiums hs ON hs.venue_id = thv.venue_id
        WHERE gv.game_id = ?
    """,
        [team, season, game_id],
    )
    form = rows_to_dicts(
        con,
        """
        SELECT game_id, opponent, site, team_score, opp_score, win, margin, season
        FROM v_matchup_games WHERE team = ?
          AND game_date < (SELECT gameday FROM schedules WHERE game_id = ?)
        ORDER BY game_date DESC LIMIT 5
    """,
        [team, game_id],
    )
    epa = rows_to_dicts(
        con,
        """
        WITH o AS (SELECT team, off_epa,
                          rank() OVER (ORDER BY off_epa DESC) AS off_rank
                   FROM v_team_epa_season WHERE season = ?),
             d AS (SELECT team, def_epa,
                          rank() OVER (ORDER BY def_epa ASC) AS def_rank
                   FROM v_team_def_epa_season WHERE season = ?)
        SELECT round(o.off_epa, 3) AS off_epa, o.off_rank,
               round(d.def_epa, 3) AS def_epa, d.def_rank
        FROM o JOIN d USING (team) WHERE team = ?
    """,
        [season, season, team],
    )
    return {
        "code": team,
        "coach": coach,
        "qb": qb,
        "record": rec,
        "rest_days": rest,
        "is_off_bye": rest is not None and rest >= 12,
        "short_week": rest is not None and rest <= 5,
        "travel_miles": travel[0]["travel_miles"] if travel else None,
        "tz_shift_hours": travel[0]["tz_shift_hours"] if travel else None,
        "form_last5": form,
        "epa": epa[0] if epa else None,
    }


@router.get("/api/matchup/h2h/{team_a}/{team_b}")
def h2h(
    team_a: str,
    team_b: str,
    season_min: int | None = None,
    season_max: int | None = None,
    season_type: str | None = None,
    site: str | None = None,
) -> dict:
    a, b = _team(team_a), _team(team_b)
    if season_type not in (None, "REG", "POST"):
        raise HTTPException(400, "season_type must be REG or POST")
    if site is not None and site not in SITES:
        raise HTTPException(400, f"site must be one of {sorted(SITES)}")
    where, params = ["team = ?", "opponent = ?"], [a, b]
    if season_min is not None:
        where.append("season >= ?")
        params.append(season_min)
    if season_max is not None:
        where.append("season <= ?")
        params.append(season_max)
    if season_type:
        where.append("season_type = ?")
        params.append(season_type)
    if site == "a_home":
        where.append("site = 'home'")
    elif site == "b_home":
        where.append("site = 'away'")
    elif site == "neutral":
        where.append("site = 'neutral'")
    w = " AND ".join(where)

    with read_conn() as con:
        games = rows_to_dicts(
            con,
            f"""
            SELECT game_id, season, week, season_type, game_type,
                   strftime(game_date, '%b %d, %Y') AS date, site,
                   venue_name, venue_country, team_score AS a_score,
                   opp_score AS b_score, margin AS margin_a, win AS a_win,
                   overtime, spread_line_team AS spread_line_a, covered AS covered_a,
                   total_line, went_over, team_coach AS a_coach,
                   opp_coach AS b_coach, team_qb AS a_qb, opp_qb AS b_qb, referee
            FROM v_matchup_games WHERE {w}
            ORDER BY game_date DESC
        """,
            params,
        )
        summary = rows_to_dicts(
            con,
            f"""
            SELECT count(*) AS games,
                   count(*) FILTER (WHERE win = 1)::int AS a_wins,
                   count(*) FILTER (WHERE win = 0)::int AS b_wins,
                   count(*) FILTER (WHERE win = 0.5)::int AS ties,
                   count(*) FILTER (WHERE site = 'home')::int AS a_home_games,
                   count(*) FILTER (WHERE site = 'home' AND win = 1)::int AS a_home_wins,
                   count(*) FILTER (WHERE site = 'away')::int AS a_away_games,
                   count(*) FILTER (WHERE site = 'away' AND win = 1)::int AS a_away_wins,
                   count(*) FILTER (WHERE site = 'neutral')::int AS neutral_games,
                   round(avg(margin), 1) AS avg_margin_a,
                   round(avg(team_score + opp_score), 1) AS avg_total,
                   count(*) FILTER (WHERE covered)::int AS a_covers,
                   count(*) FILTER (WHERE covered IS NOT NULL)::int AS ats_games,
                   min(season) AS first_season, max(season) AS last_season
            FROM v_matchup_games WHERE {w}
        """,
            params,
        )[0]
        streak = rows_to_dicts(
            con,
            """
            SELECT current_streak, last_meeting_game_id
            FROM v_team_matchups WHERE team = ? AND opponent = ?
        """,
            [a, b],
        )
        splits = {
            "by_decade": rows_to_dicts(
                con,
                f"""
                SELECT (season / 10) * 10 AS era, count(*) AS g,
                       count(*) FILTER (WHERE win = 1)::int AS a_wins
                FROM v_matchup_games WHERE {w} GROUP BY era ORDER BY era
            """,
                params,
            ),
            "by_venue": rows_to_dicts(
                con,
                f"""
                SELECT venue_name AS venue, count(*) AS g,
                       count(*) FILTER (WHERE win = 1)::int AS a_wins
                FROM v_matchup_games WHERE {w} AND venue_name IS NOT NULL
                GROUP BY venue_name ORDER BY g DESC LIMIT 12
            """,
                params,
            ),
            "by_season_type": rows_to_dicts(
                con,
                f"""
                SELECT season_type, count(*) AS g,
                       count(*) FILTER (WHERE win = 1)::int AS a_wins
                FROM v_matchup_games WHERE {w} GROUP BY season_type
            """,
                params,
            ),
        }
    return {
        "teams": [a, b],
        "summary": summary,
        "streak": streak[0] if streak else None,
        "splits": splits,
        "games": games,
    }


@router.get("/api/matchup/{game_id}")
def matchup(game_id: str) -> dict:
    with read_conn(attach_kalshi=True) as con:
        spine = rows_to_dicts(
            con,
            """
            SELECT s.game_id, s.season, s.week, s.game_type,
                   CASE WHEN s.game_type = 'REG' THEN 'REG' ELSE 'POST' END AS season_type,
                   strftime(s.gameday, '%a %b %d, %Y') AS date, s.gameday, s.gametime,
                   (s.result IS NOT NULL) AS final,
                   canon_team(s.away_team) AS away_team, canon_team(s.home_team) AS home_team,
                   s.away_score, s.home_score, s.overtime,
                   s.away_rest, s.home_rest, s.div_game,
                   s.away_coach, s.home_coach, s.away_qb_name, s.home_qb_name,
                   s.referee, s.spread_line, s.total_line,
                   s.home_moneyline, s.away_moneyline, s.surface,
                   gv.venue_id, gv.venue_name, gv.venue_city, gv.venue_country,
                   gv.venue_roof AS roof, gv.neutral_site, gv.is_international
            FROM schedules s
            LEFT JOIN game_venues gv ON gv.game_id = s.game_id
            WHERE s.game_id = ?
        """,
            [game_id],
        )
        if not spine:
            raise HTTPException(404, "unknown game_id")
        g = spine[0]
        away, home, season = g["away_team"], g["home_team"], g["season"]

        teams = {
            "away": _side(
                con, away, season, game_id, g["away_rest"], g["away_coach"], g["away_qb_name"]
            ),
            "home": _side(
                con, home, season, game_id, g["home_rest"], g["home_coach"], g["home_qb_name"]
            ),
        }

        coach_h2h = None
        if g["away_coach"] and g["home_coach"]:
            rows = rows_to_dicts(
                con,
                """
                SELECT games, wins::double AS wins, round(avg_pf, 1) AS avg_pf,
                       round(avg_pa, 1) AS avg_pa, first_season, last_season,
                       ats_games, ats_wins
                FROM v_coach_matchups WHERE coach = ? AND opp_coach = ?
            """,
                [g["away_coach"], g["home_coach"]],
            )
            if rows:
                meetings = rows_to_dicts(
                    con,
                    """
                    SELECT game_id, season, week, points_for AS away_coach_pts,
                           points_against AS home_coach_pts, win::double AS win
                    FROM v_team_games WHERE coach = ? AND opp_coach = ?
                    ORDER BY game_date DESC LIMIT 5
                """,
                    [g["away_coach"], g["home_coach"]],
                )
                coach_h2h = {
                    "away_coach": g["away_coach"],
                    "home_coach": g["home_coach"],
                    **rows[0],
                    "meetings": meetings,
                }

        referee = None
        if g["referee"]:
            career = rows_to_dicts(
                con,
                """
                SELECT sum(games)::int AS games,
                       round(sum(pen_per_game * games) / sum(games), 2) AS pen_per_game,
                       round(sum(over_rate * games) / sum(games), 3) AS over_rate,
                       round(sum(home_cover_rate * games) / sum(games), 3) AS home_cover_rate,
                       round(sum(home_win_rate * games) / sum(games), 3) AS home_win_rate,
                       any_value(ref_key) AS ref_key
                FROM v_referee_seasons WHERE upper(trim(name)) = upper(trim(?))
            """,
                [g["referee"]],
            )
            splits = rows_to_dicts(
                con,
                """
                SELECT team, games, team_wins, team_win_pct, team_covers,
                       ats_games, pen_on_team_pg, pen_diff_pg, over_rate
                FROM v_referee_team_splits
                WHERE upper(trim(official_name)) = upper(trim(?)) AND team IN (?, ?)
            """,
                [g["referee"], away, home],
            )
            referee = {
                "name": g["referee"],
                "career": career[0] if career and career[0]["games"] else None,
                "team_splits": {s["team"]: s for s in splits},
            }
        elif not g["final"]:
            referee = {
                "name": None,
                "career": None,
                "team_splits": {},
                "note": "Crew assignments publish weekly in-season",
            }

        weather = rows_to_dicts(
            con,
            """
            SELECT is_indoor, weather_source, temp_f, wind_mph, humidity_pct,
                   gust_mph, wind_dir, precip_prob_pct, precip_in, sky, roof
            FROM v_game_weather WHERE game_id = ?
        """,
            [game_id],
        )

        market = {
            "spread_line": g["spread_line"],
            "total_line": g["total_line"],
            "home_moneyline": g["home_moneyline"],
            "away_moneyline": g["away_moneyline"],
            "line_history": [],
            "kalshi": None,
        }
        try:
            market["line_history"] = rows_to_dicts(
                con,
                """
                SELECT strftime(snapshot_ts, '%m/%d %H:%M') AS ts,
                       spread_line AS spread, total_line AS total
                FROM kalshi.line_snapshots WHERE game_id = ?
                ORDER BY snapshot_ts
            """,
                [game_id],
            )
            k = rows_to_dicts(
                con,
                """
                WITH latest AS (
                    SELECT *, row_number() OVER (PARTITION BY ticker
                                                 ORDER BY snapshot_ts DESC) rn
                    FROM kalshi.kalshi_snapshots)
                SELECT d.yes_team, l.implied_prob_mid AS prob, l.volume, l.ticker
                FROM latest l JOIN kalshi.kalshi_markets_dim d USING (ticker)
                WHERE l.rn = 1 AND d.kind = 'game' AND l.status = 'active'
                  AND d.away_team = ? AND d.home_team = ?
            """,
                [away, home],
            )
            if k:
                m = k[0]
                prob_home = (
                    m["prob"]
                    if m["yes_team"] == home
                    else (1 - m["prob"] if m["prob"] is not None else None)
                )
                market["kalshi"] = {
                    "prob_home": prob_home,
                    "ticker": m["ticker"],
                    "volume": m["volume"],
                }
        except Exception:
            pass  # kalshi store busy — card still serves

        injuries = {"away": [], "home": []}
        try:
            for r in rows_to_dicts(
                con,
                """
                SELECT canon_team(team) AS team, full_name AS player, position,
                       report_status AS status, report_primary_injury AS injury,
                       practice_status
                FROM injuries WHERE season = ? AND week = ?
                  AND canon_team(team) IN (?, ?) AND report_status IS NOT NULL
                ORDER BY team, position
            """,
                [season, g["week"], away, home],
            ):
                injuries["away" if r["team"] == away else "home"].append(r)
        except Exception:
            pass

        series = None
        srows = rows_to_dicts(
            con,
            """
            SELECT games, wins AS away_wins, losses AS home_wins, ties,
                   avg_margin, avg_total, current_streak,
                   first_meeting_season, last_meeting_game_id, ats_wins, ats_games
            FROM v_team_matchups WHERE team = ? AND opponent = ?
        """,
            [away, home],
        )
        if srows:
            last5 = rows_to_dicts(
                con,
                """
                SELECT game_id, season, week, season_type, site,
                       strftime(game_date, '%b %Y') AS date, venue_name,
                       team_score AS away_pts, opp_score AS home_pts, win AS away_win
                FROM v_matchup_games WHERE team = ? AND opponent = ?
                ORDER BY game_date DESC LIMIT 5
            """,
                [away, home],
            )
            series = {**srows[0], "last5": last5}

    return {
        "game": {
            k: g[k]
            for k in (
                "game_id",
                "season",
                "week",
                "season_type",
                "game_type",
                "date",
                "gametime",
                "final",
                "away_team",
                "home_team",
                "away_score",
                "home_score",
                "overtime",
                "div_game",
                "surface",
            )
        },
        "venue": {
            k: g[k]
            for k in (
                "venue_id",
                "venue_name",
                "venue_city",
                "venue_country",
                "roof",
                "neutral_site",
                "is_international",
            )
        },
        "teams": teams,
        "coach_h2h": coach_h2h,
        "referee": referee,
        "weather": weather[0] if weather else None,
        "market": market,
        "injuries": injuries,
        "series": series,
    }
