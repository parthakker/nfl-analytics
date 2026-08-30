"""Operations: run a maintenance job by hand and stream its output.

This replaced the five Task Scheduler jobs. The transport is modelled closely
on routers/chat.py — the same non-blocking lock, the same double-released
BackgroundTask, the same never-cancel-a-pipe-read pump — because those details
were each paid for by a real Windows bug and the failure modes here are
identical. Read that file before changing this one.

Two things this endpoint has that chat does not, because it mutates:
  * a stricter front door (loopback-only, JSON-only, same-origin), since a
    stray cross-site POST here would kick off a warehouse rebuild;
  * the maintenance gate, which holds API reads off nfl.duckdb so the
    atomic swap at the end of a rebuild cannot fail on a sharing violation.

Every job name and argument is a lookup in nfl_analytics.ops — no caller
string ever reaches argv.
"""

import asyncio
import json
import logging
import os
import time

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from sse_starlette.sse import EventSourceResponse
from starlette.background import BackgroundTask

from nfl_analytics import ops

from ..deps import ROOT, clear_season_cache
from ..middleware import gate

log = logging.getLogger(__name__)

router = APIRouter()
_lock = asyncio.Lock()
_current: dict | None = None

# how long to wait for in-flight readers to drain before a warehouse write
DRAIN_TIMEOUT_S = 10.0
# a full refresh prints far more than a browser should render
MAX_STREAMED_LINES = 5000


def _running_view() -> dict | None:
    """Public shape of `_current` — the underscore-prefixed bookkeeping keys
    are internal and must not reach the wire."""
    if _current is None:
        return None
    view = {k: v for k, v in _current.items() if not k.startswith("_")}
    view["elapsed_s"] = round(time.monotonic() - _current["_started"], 1)
    return view


@router.get("/api/ops/jobs")
def ops_jobs() -> dict:
    """Registry, freshness and last-run status. GET so it is smoke-checkable —
    the POST below cannot be, since CHECKS only issues GETs."""
    return {**ops.status_payload(), "running": _running_view()}


def _clear_warehouse_caches() -> None:
    """Three independent 1-hour TTL caches would otherwise keep serving
    pre-rebuild answers for up to an hour after a refresh."""
    from nfl_analytics import rules as rules_mod

    from . import meta as meta_mod

    for fn in (clear_season_cache, meta_mod.clear_cache, rules_mod.clear_cache):
        try:
            fn()
        except Exception as e:  # a cache that will not clear must not fail the run
            log.warning("ops: cache clear failed (%s): %s", getattr(fn, "__name__", fn), e)


async def _pump(stream: asyncio.StreamReader, q: asyncio.Queue, tag: str) -> None:
    """Read lines into a queue. Never cancelled mid-read — cancelling proactor
    pipe reads on Windows corrupts the stream. EOF is signalled with None."""
    try:
        while True:
            line = await stream.readline()
            if not line:
                break
            await q.put((tag, line))
    finally:
        await q.put((tag, None))


async def _drain_readers():
    """Wait for in-flight API reads to finish so nothing in this process holds
    nfl.duckdb open when build_warehouse does its os.replace. Yields progress
    lines so a slow drain is visible in the console rather than looking hung."""
    deadline = time.monotonic() + DRAIN_TIMEOUT_S
    while gate.readers > 0 and time.monotonic() < deadline:
        yield f"waiting for {gate.readers} in-flight request(s) to finish"
        await asyncio.sleep(0.25)
    if gate.readers > 0:
        yield (
            f"proceeding with {gate.readers} request(s) still open — "
            "the rebuild retries the final swap if it is blocked"
        )


async def _run_job(job_key: str, variant: str, base_url: str | None):
    """Yield SSE events for one job. Raises nothing: failures become events."""
    job = ops.JOBS[job_key]
    try:
        cmd = ops.argv(job_key, variant)
    except KeyError as e:  # already validated, but never build a path on a guess
        yield {"event": "error", "data": json.dumps({"message": f"unknown job/variant: {e}"})}
        return

    env_extra: dict[str, str] = {}
    if job_key == "smoke" and base_url:
        # point the smoke test at the socket we actually bound, so it reuses
        # this server instead of failing to start a second one on the port
        env_extra["SMOKE_BASE_URL"] = base_url

    # tests and the e2e spec set this so exercising the transport never kicks
    # off a real rebuild. Nothing caller-supplied is interpolated into the -c.
    dry = os.environ.get("NFL_OPS_DRY_RUN") == "1"
    if dry:
        cmd = [cmd[0], "-c", "print('dry run ok')"]

    lines_out: list[str] = []

    if "nfl" in job.writes and not dry:
        gate.raise_for(job.label)
        async for msg in _drain_readers():
            yield {"event": "line", "data": json.dumps({"text": msg, "stream": "ops"})}

    started = time.monotonic()
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=str(ROOT),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=ops.child_env(env_extra),
        )
    except Exception as e:
        yield {"event": "error", "data": json.dumps({"message": f"could not start {job_key}: {e}"})}
        return

    if _current is not None:
        _current["pid"] = proc.pid  # mutation, not rebinding — no `global` needed

    q: asyncio.Queue = asyncio.Queue()
    pumps = [
        asyncio.create_task(_pump(proc.stdout, q, "stdout")),
        asyncio.create_task(_pump(proc.stderr, q, "stderr")),
    ]
    open_streams = 2
    emitted = 0
    truncated = False
    try:
        while open_streams:
            try:
                tag, raw = await asyncio.wait_for(q.get(), timeout=10)
            except TimeoutError:
                # safe: only the queue-wait is cancelled, never the pipe read
                yield {"event": "ping", "data": "{}"}
                continue
            if raw is None:
                open_streams -= 1
                continue
            text = raw.decode("utf-8", "replace").rstrip("\r\n")
            lines_out.append(text)
            if len(lines_out) > 400:
                del lines_out[:200]
            emitted += 1
            if emitted <= MAX_STREAMED_LINES:
                yield {"event": "line", "data": json.dumps({"text": text, "stream": tag})}
            elif not truncated:
                truncated = True
                yield {
                    "event": "line",
                    "data": json.dumps(
                        {
                            "text": f"— output past {MAX_STREAMED_LINES} lines is not shown; "
                            "the job is still running —",
                            "stream": "ops",
                        }
                    ),
                }

        rc = await proc.wait()
        duration = time.monotonic() - started
        ops.record_run(job_key, variant, rc, duration, "\n".join(lines_out))
        yield {
            "event": "done",
            "data": json.dumps(
                {
                    "exit_code": rc,
                    "duration_s": round(duration, 1),
                    "lines": emitted,
                    "truncated": truncated,
                }
            ),
        }
    except asyncio.CancelledError:
        raise
    except Exception as e:
        yield {"event": "error", "data": json.dumps({"message": f"{type(e).__name__}: {e}"})}
    finally:
        for p in pumps:
            p.cancel()
        if proc.returncode is None:
            proc.kill()
            try:
                await asyncio.wait_for(proc.wait(), timeout=5)
            except Exception as e:  # never mask the original exit path
                log.warning("ops: %s did not reap after kill: %s", job_key, e)


async def _with_timeout(agen, seconds: float):
    """Cap the stream. The finally acloses the inner generator on EVERY exit —
    timeout, client disconnect, Stop button — which unwinds to _run_job's
    finally and kills the subprocess rather than leaving it to GC."""
    start = asyncio.get_event_loop().time()
    try:
        async for item in agen:
            if asyncio.get_event_loop().time() - start > seconds:
                yield {
                    "event": "error",
                    "data": json.dumps({"message": f"timed out after {int(seconds)}s"}),
                }
                return
            yield item
    finally:
        await agen.aclose()


def _origin_ok(request: Request) -> bool:
    origin = request.headers.get("origin")
    if not origin:
        return True  # same-origin fetches and curl send none
    host = request.headers.get("host", "")
    allowed = {f"http://{host}", f"https://{host}"}
    # the Vite dev server proxies /api from :5173
    allowed |= {"http://localhost:5173", "http://127.0.0.1:5173"}
    return origin in allowed


@router.post("/api/ops/run/{job}")
async def ops_run(job: str, request: Request):
    # Belt-and-braces: run_web.py already binds 127.0.0.1. "testclient" is
    # Starlette's TestClient peer name — safe to allow, since this value comes
    # from the socket peer and not from a header, so it cannot be spoofed.
    client_host = request.client.host if request.client else ""
    if client_host not in ("127.0.0.1", "::1", "localhost", "testclient"):
        return JSONResponse({"error": "ops is loopback-only"}, status_code=403)

    # a no-preflight text/plain form post from any page must not be able to
    # start a warehouse rebuild
    ctype = request.headers.get("content-type", "")
    if ctype.split(";")[0].strip().lower() != "application/json":
        return JSONResponse({"error": "Content-Type must be application/json"}, status_code=415)
    if not _origin_ok(request):
        return JSONResponse({"error": "cross-origin request refused"}, status_code=403)

    if job not in ops.JOBS:
        return JSONResponse({"error": f"unknown job: {job}"}, status_code=404)
    try:
        body = await request.json()
    except Exception:
        body = {}
    variant = (body or {}).get("variant") or ""
    if variant not in ops.JOBS[job].variants:
        return JSONResponse({"error": f"unknown variant: {variant}"}, status_code=400)

    # non-blocking acquire: locked() then acquire() has NO await between them,
    # so no other request can slip in. Jobs contend on the DB and the CPU, so
    # the lock is global rather than per-job.
    if _lock.locked():
        running = _running_view()
        return JSONResponse(
            {
                "error": f"{running['label'] if running else 'a job'} is already running",
                "running": running,
            },
            status_code=409,
        )
    await _lock.acquire()

    global _current
    _current = {
        "job": job,
        "label": ops.JOBS[job].label,
        "variant": variant,
        "pid": None,
        "_started": time.monotonic(),
    }

    server = request.scope.get("server")
    base_url = f"http://{server[0]}:{server[1]}" if server else None

    # release must not depend on gen() being iterated: if the client vanishes
    # before sse-starlette starts the generator, gen's finally never runs and
    # the lock would wedge every later request into a 409.
    released = False

    def _release_once() -> None:
        nonlocal released
        if released:
            return
        released = True
        global _current
        was_warehouse = "nfl" in ops.JOBS[job].writes
        _current = None
        gate.lower()
        if was_warehouse:
            _clear_warehouse_caches()
        _lock.release()

    async def generate():
        try:
            async for ev in _with_timeout(
                _run_job(job, variant, base_url), ops.JOBS[job].timeout_s
            ):
                yield ev
        finally:
            _release_once()

    return EventSourceResponse(generate(), background=BackgroundTask(_release_once))
