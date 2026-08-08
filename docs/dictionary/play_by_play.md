# Data Dictionary: `play_by_play` and `games`

DuckDB warehouse: `nfl.duckdb` (nflverse data). Query read-only:

```python
import duckdb

con = duckdb.connect("nfl.duckdb", read_only=True)  # from the repo root
```

All facts below were verified with queries against this database (2026-08).

---

## Table: `play_by_play`

**860,268 rows, 372 columns.** One row per play event, seasons 2007–2024 (game dates 2007-09-06 through 2025-02-09 — a season's Super Bowl lands in February of the following calendar year; always filter on `season`, not date year). Includes non-play rows: timeouts, quarter/game boundaries, comments. Natural key: (`game_id`, `play_id`).

### Key encodings (verified)

- **`game_id` format**: `{season}_{week:02d}_{AWAY}_{HOME}`, e.g. `2007_01_ARI_SF` = 2007 week 1, ARI at SF (confirmed: that game has `home_team='SF'`, `away_team='ARI'`). Week is zero-padded.
- **`season_type`**: only `REG` (823,653 rows) and `POST` (36,615). No preseason.
- **Week numbering**: REG is 1–17 for 2007–2020, 1–18 from 2021 (17-game era). POST is 18/19/20/21 (WC/DIV/CONF/SB) for 2007–2020 and 19/20/21/22 from 2021. 2020 is the only season with 6 wild-card games at week 18; 2021+ have 6 at week 19.
- **Team abbreviations**: `posteam` takes exactly 32 modern values across ALL seasons — `LA`, `LAC`, `LV` appear from 2007; `STL`, `SD`, `OAK` never appear. The warehouse pre-normalized relocated franchises. The `team_aliases` table maps external/legacy codes to canonical: `SD→LAC`, `OAK→LV`, `STL→LA`, `JAC→JAX`, `LAR→LA`. Use it when joining outside data: `JOIN team_aliases a ON ext.team = a.alias` then match `a.canonical` to `posteam`.
- **`play_type`** distinct values and counts:

| play_type | rows |
|---|---|
| pass | 356,792 |
| run | 255,271 |
| no_play | 79,500 |
| kickoff | 49,536 |
| punt | 43,239 |
| NULL | 25,491 |
| extra_point | 22,919 |
| field_goal | 18,786 |
| qb_kneel | 7,353 |
| qb_spike | 1,381 |

NULL `play_type` rows are administrative events; by `play_type_nfl`: END_QUARTER 14,931, END_GAME 4,879, GAME_START 4,879, COMMENT 632, UNSPECIFIED 168.

### Group 1 — Game & play context (fully documented)

| column | type | meaning / values | nulls |
|---|---|---|---|
| `play_id` | BIGINT | Play event id, ascending within game (not gapless). | none |
| `game_id` | VARCHAR | `{season}_{WW}_{AWAY}_{HOME}`; joins to `games`. | none |
| `old_game_id` | BIGINT | Legacy NFL GameCenter id, e.g. `2023122406` (YYYYMMDDNN). | none |
| `home_team` / `away_team` | VARCHAR | Canonical team codes (see aliases above). | none |
| `season` | BIGINT | 2007–2024. | none |
| `season_type` | VARCHAR | `REG` / `POST`. | none |
| `week` | BIGINT | See numbering above. | none |
| `game_date` | DATE | Calendar date of game. | none |
| `posteam` | VARCHAR | Team with possession. | NULL on 44,681 admin rows (END QUARTER, GAME, some 3rd-timeout rows) |
| `posteam_type` | VARCHAR | `home` / `away`. | NULL when posteam NULL |
| `defteam` | VARCHAR | Defensive team. | as posteam |
| `yardline_100` | BIGINT | Yards from opponent end zone, 1–99 (100 = own goal line side). | NULL on admin rows |
| `yrdln` | VARCHAR | Human-readable spot, e.g. `SF 36`. | rare |
| `side_of_field` | VARCHAR | Team code of the field side the ball is on. | admin rows |
| `qtr` | BIGINT | 1–5; 6 exists on 5 plays (double-OT playoff `2012_19_BAL_DEN`). | none |
| `game_half` | VARCHAR | `Half1` / `Half2` / `Overtime`. | none |
| `down` | BIGINT | 1–4. NULL on 134,947 rows: all kickoffs, extra points, admin rows, many no_plays. | see left |
| `ydstogo` | BIGINT | Yards to first down. | none |
| `goal_to_go` | BIGINT | 0/1 flag. | none |
| `time` | TIME | Game clock at snap (mm:ss stored as TIME). | rare |
| `quarter_seconds_remaining` / `half_seconds_remaining` / `game_seconds_remaining` | BIGINT | Seconds left in quarter/half/game. | rare |
| `desc` | VARCHAR | Full play text. **Reserved word in DuckDB — quote as `"desc"`.** | none |
| `play_type` | VARCHAR | See table above. | 25,491 admin rows |
| `play_type_nfl` | VARCHAR | NFL's raw typing: PASS, RUSH, SACK, PENALTY, TIMEOUT, KICK_OFF, PUNT, XP_KICK, FIELD_GOAL, END_QUARTER, INTERCEPTION, END_GAME, GAME_START, UNSPECIFIED, PAT2, COMMENT, FUMBLE_RECOVERED_BY_OPPONENT, FREE_KICK. | none |
| `yards_gained` | BIGINT | Net yards on play. | admin rows |
| `shotgun` | BIGINT | 0/1 (1 on 366,388 rows). | none |
| `no_huddle` | BIGINT | 0/1 (1 on 57,398). | none |
| `qb_dropback` | BIGINT | 0/1 — pass att + sacks + scrambles. | admin rows |
| `qb_kneel` | BIGINT | 0/1. When 1, `play_type` is `qb_kneel` (7,353) or `no_play` (22). | none |
| `qb_spike` | BIGINT | 0/1. When 1, `play_type` is `qb_spike` (1,381) or `no_play` (50). | none |
| `qb_scramble` | BIGINT | 0/1 (see scramble gotcha). | none |
| `drive` | BIGINT | NFL drive number. **NULL on 10,070 rows — prefer `fixed_drive`.** | see left |
| `sp` | BIGINT | 0/1 scoring play flag. | none |
| `quarter_end` | BIGINT | 0/1 end-of-quarter row flag. | none |

### Group 2 — Scores & timeouts (fully documented)

| column | type | meaning | nulls |
|---|---|---|---|
| `total_home_score` / `total_away_score` | BIGINT | Running score before/at play. | none |
| `posteam_score` / `defteam_score` | BIGINT | Score from possession perspective, pre-play. | admin rows |
| `score_differential` | BIGINT | posteam − defteam, pre-play. | admin rows |
| `posteam_score_post` / `defteam_score_post` / `score_differential_post` | BIGINT | Same, post-play. | admin rows |
| `home_timeouts_remaining` / `away_timeouts_remaining` | BIGINT | 0–3 (per half). | none |
| `posteam_timeouts_remaining` / `defteam_timeouts_remaining` | BIGINT | 0–3. | admin rows |
| `timeout` | BIGINT | 0/1. Timeouts are mostly their own `no_play` rows (34,813) but 1,881 are attached to real plays (pass 1,365, run 409, punt 69, kickoff 37, fg 1). | none |
| `timeout_team` | VARCHAR | Team calling timeout. | NULL unless timeout=1 |
| `td_team` / `td_player_name` / `td_player_id` | VARCHAR | Scoring team/player on TDs (id is GSIS `00-00xxxxx`). | NULL unless TD |

### Group 3 — EPA / WP analytics (fully documented)

| column | type | meaning / verified range | nulls |
|---|---|---|---|
| `ep` | DOUBLE | Expected points, posteam perspective, pre-play. | admin rows |
| `epa` | DOUBLE | Expected points added. Pass plays: mean +0.020, p1/p99 −5.13/+4.09, extremes −13.03/+8.88. Runs: mean −0.042, p1/p99 −3.21/+2.82. Kneels mean −0.563. | NULL on 9,862 rows, almost all `play_type IS NULL` admin rows (END_QUARTER/GAME_START/etc.); populated on no_play, kickoffs, XPs |
| `qb_epa` | DOUBLE | EPA crediting QB (fumbled snaps etc. adjusted). Differs from `epa` on only 1,352 plays. | as epa |
| `air_epa` / `yac_epa` | DOUBLE | EPA split into air / after-catch components (pass plays). | non-pass NULL |
| `comp_air_epa` / `comp_yac_epa` | DOUBLE | Same, zeroed for incompletions. | non-pass NULL |
| `wp` | DOUBLE | Posteam pre-play win probability, 0–1 (model, no Vegas prior). | NULL on 12,448 rows (admin) |
| `def_wp` / `home_wp` / `away_wp` | DOUBLE | 1−wp and home/away views. | as wp |
| `wpa` | DOUBLE | Win prob added. p1/p99 = −0.114/+0.120, extremes ±0.999, median 0. | as wp |
| `vegas_wp` / `vegas_home_wp` | DOUBLE | WP incorporating pregame spread. Full coverage 2007–2024 (≈99.4% of rows each season). | admin rows |
| `vegas_wpa` / `vegas_home_wpa` | DOUBLE | WPA under the Vegas model. | admin rows |
| `success` | BIGINT | 0/1. **Verified definition: `success = (epa > 0)` — 0 mismatches over all 850k EPA rows.** Not the Football-Outsiders yardage definition. | NULL exactly when epa NULL (9,862) |
| `cp` | DOUBLE | Completion probability of the pass. | pass attempts only (325,342 rows non-null) |
| `cpoe` | DOUBLE | Completion pct over expected, in percentage points; observed −92.3 to +85.3. | as cp |
| `xpass` | DOUBLE | Probability play is a pass given situation (654,400 non-null; scrimmage plays). | ST/admin NULL |
| `pass_oe` | DOUBLE | Pass over expected, percentage points, −99.5 to +98.0. | as xpass |
| `xyac_epa` / `xyac_mean_yardage` / `xyac_median_yardage` / `xyac_success` / `xyac_fd` | DOUBLE/BIGINT | Expected-YAC family for completions. | receptions only |
| `no_score_prob`, `opp_fg_prob`, `opp_safety_prob`, `opp_td_prob`, `fg_prob`, `safety_prob`, `td_prob`, `extra_point_prob`, `two_point_conversion_prob` | DOUBLE | Next-score-type probabilities underlying `ep`. | admin rows |

One-line (cumulative running totals per game, rarely needed):
`total_home_epa`, `total_away_epa`, `total_home_rush_epa`, `total_away_rush_epa`, `total_home_pass_epa`, `total_away_pass_epa`, `total_home_comp_air_epa`, `total_away_comp_air_epa`, `total_home_comp_yac_epa`, `total_away_comp_yac_epa`, `total_home_raw_air_epa`, `total_away_raw_air_epa`, `total_home_raw_yac_epa`, `total_away_raw_yac_epa`, and the analogous 14 `*_wpa` running totals; `air_wpa`, `yac_wpa`, `comp_air_wpa`, `comp_yac_wpa` (WPA analogues of the EPA splits).

### Group 4 — Passing detail (fully documented)

| column | type | meaning | nulls |
|---|---|---|---|
| `pass` | BIGINT | 0/1 dropback flag — **includes sacks and scrambles**. 390,752 rows =1. | none |
| `pass_attempt` | BIGINT | 0/1 official pass attempt (incl. sacks per nflverse convention). | admin rows |
| `complete_pass` / `incomplete_pass` | BIGINT | 0/1. | admin rows |
| `pass_length` | VARCHAR | `short` (270,682) / `deep` (61,368); NULL otherwise (sacks, non-pass). | see left |
| `pass_location` | VARCHAR | `left` / `middle` / `right`; NULL otherwise. | see left |
| `air_yards` | BIGINT | Depth of target; observed −93 to 69. Non-null on 332,782 of 356,792 pass-type plays (NULL on sacks/laterals). | see left |
| `yards_after_catch` | BIGINT | YAC on completions (209,668 non-null). | incompletions NULL |
| `passing_yards` / `receiving_yards` | BIGINT | Yards credited on completion. | NULL if no completion |
| `sack` | BIGINT | 0/1; 22,624 sacks, all `play_type='pass'`; mean EPA −1.75. | none |
| `qb_hit` | BIGINT | 0/1. | none |
| `interception` | BIGINT | 0/1; 8,491 INTs (40 also `fumble_lost=1` — INT then fumble on return). | admin rows |

### Group 5 — Rushing detail (fully documented)

| column | type | meaning | nulls |
|---|---|---|---|
| `rush` | BIGINT | 0/1 designed rush (excludes scrambles). 247,129 rows =1. | none |
| `rush_attempt` | BIGINT | 0/1 official rush attempt (includes scrambles/kneels). | admin rows |
| `run_location` | VARCHAR | `left` (92,622) / `middle` (68,753) / `right` (91,130). | non-rush NULL |
| `run_gap` | VARCHAR | `end` (63,171) / `tackle` (61,325) / `guard` (59,255); NULL for middle runs. | see left |
| `rushing_yards` | BIGINT | Yards on the carry. | non-rush NULL |

### Group 6 — Down/outcome flags (fully documented)

| column | type | meaning | nulls |
|---|---|---|---|
| `first_down` | BIGINT | 0/1 play produced a first down or TD (190,763 =1). | 26,328 admin rows |
| `first_down_rush` / `first_down_pass` / `first_down_penalty` | BIGINT | 0/1 source of first down. | admin rows |
| `third_down_converted` / `third_down_failed` | BIGINT | 0/1. | admin rows |
| `fourth_down_converted` / `fourth_down_failed` | BIGINT | 0/1. | admin rows |
| `touchdown`, `pass_touchdown`, `rush_touchdown`, `return_touchdown` | BIGINT | 0/1. | admin rows |
| `fumble`, `fumble_lost`, `fumble_forced`, `fumble_not_forced`, `fumble_out_of_bounds` | BIGINT | 0/1; 5,719 lost fumbles. | admin rows |
| `safety` | BIGINT | 0/1. | admin rows |
| `tackled_for_loss` | BIGINT | 0/1. | admin rows |
| `play` | BIGINT | 0/1 "real scrimmage play" flag (pass or rush, excl. ST/admin/no-play). | none |
| `special` | BIGINT | 0/1 special-teams play. | none |
| `special_teams_play` | BIGINT | 0/1 (raw NFL flag). | none |
| `aborted_play` | BIGINT | 0/1; 2,080 aborted snaps. | none |
| `out_of_bounds` | BIGINT | 0/1. | none |

### Group 7 — Player identity (key columns documented)

All `*_player_id` columns, plus `id`, `passer_id`, `rusher_id`, `receiver_id`, `fantasy_player_id`, `td_player_id`, use **GSIS format `00-00xxxxx`** (verified: 358,209/358,209 passer ids, 91,223/91,223 kicker ids, 8,491/8,491 interception ids match `00-00%`). They join to `players.gsis_id` / weekly stats tables.

| column | meaning |
|---|---|
| `passer_player_id` / `passer_player_name` | Passer on dropbacks (name style `T.Brady`). |
| `rusher_player_id` / `rusher_player_name` | Ball carrier on rushes. |
| `receiver_player_id` / `receiver_player_name` | Targeted receiver. |
| `name` / `id` / `jersey_number` | The "play maker": passer if dropback, else rusher (verified: on runs `name` = `rusher_player_name`). |
| `passer` / `rusher` / `receiver` (+ `passer_id`, `rusher_id`, `receiver_id`, `*_jersey_number`) | Cleaned mutually-exclusive versions of the above (scrambles get `rusher` filled from QB). |
| `fantasy` / `fantasy_id` / `fantasy_player_name` / `fantasy_player_id` | Rusher or receiver (fantasy-relevant player). |
| `kicker_player_id/_name`, `punter_player_id/_name` | Kicker (FG/XP/KO), punter. |
| `sack_player_id/_name`, `half_sack_1/2_player_id/_name` | Sackers. |
| `interception_player_id/_name` | Intercepting defender. |
| `punt_returner_player_id/_name`, `kickoff_returner_player_id/_name` | Returners. |

One-line each (same GSIS conventions): `lateral_receiver_*`, `lateral_rusher_*`, `lateral_sack_*`, `lateral_interception_*`, `lateral_punt_returner_*`, `lateral_kickoff_returner_*` (+ `lateral_receiving_yards`, `lateral_rushing_yards`, `lateral_reception`, `lateral_rush`, `lateral_return`, `lateral_recovery`); `tackle_for_loss_1/2_*`; `qb_hit_1/2_*`; `forced_fumble_player_1/2_team/_player_id/_player_name`; `solo_tackle`, `solo_tackle_1/2_team/_player_id/_player_name`; `assist_tackle`, `assist_tackle_1..4_player_id/_player_name/_team`; `tackle_with_assist`, `tackle_with_assist_1/2_player_id/_player_name/_team`; `pass_defense_1/2_player_id/_player_name`; `fumbled_1/2_team/_player_id/_player_name`; `fumble_recovery_1/2_team/_yards/_player_id/_player_name`; `own_kickoff_recovery_player_id/_name`; `blocked_player_id/_name`; `safety_player_id/_name`.

### Group 8 — Penalties / challenges (fully documented)

| column | type | meaning | nulls |
|---|---|---|---|
| `penalty` | BIGINT | 0/1; 60,097 penalty plays. Penalties that negate the play appear as `play_type='no_play'` (43,903 of 79,500 no_plays have penalty=1; 34,757 no_plays are timeouts). Accepted penalties on completed plays keep their real play_type. | 26,328 admin rows |
| `penalty_team` | VARCHAR | Penalized team. | 100% filled when penalty=1 |
| `penalty_type` | VARCHAR | Text, e.g. Offensive Holding (11,294), False Start (11,161), DPI (4,430). | 35 penalty rows lack type |
| `penalty_yards` | BIGINT | Assessed yards. | non-penalty NULL |
| `penalty_player_id/_name` | VARCHAR | Penalized player (GSIS id). | may be NULL (team fouls) |
| `replay_or_challenge` | BIGINT | 0/1 reviewed play. | none |
| `replay_or_challenge_result` | VARCHAR | `upheld` (3,758) / `reversed` (3,153) / `denied` (14). | non-review NULL |

### Group 9 — Drive / series (fully documented)

| column | type | meaning | nulls |
|---|---|---|---|
| `fixed_drive` | BIGINT | nflverse-corrected drive number, 1..n per game. **Never NULL — use this over `drive`.** | none |
| `fixed_drive_result` | VARCHAR | Punt (275,184), Touchdown (227,732), Field goal (168,224), Turnover (68,569), Turnover on downs (43,331), End of half (37,173), Missed field goal (29,268), Opp touchdown (9,767), Safety (979). | 41 |
| `drive` | BIGINT | Raw NFL drive number; NULL on 10,070 rows. | see left |
| `series` | BIGINT | First-down series number within game. | admin rows |
| `series_success` | BIGINT | 0/1 series ended in first down or TD. | admin rows |
| `series_result` | VARCHAR | First down (410,024), Punt, Touchdown, Field goal, Turnover, Turnover on downs, QB kneel, Missed field goal, End of half, Opp touchdown, Safety. | 44 |
| `drive_start_transition` | VARCHAR | KICKOFF (410,086), PUNT, INTERCEPTION, FUMBLE, DOWNS, MISSED_FG, MUFFED_PUNT. | 10,085 |
| `drive_end_transition` | VARCHAR | PUNT, TOUCHDOWN, FIELD_GOAL, INTERCEPTION, DOWNS, MISSED_FG, FUMBLE, END_GAME, END_HALF, … | 10,084 |
| `drive_play_count`, `drive_first_downs`, `drive_yards_penalized` | BIGINT | Drive aggregates (repeated on every row of drive). | ~1% |
| `drive_time_of_possession` | TIME | Drive TOP. | ~1% |
| `ydsnet` | BIGINT | Net yards of the drive. | admin rows |

One-line: `drive_inside20`, `drive_ended_with_score`, `drive_quarter_start`, `drive_quarter_end`, `drive_game_clock_start`, `drive_game_clock_end`, `drive_start_yard_line`, `drive_end_yard_line`, `drive_play_id_started`, `drive_play_id_ended`, `drive_real_start_time`, `order_sequence` (sort key within game).

### Group 10 — Kicking / special teams (fully documented)

| column | type | meaning | nulls |
|---|---|---|---|
| `kickoff_attempt` / `punt_attempt` / `field_goal_attempt` / `extra_point_attempt` / `two_point_attempt` | BIGINT | 0/1 flags. | admin rows |
| `field_goal_result` | VARCHAR | `made` (15,802) / `missed` (2,613) / `blocked` (371). | non-FG NULL |
| `extra_point_result` | VARCHAR | `good` (22,091) / `failed` (655) / `blocked` (157) / `aborted` (16). | non-XP NULL |
| `two_point_conv_result` | VARCHAR | `success` (843) / `failure` (918). | non-2pt NULL |
| `kick_distance` | BIGINT | Kick/punt distance in yards; non-null on 111,559 of 111,561 punt/FG/kickoff plays. | see left |
| `touchback` | BIGINT | 0/1. | admin rows |
| `punt_blocked` | BIGINT | 0/1. | admin rows |
| `return_team` / `return_yards` | VARCHAR/BIGINT | Returning team and yards on kick/punt/INT/fumble returns. | non-return NULL |
| `st_play_type` | VARCHAR | **All 860,268 rows NULL — dead column.** | all |

One-line: `punt_inside_twenty`, `punt_in_endzone`, `punt_out_of_bounds`, `punt_downed`, `punt_fair_catch`, `kickoff_inside_twenty`, `kickoff_in_endzone`, `kickoff_out_of_bounds`, `kickoff_downed`, `kickoff_fair_catch`, `own_kickoff_recovery`, `own_kickoff_recovery_td`, `defensive_two_point_attempt`, `defensive_two_point_conv`, `defensive_extra_point_attempt`, `defensive_extra_point_conv`.

### Group 11 — Game-level columns (denormalized onto every play; fully documented)

These repeat per game and match the `games` table (verified: 0 roof mismatches on join).

| column | type | meaning | nulls |
|---|---|---|---|
| `home_coach` / `away_coach` | VARCHAR | Head coach full names, e.g. `Mike Tomlin`. **100% coverage: 860,268/860,268 non-null in pbp; 4,879/4,879 in games.** | none |
| `home_score` / `away_score` | BIGINT | Final score. | none |
| `result` | BIGINT | Final home margin. Verified `result = home_score − away_score` on all 860,268 rows. | none |
| `total` | BIGINT | Verified `= home_score + away_score` on all rows. | none |
| `spread_line` | DOUBLE | Closing spread, **positive = home favored** (see games table for proof). | none |
| `total_line` | DOUBLE | Closing over/under, 28.5–63.5. | none |
| `location` | VARCHAR | `Home` (846,857) / `Neutral` (13,411). | none |
| `div_game` | BIGINT | 0/1 divisional matchup. | none |
| `roof` | VARCHAR | `outdoors` / `dome` / `closed` / `open`. | none |
| `surface` | VARCHAR | See games table; beware `'grass '` trailing-space variant. | small |
| `temp` / `wind` | BIGINT | Kickoff temperature (F) / wind (mph). **NULL for all dome/closed/open-roof games**; 592,379 rows non-null (outdoors only, minus 122 outdoor games missing data). | see left |
| `stadium` / `game_stadium` | VARCHAR | Stadium name (two source variants; both fully populated). | none |
| `stadium_id` | VARCHAR | e.g. `NYC01`. | none |
| `start_time` | VARCHAR | String like `12/24/23, 13:03:05` (not a timestamp type). | none |
| `weather` | VARCHAR | Raw text, e.g. `Clear Temp: 64� F, Humidity: 67%, Wind: west 18 mph` (note mojibake `�` for the degree sign). | 7,693 NULL |
| `home_opening_kickoff` | BIGINT | 0/1 home team received... actually =1 when home team kicked/received opening KO split ~51/49; treat as raw flag. | none |

### Group 12 — Misc (one line each)

`nfl_api_id` (UUID-ish game id), `play_clock` (seconds on play clock at snap), `play_deleted` (only 1 row =1), `time_of_day` (TIMESTAMPTZ, 821,076 non-null), `end_clock_time` (TIMESTAMPTZ, sparse: 120,648 non-null), `end_yard_line` (sparse text spot).

---

## Table: `games`

**4,879 rows** (4,671 REG + 208 POST), one per game, derived from play_by_play. `game_id` is unique.

| column | type | meaning (verified) | nulls |
|---|---|---|---|
| `game_id` | VARCHAR | `{season}_{WW}_{AWAY}_{HOME}`; unique key. | none |
| `old_game_id` | BIGINT | Legacy id `YYYYMMDDNN`. | none |
| `season` | BIGINT | 2007–2024. | none |
| `week` | BIGINT | REG 1–17 (≤2020) / 1–18 (2021+); POST 18–21 / 19–22. | none |
| `season_type` | VARCHAR | `REG` / `POST`. | none |
| `game_date` | DATE | Game date (SB in Feb of following year). | none |
| `start_time` | VARCHAR | e.g. `9/8/24, 13:03:08` (string, local kickoff-ish timestamp). | none |
| `home_team` / `away_team` | VARCHAR | Canonical codes (LA/LAC/LV throughout). | none |
| `home_coach` / `away_coach` | VARCHAR | Head coaches; **no NULLs (4,879/4,879 each)**. | none |
| `home_score` / `away_score` | BIGINT | Final score, 0–70. | none |
| `spread_line` | DOUBLE | Closing spread, −19 to +27. **Sign convention verified: positive = home team favored.** When `spread_line > 0` (3,142 games) home wins 67.5% with avg margin +5.95; when negative (1,732 games) home wins 34.8% with avg margin −4.61; corr(spread_line, home margin) = +0.43. So `spread_line` ≈ expected home margin; home covers iff `home_score − away_score > spread_line`. 5 pick'em games at 0.0. | none |
| `total_line` | DOUBLE | Over/under, 28.5–63.5. | none |
| `roof` | VARCHAR | `outdoors` (3,484), `dome` (737), `closed` (554), `open` (104). | none |
| `surface` | VARCHAR | `grass` (2,618), `fieldturf` (1,337), `sportturf` (278), `matrixturf` (195), `astroturf` (109), `a_turf` (101), **`'grass '` with trailing space (93)**, `astroplay` (78), `dessograss` (27). | 43 NULL |
| `temp` | BIGINT | Kickoff temp F, −6 to 97. NULL for ALL dome/closed/open games and 122 outdoors games (3,362/3,484 outdoors have it). | see left |
| `wind` | BIGINT | Wind mph, 0–71 (71 is suspect; verify before use). Same null pattern as temp. | see left |
| `stadium` | VARCHAR | Stadium name. | none |
| `stadium_id` | VARCHAR | e.g. `BUF00`, `NYC01`. | none |
| `div_game` | BIGINT | 0/1; 1,754 divisional games. | none |

---

## Gotchas (all verified by query)

1. **Team codes are pre-normalized.** `SELECT posteam, MIN(season) FROM play_by_play GROUP BY 1` returns exactly 32 modern codes, each spanning 2007–2024; `STL`, `SD`, `OAK` never occur. Use `team_aliases` (SD→LAC, OAK→LV, STL→LA, JAC→JAX, LAR→LA) only for joining external data.
2. **`success` is literally `epa > 0`.** `SELECT COUNT(*) FROM play_by_play WHERE epa IS NOT NULL AND success != (CASE WHEN epa>0 THEN 1 ELSE 0 END)` → 0. It is not the down-and-distance yardage definition.
3. **Scrambles are `pass=1` but `play_type='run'`** (14,130 rows with `qb_scramble=1`; query: `SELECT sack, qb_scramble, COUNT(*) FROM play_by_play WHERE pass=1 AND play_type='run' GROUP BY 1,2`). Sacks are `play_type='pass'`. For pass/rush splits use the `pass`/`rush` columns, not `play_type`.
4. **`surface` has a trailing-space duplicate**: `SELECT DISTINCT surface, LENGTH(surface) FROM games` shows both `grass` (len 5, 2,618) and `'grass '` (len 6, 93). Use `TRIM(surface)`.
5. **`st_play_type` is 100% NULL** (`SELECT COUNT(*), COUNT(st_play_type) FROM play_by_play` → 860268, 0). Ignore it.
6. **`drive` is NULL on 10,070 rows; `fixed_drive` is never NULL.** Use `fixed_drive`/`fixed_drive_result`.
7. **`desc` must be quoted** (`"desc"`) — DuckDB reserved word; unquoted use throws a parser error.
8. **Admin rows pollute naive averages**: 25,491 rows have NULL `play_type` (END_QUARTER/GAME_START/END_GAME/COMMENT) and 44,681 have NULL `posteam`; `epa` is NULL on 9,862 rows (almost all these admin rows). Timeouts are 34,813 `no_play` rows, but 1,881 timeouts are flagged on real plays. Filter with `play_type IS NOT NULL` or `pass=1 OR rush=1` as appropriate.
9. **Postseason week shift**: POST weeks are 18–21 through 2020 and 19–22 from 2021 (`SELECT season, week, COUNT(DISTINCT game_id) FROM games WHERE season_type='POST' GROUP BY 1,2`). Week 18 means Wild Card pre-2021 but a REG week from 2021 on — never filter playoffs by week number alone.
10. **`qtr` reaches 6**: 5 plays in `2012_19_BAL_DEN` (double-OT playoff). `game_half='Overtime'` covers qtr 5 and 6.
11. **`temp`/`wind` NULL for every non-outdoors roof** including `open` (query: `SELECT roof, COUNT(*), COUNT(temp) FROM games GROUP BY 1` → open 104/0, dome 737/0, closed 554/0, outdoors 3484/3362). Max wind of 71 mph is a likely data error.
12. **`weather` text has encoding mojibake** (`Clear Temp: 64� F, ...`) — the degree symbol is corrupted; parse numerically with regex, or prefer `temp`/`wind`.
13. **Season vs calendar year**: `MAX(game_date)` = 2025-02-09 while `MAX(season)` = 2024. Filter on `season`.
14. **`qb_epa` != `epa` on 1,352 plays** (QB-crediting adjustment); use `qb_epa` for QB evaluation.
15. **`interception=1 AND fumble_lost=1` co-occur on 40 plays** (pick then fumbled return) — don't count turnovers as `interception + fumble_lost` without dedup via `GREATEST(...)` if you want per-play turnovers.

---

## Example queries (tested against this database)

**1. Best QB seasons by EPA/dropback (min 300 dropbacks, REG season):**

```sql
SELECT season, passer_player_name,
       COUNT(*) AS dropbacks,
       ROUND(AVG(qb_epa), 3) AS epa_per_db,
       ROUND(AVG(cpoe), 1)   AS cpoe
FROM play_by_play
WHERE qb_dropback = 1 AND passer_player_id IS NOT NULL AND season_type = 'REG'
GROUP BY 1, 2
HAVING COUNT(*) >= 300
ORDER BY epa_per_db DESC
LIMIT 10;
-- Top: 2007 T.Brady 0.417, 2011 A.Rodgers 0.417, 2013 P.Manning 0.387
```

**2. Team pass vs rush efficiency, 2024 regular season:**

```sql
SELECT posteam,
       ROUND(AVG(CASE WHEN pass = 1 THEN epa END), 3)     AS pass_epa,
       ROUND(AVG(CASE WHEN rush = 1 THEN epa END), 3)     AS rush_epa,
       ROUND(AVG(CASE WHEN pass = 1 THEN success END), 3) AS pass_sr
FROM play_by_play
WHERE season = 2024 AND season_type = 'REG'
  AND (pass = 1 OR rush = 1) AND epa IS NOT NULL
GROUP BY 1
ORDER BY pass_epa DESC;
-- Top: BAL 0.324, BUF 0.299, DET 0.269
```

**3. Home cover rate and scoring by roof type (uses the positive-=-home-favored spread convention):**

```sql
SELECT roof, COUNT(*) AS games,
       ROUND(AVG(CASE WHEN home_score - away_score > spread_line THEN 1.0
                      WHEN home_score - away_score = spread_line THEN 0.5
                      ELSE 0 END), 3) AS home_cover_rate,
       ROUND(AVG(home_score + away_score), 1) AS avg_total,
       ROUND(AVG(total_line), 1)              AS avg_total_line
FROM games
GROUP BY 1 ORDER BY games DESC;
-- outdoors 0.486 cover / 44.3 pts; dome 0.509 / 48.1; closed 0.483 / 46.7; open 0.462 / 47.9
```
