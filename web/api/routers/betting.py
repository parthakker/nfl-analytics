"""Betting board: Vegas lines + Kalshi prices + situational angles per game.

Edges are MARKET-vs-MARKET only: |kalshi mid − devigged Vegas ML prob|,
flagged when the gap survives Kalshi's fee. The prediction model is not
involved (paused by design).
"""

import logging

from fastapi import APIRouter

from ..deps import current_schedule_season, read_conn, rows_to_dicts

log = logging.getLogger(__name__)

router = APIRouter()

FEE = 0.07  # kalshi fee factor: fee = 0.07 * P * (1-P)


def _ml_prob(ml) -> float | None:
    if ml is None:
        return None
    ml = float(ml)
    return 100.0 / (ml + 100.0) if ml > 0 else -ml / (-ml + 100.0)


@router.get("/api/betting/board")
def board(season: int | None = None, week: int | None = None) -> dict:
    if season is None:
        season = current_schedule_season()
    with read_conn(attach_kalshi=True) as con:
        if week is None:
            row = con.execute(
                "SELECT min(week) FROM schedules WHERE season=? AND result IS NULL", [season]
            ).fetchone()
            week = row[0] if row and row[0] is not None else 1

        games = rows_to_dicts(
            con,
            """
            SELECT s.game_id, strftime(s.gameday, '%a %b %d') AS date, s.gametime,
                   s.away_team, s.home_team, s.spread_line, s.total_line,
                   s.home_moneyline, s.away_moneyline,
                   s.home_rest, s.away_rest, s.div_game, s.referee,
                   s.roof, s.temp, s.wind
            FROM schedules s WHERE s.season = ? AND s.week = ?
            ORDER BY s.gameday, s.gametime
        """,
            [season, week],
        )

        # latest kalshi game-winner prices, mapped to games by teams+date
        kalshi = {}
        try:
            for r in rows_to_dicts(
                con,
                """
                WITH latest AS (
                    SELECT *, row_number() OVER (PARTITION BY ticker
                                                 ORDER BY snapshot_ts DESC) rn
                    FROM kalshi.kalshi_snapshots)
                SELECT d.away_team, d.home_team, d.event_date, d.yes_team,
                       l.implied_prob_mid AS prob, l.yes_bid, l.yes_ask,
                       l.volume, l.ticker
                FROM latest l JOIN kalshi.kalshi_markets_dim d USING (ticker)
                WHERE l.rn = 1 AND d.kind = 'game' AND l.status = 'active'
            """,
            ):
                kalshi[(r["away_team"], r["home_team"], r["yes_team"])] = r
        except Exception as e:
            # kalshi store may be briefly busy/absent — board still serves
            log.warning("betting/board s%s w%s: kalshi block failed: %s", season, week, e)

        # referee over-rate and coach ATS context
        refs = {
            r["name"]: r
            for r in rows_to_dicts(
                con,
                """
            SELECT any_value(name) AS name,
                   round(sum(over_rate*games)/sum(games), 3) AS over_rate,
                   round(sum(pen_per_game*games)/sum(games), 2) AS pen_per_game
            FROM v_referee_seasons GROUP BY ref_key
        """,
            )
        }
        coach_ats = {
            r["coach"]: r
            for r in rows_to_dicts(
                con,
                """
            SELECT coach, sum(ats_wins)::int AS w, sum(ats_games)::int AS g
            FROM v_coach_seasons GROUP BY coach
        """,
            )
        }
        coaches = {
            (r["home_team"]): r["home_coach"]
            for r in rows_to_dicts(
                con,
                "SELECT home_team, any_value(home_coach) AS home_coach FROM schedules WHERE season=? GROUP BY home_team",
                [season],
            )
        }

    out = []
    for g in games:
        ph, pa = _ml_prob(g["home_moneyline"]), _ml_prob(g["away_moneyline"])
        vegas_home = ph / (ph + pa) if ph and pa else None

        km = None
        for k, m in kalshi.items():
            if k[0] == g["away_team"] and k[1] == g["home_team"]:
                is_home_market = m["ticker"].endswith(f"-{g['home_team']}")
                km = {
                    "prob_home": m["prob"]
                    if is_home_market
                    else (1 - m["prob"] if m["prob"] is not None else None),
                    "ticker": m["ticker"],
                    "volume": m["volume"],
                    "spread_width": (
                        round(m["yes_ask"] - m["yes_bid"], 3)
                        if m["yes_ask"] is not None and m["yes_bid"] is not None
                        else None
                    ),
                }
                break

        dislocation = None
        if km and km["prob_home"] is not None and vegas_home is not None:
            gap = km["prob_home"] - vegas_home
            fee = FEE * km["prob_home"] * (1 - km["prob_home"])
            dislocation = {
                "gap": round(gap, 4),
                "fee": round(fee, 4),
                "actionable": abs(gap) > fee + (km["spread_width"] or 0.02) / 2,
                "cheaper_side": ("home on Kalshi" if gap < 0 else "away on Kalshi"),
            }

        ref = refs.get(g["referee"]) if g["referee"] else None
        hc = coaches.get(g["home_team"])
        out.append(
            {
                **g,
                "vegas_home_prob": round(vegas_home, 4) if vegas_home else None,
                "kalshi": km,
                "dislocation": dislocation,
                "angles": {
                    "rest_diff": (g["home_rest"] - g["away_rest"])
                    if g["home_rest"] is not None and g["away_rest"] is not None
                    else None,
                    "div_game": bool(g["div_game"]),
                    "referee": (
                        {"name": g["referee"], **{k: ref[k] for k in ("over_rate", "pen_per_game")}}
                        if ref
                        else None
                    ),
                    "home_coach_ats": (
                        {"coach": hc, "pct": round(coach_ats[hc]["w"] / coach_ats[hc]["g"], 3)}
                        if hc and coach_ats.get(hc, {}).get("g")
                        else None
                    ),
                    "roof": g["roof"],
                },
            }
        )
    return {"season": season, "week": week, "games": out}


@router.get("/api/betting/situations")
def situations(season: int | None = None) -> dict:
    """Canned situational screens over upcoming games."""
    if season is None:
        season = current_schedule_season()
    with read_conn() as con:
        rest = rows_to_dicts(
            con,
            """
            SELECT week, away_team || ' @ ' || home_team AS game,
                   home_rest, away_rest, home_rest - away_rest AS edge_days,
                   spread_line
            FROM schedules WHERE season=? AND result IS NULL
              AND abs(home_rest - away_rest) >= 3
            ORDER BY abs(home_rest - away_rest) DESC, week LIMIT 25
        """,
            [season],
        )
        travel = rows_to_dicts(
            con,
            """
            SELECT s.week, s.away_team || ' @ ' || s.home_team AS game,
                   ta.tz AS away_tz, th.tz AS home_tz,
                   ta.offset_behind_et - th.offset_behind_et AS hours_east,
                   s.spread_line
            FROM schedules s
            JOIN team_timezones ta ON ta.team = s.away_team
            JOIN team_timezones th ON th.team = s.home_team
            WHERE s.season = ? AND s.result IS NULL
              AND abs(ta.offset_behind_et - th.offset_behind_et) >= 2
            ORDER BY s.week LIMIT 40
        """,
            [season],
        )
        div_dogs = rows_to_dicts(
            con,
            """
            SELECT week, away_team || ' @ ' || home_team AS game, spread_line,
                   CASE WHEN spread_line > 0 THEN away_team ELSE home_team END AS underdog
            FROM schedules WHERE season=? AND result IS NULL AND div_game
              AND spread_line IS NOT NULL AND abs(spread_line) >= 3
            ORDER BY week LIMIT 40
        """,
            [season],
        )
    return {"rest_mismatches": rest, "long_travel": travel, "division_dogs": div_dogs}
