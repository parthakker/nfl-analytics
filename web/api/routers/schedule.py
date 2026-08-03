from fastapi import APIRouter

from ..deps import read_conn, rows_to_dicts

router = APIRouter()


@router.get("/api/schedule")
def schedule(season: int = 2026, week: int | None = None) -> dict:
    with read_conn() as con:
        weeks = [r["week"] for r in rows_to_dicts(con,
            "SELECT DISTINCT week FROM schedules WHERE season=? ORDER BY week",
            [season])]
        if week is None:
            # default: first week with unplayed games, else last week
            row = con.execute("""
                SELECT min(week) FROM schedules WHERE season=? AND result IS NULL
            """, [season]).fetchone()
            week = row[0] if row and row[0] is not None else (weeks[-1] if weeks else 1)
        games = rows_to_dicts(con, """
            SELECT game_id, strftime(gameday, '%a %b %d') AS date, gametime,
                   away_team AS away, away_score, home_team AS home, home_score,
                   spread_line AS spread, total_line AS total,
                   home_moneyline AS home_ml
            FROM schedules WHERE season=? AND week=? ORDER BY gameday, gametime
        """, [season, week])
    return {"season": season, "week": week, "weeks": weeks, "games": games}
