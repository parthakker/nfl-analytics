"""Read-only DuckDB access for MCP tools and the web API.

Every tool call opens a short-lived read_only connection so the warehouse
is never write-locked by long-lived servers. Opens and attaches RETRY with
backoff: the scheduled collectors (kalshi snapshot, news poll, weekly
refresh) briefly hold write locks, and DuckDB allows one writer OR many
readers per file — without retries, any request racing a collector fails.
"""

import time
from contextlib import contextmanager

import duckdb

from .config import KALSHI_DB, NEWS_DB, NFL_DB


class StoreBusyError(RuntimeError):
    """A database file is momentarily locked by a scheduled writer."""


def _retry(fn, what: str, tries: int = 4, delay: float = 0.6):
    last = None
    for i in range(tries):
        try:
            return fn()
        except duckdb.Error as e:
            last = e
            msg = str(e).lower()
            if "lock" not in msg and "file handle" not in msg and "being used" not in msg:
                raise
            time.sleep(delay * (i + 1))
    raise StoreBusyError(
        f"{what} is busy (a scheduled data update is writing to it) — "
        f"try again in a few seconds. [{last}]"
    )


@contextmanager
def read_conn(attach_kalshi: bool = False, attach_news: bool = False):
    con = _retry(lambda: duckdb.connect(str(NFL_DB), read_only=True), "warehouse")
    try:
        # IF NOT EXISTS: duckdb caches database instances per path within a
        # process, so another live connection (tests, tools) may have left the
        # sidecar attached already
        if attach_kalshi and KALSHI_DB.exists():
            _retry(
                lambda: con.execute(
                    f"ATTACH IF NOT EXISTS '{KALSHI_DB.as_posix()}' AS kalshi (READ_ONLY)"
                ),
                "market history store",
            )
        if attach_news and NEWS_DB.exists():
            _retry(
                lambda: con.execute(
                    f"ATTACH IF NOT EXISTS '{NEWS_DB.as_posix()}' AS newsdb (READ_ONLY)"
                ),
                "news store",
            )
        yield con
    finally:
        con.close()


def table_result(
    con, sql: str, params: list | None = None, max_rows: int = 200, filters_applied: str = ""
) -> dict:
    cur = con.execute(sql, params or [])
    cols = [d[0] for d in cur.description]
    rows = cur.fetchmany(max_rows + 1)
    truncated = len(rows) > max_rows
    rows = [
        [None if v != v else v if not hasattr(v, "isoformat") else v.isoformat() for v in row]
        for row in rows[:max_rows]
    ]
    return {
        "columns": cols,
        "rows": rows,
        "row_count": len(rows),
        "truncated": truncated,
        "filters_applied": filters_applied,
    }
