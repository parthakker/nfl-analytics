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


async def _stream_events(message: str, session_id: str | None):
    streaming = os.environ.get("CHAT_STREAMING", "1") != "0"
    cmd = _claude_cmd(message, session_id, streaming)
    if cmd is None:
        yield {"event": "error", "data": json.dumps({"message": "claude CLI not found"})}
        return

    proc = await asyncio.create_subprocess_exec(
        *cmd, cwd=str(ROOT),
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    got_done = False
    try:
        while True:
            try:
                line = await asyncio.wait_for(proc.stdout.readline(), timeout=10)
            except asyncio.TimeoutError:
                yield {"event": "ping", "data": "{}"}
                continue
            if not line:
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
                ev = js.get("event", {})
                delta = ev.get("delta", {})
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
        await asyncio.wait_for(proc.wait(), timeout=5)
        if not got_done:
            err = (await proc.stderr.read()).decode(errors="replace")[-500:]
            yield {"event": "error",
                   "data": json.dumps({"message": err or "stream ended without a result"})}
    except asyncio.CancelledError:
        raise
    finally:
        if proc.returncode is None:
            proc.kill()


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
