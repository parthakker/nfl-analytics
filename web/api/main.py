"""Jarvis web app: JSON API + built SPA, one port.

Dev:   python -m uvicorn web.api.main:app --port 8000 --reload --reload-dir web/api
       (+ `npm run dev` in web/ui for the frontend on :5173)
Prod:  python web/run_web.py  (serves web/ui/dist)
"""

import shutil
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from nfl_analytics.db import StoreBusyError

from .deps import read_conn
from .routers import (
    betting,
    chat,
    coaches,
    knowledge,
    leaders,
    league,
    markets,
    matchup,
    meta,
    news,
    players,
    referees,
    schedule,
    teams,
)

app = FastAPI(title="NFL Jarvis", docs_url="/api/docs", openapi_url="/api/openapi.json")

for _r in (
    meta,
    league,
    teams,
    players,
    leaders,
    schedule,
    news,
    markets,
    chat,
    coaches,
    referees,
    betting,
    matchup,
    knowledge,
):
    app.include_router(_r.router)


@app.exception_handler(StoreBusyError)
def busy_handler(request: Request, exc: StoreBusyError):
    return JSONResponse({"error": str(exc), "retryable": True}, status_code=503)


DIST = Path(__file__).resolve().parent.parent / "ui" / "dist"


@app.get("/api/health")
def health() -> dict:
    from nfl_analytics.config import KALSHI_DB, NEWS_DB, NFL_DB

    # configured paths, not hardcoded root files — env overrides (tests, CI
    # fixtures) must be honored
    dbs = {"nfl": NFL_DB.exists(), "news": NEWS_DB.exists(), "kalshi": KALSHI_DB.exists()}
    try:
        with read_conn() as con:
            con.execute("SELECT 1")
        dbs["nfl_readable"] = True
    except Exception:
        dbs["nfl_readable"] = False
    return {
        "ok": all(dbs.values()),
        "dbs": dbs,
        "claude": shutil.which("claude") is not None,
        "ui_built": (DIST / "index.html").exists(),
    }


if (DIST / "index.html").exists():
    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")

    @app.get("/{full_path:path}")
    def spa(full_path: str, request: Request):
        # SPA fallback: every non-API GET serves the app shell
        if full_path.startswith("api/"):
            return JSONResponse({"error": "not found"}, status_code=404)
        candidate = DIST / full_path
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(DIST / "index.html")
