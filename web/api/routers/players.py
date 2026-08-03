from fastapi import APIRouter, HTTPException

from ..deps import read_conn, rows_to_dicts

router = APIRouter()


@router.get("/api/players/search")
def search(q: str) -> dict:
    with read_conn() as con:
        hits = rows_to_dicts(
            con,
            """
            SELECT gsis_id, display_name AS name, position AS pos,
                   latest_team AS team, last_season
            FROM players WHERE display_name ILIKE '%' || ? || '%'
            ORDER BY (last_season IS NULL), last_season DESC LIMIT 8
        """,
            [q],
        )
    return {"hits": hits}


@router.get("/api/players/{gsis_id}")
def detail(gsis_id: str) -> dict:
    with read_conn(attach_news=True) as con:
        info = rows_to_dicts(
            con,
            """
            SELECT display_name AS name, position AS pos, latest_team AS team,
                   rookie_season, last_season, draft_year, draft_round, headshot
            FROM players WHERE gsis_id = ?
        """,
            [gsis_id],
        )
        if not info:
            raise HTTPException(404, "player not found")
        seasons = rows_to_dicts(
            con,
            """
            SELECT season, count(*) AS games,
                   sum(passing_yards)::int AS pass_yds, sum(passing_tds)::int AS pass_td,
                   sum(carries)::int AS att, sum(rushing_yards)::int AS rush_yds,
                   sum(receptions)::int AS rec, sum(receiving_yards)::int AS rec_yds,
                   round(sum(fantasy_points),1) AS std,
                   round(sum(fantasy_points_half_ppr),1) AS half_ppr,
                   round(sum(fantasy_points_ppr),1) AS ppr
            FROM v_player_stats_week_all
            WHERE player_id=? AND season_type='REG' AND week IS NOT NULL
            GROUP BY season ORDER BY season DESC
        """,
            [gsis_id],
        )
        weekly = rows_to_dicts(
            con,
            """
            SELECT season, week, round(fantasy_points_ppr,1) AS ppr,
                   opponent_team AS opp
            FROM v_player_stats_week_all
            WHERE player_id=? AND season_type='REG'
            ORDER BY season, week
        """,
            [gsis_id],
        )
        news = rows_to_dicts(
            con,
            """
            SELECT published_ts AS ts, headline, url FROM newsdb.news
            WHERE list_contains(players, ?) ORDER BY published_ts DESC LIMIT 8
        """,
            [gsis_id],
        )
    return {"info": info[0], "seasons": seasons, "weekly": weekly, "news": news}
