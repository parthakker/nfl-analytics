"""knowledge_lookup + query_warehouse SQL-surface guards (no DB needed for
the parts under test — query_warehouse rejections happen before connecting)."""

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO / "src"))

from nfl_analytics import mcp_server  # noqa: E402

_tool = lambda t: t.fn if hasattr(t, "fn") else t  # noqa: E731


def test_index_lists_chapters_and_dictionaries():
    out = _tool(mcp_server.knowledge_lookup)()
    slugs = [c["slug"] for c in out["chapters"]]
    assert "analytics-primer" in slugs and len(slugs) == 15
    assert "dict/schedules" in out["dictionaries"]


def test_chapter_fetch_and_cap():
    out = _tool(mcp_server.knowledge_lookup)("analytics-primer")
    assert "EPA" in out["markdown"]
    assert len(out["markdown"]) <= mcp_server._KNOWLEDGE_CHAR_CAP


def test_dictionary_fetch():
    out = _tool(mcp_server.knowledge_lookup)("dict/play_by_play")
    assert "play_by_play" in out["markdown"]


def test_whitelist_rejects_traversal_and_unknowns():
    for bad in ("../CLAUDE.local", "..\\secrets", "dict/../../CLAUDE", "nope"):
        out = _tool(mcp_server.knowledge_lookup)(bad)
        assert "error" in out, bad
        assert "markdown" not in out


def test_query_warehouse_blocks_file_functions():
    qw = _tool(mcp_server.query_warehouse)
    for sql in (
        "SELECT * FROM read_json('data/betting_rules.json')",
        "select content from read_text('CLAUDE.local.md')",
        "WITH x AS (SELECT * FROM read_csv_auto('logs/health.log')) SELECT * FROM x",
        "SELECT * FROM glob('**/*.md')",
        "SELECT * FROM parquet_scan('foo.parquet')",
    ):
        out = qw(sql)
        assert out.get("error", "").startswith("file-reading"), sql


def test_query_warehouse_allows_plain_selects_past_the_guard():
    # these must NOT trip the filesystem-function regex (word-boundary check);
    # they may still fail later at the DB layer, which is fine for this tier
    for sql in (
        "SELECT spread_line FROM schedules LIMIT 1",
        # substring in a literal, not a function call — must not match
        "SELECT * FROM games WHERE game_id LIKE '%read_json%'",
    ):
        assert not mcp_server._FS_FUNCS_RE.search(sql), sql
