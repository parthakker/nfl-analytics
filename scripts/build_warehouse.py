"""Build nfl.duckdb from the raw CSVs in data/.

Sources: nflverse bulk pull (2007-2024 core, varying coverage floors per source).
Deliberately skipped:
  - data/.MasterData/*  -- Power Query re-exports; AdvancedStats.csv and
    NextGenStats.csv stack heterogeneous schemas under one header (misaligned
    columns, double counting). The rest are byte-identical twins of folder files.
  - data/next_gen_stats/ngs_<year>_*.csv -- the 2024 files are truncated stubs
    (4-8 rows). The combined ngs_{passing,receiving,rushing}.csv cover
    2016-2024 completely, so only those are loaded.

Run:  python scripts/build_warehouse.py
"""

import sys
import time
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
DB = ROOT / "nfl.duckdb"

# table name -> csv glob (relative to data/)
TABLES = {
    # core
    "play_by_play": "play_by_play/play_by_play_*.csv",
    "team_stats": "team_stats/stats_team_regpost_*.csv",
    # player stats: six shapes, one table each
    "player_stats_week": "player_stats/player_stats_[0-9]*.csv",
    "player_stats_season": "player_stats/player_stats_season_*.csv",
    "player_stats_def_week": "player_stats/player_stats_def_[0-9]*.csv",
    "player_stats_def_season": "player_stats/player_stats_def_season_*.csv",
    "player_stats_kicking_week": "player_stats/player_stats_kicking_[0-9]*.csv",
    "player_stats_kicking_season": "player_stats/player_stats_kicking_season_*.csv",
    # 2025+ unified-schema player stats (nflverse v2 format; offense+def+kicking
    # in one file, renamed keys). Kept separate from pre-2025 tables — a compat
    # view in build_views.py unions them under the old column names.
    "player_stats_week_v2": "player_stats_v2/stats_player_week_*.csv",
    # [rp]* matches reg/post/regpost season files but not week; files carry season_type
    "player_stats_season_v2": "player_stats_v2/stats_player_[rp]*.csv",
    # PFR advanced stats (2018+, keyed on pfr_id -- bridge via players)
    "advstats_season_pass": "advanced_stats/advstats_season_pass.csv",
    "advstats_season_rush": "advanced_stats/advstats_season_rush.csv",
    "advstats_season_rec": "advanced_stats/advstats_season_rec.csv",
    "advstats_season_def": "advanced_stats/advstats_season_def.csv",
    "advstats_week_pass": "advanced_stats/advstats_week_pass_*.csv",
    "advstats_week_rush": "advanced_stats/advstats_week_rush_*.csv",
    "advstats_week_rec": "advanced_stats/advstats_week_rec_*.csv",
    "advstats_week_def": "advanced_stats/advstats_week_def_*.csv",
    # Next Gen Stats: combined files only (see module docstring)
    "ngs_passing": "next_gen_stats/ngs_passing.csv",
    "ngs_receiving": "next_gen_stats/ngs_receiving.csv",
    "ngs_rushing": "next_gen_stats/ngs_rushing.csv",
    # schedules incl. upcoming season, with odds (nfldata games.csv, 1999+)
    "schedules": "schedules/games.csv",
    # dimensions / misc
    "players": "player_info/players.csv",
    "rosters_weekly": "rosters/roster_weekly_*.csv",
    "injuries": "injuries/injuries_*.csv",
    "draft_picks": "draft_picks/draft_picks.csv",
    "officials": "officals/officials.csv",
    # usage / charting / context (enrichment wave 2026-08)
    "snap_counts": "snap_counts/snap_counts_*.csv",
    "depth_charts": "depth_charts/depth_charts_*.csv",
    "participation": "participation/pbp_participation_*.csv",
    "ftn_charting": "ftn_charting/ftn_charting_*.csv",
    "combine": "combine/combine.csv",
    "espn_qbr_week": "espn_qbr/qbr_week_level.csv",
    "espn_qbr_season": "espn_qbr/qbr_season_level.csv",
    # Open-Meteo backfill/forecast rows written by scripts/fetch_weather.py
    "weather_openmeteo": "weather/openmeteo.csv",
}

# Tables whose source may legitimately be absent (mid-bootstrap, fresh clone
# before the first fetch_weather run) — a missing glob is a skip, not a failure.
OPTIONAL_TABLES = {
    "snap_counts", "depth_charts", "participation", "ftn_charting",
    "combine", "espn_qbr_week", "espn_qbr_season", "weather_openmeteo",
}

# Team relocations/renames. Raw tables keep original abbreviations; join this
# to get one canonical abbreviation per franchise across eras.
TEAM_ALIASES = [
    ("SD", "LAC"), ("OAK", "LV"), ("STL", "LA"),
    ("JAC", "JAX"), ("LAR", "LA"),
]


def build() -> int:
    if DB.exists():
        DB.unlink()
    con = duckdb.connect(str(DB))
    failures = []

    for table, glob in TABLES.items():
        paths = sorted(DATA.glob(glob))
        if not paths:
            if table in OPTIONAL_TABLES:
                print(f"  {table:28s} skipped (no files yet: {glob})")
            else:
                failures.append(f"{table}: no files match {glob}")
            continue
        t0 = time.time()
        try:
            con.execute(f"""
                CREATE TABLE {table} AS
                SELECT * FROM read_csv(
                    '{(DATA / glob).as_posix()}',
                    union_by_name=true, sample_size=-1, header=true
                )
            """)
            n = con.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
            print(f"  {table:28s} {n:>9,} rows  ({len(paths)} files, {time.time()-t0:.1f}s)")
        except Exception as e:
            failures.append(f"{table}: {e}")

    con.execute("CREATE TABLE team_aliases (alias VARCHAR, canonical VARCHAR)")
    con.executemany("INSERT INTO team_aliases VALUES (?, ?)", TEAM_ALIASES)

    # games dimension distilled from play_by_play: one row per game with
    # context that situational queries need (coaches, rest, stadium, weather).
    con.execute("""
        CREATE TABLE games AS
        SELECT game_id, any_value(old_game_id) AS old_game_id,
               any_value(season) AS season, any_value(week) AS week,
               any_value(season_type) AS season_type,
               any_value(game_date) AS game_date,
               any_value(start_time) AS start_time,
               any_value(home_team) AS home_team, any_value(away_team) AS away_team,
               any_value(home_coach) AS home_coach, any_value(away_coach) AS away_coach,
               any_value(home_score) AS home_score, any_value(away_score) AS away_score,
               any_value(spread_line) AS spread_line, any_value(total_line) AS total_line,
               any_value(roof) AS roof, any_value(surface) AS surface,
               any_value(temp) AS temp, any_value(wind) AS wind,
               any_value(stadium) AS stadium, any_value(stadium_id) AS stadium_id,
               any_value(div_game) AS div_game
        FROM play_by_play
        GROUP BY game_id
    """)
    n = con.execute("SELECT count(*) FROM games").fetchone()[0]
    print(f"  {'games (derived)':28s} {n:>9,} rows")

    # validation: seasons present per yearly-file table
    print("\nSeason coverage:")
    for table in ["play_by_play", "player_stats_week", "team_stats", "injuries",
                  "rosters_weekly", "advstats_week_pass", "ngs_passing"]:
        try:
            lo, hi, n = con.execute(
                f"SELECT min(season), max(season), count(DISTINCT season) FROM {table}"
            ).fetchone()
            print(f"  {table:28s} {lo}-{hi} ({n} seasons)")
        except Exception as e:
            failures.append(f"coverage {table}: {e}")

    bad = con.execute("""
        SELECT season, count(*) FROM play_by_play
        GROUP BY season HAVING count(*) < 40000 ORDER BY season
    """).fetchall()
    if bad:
        failures.append(f"play_by_play seasons with suspiciously few rows: {bad}")

    con.close()
    print(f"\nWarehouse: {DB}  ({DB.stat().st_size / 1e9:.2f} GB)")
    if failures:
        print("\nFAILURES:")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("All tables loaded, validation passed.")
    return 0


if __name__ == "__main__":
    sys.exit(build())
