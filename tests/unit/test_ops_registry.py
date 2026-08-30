"""Ops registry, log rotation and last-run parsing. No database needed."""

import json

from nfl_analytics import ops


def test_every_job_key_exists_in_the_cli_dispatcher():
    for key, job in ops.JOBS.items():
        assert key in ops.COMMANDS
        assert job.script == ops.COMMANDS[key][0]


def test_every_job_has_a_default_variant():
    """The UI selects "" before the user picks anything."""
    for job in ops.JOBS.values():
        assert "" in job.variants


def test_bootstrap_is_not_exposed():
    """~2 GB and the better part of an hour stays a terminal command."""
    for job in ops.JOBS.values():
        assert all("--bootstrap" not in args for args in job.variants.values())


def test_child_env_forces_utf8_and_unbuffered():
    # several build scripts print non-ASCII glyphs; a piped child on Windows
    # would otherwise die with UnicodeEncodeError partway through a rebuild
    env = ops.child_env()
    assert env["PYTHONIOENCODING"] == "utf-8"
    assert env["PYTHONUNBUFFERED"] == "1"
    assert ops.child_env({"SMOKE_BASE_URL": "http://x"})["SMOKE_BASE_URL"] == "http://x"


# ── rotation ─────────────────────────────────────────────────────────────────


def test_rotate_log_is_a_noop_under_the_cap(tmp_path):
    p = tmp_path / "x.log"
    p.write_text("small", encoding="utf-8")
    assert ops.rotate_log(p, 1024) is False
    assert p.read_text(encoding="utf-8") == "small"


def test_rotate_log_rolls_over_the_cap(tmp_path):
    p = tmp_path / "x.log"
    p.write_text("y" * 2000, encoding="utf-8")
    assert ops.rotate_log(p, 1024) is True
    assert not p.exists()
    assert (tmp_path / "x.log.1").read_text(encoding="utf-8") == "y" * 2000


def test_rotate_log_keeps_one_generation(tmp_path):
    p = tmp_path / "x.log"
    for marker in ("first", "second"):
        p.write_text(marker + "z" * 2000, encoding="utf-8")
        ops.rotate_log(p, 1024)
    assert (tmp_path / "x.log.1").read_text(encoding="utf-8").startswith("second")


def test_rotate_log_never_raises_on_a_missing_file(tmp_path):
    assert ops.rotate_log(tmp_path / "nope.log", 10) is False


# ── last-run parsing ─────────────────────────────────────────────────────────


def test_parses_a_legacy_refresh_line(tmp_path, monkeypatch):
    monkeypatch.setattr(ops, "LOGS_DIR", tmp_path)
    monkeypatch.setattr(ops, "RUNS_LOG", tmp_path / "none.jsonl")
    (tmp_path / "refresh.log").write_text(
        "2026-08-23T14:48:37.314773 mode=weekly fetched=43 failures=1 line_snap=skip rc=1\n",
        encoding="utf-8",
    )
    row = ops.last_runs()["refresh"]
    assert row["ok"] is False  # rc=1
    assert row["source"] == "log"
    assert "line_snap=skip" in row["summary"]


def test_truncates_a_pathological_smoke_line(tmp_path, monkeypatch):
    """One failing run appended all 36 failures as a single ~10 KB line."""
    monkeypatch.setattr(ops, "LOGS_DIR", tmp_path)
    monkeypatch.setattr(ops, "RUNS_LOG", tmp_path / "none.jsonl")
    (tmp_path / "smoke.log").write_text(
        "2026-08-27T23:39:23.396604 smoke: 0/36 passed | FAILURES: " + ("x" * 10_000) + "\n",
        encoding="utf-8",
    )
    row = ops.last_runs()["smoke"]
    assert row["ok"] is False
    assert len(row["summary"]) <= ops.SUMMARY_CHARS


def test_passing_smoke_line_reads_as_ok(tmp_path, monkeypatch):
    monkeypatch.setattr(ops, "LOGS_DIR", tmp_path)
    monkeypatch.setattr(ops, "RUNS_LOG", tmp_path / "none.jsonl")
    (tmp_path / "smoke.log").write_text(
        "2026-08-28T10:00:00.000000 smoke: 37/37 passed\n", encoding="utf-8"
    )
    assert ops.last_runs()["smoke"]["ok"] is True


def test_ops_runs_log_wins_over_the_legacy_log(tmp_path, monkeypatch):
    monkeypatch.setattr(ops, "LOGS_DIR", tmp_path)
    monkeypatch.setattr(ops, "RUNS_LOG", tmp_path / "ops_runs.jsonl")
    (tmp_path / "news.log").write_text(
        "2020-01-01T00:00:00.000000 news poll: fetched=1\n", encoding="utf-8"
    )
    ops.record_run("news", "", 0, 1.5, "news poll: fetched=99")
    row = ops.last_runs()["news"]
    assert row["source"] == "ops"
    assert row["ok"] is True
    assert row["duration_s"] == 1.5


def test_record_run_caps_the_stored_tail(tmp_path, monkeypatch):
    monkeypatch.setattr(ops, "LOGS_DIR", tmp_path)
    monkeypatch.setattr(ops, "RUNS_LOG", tmp_path / "ops_runs.jsonl")
    ops.record_run("audit", "", 0, 1.0, "q" * 50_000)
    row = json.loads((tmp_path / "ops_runs.jsonl").read_text(encoding="utf-8").strip())
    assert len(row["tail"]) == ops.TAIL_CHARS


def test_runs_log_is_trimmed(tmp_path, monkeypatch):
    monkeypatch.setattr(ops, "LOGS_DIR", tmp_path)
    monkeypatch.setattr(ops, "RUNS_LOG", tmp_path / "ops_runs.jsonl")
    for _ in range(ops.RUNS_LOG_MAX_LINES + 40):
        ops.record_run("news", "", 0, 0.1, "x")
    ops._trim_runs_log()
    kept = (tmp_path / "ops_runs.jsonl").read_text(encoding="utf-8").strip().splitlines()
    assert len(kept) == ops.RUNS_LOG_MAX_LINES


def test_naive_log_timestamps_are_read_as_local_not_utc():
    """The legacy logs used a bare datetime.now().isoformat(). Reading those
    as UTC put every reported age out by the machine's offset."""
    from datetime import datetime

    now_local = datetime.now().isoformat()
    assert abs(ops._age_hours(now_local)) < 0.2
