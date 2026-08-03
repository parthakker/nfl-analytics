"""Game-time weather from Open-Meteo (free, keyless) into data/weather/openmeteo.csv.

The CSV lives under data/ so it survives full warehouse rebuilds (build_warehouse
loads it as the weather_openmeteo table). One row per game; forecast rows for a
game are overwritten on each run until the game is played, archive rows are
written once and never re-fetched (resumable backfill).

Usage:
  python scripts/fetch_weather.py               # forecasts for upcoming games (<16 days out)
  python scripts/fetch_weather.py --backfill    # archive obs for past outdoor games missing weather
  python scripts/fetch_weather.py --backfill --limit 500   # chunked backfill

Kickoff hour: nfldata gametime is US/Eastern; venue-local hour is derived with
the stadium's et_offset (stadiums.json). Open-Meteo is asked in the venue's IANA
timezone, and the hourly row nearest local kickoff wins.
"""

import argparse
import csv
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path

import duckdb
import httpx

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "nfl.duckdb"
OUT = ROOT / "data" / "weather" / "openmeteo.csv"

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
HOURLY = ("temperature_2m,apparent_temperature,relative_humidity_2m,"
          "wind_speed_10m,wind_gusts_10m,wind_direction_10m,"
          "precipitation,snowfall,cloud_cover,weather_code")

COLS = ["game_id", "venue_id", "kickoff_local", "fetched_at", "source",
        "temp_f", "feels_like_f", "humidity_pct", "wind_mph", "wind_gust_mph",
        "wind_dir_deg", "precip_in", "precip_prob_pct", "snowfall_in",
        "cloud_cover_pct", "weather_code"]


def load_existing() -> dict[str, dict]:
    if not OUT.exists():
        return {}
    with open(OUT, newline="", encoding="utf-8") as f:
        return {r["game_id"]: r for r in csv.DictReader(f)}


def save(rows: dict[str, dict]) -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    tmp = OUT.with_suffix(".csv.tmp")
    with open(tmp, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLS)
        w.writeheader()
        for gid in sorted(rows):
            w.writerow({c: rows[gid].get(c, "") for c in COLS})
    tmp.replace(OUT)


def kickoff_local(gameday: str, gametime: str | None, et_offset: float) -> datetime:
    """Venue-local kickoff from the ET gameday/gametime (13:00 default)."""
    t = str(gametime or "13:00")[:5]  # gametime is HH:MM, HH:MM:SS in old rows
    dt = datetime.fromisoformat(f"{gameday}T{t}:00")
    return dt - timedelta(hours=et_offset)  # et_offset = hours behind ET


def fetch_game(client: httpx.Client, url: str, g: dict, source: str) -> dict | None:
    ko = kickoff_local(g["gameday"], g["gametime"], g["venue_et_offset"])
    params = {
        "latitude": g["lat"], "longitude": g["lon"],
        "hourly": HOURLY + ("" if source == "archive" else ",precipitation_probability"),
        "temperature_unit": "fahrenheit", "wind_speed_unit": "mph",
        "precipitation_unit": "inch", "timezone": g["venue_tz"],
        "start_date": ko.date().isoformat(), "end_date": ko.date().isoformat(),
    }
    try:
        r = client.get(url, params=params)
        if r.status_code != 200:
            return None
        h = r.json().get("hourly") or {}
        times = h.get("time") or []
        if not times:
            return None
    except (httpx.HTTPError, ValueError):
        return None
    idx = min(range(len(times)),
              key=lambda i: abs(datetime.fromisoformat(times[i]) - ko))

    def pick(key):
        v = (h.get(key) or [None] * len(times))[idx]
        return "" if v is None else v

    return {
        "game_id": g["game_id"], "venue_id": g["venue_id"],
        "kickoff_local": ko.isoformat(), "fetched_at": datetime.now().isoformat(timespec="seconds"),
        "source": source,
        "temp_f": pick("temperature_2m"), "feels_like_f": pick("apparent_temperature"),
        "humidity_pct": pick("relative_humidity_2m"), "wind_mph": pick("wind_speed_10m"),
        "wind_gust_mph": pick("wind_gusts_10m"), "wind_dir_deg": pick("wind_direction_10m"),
        "precip_in": pick("precipitation"), "precip_prob_pct": pick("precipitation_probability"),
        "snowfall_in": pick("snowfall"), "cloud_cover_pct": pick("cloud_cover"),
        "weather_code": pick("weather_code"),
    }


def game_pool(backfill: bool) -> list[dict]:
    con = duckdb.connect(str(DB), read_only=True)
    try:
        have = {t[0] for t in con.execute("SHOW TABLES").fetchall()}
        if "game_venues" not in have:
            print("game_venues not built yet (run build_views.py first) — nothing to do")
            return []
        if backfill:
            # completed open-air games with no observed temp from pbp
            parsed = ("LEFT JOIN game_weather_parsed w ON w.game_id = s.game_id"
                      if "game_weather_parsed" in have else
                      "LEFT JOIN (SELECT NULL AS game_id, NULL AS temp_f) w ON w.game_id = s.game_id")
            sql = f"""
                SELECT s.game_id, s.gameday, s.gametime, gv.venue_id, gv.lat, gv.lon,
                       gv.venue_tz, gv.venue_et_offset
                FROM schedules s
                JOIN game_venues gv ON gv.game_id = s.game_id
                {parsed}
                WHERE s.result IS NOT NULL AND s.roof IN ('outdoors', 'open')
                  AND w.temp_f IS NULL AND coalesce(s.temp, NULL) IS NULL
                  AND gv.lat IS NOT NULL
                ORDER BY s.game_id
            """
        else:
            horizon = (date.today() + timedelta(days=15)).isoformat()
            sql = f"""
                SELECT s.game_id, s.gameday, s.gametime, gv.venue_id, gv.lat, gv.lon,
                       gv.venue_tz, gv.venue_et_offset
                FROM schedules s
                JOIN game_venues gv ON gv.game_id = s.game_id
                WHERE s.result IS NULL AND s.gameday >= current_date
                  AND s.gameday <= '{horizon}' AND gv.lat IS NOT NULL
                ORDER BY s.gameday
            """
        cols = ["game_id", "gameday", "gametime", "venue_id", "lat", "lon",
                "venue_tz", "venue_et_offset"]
        return [dict(zip(cols, r)) for r in con.execute(sql).fetchall()]
    finally:
        con.close()


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--backfill", action="store_true")
    p.add_argument("--limit", type=int, default=0, help="max API calls this run")
    a = p.parse_args()

    if not DB.exists():
        print("nfl.duckdb missing — nothing to do")
        return 0
    pool = game_pool(a.backfill)
    rows = load_existing()
    if a.backfill:  # resumable: skip games already fetched
        pool = [g for g in pool if g["game_id"] not in rows]
    if a.limit:
        pool = pool[:a.limit]
    if not pool:
        print("fetch_weather: nothing to fetch")
        return 0

    source = "archive" if a.backfill else "forecast"
    url = ARCHIVE_URL if a.backfill else FORECAST_URL
    client = httpx.Client(timeout=30)
    got = misses = 0
    for i, g in enumerate(pool):
        row = fetch_game(client, url, g, source)
        if row and row["temp_f"] != "":
            rows[g["game_id"]] = row
            got += 1
        else:
            misses += 1
        if (i + 1) % 100 == 0:
            save(rows)
            print(f"  ...{i + 1}/{len(pool)} ({got} ok)")
        time.sleep(0.2)
    save(rows)
    print(f"fetch_weather: {source} {got} fetched, {misses} misses, "
          f"{len(rows)} total rows in {OUT.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
