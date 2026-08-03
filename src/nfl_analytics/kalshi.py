"""Kalshi prediction-market client (read-only, unauthenticated) + snapshots.

Live series confirmed 2026-08-02: KXNFLGAME (winners), KXNFLSPREAD,
KXNFLTOTAL, KXNFLWINS (season win totals), KXSB (Super Bowl champion).
Prices are dollar strings ('0.6400'); orderbook returns BID arrays only
(yes_dollars / no_dollars) — the ask side is implied: yes_ask = 1 - best
no_bid. Fee estimate: Kalshi's standard 7% formula, 0.07 * P * (1-P).

Snapshots accumulate in kalshi.duckdb so line movement is queryable later.
"""

import re
from datetime import UTC, datetime

import duckdb
import httpx

from .config import KALSHI_API, KALSHI_DB

SERIES = {
    "game": "KXNFLGAME",
    "spread": "KXNFLSPREAD",
    "total": "KXNFLTOTAL",
    "win_totals": "KXNFLWINS",
    "superbowl": "KXSB",
}

TEAM_CODES = {  # canonical nflverse codes, for ticker parsing
    "ARI",
    "ATL",
    "BAL",
    "BUF",
    "CAR",
    "CHI",
    "CIN",
    "CLE",
    "DAL",
    "DEN",
    "DET",
    "GB",
    "HOU",
    "IND",
    "JAX",
    "KC",
    "LA",
    "LAC",
    "LV",
    "MIA",
    "MIN",
    "NE",
    "NO",
    "NYG",
    "NYJ",
    "PHI",
    "PIT",
    "SEA",
    "SF",
    "TB",
    "TEN",
    "WAS",
}

SCHEMA = """
    CREATE TABLE IF NOT EXISTS kalshi_snapshots (
        snapshot_ts TIMESTAMP, ticker VARCHAR, event_ticker VARCHAR,
        series_ticker VARCHAR, status VARCHAR,
        yes_bid DOUBLE, yes_ask DOUBLE, no_bid DOUBLE, no_ask DOUBLE,
        last_price DOUBLE, volume DOUBLE, open_interest DOUBLE,
        implied_prob_mid DOUBLE
    );
    CREATE TABLE IF NOT EXISTS kalshi_markets_dim (
        ticker VARCHAR PRIMARY KEY, event_ticker VARCHAR, series_ticker VARCHAR,
        kind VARCHAR, title VARCHAR, yes_team VARCHAR,
        away_team VARCHAR, home_team VARCHAR, event_date DATE
    );
"""


def _f(v) -> float | None:
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def client() -> httpx.Client:
    return httpx.Client(base_url=KALSHI_API, timeout=30)


def parse_event_ticker(event_ticker: str) -> dict:
    """'KXNFLGAME-26AUG15DALSEA' -> teams + date. Best-effort; None on miss."""
    m = re.search(r"-(\d{2})([A-Z]{3})(\d{2})([A-Z]+)$", event_ticker)
    if not m:
        return {"away_team": None, "home_team": None, "event_date": None}
    yy, mon, dd, teams = m.groups()
    try:
        date = datetime.strptime(f"20{yy}{mon}{dd}", "%Y%b%d").date()
    except ValueError:
        date = None
    for i in range(2, len(teams) - 1):
        a, h = teams[:i], teams[i:]
        if a in TEAM_CODES and h in TEAM_CODES:
            return {"away_team": a, "home_team": h, "event_date": date}
    return {"away_team": None, "home_team": None, "event_date": date}


def fetch_markets(kind: str = "game", status: str = "open", max_markets: int = 500) -> list[dict]:
    series = SERIES.get(kind)
    if not series:
        raise ValueError(f"kind must be one of {list(SERIES)}")
    out, cursor = [], None
    with client() as c:
        while len(out) < max_markets:
            params = {"series_ticker": series, "status": status, "limit": 200}
            if cursor:
                params["cursor"] = cursor
            js = c.get("/markets", params=params).json()
            batch = js.get("markets", [])
            out.extend(batch)
            cursor = js.get("cursor")
            if not cursor or not batch:
                break
    return out[:max_markets]


def market_row(m: dict) -> dict:
    yb, ya = _f(m.get("yes_bid_dollars")), _f(m.get("yes_ask_dollars"))
    mid = (yb + ya) / 2 if yb is not None and ya is not None else None
    return {
        "ticker": m["ticker"],
        "event_ticker": m.get("event_ticker", ""),
        "series_ticker": m.get("event_ticker", "").split("-")[0],
        "status": m.get("status", ""),
        "title": m.get("title", ""),
        "yes_team": m.get("yes_sub_title", ""),
        "yes_bid": yb,
        "yes_ask": ya,
        "no_bid": _f(m.get("no_bid_dollars")),
        "no_ask": _f(m.get("no_ask_dollars")),
        "last_price": _f(m.get("last_price_dollars")),
        "volume": _f(m.get("volume_fp")),
        "open_interest": _f(m.get("open_interest_fp")),
        "implied_prob_mid": mid,
        "fee_at_mid": round(0.07 * mid * (1 - mid), 4) if mid is not None else None,
        "spread_width": round(ya - yb, 4) if yb is not None and ya is not None else None,
    }


def orderbook_top(ticker: str) -> dict:
    with client() as c:
        js = c.get(f"/markets/{ticker}/orderbook").json()
    ob = js.get("orderbook_fp", {})

    def best(side):
        rows = ob.get(side) or []
        # bids sorted ascending by price; best bid is the highest price level
        return max(((_f(p), _f(q)) for p, q in rows), default=(None, None))

    yb, ybq = best("yes_dollars")
    nb, nbq = best("no_dollars")
    return {
        "yes_bid": yb,
        "yes_bid_qty": ybq,
        "no_bid": nb,
        "no_bid_qty": nbq,
        "yes_ask": round(1 - nb, 4) if nb is not None else None,
        "depth_levels_yes": len(ob.get("yes_dollars") or []),
        "depth_levels_no": len(ob.get("no_dollars") or []),
    }


def snapshot(kinds: list[str] | None = None) -> dict:
    """Snapshot all open markets for the given kinds into kalshi.duckdb."""
    kinds = kinds or list(SERIES)
    now = datetime.now(UTC)
    rows, dims = [], []
    for kind in kinds:
        for m in fetch_markets(kind):
            r = market_row(m)
            rows.append(
                [
                    now,
                    r["ticker"],
                    r["event_ticker"],
                    r["series_ticker"],
                    r["status"],
                    r["yes_bid"],
                    r["yes_ask"],
                    r["no_bid"],
                    r["no_ask"],
                    r["last_price"],
                    r["volume"],
                    r["open_interest"],
                    r["implied_prob_mid"],
                ]
            )
            p = parse_event_ticker(r["event_ticker"])
            dims.append(
                [
                    r["ticker"],
                    r["event_ticker"],
                    r["series_ticker"],
                    kind,
                    r["title"],
                    r["yes_team"],
                    p["away_team"],
                    p["home_team"],
                    p["event_date"],
                ]
            )
    con = duckdb.connect(str(KALSHI_DB))
    try:
        con.execute(SCHEMA)
        con.executemany("INSERT INTO kalshi_snapshots VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", rows)
        con.executemany(
            """
            INSERT OR REPLACE INTO kalshi_markets_dim VALUES (?,?,?,?,?,?,?,?,?)
        """,
            dims,
        )
        total = con.execute("SELECT count(*) FROM kalshi_snapshots").fetchone()[0]
    finally:
        con.close()
    return {
        "markets_snapshotted": len(rows),
        "snapshot_rows_total": total,
        "kinds": kinds,
        "at": now.isoformat(),
    }
