# NFL Analytics Warehouse

Personal NFL analyst project. All questions are answered by running SQL against
`nfl.duckdb` (DuckDB, project root) — computed answers, not retrieval. Detailed
per-table dictionaries live in `docs/dictionary/*.md`; read the relevant one
before writing non-trivial queries against a table.

## Front end

`dashboard.py` (Streamlit v2) is the user-facing UI — launched via the
"NFL Dashboard" desktop shortcut or `python -m streamlit run dashboard.py`.
Pages: League (division grid w/ logos → click into teams), Team (banner,
Overview/Roster/Coaching/News/Schedule tabs), Players, Leaders, Schedule,
News (ESPN + all-32 team-site RSS), Chat (embedded — subprocess
`claude -p --resume <session> --allowedTools mcp__nfl`, ~$0.30/question).
Team metadata (names/divisions/domains/logos/colors) lives in
`src/nfl_analytics/teams_meta.py` — single source of truth.
Keep it SIMPLE per Parth's explicit preference; long-term vision (US map
navigation, referee pages) is in memory. The model is deliberately not
surfaced in the dashboard. `data/.MasterData/` was deleted 2026-08-02.

## How to query

```
python -c "import duckdb; con=duckdb.connect('nfl.duckdb', read_only=True); print(con.execute('''<SQL>''').fetchdf().to_string())"
```

Always connect `read_only=True` for analysis. Rebuild scripts:
`python scripts/build_warehouse.py` (raw tables, ~30s) then
`python scripts/build_views.py` (views, aliases, macro).

## Tables (grain — coverage)

| Table | Grain | Seasons |
|---|---|---|
| play_by_play | play (372 cols) | 2007–2025 |
| games | game (derived: coaches, scores, spread/total, roof, weather) | 2007–2025 |
| schedules | game incl. UPCOMING; odds, rest, QBs, refs (see dictionary) | 1999–2026 |
| player_stats_week / _season | player-week / player-season(type) offense | 2007–2024 |
| player_stats_week_v2 / _season_v2 | unified 145-col v2 format (off+def+kicking) | 2025+ |
| v_player_stats_week_all | compat view: old + v2 under old column names | 2007–2025 |
| player_stats_def_week / _def_season | same, defense | 2007–2024 |
| player_stats_kicking_week / _kicking_season | same, kicking | 2007–2024 |
| team_stats | team-season-seasontype (101→131 cols; new cols null pre-2025) | 2007–2025 |
| advstats_season_{pass,rush,rec,def} | player-season (PFR) | 2018–2025 |
| advstats_week_{pass,rush,rec,def} | player-game (PFR) | 2018–2025 |
| ngs_{passing,receiving,rushing} | player-week + week=0 season rows | 2016–2025 |
| players | player (master ID bridge, gsis_id PK) | all |
| rosters_weekly | player-team-week | 2002–2026 |
| injuries | player-week injury report | 2009–2025 |
| draft_picks | draft slot | 1980–2026 |
| officials | official-game | 2015–2025 |
| team_aliases / team_timezones | lookup | — |

**Refresh:** `python scripts/refresh_data.py` (weekly in-season; `--full` for
everything). nflverse updates nightly. 2025+ player stats use the renamed v2
schema — query `v_player_stats_week_all` for cross-era weekly offense; the raw
pre-2025 tables STOP at 2024 and will not grow.

**Automation (Windows Task Scheduler, created 2026-08-02):**
`NFL-WeeklyRefresh` (Tue 08:00 → refresh_data.py), `NFL-NewsPoll` (every 6h →
poll_news.py → news.duckdb), `NFL-KalshiSnapshot` (every 6h →
snapshot_kalshi.py → kalshi.duckdb). All log one line per run to `logs/*.log`;
the `data_status` MCP tool surfaces the tails. Manage with
`schtasks /Query|/Run|/Delete /TN <name>`.

**Sidecar DBs:** `kalshi.duckdb` (market snapshots; series KXNFLGAME/SPREAD/
TOTAL/WINS/SB) and `news.duckdb` (ESPN news+injuries, players tagged by
gsis_id). Attached read-only by MCP tools; never part of the warehouse rebuild.
**Model status:** built and validated but PAUSED per Parth — don't surface it
proactively; kalshi_edge_scan intentionally not built yet.

Derived views: `v_team_games` (team-game with win, rest_days, tz_shift_hours),
`v_strength_of_schedule`, `v_team_epa_season`, `v_team_def_epa_season`,
`v_coach_matchups`, `v_redzone_usage_week`.

## Join keys

- **Player:** `gsis_id` (`00-0033873` format; named `player_id` in player_stats,
  `player_gsis_id` in NGS). Advanced stats key on `pfr_id`/`pfr_player_id` ONLY —
  bridge via `players` (has both; join verified 99.5%+).
- **Game:** `game_id` = `2024_01_ARI_BUF` (season_week_AWAY_HOME) everywhere
  EXCEPT `officials.game_id`, which is numeric and matches `games.old_game_id`.
- **Team-week:** `season` + `week` + team code.

## Critical gotchas (each verified; details in docs/dictionary/)

1. **Season tables double-count:** `player_stats_*_season` contain REG, POST,
   AND combined `REG+POST` rows — always filter `season_type`. `team_stats` has
   only `REG` or `REG+POST`: playoff teams have NO pure-REG row, so compare
   per-game rates, or aggregate REG from weekly/pbp instead.
2. **NGS `week = 0` rows are season aggregates** (REG only, qualified players
   only) mixed into the same tables. Filter `week = 0` or `week > 0` explicitly.
3. **Team codes:** pbp, player_stats, team_stats, NGS are canonical
   (LA/LAC/LV/JAX), but injuries use OAK/SD/STL, NGS uses LAR,
   `advstats_season_pass` uses LVR, and draft_picks uses PFR codes
   (KAN/GNB/TAM/...). Use `canon_team(col)` macro (or `team_aliases`) when
   joining across tables. NGS also backdates LV/LAC to pre-relocation seasons.
4. **advstats percentage scales differ:** `advstats_season_pass` pcts are 0–100;
   all other advstats tables are 0–1 fractions. Small-sample rows produce
   absurd ratios (pressure_pct 150); require attempt minimums.
5. **advstats_week_def / _week_rush numerics are VARCHAR** with `'NA'` strings
   (2018–21) — `TRY_CAST(col AS DOUBLE)` is mandatory. Season advstats collapse
   traded players into `2TM`/`3TM` rows.
6. **Postseason week numbering shifted in 2021** (17-game era): POST weeks
   18–21 before 2021, 19–22 after. `success` = `epa > 0` exactly. Scrambles are
   `pass=1, play_type='run'`. `spread_line` positive = home team favored;
   in `v_team_games` it is flipped to always mean "this team favored by".
7. **players.gsis_id is unique**, but ~6.4k historical rows carry ESB-format
   ids that never join. rosters_weekly (gsis_id, season, week) has same-team
   dup rows pre-2017 — dedupe or use 2017+. `roster_weekly_2025` is a preseason
   partial with NULL week. draft_picks `car_av` is 100% NULL — use `w_av`.
8. **Coverage floors differ:** full-join analyses are capped by the narrowest
   source (advstats 2018+, NGS 2016+, officials 2015+, injuries 2009+).
   NGS rush-yards-over-expected cols are NULL 2016–17.
9. **Weather:** `temp`/`wind` NULL for all non-outdoor roofs (+122 outdoor
   games); `surface` has a `'grass '` (trailing space) variant.
10. **Aggregate officials by `official_id`**, not name (name spelling varies).

## Conventions for answers

- EPA/play from pbp: filter `play_type IN ('pass','run')` and `season_type='REG'`
  unless the question says otherwise; state the filter used.
- Rate stats: apply sensible minimums (e.g. 160 att for QB season rates) and
  say what minimum was applied.
- Travel questions: `v_team_games.tz_shift_hours` (positive = traveling east;
  home-team timezone stands in for stadium; international games not modeled).
- Cite seasons/filters in every answer so results are reproducible.
