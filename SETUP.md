# Setup Guide

Get the whole thing running from scratch in ~15 minutes. No accounts or API
keys needed for the core experience.

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

## 7. Automation (optional, Windows)

Five Task Scheduler jobs keep everything fresh — create what you want:

| Task | Schedule | Runs |
|---|---|---|
| NFL-WeeklyRefresh | Tue 08:00 | `scripts\refresh_data.py` |
| NFL-NewsPoll | every 6h | `scripts\poll_news.py` |
| NFL-KalshiSnapshot | every 6h | `scripts\snapshot_kalshi.py` |
| NFL-SmokeTest | daily 07:30 | `scripts\smoke_test.py` |
| NFL-NightlyHealth | daily 06:45 | `scripts\nightly_health.cmd` (headless Claude `/health-check`; needs Claude Code installed) |

Example:
`schtasks /Create /TN NFL-WeeklyRefresh /SC WEEKLY /D TUE /ST 08:00 /TR "C:\PathTo\pythonw.exe C:\PathTo\repo\scripts\refresh_data.py"`

All jobs append one line per run to `logs\*.log`; the `data_status` MCP tool
surfaces the tails.

## 8. Maintainer bits

- `nfl fixture` rebuilds the committed ~24 MB CI fixture DBs (do this a few
  times a season).
- `nfl audit` regenerates `docs/data_audit.md`.
- Model training (paused feature): `nfl train`.

## Troubleshooting

- **"database is locked"** — close `explore.cmd` (DuckDB browser UI) before
  any refresh/rebuild; the API retries briefly and returns 503s while
  collectors write.
- **A download fails with "no candidate matched"** — nflverse renamed an
  asset; check their releases page and update `scripts/refresh_data.py`.
- **`nfl` not found** — use `python -m nfl_analytics.cli` (PATH-independent).
- **UI shows stale pages after edits** — rebuild: `cd web/ui && npm run build`.
