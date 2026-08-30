"""Manual maintenance jobs — the registry the /ops page and the MCP tools share.

Nothing in this project is scheduled any more. The five Task Scheduler jobs
were deleted because every one of them carried StartWhenAvailable with no idle
guard and no time limit, so waking the laptop fired every missed job at once —
an 18-minute headless Claude health check, a smoke test and two collectors,
all contending for the same DuckDB files.

This module is what replaced them:

  * a fixed registry of the maintenance scripts, keyed the same way as
    `cli.COMMANDS` so the two can never drift,
  * `argv()`, the whole allowlist — a URL segment never becomes a path or an
    argument, it only ever looks up a key,
  * run bookkeeping in `logs/ops_runs.jsonl`, because six of the ten jobs
    never wrote a log line of their own and log-tailing alone cannot say when
    `rebuild` or `audit` last ran,
  * log rotation, since nothing prunes `logs/` and `health_runner.log` was
    accumulating a full JSON transcript per run.

Pure stdlib + duckdb on purpose. `web/api/routers/ops.py` owns the async
subprocess transport and `mcp_server.py` calls `run_job_sync()`; both import
from here rather than from each other (the routers/rules.py convention).
"""

import json
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from .cli import COMMANDS
from .config import KALSHI_DB, LOGS_DIR, NEWS_DB, NFL_DB, ROOT
from .db import read_conn

RUNS_LOG = LOGS_DIR / "ops_runs.jsonl"

# The empty-string key is the default the UI selects, so every job has at
# least {"": ()} — "run it with no extra arguments".
NO_ARGS: dict[str, tuple[str, ...]] = {"": ()}


@dataclass(frozen=True)
class Job:
    key: str
    label: str
    blurb: str
    est_seconds: int
    writes: tuple[str, ...]  # stores it write-locks: nfl / kalshi / news
    timeout_s: int
    danger: bool  # UI requires a second click
    variants: dict[str, tuple[str, ...]] = field(default_factory=lambda: dict(NO_ARGS))
    log: str | None = None  # legacy logs/<name>.log to fall back on

    @property
    def script(self) -> str:
        """Always resolved through cli.COMMANDS — never hand-typed, so the
        `nfl <cmd>` dispatcher and this registry cannot disagree."""
        return COMMANDS[self.key][0]


# refresh --bootstrap is deliberately absent: ~2 GB and the better part of an
# hour is a terminal job, not something to hang a browser tab on.
JOBS: dict[str, Job] = {
    "refresh": Job(
        key="refresh",
        label="Refresh data",
        blurb="Download the latest nflverse releases, then rebuild the warehouse and views.",
        est_seconds=300,
        writes=("nfl", "kalshi"),
        timeout_s=1800,
        danger=True,
        variants={"": (), "full": ("--full",), "download": ("--no-rebuild",)},
        log="refresh",
    ),
    "rebuild": Job(
        key="rebuild",
        label="Rebuild warehouse",
        blurb="Rebuild nfl.duckdb from what is already in data/. No downloads.",
        est_seconds=60,
        writes=("nfl",),
        timeout_s=900,
        danger=True,
    ),
    "views": Job(
        key="views",
        label="Rebuild views",
        blurb="Recreate the derived v_* views and re-run the sanity checks.",
        est_seconds=40,
        writes=("nfl",),
        timeout_s=900,
        danger=True,
    ),
    "weather": Job(
        key="weather",
        label="Fetch weather",
        blurb="Open-Meteo forecasts for upcoming games; backfill walks history.",
        est_seconds=45,
        writes=(),
        timeout_s=900,
        danger=False,
        variants={"": (), "backfill": ("--backfill",)},
    ),
    "news": Job(
        key="news",
        label="Poll news",
        blurb="ESPN news + injuries and the PFT/Yahoo feeds into news.duckdb.",
        est_seconds=20,
        writes=("news",),
        timeout_s=300,
        danger=False,
        log="news",
    ),
    "kalshi": Job(
        key="kalshi",
        label="Snapshot Kalshi",
        blurb="Snapshot open Kalshi markets. Perishable — a missed window is gone.",
        est_seconds=25,
        writes=("kalshi",),
        timeout_s=300,
        danger=False,
        log="kalshi",
    ),
    "smoke": Job(
        key="smoke",
        label="Smoke test",
        blurb="Hit every API endpoint and require real data, not just HTTP 200.",
        est_seconds=20,
        writes=(),
        timeout_s=600,
        danger=False,
        log="smoke",
    ),
    "audit": Job(
        key="audit",
        label="Data audit",
        blurb="Completeness audit across every table into docs/data_audit.md.",
        est_seconds=20,
        writes=(),
        timeout_s=900,
        danger=False,
    ),
    "train": Job(
        key="train",
        label="Train model",
        blurb="Retrain and validate the prediction model. Overwrites model_* tables.",
        est_seconds=600,
        writes=("nfl",),
        timeout_s=3600,
        danger=True,
    ),
    "experiment": Job(
        key="experiment",
        label="Model experiment",
        blurb="One configuration through the holdout in seconds; logs the scorecard. "
        "Nothing is persisted. Free-form flags: `nfl experiment` in a terminal.",
        est_seconds=10,
        writes=(),
        timeout_s=300,
        danger=False,
        variants={
            "": (),
            "no-qb": ("--features", "-d_qb_out", "--note", "ops: without QB flag"),
            "no-rest": ("--features", "-d_rest", "--note", "ops: without rest edge"),
            "hl12": ("--half-life", "12", "--note", "ops: half-life 12"),
            "rest-sched": (
                "--features",
                "+d_rest_sched,-d_rest",
                "--note",
                "ops: schedule rest instead of lag rest",
            ),
            "drift": ("--recency", "6", "--calib-window", "6", "--note", "ops: drift controls"),
        },
    ),
    "recap": Job(
        key="recap",
        label="Model recap",
        blurb="Export the model recap workbook to the Desktop.",
        est_seconds=20,
        writes=(),
        timeout_s=300,
        danger=False,
    ),
    "fixture": Job(
        key="fixture",
        label="Rebuild CI fixture",
        blurb="Regenerate the committed test fixture DBs from the real ones.",
        est_seconds=120,
        writes=(),
        timeout_s=900,
        danger=False,
    ),
}


# ── argv allowlist ───────────────────────────────────────────────────────────


def argv(job_key: str, variant: str = "") -> list[str]:
    """Build the child argv for a job.

    This is the entire allowlist. `job_key` and `variant` are dict lookups — a
    caller-supplied string is never joined into a path, never handed to a
    shell, and never appended to argv. Anything unrecognised raises KeyError,
    which the router turns into a 404 or a 400.
    """
    job = JOBS[job_key]
    extras = job.variants[variant]
    return [sys.executable, str(ROOT / job.script), *extras]


def child_env(extra: dict[str, str] | None = None) -> dict[str, str]:
    """Environment for a spawned job.

    PYTHONIOENCODING: several build scripts print non-ASCII status glyphs. A
    child whose stdout is a pipe rather than a console falls back to the ANSI
    codepage on Windows and dies with UnicodeEncodeError partway through a
    rebuild.

    PYTHONUNBUFFERED: without it a piped Python child block-buffers stdout, so
    a "live" console shows nothing for fifteen minutes and then everything at
    once — which defeats the point of streaming the output at all.
    """
    env = {
        **os.environ,
        "PYTHONIOENCODING": "utf-8",
        "PYTHONUNBUFFERED": "1",
        "NFL_OPS_CHILD": "1",
    }
    if extra:
        env.update(extra)
    return env


# ── log rotation ─────────────────────────────────────────────────────────────

# (filename, cap in bytes). health_runner.log is the one that actually grew
# without bound — nightly_health.cmd appended the full JSON result of every
# headless Claude run to it.
ROTATE_CAPS: tuple[tuple[str, int], ...] = (
    ("health_runner.log", 256 * 1024),
    ("smoke.log", 128 * 1024),
    ("jarvis.log", 1024 * 1024),
    ("health.log", 128 * 1024),
    ("refresh.log", 128 * 1024),
    ("news.log", 128 * 1024),
    ("kalshi.log", 128 * 1024),
)

RUNS_LOG_MAX_LINES = 500


def rotate_log(path: Path, max_bytes: int) -> bool:
    """Roll `x.log` to `x.log.1` once it exceeds the cap. One generation is
    plenty — these are diagnostic tails, not an audit trail.

    Never raises: a log held open by a running writer is skipped and retried
    on the next call rather than failing the request that triggered it.
    """
    try:
        if not path.exists() or path.stat().st_size <= max_bytes:
            return False
        backup = path.with_suffix(path.suffix + ".1")
        backup.unlink(missing_ok=True)
        path.rename(backup)
        return True
    except OSError:
        return False


def _trim_runs_log() -> None:
    try:
        if not RUNS_LOG.exists():
            return
        lines = RUNS_LOG.read_text(encoding="utf-8", errors="replace").splitlines()
        if len(lines) <= RUNS_LOG_MAX_LINES:
            return
        RUNS_LOG.write_text("\n".join(lines[-RUNS_LOG_MAX_LINES:]) + "\n", encoding="utf-8")
    except OSError:
        pass


def rotate_all() -> list[str]:
    """Apply every cap. Called on each status read, so rotation happens
    without anything scheduled."""
    rotated = [name for name, cap in ROTATE_CAPS if rotate_log(LOGS_DIR / name, cap)]
    _trim_runs_log()
    return rotated


# ── run bookkeeping ──────────────────────────────────────────────────────────

TAIL_CHARS = 2000
SUMMARY_CHARS = 300


def record_run(
    job_key: str, variant: str, exit_code: int, duration_s: float, tail: str = ""
) -> None:
    """Append one line to logs/ops_runs.jsonl.

    Six of the ten jobs write no log of their own, so without this the UI
    could not show when `rebuild`, `views`, `audit`, `weather`, `train` or
    `fixture` last ran.
    """
    row = {
        "ts": datetime.now(UTC).isoformat(timespec="seconds"),
        "job": job_key,
        "variant": variant,
        "exit_code": exit_code,
        "duration_s": round(duration_s, 1),
        "tail": (tail or "")[-TAIL_CHARS:],
    }
    try:
        LOGS_DIR.mkdir(exist_ok=True)
        with open(RUNS_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(row) + "\n")
    except OSError:
        pass  # bookkeeping must never break the run it is recording


# the legacy one-line-per-run logs all lead with an ISO timestamp
_LEGACY_LINE = re.compile(r"^(?P<ts>\d{4}-\d{2}-\d{2}[T ][\d:.]+Z?)\s+(?P<summary>.*)$")


def _legacy_ok(summary: str) -> bool | None:
    """Best-effort verdict from a legacy log line. None means "can't tell"."""
    if m := re.search(r"\brc=(\d+)", summary):
        return m.group(1) == "0"
    if m := re.search(r"\bfailures=(\d+)", summary):
        return m.group(1) == "0"
    if m := re.search(r"(\d+)/(\d+) passed", summary):
        return m.group(1) == m.group(2)
    if "HEALTHY" in summary:
        return True
    if "DEGRADED" in summary or "BROKEN" in summary:
        return False
    return None


def _age_hours(ts_iso: str) -> float | None:
    """Hours since `ts_iso`.

    A naive timestamp is LOCAL, not UTC: the legacy job logs were written with
    a bare `datetime.now().isoformat()`, so reading them as UTC put every age
    out by the machine's offset. `record_run` writes an explicit offset, so
    entries it produces take the aware branch instead.
    """
    try:
        ts = datetime.fromisoformat(ts_iso.replace("Z", "+00:00").replace(" ", "T"))
    except ValueError:
        return None
    if ts.tzinfo is None:
        ts = ts.astimezone()
    return round((datetime.now(UTC) - ts).total_seconds() / 3600, 1)


def _legacy_last_run(job: Job) -> dict | None:
    if not job.log:
        return None
    path = LOGS_DIR / f"{job.log}.log"
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if not lines:
        return None
    m = _LEGACY_LINE.match(lines[-1])
    if not m:
        return None
    summary = m.group("summary")
    return {
        "ts": m.group("ts"),
        "age_hours": _age_hours(m.group("ts")),
        # one failing smoke run wrote every failure onto a single 10 KB line
        "summary": summary[:SUMMARY_CHARS],
        "ok": _legacy_ok(summary),
        "source": "log",
    }


def _ops_summary(row: dict) -> str:
    tail = (row.get("tail") or "").strip()
    if tail:
        return tail.splitlines()[-1][:SUMMARY_CHARS]
    return f"exit {row.get('exit_code')}"


def last_runs() -> dict[str, dict]:
    """Newest run per job: ops_runs.jsonl first, legacy log tail as fallback."""
    out: dict[str, dict] = {}
    try:
        raw = RUNS_LOG.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        raw = []
    for line in raw:
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        key = row.get("job")
        if key in JOBS:
            out[key] = {
                "ts": row.get("ts"),
                "age_hours": _age_hours(row.get("ts") or ""),
                "summary": _ops_summary(row),
                "ok": row.get("exit_code") == 0,
                "duration_s": row.get("duration_s"),
                "variant": row.get("variant", ""),
                "source": "ops",
            }
    for key, job in JOBS.items():
        if key not in out:
            legacy = _legacy_last_run(job)
            if legacy:
                out[key] = legacy
    return out


# ── freshness ────────────────────────────────────────────────────────────────


def _mtime_info(path: Path) -> dict:
    """File mtimes work even when the store is write-locked, so this block
    never goes blank while a rebuild is running."""
    try:
        st = path.stat()
    except OSError:
        return {"exists": False, "mb": None, "modified": None, "age_hours": None}
    ts = datetime.fromtimestamp(st.st_mtime, UTC)
    return {
        "exists": True,
        "mb": round(st.st_size / 1_000_000, 1),
        "modified": ts.isoformat(timespec="seconds"),
        "age_hours": _age_hours(ts.isoformat()),
    }


def freshness() -> dict:
    """Coverage plus store ages. Every DB touch is guarded: a locked or
    missing store degrades to an `error` key instead of blanking the page."""
    out: dict = {
        "files": {
            "nfl": _mtime_info(NFL_DB),
            "kalshi": _mtime_info(KALSHI_DB),
            "news": _mtime_info(NEWS_DB),
        }
    }
    try:
        with read_conn(attach_kalshi=True, attach_news=True) as con:
            row = con.execute(
                """
                SELECT max(season),
                       max(week) FILTER (WHERE season = (SELECT max(season) FROM play_by_play))
                FROM play_by_play
                """
            ).fetchone()
            out["warehouse"] = {"season": row[0], "week": row[1]}
            out["schedules_season"] = con.execute("SELECT max(season) FROM schedules").fetchone()[0]
            try:
                snaps = con.execute(
                    "SELECT count(*), max(snapshot_ts) FROM kalshi.kalshi_snapshots"
                ).fetchone()
                out["kalshi"] = {
                    "snapshots": snaps[0],
                    "latest": str(snaps[1]) if snaps[1] else None,
                }
            except Exception as e:
                out["kalshi"] = {"error": str(e)[:200]}
            try:
                nrow = con.execute("SELECT count(*), max(published_ts) FROM newsdb.news").fetchone()
                out["news"] = {"items": nrow[0], "latest": str(nrow[1]) if nrow[1] else None}
            except Exception as e:
                out["news"] = {"error": str(e)[:200]}
    except Exception as e:
        out["error"] = str(e)[:300]
    return out


# ── payload + synchronous runner ─────────────────────────────────────────────


def job_view(job: Job) -> dict:
    return {
        "key": job.key,
        "label": job.label,
        "blurb": job.blurb,
        "script": job.script,
        "est_seconds": job.est_seconds,
        "writes": list(job.writes),
        "danger": job.danger,
        "timeout_s": job.timeout_s,
        "variants": sorted(job.variants),
    }


TAIL_LINES = 3


def log_tails(
    names: tuple[str, ...] = ("refresh", "news", "kalshi", "smoke", "health", "jarvis"),
) -> dict[str, str]:
    """Last few lines of each legacy job log, for the MCP data_status tool."""
    out: dict[str, str] = {}
    for name in names:
        path = LOGS_DIR / f"{name}.log"
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            out[name] = "never run"
            continue
        tail = [ln[:SUMMARY_CHARS] for ln in lines[-TAIL_LINES:] if ln.strip()]
        out[name] = "\n".join(tail) if tail else "never run"
    return out


def status_payload() -> dict:
    """Everything GET /api/ops/jobs returns, minus the `running` block the
    router owns. Flat dict of named lists and objects, per the API rules."""
    rotate_all()
    return {
        "jobs": [job_view(j) for j in JOBS.values()],
        "freshness": freshness(),
        "last_runs": last_runs(),
        "running": None,
    }


def run_job_sync(job_key: str, variant: str = "") -> dict:
    """Blocking run — for the MCP tools, which have no streaming transport.

    The /ops page uses the async streaming runner in web/api/routers/ops.py;
    both record into the same ops_runs.jsonl, so a refresh started from chat
    still shows up on the page.
    """
    job = JOBS[job_key]
    cmd = argv(job_key, variant)
    started = time.monotonic()
    try:
        r = subprocess.run(
            cmd,
            cwd=str(ROOT),
            env=child_env(),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=job.timeout_s,
        )
    except subprocess.TimeoutExpired:
        duration = time.monotonic() - started
        record_run(job_key, variant, -1, duration, "timed out")
        return {
            "exit_code": -1,
            "output_tail": "",
            "errors": f"{job_key} timed out after {job.timeout_s}s",
            "duration_s": round(duration, 1),
        }
    duration = time.monotonic() - started
    record_run(job_key, variant, r.returncode, duration, r.stdout or "")
    return {
        "exit_code": r.returncode,
        "output_tail": (r.stdout or "")[-3000:],
        "errors": (r.stderr or "")[-1000:] if r.returncode else "",
        "duration_s": round(duration, 1),
    }
