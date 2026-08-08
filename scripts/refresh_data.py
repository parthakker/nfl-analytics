"""Refresh data/ from nflverse and rebuild the warehouse.

Sources are nflverse-data GitHub release assets (updated nightly in-season)
plus nfldata's games.csv (schedules with odds, 1999-current, incl. upcoming).

Usage:
  python scripts/refresh_data.py            # weekly mode: current + last season assets + schedules
  python scripts/refresh_data.py --full     # everything in the manifest
  python scripts/refresh_data.py --no-rebuild   # download only

Each asset has a list of candidate names (nflverse has renamed assets before);
the first that downloads wins, and the log records which. A miss on every
candidate is a loud failure, not a skip.
"""

import argparse
import gzip
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
LOGS = ROOT / "logs"
RELEASE = "https://github.com/nflverse/nflverse-data/releases/download"
GAMES_URL = "https://github.com/nflverse/nfldata/raw/master/data/games.csv"

sys.path.insert(0, str(ROOT / "src"))

from nfl_analytics.db import _retry  # noqa: E402

# League year rolls at the new league year in March: Jan/Feb runs still belong
# to the season that started the previous fall.
_today = datetime.now()
CURRENT_SEASON = _today.year - (1 if _today.month < 3 else 0)
LAST_SEASON = CURRENT_SEASON - 1


# (release tag, [candidate asset names], dest relative to data/)
# 2025+ player stats live in the new unified-schema 'stats_player' release
# (145-col v2 format, offense+def+kicking merged) — loaded as *_v2 tables,
# never merged into the pre-2025 tables (renamed columns would misalign).
# Pre-2025 seasons use the original per-year assets (still published under
# the 'player_stats' tag) so --bootstrap can rebuild the full history.
# Coverage floors per source: pbp/team 2007, rosters 2002, injuries 2009,
# advstats 2018.
def manifest(season: int) -> list[tuple[str, list[str], str]]:
    y = str(season)
    out = []
    if season >= 1999:
        out.append(("pbp", [f"play_by_play_{y}.csv"], f"play_by_play/play_by_play_{y}.csv"))
    if season >= 2007:
        out.append(
            (
                "stats_team",
                [f"stats_team_regpost_{y}.csv"],
                f"team_stats/stats_team_regpost_{y}.csv",
            )
        )
    if 2007 <= season <= 2024:
        for stem in (
            "player_stats",
            "player_stats_season",
            "player_stats_def",
            "player_stats_def_season",
            "player_stats_kicking",
            "player_stats_kicking_season",
        ):
            out.append(("player_stats", [f"{stem}_{y}.csv"], f"player_stats/{stem}_{y}.csv"))
    if season >= 2025:
        for stem in (
            "stats_player_week",
            "stats_player_reg",
            "stats_player_post",
            "stats_player_regpost",
        ):
            out.append(("stats_player", [f"{stem}_{y}.csv"], f"player_stats_v2/{stem}_{y}.csv"))
    if season >= 2009:
        out.append(("injuries", [f"injuries_{y}.csv"], f"injuries/injuries_{y}.csv"))
    if season >= 2002:
        out.append(("weekly_rosters", [f"roster_weekly_{y}.csv"], f"rosters/roster_weekly_{y}.csv"))
    if season >= 2018:
        for kind in ("pass", "rush", "rec", "def"):
            out.append(
                (
                    "pfr_advstats",
                    [f"advstats_week_{kind}_{y}.csv"],
                    f"advanced_stats/advstats_week_{kind}_{y}.csv",
                )
            )
    if season >= 2012:
        out.append(("snap_counts", [f"snap_counts_{y}.csv"], f"snap_counts/snap_counts_{y}.csv"))
    if season >= 2001:
        out.append(
            ("depth_charts", [f"depth_charts_{y}.csv"], f"depth_charts/depth_charts_{y}.csv")
        )
    # NFL pulled the participation feed after 2023; 2024 asset exists but is
    # unofficial — capped here, verified at load
    if 2016 <= season <= 2024:
        out.append(
            (
                "pbp_participation",
                [f"pbp_participation_{y}.csv"],
                f"participation/pbp_participation_{y}.csv",
            )
        )
    if season >= 2022:
        out.append(
            ("ftn_charting", [f"ftn_charting_{y}.csv"], f"ftn_charting/ftn_charting_{y}.csv")
        )
    return out


# cumulative files: re-download whole file every refresh (they span all seasons)
# NGS is published gzip-only now; download() decompresses .gz -> .csv dest.
CUMULATIVE = [
    ("nextgen_stats", ["ngs_passing.csv.gz"], "next_gen_stats/ngs_passing.csv"),
    ("nextgen_stats", ["ngs_receiving.csv.gz"], "next_gen_stats/ngs_receiving.csv"),
    ("nextgen_stats", ["ngs_rushing.csv.gz"], "next_gen_stats/ngs_rushing.csv"),
    ("pfr_advstats", ["advstats_season_pass.csv"], "advanced_stats/advstats_season_pass.csv"),
    ("pfr_advstats", ["advstats_season_rush.csv"], "advanced_stats/advstats_season_rush.csv"),
    ("pfr_advstats", ["advstats_season_rec.csv"], "advanced_stats/advstats_season_rec.csv"),
    ("pfr_advstats", ["advstats_season_def.csv"], "advanced_stats/advstats_season_def.csv"),
    ("players", ["players.csv"], "player_info/players.csv"),
    ("officials", ["officials.csv"], "officals/officials.csv"),
    ("draft_picks", ["draft_picks.csv"], "draft_picks/draft_picks.csv"),
    ("combine", ["combine.csv"], "combine/combine.csv"),
    ("espn_data", ["qbr_week_level.csv"], "espn_qbr/qbr_week_level.csv"),
    ("espn_data", ["qbr_season_level.csv"], "espn_qbr/qbr_season_level.csv"),
]


def download(client: httpx.Client, url: str, dest: Path) -> bool:
    try:
        r = client.get(url)
        if r.status_code != 200 or len(r.content) < 50:
            return False
    except httpx.HTTPError:
        return False
    content = r.content
    if url.endswith(".gz") and not dest.name.endswith(".gz"):
        content = gzip.decompress(content)
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".tmp")
    tmp.write_bytes(content)
    tmp.replace(dest)  # atomic: never leave a half-written csv
    return True


def refresh(full: bool, rebuild: bool, bootstrap: bool = False) -> int:
    t0 = time.time()
    client = httpx.Client(follow_redirects=True, timeout=180)
    failures, fetched = [], []

    ok = download(client, GAMES_URL, DATA / "schedules" / "games.csv")
    (fetched if ok else failures).append("schedules/games.csv")

    seasons = list(range(1999, CURRENT_SEASON + 1)) if bootstrap else [LAST_SEASON, CURRENT_SEASON]
    items = [(t, c, d) for s in seasons for (t, c, d) in manifest(s)] + CUMULATIVE
    for tag, candidates, rel_dest in items:
        dest = DATA / rel_dest
        # bootstrap is resumable: files already on disk are not re-downloaded
        if bootstrap and dest.exists() and dest.stat().st_size > 1000:
            continue
        hit = None
        for name in candidates:
            if download(client, f"{RELEASE}/{tag}/{name}", dest):
                hit = name
                break
        if hit:
            fetched.append(f"{rel_dest}  (<- {hit})")
        else:
            # current-season assets legitimately don't exist before week 1;
            # anything else missing is a real failure
            season_of = rel_dest[-8:-4]
            if season_of.isdigit() and int(season_of) >= CURRENT_SEASON:
                fetched.append(f"{rel_dest}  (not yet published — pre-season, OK)")
            else:
                failures.append(f"{rel_dest}: no candidate matched {candidates} in tag {tag}")

    print(f"Downloaded {len(fetched)} assets in {time.time() - t0:.0f}s:")
    for f in fetched:
        print(f"  {f}")
    if failures:
        print("FAILURES:")
        for f in failures:
            print(f"  - {f}")

    rc = 0
    if rebuild and not failures:
        # weather: forecasts for upcoming games (+ archive gaps) into
        # data/weather/openmeteo.csv BEFORE the rebuild loads it. Non-fatal.
        w = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "fetch_weather.py")],
            capture_output=True,
            text=True,
        )
        print((w.stdout or "").strip()[-500:])
        if w.returncode != 0:
            print(f"fetch_weather failed (non-fatal): {(w.stderr or '').strip()[-300:]}")
        for script in ("build_warehouse.py", "build_views.py"):
            r = subprocess.run(
                [sys.executable, str(ROOT / "scripts" / script)], capture_output=True, text=True
            )
            print(r.stdout[-2000:])
            if r.returncode != 0:
                print(r.stderr[-2000:])
                failures.append(f"{script} exited {r.returncode}")
                break
    rc = 1 if failures else 0

    # append current Vegas lines to kalshi.duckdb so line MOVEMENT accumulates
    # (schedules only ever holds the latest numbers). A miss here is a silent
    # gap in line-movement history, so it is logged, never swallowed bare.
    line_snap = "skip"
    if rc == 0:
        try:
            import duckdb

            # the 6-hourly Kalshi snapshot job may hold the write lock — retry
            kdb = _retry(
                lambda: duckdb.connect(str(ROOT / "kalshi.duckdb")), "market history store"
            )
            try:
                kdb.execute("""
                    CREATE TABLE IF NOT EXISTS line_snapshots (
                        snapshot_ts TIMESTAMP, game_id VARCHAR, season INT, week INT,
                        spread_line DOUBLE, total_line DOUBLE,
                        home_moneyline INT, away_moneyline INT)
                """)
                kdb.execute(f"""
                    INSERT INTO line_snapshots
                    SELECT now(), game_id, season, week, spread_line, total_line,
                           home_moneyline, away_moneyline
                    FROM read_csv('{(DATA / "schedules" / "games.csv").as_posix()}')
                    WHERE result IS NULL AND spread_line IS NOT NULL
                """)
            finally:
                kdb.close()
            print("line_snapshots: appended current Vegas lines for upcoming games")
            line_snap = "ok"
        except Exception as e:
            line_snap = "fail"
            print(f"line snapshot FAILED: {e}")

    LOGS.mkdir(exist_ok=True)
    with open(LOGS / "refresh.log", "a", encoding="utf-8") as f:
        mode = "bootstrap" if bootstrap else ("full" if full else "weekly")
        f.write(
            f"{datetime.now().isoformat()} mode={mode} "
            f"fetched={len(fetched)} failures={len(failures)} line_snap={line_snap} rc={rc}\n"
        )
    return rc


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--full", action="store_true")
    p.add_argument("--no-rebuild", action="store_true")
    p.add_argument(
        "--bootstrap", action="store_true", help="download ALL seasons (fresh clone setup, ~2 GB)"
    )
    a = p.parse_args()
    sys.exit(refresh(a.full, not a.no_rebuild, bootstrap=a.bootstrap))
