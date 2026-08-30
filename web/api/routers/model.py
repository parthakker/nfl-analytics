"""Model Lab — the prediction model, explained and scored.

Read-only over the four model_* tables train_model.py persists plus the
experiment log `nfl experiment` appends to. Every metric here comes from
`nfl_analytics.model.backtest` / `.experiment`, the same functions the
training script uses, so the page can never disagree with the report.

When no model has been trained (a fresh clone, or a fixture without the
tables) every endpoint answers 200 with `{"available": false}` — the page
renders an empty state instead of an error.
"""

import json

from fastapi import APIRouter, HTTPException

from nfl_analytics.model import backtest as bt
from nfl_analytics.model import experiment as ex
from nfl_analytics.model.config import (
    BONUS_SEASON,
    FEATURE_LABELS,
    HOLDOUT_SEASONS,
    NET_RATING_SQL,
)
from nfl_analytics.model.predict import upcoming_week

from ..deps import read_conn, rows_to_dicts

router = APIRouter()

UNAVAILABLE = {"available": False, "reason": "no trained model — run `nfl train`"}


def _has(con, table: str) -> bool:
    return bool(
        con.execute(
            "SELECT count(*) FROM duckdb_tables() WHERE table_name = ?", [table]
        ).fetchone()[0]
    )


def _records(df) -> list[dict]:
    return [{k: ex._py(v) for k, v in r.items()} for r in df.to_dict("records")]


def _summary(s: dict) -> dict:
    """backtest.summarize() minus its DataFrames, JSON-native."""
    return {
        k: ex._py(v) for k, v in s.items() if k not in ("calibration", "ats", "ats_late_season")
    }


@router.get("/api/model/report")
def report() -> dict:
    with read_conn() as con:
        if not _has(con, "model_params"):
            return UNAVAILABLE
        p = con.execute("SELECT * FROM model_params").fetchdf().iloc[0].to_dict()
        pred = con.execute("SELECT * FROM model_predictions").fetchdf()
    feature_cols = json.loads(p["feature_cols"])
    win_coefs, margin_coefs = json.loads(p["win_coefs"]), json.loads(p["margin_coefs"])
    hold = bt.summarize(pred, *HOLDOUT_SEASONS)
    has_bonus = bool((pred["season"] == BONUS_SEASON).any())
    bonus = bt.summarize(pred, BONUS_SEASON, BONUS_SEASON) if has_bonus else None
    return {
        "available": True,
        "fitted_at": str(p["fitted_at"]),
        "config": {
            "ratings_source": p.get("ratings_source", "ewma"),
            "half_life": ex._py(p["half_life"]),
            "carryover": ex._py(p["carryover"]),
            "ridge_alpha": ex._py(p.get("ridge_alpha")),
            "qb_flag": bool(p.get("qb_flag")),
            "features": feature_cols,
            "train_games": ex._py(p.get("train_games")),
        },
        "holdout": {"seasons": list(HOLDOUT_SEASONS), **_summary(hold)},
        "bonus": {"season": BONUS_SEASON, **_summary(bonus)} if bonus else None,
        "calibration": _records(hold["calibration"]),
        "ats": _records(hold["ats"]),
        "ats_late_season": _records(hold["ats_late_season"]),
        "by_season": ex.by_season(pred),
        "coefs": [
            {
                "feature": c,
                "label": FEATURE_LABELS.get(c, (c, ""))[0],
                "help": FEATURE_LABELS.get(c, (c, ""))[1],
                "win_coef": w,
                "margin_coef": m,
            }
            for c, w, m in zip(feature_cols, win_coefs, margin_coefs, strict=True)
        ],
        "intercept": {
            "win": ex._py(p["win_intercept"]),
            "margin": ex._py(p["margin_intercept"]),
        },
    }


@router.get("/api/model/week")
def week(season: int | None = None, week: int | None = None) -> dict:
    with read_conn() as con:
        if not _has(con, "model_params"):
            return UNAVAILABLE
        out = upcoming_week(con, season, week)
    return {"available": True, **out}


@router.get("/api/model/ratings")
def ratings() -> dict:
    with read_conn() as con:
        if not _has(con, "model_ratings"):
            return UNAVAILABLE
        fitted = con.execute("SELECT fitted_at FROM model_params").fetchone()
        teams = rows_to_dicts(
            con,
            f"""
            SELECT team,
                   rank() OVER (ORDER BY {NET_RATING_SQL} DESC) AS rank,
                   round({NET_RATING_SQL}, 4) AS net,
                   round(r_off_pass, 4) AS off_pass, round(r_off_rush, 4) AS off_rush,
                   round(r_def_pass, 4) AS def_pass, round(r_def_rush, 4) AS def_rush
            FROM model_ratings ORDER BY net DESC
            """,
        )
    return {
        "available": True,
        "as_of": str(fitted[0]) if fitted else None,
        "teams": teams,
    }


@router.get("/api/model/ratings/{team}/history")
def rating_history(team: str) -> dict:
    with read_conn() as con:
        if not _has(con, "model_rating_history"):
            return UNAVAILABLE
        rows = rows_to_dicts(
            con,
            f"""
            SELECT game_id, season, week, opponent,
                   round(r_off_pass, 4) AS off_pass, round(r_off_rush, 4) AS off_rush,
                   round(r_def_pass, 4) AS def_pass, round(r_def_rush, 4) AS def_rush,
                   round({NET_RATING_SQL}, 4) AS net
            FROM model_rating_history WHERE team = canon_team(?)
            ORDER BY season, week
            """,
            [team],
        )
    if not rows:
        raise HTTPException(404, "unknown team")
    return {"available": True, "team": team.upper(), "rows": rows}


@router.get("/api/model/experiments")
def experiments(limit: int = 100) -> dict:
    runs = ex.read_log(ex.EXPERIMENT_LOG, limit=max(1, min(limit, 500)))
    with read_conn() as con:
        shipped = ex.shipped_metrics(con)
        cfg = ex.shipped_config(con) if shipped else None
    scored = [r for r in runs if (r.get("metrics") or {}).get("brier_model") is not None]
    best = min(scored, key=lambda r: r["metrics"]["brier_model"]) if scored else None
    return {
        "available": True,
        "shipped": (
            {"metrics": shipped, "config": {"features": list(cfg.features), **cfg.__dict__}}
            if shipped and cfg
            else None
        ),
        "runs": runs,
        "best": best,
        "how_to": "nfl experiment --features -d_qb_out --note 'without the QB flag'",
    }
