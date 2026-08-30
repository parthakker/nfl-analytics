"""Smoke test: hit every Jarvis API endpoint and verify real data flows.

Uses the running server if one answers, otherwise starts a temporary one.
Each check requires NON-EMPTY data, not just HTTP 200. One summary line per
run goes to logs/smoke.log; failures list what broke.

Run:  python scripts/smoke_test.py     (or the Smoke test button on /ops)

SMOKE_BASE_URL overrides the target. The /ops runner sets it to the socket
the server actually bound, so running this from inside Jarvis reuses that
server instead of trying to start a second one on an occupied port.
"""

import os
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
BASE = os.environ.get("SMOKE_BASE_URL", "http://127.0.0.1:8000").rstrip("/")

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
    # betting rules engine (2026-08): every rule carries a backtest verdict
    "/api/rules": lambda js: (
        len(js.get("rules", [])) >= 8
        and all(isinstance(r.get("backtest_summary"), dict) for r in js["rules"])
    ),
    "/api/rules/wind-under-15/backtest": lambda js: len(js.get("seasons", [])) > 0,
    # Model Lab (2026-08): read-only over model_* tables; the fixture carries
    # them, so `available` must be true everywhere
    "/api/model/report": lambda js: (
        js.get("available") is True
        and isinstance(js["holdout"].get("brier_model"), float)
        and len(js.get("calibration", [])) >= 8
        and len(js.get("coefs", [])) >= 7
    ),
    "/api/model/ratings": lambda js: len(js.get("teams", [])) == 32,
    "/api/model/week": lambda js: (
        len(js.get("games", [])) > 0 and any(g.get("p_home_win") is not None for g in js["games"])
    ),
    "/api/model/experiments": lambda js: isinstance(js.get("runs"), list),
    "/api/knowledge": lambda js: len(js.get("chapters", [])) >= 10,
    "/api/knowledge/analytics-primer": lambda js: len(js.get("markdown", "")) > 1000,
    # ops registry (2026-08, replaced the Task Scheduler jobs). Deliberately
    # asserts only on the registry, never on log contents or live freshness:
    # LOGS_DIR is not env-overridable, so a fixture run reads the real logs/.
    "/api/ops/jobs": lambda js: (
        len(js.get("jobs", [])) >= 10
        and all(j.get("key") and j.get("script", "").startswith("scripts/") for j in js["jobs"])
        and "freshness" in js
        and "last_runs" in js
    ),
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
    spawn_log = None
    print(f"target: {BASE}")
    try:
        client.get(BASE + "/api/health", timeout=3)
        print("using the server already listening there")
    except Exception:
        print("nothing listening — starting a temporary server")
        # Capture the child's output to a real file rather than DEVNULL. When
        # this spawn failed (a port already taken, an import error) the reason
        # went straight to /dev/null and every check then reported a bare
        # ConnectError, which is how a run once logged 0/36 with no clue why.
        spawn_log = Path(tempfile.gettempdir()) / "nfl_smoke_uvicorn.log"
        sink = open(spawn_log, "w+", encoding="utf-8")
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
            stdout=sink,
            stderr=subprocess.STDOUT,
        )
        up = False
        for _ in range(20):
            time.sleep(1)
            if proc.poll() is not None:
                break  # it died; no point waiting out the full 20s
            try:
                client.get(BASE + "/api/health", timeout=2)
                up = True
                break
            except Exception:
                pass
        if not up:
            why = ""
            try:
                sink.flush()
                why = spawn_log.read_text(encoding="utf-8", errors="replace")[-1500:].strip()
            except OSError:
                pass
            print(f"temporary server never came up (exit={proc.poll()})")
            if why:
                print("--- uvicorn output ---")
                print(why)
                print("----------------------")

    try:
        failures = run_checks(client)
    finally:
        if proc:
            proc.kill()

    stamp = datetime.now().isoformat()
    passed = len(CHECKS) - len(failures)

    # The full list goes to stdout (the /ops console shows it live); the log
    # line gets a bounded version. A run where every endpoint failed the same
    # way used to append all 36 messages as one ~10 KB line, which is what
    # made logs/smoke.log unreadable and the "last run" summary useless.
    for f_ in failures:
        print(f"  FAIL {f_}")
    summary = "; ".join(failures)
    if len(summary) > 400:
        summary = summary[:400] + f" ... (+{len(failures)} failures, see stdout)"
    line = f"{stamp} smoke: {passed}/{len(CHECKS)} passed" + (
        f" | FAILURES: {summary}" if failures else ""
    )
    print(line)

    logs = ROOT / "logs"
    logs.mkdir(exist_ok=True)
    try:
        sys.path.insert(0, str(ROOT / "src"))
        from nfl_analytics.ops import rotate_log

        rotate_log(logs / "smoke.log", 128 * 1024)
    except Exception:
        pass  # rotation is housekeeping, never a reason to lose the result
    with open(logs / "smoke.log", "a", encoding="utf-8") as f:
        f.write(line + "\n")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
