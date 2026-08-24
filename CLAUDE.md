# NFL Analytics Warehouse

**Repo:** https://github.com/parthakker/nfl-analytics (public, MIT). Local git
identity is Parth's personal email (repo-local config). `data/*` (except the
two hand-curated JSONs), `*.duckdb`, and `logs/` are gitignored — fresh clones
rebuild via `nfl refresh --bootstrap`. Commit when Parth asks; follow
`/release` for the ritual.

Personal NFL analyst project. Questions are answered by running SQL against
`nfl.duckdb` (DuckDB, repo root) — computed answers, not retrieval. Before
non-trivial SQL, load the `warehouse-queries` skill (table grid, view catalog,
query patterns); per-table dictionaries live in `docs/dictionary/*.md`.

## How to query

```
python -c "import duckdb; con=duckdb.connect('nfl.duckdb', read_only=True); print(con.execute('''<SQL>''').fetchdf().to_string())"
```

Always `read_only=True` for analysis. Never write to any `*.duckdb` outside
the build scripts (enforced by permissions.deny).

## Commands

- `nfl <cmd>` (or `python -m nfl_analytics.cli <cmd>`): refresh / rebuild /
  views / audit / smoke / weather / train / news / kalshi / fixture.
  Rebuild = `nfl rebuild` then `nfl views` (~60s).
- Tests: `pytest tests/unit` (fast, no DB) · `pytest -m warehouse` (real-DB
  invariants) · `pytest -m api` (TestClient contracts) · `cd web/ui && npm run
  e2e` (Playwright vs live server). Prefer running single tests, not the whole
  suite. CI runs unit + fixture tiers (`NFL_TEST_USE_FIXTURE=1`).
- Chat answer quality has its own suite: `python scripts/run_chat_evals.py`
  (`evals/`, 28 questions × 4 moments). Costs real API budget and is manual —
  re-run the affected `--moment` slice after editing CLAUDE.md, `mcp_server.py`
  or `chat.py`, and `--compare` against the previous run dir.
- UI rebuild after web/ui edits: `cd web/ui && npm run build`.
- Jarvis (primary UI): "NFL Jarvis" shortcut or `python web/run_web.py` (:8000).
  Legacy Streamlit lives in `legacy/` — frozen, don't extend.

## Front end

`web/` — FastAPI routers (`web/api/`) + React/Vite/Tailwind SPA (`web/ui/`).
Nav is 6 sections + More: Today `/` · Scores `/scores` · Teams `/teams` ·
Players `/players` · Betting `/betting` · Learn `/knowledge`; under More sit
Leaders, Coaches, Refs, H2H, Markets, News. Details are singular
(`/team/:code`, `/player/:gsis`, `/coach/:name`, `/matchup/:gameId`). Old
paths redirect, unknown paths go to `/`. Ctrl-K is a moded command palette
(jump / `>` commands / `?` analyst) in `components/CommandPalette.tsx`.

Design system: tokens in `src/styles/tokens.css`, primitives in
`components/ui/`, charts in `components/charts/`. **Never type a hex or
rgba() in a component** — `npm run lint` runs `scripts/check_tokens.mjs` and
fails on it. Conventions in `.claude/rules/{frontend,api}.md` (auto-load when
touching those dirs). Chat = SSE over `claude -p` (chat.py). The prediction
model is built but PAUSED per Parth — don't surface it proactively.

## Data & automation

**Warehouse:** nflverse, pbp 1999–2025 + schedules 1999–2026 (incl. upcoming,
odds, refs). Weekly stats are v2-schema 2025+ — query `v_player_stats_week_all`
for cross-era. Sidecars: `kalshi.duckdb` (market + Vegas line snapshots),
`news.duckdb` (tagged news + FTS). Hand-curated (never overwritten by
refresh): `data/stadiums.json`, `data/coaches_meta.json` — rules in
`.claude/rules/data-curation.md`.

**Task Scheduler (5 jobs, one log line per run in `logs/*.log`):**
`NFL-WeeklyRefresh` (Tue 08:00 → refresh_data.py), `NFL-NewsPoll` (6h),
`NFL-KalshiSnapshot` (6h), `NFL-SmokeTest` (daily 07:30),
`NFL-NightlyHealth` (daily 06:45 → headless `claude -p "/health-check"`).
Manage via `schtasks /Query|/Run /TN <name>`; `data_status` MCP tool tails logs.

## Join keys

- **Player:** `gsis_id` (`00-0033873`; named `player_id` in player_stats,
  `player_gsis_id` in NGS). Advanced stats key on `pfr_id` ONLY — bridge via
  `players`. ESPN QBR: join `players.espn_id = espn_qbr_*.player_id`.
- **Game:** `game_id` = `2024_01_ARI_BUF` everywhere EXCEPT
  `officials.game_id` (numeric = `games.old_game_id`). participation/ftn join
  pbp on `nflverse_game_id` (+ play_id).
- **Team-week:** `season` + `week` + team code; `canon_team(col)` macro for
  legacy codes (OAK/SD/STL etc.).

## Critical gotchas (one-liners — detail in .claude/rules/warehouse.md + docs/dictionary/)

1. Season stat tables mix REG / POST / REG+POST rows — always filter `season_type`.
2. NGS `week = 0` rows are season aggregates — filter explicitly.
3. Team codes vary by table — `canon_team()` when joining across tables.
4. advstats pct scales differ (season_pass 0–100, rest 0–1); require attempt minimums.
5. advstats_week_def/_rush numerics are VARCHAR with 'NA' — `TRY_CAST` mandatory.
6. POST week numbering shifted in 2021; `success` = `epa > 0`; `spread_line`
   positive = home favored (team-perspective in v_team_games/v_matchup_games).
7. players has 6,093 ESB-format ids that never join; rosters_weekly has
   pre-2017 dup rows.
8. Coverage floors: advstats 2018+, NGS 2016+, officials 2015+ (head refs
   1999+ via schedules.referee on `ref_key`), injuries 2009+, snap_counts
   2013+, participation 2016–2024 only (discontinued; 2024 rows are
   unofficial — never expect 2025+), ftn 2022+.
9. Weather: temp/wind NULL for domes; query `v_game_weather`, not raw cols.
10. Aggregate the raw `officials` table by `official_id`; aggregate the
    referee VIEWS by `ref_key` (the canonical name — official_id is NULL
    pre-2015 and nflverse reissued ids in 2023, so it splits careers).

## Conventions for answers

- EPA/play from pbp: `play_type IN ('pass','run')` and `season_type='REG'`
  unless asked otherwise; state the filter used.
- Rate stats: sensible minimums (e.g. 160 att for QB season rates); say what
  was applied.
- Travel: `v_team_games.travel_miles` (home-base haversine; internationals
  modeled) + `tz_shift_hours` (positive = east). Prefer `rest_days_sched`
  (populated wk 1) over `rest_days`.
- Cite seasons/filters in every answer so results are reproducible.
- Concept/scheme/rules/fantasy-basics questions: check `knowledge_lookup`
  (chapters + table dictionaries) before writing SQL or answering from
  memory — it carries this project's own definitions.
- In chat, lead with the answer in 1-2 sentences, then compact support (a
  small table for numbers); the reader is on a phone-width overlay.
- Every new API endpoint gets a smoke CHECK + a tests/api case; every new
  view gets a dictionary entry + a tests/warehouse invariant.
