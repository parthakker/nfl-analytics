---
paths:
  - "scripts/**"
  - "src/nfl_analytics/**"
---
# Warehouse & pipeline rules

- **Build order matters:** `build_warehouse.py` (deletes + reloads nfl.duckdb
  from data/ CSVs) then `build_views.py` (venue/weather tables, macros, views).
  `refresh_data.py` orchestrates: download → fetch_weather → both builds →
  line snapshot. `TEAM_ALIASES` in build_views OVERWRITES the table
  build_warehouse creates — keep them in sync.
- Validation lives in three places: row floors + coverage in build_warehouse,
  travel-sanity + per-view counts in build_views, invariants in
  tests/warehouse/. When you add a view: add it to the VIEWS dict WITH a grain
  comment, add a dictionary entry, add an invariant test.
- `data/officals/` (typo) is intentional — it matches the hardcoded TABLES
  glob; do not rename.
- **Never write to `*.duckdb` outside the build scripts.** Analysis connections
  are `read_only=True`; sidecars attach via `read_conn(attach_...)` which uses
  ATTACH IF NOT EXISTS (duckdb caches instances per path in-process).
- OPTIONAL_TABLES in build_warehouse may legitimately be absent mid-bootstrap;
  a missing non-optional glob is a real failure.
- v1/v2 stats seam: pre-2025 player_stats_* tables STOP at 2024 and will not
  grow; 2025+ lives in *_v2 with renamed columns. Cross-era queries go through
  `v_player_stats_week_all`. Never union the raw tables directly.
- pbp 1999–2006 has NULL cpoe/xpass (model floor 2006/2007) — FILTER-safe
  aggregations only.
- Fixture rebuild: `nfl fixture` (hard-fails if nfl_fixture.duckdb > 25 MB).
  Refresh it a few times a season and after schema changes; tests derive
  "current season" from the DB, never hardcode it.
- Weather: `game_weather_parsed` is regex over pbp free text (see
  tests/unit/test_weather_parse.py for the contract); `weather_openmeteo`
  loads from data/weather/openmeteo.csv written by fetch_weather.py; consumers
  use `v_game_weather` only.
