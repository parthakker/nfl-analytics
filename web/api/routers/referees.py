from fastapi import APIRouter, HTTPException

from ..deps import read_conn, rows_to_dicts

router = APIRouter()


@router.get("/api/referees")
def referees(min_games: int = 30) -> dict:
    with read_conn() as con:
        league = con.execute(
            "SELECT round(avg(penalties), 2) FROM v_referee_games").fetchone()[0]
        rows = rows_to_dicts(con, """
            SELECT ref_key AS official_id, any_value(name) AS name,
                   sum(games)::int AS games,
                   min(season) AS first_season, max(season) AS last_season,
                   round(sum(pen_per_game * games) / sum(games), 2) AS pen_per_game,
                   round(sum(home_pen_bias * games) / sum(games), 2) AS home_pen_bias,
                   round(sum(avg_total_points * games) / sum(games), 1) AS avg_total,
                   round(sum(over_rate * games) / sum(games), 3) AS over_rate,
                   round(sum(home_win_rate * games) / sum(games), 3) AS home_win_rate,
                   round(sum(home_cover_rate * games) / sum(games), 3) AS home_cover_rate
            FROM v_referee_seasons
            GROUP BY ref_key HAVING sum(games) >= ?
            ORDER BY pen_per_game DESC
        """, [min_games])
    return {"league_avg_pen_per_game": league, "referees": rows}


@router.get("/api/referees/{official_id}")
def referee(official_id: str) -> dict:
    with read_conn() as con:
        seasons = rows_to_dicts(con, """
            SELECT season, games, pen_per_game, pen_yds_per_game, home_pen_bias,
                   avg_total_points, over_rate, home_win_rate, home_cover_rate,
                   any_value(name) AS name
            FROM v_referee_seasons WHERE ref_key = ?
            GROUP BY ALL ORDER BY season
        """, [official_id])
        if not seasons:
            raise HTTPException(404, "unknown official")
    return {"official_id": official_id, "name": seasons[-1]["name"], "seasons": seasons}
