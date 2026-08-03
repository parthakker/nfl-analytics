from fastapi import APIRouter, HTTPException

from ..deps import read_conn, rows_to_dicts

router = APIRouter()

# category -> (aggregate SQL, label); keys are the ONLY accepted values —
# user input never reaches the SQL string.
CATS = {
    "ppr": ("round(sum(fantasy_points_ppr),1)", "PPR points"),
    "half_ppr": ("round(sum(fantasy_points_half_ppr),1)", "Half-PPR points"),
    "std": ("round(sum(fantasy_points),1)", "Standard points"),
    "passing": ("sum(passing_yards)::int", "passing yards"),
    "rushing": ("sum(rushing_yards)::int", "rushing yards"),
    "receiving": ("sum(receiving_yards)::int", "receiving yards"),
}


@router.get("/api/leaders")
def leaders(season: int = 2025, cat: str = "ppr", min_games: int = 8) -> dict:
    if cat not in CATS:
        raise HTTPException(400, f"cat must be one of {list(CATS)}")
    agg, label = CATS[cat]
    with read_conn() as con:
        rows = rows_to_dicts(
            con,
            f"""
            SELECT player_display_name AS player, any_value(position) AS pos,
                   any_value(recent_team) AS team, count(*) AS games,
                   {agg} AS value
            FROM v_player_stats_week_all
            WHERE season = ? AND season_type = 'REG'
            GROUP BY player_display_name
            HAVING count(*) >= ? ORDER BY value DESC LIMIT 25
        """,
            [season, min_games],
        )
    return {"season": season, "cat": cat, "label": label, "rows": rows}
