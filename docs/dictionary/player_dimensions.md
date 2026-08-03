# Player Dimensions — Data Dictionary

Warehouse: `nfl.duckdb` (nflverse). Tables: `players`, `rosters_weekly`, `draft_picks`.
All claims below verified with read-only queries on 2026-08-02.

---

## 1. `players` — master player table (24,509 rows)

**Grain / PK:** one row per player. `gsis_id` is unique and non-null (24,509 rows = 24,509 distinct, 0 nulls) — verified PK. This is **THE ID bridge** for the warehouse: `gsis_id ↔ esb_id ↔ smart_id ↔ nfl_id ↔ pfr_id ↔ pff_id ↔ otc_id ↔ espn_id`.

**gsis_id format caveat (verified):** 18,118 rows use the true GSIS format `00-00XXXXX`; 6,391 older players (careers back to 1974, pre-GSIS era) carry an ESB-style fallback (e.g. `ABB498348`, identical to `esb_id`). Those older IDs never appear in `rosters_weekly` (which is 100% `00-` format), so historical players simply won't join to rosters.

### ID columns — null rates (n = 24,509)

| column | type | null % | example | notes |
|---|---|---|---|---|
| `gsis_id` | VARCHAR | 0.0% | `00-0028830` | PK. NFL GSIS ID; ESB-style fallback for pre-GSIS players |
| `esb_id` | VARCHAR | 0.0% | `AAI622937` | Elias Sports Bureau ID |
| `smart_id` | VARCHAR | 0.0% | `32004141-4962-...` | NFL "smart" UUID-style ID |
| `pfr_id` | VARCHAR | 10.3% | `AaitIs00` | Pro-Football-Reference. Best-covered external ID |
| `espn_id` | BIGINT | 60.7% | `56008`-style ints | ESPN |
| `pff_id` | BIGINT | 62.1% | | Pro Football Focus |
| `otc_id` | BIGINT | 62.5% | | OverTheCap |
| `nfl_id` | BIGINT | 68.7% | `56008` | NFL.com numeric ID |

External IDs (espn/pff/otc/nfl) are mostly populated only for modern players; the ~60-69% null rates are dominated by the historical population.

### Other columns

| column | type | notes (observed) |
|---|---|---|
| `display_name` | VARCHAR | Full display name, e.g. `Israel Abanikanda` |
| `common_first_name`, `first_name`, `last_name`, `short_name`, `football_name`, `suffix` | VARCHAR | Name variants; `football_name` is the "goes-by" name |
| `birth_date` | DATE | 1927-09-17 to 2004-09-14 |
| `position_group` | VARCHAR | 9 values: DB, OL, DL, LB, WR, RB, TE, QB, SPEC |
| `position` | VARCHAR | 25 values (WR, LB, RB, DB, DE, OT, TE, G, DT, CB, QB, C, …) |
| `ngs_position_group`, `ngs_position` | VARCHAR | Next Gen Stats position taxonomy (sparser) |
| `height` | BIGINT | Inches, 64–83 |
| `weight` | BIGINT | Pounds, nominal max 388; **bad values exist** (Gerry Raymond = 1, Jalen Milroe = 16) |
| `headshot` | VARCHAR | NFL image URL template — contains literal `{formatInstructions}` placeholder you must substitute |
| `college_name`, `college_conference` | VARCHAR | Last college / its conference |
| `jersey_number` | BIGINT | Latest jersey number |
| `rookie_season`, `last_season` | BIGINT | 1974–2025 both; career span |
| `latest_team` | VARCHAR | Most recent team (32 distinct, current GSIS codes) |
| `status` | VARCHAR | Current roster status; 13 values, top: ACT 14,931; CUT 3,269; RES 3,191; DEV 2,577 (see status legend in §2) |
| `ngs_status`, `ngs_status_short_description` | VARCHAR | NGS-side status; `ngs_status` null for 16,594 rows |
| `years_of_experience` | BIGINT | 0–26 |
| `pff_position`, `pff_status` | VARCHAR | PFF-side attributes |
| `draft_year`, `draft_round`, `draft_pick`, `draft_team` | BIGINT/VARCHAR | 1974–2025; round 1–17, pick 1–472 (pre-1994 drafts had up to 17 rounds); null for undrafted |

---

## 2. `rosters_weekly` — player-team-week (862,768 rows, seasons 2002–2025)

**Grain:** approximately `(gsis_id, season, week)` but **NOT strictly unique** — verified: 862,608 non-null-gsis rows vs 845,139 distinct keys → 16,302 duplicated keys. Breakdown (verified):

- **16,289 same-team duplicates**, all in **2002–2015** (peak 2015: 1,777). Rows differ only in `status` (e.g. Hank Poteat 2006 NYJ wk: TRT + ACT) or are fully identical (441 keys duplicated even on team+status+jersey+position). Legacy-feed artifact — dedupe with `DISTINCT` or prefer `status='ACT'`.
- **13 multi-team duplicates**, ALL one bad record: `00-0035718` in 2019 is Quinnen Williams (NYJ) but was also wrongly assigned to Isaiah Searight (NYG). No genuine "two teams same week" rows exist.

`gsis_id` is null on only 160 rows. **2017+ rows are NOT deduplicated-per-status; they are clean one-row-per-player-week.**

### Season coverage (verified row counts)

| era | rows/season | weeks | notes |
|---|---|---|---|
| 2002–2015 | ~31–32k | 1–21 | legacy feed; sparse columns (below), status-duplicates |
| 2016 | 35,020 | 1–21 | transitional |
| 2017–2020 | 44–52k | 1–21 | full modern feed |
| 2021–2024 | 45–47k | 1–22 | 17-game era, week 22 = Super Bowl |
| **2025** | **3,239** | **week = NULL** | **preseason partial — see Gotchas** |

`game_type`: REG 820,429; WC 17,215; DIV 12,508; CON 6,253; SB 3,124; NULL 3,239 (= all of 2025). Playoff weeks are included as weeks 18–22.

### 2002–2016 vs 2017+ column coverage (null %, verified)

| column | pre-2017 | 2017+ |
|---|---|---|
| `depth_chart_position` | 92.6% | 0.0% |
| `college` | 64.1% | 0.0% |
| `gsis_it_id` | 63.8% | 0.0% |
| `ngs_position` | 95.8% | 57.3% |
| `espn_id` | 74.5% | 32.5% |
| `sportradar_id` | 74.8% | 29.5% |
| `yahoo_id` | 78.3% | 33.5% |
| `rotowire_id` | 74.4% | 29.5% |
| `pff_id` | 74.6% | 38.3% |
| `pfr_id` | 80.4% | 49.0% |
| `fantasy_data_id` | 77.4% | 41.2% |
| `sleeper_id` | 77.4% | 29.5% |
| `draft_club` / `draft_number` | 27.2% / 29.1% | 41.0% / 46.9% |

Always well-populated in both eras: `season, team, position, jersey_number, status, full_name, height, weight, gsis_id, esb_id, smart_id, football_name, entry_year, rookie_year` (≤0.5% null). External fantasy IDs here are convenience columns — prefer joining `players` on `gsis_id` for ID bridging.

### Columns

| column | type | notes |
|---|---|---|
| `season` | BIGINT | 2002–2025 |
| `team` | VARCHAR | 39 distinct — includes relocated codes: OAK & LV, SD & LAC, STL & LA, plus WAS-era variants. GSIS-style codes (KC, TB), NOT PFR codes |
| `position` | VARCHAR | Roster position |
| `depth_chart_position` | VARCHAR | 2017+ only |
| `jersey_number` | VARCHAR | String here (BIGINT in `players`) |
| `status` | VARCHAR | See legend below |
| `full_name`,`first_name`,`last_name`,`football_name` | VARCHAR | |
| `birth_date` | DATE | 6.5% null post-2017 |
| `height`,`weight` | BIGINT | inches / lbs |
| `college` | VARCHAR | 2017+ |
| `gsis_id` | VARCHAR | join key to `players` (always `00-` format here) |
| `espn_id`,`sportradar_id`,`yahoo_id`,`rotowire_id`,`pff_id`,`pfr_id`,`fantasy_data_id`,`sleeper_id` | mixed | external IDs, patchy (see table above) |
| `years_exp` | BIGINT | |
| `headshot_url` | VARCHAR | |
| `ngs_position` | VARCHAR | |
| `week` | BIGINT | 1–22; **NULL for all 2025 rows** |
| `game_type` | VARCHAR | REG/WC/DIV/CON/SB; NULL for 2025 |
| `status_description_abbr` | VARCHAR | Finer-grained code (A01 Active, I01 Injured, P01/P06/P07 practice-squad variants, R01 IR, R02 Retired, W03 Waived, …); 19.1% null post-2017 |
| `esb_id`,`gsis_it_id`,`smart_id` | VARCHAR/BIGINT | other NFL IDs |
| `entry_year`,`rookie_year` | BIGINT | |
| `draft_club`,`draft_number` | VARCHAR/BIGINT | null for undrafted |

### `status` values (distinct counts, verified)

| status | rows | meaning |
|---|---|---|
| ACT | 635,188 | Active (53-man roster) |
| RES | 75,259 | Reserve (mostly Injured Reserve; also other reserve lists — pairs with R01) |
| DEV | 59,598 | Practice squad (development; pairs with P01/P06/P07) |
| CUT | 48,532 | Cut/waived that week |
| INA | 20,273 | Inactive |
| TRC | 8,265 | Trade-related (commissioner/pending) |
| TRD | 6,924 | Traded |
| TRT | 1,967 | Trade-related |
| RET | 1,731 | Retired (pairs with R02) |
| RSN | 1,269 | Reserve/Non-football injury or illness |
| SUS | 998 | Suspended |
| PUP | 996 | Physically Unable to Perform |
| NWT | 977 | Not With Team |
| UFA | 180 | Unrestricted Free Agent |
| EXE | 178 | Exempt (commissioner's list) |
| RSR | 174 | Reserve/Retired |
| U01/E14/E01/A02/RFA/UDF | ≤152 ea | minor admin codes |
| NULL | 31 | |

Trade/CUT/RET rows mean the roster file still lists the player for that team-week in a non-active capacity — **filter `status='ACT'` (optionally + INA) when you want "on the game-day roster."**

---

## 3. `draft_picks` — drafts 1980–2025 (12,670 rows)

**Grain / PK:** `(season, round, pick)` — verified unique (12,670 = 12,670 distinct). Sourced from PFR.

**Second ID bridge:** carries both `gsis_id` and `pfr_player_id`, letting you link PFR draft/career data to GSIS players even when `players.pfr_id` is missing.

### `gsis_id` null % by era (verified, yearly query)

| era | gsis_id null % |
|---|---|
| 1980–1996 | 100% |
| 1997–2005 | 91–99% |
| 2006–2010 | 71–84% |
| 2011–2014 | 41–60% |
| 2015–2016 | 29–31% |
| 2017–2024 | **16–29%** (never 0 — picks who never signed/appeared lack GSIS IDs) |
| 2025 | **100%** (not yet assigned) |

Overall: `gsis_id` 77.5% null, `pfr_player_id` 13.8% null, `cfb_player_id` 30.8% null.

### Columns

| column | type | notes (observed) |
|---|---|---|
| `season` | BIGINT | Draft year, 1980–2025 |
| `round` | BIGINT | 1–12 (12-round drafts through 1993; 7 rounds modern) |
| `pick` | BIGINT | Overall pick, 1–336 |
| `team` | VARCHAR | **PFR team codes**: KAN, TAM, GNB, NOR, NWE, SFO, LVR, LAR… — do NOT join directly to `rosters_weekly.team` (GSIS codes) |
| `gsis_id` | VARCHAR | bridge to `players` (77.5% null overall, see era table) |
| `pfr_player_id` | VARCHAR | bridge to PFR / `players.pfr_id` |
| `cfb_player_id` | VARCHAR | Sports-Reference CFB ID |
| `pfr_player_name` | VARCHAR | name as on PFR |
| `hof` | BOOLEAN | Hall of Fame (95 true) |
| `position` | VARCHAR | PFR position |
| `category` | VARCHAR | coarse group: DB, OL, DL, LB, WR, RB, TE, QB, K, P, LS (+few stray OG/FS/KR) |
| `side` | VARCHAR | O 6,325 / D 6,085 / S 251 / null 9 |
| `college` | VARCHAR | |
| `age` | BIGINT | draft-year age, 20–29 |
| `to` | BIGINT | **Last season played** (1980–2024). NULL for 2,328 picks — exactly the picks with NULL `games`, i.e. never played a game (verified 1:1 correspondence) |
| `allpro` | BIGINT | Career AP first-team All-Pro selections, max 10 |
| `probowls` | BIGINT | Career Pro Bowls, max 15 |
| `seasons_started` | BIGINT | Seasons as primary starter |
| `w_av` | BIGINT | **Weighted career Approximate Value (PFR)** — the career-value column to use; max 184; 18.4% null (non-players) |
| `car_av` | VARCHAR | **DEAD COLUMN — 100% NULL. Use `w_av`.** (VARCHAR type is a load artifact) |
| `dr_av` | BIGINT | AV accrued with drafting team only |
| `games` | BIGINT | career games, max 382 |
| `pass_completions`…`pass_ints` | BIGINT | career passing totals |
| `rush_atts`,`rush_yards`,`rush_tds` | BIGINT | career rushing totals |
| `receptions`,`rec_yards`,`rec_tds` | BIGINT | career receiving totals |
| `def_solo_tackles`,`def_ints`,`def_sacks` | BIGINT/DOUBLE | career defense totals |

Career-total columns are snapshots through the 2024 season for active players (`to` max = 2024).

---

## Canonical query: which team did player X play for in week Y of season Z?

```sql
SELECT r.season, r.week, r.team, r.status
FROM rosters_weekly r
JOIN players p USING (gsis_id)
WHERE p.display_name = 'Amari Cooper'
  AND r.season = 2018 AND r.week = 9;
-- → 2018 | 9 | DAL | ACT   (tested)
```

Tested caveat: **transition weeks can be missing entirely.** Amari Cooper (traded OAK→DAL after week 7, 2018) has rows for weeks 1–6 (OAK) and 9–19 (DAL) — **no rows at all for weeks 7–8**. Handle "no row" as "in transit / not rostered," don't assume coverage. Also add `AND r.status = 'ACT'` if you require the active roster, and `QUALIFY row_number() OVER (PARTITION BY gsis_id, season, week ORDER BY status = 'ACT' DESC) = 1` to be safe against the 2002–2015 status-duplicates.

---

## Gotchas (all verified by query)

1. **2025 rosters are a preseason partial**: 3,239 rows (vs ~46k for a full season), and `week` and `game_type` are NULL on every 2025 row. Any week-filtered query silently drops 2025. Do not use for 2025 analysis until refreshed.
2. **(gsis_id, season, week) is not unique pre-2016**: 16,289 same-team status-duplicate keys in 2002–2015 (some rows fully identical). Dedupe or prefer `status='ACT'`.
3. **One corrupt gsis_id**: `00-0035718` in 2019 rosters is both Quinnen Williams (NYJ) and Isaiah Searight (NYG) — the only multi-team "duplicates" in the table (13 keys). Searight's 2019 NYG rows are mislabeled.
4. **Missing weeks around trades**: roster rows can be absent for weeks a player is between teams (Cooper 2018 wk 7–8).
5. **Team-code mismatch**: `draft_picks.team` uses PFR codes (KAN, TAM, GNB, SFO, LVR); `rosters_weekly.team`/`players.latest_team` use GSIS codes (KC, TB, GB, SF, LV). A crosswalk is needed to join them. `rosters_weekly` also keeps historical relocation codes (OAK vs LV, SD vs LAC, STL vs LA) as distinct values (39 distinct team codes).
6. **`draft_picks.car_av` is 100% NULL** (and typed VARCHAR). Use `w_av` (or `dr_av` for drafting-team value).
7. **`players.gsis_id` isn't always GSIS-format**: 6,391 historical players carry ESB-style IDs that will never match `rosters_weekly` (which is 100% `00-` format, only 160 nulls).
8. **Rosters start in 2002**; players/draft history extend back much further (1974 / 1980). Pre-2017 rosters lack `depth_chart_position` (92.6% null), `college` (64.1% null), and most external IDs (74–80% null).
9. **Bad biometrics in `players`**: `weight` has garbage lows (1, 16 lbs). Sanity-filter `weight BETWEEN 140 AND 400` for modeling.
10. **`players.headshot` is a URL template** containing a literal `{formatInstructions}` token, not a fetchable URL as-is.
11. **`draft_picks.gsis_id` is never fully populated even in modern drafts** (16–29% null 2017–2024; 100% null for 2025). Fall back to `pfr_player_id ↔ players.pfr_id` when bridging.

---

## Example queries (tested)

### 1. First-round QBs since 2010, by career weighted AV

```sql
SELECT season, pick, team, pfr_player_name, college, w_av, dr_av, "to", probowls
FROM draft_picks
WHERE round = 1 AND position = 'QB' AND season >= 2010
ORDER BY w_av DESC NULLS LAST;
```
Top results: Cam Newton (115), Patrick Mahomes (106), Lamar Jackson (101), Josh Allen (98), Jared Goff (96). Note `"to"` must be quoted (reserved word).

### 2. A player's team history (season × team stints)

```sql
SELECT r.season, r.team, count(*) AS weeks, min(r.week) AS first_wk, max(r.week) AS last_wk
FROM rosters_weekly r
JOIN players p USING (gsis_id)
WHERE p.display_name = 'Amari Cooper'
GROUP BY 1, 2
ORDER BY 1, first_wk;
```
Returns OAK 2015–2018(wk6) → DAL 2018(wk9)–2021 → CLE 2022–2024(wk6) → BUF 2024(wk7)–2025. The 2025 row has NULL weeks (preseason partial).

### 3. Roster snapshot: KC active roster + QBs, 2023 week 12

```sql
SELECT full_name, position, jersey_number, status
FROM rosters_weekly
WHERE team = 'KC' AND season = 2023 AND week = 12 AND status = 'ACT'
ORDER BY position, full_name;
```
48 active players; QB rows: Mahomes (ACT), Gabbert (ACT), Oladokun (DEV — excluded by the ACT filter, included if you drop it).
