# Context Tables: team_stats, injuries, officials, team_aliases

Source: nflverse. All claims below verified with read-only queries against `nfl.duckdb` (2026-08).

---

## team_stats

Season-level team aggregates. **576 rows, seasons 2007–2024, grain = (team, season, season_type)** — verified unique (576 rows = 576 distinct keys). Exactly **one row per team-season**.

### season_type semantics (important)

| season_type | Rows | Meaning |
|---|---|---|
| `REG` | 350 | Regular season only — present **only for teams that missed the playoffs** |
| `REG+POST` | 226 | Regular season + playoffs combined — present **only for playoff teams** |

There is **no `POST` value and no pure-`REG` row for playoff teams** (e.g. KC 2023 has a single `REG+POST` row with `games = 21`). Per-season counts confirm: 12 `REG+POST` rows/season 2007–2019, 14/season 2020–2024 (matches playoff-field size). `games` ranges 16–21. To compare teams on equal footing, normalize per game or accept that playoff teams' totals include postseason.

Team codes are **canonical/current for all seasons**: 32 codes, each with 18 rows — `LA`, `LAC`, `LV`, `JAX` appear back to 2007. No `STL`/`SD`/`OAK`/`JAC`/`LAR` ever appear (aliases pre-normalized).

### Columns (101)

#### Identifiers
| Column | Type | Notes |
|---|---|---|
| `season` | BIGINT | 2007–2024 |
| `team` | VARCHAR | Canonical code (see team_aliases) |
| `season_type` | VARCHAR | `REG` or `REG+POST` (see above) |
| `games` | BIGINT | Games included in the row (16–21) |

#### Passing (team offense)
| Column | Type | Notes |
|---|---|---|
| `completions`, `attempts` | BIGINT | Pass completions / attempts |
| `passing_yards`, `passing_tds`, `passing_interceptions` | BIGINT | |
| `sacks_suffered`, `sack_yards_lost` | BIGINT | Sacks taken by this team's offense |
| `sack_fumbles`, `sack_fumbles_lost` | BIGINT | Fumbles on sacks / lost |
| `passing_air_yards`, `passing_yards_after_catch` | BIGINT | |
| `passing_first_downs` | BIGINT | |
| `passing_epa` | DOUBLE | Total EPA on pass plays |
| `passing_cpoe` | DOUBLE | Completion % over expected |
| `passing_2pt_conversions` | BIGINT | |

#### Rushing (team offense)
| Column | Type | Notes |
|---|---|---|
| `carries`, `rushing_yards`, `rushing_tds` | BIGINT | |
| `rushing_fumbles`, `rushing_fumbles_lost` | BIGINT | |
| `rushing_first_downs` | BIGINT | |
| `rushing_epa` | DOUBLE | Total EPA on rush plays |
| `rushing_2pt_conversions` | BIGINT | |

#### Receiving (mirrors passing from the catch side; team-level ≈ passing totals)
| Column | Type | Notes |
|---|---|---|
| `receptions`, `targets` | BIGINT | |
| `receiving_yards`, `receiving_tds` | BIGINT | |
| `receiving_fumbles`, `receiving_fumbles_lost` | BIGINT | |
| `receiving_air_yards`, `receiving_yards_after_catch` | BIGINT | |
| `receiving_first_downs` | BIGINT | |
| `receiving_epa` | DOUBLE | |
| `receiving_2pt_conversions` | BIGINT | |

#### Defense (what this team's defense recorded)
| Column | Type | Notes |
|---|---|---|
| `def_tackles_solo`, `def_tackles_with_assist`, `def_tackle_assists` | BIGINT | |
| `def_tackles_for_loss`, `def_tackles_for_loss_yards` | BIGINT | |
| `def_fumbles_forced` | BIGINT | |
| `def_sacks`, `def_sack_yards` | BIGINT | Sacks made by this defense |
| `def_qb_hits` | BIGINT | |
| `def_interceptions`, `def_interception_yards`, `def_pass_defended` | BIGINT | |
| `def_tds` | BIGINT | Defensive touchdowns |
| `def_fumbles` | BIGINT | Fumbles by defensive players |
| `def_safeties` | BIGINT | |

#### Fumble recovery / misc
| Column | Type | Notes |
|---|---|---|
| `misc_yards` | BIGINT | Miscellaneous yardage (e.g. blocked-kick returns) |
| `fumble_recovery_own`, `fumble_recovery_yards_own` | BIGINT | Own fumbles recovered |
| `fumble_recovery_opp`, `fumble_recovery_yards_opp` | BIGINT | Opponent fumbles recovered |
| `fumble_recovery_tds` | BIGINT | |
| `special_teams_tds` | BIGINT | |

#### Penalties / game management
| Column | Type | Notes |
|---|---|---|
| `penalties`, `penalty_yards` | BIGINT | Committed by this team |
| `timeouts` | BIGINT | Timeouts taken over the season (range 38–99) |

#### Returns
| Column | Type | Notes |
|---|---|---|
| `punt_returns`, `punt_return_yards` | BIGINT | |
| `kickoff_returns`, `kickoff_return_yards` | BIGINT | |

#### Kicking — field goals
| Column | Type | Notes |
|---|---|---|
| `fg_made`, `fg_att`, `fg_missed`, `fg_blocked` | BIGINT | `fg_att = made + missed + blocked` |
| `fg_long` | BIGINT | Longest made FG |
| `fg_pct` | DOUBLE | 0–1 fraction (min 0.474, max 1.0) |
| `fg_made_0_19` … `fg_made_60_` | BIGINT | Made by distance bucket (0-19, 20-29, 30-39, 40-49, 50-59, 60+) |
| `fg_missed_0_19` … `fg_missed_60_` | BIGINT | Missed by distance bucket |
| `fg_made_distance`, `fg_missed_distance`, `fg_blocked_distance` | BIGINT | **Sum** of distances (verified: ARI 2007 `fg_made_distance` 733 = sum of `fg_made_list`) |

#### Kicking — list-format columns (VARCHAR)
Semicolon-delimited distances in yards, one entry per kick, no spaces. NULL when no such kicks.

| Column | Real example (ARI 2007 REG) |
|---|---|
| `fg_made_list` | `35;28;52;42;48;40;41;50;32;50;47;23;19;33;19;26;32;29;31;23;33` |
| `fg_missed_list` | `53;47;52;55;54;32;50;54` |
| `fg_blocked_list` | `39` |
| `gwfg_distance_list` | `42;55;31` (game-winning FG attempt distances) |

Parse with `string_split(col, ';')` then cast to INT.

#### Kicking — PATs and game-winning FGs
| Column | Type | Notes |
|---|---|---|
| `pat_made`, `pat_att`, `pat_missed`, `pat_blocked` | BIGINT | Extra points |
| `pat_pct` | DOUBLE | 0–1 fraction (min 0.788) |
| `gwfg_made`, `gwfg_att`, `gwfg_missed`, `gwfg_blocked` | BIGINT | Game-winning FG attempts (final ~2 min / OT go-ahead) |

---

## injuries

Weekly official injury-report entries. **84,684 rows, seasons 2009–2024** (no 2007–2008). One row ≈ one player appearing on one team's injury report for one week.

| Column | Type | Notes |
|---|---|---|
| `season` | BIGINT | 2009–2024 |
| `game_type` | VARCHAR | `REG` (81,425), `WC` (1,478), `DIV` (1,031), `CON` (526), `SB` (224) |
| `team` | VARCHAR | **Era-accurate codes**: `OAK` 2009–2019, `SD` 2009–2016, `STL` 2009–2015, then `LV`/`LAC`/`LA`. 35 distinct codes — join to team_stats requires team_aliases for pre-relocation seasons |
| `week` | BIGINT | 1–22 |
| `gsis_id` | VARCHAR | Player id, `00-00xxxxx` format; joins to `players`/`rosters_weekly` |
| `position` | VARCHAR | Player position |
| `full_name`, `first_name`, `last_name` | VARCHAR | |
| `report_primary_injury`, `report_secondary_injury` | VARCHAR | Body part on official game-status report (top: Knee, Ankle, Hamstring, Shoulder, Foot, Concussion, Groin). NULL in ~27k rows (practice-report-only entries). Rows with `report_status='Note'` contain free-text sentences here |
| `report_status` | VARCHAR | `NULL` (26,960), `Questionable` (22,333), `Probable` (17,400 — **2009–2015 only**, category abolished 2016), `Out` (14,725), `Doubtful` (3,260), `Note` (6, 2024 only — free-text advisories) |
| `practice_primary_injury`, `practice_secondary_injury` | VARCHAR | Body part on practice report |
| `practice_status` | VARCHAR | `Full Participation in Practice` (38,799), `Did Not Participate In Practice` (23,068), `Limited Participation in Practice` (21,627), `Out (Definitely Will Not Play)` (974), **literal `"\n "` junk value** (215 rows, 2011–2024), `Note` (1) |
| `date_modified` | TIMESTAMP WITH TIME ZONE | Last report update, tz-aware (e.g. `2024-12-15 09:17:06-05:00`); range 2010-01-01 → 2025-02-07; **4,866 NULLs** |

### Grain
`(season, week, team, gsis_id)` is **almost** unique: exactly 2 duplicate keys in 84,684 rows (2024 wk15: Cade Stover HOU, Tyler Conklin NYJ — each has a `Questionable` row and a later `Out` row with different `date_modified`). If you need strict uniqueness, keep the row with max `date_modified`.

### game_type coverage quirks (verified per season)
- 2013 has no `SB` rows; 2023 has only `REG,WC` (no DIV/CON/SB). All other seasons 2009–2024 have all five.
- Playoff weeks use week numbers up to 22 with `game_type` distinguishing rounds.

---

## officials

One row per official per game. **19,834 rows, seasons 2015–2024, 2,744 distinct games.**

| Column | Type | Notes |
|---|---|---|
| `game_id` | BIGINT | **Numeric date-based id, e.g. `2015091000` — this is NOT the nflverse `2024_01_ARI_BUF` id.** Matches `games.old_game_id` (BIGINT). See join pattern below |
| `game_key` | BIGINT | NFL internal game key |
| `official_name` | VARCHAR | Full name. Embedded commas from the raw CSV loaded correctly (e.g. `Terry Killens, Jr.` — 55 rows) |
| `position` | VARCHAR | `Referee`, `Umpire`, `Back Judge`, `Side Judge`, `Field Judge`, `Line Judge` (~2,740 each); `Down Judge` (2,207, 2017+) vs `Head Linesman` (534, pre-2017 name for same role); `Replay Official` (191); plus long tail of `Alternate*`, `AL`, `RA` labels |
| `jersey_number` | BIGINT | No NULLs |
| `official_id` | BIGINT | Stable id per official |
| `season` | BIGINT | 2015–2024 |
| `season_type` | VARCHAR | **Inconsistent across eras**: 2015–2018 uses `REG`,`WC`,`DIV`,`CON`,`SB`; 2019–2024 uses `REG`,`POST` |
| `week` | BIGINT | |

### Crew size
A standard crew is **7 on-field officials** (Referee, Umpire, Down Judge/Head Linesman, Line Judge, Field Judge, Side Judge, Back Judge). Rows per game: 7 for 2,425 games (88%); 8 for 228 (adds Replay Official); 6 for 12 (one missing); 9–15 for a handful (alternates listed, e.g. Super Bowls). To count "games worked," filter to a position or `COUNT(DISTINCT game_id)`.

### Join pattern (tested)
`officials.game_id` = `games.old_game_id` (both BIGINT). Direct join to the string `games.game_id` matches **0 rows**.

```sql
SELECT count(*) AS total, count(g.game_id) AS matched
FROM officials o LEFT JOIN games g ON o.game_id = g.old_game_id;
-- total 19834, matched 19806  (99.86%)
-- distinct games: 2744, matched 2740
```

The 4 unmatched games (`2021121902`, `2021121904`, `2021121908` = 2021 wk15; `2023010200` = 2022 wk17) are **rescheduled games**: `games.old_game_id` encodes the actual played date (e.g. `2021_15_SEA_LA` → `2021122101`, moved 12/19 → 12/21) while officials keeps the originally scheduled date-based id. Use a LEFT JOIN and expect these to drop.

### Name integrity caveat
Commas survived loading, but the same person can appear under variant spellings: `Terry Killens, Jr.` (55 rows) **and** `Terry Killens Jr.` (47 rows). Group by `official_id` (stable) rather than `official_name` when aggregating careers.

---

## team_aliases

5 rows: historical/alternate code → canonical code.

| alias | canonical |
|---|---|
| SD | LAC |
| OAK | LV |
| STL | LA |
| JAC | JAX |
| LAR | LA |

Usage verified against actual data:
- **team_stats**: never needs aliases — already canonical for all seasons (LA/LAC/LV/JAX back to 2007).
- **injuries**: needs aliases — uses `OAK` (2009–2019), `SD` (2009–2016), `STL` (2009–2015). `JAC` and `LAR` do not appear in injuries.
- **officials**: has no team column.

Join idiom: `COALESCE(a.canonical, i.team)` via `LEFT JOIN team_aliases a ON i.team = a.alias`.

---

## Gotchas (all verified by query)

1. **team_stats has no pure regular-season row for playoff teams.** `season_type` is only `REG` (non-playoff teams) or `REG+POST` (playoff teams, postseason included, `games` up to 21). Cross-team season comparisons must normalize per game or tolerate mixed scopes.
2. **officials.game_id joins on games.old_game_id, not games.game_id** (numeric vs `YYYY_WW_AWAY_HOME` string; direct string join matches 0 rows). 4 of 2,744 games don't match due to COVID-era reschedules.
3. **officials.season_type scheme changed in 2019**: `WC/DIV/CON/SB` (2015–2018) → single `POST` (2019–2024). Filter postseason with `season_type <> 'REG'`.
4. **injuries.team uses era-accurate codes** (OAK/SD/STL) while team_stats uses current codes — route joins through team_aliases.
5. **`Probable` only exists 2009–2015** in `injuries.report_status` (NFL dropped the category); `NULL` report_status (~32%) means the player was on the practice report but had no game-status designation, not "healthy".
6. **injuries.practice_status contains a literal `"\n "` junk value** (215 rows) and `report_status='Note'` rows (6, 2024) put free-text sentences in the injury columns.
7. **injuries grain is not strictly unique**: 2 player-weeks have both a `Questionable` and a later `Out` row — dedupe on max `date_modified` if needed.
8. **Official name spelling variants exist** (`Terry Killens, Jr.` vs `Terry Killens Jr.`) — aggregate by `official_id`.
9. **fg_pct / pat_pct are 0–1 fractions**, not 0–100 percentages.
10. **injuries starts in 2009, officials in 2015** — neither covers team_stats' full 2007–2024 range.

---

## Example queries (all tested)

### 1. Penalty flags per game by referee (officials → games → play_by_play)
```sql
SELECT o.official_name AS referee,
       COUNT(DISTINCT p.game_id) AS games,
       ROUND(SUM(p.penalty)::DOUBLE / COUNT(DISTINCT p.game_id), 2) AS penalties_per_game
FROM officials o
JOIN games g        ON o.game_id = g.old_game_id      -- numeric-id bridge
JOIN play_by_play p ON p.game_id = g.game_id          -- string-id side
WHERE o.position = 'Referee' AND p.penalty = 1
GROUP BY 1
HAVING games >= 50
ORDER BY penalties_per_game DESC;
-- Top: Walt Anderson 14.79/gm (78 games), Ed Hochuli 13.68 (50), Peter Morelli 13.25 (61)
```

### 2. Top offensive EPA per game by season (handles REG vs REG+POST)
```sql
SELECT season, team, season_type,
       ROUND((passing_epa + rushing_epa) / games, 2) AS off_epa_per_game
FROM team_stats
QUALIFY ROW_NUMBER() OVER (PARTITION BY season
                           ORDER BY (passing_epa + rushing_epa) / games DESC) <= 2
ORDER BY season DESC, off_epa_per_game DESC;
-- 2024: BAL 13.18/gm, BUF 10.65 (per-game divides out the extra playoff games in REG+POST rows)
```

### 3. "Out" designations per team-season — the closest injuries gets to "games missed"
```sql
SELECT i.season,
       COALESCE(a.canonical, i.team) AS team,
       COUNT(*)                     AS out_designations,
       COUNT(DISTINCT i.gsis_id)    AS players_ruled_out
FROM injuries i
LEFT JOIN team_aliases a ON i.team = a.alias
WHERE i.report_status = 'Out' AND i.game_type = 'REG'
GROUP BY 1, 2
ORDER BY out_designations DESC;
-- Most: 2022 TEN 71 Out designations (31 players); 2020 SF 63 (27)
```

**What injuries cannot answer:** true "games missed to injury" per team-season is **not derivable** from this table alone. It records report designations, not participation: players on IR/PUP typically never appear on the weekly report, `Questionable` players may or may not play, ~32% of rows have no game-status at all, and there is no played/inactive flag. Query 3 counts *ruled-out designations*, a lower bound biased toward teams that keep injured players on the active roster. Actual availability requires joining `rosters_weekly` (status) or snap participation data.
