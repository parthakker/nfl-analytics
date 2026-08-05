from fastapi import APIRouter

from ..deps import read_conn, team_tokens, teams_meta

router = APIRouter()


@router.get("/api/meta")
def meta() -> dict:
    with read_conn() as con:
        row = con.execute(
            "SELECT min(gameday) FROM schedules WHERE season = 2026 AND week = 1"
        ).fetchone()
    kickoff = row[0].isoformat() if row and row[0] else None
    teams = {}
    for code, t in teams_meta.TEAMS.items():
        tok = team_tokens(t[5])
        teams[code] = {
            "name": t[0],
            "conf": t[1],
            "div": t[2],
            "color": t[5],
            "tokens": tok,
            # `glow` is the old single colour the UI set as --accent. Kept one
            # wave so nothing 404s mid-migration. TODO(wave 5): delete.
            "glow": tok["ink"],
            "logo": teams_meta.logo_url(code),
        }
    return {"teams": teams, "divisions": teams_meta.DIVISIONS, "kickoff_2026": kickoff}
