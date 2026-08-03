"""Streaming chat: claude CLI (stream-json) -> Server-Sent Events.

One subprocess at a time (asyncio.Lock). Unknown stream-json line types are
skipped so CLI format evolution degrades gracefully; the `result` line is
always authoritative for the final text. Set CHAT_STREAMING=0 to force the
proven single-shot JSON path (same SSE contract, one big token).
"""

import asyncio
import json
import os
import shutil

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from sse_starlette.sse import EventSourceResponse

from ..deps import ROOT

router = APIRouter()
_lock = asyncio.Lock()

TIMEOUT_S = 300


def _claude_cmd(message: str, session_id: str | None, streaming: bool) -> list[str] | None:
    exe = shutil.which("claude")
    if not exe:
        return None
    cmd = [exe, "-p", message, "--allowedTools", "mcp__nfl"]
    if streaming:
        cmd += ["--output-format", "stream-json", "--verbose",
                "--include-partial-messages"]
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
    cmd = _claude_cmd(message, session_id, streaming)
    if cmd is None:
        yield {"event": "error", "data": json.dumps({"message": "claude CLI not found"})}
        return
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd, cwd=str(ROOT),
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    except Exception as e:
        yield {"event": "error",
               "data": json.dumps({"message": f"could not start claude: {e}"})}
        return

    q: asyncio.Queue = asyncio.Queue()
    pump = asyncio.create_task(_pump(proc.stdout, q))
    got_done = False
    try:
        while True:
            try:
                line = await asyncio.wait_for(q.get(), timeout=10)
            except asyncio.TimeoutError:
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
                yield {"event": "session",
                       "data": json.dumps({"session_id": js.get("session_id")})}
            elif t == "stream_event":
                delta = js.get("event", {}).get("delta", {})
                if delta.get("type") == "text_delta" and delta.get("text"):
                    yield {"event": "token",
                           "data": json.dumps({"text": delta["text"]})}
            elif t == "assistant":
                for block in (js.get("message", {}) or {}).get("content", []):
                    if isinstance(block, dict) and block.get("type") == "tool_use":
                        yield {"event": "tool",
                               "data": json.dumps({"name": block.get("name", ""),
                                                   "hint": _tool_hint(block.get("name", ""))})}
            elif t == "result":
                got_done = True
                yield {"event": "done",
                       "data": json.dumps({"text": js.get("result", ""),
                                           "session_id": js.get("session_id"),
                                           "duration_ms": js.get("duration_ms")})}
        if not got_done:
            err = (await proc.stderr.read()).decode(errors="replace")[-500:]
            yield {"event": "error",
                   "data": json.dumps({"message": err.strip() or
                                       "stream ended without a result"})}
    except asyncio.CancelledError:
        raise
    except Exception as e:  # any parser/transport surprise -> visible error
        yield {"event": "error", "data": json.dumps({"message": f"{type(e).__name__}: {e}"})}
    finally:
        pump.cancel()
        if proc.returncode is None:
            proc.kill()


async def _stream_events(message: str, session_id: str | None):
    """Streaming first; if it fails before producing an answer, retry once
    with the proven single-shot JSON mode inside the same SSE response."""
    streaming = os.environ.get("CHAT_STREAMING", "1") != "0"
    saw_answer = False
    failed = False
    async for ev in _run_claude(message, session_id, streaming):
        if ev["event"] == "done":
            saw_answer = True
        if ev["event"] == "error" and streaming and not saw_answer:
            failed = True
            yield {"event": "tool",
                   "data": json.dumps({"name": "fallback",
                                       "hint": "stream hiccup — retrying in reliable mode"})}
            break
        yield ev
    if failed:
        async for ev in _run_claude(message, session_id, streaming=False):
            yield ev


@router.post("/api/chat/stream")
async def chat_stream(request: Request):
    body = await request.json()
    message = (body.get("message") or "").strip()
    if not message:
        return JSONResponse({"error": "empty message"}, status_code=400)
    if _lock.locked():
        return JSONResponse(
            {"error": "the analyst is mid-thought — one question at a time"},
            status_code=409)

    session_id = body.get("session_id") or None

    async def gen():
        async with _lock:
            async for ev in _with_timeout(_stream_events(message, session_id)):
                yield ev

    return EventSourceResponse(gen())


async def _with_timeout(agen):
    start = asyncio.get_event_loop().time()
    async for item in agen:
        if asyncio.get_event_loop().time() - start > TIMEOUT_S:
            yield {"event": "error",
                   "data": json.dumps({"message": f"timed out after {TIMEOUT_S}s"})}
            return
        yield item
