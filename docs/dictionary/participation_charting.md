# Usage, charting & context tables (enrichment wave 2026-08)

New tables loaded 2026-08-03. Verified row counts and join keys below.

## snap_counts (2012–2025, ~325k rows)

Grain: player-game. Source: PFR via nflverse `snap_counts` release.
Key cols: `game_id` (standard `2024_01_ARI_BUF` format), `pfr_game_id`,
`season`, `week`, `player` (name), `pfr_player_id`, `position`, `team`,
`offense_snaps`, `offense_pct`, `defense_snaps`, `defense_pct`, `st_snaps`,
`st_pct`. Bridge to gsis via `players.pfr_id`. Team codes are PFR-style in
places — run through `canon_team()` before joining.

## depth_charts (2001–2025, ~1.8M rows)

Grain: team-week-position-slot (multiple rows per player possible).
**Schema changed in 2025** (new NFL feed) — loaded with union_by_name, so
era-dependent NULL columns exist; check both `depth_team`/`position`/`gsis_id`
(old era) and the 2025+ column variants before querying cross-era.

## participation (2016–2024, ~434k rows)

Grain: play. Joins pbp on `nflverse_game_id` + `play_id`
(nflverse_game_id = standard game_id format). Key cols: `possession_team`,
`offense_formation`, `offense_personnel` ("11", "1 RB, 1 TE, 3 WR" style),
`defense_personnel`, `defenders_in_box`, `number_of_pass_rushers`,
`defense_man_zone_type`, `defense_coverage_type`, `route`, `was_pressure`,
`time_to_throw`, plus offense/defense player id lists.
**The NFL discontinued this feed after 2023.** 2024 rows exist but are
unofficial; treat 2016–2023 as the reliable window. No 2025+ ever.

## ftn_charting (2022–2025, ~185k rows)

Grain: play (FTN manual charting). Joins pbp on `nflverse_game_id` +
`nflverse_play_id`. Booleans: `is_play_action`, `is_screen_pass`, `is_rpo`,
`is_motion`, `is_no_huddle`, `is_qb_out_of_pocket`, `is_trick_play`,
`is_qb_sneak`, `n_offense_backfield`, `n_defense_box`, `n_blitzers`,
`n_pass_rushers`, `is_qb_fault_sack`, drop/throwaway/batted/hit flags.
Best surviving personnel-adjacent source post-2023.

## combine (2000–2026, ~9k rows)

Grain: prospect. Keys: `pfr_id`, `cfb_id` — bridge via `players`. Forty,
bench, vert, broad, cone, shuttle + draft outcome cols.

## espn_qbr_week / espn_qbr_season (2006–2025)

Grain: QB-week / QB-season. No game_id — key on (season, game_week,
team/player). Player key is `player_id` (ESPN id) — bridge via
`players.espn_id`. `qbr_total`, `epa_total`, `pass`, `run`, `sack` splits.

## stadiums / stadium_aliases / game_venues / team_home_venues (built by build_views)

Curated source: `data/stadiums.json` (HAND EDITED — never overwritten;
~68 venues incl. internationals, coords, tz, et_offset, roof, eras, plus
`game_overrides` pinning the 7 mislabeled 2025 international games).
`game_venues` grain: game 1999–2026 incl. upcoming; resolution rule:
override > (neutral: name-alias, else stadium_id) > name > home-venue
fallback; `resolution` column records which path fired; build prints
unresolved count (must be 0). `team_home_venues` grain: team-season (modal
venue of non-neutral home games). `haversine_miles(lat1,lon1,lat2,lon2)`
macro registered alongside `canon_team`.

## game_weather_parsed / weather_openmeteo / v_game_weather

`game_weather_parsed` grain: game 1999–2025 — regex parse of the pbp
free-text `weather` col (sky, temp_f, humidity_pct, wind_dir, wind_mph,
wind_mph_high, gust_mph, is_indoor_note). ~92% of games have temp.
`weather_openmeteo` is loaded from `data/weather/openmeteo.csv`, written by
`scripts/fetch_weather.py` (archive backfill for the 7 games no source
covers + forecasts <16 days out; runs inside refresh_data before rebuild).
Query **`v_game_weather`** for "what was/will be the weather": one row per
game with `weather_source` ∈ indoor/pbp/openmeteo/schedules/forecast.
Roof rule: a venue whose curated roof is `outdoors` can never be indoor —
this overrides the (sometimes wrong for neutral games) schedules.roof.
