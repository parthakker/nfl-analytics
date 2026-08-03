# schedules (nfldata games.csv)

Grain: one row per game, 1999–2026 (7,548 rows), **including unplayed upcoming
games** (scores null). Source: nflverse/nfldata `games.csv`, refreshed by
`scripts/refresh_data.py`.

Use this table for: upcoming games, betting lines (moneylines/spread/total),
rest days, QB/coach/referee/stadium per game. Use `games` (pbp-derived) for
roof/surface/temp/wind detail on played games 2007+. `game_id` joins them
1:1 (verified: spread_line corr = 1.0 on shared games).

Key columns: `game_id` (standard `2026_01_NE_SEA` format), `season`, `game_type`
(REG/WC/DIV/CON/SB — NOT the REG/POST convention), `week`, `gameday`, `weekday`,
`gametime`, `away_team`/`home_team` (canonical codes, verified), scores,
`home_rest`/`away_rest` (days), `spread_line` (positive = home favored, same
sign convention as `games`), `total_line`, `away_moneyline`/`home_moneyline`
(American odds), `div_game`, `roof`, `surface`, `temp`, `wind`,
`away_qb_name`/`home_qb_name`, `away_coach`/`home_coach`, `referee`, `stadium_id`.

Gotchas:
- Moneyline coverage: ~32% pre-2010, 100% 2010–2019, high-but-partial for
  unplayed 2026 games (lines post as the season nears).
- `game_type` uses WC/DIV/CON/SB for playoffs, unlike `season_type` REG/POST
  elsewhere; map with `game_type = 'REG'` vs `game_type <> 'REG'`.
- Weather columns here are forecasts/typicals for future games; prefer
  `games` for played-game weather.
