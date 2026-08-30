import time
from functools import lru_cache

from fastapi import APIRouter

from ..deps import current_schedule_season, read_conn, team_tokens, teams_meta

router = APIRouter()


@lru_cache(maxsize=1)
def _teams_payload() -> dict:
    """Static per-team block (names, divisions, Oklab tokens, logos).

    32 Oklab conversions per request added up to nothing but heat — the
    inputs are constants, so compute once per process.
    """
    teams = {}
    for code, t in teams_meta.TEAMS.items():
        teams[code] = {
            "name": t[0],
            "conf": t[1],
            "div": t[2],
            "color": t[5],
            "tokens": team_tokens(t[5]),
            "logo": teams_meta.logo_url(code),
        }
    return teams


# kickoff moves once a year; cache the lookup with the same coarse TTL the
# season helpers use instead of hitting the DB per request
_KICKOFF_TTL_S = 3600.0
_kickoff_cache: tuple[float, str | None] | None = None


def _kickoff_iso() -> str | None:
    global _kickoff_cache
    now = time.monotonic()
    if _kickoff_cache is not None and now - _kickoff_cache[0] < _KICKOFF_TTL_S:
        return _kickoff_cache[1]
    season = current_schedule_season()
    with read_conn() as con:
        row = con.execute(
            "SELECT min(gameday) FROM schedules WHERE season = ? AND week = 1", [season]
        ).fetchone()
    kickoff = row[0].isoformat() if row and row[0] else None
    _kickoff_cache = (now, kickoff)
    return kickoff


def clear_cache() -> None:
    """Drop the kickoff lookup after a warehouse write (see deps.clear_season_cache).

    _teams_payload is deliberately NOT cleared: its inputs are module
    constants, so a rebuild cannot change it.
    """
    global _kickoff_cache
    _kickoff_cache = None


@router.get("/api/meta")
def meta() -> dict:
    return {
        "teams": _teams_payload(),
        "divisions": teams_meta.DIVISIONS,
        "kickoff": _kickoff_iso(),
    }
