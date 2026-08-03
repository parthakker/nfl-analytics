---
name: warehouse-queries
description: Schema, join keys, gotchas and canonical query patterns for nfl.duckdb. Load before writing any non-trivial SQL against the warehouse — table grains, view catalog, cross-era rules, and the traps that silently corrupt results.
---

# Warehouse query guide

Connect read-only: `duckdb.connect('nfl.duckdb', read_only=True)`. Full
per-table dictionaries: `docs/dictionary/*.md` — read the relevant one before
querying a table in depth (`participation_charting.md` covers the 2026-08
additions).

## Tables (grain — coverage)

| Table | Grain | Seasons |
|---|---|---|
| play_by_play | play (372 cols) | 1999–2025 |
| games | game (derived: coaches, scores, lines, roof, weather) | 1999–2025 |
| schedules | game incl. UPCOMING; odds, rest, QBs, refs | 1999–2026 |
| player_stats_week / _season (+_def, _kicking) | player-week / player-season(type) | 2007–2024 |
| player_stats_week_v2 / _season_v2 | unified 145-col v2 | 2025+ |
| team_stats | team-season-seasontype | 2007–2025 |
| advstats_season_/week_{pass,rush,rec,def} | player-season / player-game (PFR) | 2018–2025 |
| ngs_{passing,receiving,rushing} | player-week + week=0 season rows | 2016–2025 |
| players | master ID bridge (gsis_id PK; pfr_id, espn_id) | all |
| rosters_weekly | player-team-week | 2002–2026 |
| injuries | player-week report | 2009–2025 |
| snap_counts | player-game snaps + pct | 2013–2025 |
| depth_charts | team-week slots (2025 schema differs) | 2001–2025 |
| participation | play: personnel, box, rushers | 2016–2023 (+2024 unofficial) |
| ftn_charting | play: PA/screen/RPO/motion/blitz | 2022–2025 |
| combine | prospect-year | 2000–2026 |
| espn_qbr_week / _season | QB-week / QB-season | 2006–2025 |
| draft_picks | draft slot (use w_av, car_av is NULL) | 1980–2026 |
| officials | official-game (numeric game_id = old_game_id) | 2015–2025 |
| stadiums / stadium_aliases / game_venues / team_home_venues | curated venues + per-game resolution | 1999–2026 |
| game_weather_parsed / weather_openmeteo | game weather (parsed pbp / Open-Meteo) | 1999–2025 / sparse |

## Views (each has a grain comment in scripts/build_views.py)

- `v_team_games` — team-game workhorse: win, rest_days + **rest_days_sched /
  is_off_bye / short_week**, **travel_miles** (home-base haversine),
  tz_shift_hours (venue-true, + = east), venue cols, team-perspective
  spread_line.
- `v_matchup_games` / `v_team_matchups` — team-pair series 1999+ from
  schedules, franchise-canonicalized (STL→LA…), site/venue/ATS splits, signed
  current_streak (+N = team won last N).
- `v_coach_matchups` (h2h + ATS + last_meeting_game_id), `v_coach_seasons`
  (records/ATS/playoffs), `v_coach_tendencies` (PROE, 4th-down go rate,
  shotgun/no-huddle/deep-shot, tempo), `v_coach_def_tendencies`.
- `v_referee_games` / `v_referee_seasons` (head refs 1999+; officials 2015+
  coalesced with schedules.referee; aggregate on **ref_key**),
  `v_referee_team_splits` (ref × team W%/ATS/pen diff).
- `v_game_weather` — the one weather answer per game (indoor → pbp parse →
  open-meteo → schedules; forecast for upcoming). Use this, not raw cols.
- `v_player_stats_week_all` — cross-era weekly offense (v1+v2 under old
  names, incl. fantasy_points_half_ppr). `v_player_stats_def_week_all` /
  `v_player_stats_kicking_week_all` — same seam pattern for defense/kicking
  (v2 arm activity-filtered; def_tackles recomputed solo+assists).
  `v_redzone_usage_week`.
- `v_team_epa_season` / `v_team_def_epa_season`, `v_strength_of_schedule`,
  `v_team_travel_season` (season travel totals).

Macros: `canon_team(code)`, `haversine_miles(lat1,lon1,lat2,lon2)`.

## Canonical patterns

EPA/play (state your filters in the answer):
```sql
SELECT posteam, round(avg(epa),3) AS epa_play FROM play_by_play
WHERE season=2025 AND season_type='REG' AND play_type IN ('pass','run')
GROUP BY posteam ORDER BY epa_play DESC
```

Cross-table team join (codes vary): `JOIN x ON canon_team(x.team) = canon_team(y.team)`.

PFR-keyed advstats → names: `JOIN players p ON p.pfr_id = a.pfr_id` (99.5%
match; season advstats collapse traded players into 2TM/3TM rows).

All-time H2H: `SELECT * FROM v_team_matchups WHERE team='BUF' AND
opponent='MIA'` (directional — one row each way; wins(a→b) == losses(b→a)).

Ref career: `SELECT ref_key, any_value(name), sum(games), ... FROM
v_referee_seasons GROUP BY ref_key` — never group by name (spelling varies)
or official_id (NULL pre-2015).

## Traps

1. Season stat tables mix REG / POST / REG+POST — filter `season_type` always;
   playoff teams have NO pure-REG row in team_stats (compare per-game rates).
2. NGS week=0 rows are season aggregates mixed into weekly tables.
3. advstats_season_pass pcts are 0–100; every other advstats pct is 0–1.
4. advstats_week_def/_rush numerics are VARCHAR with 'NA' → TRY_CAST.
5. POST week numbers shifted in 2021 (18–21 before, 19–22 after).
6. Scrambles are `pass=1, play_type='run'`; `success` = `epa > 0` exactly.
7. cpoe/xpass NULL pre-2006/2007; NGS RYOE NULL 2016–17.
8. `surface` has a `'grass '` (trailing space) variant.
9. rosters_weekly pre-2017 has same-team dup rows — dedupe or use 2017+.
10. participation ends at 2023 (2024 rows exist, unofficial); never expect 2025+.

