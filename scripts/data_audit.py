"""Historical data completeness audit -> docs/data_audit.md.

Separates three kinds of 'missing':
  1. GAPS  — data that should exist in-table but doesn't (bugs; fix these)
  2. FLOORS — sources that genuinely start later (documented, not fixable)
  3. FILLABLE — data nflverse publishes that we simply haven't loaded

Run:  python scripts/data_audit.py
"""

import sys
from datetime import datetime
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "data_audit.md"


def main() -> int:
    con = duckdb.connect(str(ROOT / "nfl.duckdb"), read_only=True)
    md = [f"# Data Completeness Audit\n\nGenerated {datetime.now():%Y-%m-%d %H:%M}.\n"]

    # 1. Game-level completeness: schedules (source of truth) vs pbp
    md.append("## Game coverage: schedule vs play-by-play\n")
    md.append("| Season | Scheduled (played) | In play_by_play | Missing | Plays/game min |")
    md.append("|---|---|---|---|---|")
    gaps = []
    rows = con.execute("""
        WITH sched AS (
            SELECT season, count(*) AS played
            FROM schedules WHERE result IS NOT NULL AND season >= 2007
            GROUP BY season),
        pbp AS (
            SELECT season, count(DISTINCT game_id) AS games,
                   min(plays) AS min_plays
            FROM (SELECT season, game_id, count(*) AS plays
                  FROM play_by_play GROUP BY season, game_id)
            GROUP BY season)
        SELECT s.season, s.played, coalesce(p.games, 0), coalesce(p.min_plays, 0)
        FROM sched s LEFT JOIN pbp p USING (season) ORDER BY s.season
    """).fetchall()
    for season, played, in_pbp, min_plays in rows:
        missing = played - in_pbp
        flag = " ⚠" if missing != 0 or min_plays < 120 else ""
        md.append(f"| {season} | {played} | {in_pbp} | {missing}{flag} | {min_plays} |")
        if missing != 0:
            gaps.append(f"pbp missing {missing} games in {season}")
        if 0 < min_plays < 120:
            gaps.append(f"{season} has a game with only {min_plays} plays (truncated?)")

    # which specific games are missing, if any
    missing_games = con.execute("""
        SELECT s.game_id FROM schedules s
        LEFT JOIN (SELECT DISTINCT game_id FROM play_by_play) p USING (game_id)
        WHERE s.result IS NOT NULL AND s.season >= 2007 AND p.game_id IS NULL
        ORDER BY s.game_id
    """).fetchall()
    if missing_games:
        md.append(f"\n**Missing game ids:** {', '.join(g[0] for g in missing_games[:40])}"
                  + (" …" if len(missing_games) > 40 else ""))

    # 2. Key analytics columns: null % by era in pbp
    md.append("\n## Play-by-play analytics columns — null % by era\n")
    md.append("| Column | 2007-2010 | 2011-2015 | 2016-2020 | 2021-2025 |")
    md.append("|---|---|---|---|---|")
    for col in ("epa", "wp", "cpoe", "xpass", "air_yards", "success",
                "temp", "wind", "drive"):
        vals = []
        for lo, hi in ((2007, 2010), (2011, 2015), (2016, 2020), (2021, 2025)):
            pct = con.execute(f"""
                SELECT round(100.0 * sum(CASE WHEN {col} IS NULL THEN 1 ELSE 0 END)
                       / count(*), 1)
                FROM play_by_play WHERE season BETWEEN {lo} AND {hi}
            """).fetchone()[0]
            vals.append(f"{pct}%")
        md.append(f"| {col} | " + " | ".join(vals) + " |")

    # 3. Per-table season row counts (compact)
    md.append("\n## Table coverage by season\n")
    tables = ["player_stats_week", "player_stats_week_v2", "team_stats",
              "injuries", "rosters_weekly", "advstats_week_pass",
              "ngs_passing", "officials"]
    md.append("| Table | First | Last | Seasons | Rows | Empty/suspect seasons |")
    md.append("|---|---|---|---|---|---|")
    for t in tables:
        lo, hi, n_seasons, n = con.execute(
            f"SELECT min(season), max(season), count(DISTINCT season), count(*) FROM {t}"
        ).fetchone()
        expected = set(range(int(lo), int(hi) + 1))
        have = {r[0] for r in con.execute(f"SELECT DISTINCT season FROM {t}").fetchall()}
        holes = sorted(expected - have)
        # suspiciously small seasons (under 40% of the median season size)
        sizes = con.execute(f"""
            SELECT season, count(*) FROM {t} GROUP BY season ORDER BY season
        """).fetchall()
        med = sorted(s[1] for s in sizes)[len(sizes) // 2] if sizes else 0
        small = [str(s) for s, c in sizes if med and c < 0.4 * med]
        note = (f"holes: {holes} " if holes else "") + (f"small: {','.join(small)}" if small else "")
        if holes:
            gaps.append(f"{t}: missing seasons {holes}")
        md.append(f"| {t} | {int(lo)} | {int(hi)} | {n_seasons} | {n:,} | {note or '—'} |")

    # 4. Verdict sections
    md.append("\n## Verdict\n")
    if gaps:
        md.append("### Real gaps (bugs to fix)\n")
        for g in gaps:
            md.append(f"- ⚠ {g}")
    else:
        md.append("**No unexpected gaps found** — every played game since 2007 has "
                  "play-by-play, and no table has missing or suspiciously small "
                  "seasons within its coverage window.")

    md.append("""
### Documented floors (not missing — never existed publicly)

| Source | Starts | Why |
|---|---|---|
| Play-by-play | 1999 (loaded 2026-08) | nflverse floor |
| Play-by-play EPA/WP | 1999; CPOE/xpass 2006/2007+ | model-derived columns begin when tracking allows |
| Next Gen Stats | 2016 | NFL player-tracking chips introduced leaguewide |
| NGS rush-yards-over-expected | 2018 | model added later |
| PFR advanced stats | 2018 | PFR began charting these |
| Snap counts | 2012 | PFR source floor |
| Participation (personnel/box) | 2016–2023 only | NFL discontinued the feed after 2023 |
| FTN charting | 2022 | FTN began charting |
| Injuries | 2009 | league injury-report data availability |
| Officials | 2015 (head refs 1999+ via schedules.referee) | source coverage |
| Moneylines in schedules | ~68% missing pre-2010 | historical odds archives are spotty |
| Weather (temp/wind) | outdoor games only | domes have no weather by definition |

### Fillable — published by nflverse but not yet loaded

All previously listed fillable datasets (pbp 1999–2006, snap counts, depth
charts, participation, FTN charting, combine, ESPN QBR) were loaded in the
2026-08 enrichment wave. Remaining candidates: nflverse `contracts`,
PFR season splits, `trades`.
""")

    OUT.write_text("\n".join(md), encoding="utf-8")
    print(f"Audit written to {OUT}")
    print(f"Real gaps found: {len(gaps)}")
    for g in gaps:
        print(f"  - {g}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
