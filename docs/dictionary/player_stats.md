# Player Stats Tables — Data Dictionary

Source: nflverse player-level stats, seasons **2007–2024**, loaded into `nfl.duckdb`.
All claims below verified with read-only queries against the warehouse (queries noted inline or in Gotchas).

| Table | Rows | Grain |
|---|---|---|
| `player_stats_week` | 95,757 | player × season × week (offense) |
| `player_stats_season` | 23,851 | player × season × season_type (offense) |
| `player_stats_def_week` | 168,885 | player × season × week × team (defense) |
| `player_stats_def_season` | 57,726 | player × season × season_type (defense) |
| `player_stats_kicking_week` | 9,663 | player × season × week (kicking) |
| `player_stats_kicking_season` | 1,803 | player × season × season_type (kicking) |

## Cross-table conventions (verified)

- **`player_id`**: GSIS format `00-00xxxxx` for **all** rows (min `00-0000108`, max `00-0039921`, 0 rows off-pattern; 3,106 distinct in weekly offense). Joins **100% cleanly** to `players.gsis_id`: `LEFT JOIN players p ON w.player_id = p.gsis_id` matched 95,757 / 95,757 weekly-offense rows.
- **`season_type`**: weekly tables use `REG` (weeks 1–18) and `POST` (weeks 18–22; POST starts at week 18 in pre-2021 seasons because REG ended at 17 through 2020, at 18 from 2021). Season tables have **three** values: `REG`, `POST`, and `REG+POST` (combined). Verified `REG+POST` = sum of the other two (Mahomes 2023: games 16+4=20, PPR 280.22+78.14=358.36). So yes, season tables include playoffs — but **naive `GROUP BY player_id` double-counts**; always filter `season_type`.
- **Team columns** (`recent_team`, `opponent_team`, `team`): **already canonicalized** to 32 current abbreviations in every table. `STL`, `SD`, `OAK`, `LAR`, `JAC` never appear (0 rows); Rams=`LA`, Chargers=`LAC`, Raiders=`LV`, Jaguars=`JAX` across all 18 seasons. The `team_aliases` table (`alias` → `canonical`: SD→LAC, OAK→LV, STL→LA, JAC→JAX, LAR→LA) exists for joining against *other* tables (e.g. older `games`/pbp data) that may still use era abbreviations.
- Counting stats (BIGINT columns) are **never NULL** — they are 0 when nothing happened. NULLs are confined to rate/model columns (EPA, pacr, racr, dakota, shares, wopr, pct) and identity fields (`player_name`, `position`, `headshot_url`).
- `player_name` is short form (`T.Brady`); `player_display_name` is full (`Tom Brady`). `player_name` is NULL for 29,435 weekly-offense rows, concentrated in early seasons (91% NULL in 2007 declining to 0% from 2017). **Use `player_display_name`**, which is never NULL.

## `player_stats_week` (weekly offense) — full column reference

Grain: one row per player per game. Unique on (`player_id`, `season`, `week`) **except one exact duplicate row**: Matthew Stafford 2010 week 8 (all-zero stat line, appears twice). Use `DISTINCT` or dedupe if exact uniqueness matters.

### Identity / context

| Column | Type | Meaning | Notes (verified) |
|---|---|---|---|
| `player_id` | VARCHAR | GSIS id `00-00xxxxx` | Never NULL; joins 100% to `players.gsis_id` |
| `player_name` | VARCHAR | Short name `T.Brady` | NULL in 31% of rows (2007–2016 era; 0% from 2017) |
| `player_display_name` | VARCHAR | Full name | Never NULL |
| `position` | VARCHAR | Roster position | Mostly WR/RB/TE/QB/FB; stray P, CB, T, etc.; NULL in 69 rows |
| `position_group` | VARCHAR | Coarse group | WR, RB, TE, QB, SPEC, DB, OL, LB, DL; NULL in 69 rows |
| `headshot_url` | VARCHAR | Image URL | NULL in 22,139 rows (older seasons) |
| `recent_team` | VARCHAR | Player's team that week | 32 canonical abbrevs (LA/LAC/LV/JAX in all eras) |
| `season` | BIGINT | Season year | 2007–2024 |
| `week` | BIGINT | Game week | 1–18 REG; 18–22 POST |
| `season_type` | VARCHAR | `REG` / `POST` | Only these two values in weekly tables |
| `opponent_team` | VARCHAR | Opponent | 32 canonical abbrevs; never NULL |

### Passing

| Column | Type | Meaning | Observed range / nulls |
|---|---|---|---|
| `completions` | BIGINT | Pass completions | 0–max; never NULL |
| `attempts` | BIGINT | Pass attempts | 0–68 |
| `passing_yards` | BIGINT | Passing yards | −7 to 527 (negative possible) |
| `passing_tds` | BIGINT | Passing TDs | ≥0 |
| `interceptions` | BIGINT | INTs thrown | ≥0 |
| `sacks` | BIGINT | Times sacked | ≥0 |
| `sack_yards` | BIGINT | Yards lost to sacks | ≥0 |
| `sack_fumbles` | BIGINT | Fumbles on sacks | ≥0 |
| `sack_fumbles_lost` | BIGINT | ...lost to defense | ≥0 |
| `passing_air_yards` | BIGINT | Air yards on attempts | never NULL |
| `passing_yards_after_catch` | BIGINT | YAC on completions | ≥0 |
| `passing_first_downs` | BIGINT | Passing first downs | ≥0 |
| `passing_epa` | DOUBLE | Total EPA on pass plays | −38.9 to 41.6; NULL iff `attempts = 0` (0 rows null with attempts>0) |
| `passing_2pt_conversions` | BIGINT | 2-pt passes converted | ≥0 |
| `pacr` | DOUBLE | Passing Air Conversion Ratio = `passing_yards / passing_air_yards` (formula verified exactly) | −0.29 to 32.5; NULL when `attempts=0` or air yards 0 (87.8% of rows NULL; only 29 NULL among rows with attempts>0) |
| `dakota` | DOUBLE | nflverse composite QB metric (EPA + CPOE model estimate) | −0.231 to 0.648; NULL when `attempts=0` **and for low-volume passers**: max attempts with NULL dakota = 4, min attempts with non-NULL = 5. Populated every season 2007–2024 (100% for attempts≥10) |

### Rushing

| Column | Type | Meaning | Observed range |
|---|---|---|---|
| `carries` | BIGINT | Rush attempts | 0–39 |
| `rushing_yards` | BIGINT | Rush yards | −28 to 296 |
| `rushing_tds` | BIGINT | Rush TDs | ≥0 |
| `rushing_fumbles` / `rushing_fumbles_lost` | BIGINT | Fumbles on rushes / lost | ≥0 |
| `rushing_first_downs` | BIGINT | Rushing first downs | ≥0 |
| `rushing_epa` | DOUBLE | Total EPA on rushes | −17.3 to 19.2; NULL iff `carries = 0` |
| `rushing_2pt_conversions` | BIGINT | 2-pt rushes converted | ≥0 |

### Receiving

| Column | Type | Meaning | Observed range / nulls |
|---|---|---|---|
| `receptions` | BIGINT | Catches | 0–21 |
| `targets` | BIGINT | Targets | 0–28 |
| `receiving_yards` | BIGINT | Receiving yards | −22 to 329 |
| `receiving_tds` | BIGINT | Receiving TDs | ≥0 |
| `receiving_fumbles` / `receiving_fumbles_lost` | BIGINT | Fumbles after catch / lost | ≥0 |
| `receiving_air_yards` | BIGINT | Air yards on targets | can be negative (behind-LOS targets) |
| `receiving_yards_after_catch` | BIGINT | YAC | ≥0 |
| `receiving_first_downs` | BIGINT | Receiving first downs | ≥0 |
| `receiving_epa` | DOUBLE | Total EPA on targets | −23.3 to 25.5; NULL iff `targets = 0` |
| `receiving_2pt_conversions` | BIGINT | 2-pt catches converted | ≥0 |
| `racr` | DOUBLE | Receiver Air Conversion Ratio = `receiving_yards / receiving_air_yards` (formula verified) | **−102 to 150** — wild outliers when air yards are tiny/negative. NULL when `targets=0` (18,972 rows) or `receiving_air_yards=0` (586 rows with targets>0, all with air yards = 0) |
| `target_share` | DOUBLE | Player targets ÷ team pass attempts that week | 0.015–0.714; NULL iff `targets = 0` (19.8% of rows) |
| `air_yards_share` | DOUBLE | Player air yards ÷ team air yards | **−9.0 to 8.0** — explodes when team air yards near 0/negative; NULL iff `targets = 0` |
| `wopr` | DOUBLE | Weighted Opportunity Rating = `1.5*target_share + 0.7*air_yards_share` (formula verified exactly) | −5.8 to 5.85; NULL iff `targets = 0` |

### Misc / fantasy

| Column | Type | Meaning | Notes |
|---|---|---|---|
| `special_teams_tds` | BIGINT | Return/ST TDs by this player | never NULL |
| `fantasy_points` | DOUBLE | Standard scoring | −6.96 to 59.5 (PPR max) |
| `fantasy_points_ppr` | DOUBLE | `fantasy_points` + 1.0 × `receptions` | |

**Scoring verified by recomputation** (two spot checks):
`fantasy_points = 0.04*passing_yards + 4*passing_tds − 2*interceptions + 0.1*(rushing_yards+receiving_yards) + 6*(rushing_tds+receiving_tds+special_teams_tds) − 2*fumbles_lost + 2*(2pt conversions)`.
- Tyreek Hill 2023 wk1: 11 rec, 215 yd, 2 TD → 21.5+12 = **33.5** std, +11 rec = **44.5** PPR ✓
- Lamar Jackson 2019 wk1: 324 pass yd, 5 pass TD, 6 rush yd → 12.96+20+0.6 = **33.56** ✓ (pass TD = 4 pts)
PPR differs from standard only by +1/reception.

## `player_stats_season` (season offense) — differences from weekly

Same 52 stat columns; differences only in shape:
- Drops `week`, `opponent_team`, `season_type` REG/POST-only coding; adds **`games`** (BIGINT, games played) and column order shifts (`season`, `season_type` lead).
- `season_type` ∈ {`REG` (10,711), `POST` (2,384), `REG+POST` (10,756)}. **Filter it** — `REG+POST` duplicates the others.
- Unique on (`player_id`, `season`, `season_type`) — verified 23,851 distinct.
- Counting stats are season sums. Rate columns are **recomputed from season aggregates, not averaged**: Malik Nabers 2024 REG `target_share` = 0.3491 in season table vs 0.357 as the mean of his weekly values.

## `player_stats_def_week` / `player_stats_def_season` (defense)

Different stat set entirely; identity columns as above but team column is named **`team`** (not `recent_team`), and there is no `opponent_team` in either def table.

| Column | Type | Meaning |
|---|---|---|
| `def_tackles` | BIGINT | Total tackles (solo + with-assist); weekly max observed 20 |
| `def_tackles_solo` | BIGINT | Solo tackles |
| `def_tackles_with_assist` | BIGINT | Tackles shared with another defender |
| `def_tackle_assists` | BIGINT | Assists credited |
| `def_tackles_for_loss` / `def_tackles_for_loss_yards` | BIGINT | TFLs and yards |
| `def_fumbles_forced` | BIGINT | Forced fumbles |
| `def_sacks` / `def_sack_yards` | DOUBLE | Sacks (half-sacks → fractional, hence DOUBLE; weekly max 6.0) |
| `def_qb_hits` | BIGINT | QB hits |
| `def_interceptions` / `def_interception_yards` | BIGINT | INTs (weekly max 4) and return yards |
| `def_pass_defended` | BIGINT | Passes defended (weekly max 6) |
| `def_tds` | BIGINT | Defensive TDs (weekly max 2) |
| `def_fumbles` | BIGINT | Fumbles by the defender himself |
| `def_fumble_recovery_own` / `_yards_own` | BIGINT | Own-team fumble recoveries / yards |
| `def_fumble_recovery_opp` / `_yards_opp` | BIGINT | Opponent fumble recoveries / yards |
| `def_safety` | BIGINT | Safeties |
| `def_penalty` / `def_penalty_yards` | BIGINT | Penalties committed / yards |

- **Coverage is uniform 2007–2024**: per-season sweep of `def_qb_hits`, `def_tackles_for_loss_yards`, `def_penalty_yards`, `def_sacks` shows 0 NULLs in every season — no schema drift.
- Rows include offensive players who made a tackle (position_group WR 3,812 rows, OL 2,890, QB 656, etc.).
- Weekly grain is (`player_id`, `season`, `week`, **`team`**): 71 player-weeks have two rows with different teams (e.g. Craig Steltz 2008 wk12 appears for both CHI and LA). (`player_id`, `season`, `week`) alone is **not** unique.
- Season table: adds `games`, drops `week`; same three `season_type` values (REG 26,443 / POST 4,388 / REG+POST 26,895); unique on (`player_id`, `season`, `season_type`).

## `player_stats_kicking_week` / `player_stats_kicking_season`

Team column is `team`; no `opponent_team`. Position is almost all `K` (9,636/9,663 weekly; stray P/SS/RB/WR rows).

| Column | Type | Meaning |
|---|---|---|
| `fg_made`, `fg_att`, `fg_missed`, `fg_blocked` | BIGINT | FG counts (weekly `fg_att` max 8) |
| `fg_long` | BIGINT | Longest make (max observed 66) |
| `fg_pct` | DOUBLE | `fg_made/fg_att`, 0.0–1.0; NULL iff `fg_att = 0` (verified: 0 rows NULL with fg_att>0) |
| `fg_made_0_19` … `fg_made_60_` | BIGINT | Makes by distance bucket (0–19, 20–29, 30–39, 40–49, 50–59, 60+) |
| `fg_missed_0_19` … `fg_missed_60_` | BIGINT | Misses by bucket |
| `fg_made_list`, `fg_missed_list`, `fg_blocked_list` | VARCHAR | **Semicolon-delimited distances**, e.g. `54;43;54;20;57`; NULL when no such kicks |
| `fg_made_distance`, `fg_missed_distance`, `fg_blocked_distance` | BIGINT | **Sum** of the corresponding list (verified: `54+43+54+20+57 = 228`); NULL iff `fg_att = 0` |
| `pat_made`, `pat_att`, `pat_missed`, `pat_blocked` | BIGINT | Extra points (weekly `pat_att` max 10) |
| `pat_pct` | DOUBLE | NULL iff `pat_att = 0` |
| `gwfg_att`, `gwfg_made`, `gwfg_missed`, `gwfg_blocked` | BIGINT | Game-winning FG attempts/results |
| `gwfg_distance` | **BIGINT — weekly table only** | Distance of the (single) GWFG attempt; weekly `gwfg_att` max is 1, so a scalar works; NULL iff `gwfg_att = 0` |
| `gwfg_distance_list` | **VARCHAR — season table only** | Semicolon list of GWFG distances across the season, e.g. `42;23;49;30` |

- **Naming difference**: weekly has scalar `gwfg_distance`; season replaces it with `gwfg_distance_list` (same column position, different name *and* type). Parse lists with `string_split(col, ';')` then cast elements to INT.
- Coverage sweep 2007–2024: no season is fully NULL for `fg_pct`/`gwfg_distance`/`fg_made_distance`/`pat_pct`; NULLs track zero attempts, not era.
- Season table: adds `games`, drops `week`; `season_type` REG 789 / POST 224 / REG+POST 790; unique on (`player_id`, `season`, `season_type`).

## Gotchas (all query-verified)

1. **One duplicate row** in `player_stats_week`: Matthew Stafford (`00-0026498`) 2010 week 8 vs WAS, an all-zero line, appears twice. Query: `GROUP BY player_id, season, week HAVING count(*) > 1`.
2. **`REG+POST` rows in all three season tables** — summing over a season table without `WHERE season_type = 'REG'` (or `= 'REG+POST'`) double-counts everything.
3. **POST weeks start at 18** even before 2021 (REG ended wk 17 through 2020) — `week >= 19` is *not* a safe playoff filter; use `season_type`.
4. **`player_name` (short form) is NULL for most pre-2016 rows** (91% NULL in 2007 → 0% from 2017). Use `player_display_name`.
5. **Team abbreviations are pre-canonicalized** (no STL/SD/OAK/LAR/JAC anywhere in these six tables). `team_aliases` is only needed when joining to other warehouse tables that keep era codes.
6. **`racr`/`air_yards_share`/`wopr` have extreme outliers** (racr −102 to 150; air_yards_share −9 to 8) driven by near-zero or negative air-yard denominators — clamp or volume-filter before modeling.
7. **`dakota` is NULL below 5 attempts** even when `attempts > 0` (max attempts with NULL = 4; min with value = 5). `pacr` NULL requires zero air yards. No season-level drift: every analytics column checked (`passing_epa`, `passing_air_yards`, `dakota`, `wopr`, def columns, kicking pct/distance columns) is populated in all 18 seasons — **no fully-NULL season anywhere**.
8. **Def weekly grain includes `team`**: 71 player-weeks have two rows (different `team` values) for the same (`player_id`, `season`, `week`).
9. **Kicking `gwfg_distance` (weekly, BIGINT) vs `gwfg_distance_list` (season, VARCHAR)** — same concept, different name and type across the two tables. `fg_*_distance` columns are *sums* of list distances, not averages.
10. **EPA columns are NULL exactly when the corresponding opportunity count is 0** (`attempts`/`carries`/`targets`) — 0 violations found in either direction.

## Example queries (tested)

**1. Target-share leaders, 2024 regular season (min 10 games):**
```sql
SELECT player_display_name, recent_team,
       round(avg(target_share), 3) AS ts, sum(targets) AS tgt
FROM player_stats_week
WHERE season = 2024 AND season_type = 'REG' AND position = 'WR'
GROUP BY 1, 2 HAVING count(*) >= 10
ORDER BY ts DESC LIMIT 5;
-- Nabers 0.357, A.J. Brown 0.339, Nacua 0.325, Adams 0.308, Jefferson 0.301
```

**2. Fantasy WR1 (PPR) by season:**
```sql
SELECT season, player_display_name, round(fantasy_points_ppr, 1) AS ppr
FROM (SELECT season, player_display_name, fantasy_points_ppr,
             row_number() OVER (PARTITION BY season ORDER BY fantasy_points_ppr DESC) AS rn
      FROM player_stats_season
      WHERE season_type = 'REG' AND position = 'WR')
WHERE rn = 1 ORDER BY season DESC;
-- 2024 Chase 403.0, 2023 Lamb 405.2, 2022 Jefferson 368.7, 2021 Kupp 439.5, ...
```

**3. Most 50+ yard FG makes in a season (parsing the list column):**
```sql
SELECT player_display_name, season,
       len(list_filter(string_split(fg_made_list, ';'), x -> x::INT >= 50)) AS fg50
FROM player_stats_kicking_season
WHERE season_type = 'REG' AND fg_made_list IS NOT NULL
ORDER BY fg50 DESC LIMIT 5;
-- Aubrey 2024: 14, Boswell 2024: 13, Fairbairn 2024: 13, ...
```

## v_player_stats_def_week_all / v_player_stats_kicking_week_all (added 2026-08-03)

Cross-era weekly defense and kicking, same seam pattern as
v_player_stats_week_all: pre-2025 dedicated tables UNION the v2 columns from
player_stats_week_v2. Use the views, never union raw tables.

Grain: player x season x week x team (v1 splits multi-team weeks by team; the
v2 arm is filtered to rows with actual defensive/kicking activity or a
defensive position_group, because v2 lists every rostered player).

v1 -> view rename map (defense): def_tackles is recomputed as
def_tackles_solo + def_tackle_assists in the v2 arm (identity verified on
100% of v1 rows); def_safety -> def_safeties; def_fumble_recovery_opp ->
fumble_recovery_opp. Kicking column names match across eras (verified).
