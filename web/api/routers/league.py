from fastapi import APIRouter

from ..deps import read_conn, rows_to_dicts, teams_meta

router = APIRouter()


@router.get("/api/league/overview")
def overview(season: int = 2025) -> dict:
    with read_conn() as con:
        recs = {r["team"]: r for r in rows_to_dicts(con, """
            SELECT team, count(*) AS g, sum(win)::int AS w,
                   round(avg(points_for), 1) AS pf_pg,
                   round(avg(points_against), 1) AS pa_pg
            FROM v_team_games
            WHERE season = ? AND season_type = 'REG'
            GROUP BY team
        """, [season])}
    divisions = []
    for div_name, codes in teams_meta.DIVISIONS.items():
        teams = []
        for code in codes:
            r = recs.get(code, {})
            teams.append({"code": code,
                          "w": r.get("w", 0), "l": (r.get("g", 0) or 0) - (r.get("w", 0) or 0),
                          "pf_pg": r.get("pf_pg"), "pa_pg": r.get("pa_pg")})
        teams.sort(key=lambda t: -(t["w"] or 0))
        divisions.append({"name": div_name, "teams": teams})
    return {"season": season, "divisions": divisions}
