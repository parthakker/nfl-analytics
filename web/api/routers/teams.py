import logging

from fastapi import APIRouter, HTTPException

from ..deps import (
    current_schedule_season,
    latest_stats_season,
    read_conn,
    rows_to_dicts,
    teams_meta,
)

log = logging.getLogger(__name__)

router = APIRouter()


def _canon(code: str) -> str:
    code = code.upper()
    if code not in teams_meta.TEAMS:
        raise HTTPException(404, f"unknown team {code}")
    return code


@router.get("/api/teams/{code}")
def team(code: str, season: int | None = None) -> dict:
    code = _canon(code)
    if season is None:
        season = latest_stats_season()
    coach_season = current_schedule_season()
    with read_conn() as con:
        rec = rows_to_dicts(
            con,
            """
            SELECT count(*) AS g, sum(win)::int AS w,
                   round(avg(points_for),1) AS pf_pg,
                   round(avg(points_against),1) AS pa_pg
            FROM v_team_games WHERE team=? AND season=? AND season_type='REG'
        """,
            [code, season],
        )[0]
        sos = rows_to_dicts(
            con,
            """
            SELECT rank() OVER (ORDER BY opp_avg_win_pct DESC) AS rank,
                   round(opp_avg_win_pct,3) AS value
            FROM v_strength_of_schedule WHERE season=? QUALIFY team=?
        """,
            [season, code],
        )
        cur = con.execute(
            """
            SELECT any_value(home_coach) FROM schedules
            WHERE season=? AND home_team=?
        """,
            [coach_season, code],
        ).fetchone()
        hist = rows_to_dicts(
            con,
            """
            SELECT season, any_value(coach) AS coach, count(*) AS games,
                   sum(win)::int AS wins, round(avg(points_for),1) AS ppg
            FROM (SELECT season, week, coach, win, points_for
                  FROM v_team_games WHERE team=? AND season_type='REG')
            GROUP BY season ORDER BY season DESC
        """,
            [code],
        )
    return {
        "code": code,
        "season": season,
        "record": {
            "w": rec["w"] or 0,
            "l": (rec["g"] or 0) - (rec["w"] or 0),
            "pf_pg": rec["pf_pg"],
            "pa_pg": rec["pa_pg"],
        },
        "sos": sos[0] if sos else None,
        "coach": {"current": cur[0] if cur else None, "history": hist},
    }


@router.get("/api/teams/{code}/epa")
def team_epa(code: str, season: int | None = None) -> dict:
    code = _canon(code)
    if season is None:
        season = latest_stats_season()
    with read_conn() as con:
        weeks = rows_to_dicts(
            con,
            """
            SELECT g.week,
                   round(avg(p.epa) FILTER (WHERE p.posteam=$t),3) AS off,
                   round(avg(p.epa) FILTER (WHERE p.defteam=$t),3) AS def
            FROM play_by_play p JOIN games g USING (game_id)
            WHERE p.season=$s AND p.play_type IN ('pass','run')
              AND (p.posteam=$t OR p.defteam=$t)
            GROUP BY g.week ORDER BY g.week
        """,
            {"t": code, "s": season},
        )
    return {"season": season, "weeks": weeks}


@router.get("/api/teams/{code}/roster")
def roster(code: str, season: int | None = None) -> dict:
    """Season-aware roster (rosters_weekly covers 2002-2026; GROUP BY gsis_id
    also dedupes the known pre-2017 same-team dup rows). Historical rosters
    make every era's player reachable from the team page."""
    code = _canon(code)
    if season is None:
        season = current_schedule_season()
    with read_conn() as con:
        seasons = [
            r[0]
            for r in con.execute(
                """
            SELECT DISTINCT season FROM rosters_weekly WHERE team = ?
            ORDER BY season DESC
        """,
                [code],
            ).fetchall()
        ]
        players = rows_to_dicts(
            con,
            """
            SELECT r.gsis_id AS gsis, any_value(r.jersey_number)::int AS num,
                   any_value(r.full_name) AS name,
                   any_value(r.position) AS pos, any_value(r.status) AS status,
                   any_value(r.college) AS college,
                   any_value(r.years_exp)::int AS exp,
                   any_value(p.headshot) AS headshot
            FROM rosters_weekly r
            LEFT JOIN players p ON p.gsis_id = r.gsis_id
            WHERE r.season = ? AND r.team = ?
            GROUP BY r.gsis_id ORDER BY pos, num
        """,
            [season, code],
        )
    return {"season": season, "seasons": seasons, "players": players}


@router.get("/api/teams/{code}/schedule")
def schedule(code: str, season: int | None = None) -> dict:
    code = _canon(code)
    if season is None:
        season = current_schedule_season()
    with read_conn() as con:
        games = rows_to_dicts(
            con,
            """
            SELECT game_id, week, strftime(gameday, '%a %b %d') AS date,
                   CASE WHEN home_team=$t THEN away_team ELSE home_team END AS opponent,
                   home_team=$t AS home,
                   home_score, away_score,
                   CASE WHEN spread_line IS NULL THEN NULL
                        WHEN (home_team=$t AND spread_line>0) OR (away_team=$t AND spread_line<0)
                        THEN 'favored by ' || abs(spread_line)
                        ELSE 'underdog by ' || abs(spread_line) END AS line_text,
                   total_line AS total
            FROM schedules WHERE season=$s AND (home_team=$t OR away_team=$t)
            ORDER BY week
        """,
            {"t": code, "s": season},
        )
    return {"season": season, "games": games}


@router.get("/api/teams/{code}/news")
def team_news(code: str, limit: int = 30) -> dict:
    code = _canon(code)
    nickname = teams_meta.TEAMS[code][0].split()[-1]
    items = []
    with read_conn(attach_news=True) as con:
        try:
            items = rows_to_dicts(
                con,
                """
                SELECT published_ts AS ts, source, headline, url
                FROM newsdb.news
                WHERE list_contains(teams, ?) OR headline ILIKE '%' || ? || '%'
                ORDER BY published_ts DESC NULLS LAST LIMIT ?
            """,
                [code, nickname, min(limit, 100)],
            )
        except Exception as e:
            # news sidecar absent/locked — the team page still serves
            log.warning("teams/%s/news: news sidecar query failed: %s", code, e)
    return {"items": items}


@router.get("/api/teams/{code}/overview")
def overview(code: str, season: int | None = None) -> dict:
    code = _canon(code)
    import json as _json

    from ..deps import ROOT

    meta_path = ROOT / "data" / "coaches_meta.json"
    meta = {}
    if meta_path.exists():
        raw = _json.loads(meta_path.read_text(encoding="utf-8"))
        meta = {k: v for k, v in raw.items() if not k.startswith("_")}
    team_meta = meta.get(code)

    division = next((d for d, teams in teams_meta.DIVISIONS.items() if code in teams), None)
    div_teams = list(teams_meta.DIVISIONS.get(division, []))

    with read_conn() as con:
        if season is None:
            season = con.execute(
                "SELECT max(season) FROM v_matchup_games WHERE team = ?", [code]
            ).fetchone()[0]

        header = rows_to_dicts(
            con,
            """
            SELECT count(*) FILTER (WHERE win = 1)::int AS w,
                   count(*) FILTER (WHERE win = 0)::int AS l,
                   count(*) FILTER (WHERE win = 0.5)::int AS t,
                   round(avg(team_score), 1) AS pf_pg,
                   round(avg(opp_score), 1) AS pa_pg
            FROM v_matchup_games
            WHERE team = ? AND season = ? AND season_type = 'REG'
        """,
            [code, season],
        )[0]

        pf_ranks = rows_to_dicts(
            con,
            """
            WITH t AS (
                SELECT team, avg(team_score) AS pf, avg(opp_score) AS pa
                FROM v_matchup_games WHERE season = ? AND season_type = 'REG'
                GROUP BY team)
            SELECT rank() OVER (ORDER BY pf DESC) AS pf_rank,
                   rank() OVER (ORDER BY pa ASC) AS pa_rank
            FROM t QUALIFY team = ?
        """,
            [season, code],
        )
        header.update(pf_ranks[0] if pf_ranks else {"pf_rank": None, "pa_rank": None})

        standings = rows_to_dicts(
            con,
            f"""
            SELECT team, count(*) FILTER (WHERE win = 1)::int AS w,
                   count(*) FILTER (WHERE win = 0)::int AS l,
                   count(*) FILTER (WHERE win = 0.5)::int AS t,
                   round(avg(win), 3) AS pct,
                   sum(team_score)::int AS pf, sum(opp_score)::int AS pa
            FROM v_matchup_games
            WHERE season = ? AND season_type = 'REG'
              AND team IN ({",".join("?" for _ in div_teams)})
            GROUP BY team ORDER BY pct DESC, pf - pa DESC
        """,
            [season, *div_teams],
        )
        div_rank = next((i + 1 for i, r in enumerate(standings) if r["team"] == code), None)

        leaders = []
        for key, label, view, expr, joinkey in (
            (
                "pass_yds",
                "Passing yards",
                "v_player_stats_week_all",
                "sum(v.passing_yards)::int",
                "recent_team",
            ),
            (
                "rush_yds",
                "Rushing yards",
                "v_player_stats_week_all",
                "sum(v.rushing_yards)::int",
                "recent_team",
            ),
            (
                "rec_yds",
                "Receiving yards",
                "v_player_stats_week_all",
                "sum(v.receiving_yards)::int",
                "recent_team",
            ),
            (
                "tackles",
                "Tackles",
                "v_player_stats_def_week_all",
                "sum(v.def_tackles)::int",
                "team",
            ),
            (
                "ints",
                "Interceptions",
                "v_player_stats_def_week_all",
                "sum(v.def_interceptions)::int",
                "team",
            ),
        ):
            row = rows_to_dicts(
                con,
                f"""
                SELECT v.player_id, any_value(v.player_display_name) AS name,
                       any_value(p.headshot) AS headshot, {expr} AS value
                FROM {view} v LEFT JOIN players p ON p.gsis_id = v.player_id
                WHERE v.{joinkey} = ? AND v.season = ? AND v.season_type = 'REG'
                GROUP BY v.player_id
                HAVING value > 0 ORDER BY value DESC LIMIT 1
            """,
                [code, season],
            )
            leaders.append({"key": key, "label": label, **(row[0] if row else {})})

        epa = rows_to_dicts(
            con,
            """
            WITH o AS (SELECT team, off_epa, off_pass_epa, off_rush_epa,
                              rank() OVER (ORDER BY off_epa DESC) AS off_rank,
                              rank() OVER (ORDER BY off_pass_epa DESC) AS pass_rank,
                              rank() OVER (ORDER BY off_rush_epa DESC) AS rush_rank
                       FROM v_team_epa_season WHERE season = ?),
                 d AS (SELECT team, def_epa,
                              rank() OVER (ORDER BY def_epa ASC) AS def_rank
                       FROM v_team_def_epa_season WHERE season = ?)
            SELECT round(o.off_epa,3) AS off_epa, o.off_rank,
                   round(d.def_epa,3) AS def_epa, d.def_rank,
                   round(o.off_pass_epa,3) AS pass_epa, o.pass_rank,
                   round(o.off_rush_epa,3) AS rush_epa, o.rush_rank
            FROM o JOIN d USING (team) WHERE team = ?
        """,
            [season, season, code],
        )

        travel = rows_to_dicts(
            con,
            """
            SELECT total_travel_miles, avg_road_trip_miles, max_trip_miles,
                   international_games, total_tz_hours
            FROM v_team_travel_season WHERE team = ? AND season = ?
        """,
            [code, season],
        )
        extras = rows_to_dicts(
            con,
            """
            SELECT count(*) FILTER (WHERE short_week)::int AS short_weeks,
                   count(*) FILTER (WHERE is_off_bye)::int AS byes
            FROM v_team_games
            WHERE team = ? AND season = ? AND season_type = 'REG'
        """,
            [code, season],
        )

        franchise = rows_to_dicts(
            con,
            """
            WITH post AS (
                SELECT season, arg_max(game_type, game_date) AS last_round,
                       arg_max(win, game_date) AS last_win
                FROM v_matchup_games
                WHERE team = ? AND season_type = 'POST' GROUP BY season)
            SELECT m.season,
                   count(*) FILTER (WHERE m.win = 1)::int AS w,
                   count(*) FILTER (WHERE m.win = 0)::int AS l,
                   count(*) FILTER (WHERE m.win = 0.5)::int AS t,
                   any_value(CASE
                     WHEN p.last_round = 'SB' AND p.last_win = 1 THEN 'SB champs'
                     WHEN p.last_round = 'SB' THEN 'Lost SB'
                     WHEN p.last_round = 'CON' THEN 'Lost CONF'
                     WHEN p.last_round = 'DIV' THEN 'Lost DIV'
                     WHEN p.last_round = 'WC' THEN 'Lost WC'
                   END) AS playoffs
            FROM v_matchup_games m LEFT JOIN post p USING (season)
            WHERE m.team = ? AND m.season_type = 'REG' AND m.season >= 2007
            GROUP BY m.season ORDER BY m.season
        """,
            [code, code],
        )

        injuries = []
        try:
            wk = con.execute(
                """
                SELECT max(week) FROM injuries WHERE season = ?
            """,
                [season],
            ).fetchone()[0]
            if wk is not None:
                injuries = rows_to_dicts(
                    con,
                    """
                    SELECT full_name AS player, position, report_status AS status,
                           report_primary_injury AS injury
                    FROM injuries
                    WHERE season = ? AND week = ? AND canon_team(team) = ?
                      AND report_status IS NOT NULL
                    ORDER BY position
                """,
                    [season, wk, code],
                )
        except Exception as e:
            # injuries block is optional context — degrade, but visibly
            log.warning("teams/%s/overview: injuries block failed: %s", code, e)

    return {
        "code": code,
        "season": season,
        "division": division,
        "div_rank": div_rank,
        "header": header,
        "staff": {
            "head_coach": team_meta.get("head_coach") if team_meta else None,
            "hc": team_meta.get("hc") if team_meta else None,
            "oc": team_meta.get("oc") if team_meta else None,
            "dc": team_meta.get("dc") if team_meta else None,
            "offense_scheme": team_meta.get("offense_scheme") if team_meta else None,
            "defense_scheme": team_meta.get("defense_scheme") if team_meta else None,
            "note": team_meta.get("note") if team_meta else None,
        },
        "leaders": leaders,
        "standings": standings,
        "epa": epa[0] if epa else None,
        "travel": {**(travel[0] if travel else {}), **(extras[0] if extras else {})},
        "franchise": franchise,
        "injuries": injuries,
    }


@router.get("/api/teams/{code}/results")
def results(code: str, season: int | None = None) -> dict:
    code = _canon(code)
    with read_conn() as con:
        seasons = [
            r[0]
            for r in con.execute(
                """
            SELECT DISTINCT season FROM v_matchup_games
            WHERE team = ? AND season >= 2007 ORDER BY season DESC
        """,
                [code],
            ).fetchall()
        ]
        if season is None:
            season = seasons[0] if seasons else latest_stats_season()
        rows = rows_to_dicts(
            con,
            """
            WITH g AS (
                SELECT m.*, tg.rest_days_sched, tg.travel_miles
                FROM v_matchup_games m
                LEFT JOIN v_team_games tg
                       ON tg.game_id = m.game_id AND tg.team = m.team
                WHERE m.team = ? AND m.season = ?
            )
            SELECT game_id, week, game_type, season_type,
                   strftime(game_date, '%a %b %d') AS date, site, opponent,
                   win, team_score, opp_score, overtime,
                   sum(CASE WHEN win = 1 AND season_type = 'REG' THEN 1 ELSE 0 END)
                       OVER (ORDER BY game_date ROWS UNBOUNDED PRECEDING) AS w_td,
                   sum(CASE WHEN win = 0 AND season_type = 'REG' THEN 1 ELSE 0 END)
                       OVER (ORDER BY game_date ROWS UNBOUNDED PRECEDING) AS l_td,
                   sum(CASE WHEN win = 0.5 AND season_type = 'REG' THEN 1 ELSE 0 END)
                       OVER (ORDER BY game_date ROWS UNBOUNDED PRECEDING) AS t_td,
                   spread_line_team, covered, total_line, went_over,
                   team_qb, opp_qb, referee, venue_name,
                   rest_days_sched, travel_miles
            FROM g ORDER BY game_date
        """,
            [code, season],
        )
        # running streak (client-friendly precompute)
        streak = 0
        for r in rows:
            if r["season_type"] != "REG":
                r["streak"] = None
                continue
            w = r["win"]
            if w == 0.5:
                streak = 0
            elif w == 1:
                streak = streak + 1 if streak > 0 else 1
            else:
                streak = streak - 1 if streak < 0 else -1
            r["streak"] = f"W{streak}" if streak > 0 else (f"L{-streak}" if streak < 0 else "T")
        summary = rows_to_dicts(
            con,
            """
            SELECT count(*) FILTER (WHERE win = 1 AND season_type='REG')::int AS w,
                   count(*) FILTER (WHERE win = 0 AND season_type='REG')::int AS l,
                   count(*) FILTER (WHERE win = 0.5 AND season_type='REG')::int AS t,
                   count(*) FILTER (WHERE covered)::int AS ats_w,
                   count(*) FILTER (WHERE covered = false)::int AS ats_l,
                   count(*) FILTER (WHERE went_over)::int AS overs,
                   count(*) FILTER (WHERE went_over = false)::int AS unders,
                   count(*) FILTER (WHERE win = 1 AND site = 'home' AND season_type='REG')::int AS home_w,
                   count(*) FILTER (WHERE win = 0 AND site = 'home' AND season_type='REG')::int AS home_l,
                   count(*) FILTER (WHERE win = 1 AND site != 'home' AND season_type='REG')::int AS away_w,
                   count(*) FILTER (WHERE win = 0 AND site != 'home' AND season_type='REG')::int AS away_l
            FROM v_matchup_games WHERE team = ? AND season = ?
        """,
            [code, season],
        )[0]
    return {"code": code, "season": season, "seasons": seasons, "summary": summary, "rows": rows}
