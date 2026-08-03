from fastapi import APIRouter, HTTPException

from ..deps import read_conn, rows_to_dicts, teams_meta

router = APIRouter()


def _canon(code: str) -> str:
    code = code.upper()
    if code not in teams_meta.TEAMS:
        raise HTTPException(404, f"unknown team {code}")
    return code


@router.get("/api/teams/{code}")
def team(code: str, season: int = 2025) -> dict:
    code = _canon(code)
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
            WHERE season=2026 AND home_team=?
        """,
            [code],
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
def team_epa(code: str, season: int = 2025) -> dict:
    code = _canon(code)
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
def roster(code: str) -> dict:
    code = _canon(code)
    with read_conn() as con:
        players = rows_to_dicts(
            con,
            """
            SELECT gsis_id AS gsis, any_value(jersey_number)::int AS num,
                   any_value(full_name) AS name,
                   any_value(position) AS pos, any_value(status) AS status,
                   any_value(college) AS college, any_value(years_exp)::int AS exp
            FROM rosters_weekly WHERE season=2026 AND team=?
            GROUP BY gsis_id ORDER BY pos, num
        """,
            [code],
        )
    return {"season": 2026, "players": players}


@router.get("/api/teams/{code}/schedule")
def schedule(code: str, season: int = 2026) -> dict:
    code = _canon(code)
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
    with read_conn(attach_news=True) as con:
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
    return {"items": items}
