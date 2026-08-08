"""Streaming chat: claude CLI (stream-json) -> Server-Sent Events.

One subprocess at a time (asyncio.Lock). Unknown stream-json line types are
skipped so CLI format evolution degrades gracefully; the `result` line is
always authoritative for the final text. Set CHAT_STREAMING=0 to force the
proven single-shot JSON path (same SSE contract, one big token).
"""

import asyncio
import json
import logging
import os
import re
import shutil

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from sse_starlette.sse import EventSourceResponse
from starlette.background import BackgroundTask

from ..deps import ROOT

log = logging.getLogger(__name__)

router = APIRouter()
_lock = asyncio.Lock()

TIMEOUT_S = 300

# session ids are echoed back into argv (--resume); if claude ever resolves
# to a .cmd shim, argv crosses cmd.exe's parser, so they must never carry
# shell metacharacters (defense-in-depth — real ids are UUIDs)
_SESSION_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,128}$")


def _claude_cmd(session_id: str | None, streaming: bool) -> list[str] | None:
    """argv for one claude invocation. The PROMPT IS NOT HERE on purpose:
    if `claude` resolves to a .cmd/.bat shim, argv goes through cmd.exe's
    parser and user text containing & | % would execute — the prompt travels
    over stdin instead (`claude -p` reads it when piped). Current installs
    ship a real claude.EXE, so the shim branch below is a safety net, not
    the normal path."""
    exe = shutil.which("claude")
    if not exe:
        return None
    cmd = [exe, "-p", "--allowedTools", "mcp__nfl"]
    if streaming:
        cmd += ["--output-format", "stream-json", "--verbose", "--include-partial-messages"]
    else:
        cmd += ["--output-format", "json"]
    if session_id:
        cmd += ["--resume", session_id]
    if exe.lower().endswith((".cmd", ".bat")):
        cmd = ["cmd", "/c"] + cmd
    return cmd


def _tool_hint(name: str) -> str:
    hints = {
        "query_warehouse": "querying the warehouse",
        "describe_warehouse": "reading the schema",
        "team_form": "pulling team form",
        "player_lookup": "looking up player",
        "predict_game": "running the model",
        "power_ratings": "reading power ratings",
        "kalshi_markets": "checking Kalshi markets",
        "kalshi_market_detail": "reading the orderbook",
        "kalshi_price_history": "loading price history",
        "player_news": "scanning news",
        "league_news": "scanning news",
        "data_status": "checking data freshness",
    }
    short = name.replace("mcp__nfl__", "")
    return hints.get(short, f"using {short}")


async def _pump(stream: asyncio.StreamReader, q: asyncio.Queue) -> None:
    """Read lines into a queue. Never cancelled mid-read (cancelling proactor
    pipe reads on Windows corrupts the stream — the original 'connection
    closed early' bug). EOF is signalled with None."""
    try:
        while True:
            line = await stream.readline()
            if not line:
                break
            await q.put(line)
    finally:
        await q.put(None)


async def _run_claude(message: str, session_id: str | None, streaming: bool):
    """Yield SSE events for one claude invocation. Raises nothing: all
    failures become 'error' events."""
    cmd = _claude_cmd(session_id, streaming)
    if cmd is None:
        yield {"event": "error", "data": json.dumps({"message": "claude CLI not found"})}
        return
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=str(ROOT),
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except Exception as e:
        yield {"event": "error", "data": json.dumps({"message": f"could not start claude: {e}"})}
        return
    # the pump must be draining stdout BEFORE the prompt is written: a prompt
    # larger than the pipe buffer would otherwise block drain() while claude
    # blocks writing stdout — mutual deadlock
    q: asyncio.Queue = asyncio.Queue()
    pump = asyncio.create_task(_pump(proc.stdout, q))
    try:
        proc.stdin.write(message.encode("utf-8"))
        await proc.stdin.drain()
        proc.stdin.close()
    except (BrokenPipeError, ConnectionResetError, OSError) as e:
        # claude died before reading the prompt; the EOF/stderr path below
        # turns that into a visible error event
        log.warning("chat: writing prompt to claude stdin failed: %s", e)
    got_done = False
    try:
        while True:
            try:
                line = await asyncio.wait_for(q.get(), timeout=10)
            except TimeoutError:
                # safe: only the queue-wait is cancelled, never the pipe read
                yield {"event": "ping", "data": "{}"}
                continue
            if line is None:
                break
            try:
                js = json.loads(line)
            except json.JSONDecodeError:
                continue
            t = js.get("type")
            if t == "system" and js.get("subtype") == "init":
                yield {"event": "session", "data": json.dumps({"session_id": js.get("session_id")})}
            elif t == "stream_event":
                delta = js.get("event", {}).get("delta", {})
                if delta.get("type") == "text_delta" and delta.get("text"):
                    yield {"event": "token", "data": json.dumps({"text": delta["text"]})}
            elif t == "assistant":
                for block in (js.get("message", {}) or {}).get("content", []):
                    if isinstance(block, dict) and block.get("type") == "tool_use":
                        yield {
                            "event": "tool",
                            "data": json.dumps(
                                {
                                    "name": block.get("name", ""),
                                    "hint": _tool_hint(block.get("name", "")),
                                }
                            ),
                        }
            elif t == "result":
                got_done = True
                yield {
                    "event": "done",
                    "data": json.dumps(
                        {
                            "text": js.get("result", ""),
                            "session_id": js.get("session_id"),
                            "duration_ms": js.get("duration_ms"),
                        }
                    ),
                }
        if not got_done:
            err = (await proc.stderr.read()).decode(errors="replace")[-500:]
            yield {
                "event": "error",
                "data": json.dumps({"message": err.strip() or "stream ended without a result"}),
            }
    except asyncio.CancelledError:
        raise
    except Exception as e:  # any parser/transport surprise -> visible error
        yield {"event": "error", "data": json.dumps({"message": f"{type(e).__name__}: {e}"})}
    finally:
        pump.cancel()
        if proc.returncode is None:
            proc.kill()
            try:
                await asyncio.wait_for(proc.wait(), timeout=5)
            except Exception as e:  # never mask the original exit path
                log.warning("chat: claude subprocess did not reap after kill: %s", e)


async def _stream_events(message: str, session_id: str | None):
    """Streaming first; if it fails before producing an answer, retry once
    with the proven single-shot JSON mode inside the same SSE response.

    Inner generators are aclosed explicitly (not left to GC) so that when WE
    are closed early — timeout, client disconnect — _run_claude's finally
    kills the subprocess deterministically."""
    streaming = os.environ.get("CHAT_STREAMING", "1") != "0"
    saw_answer = False
    failed = False
    inner = _run_claude(message, session_id, streaming)
    try:
        async for ev in inner:
            if ev["event"] == "done":
                saw_answer = True
            if ev["event"] == "error" and streaming and not saw_answer:
                failed = True
                yield {
                    "event": "tool",
                    "data": json.dumps(
                        {"name": "fallback", "hint": "stream hiccup — retrying in reliable mode"}
                    ),
                }
                break
            yield ev
    finally:
        await inner.aclose()
    if failed:
        inner = _run_claude(message, session_id, streaming=False)
        try:
            async for ev in inner:
                yield ev
        finally:
            await inner.aclose()


@router.post("/api/chat/stream")
async def chat_stream(request: Request):
    # no-CORS-preflight requests (text/plain form posts from any webpage)
    # must not be able to drive a subprocess-spawning endpoint
    ctype = request.headers.get("content-type", "")
    if ctype.split(";")[0].strip().lower() != "application/json":
        return JSONResponse({"error": "Content-Type must be application/json"}, status_code=415)
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid JSON body"}, status_code=400)
    message = (body.get("message") or "").strip()
    if not message:
        return JSONResponse({"error": "empty message"}, status_code=400)
    session_id = body.get("session_id") or None
    if session_id and not _SESSION_ID_RE.match(str(session_id)):
        return JSONResponse({"error": "bad session_id"}, status_code=400)

    # non-blocking acquire: locked() then acquire() has NO await between them,
    # so no other task can slip in — the old locked()-check-then-`async with`
    # let a second request queue behind the lock for up to TIMEOUT_S
    if _lock.locked():
        return JSONResponse(
            {"error": "the analyst is mid-thought — one question at a time"}, status_code=409
        )
    await _lock.acquire()  # uncontended fast path: returns without suspending

    # release must not depend on gen() being iterated: if the client vanishes
    # before sse-starlette starts the generator, gen's finally never runs and
    # the lock would wedge every later request into a 409. The response
    # background task runs on every teardown path, so release both ways,
    # idempotently.
    released = False

    def _release_once() -> None:
        nonlocal released
        if not released:
            released = True
            _lock.release()

    async def gen():
        try:
            async for ev in _with_timeout(_stream_events(message, session_id)):
                yield ev
        finally:
            _release_once()

    return EventSourceResponse(gen(), background=BackgroundTask(_release_once))


async def _with_timeout(agen):
    """Cap the stream at TIMEOUT_S. The finally acloses the inner generator on
    EVERY exit — timeout, client disconnect, exhaustion — which unwinds down
    to _run_claude's finally and kills the subprocess, instead of leaving that
    to async-generator GC."""
    start = asyncio.get_event_loop().time()
    try:
        async for item in agen:
            if asyncio.get_event_loop().time() - start > TIMEOUT_S:
                yield {
                    "event": "error",
                    "data": json.dumps({"message": f"timed out after {TIMEOUT_S}s"}),
                }
                return
            yield item
    finally:
        await agen.aclose()
