# 🏈 NFL Analytics

A personal NFL analytics platform that runs entirely on your machine: a local
warehouse of every NFL play since 2007, a visual dashboard, auto-updating data
and news, a prediction-market price tracker, and an AI analyst you can ask
questions in plain English.

**No API keys. No subscriptions for the core experience. One ~2 GB download.**

## What's inside

| Piece | What it does |
|---|---|
| **Warehouse** (DuckDB) | 909k+ plays (2007–2025), player/team stats, rosters, injuries, officials, draft history, and the full 2026 schedule with betting lines — all queryable in milliseconds |
| **Dashboard** (Streamlit) | Division standings with logos → click into team pages (roster, coaching history, efficiency charts, news, schedule) → players, league leaders, schedules & lines |
| **News engine** | Auto-polls ESPN plus all 32 official team websites every 6 hours; headlines are tagged to players/teams in the warehouse |
| **Kalshi tracker** | Records prediction-market prices (game winners, spreads, totals, win totals, Super Bowl futures) every 6 hours, building line-movement history |
| **Prediction model** | Opponent-adjusted EPA ratings → win probabilities, honestly backtested against 18 years of closing lines (spoiler: Vegas wins — the model's value is calibration, and the [report](docs/model_report.md) shows exactly by how much) |
| **AI analyst** | A chat page (and MCP server for Claude Code/Desktop) that writes and runs real SQL against your warehouse to answer questions like *"which QBs perform best traveling east?"* |

## Quick start

See **[SETUP.md](SETUP.md)** for the full guide. The short version:

```bash
git clone https://github.com/parthakker/nfl-analytics.git
cd nfl-analytics
pip install -e .
python scripts/refresh_data.py --bootstrap   # ~2 GB from nflverse, one time
python -m streamlit run dashboard.py
```

## Architecture

```
nflverse releases ─┐  (nightly-updated public data)
ESPN + team sites ─┼─► scripts/refresh_data.py / poll_news.py / snapshot_kalshi.py
Kalshi API ────────┘            │ (scheduled: weekly / 6h / 6h)
                                ▼
              nfl.duckdb + news.duckdb + kalshi.duckdb
                                │
              ┌─────────────────┼──────────────────┐
              ▼                 ▼                  ▼
        dashboard.py     MCP server (15 tools)   model/
        (Streamlit UI)   (Claude Code/Desktop)   (ratings, backtest)
```

Design principles: **compute, don't retrieve** (questions are answered by SQL
over plays, not by searching documents); **verified semantic layer** (every
data gotcha — and NFL data has many — is documented in `docs/dictionary/` and
enforced in `CLAUDE.md`); **honest modeling** (walk-forward backtests with an
untouched holdout, reported even when the answer is "the market is better").

## Data credits

All stats data from the outstanding [nflverse](https://github.com/nflverse)
project. News from ESPN and official team site feeds. Market data from
[Kalshi](https://kalshi.com)'s public API. This is a personal, non-commercial
project; all data remains property of its respective owners.

## License

MIT — see [LICENSE](LICENSE).
