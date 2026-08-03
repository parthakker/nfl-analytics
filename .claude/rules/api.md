---
paths:
  - "web/api/**"
---
# Jarvis API rules (web/api)

- New router: bare `APIRouter()`, full `/api/...` path on each decorator, and
  register in **BOTH** the import tuple and the `for _r in (...)` loop in
  `main.py` — missing either is the classic silent 404.
- Query pattern: `with read_conn(...) as con:` + `rows_to_dicts(con, sql,
  params)`. Positional `?` lists or named `$x` dicts. Whitelist-validate any
  enum param interpolated into SQL. `HTTPException(404, ...)` for misses.
- Sidecar blocks (kalshi/news) wrap in try/except so a locked store degrades
  gracefully; `StoreBusyError` → 503 is handled globally (UI retries once).
- Return flat dicts of named lists/objects, never bare lists. Pre-format
  dates in SQL (`strftime`) — the UI does no date formatting.
- Upcoming games are NOT in `games`/pbp — endpoints that must work for them
  need a schedules-only path (see matchup.py `_side`).
- injuries use legacy team codes → `canon_team()`; officials join via
  `old_game_id`; ref aggregation on `ref_key`.
- **Every new endpoint gets a smoke CHECK in scripts/smoke_test.py AND a
  tests/api case** — and the predicate must hold on the CI fixture (derive
  "current season" from the DB, relax live-data expectations via
  FIXTURE_RELAXED in test_smoke_contract.py if needed).
