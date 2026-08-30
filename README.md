# 🏈 NFL Analytics

A personal NFL analytics platform that runs entirely on your machine: a DuckDB
warehouse of every NFL play since 1999, a dark token-themed web app ("Jarvis"),
auto-updating data and news, a prediction-market tracker, and an AI analyst
wired in through MCP. Questions get answered by running SQL against real data —
computed answers, not vibes.

**No API keys. No subscriptions for the core experience. One ~2 GB download.**

![CI](https://github.com/parthakker/nfl-analytics/actions/workflows/ci.yml/badge.svg)

## What's inside

| Piece | What it does |
|---|---|
| **Warehouse** (`nfl.duckdb`) | 1.28M plays 1999–2025, schedules with odds through 2026, player/team stats across the v1/v2 nflverse eras, advanced stats, NGS, snap counts, depth charts, personnel/participation, FTN charting, combine, ESPN QBR — plus curated venue coordinates powering true travel distances |
| **Jarvis web app** (`web/`) | FastAPI + React SPA: team HUDs, matchup cards (travel/rest/refs/coach-H2H/weather/market for any game 1999→upcoming), all-time H2H explorer, coaches with scheme fingerprints, referee intel, betting board (Vegas-vs-Kalshi dislocations), news, and a 16-chapter football Knowledge book |
| **Derived views** | SQL views for the common questions: team-game workhorse with haversine travel miles, H2H series with relocations merged, referee tendencies 1999+, coach PROE/4th-down aggression, one unified weather answer per game |
| **News engine** (`news.duckdb`) | ESPN + team feeds polled 6-hourly, categorized, player-tagged by gsis_id, full-text searchable |
| **Kalshi tracker** (`kalshi.duckdb`) | Market snapshots 6-hourly + Vegas line history per game |
| **Prediction model** | Trained, validated and surfaced on its own Model Lab page (`/model`: this week's model-vs-market with per-input reasons, report card, power ratings, experiment log) plus a seconds-fast `nfl experiment` loop. Betting surfaces stay market-vs-market — the model loses to the market on the holdout and says so |
| **MCP server** | Tools (`query_warehouse`, `betting_board`, `coach_profile`, `referee_stats`, `news_search`…) exposing all of it to Claude |
| **Legacy dashboard** (`legacy/`) | The original Streamlit UI, kept for friends — frozen |

## Architecture

```
nflverse releases ──► scripts/refresh_data.py ──► data/*.csv
                                 │
              Open-Meteo ──► fetch_weather.py
                                 │
        build_warehouse.py ──► nfl.duckdb ◄── build_views.py (views, venues, macros)
                                 │
     ┌───────────────────────────┼──────────────────────────┐
     │                           │                          │
 MCP server              FastAPI (web/api)        pytest invariants (tests/)
     │                           │
  Claude Code            React SPA (web/ui) ── Playwright e2e
                                 │
              kalshi.duckdb ── news.duckdb (sidecars, 6h pollers)
```

Five Windows Task Scheduler jobs keep it fresh: weekly data refresh, 6-hourly
news + Kalshi pollers, a daily smoke test, and a nightly headless Claude
health check that audits the data and runs the test suite.

## Quick start

See [SETUP.md](SETUP.md). Short version:

```bash
git clone https://github.com/parthakker/nfl-analytics && cd nfl-analytics
uv sync --extra dev                               # or: pip install -e ".[dev]"
python -m nfl_analytics.cli refresh --bootstrap   # ~2 GB nflverse download
cd web/ui && npm ci && npm run build && cd ../..
python web/run_web.py                             # Jarvis on http://localhost:8000
```

## Testing

Three pytest tiers: `tests/unit` (no database), `tests/warehouse` (invariants
against the real DB — travel distances, H2H symmetry, venue resolution, era
continuity), `tests/api` (contract tests for every endpoint). CI runs the unit
tier plus warehouse/api against committed ~24 MB fixture databases
(`nfl fixture` rebuilds them). Playwright e2e (`web/ui/e2e/`) runs locally
against the real server: `npm run e2e`.

## Design principles

- **Compute, don't retrieve** — every answer is SQL with its filters cited.
- **Hand-curated where sources are wrong** — `data/stadiums.json` fixes venues
  nflverse mislabels (all seven 2025 international games); curated files are
  version-controlled and never overwritten by refreshes.
- **Verification built in** — row floors and sanity checks in the build,
  invariant tests in CI, a smoke test and an AI health loop on the scheduler.
- **Keep it simple** — one machine, no cloud dependencies, boring tools.

## Data credits

[nflverse](https://github.com/nflverse) (play-by-play, stats, rosters),
[nfldata](https://github.com/nflverse/nfldata) (schedules + odds),
[Open-Meteo](https://open-meteo.com) (weather), ESPN (news, QBR), Kalshi
(market data). MIT licensed; the data belongs to its sources.
