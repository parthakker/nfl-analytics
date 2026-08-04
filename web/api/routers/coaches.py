"""Coaches: head-coach records from the warehouse + the hand-curated staff db
(data/coaches_meta.json) for current-staff info, coordinators and scheme
knowledge links.

/api/coaches/{name} is role-aware:
  1. warehouse HC (v_coach_seasons)      -> full HC payload (+ meta about/staff)
  2. meta-only HC (new hire, no history) -> HC payload with empty seasons
  3. coordinator (oc/dc in meta)         -> coordinator payload + unit EPA
  4. otherwise                           -> 404
"""

import json

from fastapi import APIRouter, HTTPException

from ..deps import ROOT, read_conn, rows_to_dicts

router = APIRouter()

META_PATH = ROOT / "data" / "coaches_meta.json"


def _meta() -> dict:
    if META_PATH.exists():
        raw = json.loads(META_PATH.read_text(encoding="utf-8"))
        return {k: v for k, v in raw.items() if not k.startswith("_")}
    return {}


def _staff_rows(meta: dict) -> list[dict]:
    rows = []
    for team, v in sorted(meta.items()):
        for role, key, scheme_key in (
            ("OC", "oc", "offense_scheme"),
            ("DC", "dc", "defense_scheme"),
        ):
            block = v.get(key)
            if not block:
                continue
            rows.append(
                {
                    "team": team,
                    "role": role,
                    "name": block["name"],
                    "since": block.get("since"),
                    "playcaller": block.get("playcaller"),
                    "scheme_family": v[scheme_key]["family"],
                    "about": block.get("about", ""),
                }
            )
    return rows


def _team_of_hc(meta: dict, name: str) -> str | None:
    return next((k for k, v in meta.items() if v["head_coach"] == name), None)


def _find_coordinator(meta: dict, name: str) -> tuple[str, str, dict] | None:
    for team, v in meta.items():
        for role, key in (("OC", "oc"), ("DC", "dc")):
            block = v.get(key)
            if block and block["name"] == name:
                return team, role, v
    return None


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
    meta = _meta()
    current = {v["head_coach"]: k for k, v in meta.items()}
    for r in rows:
        r["current_team"] = current.get(r["coach"])
    return {"coaches": rows, "staff": _staff_rows(meta)}


def _hc_payload(con, name: str, meta: dict, seasons: list[dict]) -> dict:
    team = _team_of_hc(meta, name)
    team_meta = meta.get(team) if team else None
    fp: list[dict] = []
    rivals: list[dict] = []
    note = (
        f"no NFL head-coaching record yet (first season {team_meta['hc']['since']})"
        if not seasons and team_meta
        else ""
    )

    if seasons:
        latest = seasons[-1]["season"]
        metrics = [
            ("proe", "Pass rate over expected", "v_coach_tendencies", False),
            ("go_rate_calc", "4th-down aggression", "v_coach_tendencies", False),
            ("deep_shot_rate", "Deep shots", "v_coach_tendencies", False),
            ("no_huddle_rate", "Tempo (no-huddle)", "v_coach_tendencies", False),
            ("sack_rate", "Pass rush (sacks)", "v_coach_def_tendencies", False),
            ("def_pass_epa", "Pass defense", "v_coach_def_tendencies", True),
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
        note = f"percentile vs all head coaches, {latest} season"

    return {
        "role": "HC",
        "coach": name,
        "current_team": team,
        "about": team_meta["hc"]["about"] if team_meta else None,
        "since": team_meta["hc"]["since"] if team_meta else None,
        "team_note": team_meta.get("note") if team_meta else None,
        "scheme": team_meta,
        "staff": {"oc": team_meta.get("oc"), "dc": team_meta.get("dc")} if team_meta else None,
        "seasons": seasons,
        "fingerprint": fp,
        "rivals": rivals,
        "fingerprint_note": note,
    }


@router.get("/api/coaches/{name}")
def coach(name: str, role: str | None = None) -> dict:
    """role=OC|DC forces the coordinator view — needed because many current
    coordinators (Daboll, Spagnuolo, Reich, Nagy...) also have HC history in
    the warehouse, which otherwise wins the lookup."""
    if role is not None and role not in ("OC", "DC"):
        raise HTTPException(400, "role must be OC or DC")
    meta = _meta()
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
        found = _find_coordinator(meta, name)
        wants_coordinator = role is not None and found is not None and found[1] == role
        if not wants_coordinator and (seasons or _team_of_hc(meta, name)):
            payload = _hc_payload(con, name, meta, seasons)
            if found:  # ex-coordinator crosslink (e.g. an HC who is now an OC)
                payload["coordinator_role"] = {"role": found[1], "team": found[0]}
            return payload

        if not found:
            raise HTTPException(404, f"no coaching record for {name!r}")
        team, role, team_meta = found
        block = team_meta["oc"] if role == "OC" else team_meta["dc"]
        scheme = team_meta["offense_scheme"] if role == "OC" else team_meta["defense_scheme"]
        view = "v_team_epa_season" if role == "OC" else "v_team_def_epa_season"
        col, asc = ("off_epa", "DESC") if role == "OC" else ("def_epa", "ASC")
        unit_seasons = rows_to_dicts(
            con,
            f"""
            WITH ranked AS (
                SELECT season, team, round({col}, 3) AS epa,
                       rank() OVER (PARTITION BY season ORDER BY {col} {asc}) AS rank
                FROM {view}
            )
            SELECT season, epa, rank FROM ranked
            WHERE team = ? AND season >= ? ORDER BY season
        """,
            [team, block.get("since", 2020) - 1],
        )
    return {
        "role": role,
        "coach": name,
        "current_team": team,
        "head_coach": team_meta["head_coach"],
        "since": block.get("since"),
        "playcaller": block.get("playcaller"),
        "about": block.get("about", ""),
        "team_note": team_meta.get("note"),
        "scheme": scheme,
        "unit_seasons": unit_seasons,
        "unit_label": "offense EPA/play" if role == "OC" else "defense EPA/play allowed",
    }
