# Setup Guide

Get the whole thing running from scratch in ~15 minutes. No accounts or API
keys needed for the core experience.

## 1. Prerequisites

- **Python 3.12 or newer** — check with `python --version`; install from
  [python.org](https://www.python.org/downloads/) (Windows: tick "Add to PATH")
- **Git** — [git-scm.com](https://git-scm.com/downloads)
- **~4 GB free disk** (2 GB download + 0.6 GB database + headroom)

Works on Windows, macOS, and Linux.

## 2. Install

```bash
git clone https://github.com/parththakker/nfl-analytics.git
cd nfl-analytics
pip install -e .
```

## 3. Download the data (one time, ~2 GB)

```bash
python scripts/refresh_data.py --bootstrap
```

This pulls every season 2002–present from nflverse's public releases (play-by-
play, player stats, rosters, injuries, advanced stats, Next Gen Stats,
schedules with betting lines) and builds `nfl.duckdb`. It's resumable — if it
fails midway, run it again and it continues where it left off.

You should see it end with `All tables loaded, validation passed.`

## 4. Launch the dashboard

```bash
python -m streamlit run dashboard.py
```

Your browser opens to the app: click through divisions → teams → rosters,
coaching history, schedules with lines, league leaders, and news.

*(Windows: you can also create a shortcut to a `.cmd` file containing that
command — see `NFL Dashboard.cmd` for a template.)*

## 5. Keep it fresh (optional but recommended)

During the season, data updates nightly at the source. Refresh yours with:

```bash
python scripts/refresh_data.py     # stats + schedule (~1 min)
python scripts/poll_news.py        # ESPN + all 32 team-site news
python scripts/snapshot_kalshi.py  # prediction-market prices
```

To automate: schedule those three commands with Task Scheduler (Windows) or
cron (Mac/Linux). Suggested cadence: refresh weekly (Tuesday mornings), news
and Kalshi every 6 hours.

## 6. The AI analyst (optional — needs Claude)

The chat page in the dashboard and the natural-language analyst run on
[Claude Code](https://claude.com/claude-code). With it installed and logged in:

```bash
claude mcp add nfl -- python -m nfl_analytics.mcp_server
```

Then either use the dashboard's **Chat** page, or just open `claude` in the
project folder and ask football questions directly — it has 15 tools for
querying the warehouse, checking Kalshi prices, and pulling news. Note: chat
answers consume your Claude plan usage.

## 7. The prediction model (optional)

```bash
python scripts/train_model.py   # ~3 min: tunes, backtests, writes docs/model_report.md
```

Read `docs/model_report.md` before trusting it with a dollar — the honest
finding is that Vegas closing lines beat it, which is expected for public
data. Its value is calibrated probabilities and knowing the error bar.

## Troubleshooting

- **"file is being used by another process"** — the database is rebuilding
  (refresh) or open elsewhere. Close the dashboard/refresh and retry in a
  minute.
- **Bootstrap fails on one file** — nflverse occasionally renames release
  assets. Re-run first (transient errors happen); if it persists, open an
  issue with the log line.
- **Dashboard shows stale data** — it caches queries for 5 minutes; press
  `R` (rerun) or wait.
- **Chat page says CLI not found** — install Claude Code and ensure `claude`
  works in a terminal, then restart the dashboard.
