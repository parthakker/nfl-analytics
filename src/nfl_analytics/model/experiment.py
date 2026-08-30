"""One model configuration, end to end, in seconds — the experiment loop.

`train_model.py` is the full protocol: grids, gates, causality asserts,
persistence (~5 min). Almost all of that time is the hyperparameter grids;
a single configuration through the whole walk-forward takes ~3 s. This
module is that fast path, shared by:

  * scripts/run_experiment.py   (`nfl experiment`) — try one idea, log it
  * scripts/train_model.py      — logs the shipped result the same way
  * web/api/routers/model.py    — the Model Lab reads the log + by_season
  * scripts/export_model_recap.py

Every run appends one JSON line to logs/model_experiments.jsonl so the
question "what have I tried and what did it score?" always has an answer.
"""

from __future__ import annotations

import json
import subprocess
import time
from dataclasses import asdict, dataclass, replace
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

from ..config import ROOT
from . import backtest as bt
from .config import BONUS_SEASON, EXPERIMENT_LOG, FIRST_TARGET, HOLDOUT_SEASONS
from .features import FEATURE_COLS, RATINGS_SOURCES, build_features, compute_ratings_source

# Columns build_features produces that are NOT legal model inputs: targets,
# ids, and the market reference. Everything else is fair game for --features.
_NON_FEATURES = {
    "game_id",
    "season",
    "week",
    "season_type",
    "home_team",
    "away_team",
    "home_margin",
    "home_win",
    "spread_line",
    "home_rest",
    "away_rest",
    "away_tz_shift",
    "home_moneyline",
    "away_moneyline",
    "market_home_prob",
    "home_qb_out",
    "away_qb_out",
}


@dataclass(frozen=True)
class ExperimentConfig:
    features: tuple[str, ...] = tuple(FEATURE_COLS)
    half_life: float = 8.0
    carryover: float = 0.5
    ratings_source: str = "ewma"
    ridge_alpha: float | None = None
    recency_half_life: float | None = None
    calibration_window: int | None = None
    note: str = ""

    def describe(self) -> str:
        src = f"{self.ratings_source} h={self.half_life:g} c={self.carryover:g}"
        if self.ratings_source == "ridge" and self.ridge_alpha is not None:
            src += f" a={self.ridge_alpha:g}"
        extras = []
        if self.recency_half_life:
            extras.append(f"recency={self.recency_half_life:g}")
        if self.calibration_window:
            extras.append(f"platt={self.calibration_window}")
        return src + (" " + " ".join(extras) if extras else "")


@dataclass
class ExperimentResult:
    config: ExperimentConfig
    pred: pd.DataFrame  # walk-forward rows FIRST_TARGET..BONUS_SEASON
    holdout: dict  # backtest.summarize over HOLDOUT_SEASONS
    bonus: dict | None  # backtest.summarize over BONUS_SEASON, if present
    seconds: float


# ── configuration ────────────────────────────────────────────────────────────


def shipped_config(con) -> ExperimentConfig:
    """The configuration train_model.py persisted, or the package defaults if
    no model has been trained yet."""
    try:
        row = con.execute("SELECT * FROM model_params").fetchdf().iloc[0]
    except Exception:
        return ExperimentConfig()
    alpha = row.get("ridge_alpha")
    return ExperimentConfig(
        features=tuple(json.loads(row["feature_cols"])),
        half_life=float(row["half_life"]),
        carryover=float(row["carryover"]),
        ratings_source=str(row.get("ratings_source") or "ewma"),
        ridge_alpha=None if alpha is None or pd.isna(alpha) else float(alpha),
    )


def shipped_metrics(con) -> dict | None:
    """Headline numbers train_model.py recorded for the shipped model."""
    try:
        row = (
            con.execute("SELECT holdout_brier, holdout_logloss, fitted_at FROM model_params")
            .fetchdf()
            .iloc[0]
        )
    except Exception:
        return None
    return {
        "brier_model": float(row["holdout_brier"]),
        "logloss_model": float(row["holdout_logloss"]),
        "fitted_at": str(row["fitted_at"]),
    }


def apply_feature_edits(base: tuple[str, ...], spec: str | None) -> tuple[str, ...]:
    """`+col,-col` edits the base list; a plain `a,b,c` replaces it."""
    if not spec:
        return tuple(base)
    tokens = [t.strip() for t in spec.split(",") if t.strip()]
    if all(t[0] in "+-" for t in tokens):
        cols = list(base)
        for t in tokens:
            name = t[1:]
            if t[0] == "+" and name not in cols:
                cols.append(name)
            elif t[0] == "-" and name in cols:
                cols.remove(name)
        return tuple(cols)
    return tuple(tokens)


# ── running ──────────────────────────────────────────────────────────────────


def build_frame(con, cfg: ExperimentConfig) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Ratings -> QB flags -> features. Returns (feature frame, per-game
    entering ratings, current end-state ratings). This is the ~3 s part."""
    if cfg.ratings_source not in RATINGS_SOURCES:
        raise ValueError(f"ratings_source must be one of {RATINGS_SOURCES}")
    hyper = {"half_life": cfg.half_life, "carryover": cfg.carryover}
    if cfg.ratings_source == "ridge" and cfg.ridge_alpha is not None:
        hyper["alpha"] = cfg.ridge_alpha
    per_game, current = compute_ratings_source(con, cfg.ratings_source, **hyper)
    from .qb_flag import qb_out_flags

    flags = qb_out_flags(con)
    return build_features(con, per_game, flags), per_game, current


def validate_features(frame: pd.DataFrame, features: tuple[str, ...]) -> None:
    legal = [c for c in frame.columns if c not in _NON_FEATURES and not c.startswith(("h_", "a_"))]
    unknown = [f for f in features if f not in frame.columns]
    illegal = [f for f in features if f in _NON_FEATURES]
    if unknown or illegal:
        raise ValueError(
            f"unknown features {unknown}, target/leak columns {illegal}; "
            f"legal choices: {sorted(legal)}"
        )


def run(con, cfg: ExperimentConfig, frame: pd.DataFrame | None = None) -> ExperimentResult:
    t0 = time.time()
    if frame is None:
        frame, _, _ = build_frame(con, cfg)
    validate_features(frame, cfg.features)
    pred = bt.walk_forward(
        frame,
        first_target=FIRST_TARGET,
        last_target=BONUS_SEASON,
        feature_cols=list(cfg.features),
        recency_half_life=cfg.recency_half_life,
        calibration_window=cfg.calibration_window,
    )
    holdout = bt.summarize(pred, *HOLDOUT_SEASONS)
    has_bonus = bool((pred["season"] == BONUS_SEASON).any())
    bonus = bt.summarize(pred, BONUS_SEASON, BONUS_SEASON) if has_bonus else None
    return ExperimentResult(cfg, pred, holdout, bonus, time.time() - t0)


def by_season(pred: pd.DataFrame) -> list[dict]:
    """Per-season report-card rows from walk-forward predictions. Reuses the
    backtest metric functions so the API, recap and scorecard cannot drift."""
    rows = []
    for season, g in pred.dropna(subset=["home_win"]).groupby("season"):
        y = g["home_win"].astype(float)
        m = g.dropna(subset=["market_home_prob"])
        ats3 = bt.ats_record(g, thresholds=(3.0,)).iloc[0]
        rows.append(
            {
                "season": int(season),
                "games": int(len(g)),
                "brier_model": round(bt.brier(y, g["p_home_win"]), 4),
                "brier_market": (
                    round(bt.brier(m["home_win"].astype(float), m["market_home_prob"]), 4)
                    if len(m)
                    else None
                ),
                "margin_mae": round(float((g["pred_margin"] - g["home_margin"]).abs().mean()), 2),
                "ats3_wins": int(ats3["wins"]),
                "ats3_bets": int(ats3["bets"]),
            }
        )
    for r in rows:
        r["gap"] = (
            round(r["brier_model"] - r["brier_market"], 4)
            if r["brier_market"] is not None
            else None
        )
    return rows


# ── records & log ────────────────────────────────────────────────────────────


def _py(v):
    """numpy/pandas scalars -> JSON-native."""
    if v is None:
        return None
    if isinstance(v, (np.floating, np.integer, np.bool_)):
        v = v.item()
    if isinstance(v, float) and (v != v):  # NaN
        return None
    return v


def _git_sha() -> str | None:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=5,
        )
        return out.stdout.strip() or None
    except Exception:
        return None


_METRIC_KEYS = (
    "n_games",
    "brier_model",
    "brier_market",
    "brier_home_always",
    "logloss_model",
    "logloss_market",
    "margin_mae_model",
    "margin_mae_spread",
    "calibration_gap",
    "mean_predicted",
    "actual_rate",
)


def to_record(result: ExperimentResult, source: str, shipped: dict | None = None) -> dict:
    h = result.holdout
    metrics = {k: _py(h.get(k)) for k in _METRIC_KEYS}
    ats3 = h["ats"][h["ats"]["threshold"] == 3.0]
    metrics["ats3_win_pct"] = _py(ats3["win_pct"].iloc[0]) if len(ats3) else None
    metrics["ats3_bets"] = _py(ats3["bets"].iloc[0]) if len(ats3) else None
    metrics["bonus_brier"] = _py(result.bonus["brier_model"]) if result.bonus else None
    metrics["bonus_brier_market"] = _py(result.bonus["brier_market"]) if result.bonus else None
    delta = None
    if shipped and shipped.get("brier_model") is not None:
        delta = {"brier": round(metrics["brier_model"] - shipped["brier_model"], 5)}
    cfg = asdict(result.config)
    cfg["features"] = list(cfg["features"])
    note = cfg.pop("note")
    return {
        "ts": datetime.now(UTC).isoformat(timespec="seconds"),
        "git_sha": _git_sha(),
        "source": source,
        "note": note,
        "config": cfg,
        "metrics": metrics,
        "delta_vs_shipped": delta,
        "seconds": round(result.seconds, 1),
    }


def append_log(record: dict, path: Path = EXPERIMENT_LOG) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, default=_py) + "\n")


def read_log(path: Path = EXPERIMENT_LOG, limit: int = 200) -> list[dict]:
    """Newest first. A corrupt line is skipped, never fatal."""
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return list(reversed(out))[:limit]


# ── scorecard ────────────────────────────────────────────────────────────────


def scorecard(result: ExperimentResult, shipped: dict | None = None) -> str:
    h = result.holdout
    lo, hi = HOLDOUT_SEASONS
    lines = [
        f"config   {result.config.describe()}",
        f"features {', '.join(result.config.features)}",
        f"holdout  {lo}-{hi}  ({h['n_games']} games, {result.seconds:.1f}s)",
        "",
        f"  {'':14} {'Brier':>8} {'LogLoss':>8} {'MAE':>6}",
        f"  {'model':14} {h['brier_model']:8.4f} {h['logloss_model']:8.4f} "
        f"{h['margin_mae_model']:6.2f}",
        f"  {'market':14} {h['brier_market']:8.4f} {h['logloss_market']:8.4f} "
        f"{h['margin_mae_spread']:6.2f}",
        f"  {'home-always':14} {h['brier_home_always']:8.4f}",
    ]
    if shipped and shipped.get("brier_model") is not None:
        d = h["brier_model"] - shipped["brier_model"]
        verdict = "better" if d < -1e-4 else ("worse" if d > 1e-4 else "same")
        lines.append(
            f"  {'shipped':14} {shipped['brier_model']:8.4f}   -> this run is {d:+.4f} ({verdict})"
        )
    gap = h.get("calibration_gap")
    lines += [
        "",
        f"calibration  mean predicted {h['mean_predicted']:.3f} vs actual "
        f"{h['actual_rate']:.3f}; mid-range gap "
        f"{gap:.4f}"
        if gap is not None
        else "calibration  n/a",
    ]
    ats3 = h["ats"][h["ats"]["threshold"] == 3.0]
    if len(ats3) and ats3["bets"].iloc[0]:
        r = ats3.iloc[0]
        lines.append(
            f"ATS 3+ pts   {int(r['wins'])}/{int(r['bets'])} = {r['win_pct']:.3f} (breakeven 0.524)"
        )
    if result.bonus:
        b = result.bonus
        lines.append(
            f"bonus {BONUS_SEASON}   Brier {b['brier_model']:.4f} vs market "
            f"{b['brier_market']:.4f} ({b['n_games']} games)"
        )
    return "\n".join(lines)


def with_note(cfg: ExperimentConfig, note: str) -> ExperimentConfig:
    return replace(cfg, note=note)
