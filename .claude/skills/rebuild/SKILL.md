---
name: rebuild
description: Rebuild the warehouse and views from already-downloaded data, then verify.
disable-model-invocation: true
---

# Rebuild warehouse

1. Preflight: explore.cmd (DuckDB browser UI) must be closed — the rebuild
   deletes and recreates nfl.duckdb.
2. `python -m nfl_analytics.cli rebuild` (raw tables, ~60s) then
   `python -m nfl_analytics.cli views` (venues, weather parse, views, macros).
3. Both must exit 0; views output ends with "travel sanity OK". Then
   `python -m pytest -m warehouse -q`.
4. If a table fails with "no files match": non-optional glob missing from
   data/ — run /refresh-data instead. If the Jarvis server was up during the
   rebuild it may hold a stale handle — restart it if /api/health degrades.
