"""Serve-time game prediction from persisted model tables (no sklearn)."""

import json
import math

import duckdb


def _params(con: duckdb.DuckDBPyConnection) -> dict:
    row = con.execute("SELECT * FROM model_params").fetchdf().iloc[0].to_dict()
    row["feature_cols"] = json.loads(row["feature_cols"])
    row["win_coefs"] = json.loads(row["win_coefs"])
    row["margin_coefs"] = json.loads(row["margin_coefs"])
    return row


def _rating(con, team: str) -> dict:
    df = con.execute("SELECT * FROM model_ratings WHERE team = canon_team(?)", [team]).fetchdf()
    if df.empty:
        raise ValueError(f"no ratings for team {team!r}")
    return df.iloc[0].to_dict()


def predict_game(
    con: duckdb.DuckDBPyConnection,
    home_team: str,
    away_team: str,
    rest_diff: float = 0.0,
    away_tz_shift: float | None = None,
    div_game: int | None = None,
    d_qb_out: float | None = None,
) -> dict:
    """Predict an arbitrary matchup using current ratings.

    For a scheduled game, look up rest/div from `schedules` first and pass
    them in; defaults assume equal rest. away_tz_shift defaults to the
    timezone gap between the away team's home and the venue (home team's tz).
    """
    p = _params(con)
    h, a = _rating(con, home_team), _rating(con, away_team)

    if away_tz_shift is None:
        row = con.execute(
            """
            SELECT awy.offset_behind_et - hm.offset_behind_et
            FROM team_timezones hm, team_timezones awy
            WHERE hm.team = canon_team(?) AND awy.team = canon_team(?)
        """,
            [home_team, away_team],
        ).fetchone()
        away_tz_shift = float(row[0]) if row and row[0] is not None else 0.0
    if div_game is None:
        row = con.execute(
            """
            SELECT max(div_game::int) FROM schedules
            WHERE home_team = canon_team(?) AND away_team = canon_team(?)
              AND season >= 2024
        """,
            [home_team, away_team],
        ).fetchone()
        div_game = int(row[0]) if row and row[0] is not None else 0

    feats = {
        "d_off_pass": h["r_off_pass"] - a["r_off_pass"],
        "d_off_rush": h["r_off_rush"] - a["r_off_rush"],
        "d_def_pass": a["r_def_pass"] - h["r_def_pass"],
        "d_def_rush": a["r_def_rush"] - h["r_def_rush"],
        "d_rest": rest_diff,
        "d_tz": away_tz_shift,
        "div_game": div_game,
    }
    if "d_qb_out" in p["feature_cols"]:
        if d_qb_out is None:
            # live lookup: expected starter + current-week status, schedules-
            # only path for upcoming games (see qb_flag.current_qb_out)
            from .qb_flag import current_qb_out

            try:
                d_qb_out = float(
                    current_qb_out(con, home_team)["qb_out"]
                    - current_qb_out(con, away_team)["qb_out"]
                )
            except Exception:
                d_qb_out = 0.0  # serving must not fail on a missing lookup
        feats["d_qb_out"] = d_qb_out
    x = [feats[c] for c in p["feature_cols"]]
    z = p["win_intercept"] + sum(c * v for c, v in zip(p["win_coefs"], x, strict=False))
    margin = p["margin_intercept"] + sum(c * v for c, v in zip(p["margin_coefs"], x, strict=False))
    return {
        "home_team": home_team,
        "away_team": away_team,
        "p_home_win": 1.0 / (1.0 + math.exp(-z)),
        "pred_margin": margin,  # positive = home by that many
        "inputs": feats,
        "model": {
            "ratings_source": p.get("ratings_source", "ewma"),
            "half_life": p["half_life"],
            "carryover": p["carryover"],
            "holdout_brier": p["holdout_brier"],
        },
    }
