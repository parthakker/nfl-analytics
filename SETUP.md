# Setup Guide

Get the whole thing running from scratch — budget 30–60 minutes, most of it
the ~2 GB data download and warehouse build (both resumable). No accounts or
API keys needed for the core experience.

## 1. Prerequisites

- **Python 3.12 or newer** — check with `python --version`
  (Windows: tick "Add to PATH" when installing)
- **Node 20+** — for the Jarvis web UI ([nodejs.org](https://nodejs.org))
- **Git** — [git-scm.com](https://git-scm.com/downloads)
- **~4 GB free disk** (2 GB download + ~1 GB database + headroom)

Works on Windows, macOS, and Linux.

## 2. Install

```bash
git clone https://github.com/parthakker/nfl-analytics
cd nfl-analytics
uv sync --extra dev          # recommended (install uv: pip install uv)
# — or, plain pip:
pip install -e ".[dev]"
```

The `legacy` extra (`--extra legacy` / `".[dev,legacy]"`) adds Streamlit for
the old dashboard; skip it unless you want that.

## 3. Download the data (~2 GB, resumable)

```bash
python -m nfl_analytics.cli refresh --bootstrap
```

Downloads every nflverse season 1999→current, fetches weather, builds
`nfl.duckdb`, and runs the sanity checks. Re-run it if it's interrupted —
already-downloaded files are skipped. In-season, plain
`python -m nfl_analytics.cli refresh` keeps it current.

(`nfl <command>` also works anywhere the Python scripts directory is on PATH.)

## 4. Build and launch Jarvis

```bash
cd web/ui && npm ci && npm run build && cd ../..
python web/run_web.py        # http://localhost:8000
```

Windows: double-click `NFL Jarvis.cmd` instead (auto-restarts on crashes).
The legacy Streamlit dashboard is `legacy/NFL Dashboard.cmd`.

## 5. Verify

```bash
python -m pytest tests/unit -q            # fast, no DB needed
python -m pytest -m "warehouse or api" -q # invariants vs your freshly built DB
python -m nfl_analytics.cli smoke         # live-HTTP endpoint check
cd web/ui && npx playwright install chromium && npm run e2e   # browser e2e
```

## 6. Claude Code integration (optional)

The repo ships its Claude Code config: opening it in Claude Code picks up
`CLAUDE.md`, the path-scoped rules, skills (`/health-check`, `/rebuild`,
`/new-page`…), hooks (auto-lint + a test gate), and the `nfl` MCP server via
the committed `.mcp.json` (approve it on first use). If you previously added
the server manually, remove the duplicate: `claude mcp remove nfl -s local`.

## 7. Maintenance (manual)

Nothing is scheduled. Open Jarvis and go to **More → Ops** (`/ops`): every
maintenance job is a card with a Run button and a live output console.

| Job | What it does |
|---|---|
| Refresh data | Download the latest nflverse releases, rebuild warehouse + views |
| Rebuild warehouse / Rebuild views | Rebuild from what is already in `data/` |
| Fetch weather | Open-Meteo forecasts (`backfill` walks history) |
| Poll news / Snapshot Kalshi | Refresh the sidecar stores |
| Smoke test / Data audit | Verify endpoints and table completeness |
| Model experiment / Model recap | One config through the holdout in seconds (logs a scorecard) / recap workbook to the Desktop |
| Train model / Rebuild CI fixture | Maintainer jobs |

Everything is also available as `nfl <cmd>` (see `--help`). One job runs at a
time; a second request gets a 409. Runs are recorded in `logs/ops_runs.jsonl`.

This project previously shipped five Task Scheduler jobs. They were removed —
all of them used "run as soon as possible after a missed start" with no idle
guard, so a laptop waking from sleep fired every overdue job simultaneously.
If you re-create any, set an execution time limit and require idle first.

> **Perishable:** Kalshi snapshots and Vegas line snapshots are point-in-time
> captures. Skipping a game week loses that week's line movement permanently —
> unlike the warehouse, which is always rebuildable from `data/`.

## 8. Maintainer bits

- `nfl fixture` rebuilds the committed ~24 MB CI fixture DBs (do this a few
  times a season).
- `nfl audit` regenerates `docs/data_audit.md`.
- Model: `nfl experiment` (one config, seconds, nothing persisted) · `nfl train` (full protocol, ~2-5 min, overwrites model_* tables) · `nfl recap` (workbook). The Model Lab page is at `/model`; how it works: `/knowledge/model-primer`.

## Troubleshooting

- **"database is locked"** — close `explore.cmd` (DuckDB browser UI) before
  any refresh/rebuild; the API retries briefly and returns 503s while
  collectors write.
- **A download fails with "no candidate matched"** — nflverse renamed an
  asset; check their releases page and update `scripts/refresh_data.py`.
- **`nfl` not found** — use `python -m nfl_analytics.cli` (PATH-independent).
- **UI shows stale pages after edits** — rebuild: `cd web/ui && npm run build`.
- **Linux/Mac: `python` not found** — some distros only ship `python3`; use
  that (and edit the `command` in `.mcp.json` to match if you use the MCP
  server).
- **`nfl smoke` with no server running** — fine: it starts a temporary
  server on :8000 for the duration of the check.
