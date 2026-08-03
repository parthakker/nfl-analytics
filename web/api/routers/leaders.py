"""Stat leaders: family-based wide-row leaderboards.

One request returns the family's full column set (PFR/ESPN style) — `sort`
picks the ranking column, `qual` applies the family's qualification
denominator, and the response carries the qualified-set league average plus
p10/p90 for rate columns (percentile tinting in the UI).

Grain fix (2026-08): rows GROUP BY player_id, never display name — two
different Adrian Petersons in 2007 must be two rows. Games are activity-
filtered count(DISTINCT week) so the v2 era (which lists every rostered
player) doesn't dilute per-game numbers.
"""

from fastapi import APIRouter, HTTPException

from ..deps import read_conn, rows_to_dicts

router = APIRouter()

# column spec: key -> (SQL aggregate over the family view v [+ players p], label, kind)
# kind: count (per-game toggle applies) | rate | pct (immune to the toggle)
OFF_GAMES = """count(DISTINCT v.week) FILTER (
    WHERE coalesce(v.attempts,0) + coalesce(v.carries,0) + coalesce(v.targets,0) > 0)"""

FAMILIES: dict[str, dict] = {
    "passing": {
        "view": "v_player_stats_week_all",
        "games": OFF_GAMES,
        "default_sort": "pass_yds",
        "qual": "att",
        "positions": ["QB", "RB", "WR", "TE"],
        "cols": {
            "cmp": ("sum(v.completions)::int", "Cmp", "count"),
            "att": ("sum(v.attempts)::int", "Att", "count"),
            "cmp_pct": (
                "round(100.0*sum(v.completions)/nullif(sum(v.attempts),0),1)",
                "Cmp%",
                "pct",
            ),
            "pass_yds": ("sum(v.passing_yards)::int", "Yds", "count"),
            "pass_ypg": ("round(sum(v.passing_yards)/nullif(games,0),1)", "Y/G", "rate"),
            "ypa": ("round(sum(v.passing_yards)/nullif(sum(v.attempts),0),1)", "Y/A", "rate"),
            "pass_td": ("sum(v.passing_tds)::int", "TD", "count"),
            "ints": ("sum(v.interceptions)::int", "Int", "count"),
            "sacks": ("sum(v.sacks)::int", "Sk", "count"),
            "air_yds": ("sum(v.passing_air_yards)::int", "AirYds", "count"),
            "epa_db": (
                "round(sum(v.passing_epa)/nullif(sum(v.attempts)+sum(v.sacks),0),3)",
                "EPA/db",
                "rate",
            ),
            "pacr": (
                "round(sum(v.passing_yards)/nullif(sum(v.passing_air_yards),0),2)",
                "PACR",
                "rate",
            ),
            "rush_yds": ("sum(v.rushing_yards)::int", "RushYds", "count"),
            "rush_td": ("sum(v.rushing_tds)::int", "RushTD", "count"),
        },
    },
    "rushing": {
        "view": "v_player_stats_week_all",
        "games": OFF_GAMES,
        "default_sort": "rush_yds",
        "qual": "att",
        "positions": ["QB", "RB", "WR", "TE", "FB"],
        "cols": {
            "att": ("sum(v.carries)::int", "Att", "count"),
            "rush_yds": ("sum(v.rushing_yards)::int", "Yds", "count"),
            "rush_ypg": ("round(sum(v.rushing_yards)/nullif(games,0),1)", "Y/G", "rate"),
            "ypc": ("round(sum(v.rushing_yards)/nullif(sum(v.carries),0),1)", "Y/C", "rate"),
            "rush_td": ("sum(v.rushing_tds)::int", "TD", "count"),
            "fum_lost": ("sum(v.rushing_fumbles_lost)::int", "FumL", "count"),
            "first_downs": ("sum(v.rushing_first_downs)::int", "1D", "count"),
            "epa_rush": ("round(sum(v.rushing_epa)/nullif(sum(v.carries),0),3)", "EPA/att", "rate"),
            "rec": ("sum(v.receptions)::int", "Rec", "count"),
            "rec_yds": ("sum(v.receiving_yards)::int", "RecYds", "count"),
            "ppr": ("round(sum(v.fantasy_points_ppr),1)", "PPR", "count"),
        },
    },
    "receiving": {
        "view": "v_player_stats_week_all",
        "games": OFF_GAMES,
        "default_sort": "rec_yds",
        "qual": "tgt",
        "positions": ["RB", "WR", "TE", "FB"],
        "cols": {
            "tgt": ("sum(v.targets)::int", "Tgt", "count"),
            "rec": ("sum(v.receptions)::int", "Rec", "count"),
            "catch_pct": (
                "round(100.0*sum(v.receptions)/nullif(sum(v.targets),0),1)",
                "Catch%",
                "pct",
            ),
            "rec_yds": ("sum(v.receiving_yards)::int", "Yds", "count"),
            "rec_ypg": ("round(sum(v.receiving_yards)/nullif(games,0),1)", "Y/G", "rate"),
            "ypr": ("round(sum(v.receiving_yards)/nullif(sum(v.receptions),0),1)", "Y/R", "rate"),
            "rec_td": ("sum(v.receiving_tds)::int", "TD", "count"),
            "air_yds": ("sum(v.receiving_air_yards)::int", "AirYds", "count"),
            "yac": ("sum(v.receiving_yards_after_catch)::int", "YAC", "count"),
            "first_downs": ("sum(v.receiving_first_downs)::int", "1D", "count"),
            "epa_tgt": (
                "round(sum(v.receiving_epa)/nullif(sum(v.targets),0),3)",
                "EPA/tgt",
                "rate",
            ),
            "tgt_share": ("round(avg(v.target_share),3)", "Tgt%", "rate"),
            "wopr": ("round(avg(v.wopr),3)", "WOPR", "rate"),
        },
    },
    "fantasy": {
        "view": "v_player_stats_week_all",
        "games": OFF_GAMES,
        "default_sort": "ppr",
        "qual": "games",
        "positions": ["QB", "RB", "WR", "TE"],
        "cols": {
            "std": ("round(sum(v.fantasy_points),1)", "Std", "count"),
            "half_ppr": ("round(sum(v.fantasy_points_half_ppr),1)", "Half", "count"),
            "ppr": ("round(sum(v.fantasy_points_ppr),1)", "PPR", "count"),
            "std_pg": ("round(sum(v.fantasy_points)/nullif(games,0),1)", "Std/G", "rate"),
            "half_pg": (
                "round(sum(v.fantasy_points_half_ppr)/nullif(games,0),1)",
                "Half/G",
                "rate",
            ),
            "ppr_pg": ("round(sum(v.fantasy_points_ppr)/nullif(games,0),1)", "PPR/G", "rate"),
            "att": ("sum(v.carries)::int", "RushAtt", "count"),
            "tgt": ("sum(v.targets)::int", "Tgt", "count"),
            "rec": ("sum(v.receptions)::int", "Rec", "count"),
            "touches": ("(sum(v.carries)+sum(v.receptions))::int", "Touches", "count"),
            "rush_yds": ("sum(v.rushing_yards)::int", "RushYds", "count"),
            "rec_yds": ("sum(v.receiving_yards)::int", "RecYds", "count"),
            "total_td": (
                "(sum(v.rushing_tds)+sum(v.receiving_tds)+sum(v.passing_tds))::int",
                "TD",
                "count",
            ),
        },
    },
    "defense": {
        "view": "v_player_stats_def_week_all",
        "games": "count(DISTINCT v.week)",
        "default_sort": "tackles",
        "qual": "games",
        "positions": ["DL", "LB", "DB"],
        "cols": {
            "tackles": ("sum(v.def_tackles)::int", "Comb", "count"),
            "solo": ("sum(v.def_tackles_solo)::int", "Solo", "count"),
            "ast": ("sum(v.def_tackle_assists)::int", "Ast", "count"),
            "tfl": ("sum(v.def_tackles_for_loss)::int", "TFL", "count"),
            "sacks": ("round(sum(v.def_sacks),1)", "Sk", "count"),
            "qb_hits": ("sum(v.def_qb_hits)::int", "QBHit", "count"),
            "ints": ("sum(v.def_interceptions)::int", "Int", "count"),
            "pd": ("sum(v.def_pass_defended)::int", "PD", "count"),
            "ff": ("sum(v.def_fumbles_forced)::int", "FF", "count"),
            "fr": ("sum(v.fumble_recovery_opp)::int", "FR", "count"),
            "def_td": ("sum(v.def_tds)::int", "TD", "count"),
            "safeties": ("sum(v.def_safeties)::int", "Sfty", "count"),
            "tkl_pg": ("round(sum(v.def_tackles)/nullif(games,0),1)", "Tkl/G", "rate"),
        },
    },
    "kicking": {
        "view": "v_player_stats_kicking_week_all",
        "games": "count(DISTINCT v.week)",
        "default_sort": "points",
        "qual": "fg_att",
        "positions": ["SPEC"],
        "cols": {
            "fg_made": ("sum(v.fg_made)::int", "FGM", "count"),
            "fg_att": ("sum(v.fg_att)::int", "FGA", "count"),
            "fg_pct": ("round(100.0*sum(v.fg_made)/nullif(sum(v.fg_att),0),1)", "FG%", "pct"),
            "fg_long": ("max(v.fg_long)::int", "Lng", "rate"),
            "fg_40_49": ("sum(v.fg_made_40_49)::int", "40-49", "count"),
            "fg_50_plus": ("(sum(v.fg_made_50_59)+sum(v.fg_made_60_))::int", "50+", "count"),
            "pat_made": ("sum(v.pat_made)::int", "XPM", "count"),
            "pat_att": ("sum(v.pat_att)::int", "XPA", "count"),
            "points": ("(3*sum(v.fg_made)+sum(v.pat_made))::int", "Pts", "count"),
            "pts_pg": (
                "round((3*sum(v.fg_made)+sum(v.pat_made))/nullif(games,0),1)",
                "Pts/G",
                "rate",
            ),
        },
    },
}

LABELS = {
    "passing": "Passing",
    "rushing": "Rushing",
    "receiving": "Receiving",
    "fantasy": "Fantasy",
    "defense": "Defense",
    "kicking": "Kicking",
}
LIMITS = (25, 50, 100)


def _base_sql(fam: dict, position: str | None, season_type: str) -> str:
    """Per-player aggregate CTE. `games` is aliased first so later column
    expressions can reference it (DuckDB supports lateral alias reuse)."""
    team_col = "recent_team" if fam["view"] == "v_player_stats_week_all" else "team"
    st_pred = {
        "REG": "v.season_type = 'REG'",
        "POST": "v.season_type = 'POST'",
        "ALL": "v.season_type IN ('REG','POST')",
    }[season_type]
    pos_pred = "AND coalesce(v.position_group, p.position_group) = $position" if position else ""
    col_exprs = ",\n               ".join(
        f"{sql} AS {key}" for key, (sql, _, _) in fam["cols"].items()
    )
    return f"""
        SELECT v.player_id,
               any_value(v.player_display_name) AS player,
               any_value(coalesce(v.position_group, p.position_group)) AS pos,
               CASE WHEN count(DISTINCT v.{team_col}) > 1
                    THEN count(DISTINCT v.{team_col}) || 'TM'
                    ELSE any_value(v.{team_col}) END AS team,
               any_value(p.headshot) AS headshot,
               {fam["games"]} AS games,
               {col_exprs}
        FROM {fam["view"]} v
        LEFT JOIN players p ON p.gsis_id = v.player_id
        WHERE v.season = $season AND {st_pred} {pos_pred}
        GROUP BY v.player_id
        HAVING games > 0
    """


@router.get("/api/leaders")
def leaders(
    family: str = "fantasy",
    season: int | None = None,
    season_type: str = "REG",
    position: str | None = None,
    sort: str | None = None,
    dir: str = "desc",
    qual: int = 0,
    limit: int = 25,
) -> dict:
    if family not in FAMILIES:
        raise HTTPException(400, f"family must be one of {list(FAMILIES)}")
    fam = FAMILIES[family]
    if season_type not in ("REG", "POST", "ALL"):
        raise HTTPException(400, "season_type must be REG, POST or ALL")
    if position is not None and position not in fam["positions"]:
        raise HTTPException(400, f"position must be one of {fam['positions']}")
    sort = sort or fam["default_sort"]
    if sort != "games" and sort not in fam["cols"]:
        raise HTTPException(400, f"sort must be one of {['games', *fam['cols']]}")
    if dir not in ("asc", "desc"):
        raise HTTPException(400, "dir must be asc or desc")
    if limit not in LIMITS:
        raise HTTPException(400, f"limit must be one of {LIMITS}")
    qual = max(0, qual)
    qual_col = fam["qual"]

    with read_conn() as con:
        seasons = [
            r[0]
            for r in con.execute(
                f"SELECT DISTINCT season FROM {fam['view']} ORDER BY season DESC"
            ).fetchall()
        ]
        if season is None:
            season = seasons[0] if seasons else 0
        params = {"season": season, "qual": qual}
        if position:
            params["position"] = position
        base = _base_sql(fam, position, season_type)

        rows = rows_to_dicts(
            con,
            f"""
            WITH base AS ({base})
            SELECT * FROM base WHERE {qual_col} >= $qual
            ORDER BY {sort} {dir.upper()} NULLS LAST, games DESC, player_id
            LIMIT {limit}
        """,
            params,
        )

        counts = rows_to_dicts(
            con,
            f"""
            WITH base AS ({base})
            SELECT count(*) AS total_players,
                   count(*) FILTER (WHERE {qual_col} >= $qual) AS qualified
            FROM base
        """,
            params,
        )[0]

        # league average over the qualified set + p10/p90 for rate/pct columns
        avg_exprs = ["round(avg(games), 1) AS games"]
        for key, (_, _, kind) in fam["cols"].items():
            avg_exprs.append(f"round(avg({key}), 2) AS {key}")
            if kind in ("rate", "pct"):
                avg_exprs.append(f"round(quantile_cont({key}, 0.10), 2) AS p10_{key}")
                avg_exprs.append(f"round(quantile_cont({key}, 0.90), 2) AS p90_{key}")
        avg_row = rows_to_dicts(
            con,
            f"""
            WITH base AS ({base})
            SELECT {", ".join(avg_exprs)} FROM base WHERE {qual_col} >= $qual
        """,
            params,
        )[0]

    league_avg = {k: v for k, v in avg_row.items() if not k.startswith(("p10_", "p90_"))}
    p10 = {k[4:]: v for k, v in avg_row.items() if k.startswith("p10_")}
    p90 = {k[4:]: v for k, v in avg_row.items() if k.startswith("p90_")}

    return {
        "family": family,
        "season": season,
        "season_type": season_type,
        "position": position,
        "sort": sort,
        "dir": dir,
        "label": LABELS[family],
        "qual": qual,
        "qual_key": qual_col,
        "limit": limit,
        "seasons": seasons,
        "total_players": counts["total_players"],
        "qualified": counts["qualified"],
        "columns": [
            {"key": "games", "label": "G", "kind": "count_g"},
            *[{"key": k, "label": lbl, "kind": kind} for k, (_, lbl, kind) in fam["cols"].items()],
        ],
        "league_avg": league_avg,
        "p10": p10,
        "p90": p90,
        "rows": rows,
    }
