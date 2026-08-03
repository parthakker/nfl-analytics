# NFL Next Gen Stats (NGS) Tables

Source: nflverse NGS data (player-tracking derived). Seasons **2016–2024**. Three tables:

| Table | Rows | Grain |
|---|---|---|
| `ngs_passing` | 5,328 | QB x season x week (plus `week = 0` season aggregates) |
| `ngs_receiving` | 13,329 | WR/TE x season x week (plus `week = 0` season aggregates) |
| `ngs_rushing` | 5,411 | RB/HB/FB x season x week (plus `week = 0` season aggregates) |

`(season, season_type, week, player_gsis_id)` is unique in all three tables (verified: 0 duplicate groups).

## CRITICAL: `week = 0` rows are season aggregates

Each table mixes **season-total rows (`week = 0`)** with **weekly rows (`week >= 1`)** in the same table. Verified counts per season:

| Season | passing wk0 / weekly | receiving wk0 / weekly | rushing wk0 / weekly |
|---|---|---|---|
| 2016 | 39 / 534 | 132 / 1,469 | 53 / 526 |
| 2017 | 41 / 534 | 124 / 1,298 | 50 / 545 |
| 2018 | 39 / 539 | 125 / 1,294 | 55 / 539 |
| 2019 | 39 / 537 | 125 / 1,293 | 48 / 540 |
| 2020 | 41 / 540 | 132 / 1,388 | 55 / 541 |
| 2021 | 38 / 570 | 127 / 1,448 | 52 / 566 |
| 2022 | 40 / 563 | 122 / 1,344 | 48 / 569 |
| 2023 | 45 / 575 | 115 / 1,358 | 49 / 574 |
| 2024 | 43 / 571 | 129 / 1,306 | 47 / 554 |

**Every query must filter on `week`:**

```sql
-- season-level analysis (regular-season totals, qualified players only)
WHERE week = 0
-- weekly analysis
WHERE week > 0
```

Forgetting the filter double-counts: a season's production appears once in the `week = 0` row and again spread across weekly rows. All `week = 0` rows have `season_type = 'REG'` (POST rows have `week` 18–23 only); the aggregates are **regular-season totals, no postseason aggregate exists**.

## Qualification thresholds (verified)

`week = 0` rows include **only players who met NGS minimum-qualification thresholds** — not all players:

- 2024 REG: `ngs_passing` has **43** `week = 0` QBs vs **103** players with `attempts > 0` in `player_stats_season`; minimum observed `attempts` in wk0 rows is **160**.
- 2024 REG: `ngs_receiving` has **129** wk0 players (min `targets` = 45) vs **494** players with `targets > 0` in `player_stats_season`.
- 2024 REG: `ngs_rushing` has **47** wk0 players (min `rush_attempts` = 92) vs **333** players with `carries > 0`.

Weekly rows are thresholded too (observed minimums across all seasons, `week > 0`): 15 pass attempts, 5 targets, 10 rush attempts. Low-volume games/players are simply absent — do not treat this data as complete population coverage.

## Common columns (all three tables)

| Column | Type | Notes |
|---|---|---|
| `season` | BIGINT | 2016–2024. |
| `season_type` | VARCHAR | `'REG'` or `'POST'`. POST present in all tables (passing 215, receiving 558, rushing 208 rows). |
| `week` | BIGINT | 0 = REG season aggregate. Weekly: REG 1–17 / POST 18–22 through 2020; REG 1–18 / POST 19–23 from 2021 (17-game era). Postseason weeks continue the regular-season numbering. |
| `player_display_name` | VARCHAR | e.g. "Patrick Mahomes". Never null. |
| `player_position` | VARCHAR | passing: `QB` only. receiving: `WR`, `TE` only (no RBs — see Gotchas). rushing: `RB`, `HB` (45), `FB` (9). |
| `team_abbr` | VARCHAR | Modern nflverse-style codes, **backdated**: `LV`, `LAC`, `LAR` used even for 2016 (no `OAK`/`SD`/`STL` ever appear). Null in exactly 30 rows, all 2021 `week = 0` aggregates (8 pass / 15 rec / 7 rush). See Gotchas re: `LAR` vs `LA`. |
| `player_gsis_id` | VARCHAR | GSIS id, `00-00xxxxx`. Never null; joins `players.gsis_id` at **100% match rate** (all 24,068 rows across the 3 tables matched). |
| `player_first_name`, `player_last_name` | VARCHAR | Never null. |
| `player_jersey_number` | BIGINT | Never null. |
| `player_short_name` | VARCHAR | e.g. "P.Mahomes". Null only in a few 2016 rows (7 pass / 15 rec / 8 rush). |

## `ngs_passing` (5,328 rows)

Ranges below are observed min–max for `week > 0` rows; season (`week = 0`) ranges in parentheses where materially tighter.

| Column | Type | Meaning / observed range |
|---|---|---|
| `avg_time_to_throw` | DOUBLE | Avg seconds from snap to release. Weekly 1.83–4.07 (season 2.30–3.27). Lower = quicker release. |
| `avg_completed_air_yards` | DOUBLE | Avg air yards on completions. Weekly -2.84–18.25. |
| `avg_intended_air_yards` | DOUBLE | Avg air yards on all attempts (intended depth). Weekly 0.10–19.34 (season 5.05–12.03). |
| `avg_air_yards_differential` | DOUBLE | Completed minus intended air yards. Weekly -10.03–3.23; always negative at season level (-4.55 to -0.83) — deep balls fail more often. |
| `aggressiveness` | DOUBLE | **Percent** (0–100 scale) of attempts into tight coverage (defender < 1 yd at catch point). Weekly 0.0–48.39 (season 8.66–25.85). |
| `max_completed_air_distance` | DOUBLE | Longest completion by actual 3D ball-travel distance, yards. Weekly 16.44–67.58. 1 null (2017). |
| `avg_air_yards_to_sticks` | DOUBLE | Avg (intended air yards − yards to first down marker). Negative = throwing short of sticks. Weekly -8.89–8.56. |
| `attempts` | BIGINT | Weekly 15–68 (min 15 = weekly qualification floor); season 131–733. |
| `pass_yards` | BIGINT | Weekly 24–525; season 709–5,316. |
| `pass_touchdowns` | BIGINT | Weekly 0–6; season 2–50. |
| `interceptions` | BIGINT | Weekly 0–6; season 0–30. |
| `passer_rating` | DOUBLE | Traditional NFL rating, 0.0–158.33 weekly. |
| `completions` | BIGINT | Weekly 5–47; season 74–490. |
| `completion_percentage` | DOUBLE | Percent, 23.81–100.0 weekly. |
| `expected_completion_percentage` | DOUBLE | Model-expected comp% given pass difficulty (xCOMP). Weekly 37.55–83.32. 1 null (2017). |
| `completion_percentage_above_expectation` | DOUBLE | **CPOE** = actual − expected comp%, percentage points. Weekly -40.33–31.38; season -11.26–8.70. 1 null (2017). |
| `avg_air_distance` | DOUBLE | Avg true 3D ball-travel distance, yards. Weekly 13.82–30.99. 1 null (2017). |
| `max_air_distance` | DOUBLE | Max 3D ball-travel distance. Weekly 23.45–72.39. 1 null (2017). |

## `ngs_receiving` (13,329 rows)

| Column | Type | Meaning / observed range |
|---|---|---|
| `avg_cushion` | DOUBLE | Avg yards between receiver and nearest defender **at snap**. Weekly 1.31–14.40 (season 3.76–8.14). Present since 2016. 3 nulls total (2017, 2021). |
| `avg_separation` | DOUBLE | Avg yards between receiver and nearest defender **at catch/incompletion**. Weekly 0.55–8.69 (season 1.71–5.66). Present since 2016 — no null seasons. |
| `avg_intended_air_yards` | DOUBLE | Avg air yards on targets to this player. Weekly -5.26–38.74. |
| `percent_share_of_intended_air_yards` | DOUBLE | Player's share of team intended air yards, percent. Weekly -22.31–149.15 (negative-depth targets and partial-week team totals produce out-of-[0,100] values); season 1.69–48.74. |
| `receptions` | BIGINT | Weekly 0–18 (0 possible: targets qualify, not catches); season 15–149. |
| `targets` | BIGINT | Weekly 5–23 (min 5 = weekly floor); season 43–191. |
| `catch_percentage` | DOUBLE | receptions/targets, percent. Weekly 0.0–100.0. |
| `yards` | BIGINT | Receiving yards. Weekly -5–300; season 133–1,947. ~2–9 nulls/season. |
| `rec_touchdowns` | BIGINT | Weekly 0–4; season 0–18. |
| `avg_yac` | DOUBLE | Avg yards after catch. Weekly -2.65–43.20. ~3–11 nulls/season. |
| `avg_expected_yac` | DOUBLE | Model-expected YAC (xYAC) given catch situation. Weekly -1.51–23.87. ~3–13 nulls/season. |
| `avg_yac_above_expectation` | DOUBLE | avg_yac − avg_expected_yac (+YAC = elusiveness above expectation). Weekly -17.28–37.74; season -1.90–5.20. Same null pattern as xYAC. |

YAC-family nulls are small and scattered across **all** seasons (3–13 rows/season, incl. 2016), typically rows where no reception occurred or tracking failed — not an era effect.

## `ngs_rushing` (5,411 rows)

| Column | Type | Meaning / observed range |
|---|---|---|
| `efficiency` | DOUBLE | Total distance traveled (tracking) per rushing yard gained — **lower = more north/south**. Weekly 0.74–145.58 (extreme highs are tiny-yardage games); season 2.78–5.35. |
| `percent_attempts_gte_eight_defenders` | DOUBLE | Percent of carries facing 8+ defenders in the box. Weekly 0.0–100.0; season 1.18–52.73. |
| `avg_time_to_los` | DOUBLE | Avg seconds from handoff to crossing the line of scrimmage. Weekly 1.87–4.04 (season 2.26–3.33). |
| `rush_attempts` | BIGINT | Weekly 10–38 (min 10 = weekly floor); season 85–378. |
| `rush_yards` | BIGINT | Weekly 1–255; season 258–2,027. |
| `avg_rush_yards` | DOUBLE | Yards per carry. Weekly 0.08–14.60. |
| `rush_touchdowns` | BIGINT | Weekly 0–6; season 0–18. |
| `expected_rush_yards` | DOUBLE | Model-expected rush yards (xYards). **NULL for ALL 2016–2017 rows** (579 + 595 rows); populated 2018+. Weekly 13.18–179.54; season 316.62–1,623.92. |
| `rush_yards_over_expected` | DOUBLE | **RYOE** = actual − expected, total yards. NULL 2016–2017. Weekly -55.42–175.89; season -218.77–561.85. |
| `rush_yards_over_expected_per_att` | DOUBLE | RYOE per carry. NULL 2016–2017. Weekly -4.22–10.35; season -1.22–2.87. |
| `rush_pct_over_expected` | DOUBLE | Share of carries gaining more than expected, expressed as a **fraction 0–1** (not 0–100; weekly 0.0–0.82, season 0.25–0.59) — unlike the other `percent_*` columns. NULL 2016–2017. |

## Gotchas (all verified by query)

1. **`week = 0` season aggregates mixed with weekly rows.** Always filter `week = 0` or `week > 0`. Verified via `GROUP BY season` with `count(*) FILTER (week=0)` — every season in every table has both kinds.
2. **`week = 0` only exists for `season_type = 'REG'`.** POST rows are weekly only (weeks 18–22 / 19–23). No postseason aggregates.
3. **Qualified players only.** `week = 0` covers ~40% of QBs (43/103 in 2024), ~26% of targeted players, ~14% of ball carriers. Weekly rows also have floors (15 att / 5 tgt / 10 carries). Joining to `player_stats_season` will drop most players.
4. **Team codes are backdated modern codes.** `LV` appears in 2016 (Raiders were in Oakland until 2020), `LAC` in 2016 (Chargers in San Diego until 2017). No `OAK`/`SD`/`STL` anywhere. Also NGS uses **`LAR`** for the Rams while `team_stats` uses **`LA`** — map via `team_aliases` or `replace(team_abbr,'LAR','LA')` before joining team-level tables.
5. **30 rows with NULL `team_abbr`, all 2021 `week = 0` aggregates** (8 passing, 15 receiving, 7 rushing — includes Cooper Kupp, Tyreek Hill). Use the player id, not team, to identify these rows.
6. **RYOE model starts in 2018.** `expected_rush_yards`, `rush_yards_over_expected`, `*_per_att`, `rush_pct_over_expected` are NULL for every 2016–2017 row. `avg_separation`/`avg_cushion` and CPOE, by contrast, are populated from 2016.
7. **`ngs_receiving` contains only WR and TE** — no RB receiving rows at all (verified `GROUP BY player_position`). RB receiving work must come from `player_stats_*` or `advstats_*`.
8. **Week numbering shifts in 2021**: REG max week 17 → 18; POST 18–22 → 19–23. Postseason week numbers continue regular-season numbering (wild card = 18 or 19, Super Bowl = 22 or 23).
9. **`rush_pct_over_expected` is a 0–1 fraction** while `percent_attempts_gte_eight_defenders`, `aggressiveness`, `catch_percentage`, and the completion percentages are 0–100.
10. **Join key**: `player_gsis_id = players.gsis_id`, 100% match rate in all three tables (24,068/24,068 rows), zero null ids.

## Example queries (tested)

CPOE leader per season (season aggregates):

```sql
SELECT season, player_display_name, team_abbr, attempts,
       completion_percentage_above_expectation AS cpoe
FROM ngs_passing
WHERE week = 0
QUALIFY row_number() OVER (PARTITION BY season ORDER BY cpoe DESC) = 1
ORDER BY season;
-- 2016 Cousins +8.70, 2019 Tannehill +8.53, 2024 Hurts +6.61
```

Fastest average time to throw, 2024:

```sql
SELECT player_display_name, team_abbr, attempts, avg_time_to_throw
FROM ngs_passing
WHERE season = 2024 AND week = 0
ORDER BY avg_time_to_throw ASC
LIMIT 5;
-- Tua Tagovailoa 2.42s, Andy Dalton 2.55s, Cooper Rush 2.55s
```

Rush yards over expected leaders, 2024:

```sql
SELECT player_display_name, team_abbr, rush_attempts, rush_yards,
       rush_yards_over_expected, rush_yards_over_expected_per_att
FROM ngs_rushing
WHERE season = 2024 AND week = 0
ORDER BY rush_yards_over_expected DESC
LIMIT 5;
-- Derrick Henry +561.9, Saquon Barkley +549.2, Chuba Hubbard +281.9
```
