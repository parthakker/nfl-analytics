from fastapi import APIRouter

from ..deps import glow_safe, read_conn, teams_meta

router = APIRouter()


@router.get("/api/meta")
def meta() -> dict:
    with read_conn() as con:
        row = con.execute(
            "SELECT min(gameday) FROM schedules WHERE season = 2026 AND week = 1"
        ).fetchone()
    kickoff = row[0].isoformat() if row and row[0] else None
    teams = {
        code: {
            "name": t[0], "conf": t[1], "div": t[2],
            "color": t[5], "glow": glow_safe(t[5]),
            "logo": teams_meta.logo_url(code),
        }
        for code, t in teams_meta.TEAMS.items()
    }
    return {"teams": teams, "divisions": teams_meta.DIVISIONS,
            "kickoff_2026": kickoff}
