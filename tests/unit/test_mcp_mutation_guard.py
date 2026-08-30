"""The two MCP tools that write (refresh_data, kalshi_snapshot_now) must never
run from the Jarvis chat child — chat is granted every mcp__nfl tool by
prefix, so the guard is the only thing between a chat message and a 30-minute
warehouse refresh. Interactive sessions (no NFL_CHAT_CHILD) still run them."""

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO / "src"))

from nfl_analytics import mcp_server  # noqa: E402

_tool = lambda t: t.fn if hasattr(t, "fn") else t  # noqa: E731


def _arm(monkeypatch, chat: bool):
    calls = []
    monkeypatch.setattr(
        mcp_server.ops, "run_job_sync", lambda *a: calls.append(("refresh", a)) or {"ran": True}
    )
    monkeypatch.setattr(mcp_server.ops, "status_payload", lambda: {"stub": True})
    import nfl_analytics.kalshi as kalshi

    monkeypatch.setattr(kalshi, "snapshot", lambda: calls.append(("kalshi",)) or {"ran": True})
    if chat:
        monkeypatch.setenv("NFL_CHAT_CHILD", "1")
    else:
        monkeypatch.delenv("NFL_CHAT_CHILD", raising=False)
    return calls


def test_chat_child_refuses_and_points_at_ops(monkeypatch):
    calls = _arm(monkeypatch, chat=True)
    out = _tool(mcp_server.refresh_data)()
    assert out["ran"] is False and "Ops" in out["message"]
    assert "Refresh data" in out["message"] and out["status"] == {"stub": True}
    out = _tool(mcp_server.kalshi_snapshot_now)()
    assert out["ran"] is False and "Snapshot Kalshi" in out["message"]
    assert calls == []


def test_interactive_session_still_runs(monkeypatch):
    calls = _arm(monkeypatch, chat=False)
    assert _tool(mcp_server.refresh_data)(full=True) == {"ran": True}
    assert _tool(mcp_server.kalshi_snapshot_now)() == {"ran": True}
    assert [c[0] for c in calls] == ["refresh", "kalshi"]
    assert calls[0][1] == ("refresh", "full")
