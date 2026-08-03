# Data Completeness Audit

Generated 2026-08-02 21:11.

## Game coverage: schedule vs play-by-play

| Season | Scheduled (played) | In play_by_play | Missing | Plays/game min |
|---|---|---|---|---|
| 2007 | 267 | 267 | 0 | 139 |
| 2008 | 267 | 267 | 0 | 136 |
| 2009 | 267 | 267 | 0 | 144 |
| 2010 | 267 | 267 | 0 | 146 |
| 2011 | 267 | 267 | 0 | 149 |
| 2012 | 267 | 267 | 0 | 147 |
| 2013 | 267 | 267 | 0 | 144 |
| 2014 | 267 | 267 | 0 | 151 |
| 2015 | 267 | 267 | 0 | 145 |
| 2016 | 267 | 267 | 0 | 149 |
| 2017 | 267 | 267 | 0 | 146 |
| 2018 | 267 | 267 | 0 | 148 |
| 2019 | 267 | 267 | 0 | 142 |
| 2020 | 269 | 269 | 0 | 148 |
| 2021 | 285 | 285 | 0 | 142 |
| 2022 | 284 | 284 | 0 | 147 |
| 2023 | 285 | 285 | 0 | 139 |
| 2024 | 285 | 285 | 0 | 143 |
| 2025 | 285 | 285 | 0 | 135 |

## Play-by-play analytics columns — null % by era

| Column | 2007-2010 | 2011-2015 | 2016-2020 | 2021-2025 |
|---|---|---|---|---|
| epa | 1.2% | 1.1% | 1.1% | 1.2% |
| wp | 0.6% | 0.6% | 0.6% | 0.6% |
| cpoe | 62.7% | 61.5% | 61.7% | 63.3% |
| xpass | 24.1% | 24.0% | 23.9% | 23.8% |
| air_yards | 61.9% | 60.9% | 60.6% | 61.6% |
| success | 1.2% | 1.1% | 1.1% | 1.2% |
| temp | 27.0% | 26.8% | 27.8% | 42.2% |
| wind | 27.0% | 26.8% | 27.8% | 42.2% |
| drive | 1.2% | 1.2% | 1.1% | 1.1% |

## Table coverage by season

| Table | First | Last | Seasons | Rows | Empty/suspect seasons |
|---|---|---|---|---|---|
| player_stats_week | 2007 | 2024 | 18 | 95,757 | — |
| player_stats_week_v2 | 2025 | 2025 | 1 | 19,421 | — |
| team_stats | 2007 | 2025 | 19 | 608 | — |
| injuries | 2009 | 2025 | 17 | 90,752 | — |
| rosters_weekly | 2002 | 2026 | 25 | 909,308 | small: 2026 |
| advstats_week_pass | 2018 | 2025 | 8 | 5,424 | — |
| ngs_passing | 2016 | 2025 | 10 | 5,933 | — |
| officials | 2015 | 2025 | 11 | 21,900 | — |

## Verdict

**No unexpected gaps found** — every played game since 2007 has play-by-play, and no table has missing or suspiciously small seasons within its coverage window.

### Documented floors (not missing — never existed publicly)

| Source | Starts | Why |
|---|---|---|
| Play-by-play EPA/WP | 2007 (loaded) | nflverse pbp actually goes back to **1999** — loadable, see below |
| CPOE / xpass | 2006/2007+ | model-derived columns begin when tracking allows |
| Next Gen Stats | 2016 | NFL player-tracking chips introduced leaguewide |
| NGS rush-yards-over-expected | 2018 | model added later |
| PFR advanced stats | 2018 | PFR began charting these |
| Injuries | 2009 | league injury-report data availability |
| Officials | 2015 | source coverage |
| Moneylines in schedules | ~68% missing pre-2010 | historical odds archives are spotty |
| Weather (temp/wind) | outdoor games only | domes have no weather by definition |

### Fillable — published by nflverse but not yet loaded

| Dataset | Coverage | Value |
|---|---|---|
| **Play-by-play 1999–2006** | 8 more seasons | doubles the pre-2010 sample; Brady/Manning prime years |
| **Snap counts** | 2012+ | true usage % — better than games-played for fantasy |
| **Depth charts** | 2001+ | who actually starts; useful for news context |
| **Combine data** | 2000+ | athleticism profiles for draft analysis |
| **ESPN QBR** | 2006+ | alternative QB metric |

Say the word and any of these can be added to the bootstrap manifest.
