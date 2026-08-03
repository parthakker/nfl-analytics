# PFR Advanced Stats Tables

Source: Pro-Football-Reference advanced stats via nflverse. Seasons **2018–2024 only**. Eight tables — four season-level, four weekly (game-level):

| Table | Rows | Grain |
|---|---|---|
| `advstats_season_pass` | 732 | QB (passer) x season |
| `advstats_season_rush` | 2,420 | rusher x season |
| `advstats_season_rec` | 3,525 | receiver x season |
| `advstats_season_def` | 6,380 | defender x season |
| `advstats_week_pass` | 4,740 | passer x game |
| `advstats_week_rush` | 16,106 | rusher x game |
| `advstats_week_rec` | 31,191 | receiver x game |
| `advstats_week_def` | 54,419 | defender x game |

Verified grain: `(pfr_id, season)` is unique in all season tables; `(pfr_player_id, game_id)` unique in all weekly tables (0 duplicate groups). Weekly tables include playoffs (`game_type` in `REG`, `WC`, `DIV`, `CON`, `SB`; `week` 1–22). Season tables are **regular-season totals** with playoff stats excluded.

## CRITICAL: player key is `pfr_id`, not `gsis_id`

These tables have **no** `gsis_id`. Season tables key on `pfr_id`, weekly tables on `pfr_player_id` (same id space, e.g. `MahoPa00`). Bridge to the rest of the warehouse through `players` (which has both `pfr_id` and `gsis_id`; `pfr_id` is unique there — 21,981 distinct over 24,509 rows, 0 duplicates, so the join is safe 1:1).

Verified match rates (rows whose pfr id resolves to a non-null `players.gsis_id`):

| Table | Matched / total | Rate |
|---|---|---|
| `advstats_season_pass` | 728 / 732 | 99.45% |
| `advstats_season_rush` | 2,416 / 2,420 | 99.83% |
| `advstats_season_rec` | 3,512 / 3,525 | 99.63% |
| `advstats_season_def` | 6,363 / 6,380 | 99.73% |
| `advstats_week_pass` | 4,728 / 4,740 | 99.75% |
| `advstats_week_rush` | 16,094 / 16,106 | 99.93% |
| `advstats_week_rec` | 31,118 / 31,191 | 99.77% |
| `advstats_week_def` | 54,300 / 54,419 | 99.78% |

The pfr id itself is **never null** in any table; the ~0.2–0.5% misses are fringe players absent from `players` (e.g. `BrowZa00` Zach Brown, `HodgTr00` Tre'Vius Tomlinson).

Canonical bridge pattern (tested):

```sql
SELECT a.player, p.gsis_id, p.display_name, a.pressure_pct
FROM advstats_season_pass a
JOIN players p ON a.pfr_id = p.pfr_id          -- weekly: a.pfr_player_id = p.pfr_id
WHERE a.season = 2024 AND a.pass_attempts >= 300
ORDER BY a.pressure_pct DESC;
```

## Team columns and codes (verified, messy)

- Season tables `advstats_season_rush/rec/def` use **`tm`**; `advstats_season_pass` uses **`team`**; all weekly tables use **`team`** (+ `opponent`).
- Codes are mostly nflverse-style (`GB`, `KC`, `SF`, `JAX` — **not** PFR's `GNB`/`KAN`/`SFO`), but the tables disagree with each other on LA/LV:
  - `advstats_season_pass`: `LAR` (all years), `OAK` (2018–19), **`LVR`** (2020–24). `LVR` is a PFR-ism that appears **nowhere else in the warehouse** and is **not covered by `team_aliases`** (which only has SD→LAC, OAK→LV, STL→LA, JAC→JAX, LAR→LA). Map it yourself.
  - `advstats_season_rush/rec/def`: fully backdated `LA` and `LV` for all seasons 2018–2024 (Oakland-era rows already say `LV`; no `OAK`/`LAR` ever).
  - Weekly tables: `LA` (all years), `OAK` (2018–19), `LV` (2020–24) — matches `play_by_play`/`games` usage except the historical `OAK`, which `team_aliases` does map (OAK→LV).
- Multi-team season rows use **`2TM`** / **`3TM`** as the team code (e.g. 2022 Christian McCaffrey is one `2TM` row). There are **no per-team split rows** for traded players — the combined row is all you get. Filter or map `%TM` before any team join.

## game_id (weekly tables)

`game_id` uses the warehouse-standard `2024_01_ARI_BUF` format (`{season}_{week:02d}_{away}_{home}`). Tested: all **1,942 / 1,942** distinct weekly `game_id`s join to `play_by_play.game_id`; joins to `games.game_id` also verified. `pfr_game_id` is PFR's key, format `YYYYMMDD0{home}` lowercase (e.g. `201809060phi`) — only needed for PFR cross-reference.

## Percentage scales (verified, inconsistent)

| Where | Scale |
|---|---|
| `advstats_season_pass` (`drop_pct`, `bad_throw_pct`, `pressure_pct`, `on_tgt_pct`) | **0–100** (e.g. 27.4 = 27.4%) |
| `advstats_season_rec.drop_percent`, `advstats_season_def.cmp_percent` / `m_tkl_percent` | **0–1** (0.083 = 8.3%) |
| All weekly pct columns (`passing_drop_pct`, `times_pressured_pct`, `receiving_drop_pct`, `def_completion_pct`, `def_missed_tackle_pct`) | **0–1** |

`pressure_pct` can exceed 100/1.0 (max 150.0 season, 1.5 weekly): pressures are counted on all dropbacks but the denominator is pass attempts, so tiny samples blow up (2023 Aaron Rodgers: 1 att, 3 pressures, 150.0). Apply an attempts floor.

---

## `advstats_season_pass` (732 rows)

No `pos`/`g`/`gs`/`age`/`loaded` columns (unlike the other season tables). Observed ranges from `SUMMARIZE`.

| Column | Type | Meaning / observed range |
|---|---|---|
| `player` | VARCHAR | Display name. Never null. |
| `team` | VARCHAR | See team-codes section. Includes `2TM`, `LVR`, `OAK`, `LAR`. |
| `season` | BIGINT | 2018–2024. |
| `pfr_id` | VARCHAR | PFR player id (`MahoPa00`). Never null. |
| `pass_attempts` | BIGINT | 1–733. Table includes anyone with 1+ attempt (WRs on trick plays). |
| `throwaways` | BIGINT | 0–48. |
| `spikes` | BIGINT | 0–8. |
| `drops` | BIGINT | Receiver drops of this QB's throws. 0–40. |
| `drop_pct` | DOUBLE | 0–100 scale. 0.0–100.0. |
| `bad_throws` | BIGINT | Uncatchable/poor throws (PFR charted). 0–127. |
| `bad_throw_pct` | DOUBLE | 0–100 scale, denominator excludes spikes/throwaways. 0.0–100.0. |
| `pocket_time` | DOUBLE | Avg seconds in pocket. 0.0–6.4. ~1.1% null (scattered, 0–3 rows/season). |
| `times_blitzed` | BIGINT | 0–244. |
| `times_hurried` | BIGINT | 0–121. |
| `times_hit` | BIGINT | Hit as/after throwing. 0–84. |
| `times_pressured` | BIGINT | hurries + hits + pressured sacks. 0–214. |
| `pressure_pct` | DOUBLE | 0–100 scale; can exceed 100 (max 150.0) on tiny samples. |
| `batted_balls` | BIGINT | 0–24. **All null in 2018** (14.5% overall). |
| `on_tgt_throws` | BIGINT | Accurately thrown balls. 0–545. **All null in 2018.** |
| `on_tgt_pct` | DOUBLE | 0–100 scale. 0.0–100.0. **All null in 2018.** |
| `rpo_plays`, `rpo_yards` | BIGINT | Run-pass-option plays/total yards. 0–173 / −15–1,395. **All null in 2018.** |
| `rpo_pass_att`, `rpo_pass_yards` | BIGINT | 0–122 / −7–1,107. **All null in 2018.** |
| `rpo_rush_att`, `rpo_rush_yards` | BIGINT | 0–92 / −8–671. **All null in 2018.** |
| `pa_pass_att`, `pa_pass_yards` | BIGINT | Play-action attempts/yards. 0–191 / −2–1,643. **All null in 2018.** |

## `advstats_season_rush` (2,420 rows)

| Column | Type | Meaning / observed range |
|---|---|---|
| `season`, `player`, `pfr_id` | | As above. Never null. |
| `tm` | VARCHAR | Note: `tm` not `team`. Backdated `LA`/`LV`; `2TM`/`3TM` for multi-team. |
| `age` | BIGINT | Season age. 20–45. |
| `pos` | VARCHAR | PFR position, incl. combos (`WR/QB`, `C`). 0.6% null. |
| `g`, `gs` | BIGINT | Games / games started. 1–17 / 0–17. |
| `att` | BIGINT | Carries. 1–378. |
| `yds` | BIGINT | Rush yards. −28–2,027. |
| `td` | BIGINT | 0–18. |
| `x1d` | BIGINT | Rushing first downs. 0–107. **~7% null** (14–30 rows/season, all years). |
| `ybc` | BIGINT | Yards before contact (total). −28–958. 1 null. |
| `ybc_att` | DOUBLE | YBC per attempt. −28.0–42.0. |
| `yac` | BIGINT | Yards **after contact** (rushing sense, not after-catch). 0–1,073. |
| `yac_att` | DOUBLE | YAC per attempt. 0.0–18.0. |
| `brk_tkl` | BIGINT | Broken tackles forced. 0–35. |
| `att_br` | DOUBLE | Attempts per broken tackle. 1.0–96.0. **57% null — null whenever `brk_tkl = 0`** (undefined ratio). Compute `brk_tkl/att` yourself instead. |
| `loaded` | DATE | Load timestamp, 2023-08-21–2024-12-05. Metadata only. |

## `advstats_season_rec` (3,525 rows)

| Column | Type | Meaning / observed range |
|---|---|---|
| `season`, `player`, `pfr_id`, `tm`, `age`, `pos`, `g`, `gs`, `loaded` | | As in season_rush (`pos` 0.7% null). |
| `tgt` | BIGINT | Targets. 1–191. |
| `rec` | BIGINT | Receptions. 0–149. |
| `yds` | BIGINT | Receiving yards. −11–1,947. |
| `td` | BIGINT | 0–18. |
| `x1d` | BIGINT | Receiving first downs. 0–91. ~9% null. |
| `ybc` | BIGINT | Yards before catch (total air on receptions). −130–1,242. |
| `ybc_r` | DOUBLE | YBC per reception. −10.0–48.0. 4.3% null (null when `rec = 0`). |
| `yac` | BIGINT | Yards **after catch**. −16–1,019. |
| `yac_r` | DOUBLE | YAC per reception. −9.0–49.0. Null when `rec = 0`. |
| `adot` | DOUBLE | Avg depth of target. −10.0–45.0. Never null. |
| `brk_tkl` | BIGINT | Broken tackles after catch. 0–17. |
| `rec_br` | DOUBLE | Receptions per broken tackle. 0.5–106.0. **50% null when `brk_tkl = 0`.** |
| `drop` | BIGINT | Drops. 0–13. |
| `drop_percent` | DOUBLE | **0–1 scale** (unlike season_pass `drop_pct`). 0.0–1.0. |
| `int` | BIGINT | INTs thrown when targeted. 0–11. |
| `rat` | DOUBLE | Passer rating when targeted. 0.0–158.3. |

## `advstats_season_def` (6,380 rows)

| Column | Type | Meaning / observed range |
|---|---|---|
| `season`, `player`, `pfr_id`, `tm`, `age`, `pos`, `g`, `gs`, `loaded` | | As above (`pos` 1.0% null; `g` up to 18). |
| `int` | BIGINT | Interceptions. 0–11. |
| `tgt` | BIGINT | Targets as nearest defender. 0–127. |
| `cmp` | BIGINT | Completions allowed. 0–81. |
| `cmp_percent` | DOUBLE | Completion % allowed, **0–1 scale**. 19.4% null — null when `tgt = 0` (pure pass rushers). |
| `yds` | BIGINT | Receiving yards allowed. −13–942. |
| `yds_cmp` | DOUBLE | Yards per completion allowed. −8.0–76.0. 23.5% null (when `cmp = 0`). |
| `yds_tgt` | DOUBLE | Yards per target allowed. −8.0–75.0. Null when `tgt = 0`. |
| `td` | BIGINT | TDs allowed in coverage. 0–11. |
| `rat` | DOUBLE | Passer rating allowed. 0.0–158.3. Null when `tgt = 0`. |
| `dadot` | DOUBLE | Avg depth of target when targeted. −11.0–58.0. Null when `tgt = 0`. |
| `air` | BIGINT | Air yards on completions allowed. −30–687. |
| `yac` | BIGINT | YAC allowed. −4–551. |
| `bltz` | BIGINT | Times blitzed. 0–174. |
| `hrry` | BIGINT | QB hurries. 0–32. |
| `qbkd` | BIGINT | QB knockdowns. 0–28. |
| `sk` | DOUBLE | Sacks (halves possible). 0.0–22.5. |
| `prss` | BIGINT | Pressures. 0–70. |
| `comb` | BIGINT | Combined tackles. 0–192. |
| `m_tkl` | BIGINT | Missed tackles. 0–24. |
| `m_tkl_percent` | DOUBLE | **0–1 scale**; verified formula `m_tkl / (comb + m_tkl)`. 1.6% null, rising 2018 (4) → 2024 (29): null when `comb + m_tkl = 0`. |

## Weekly tables — shared columns

All four share these (never null unless noted):

| Column | Type | Notes |
|---|---|---|
| `game_id` | VARCHAR | `2018_01_ATL_PHI` … `2024_22_KC_PHI`. 100% joins to `play_by_play` / `games`. |
| `pfr_game_id` | VARCHAR | `YYYYMMDD0{home}` (e.g. `201809060phi`). |
| `season` | BIGINT | 2018–2024. |
| `week` | BIGINT | 1–22 (playoffs use continuing week numbers: SB = 21 through 2020, 22 from 2021). |
| `game_type` | VARCHAR | `REG`, `WC`, `DIV`, `CON`, `SB`. |
| `team`, `opponent` | VARCHAR | nflverse-style; `OAK` in 2018–19, `LV` after; `LA` for Rams throughout. |
| `pfr_player_name` | VARCHAR | Display name. |
| `pfr_player_id` | VARCHAR | Join key → `players.pfr_id`. |

**Dead cross-position columns**: each weekly table carries leftover columns from the combined PFR feed that are **never populated** — the only values are the literal string `'NA'` (2018–2021 rows) or NULL (2022–2024 rows). Verified via `SELECT DISTINCT`: 
`advstats_week_pass`: `receiving_drop`, `receiving_drop_pct`, `def_times_blitzed`, `def_times_hurried`, `def_times_hitqb`. 
`advstats_week_rush`: `receiving_broken_tackles`. 
`advstats_week_rec`: `rushing_broken_tackles`, `passing_drops`, `passing_drop_pct`. 
Ignore all of these.

## `advstats_week_pass` (4,740 rows) — live columns

| Column | Type | Meaning / observed range |
|---|---|---|
| `passing_drops` | BIGINT | Drops by receivers. 0–9. |
| `passing_drop_pct` | DOUBLE | 0–1 scale. 0.0–1.0. |
| `passing_bad_throws` | BIGINT | 0–19. |
| `passing_bad_throw_pct` | DOUBLE | 0–1 scale. 0.0–1.0. |
| `times_sacked` | BIGINT | 0–11. (Season table lacks this.) |
| `times_blitzed` | BIGINT | 0–39. |
| `times_hurried` | BIGINT | 0–20. |
| `times_hit` | BIGINT | 0–12. |
| `times_pressured` | BIGINT | 0–28. |
| `times_pressured_pct` | DOUBLE | 0–1 scale; max 1.5 (small-sample artifact). |

## `advstats_week_rush` (16,106 rows) — live columns

| Column | Type | Meaning / observed range |
|---|---|---|
| `carries` | BIGINT | 0–37 (0-carry rows exist). |
| `rushing_yards_before_contact` | BIGINT | −28–191. |
| `rushing_yards_before_contact_avg` | **VARCHAR** | Numeric-as-string (`'5.3'`, `'-1'`); 4 rows are `'NA'`. Use `TRY_CAST(... AS DOUBLE)`. |
| `rushing_yards_after_contact` | BIGINT | −4–127. |
| `rushing_yards_after_contact_avg` | **VARCHAR** | Same string issue; `TRY_CAST`. |
| `rushing_broken_tackles` | BIGINT | 0–12. |

## `advstats_week_rec` (31,191 rows) — live columns

| Column | Type | Meaning / observed range |
|---|---|---|
| `receiving_broken_tackles` | BIGINT | 0–11. |
| `receiving_drop` | BIGINT | 0–6. |
| `receiving_drop_pct` | DOUBLE | 0–1 scale. 0.0–1.0. |
| `receiving_int` | BIGINT | INTs on targets to this player. 0–4. |
| `receiving_rat` | DOUBLE | Passer rating when targeted. 0.0–158.3. |

## `advstats_week_def` (54,419 rows) — live columns

Coverage-stat columns are **VARCHAR** here. Missing values are the string `'NA'` in 2018–2021 and true NULL in 2022–2024 (verified: e.g. `def_completion_pct` has 2,341–2,849 `'NA'`/season in 2018–21 and 2,475–2,645 NULLs/season in 2022–24, never both). `TRY_CAST(col AS DOUBLE)` handles both. Missing = player had 0 targets (or 0 tackle chances for `def_missed_tackle_pct`).

| Column | Type | Meaning / observed range (after cast) |
|---|---|---|
| `def_ints` | BIGINT | 0–3. |
| `def_targets` | BIGINT | 0–19. |
| `def_completions_allowed` | BIGINT | 0–17. |
| `def_completion_pct` | VARCHAR→DOUBLE | **0–1 scale.** |
| `def_yards_allowed` | VARCHAR→DOUBLE | −1 up. |
| `def_yards_allowed_per_cmp`, `def_yards_allowed_per_tgt` | VARCHAR→DOUBLE | |
| `def_receiving_td_allowed` | VARCHAR→DOUBLE | |
| `def_passer_rating_allowed` | VARCHAR→DOUBLE | 0.0–158.3. |
| `def_adot` | VARCHAR→DOUBLE | Avg depth of target. |
| `def_air_yards_completed`, `def_yards_after_catch` | VARCHAR→DOUBLE | |
| `def_times_blitzed` | BIGINT | 0–35. |
| `def_times_hurried` | BIGINT | 0–9. |
| `def_times_hitqb` | BIGINT | 0–6. |
| `def_sacks` | DOUBLE | 0.0–6.0 (halves). |
| `def_pressures` | BIGINT | 0–10. |
| `def_tackles_combined` | BIGINT | 0–21. |
| `def_missed_tackles` | BIGINT | 0–7. |
| `def_missed_tackle_pct` | VARCHAR→DOUBLE | **0–1 scale**, = missed / (combined + missed). |

## Gotchas (all verified by query)

1. **No gsis_id** — always bridge via `players.pfr_id` (99.4–99.9% match; see rates above).
2. **Percent-scale trap**: `advstats_season_pass` percentages are 0–100; every other table (incl. all weekly) is 0–1. Mixing them silently 100x's your numbers.
3. **`LVR`** in `advstats_season_pass` (2020–24 Raiders) exists nowhere else and is missing from `team_aliases`; season pass also keeps `OAK`/`LAR` while season rush/rec/def backdate to `LV`/`LA`. Weekly matches pbp except historical `OAK`.
4. **`2TM`/`3TM` rows**: season tables collapse traded players into one non-team row; no per-team splits exist.
5. **2018 season_pass holes**: `batted_balls`, `on_tgt_*`, all `rpo_*`, all `pa_*` are 100% null for 2018 (charting started 2019).
6. **`'NA'` strings**: weekly VARCHAR stat columns use literal `'NA'` for missing in 2018–2021 and NULL from 2022 — `WHERE col IS NOT NULL` alone misses half the bad rows; use `TRY_CAST`.
7. **Dead columns**: 9 weekly columns (listed above) contain only `'NA'`/NULL, never data.
8. **Ratio columns null at zero denominator**: `att_br` (57% null), `rec_br` (50% null) are null when broken tackles = 0 — sorting by them drops the worst performers; compute `brk_tkl/att` directly. Same for `cmp_percent`/`rat`/`dadot` (`tgt=0`) and `m_tkl_percent`.
9. **`yac` means different things**: yards after *contact* in rush tables, yards after *catch* in rec/def tables.
10. **`pressure_pct` > 100** possible (max 150.0 / weekly 1.5) on tiny attempt counts — always apply a `pass_attempts` floor.
11. Season tables are regular-season only; weekly tables include playoffs — summing weekly rows without `game_type = 'REG'` will not reconcile to season tables.

## Example queries (tested)

Most-pressured QBs, 2024 (note 0–100 scale):

```sql
SELECT a.player, p.gsis_id, a.pass_attempts, a.times_pressured, a.pressure_pct
FROM advstats_season_pass a
JOIN players p ON a.pfr_id = p.pfr_id
WHERE a.season = 2024 AND a.pass_attempts >= 300
ORDER BY a.pressure_pct DESC LIMIT 5;
-- C.J. Stroud 27.4, Sam Darnold 25.7, Daniel Jones 24.5, Mahomes 23.6, Minshew 23.4
```

RBs forcing missed tackles at the best rate, 2024 (avoid null-riddled `att_br`):

```sql
SELECT player, tm, att, brk_tkl, ROUND(brk_tkl * 1.0 / att, 3) AS brk_tkl_per_att
FROM advstats_season_rush
WHERE season = 2024 AND pos = 'RB' AND att >= 100
ORDER BY brk_tkl_per_att DESC LIMIT 5;
-- Josh Jacobs .118, Derrick Henry .117, David Montgomery .114, JK Dobbins .114, Chase Brown .112
```

Worst WR drop rates, 2024 (`drop_percent` is 0–1):

```sql
SELECT player, tm, tgt, "drop", ROUND(drop_percent * 100, 1) AS drop_pct
FROM advstats_season_rec
WHERE season = 2024 AND pos = 'WR' AND tgt >= 70
ORDER BY drop_percent DESC LIMIT 5;
-- Tank Dell 8.3%, Malik Nabers 7.8%, Demario Douglas 7.1%, Darnell Mooney 6.9%, Brian Thomas 6.8%
```

Bonus — weekly coverage with the VARCHAR cast pattern:

```sql
SELECT pfr_player_name, def_targets, def_completions_allowed,
       TRY_CAST(def_completion_pct AS DOUBLE) AS cmp_pct
FROM advstats_week_def
WHERE season = 2020 AND def_targets >= 8
ORDER BY cmp_pct ASC LIMIT 4;   -- TRY_CAST handles both 'NA' (2018-21) and NULL (2022-24)
```
