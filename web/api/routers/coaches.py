import json

from fastapi import APIRouter, HTTPException

from ..deps import ROOT, read_conn, rows_to_dicts

router = APIRouter()

META_PATH = ROOT / "data" / "coaches_meta.json"


def _meta() -> dict:
    if META_PATH.exists():
        return json.loads(META_PATH.read_text(encoding="utf-8"))
    return {}


@router.get("/api/coaches")
def coaches(min_games: int = 32) -> dict:
    with read_conn() as con:
        rows = rows_to_dicts(
            con,
            """
            WITH career AS (
                SELECT coach, min(season) AS first_season, max(season) AS last_season,
                       sum(reg_games)::int AS g, sum(reg_wins)::int AS w,
                       sum(post_games)::int AS post_g, sum(post_wins)::int AS post_w,
                       sum(ats_wins)::int AS ats_w, sum(ats_games)::int AS ats_g
                FROM v_coach_seasons GROUP BY coach
            ), tend AS (
                SELECT coach,
                       round(sum(go_attempts)::double / nullif(sum(go_situations), 0), 3) AS go_rate,
                       round(avg(proe), 4) AS proe
                FROM v_coach_tendencies GROUP BY coach
            )
            SELECT c.*, t.go_rate, t.proe,
                   round(c.ats_w::double / nullif(c.ats_g, 0), 3) AS ats_pct
            FROM career c LEFT JOIN tend t USING (coach)
            WHERE c.g >= ? ORDER BY c.w DESC
        """,
            [min_games],
        )
    current = {v["head_coach"]: k for k, v in _meta().items()}
    for r in rows:
        r["current_team"] = current.get(r["coach"])
    return {"coaches": rows}


@router.get("/api/coaches/{name}")
def coach(name: str) -> dict:
    with read_conn() as con:
        seasons = rows_to_dicts(
            con,
            """
            SELECT s.*, t.proe, t.shotgun_rate, t.no_huddle_rate, t.deep_shot_rate,
                   t.plays_per_game, t.go_situations, t.go_attempts,
                   round(t.go_attempts::double / nullif(t.go_situations, 0), 3) AS go_rate,
                   d.def_pass_epa, d.def_rush_epa, d.sack_rate, d.takeaway_rate,
                   d.run_stuff_rate
            FROM v_coach_seasons s
            LEFT JOIN v_coach_tendencies t ON t.coach = s.coach AND t.season = s.season
            LEFT JOIN v_coach_def_tendencies d ON d.coach = s.coach AND d.season = s.season
            WHERE s.coach = ? ORDER BY s.season
        """,
            [name],
        )
        if not seasons:
            raise HTTPException(404, f"no coaching record for {name!r} (2007+)")

        latest = seasons[-1]["season"]
        # percentile fingerprint vs all coach-seasons of the same season
        fp = []
        metrics = [
            ("proe", "Pass rate over expected", "v_coach_tendencies", False),
            ("go_rate_calc", "4th-down aggression", "v_coach_tendencies", False),
            ("deep_shot_rate", "Deep shots", "v_coach_tendencies", False),
            ("no_huddle_rate", "Tempo (no-huddle)", "v_coach_tendencies", False),
            ("sack_rate", "Pass rush (sacks)", "v_coach_def_tendencies", False),
            ("def_pass_epa", "Pass defense", "v_coach_def_tendencies", True),  # lower better
        ]
        for key, label, table, invert in metrics:
            expr = "go_attempts::double / nullif(go_situations,0)" if key == "go_rate_calc" else key
            row = con.execute(
                f"""
                WITH vals AS (
                    SELECT coach, {expr} AS v FROM {table}
                    WHERE season = ? AND {expr} IS NOT NULL
                )
                SELECT round(100.0 * count(*) FILTER (
                           WHERE v {">" if invert else "<"} (SELECT v FROM vals WHERE coach = ?))
                       / nullif(count(*), 0))
                FROM vals
            """,
                [latest, name],
            ).fetchone()
            fp.append({"metric": label, "pct": int(row[0]) if row and row[0] is not None else None})

        rivals = rows_to_dicts(
            con,
            """
            SELECT opp_coach, games::int AS games, wins::int AS wins,
                   round(avg_pf, 1) AS avg_pf, round(avg_pa, 1) AS avg_pa
            FROM v_coach_matchups WHERE coach = ? AND games >= 3
            ORDER BY games DESC LIMIT 10
        """,
            [name],
        )

    meta = _meta()
    team = next((k for k, v in meta.items() if v["head_coach"] == name), None)
    return {
        "coach": name,
        "current_team": team,
        "scheme": meta.get(team) if team else None,
        "seasons": seasons,
        "fingerprint": fp,
        "rivals": rivals,
        "fingerprint_note": f"percentile vs all head coaches, {latest} season",
    }
