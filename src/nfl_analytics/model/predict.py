"""Serve-time game prediction from persisted model tables (no sklearn)."""

import json
import math

import duckdb
import pandas as pd

from .config import FEATURE_LABELS
from .features import feature_row, moneyline_prob, rest_clip


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

    The result carries `contributions`: one row per feature with the feature
    value, its coefficient and the product — the logit and margin points that
    feature added. Summing `logit` over rows plus `intercept.logit` gives
    logit(p_home_win); same for margin_pts.
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

    if "d_qb_out" in p["feature_cols"] and d_qb_out is None:
        # live lookup: expected starter + current-week status, schedules-
        # only path for upcoming games (see qb_flag.current_qb_out)
        from .qb_flag import current_qb_out

        try:
            d_qb_out = float(
                current_qb_out(con, home_team)["qb_out"] - current_qb_out(con, away_team)["qb_out"]
            )
        except Exception:
            d_qb_out = 0.0  # serving must not fail on a missing lookup
    feats = feature_row(h, a, rest_diff, away_tz_shift, div_game, d_qb_out or 0.0)
    feats = {c: feats[c] for c in p["feature_cols"]}

    x = [feats[c] for c in p["feature_cols"]]
    contributions = [
        {
            "feature": c,
            "label": FEATURE_LABELS.get(c, (c, ""))[0],
            "value": float(v),
            "win_coef": float(wc),
            "margin_coef": float(mc),
            "logit": float(wc * v),
            "margin_pts": float(mc * v),
        }
        for c, v, wc, mc in zip(
            p["feature_cols"], x, p["win_coefs"], p["margin_coefs"], strict=True
        )
    ]
    z = p["win_intercept"] + sum(r["logit"] for r in contributions)
    margin = p["margin_intercept"] + sum(r["margin_pts"] for r in contributions)
    return {
        "home_team": home_team,
        "away_team": away_team,
        "p_home_win": 1.0 / (1.0 + math.exp(-z)),
        "pred_margin": margin,  # positive = home by that many
        "inputs": feats,
        "contributions": contributions,
        "intercept": {
            "logit": float(p["win_intercept"]),
            "margin_pts": float(p["margin_intercept"]),
        },
        "model": {
            "ratings_source": p.get("ratings_source", "ewma"),
            "half_life": p["half_life"],
            "carryover": p["carryover"],
            "holdout_brier": p["holdout_brier"],
        },
    }


_WEEK_SQL = """
    SELECT game_id, season, week, gameday, gametime, away_team, home_team,
           home_rest, away_rest, div_game, spread_line, total_line,
           home_moneyline, away_moneyline, result
    FROM schedules
    WHERE season = ? AND week = ?
    ORDER BY gameday, gametime, game_id
"""


def next_unplayed(con) -> tuple[int, int] | None:
    """(season, week) of the earliest week with an unplayed game."""
    row = con.execute(
        """
        SELECT season, min(week) FROM schedules
        WHERE result IS NULL
          AND season = (SELECT min(season) FROM schedules WHERE result IS NULL)
        GROUP BY season
        """
    ).fetchone()
    return (int(row[0]), int(row[1])) if row else None


def upcoming_week(con, season: int | None = None, week: int | None = None) -> dict:
    """Every game of one schedule week through predict_game, with the market
    alongside. Defaults to the next unplayed week. One bad game reports its
    own `error` instead of failing the whole week."""
    if season is None or week is None:
        nxt = next_unplayed(con)
        if nxt is None:
            return {"season": None, "week": None, "games": []}
        season, week = nxt
    games = con.execute(_WEEK_SQL, [season, week]).fetchdf()
    out = []
    for _, g in games.iterrows():
        row = {
            "game_id": g["game_id"],
            "date": None if pd.isna(g["gameday"]) else str(g["gameday"]),
            "time": None if pd.isna(g["gametime"]) else str(g["gametime"]),
            "away_team": g["away_team"],
            "home_team": g["home_team"],
            "played": not pd.isna(g["result"]),
            "spread_line": None if pd.isna(g["spread_line"]) else float(g["spread_line"]),
            "total_line": None if pd.isna(g["total_line"]) else float(g["total_line"]),
        }
        ph, pa = moneyline_prob(g["home_moneyline"]), moneyline_prob(g["away_moneyline"])
        row["market_home_prob"] = ph / (ph + pa) if ph and pa else None
        try:
            kw = {"rest_diff": rest_clip(g["home_rest"]) - rest_clip(g["away_rest"])}
            if not pd.isna(g["div_game"]):
                kw["div_game"] = int(g["div_game"])
            p = predict_game(con, g["home_team"], g["away_team"], **kw)
            row.update(
                {
                    "p_home_win": p["p_home_win"],
                    "pred_margin": p["pred_margin"],
                    "contributions": p["contributions"],
                    "intercept": p["intercept"],
                    "edge_prob": (
                        p["p_home_win"] - row["market_home_prob"]
                        if row["market_home_prob"] is not None
                        else None
                    ),
                    # spread_line positive = home favoured by that many, same
                    # sign as pred_margin, so the difference is the disagreement
                    "edge_pts": (
                        p["pred_margin"] - row["spread_line"]
                        if row["spread_line"] is not None
                        else None
                    ),
                    "error": None,
                }
            )
        except Exception as e:  # noqa: BLE001 — one game must not kill the week
            row.update({"p_home_win": None, "pred_margin": None, "error": str(e)})
        out.append(row)
    return {"season": season, "week": week, "games": out}
