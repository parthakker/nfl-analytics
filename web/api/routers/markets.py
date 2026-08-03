from fastapi import APIRouter, HTTPException

from ..deps import read_conn, rows_to_dicts

router = APIRouter()

KINDS = ("game", "spread", "total", "win_totals", "superbowl")


@router.get("/api/markets")
def markets(kind: str = "game") -> dict:
    if kind not in KINDS:
        raise HTTPException(400, f"kind must be one of {KINDS}")
    with read_conn(attach_kalshi=True) as con:
        rows = rows_to_dicts(
            con,
            """
            WITH latest AS (
                SELECT *, row_number() OVER (PARTITION BY ticker
                                             ORDER BY snapshot_ts DESC) AS rn
                FROM kalshi.kalshi_snapshots
            ), prev24 AS (
                SELECT ticker, arg_max(implied_prob_mid, snapshot_ts) AS prob_24h
                FROM kalshi.kalshi_snapshots
                WHERE snapshot_ts < now() - INTERVAL 24 HOUR
                GROUP BY ticker
            )
            SELECT l.ticker, d.title, d.yes_team, d.away_team, d.home_team,
                   d.event_date, l.yes_bid, l.yes_ask, l.implied_prob_mid AS prob,
                   l.last_price, l.volume, l.open_interest,
                   round(l.implied_prob_mid - p.prob_24h, 4) AS delta_24h,
                   l.snapshot_ts AS as_of
            FROM latest l
            JOIN kalshi.kalshi_markets_dim d USING (ticker)
            LEFT JOIN prev24 p USING (ticker)
            WHERE l.rn = 1 AND d.kind = ? AND l.status = 'active'
            ORDER BY l.volume DESC NULLS LAST
        """,
            [kind],
        )
        sparks = {}
        for r in rows_to_dicts(
            con,
            """
            SELECT ticker, list(implied_prob_mid ORDER BY snapshot_ts) AS pts
            FROM (SELECT ticker, implied_prob_mid, snapshot_ts,
                         row_number() OVER (PARTITION BY ticker
                                            ORDER BY snapshot_ts DESC) AS rn
                  FROM kalshi.kalshi_snapshots)
            WHERE rn <= 28 GROUP BY ticker
        """,
        ):
            sparks[r["ticker"]] = r["pts"]
    for r in rows:
        r["spark"] = sparks.get(r["ticker"], [])
    return {"kind": kind, "markets": rows[:80]}


@router.get("/api/markets/{ticker}/history")
def history(ticker: str) -> dict:
    with read_conn(attach_kalshi=True) as con:
        title = con.execute(
            "SELECT title FROM kalshi.kalshi_markets_dim WHERE ticker = ?", [ticker]
        ).fetchone()
        points = rows_to_dicts(
            con,
            """
            SELECT snapshot_ts AS ts, implied_prob_mid AS prob, last_price,
                   volume, open_interest AS oi
            FROM kalshi.kalshi_snapshots WHERE ticker = ?
            ORDER BY snapshot_ts
        """,
            [ticker],
        )
    if not title:
        raise HTTPException(404, "unknown ticker")
    return {"ticker": ticker, "title": title[0], "points": points}
