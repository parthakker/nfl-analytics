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
            "pass_yds": ("sum(v.passing_yards)::int", "PassYds", "count"),
            "pass_td": ("sum(v.passing_tds)::int", "PassTD", "count"),
            "ints": ("sum(v.interceptions)::int", "Int", "count"),
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

# hover help: key -> (full name, one-line explanation). Keys shared across
# families get one entry; the UI shows "full name — explanation".
STAT_HELP: dict[str, tuple[str, str]] = {
    "games": (
        "Games played",
        "Weeks with at least one touch, attempt or target (activity-filtered)",
    ),
    # passing
    "cmp": ("Completions", "Passes completed"),
    "att": ("Attempts / Carries", "Pass attempts (passing) or rush attempts (rushing/fantasy)"),
    "cmp_pct": ("Completion %", "Completions ÷ attempts"),
    "pass_yds": ("Passing yards", "Total passing yards"),
    "pass_ypg": ("Passing yards per game", "Passing yards ÷ games played"),
    "ypa": ("Yards per attempt", "Passing yards ÷ pass attempts"),
    "pass_td": ("Passing touchdowns", "Touchdown passes thrown"),
    "ints": ("Interceptions", "Passes intercepted"),
    "sacks": ("Sacks", "Times sacked (passing) or sacks recorded (defense)"),
    "air_yds": ("Air yards", "Yards the ball traveled in the air on throws/targets"),
    "epa_db": (
        "EPA per dropback",
        "Expected Points Added per dropback (attempts + sacks) — >0.15 is elite",
    ),
    "pacr": ("PACR", "Passing Air Conversion Ratio: passing yards ÷ air yards"),
    "rush_yds": ("Rushing yards", "Total rushing yards"),
    "rush_td": ("Rushing touchdowns", "Rushing touchdowns"),
    # rushing
    "rush_ypg": ("Rushing yards per game", "Rushing yards ÷ games played"),
    "ypc": ("Yards per carry", "Rushing yards ÷ carries"),
    "fum_lost": ("Fumbles lost", "Rushing fumbles lost to the defense"),
    "first_downs": ("First downs", "First downs gained rushing/receiving"),
    "epa_rush": (
        "EPA per rush",
        "Expected Points Added per carry — positive means the run game helps",
    ),
    "rec": ("Receptions", "Passes caught"),
    "rec_yds": ("Receiving yards", "Total receiving yards"),
    "ppr": ("PPR points", "Fantasy points, full point per reception scoring"),
    # receiving
    "tgt": ("Targets", "Passes thrown the player's way"),
    "catch_pct": ("Catch %", "Receptions ÷ targets"),
    "rec_ypg": ("Receiving yards per game", "Receiving yards ÷ games played"),
    "ypr": ("Yards per reception", "Receiving yards ÷ receptions"),
    "rec_td": ("Receiving touchdowns", "Receiving touchdowns"),
    "yac": ("Yards after catch", "Yards gained after the catch"),
    "epa_tgt": ("EPA per target", "Expected Points Added per target — receiving efficiency"),
    "tgt_share": ("Target share", "Average share of the team's targets per week"),
    "wopr": (
        "Weighted Opportunity Rating",
        "1.5×target share + 0.7×air-yards share — usage that predicts fantasy value",
    ),
    # fantasy
    "std": ("Standard points", "Fantasy points, no points for receptions"),
    "half_ppr": ("Half-PPR points", "Fantasy points, half point per reception"),
    "std_pg": ("Standard points per game", "Standard fantasy points ÷ games played"),
    "half_pg": ("Half-PPR points per game", "Half-PPR fantasy points ÷ games played"),
    "ppr_pg": ("PPR points per game", "PPR fantasy points ÷ games played"),
    "touches": ("Touches", "Carries + receptions"),
    "total_td": ("Total touchdowns", "Rushing + receiving + passing touchdowns"),
    # defense
    "tackles": ("Combined tackles", "Solo tackles + assists"),
    "solo": ("Solo tackles", "Unassisted tackles"),
    "ast": ("Tackle assists", "Assisted tackles"),
    "tfl": ("Tackles for loss", "Tackles behind the line of scrimmage"),
    "qb_hits": ("QB hits", "Hits on the quarterback (includes sacks)"),
    "pd": ("Passes defended", "Passes broken up or deflected"),
    "ff": ("Forced fumbles", "Fumbles forced"),
    "fr": ("Fumble recoveries", "Opponent fumbles recovered"),
    "def_td": ("Defensive touchdowns", "Interception/fumble returns for TD"),
    "safeties": ("Safeties", "Safeties recorded"),
    "tkl_pg": ("Tackles per game", "Combined tackles ÷ games played"),
    # kicking
    "fg_made": ("Field goals made", "Field goals converted"),
    "fg_att": ("Field goal attempts", "Field goals attempted"),
    "fg_pct": ("Field goal %", "FG made ÷ FG attempted"),
    "fg_long": ("Longest field goal", "Longest made field goal (yards)"),
    "fg_40_49": ("FG made 40-49", "Field goals made from 40-49 yards"),
    "fg_50_plus": ("FG made 50+", "Field goals made from 50+ yards"),
    "pat_made": ("Extra points made", "Extra points converted"),
    "pat_att": ("Extra point attempts", "Extra points attempted"),
    "points": ("Kicking points", "3 × FG made + extra points made"),
    "pts_pg": ("Kicking points per game", "Kicking points ÷ games played"),
}

# position-aware display order: (family, position) -> ordered column keys.
# Rows always carry the family superset; this only changes WHICH columns show
# and in what order. No entry = the family's standard order.
POSITION_COLUMNS: dict[tuple[str, str], list[str]] = {
    ("fantasy", "QB"): [
        "ppr",
        "ppr_pg",
        "std",
        "std_pg",
        "pass_yds",
        "pass_td",
        "ints",
        "att",
        "rush_yds",
        "total_td",
    ],
    ("fantasy", "RB"): [
        "ppr",
        "ppr_pg",
        "half_ppr",
        "half_pg",
        "att",
        "rush_yds",
        "touches",
        "rec",
        "rec_yds",
        "total_td",
    ],
    ("fantasy", "WR"): [
        "ppr",
        "ppr_pg",
        "half_ppr",
        "half_pg",
        "tgt",
        "rec",
        "rec_yds",
        "rush_yds",
        "total_td",
    ],
    ("fantasy", "TE"): [
        "ppr",
        "ppr_pg",
        "half_ppr",
        "half_pg",
        "tgt",
        "rec",
        "rec_yds",
        "total_td",
    ],
    ("defense", "DL"): [
        "sacks",
        "qb_hits",
        "tfl",
        "tackles",
        "solo",
        "ast",
        "ff",
        "fr",
        "def_td",
        "safeties",
    ],
    ("defense", "DB"): [
        "ints",
        "pd",
        "tackles",
        "solo",
        "ast",
        "tfl",
        "sacks",
        "ff",
        "fr",
        "def_td",
    ],
}


def columns_for(family: str, position: str | None) -> list[dict]:
    fam = FAMILIES[family]
    order = POSITION_COLUMNS.get((family, position or ""), list(fam["cols"].keys()))
    specs = [
        {"key": "games", "label": "G", "kind": "count_g", "help": " — ".join(STAT_HELP["games"])}
    ]
    for key in order:
        if key not in fam["cols"]:
            continue
        _, label, kind = fam["cols"][key]
        full, expl = STAT_HELP.get(key, (label, ""))
        specs.append(
            {"key": key, "label": label, "kind": kind, "help": f"{full} — {expl}" if expl else full}
        )
    return specs


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
        "columns": columns_for(family, position),
        "league_avg": league_avg,
        "p10": p10,
        "p90": p90,
        "rows": rows,
    }
