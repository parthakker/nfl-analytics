"""Smoke test: hit every Jarvis API endpoint and verify real data flows.

Uses the running server on :8000 if present, otherwise starts a temporary
one. Each check requires NON-EMPTY data, not just HTTP 200. One summary
line per run goes to logs/smoke.log; failures list what broke.

Run:  python scripts/smoke_test.py        (scheduled daily 07:30)
"""

import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
BASE = "http://127.0.0.1:8000"

# endpoint -> predicate(json) that must be truthy for a PASS
CHECKS = {
    "/api/health": lambda js: js.get("ok") is True,
    "/api/meta": lambda js: len(js.get("teams", {})) == 32,
    "/api/league/overview": lambda js: (
        len(js.get("divisions", [])) == 8 and all(len(d["teams"]) == 4 for d in js["divisions"])
    ),
    "/api/teams/DET": lambda js: (
        js.get("record", {}).get("w") is not None and js.get("coach", {}).get("history")
    ),
    "/api/teams/DET/epa": lambda js: len(js.get("weeks", [])) >= 15,
    "/api/teams/DET/overview": lambda js: (
        len(js.get("leaders", [])) == 5
        and js.get("staff", {}).get("head_coach")
        and len(js.get("standings", [])) == 4
        and len(js.get("franchise", [])) > 0
    ),
    "/api/teams/DET/results?season=2024": lambda js: (
        len(js.get("rows", [])) >= 17
        and js["rows"][0].get("game_id")
        and js["rows"][-1].get("w_td") is not None
    ),
    "/api/teams/DET/roster": lambda js: len(js.get("players", [])) > 40,
    "/api/teams/DET/schedule": lambda js: len(js.get("games", [])) >= 17,
    "/api/teams/DET/news": lambda js: len(js.get("items", [])) > 0,
    "/api/players/search?q=mahomes": lambda js: len(js.get("hits", [])) > 0,
    # Mahomes' gsis_id — present in the full warehouse and the CI fixture slice
    "/api/players/00-0033873": lambda js: (
        js.get("info", {}).get("name") == "Patrick Mahomes"
        and len(js.get("seasons", [])) > 0
        and len(js.get("weekly", [])) > 0
        and js["seasons"][0].get("ppr") is not None
    ),
    "/api/leaders?family=rushing&sort=rush_yds": lambda js: (
        len(js.get("rows", [])) == 25
        and js["rows"][0].get("player_id")
        and len({r["player_id"] for r in js["rows"]}) == 25
    ),
    "/api/schedule?season=2026&week=1": lambda js: (
        len(js.get("games", [])) >= 14 and js["games"][0].get("game_id")
    ),
    "/api/news?limit=5": lambda js: len(js.get("items", [])) > 0,
    "/api/markets?kind=game": lambda js: len(js.get("markets", [])) > 0,
    # current-season Super Bowl market: lives all season in kalshi.duckdb and
    # the committed fixture. Bump the ticker year when the season rolls over.
    "/api/markets/KXSB-27-KC/history": lambda js: (
        js.get("title")
        and len(js.get("points", [])) > 0
        and any(p.get("prob") is not None for p in js["points"])
    ),
    "/api/leaders?family=fantasy&sort=ppr_pg&position=RB&qual=8": lambda js: (
        len(js.get("rows", [])) > 0
        and all(r["pos"] == "RB" for r in js["rows"])
        and js.get("qualified", 0) >= len(js["rows"])
        and "league_avg" in js
    ),
    "/api/leaders?family=defense&sort=sacks": lambda js: len(js.get("rows", [])) == 25,
    "/api/leaders?family=kicking": lambda js: (
        len(js.get("rows", [])) >= 20 and js["rows"][0].get("points") is not None
    ),
    "/api/referees?min_games=100": lambda js: len(js.get("referees", [])) >= 5,
    # detail keys on ref_key (canonical NAME, url-encoded) — active crew chief
    # since 2014, so he exists in both the full DB and the one-season fixture
    "/api/referees/CRAIG%20WROLSTAD": lambda js: (
        js.get("name")
        and len(js.get("seasons", [])) >= 1
        and js["seasons"][-1].get("games", 0) > 0
        and js["seasons"][-1].get("pen_per_game") is not None
    ),
    "/api/coaches": lambda js: len(js.get("coaches", [])) >= 50 and len(js.get("staff", [])) == 63,
    "/api/coaches/Steve%20Spagnuolo?role=DC": lambda js: (
        js.get("role") == "DC" and len(js.get("unit_seasons", [])) > 0
    ),
    "/api/coaches/Andy%20Reid": lambda js: (
        len(js.get("seasons", [])) >= 15 and len(js.get("fingerprint", [])) >= 4
    ),
    "/api/betting/board?week=1": lambda js: (
        len(js.get("games", [])) >= 14 and any(g.get("kalshi") for g in js["games"])
    ),
    "/api/betting/situations": lambda js: len(js.get("division_dogs", [])) > 0,
    "/api/news/search?q=injury": lambda js: len(js.get("items", [])) > 0,
    "/api/news?category=injury&limit=5": lambda js: len(js.get("items", [])) > 0,
    # matchup center (enrichment wave 2026-08)
    "/api/matchup/2024_01_BAL_KC": lambda js: (
        js.get("series", {}).get("games", 0) > 0
        and js["teams"]["away"]["travel_miles"] is not None
        and js.get("weather", {}).get("temp_f") is not None
        and js.get("referee", {}).get("career")
    ),
    "/api/matchup/2026_01_DEN_KC": lambda js: (
        js.get("game", {}).get("final") is False
        and js["teams"]["home"]["rest_days"] is not None
        and js["teams"]["away"]["travel_miles"] is not None
    ),
    "/api/matchup/h2h/BUF/MIA": lambda js: (
        js.get("summary", {}).get("games", 0) >= 50 and len(js.get("games", [])) >= 50
    ),
    "/api/knowledge": lambda js: len(js.get("chapters", [])) >= 10,
    "/api/knowledge/analytics-primer": lambda js: len(js.get("markdown", "")) > 1000,
}


def run_checks(client: httpx.Client) -> list[str]:
    failures = []
    for path, ok in CHECKS.items():
        try:
            r = client.get(BASE + path, timeout=30)
            if r.status_code == 503:  # store busy — one retry
                time.sleep(4)
                r = client.get(BASE + path, timeout=30)
            if r.status_code != 200:
                failures.append(f"{path}: HTTP {r.status_code} {r.text[:80]}")
            elif not ok(r.json()):
                failures.append(f"{path}: 200 but data check failed: {r.text[:100]}")
        except Exception as e:
            failures.append(f"{path}: {type(e).__name__} {str(e)[:80]}")
    return failures


def main() -> int:
    client = httpx.Client()
    proc = None
    try:
        client.get(BASE + "/api/health", timeout=3)
    except Exception:
        proc = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "web.api.main:app",
                "--port",
                "8000",
                "--log-level",
                "warning",
            ],
            cwd=str(ROOT),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        for _ in range(20):
            time.sleep(1)
            try:
                client.get(BASE + "/api/health", timeout=2)
                break
            except Exception:
                pass

    try:
        failures = run_checks(client)
    finally:
        if proc:
            proc.kill()

    stamp = datetime.now().isoformat()
    line = f"{stamp} smoke: {len(CHECKS) - len(failures)}/{len(CHECKS)} passed" + (
        f" | FAILURES: {'; '.join(failures)}" if failures else ""
    )
    print(line)
    logs = ROOT / "logs"
    logs.mkdir(exist_ok=True)
    with open(logs / "smoke.log", "a", encoding="utf-8") as f:
        f.write(line + "\n")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
