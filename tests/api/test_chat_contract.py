"""Chat endpoint request gates. Every test either rejects before the
subprocess stage or stubs the CLI lookup — the live claude round-trip is
deliberately NOT tested here (it costs money and needs the CLI)."""

import pytest

import web.api.routers.chat as chat_mod

pytestmark = pytest.mark.api


@pytest.fixture
def no_claude_cli(monkeypatch):
    """Make _claude_cmd resolve nothing, so the stream yields one quick
    'claude CLI not found' error event instead of spawning a subprocess."""
    monkeypatch.setattr(chat_mod.shutil, "which", lambda _: None)


def test_rejects_non_json_content_type(client):
    r = client.post(
        "/api/chat/stream", content='{"message":"hi"}', headers={"Content-Type": "text/plain"}
    )
    assert r.status_code == 415


def test_rejects_malformed_json(client):
    r = client.post(
        "/api/chat/stream", content="{bad", headers={"Content-Type": "application/json"}
    )
    assert r.status_code == 400


def test_rejects_empty_message(client):
    assert client.post("/api/chat/stream", json={"message": "  "}).status_code == 400


def test_null_session_id_streams_and_releases_lock(client, no_claude_cli):
    # first-turn UI body: session_id null must NOT 400 — the stream opens
    # (here yielding the stubbed CLI-not-found error event)
    r = client.post("/api/chat/stream", json={"message": "x", "session_id": None})
    assert r.status_code == 200
    assert "claude CLI not found" in r.text
    # the wedge regression: a completed stream must release the lock so the
    # next request is NOT a 409
    r2 = client.post("/api/chat/stream", json={"message": "y", "session_id": None})
    assert r2.status_code == 200
    assert not chat_mod._lock.locked()


def test_rejects_shell_metachar_session_id(client):
    r = client.post(
        "/api/chat/stream",
        json={"message": "hi", "session_id": "abc&echo pwned%PATH%"},
    )
    assert r.status_code == 400
