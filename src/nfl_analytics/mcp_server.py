"""NFL analytics MCP server (stdio).

Register:  claude mcp add nfl -- python -m nfl_analytics.mcp_server
All logging goes to stderr; stdout is the MCP protocol channel.
"""

import logging
import re
import subprocess
import sys

from mcp.server.mcpserver import MCPServer

from .config import LOGS_DIR, ROOT, SCHEDULED_TASKS
from .db import read_conn, table_result

logging.basicConfig(stream=sys.stderr, level=logging.INFO)
log = logging.getLogger("nfl-mcp")

server = MCPServer(
    name="nfl-analytics",
    instructions=(
        "Local NFL analytics warehouse (2007-2025 pbp, stats, schedules with "
        "odds through 2026), a baseline prediction model, and live market/"
        "fantasy tools. Start with describe_warehouse() for schema+gotchas. "
        "Cite seasons/filters when reporting results."
    ),
)

DICTIONARY_MAP = {
    "play_by_play": "play_by_play.md",
    "games": "play_by_play.md",
    "schedules": "schedules.md",
    "players": "player_dimensions.md",
    "rosters_weekly": "player_dimensions.md",
    "draft_picks": "player_dimensions.md",
    "team_stats": "context_tables.md",
    "injuries": "context_tables.md",
    "officials": "context_tables.md",
}
for _t in (
    "player_stats_week",
    "player_stats_season",
    "player_stats_def_week",
    "player_stats_def_season",
    "player_stats_kicking_week",
    "player_stats_kicking_season",
    "player_stats_week_v2",
    "player_stats_season_v2",
    "v_player_stats_week_all",
):
    DICTIONARY_MAP[_t] = "player_stats.md"
for _t in ("ngs_passing", "ngs_receiving", "ngs_rushing"):
    DICTIONARY_MAP[_t] = "next_gen_stats.md"
for _t in (
    "advstats_season_pass",
    "advstats_season_rush",
    "advstats_season_rec",
    "advstats_season_def",
    "advstats_week_pass",
    "advstats_week_rush",
    "advstats_week_rec",
    "advstats_week_def",
):
    DICTIONARY_MAP[_t] = "advanced_stats.md"


# ---------- Group A: warehouse ----------


@server.tool()
def query_warehouse(sql: str, max_rows: int = 200) -> dict:
    """Run a read-only SELECT against the NFL warehouse (DuckDB). Multiple
    statements are rejected. See describe_warehouse for tables and gotchas."""
    stripped = sql.strip().rstrip(";")
    if ";" in stripped:
        return {"error": "single statement only"}
    if not re.match(r"^\s*(select|with|describe|show)\b", stripped, re.I):
        return {"error": "read-only: statement must start with SELECT/WITH"}
    with read_conn(attach_kalshi=True) as con:
        try:
            return table_result(
                con, stripped, max_rows=max_rows, filters_applied="user SQL, as written"
            )
        except Exception as e:
            return {"error": str(e)}


@server.tool()
def describe_warehouse(table: str = "") -> dict:
    """List tables/views (no arg) or show one table's columns plus the
    relevant data-dictionary notes (gotchas, join keys, conventions)."""
    with read_conn() as con:
        if not table:
            t = table_result(
                con,
                """
                SELECT table_name, table_type,
                       (SELECT count(*) FROM information_schema.columns c
                        WHERE c.table_name = t.table_name) AS n_cols
                FROM information_schema.tables t ORDER BY table_name
            """,
                max_rows=100,
            )
            t["note"] = (
                "Pass a table name for columns + dictionary notes. "
                "Global gotchas live in CLAUDE.md; per-table detail "
                "in docs/dictionary/."
            )
            return t
        cols = table_result(
            con,
            """
            SELECT column_name, data_type FROM information_schema.columns
            WHERE table_name = ? ORDER BY ordinal_position
        """,
            [table],
            max_rows=400,
        )
    doc = DICTIONARY_MAP.get(table)
    notes = ""
    if doc:
        p = ROOT / "docs" / "dictionary" / doc
        if p.exists():
            notes = p.read_text(encoding="utf-8", errors="replace")[:6000]
    return {"table": table, **cols, "dictionary_notes": notes}


@server.tool()
def team_form(team: str, season: int, through_week: int = 0) -> dict:
    """Team record, EPA splits (season-to-date and last 5 games), rest/travel
    profile, and next scheduled game. through_week=0 means whole season."""
    wk = through_week or 30
    with read_conn() as con:
        rec = table_result(
            con,
            """
            SELECT count(*) AS games, sum(win) AS wins,
                   round(avg(points_for),1) AS ppg, round(avg(points_against),1) AS papg,
                   round(avg(rest_days),1) AS avg_rest
            FROM v_team_games
            WHERE team = canon_team(?) AND season = ? AND week <= ? AND season_type='REG'
        """,
            [team, season, wk],
            filters_applied=f"season={season}, REG, week<={wk}",
        )
        epa = table_result(
            con,
            """
            WITH tg AS (
              SELECT p.game_id, g.week,
                     avg(p.epa) FILTER (WHERE p.posteam = canon_team($t)) AS off_epa,
                     avg(p.epa) FILTER (WHERE p.defteam = canon_team($t)) AS def_epa
              FROM play_by_play p JOIN games g USING (game_id)
              WHERE p.season = $s AND g.week <= $w
                AND p.play_type IN ('pass','run')
                AND (p.posteam = canon_team($t) OR p.defteam = canon_team($t))
              GROUP BY 1, 2)
            SELECT round(avg(off_epa),4) AS off_epa,
                   round(avg(def_epa),4) AS def_epa,
                   round(avg(off_epa) FILTER (WHERE week > (SELECT max(week)-5 FROM tg)),4) AS off_epa_last5,
                   round(avg(def_epa) FILTER (WHERE week > (SELECT max(week)-5 FROM tg)),4) AS def_epa_last5
            FROM tg
        """,
            {"t": team, "s": season, "w": wk},
            filters_applied=f"season={season}, week<={wk}, pass/run plays",
        )
    return {"team": team, "season": season, "record": rec, "epa": epa}


@server.tool()
def player_lookup(name_or_id: str, season: int = 0) -> dict:
    """Find a player (name substring or gsis_id), return id bridge, bio,
    and recent season stat lines from the cross-era weekly view."""
    with read_conn() as con:
        ident = table_result(
            con,
            """
            SELECT gsis_id, display_name, position, latest_team, status,
                   rookie_season, last_season, pfr_id, espn_id, draft_year, draft_round
            FROM players
            WHERE gsis_id = ? OR display_name ILIKE '%' || ? || '%'
            ORDER BY (last_season IS NULL), last_season DESC LIMIT 5
        """,
            [name_or_id, name_or_id],
            max_rows=5,
        )
        if not ident["rows"]:
            return {"error": f"no player matching {name_or_id!r}"}
        gsis = ident["rows"][0][0]
        season_filter = f"AND season = {int(season)}" if season else ""
        stats = table_result(
            con,
            f"""
            SELECT season, season_type, count(*) AS games,
                   sum(passing_yards)::int AS pass_yds, sum(passing_tds)::int AS pass_td,
                   sum(carries)::int AS carries, sum(rushing_yards)::int AS rush_yds,
                   sum(targets)::int AS targets, sum(receptions)::int AS rec,
                   sum(receiving_yards)::int AS rec_yds,
                   round(sum(fantasy_points_ppr),1) AS ppr_pts,
                   round(avg(target_share),3) AS tgt_share
            FROM v_player_stats_week_all
            WHERE player_id = ? {season_filter}
            GROUP BY season, season_type ORDER BY season DESC, season_type LIMIT 12
        """,
            [gsis],
            filters_applied=f"gsis_id={gsis} {season_filter}",
        )
    return {"matches": ident, "stats": stats}


# ---------- Group B: model ----------


@server.tool()
def predict_game(home_team: str, away_team: str) -> dict:
    """Model prediction for a matchup: home win probability, predicted margin,
    feature inputs. Uses schedule rest days if the game is scheduled; attaches
    the market line when available. Early-season caveat applies (weeks 1-3)."""
    from .model.predict import predict_game as _pg

    with read_conn() as con:
        sched = con.execute(
            """
            SELECT game_id, season, week, home_rest, away_rest, div_game,
                   spread_line, home_moneyline, away_moneyline, gameday
            FROM schedules
            WHERE home_team = canon_team(?) AND away_team = canon_team(?)
              AND result IS NULL
            ORDER BY gameday LIMIT 1
        """,
            [home_team, away_team],
        ).fetchdf()
        kw = {}
        market = None
        if not sched.empty:
            import pandas as pd

            s = sched.iloc[0]
            if not pd.isna(s["home_rest"]) and not pd.isna(s["away_rest"]):
                kw["rest_diff"] = float(s["home_rest"]) - float(s["away_rest"])
            if not pd.isna(s["div_game"]):
                kw["div_game"] = int(s["div_game"])

            def _clean(v):
                if pd.isna(v):
                    return None
                if hasattr(v, "isoformat"):
                    return v.isoformat()
                if hasattr(v, "item"):  # numpy scalar -> python native
                    return v.item()
                return v

            market = {
                k: _clean(s[k])
                for k in ("game_id", "gameday", "spread_line", "home_moneyline", "away_moneyline")
            }
        try:
            out = _pg(con, home_team, away_team, **kw)
        except ValueError as e:
            return {"error": str(e)}
    out["market"] = market or "no scheduled game found between these teams"
    out["caveat"] = (
        "weeks 1-3 ratings lean on prior-season shrinkage; "
        "treat early-season predictions as low confidence"
    )
    return out


@server.tool()
def power_ratings(top: int = 32) -> dict:
    """Current model power ratings for all teams (EPA/play units; ratings
    entering the next game). net = mean(off) - mean(def); lower def is better."""
    with read_conn() as con:
        return table_result(
            con,
            """
            SELECT team,
                   round((r_off_pass + r_off_rush)/2 - (r_def_pass + r_def_rush)/2, 4) AS net,
                   round(r_off_pass, 4) AS off_pass, round(r_off_rush, 4) AS off_rush,
                   round(r_def_pass, 4) AS def_pass, round(r_def_rush, 4) AS def_rush,
                   rank() OVER (ORDER BY (r_off_pass + r_off_rush)/2
                                       - (r_def_pass + r_def_rush)/2 DESC) AS rank
            FROM model_ratings ORDER BY net DESC LIMIT ?
        """,
            [top],
            filters_applied="ratings entering next game, all data through last refresh",
        )


@server.tool()
def model_report() -> dict:
    """Backtest summary and the honest verdict from the last training run."""
    p = ROOT / "docs" / "model_report.md"
    if not p.exists():
        return {"error": "no model_report.md — run scripts/train_model.py"}
    with read_conn() as con:
        params = table_result(con, "SELECT * FROM model_params", max_rows=1)
    return {"report_markdown": p.read_text(encoding="utf-8"), "params": params}


# ---------- Group C: Kalshi markets (read-only tracker) ----------


@server.tool()
def kalshi_markets(kind: str = "game", team: str = "") -> dict:
    """Open Kalshi NFL markets. kind: game | spread | total | win_totals |
    superbowl. Optional team filter (canonical code, e.g. DET). Prices are
    probabilities in dollars (0.64 = 64c = 64% implied)."""
    from .kalshi import fetch_markets, market_row, parse_event_ticker

    try:
        ms = [market_row(m) for m in fetch_markets(kind)]
    except Exception as e:
        return {"error": f"kalshi api: {e}"}
    if team:
        t = team.upper()
        ms = [
            m
            for m in ms
            if t
            in (
                parse_event_ticker(m["event_ticker"]).get("away_team"),
                parse_event_ticker(m["event_ticker"]).get("home_team"),
            )
            or t in m["ticker"]
        ]
    cols = [
        "ticker",
        "title",
        "yes_team",
        "yes_bid",
        "yes_ask",
        "implied_prob_mid",
        "fee_at_mid",
        "volume",
        "open_interest",
    ]
    return {
        "columns": cols,
        "rows": [[m[c] for c in cols] for m in ms[:100]],
        "row_count": min(len(ms), 100),
        "truncated": len(ms) > 100,
        "filters_applied": f"kind={kind}, status=open" + (f", team={team}" if team else ""),
    }


@server.tool()
def kalshi_market_detail(ticker: str) -> dict:
    """One market's full picture: current prices, top-of-book depth, implied
    probability at bid/mid/ask, spread width, and estimated fee."""
    from .kalshi import client, market_row, orderbook_top

    try:
        with client() as c:
            js = c.get(f"/markets/{ticker}").json()
        if "market" not in js:
            return {"error": f"market {ticker!r} not found"}
        row = market_row(js["market"])
        row["orderbook_top"] = orderbook_top(ticker)
        return row
    except Exception as e:
        return {"error": f"kalshi api: {e}"}


@server.tool()
def kalshi_snapshot_now() -> dict:
    """Record a price snapshot of ALL open NFL markets into kalshi.duckdb
    (adds to line-movement history). Also runs on the 6h schedule."""
    from .kalshi import snapshot

    try:
        return snapshot()
    except Exception as e:
        return {"error": f"kalshi api: {e}"}


@server.tool()
def kalshi_price_history(ticker: str) -> dict:
    """Recorded price history for one market from accumulated snapshots."""
    with read_conn(attach_kalshi=True) as con:
        try:
            return table_result(
                con,
                """
                SELECT snapshot_ts, yes_bid, yes_ask, implied_prob_mid,
                       volume, open_interest
                FROM kalshi.kalshi_snapshots WHERE ticker = ?
                ORDER BY snapshot_ts
            """,
                [ticker],
                max_rows=500,
                filters_applied=f"ticker={ticker}, all recorded snapshots",
            )
        except Exception as e:
            return {"error": f"no snapshot store yet: {e} — run scripts/snapshot_kalshi.py"}


# ---------- Group G: coaches, referees, betting ----------


@server.tool()
def coach_profile(name: str) -> dict:
    """Head coach career: records, playoffs, ATS, 4th-down aggressiveness,
    pass-rate-over-expected, scheme identity (curated), rivalry records."""
    with read_conn() as con:
        seasons = table_result(
            con,
            """
            SELECT s.season, s.team, s.reg_wins, s.reg_games - s.reg_wins AS reg_losses,
                   s.post_wins, s.post_games - s.post_wins AS post_losses,
                   s.ats_wins, s.ats_games, t.proe,
                   round(t.go_attempts::double / nullif(t.go_situations,0), 3) AS go_rate
            FROM v_coach_seasons s
            LEFT JOIN v_coach_tendencies t ON t.coach = s.coach AND t.season = s.season
            WHERE s.coach ILIKE '%' || ? || '%' ORDER BY s.season
        """,
            [name],
            filters_applied=f"coach~{name}, 2007+",
        )
        rivals = table_result(
            con,
            """
            SELECT opp_coach, games, wins FROM v_coach_matchups
            WHERE coach ILIKE '%' || ? || '%' AND games >= 3
            ORDER BY games DESC LIMIT 10
        """,
            [name],
            max_rows=10,
        )
    return {
        "seasons": seasons,
        "rivals": rivals,
        "note": "scheme metadata in data/coaches_meta.json",
    }


@server.tool()
def referee_stats(name: str = "") -> dict:
    """Head referee tendencies 2015+: penalties/game, home penalty bias,
    over rate, home win/cover rates. Empty name = all refs ranked."""
    with read_conn() as con:
        if name:
            return table_result(
                con,
                """
                SELECT * FROM v_referee_seasons
                WHERE name ILIKE '%' || ? || '%' ORDER BY season
            """,
                [name],
                filters_applied=f"ref~{name}",
            )
        return table_result(
            con,
            """
            SELECT any_value(name) AS name, sum(games)::int AS games,
                   round(sum(pen_per_game*games)/sum(games), 2) AS pen_per_game,
                   round(sum(over_rate*games)/sum(games), 3) AS over_rate,
                   round(sum(home_cover_rate*games)/sum(games), 3) AS home_cover_rate
            FROM v_referee_seasons GROUP BY official_id
            HAVING sum(games) >= 30 ORDER BY pen_per_game DESC
        """,
            filters_applied="career, min 30 games, 2015+",
        )


@server.tool()
def betting_board(week: int = 0) -> dict:
    """Upcoming games: Vegas lines vs live Kalshi prices with dislocation
    flags (market-vs-market, fee-adjusted) and situational angles."""
    from web.api.routers.betting import board

    return board(2026, week or None)


# ---------- Group F: news ----------


@server.tool()
def news_search(query: str, limit: int = 15) -> dict:
    """Full-text search over ALL stored news (ESPN, team sites, PFT, Yahoo)
    ranked by relevance. e.g. 'Gibbs hamstring', 'coaching change Arizona'."""
    from .news import search as fts

    try:
        items = fts(query, min(limit, 30))
        return {
            "query": query,
            "items": [
                {
                    k: (str(v) if hasattr(v, "isoformat") else v)
                    for k, v in it.items()
                    if k != "body"
                }
                for it in items
            ],
        }
    except Exception as e:
        return {"error": f"search unavailable: {e} — run scripts/poll_news.py first"}


@server.tool()
def player_news(name_or_id: str, days: int = 7) -> dict:
    """Recent news and injury-report entries for a player (name or gsis_id),
    from the polled ESPN feeds in news.duckdb."""
    with read_conn(attach_news=True) as con:
        row = con.execute(
            """
            SELECT gsis_id, display_name FROM players
            WHERE gsis_id = ? OR display_name ILIKE '%' || ? || '%'
            ORDER BY (last_season IS NULL), last_season DESC LIMIT 1
        """,
            [name_or_id, name_or_id],
        ).fetchone()
        if not row:
            return {"error": f"no player matching {name_or_id!r}"}
        gsis, name = row
        try:
            items = table_result(
                con,
                """
                SELECT source, published_ts, headline, body, url
                FROM newsdb.news
                WHERE list_contains(players, ?)
                  AND published_ts > now() - (? * INTERVAL 1 DAY)
                ORDER BY published_ts DESC LIMIT 25
            """,
                [gsis, days],
                filters_applied=f"player={name}, last {days} days",
            )
        except Exception as e:
            return {"error": f"news store unavailable: {e} — run scripts/poll_news.py"}
    return {"player": name, "gsis_id": gsis, **items}


@server.tool()
def league_news(team: str = "", days: int = 2) -> dict:
    """Latest league headlines (optionally filtered to one team) from the
    polled ESPN news feed."""
    with read_conn(attach_news=True) as con:
        try:
            if team:
                return table_result(
                    con,
                    """
                    SELECT published_ts, headline, body, url FROM newsdb.news
                    WHERE source = 'espn_news'
                      AND list_contains(teams, canon_team(?))
                      AND published_ts > now() - (? * INTERVAL 1 DAY)
                    ORDER BY published_ts DESC LIMIT 25
                """,
                    [team, days],
                    filters_applied=f"team={team}, last {days} days",
                )
            return table_result(
                con,
                """
                SELECT published_ts, headline, body, url FROM newsdb.news
                WHERE source = 'espn_news'
                  AND published_ts > now() - (? * INTERVAL 1 DAY)
                ORDER BY published_ts DESC LIMIT 25
            """,
                [days],
                filters_applied=f"all teams, last {days} days",
            )
        except Exception as e:
            return {"error": f"news store unavailable: {e} — run scripts/poll_news.py"}


# ---------- Group E: refresh/meta ----------


@server.tool()
def data_status() -> dict:
    """Coverage and staleness: latest season/week per core table, last
    refresh-log lines, and whether a refresh looks needed."""
    with read_conn(attach_kalshi=True) as con:
        cov = table_result(
            con,
            """
            SELECT 'play_by_play' AS tbl, max(season) AS max_season,
                   max(week) FILTER (WHERE season = (SELECT max(season) FROM play_by_play)) AS max_week,
                   count(*) AS rows FROM play_by_play
            UNION ALL SELECT 'schedules', max(season), NULL, count(*) FROM schedules
            UNION ALL SELECT 'player_stats_week_v2', max(season), NULL, count(*) FROM player_stats_week_v2
            UNION ALL SELECT 'injuries', max(season), NULL, count(*) FROM injuries
            UNION ALL SELECT 'rosters_weekly', max(season), NULL, count(*) FROM rosters_weekly
        """,
            max_rows=20,
        )
        try:
            snaps = con.execute(
                "SELECT count(*), max(snapshot_ts) FROM kalshi.kalshi_snapshots"
            ).fetchone()
        except Exception:
            snaps = (0, None)
    tails = {}
    for name in ("refresh", "news", "kalshi", "smoke", "health", "jarvis"):
        lf = LOGS_DIR / f"{name}.log"
        tails[name] = (
            "\n".join(lf.read_text(encoding="utf-8").splitlines()[-3:])
            if lf.exists()
            else "never run"
        )
    return {
        "coverage": cov,
        "kalshi_snapshots": {"count": snaps[0], "latest": str(snaps[1]) if snaps[1] else None},
        "scheduled_jobs": SCHEDULED_TASKS,
        "log_tails": tails,
    }


@server.tool()
def refresh_data(full: bool = False) -> dict:
    """Download latest nflverse data and rebuild the warehouse (~1-2 min).
    Runs as a subprocess so the server holds no DB handle during rebuild."""
    cmd = [sys.executable, str(ROOT / "scripts" / "refresh_data.py")]
    if full:
        cmd.append("--full")
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
    return {
        "exit_code": r.returncode,
        "output_tail": r.stdout[-3000:],
        "errors": r.stderr[-1000:] if r.returncode else "",
    }


def main() -> None:
    server.run("stdio")


if __name__ == "__main__":
    main()
