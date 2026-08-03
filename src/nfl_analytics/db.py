"""Read-only DuckDB access for MCP tools.

Every tool call opens a short-lived read_only connection so the warehouse
is never write-locked by the server (refresh/train can rebuild any time).
"""

from contextlib import contextmanager

import duckdb

from .config import NFL_DB, KALSHI_DB, NEWS_DB


@contextmanager
def read_conn(attach_kalshi: bool = False, attach_news: bool = False):
    con = duckdb.connect(str(NFL_DB), read_only=True)
    try:
        if attach_kalshi and KALSHI_DB.exists():
            con.execute(f"ATTACH '{KALSHI_DB.as_posix()}' AS kalshi (READ_ONLY)")
        if attach_news and NEWS_DB.exists():
            con.execute(f"ATTACH '{NEWS_DB.as_posix()}' AS newsdb (READ_ONLY)")
        yield con
    finally:
        con.close()


def table_result(con, sql: str, params: list | None = None,
                 max_rows: int = 200, filters_applied: str = "") -> dict:
    cur = con.execute(sql, params or [])
    cols = [d[0] for d in cur.description]
    rows = cur.fetchmany(max_rows + 1)
    truncated = len(rows) > max_rows
    rows = [[None if v != v else v if not hasattr(v, "isoformat") else v.isoformat()
             for v in row] for row in rows[:max_rows]]
    return {"columns": cols, "rows": rows, "row_count": len(rows),
            "truncated": truncated, "filters_applied": filters_applied}
