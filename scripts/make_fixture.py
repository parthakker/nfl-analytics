"""Build tiny committed fixture DBs for CI from the real local databases.

  python scripts/make_fixture.py     (or: nfl fixture)

Strategy (target: nfl_fixture.duckdb < 25 MB, hard-fail above):
  - FULL copy of small context tables (games, schedules, venues, officials...)
    so coach history, H2H series (1999+) and upcoming-game endpoints all work.
  - play_by_play sliced to the last 2 completed seasons AND only the columns
    build_views/tests reference (372 -> ~34 cols — the size make-or-break).
  - stats tables sliced to the seasons covering the v1/v2 seam.
  - all v_* views rebuilt inside the fixture via build_views itself.
  - tiny kalshi/news sidecars (latest snapshots, recent news + FTS).

Refresh cadence: manual, a few times a season. CI never needs the real DB.
"""

import importlib.util
import sys
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "tests" / "fixtures"
MAX_MB = 25

# every play_by_play column referenced by build_views VIEWS, the games
# derivation consumers, tests, or API pbp queries
PBP_COLS = [
    "game_id", "play_id", "season", "week", "season_type", "game_date",
    "home_team", "away_team", "posteam", "defteam", "play_type", "epa",
    "pass", "rush", "down", "qtr", "ydstogo", "yardline_100", "wp", "xpass",
    "shotgun", "no_huddle", "air_yards", "sack", "interception",
    "fumble_lost", "rushing_yards", "rusher_id", "receiver_id", "touchdown",
    "penalty", "penalty_yards", "penalty_team", "weather",
]

FULL_COPY = [
    "games", "schedules", "team_aliases", "officials",
    "weather_openmeteo",  # keyed by game_id, tiny
]

# season-sliced tables. Deliberately absent (no test/endpoint consumes them
# yet — add back when views/pages appear): snap_counts, depth_charts,
# participation, ftn_charting, espn_qbr_*, combine, draft_picks, advstats_season_*.
SLICED = [
    "team_stats", "player_stats_week", "player_stats_season",
    "player_stats_def_week", "player_stats_def_season",
    "player_stats_kicking_week", "player_stats_kicking_season",
    "player_stats_week_v2", "player_stats_season_v2",
    "injuries", "ngs_passing", "ngs_receiving",
    "ngs_rushing", "advstats_week_pass", "advstats_week_rush",
    "advstats_week_rec", "advstats_week_def",
]


def _load_build_views():
    spec = importlib.util.spec_from_file_location(
        "build_views", ROOT / "scripts" / "build_views.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def build_nfl_fixture(seasons: tuple[int, int]) -> Path:
    src = ROOT / "nfl.duckdb"
    dst = OUT_DIR / "nfl_fixture.duckdb"
    dst.unlink(missing_ok=True)
    con = duckdb.connect(str(dst))
    con.execute(f"ATTACH '{src.as_posix()}' AS live (READ_ONLY)")
    have = {r[0] for r in con.execute(
        "SELECT table_name FROM duckdb_tables() WHERE database_name = 'live'").fetchall()}

    for t in FULL_COPY:
        con.execute(f"CREATE TABLE {t} AS SELECT * FROM live.{t}")
    lo, hi = seasons
    # rosters/schedules-adjacent tables also need the upcoming season
    for t in SLICED:
        if t not in have:
            print(f"  (skip {t}: not in live db)")
            continue
        con.execute(f"""CREATE TABLE {t} AS SELECT * FROM live.{t}
                        WHERE season BETWEEN {lo} AND {hi + 1}""")
    # rosters: current + upcoming season only (roster endpoint + name tagging)
    con.execute(f"""CREATE TABLE rosters_weekly AS
                    SELECT * FROM live.rosters_weekly
                    WHERE season BETWEEN {hi} AND {hi + 1}""")
    # pbp: latest completed season only, view-referenced columns only
    con.execute(f"""
        CREATE TABLE play_by_play AS
        SELECT {', '.join(f'"{c}"' for c in PBP_COLS)}
        FROM live.play_by_play WHERE season = {hi}
    """)
    # players: only ids that appear somewhere in the sliced data
    con.execute("""
        CREATE TABLE players AS
        SELECT * FROM live.players WHERE gsis_id IN (
            SELECT player_id FROM player_stats_week
            UNION SELECT player_id FROM player_stats_week_v2
            UNION SELECT gsis_id FROM rosters_weekly)
    """)
    con.execute("DETACH live")
    con.close()

    # rebuild every view (and stadiums/venues/weather tables) IN the fixture
    bv = _load_build_views()
    bv.DB = dst
    rc = bv.build()
    if rc != 0:
        sys.exit("build_views failed against the fixture")
    return dst


def build_kalshi_fixture() -> Path:
    src = ROOT / "kalshi.duckdb"
    dst = OUT_DIR / "kalshi_fixture.duckdb"
    dst.unlink(missing_ok=True)
    con = duckdb.connect(str(dst))
    con.execute(f"ATTACH '{src.as_posix()}' AS live (READ_ONLY)")
    con.execute("""
        CREATE TABLE kalshi_snapshots AS
        SELECT * FROM (
            SELECT *, row_number() OVER (PARTITION BY ticker
                                         ORDER BY snapshot_ts DESC) rn
            FROM live.kalshi_snapshots) WHERE rn <= 2
    """)
    con.execute("ALTER TABLE kalshi_snapshots DROP COLUMN rn")
    con.execute("CREATE TABLE kalshi_markets_dim AS SELECT * FROM live.kalshi_markets_dim")
    con.execute("""
        CREATE TABLE line_snapshots AS
        SELECT * FROM live.line_snapshots
        WHERE snapshot_ts > (SELECT max(snapshot_ts) - INTERVAL 7 DAY
                             FROM live.line_snapshots)
    """)
    con.execute("DETACH live")
    con.close()
    return dst


def build_news_fixture() -> Path:
    src = ROOT / "news.duckdb"
    dst = OUT_DIR / "news_fixture.duckdb"
    dst.unlink(missing_ok=True)
    con = duckdb.connect(str(dst))
    con.execute(f"ATTACH '{src.as_posix()}' AS live (READ_ONLY)")
    con.execute("""
        CREATE TABLE news AS
        SELECT * FROM live.news ORDER BY published_ts DESC NULLS LAST LIMIT 800
    """)
    con.execute("DETACH live")
    # FTS index for /api/news/search
    sys.path.insert(0, str(ROOT / "src"))
    from nfl_analytics.news import rebuild_fts
    rebuild_fts(con)
    con.close()
    return dst


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    live = duckdb.connect(str(ROOT / "nfl.duckdb"), read_only=True)
    hi = live.execute("SELECT max(season) FROM play_by_play").fetchone()[0]
    live.close()
    seasons = (hi - 1, hi)
    print(f"Building fixtures (pbp seasons {seasons[0]}-{seasons[1]})...")

    paths = [build_nfl_fixture(seasons), build_kalshi_fixture(), build_news_fixture()]
    total_ok = True
    for p in paths:
        mb = p.stat().st_size / 1e6
        limit = MAX_MB if p.name.startswith("nfl") else 8
        flag = "OK" if mb <= limit else "TOO BIG"
        total_ok &= mb <= limit
        print(f"  {p.name:24s} {mb:6.1f} MB  [{flag}, limit {limit}]")
    if not total_ok:
        print("FAILED: fixture exceeds size budget — trim more columns/seasons")
        return 1
    print("Fixtures built. Verify with:")
    print('  $env:NFL_TEST_USE_FIXTURE="1"; python -m pytest -m "warehouse or api" -q')
    return 0


if __name__ == "__main__":
    sys.exit(main())
