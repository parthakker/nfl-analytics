"""Ops endpoint gates and the streaming contract.

The POST spawns real maintenance scripts, so every test here either rejects
before the subprocess stage or runs under NFL_OPS_DRY_RUN=1, which swaps the
child for a trivial `python -c`. Nothing in this file triggers a rebuild.
"""

import pytest

import web.api.routers.ops as ops_mod
from nfl_analytics import ops

pytestmark = pytest.mark.api


@pytest.fixture
def dry_run(monkeypatch, tmp_path):
    """Swap the child for a trivial `python -c`, and redirect the run log so a
    test sweep never writes fake rows into the real logs/ops_runs.jsonl."""
    monkeypatch.setenv("NFL_OPS_DRY_RUN", "1")
    monkeypatch.setattr(ops, "RUNS_LOG", tmp_path / "ops_runs.jsonl")


# ── GET /api/ops/jobs ────────────────────────────────────────────────────────


def test_jobs_lists_the_registry(client):
    js = client.get("/api/ops/jobs").json()
    assert {j["key"] for j in js["jobs"]} == set(ops.JOBS)
    assert "freshness" in js and "last_runs" in js
    assert js["running"] is None


def test_every_job_points_at_a_real_script(client):
    from nfl_analytics.config import ROOT

    for job in client.get("/api/ops/jobs").json()["jobs"]:
        assert job["script"].startswith("scripts/")
        assert (ROOT / job["script"]).exists(), job["script"]


def test_registry_matches_the_cli_dispatcher():
    """`nfl <cmd>` and the ops page must never disagree about what runs."""
    for key, job in ops.JOBS.items():
        assert job.script == ops.COMMANDS[key][0]


# ── request gates ────────────────────────────────────────────────────────────


def test_rejects_non_json_content_type(client):
    # a no-preflight text/plain form post from any page must not be able to
    # start a warehouse rebuild
    r = client.post("/api/ops/run/news", content="{}", headers={"Content-Type": "text/plain"})
    assert r.status_code == 415


def test_rejects_cross_origin(client):
    r = client.post("/api/ops/run/news", json={}, headers={"Origin": "http://evil.test"})
    assert r.status_code == 403


def test_unknown_job_is_404(client):
    assert client.post("/api/ops/run/nope", json={}).status_code == 404


def test_unknown_variant_is_400(client):
    # --bootstrap is deliberately not exposed: ~2 GB and about an hour
    assert client.post("/api/ops/run/refresh", json={"variant": "--bootstrap"}).status_code == 400


@pytest.mark.parametrize(
    "bad",
    ["../../etc/passwd", "refresh; rm -rf /", "refresh --bootstrap", "", "REFRESH"],
)
def test_argv_refuses_anything_not_in_the_registry(bad):
    """argv() is the whole allowlist — a caller string is only ever a dict key,
    never a path fragment and never an argument."""
    with pytest.raises(KeyError):
        ops.argv(bad)


def test_argv_only_emits_fixed_arguments():
    assert ops.argv("refresh", "full")[2:] == ["--full"]
    assert ops.argv("refresh", "download")[2:] == ["--no-rebuild"]
    assert ops.argv("news")[2:] == []


# ── streaming ────────────────────────────────────────────────────────────────


def test_dry_run_streams_to_done(client, dry_run):
    r = client.post("/api/ops/run/news", json={})
    assert r.status_code == 200
    assert "dry run ok" in r.text
    assert "event: done" in r.text


def test_completed_stream_releases_the_lock(client, dry_run):
    """The wedge regression: if the lock is not released on every teardown
    path, every later request 409s forever."""
    assert client.post("/api/ops/run/news", json={}).status_code == 200
    assert not ops_mod._lock.locked()
    assert client.post("/api/ops/run/news", json={}).status_code == 200
    assert ops_mod._current is None


def test_run_is_recorded(client, dry_run):
    client.post("/api/ops/run/news", json={})
    assert ops.last_runs()["news"]["ok"] is True


def test_gate_is_lowered_after_a_run(client, dry_run):
    from web.api.middleware import gate

    client.post("/api/ops/run/rebuild", json={})
    assert not gate.active()
