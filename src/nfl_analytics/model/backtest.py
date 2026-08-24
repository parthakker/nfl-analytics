"""Walk-forward evaluation and honest metrics for the baseline model."""

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression, Ridge

from .features import FEATURE_COLS


def walk_forward(
    df: pd.DataFrame,
    first_target: int = 2012,
    last_target: int | None = None,
    feature_cols: list[str] | None = None,
) -> pd.DataFrame:
    """Fit on all seasons < s, predict season s, for each target season.
    Returns df restricted to predicted rows with p_home_win / pred_margin."""
    cols = feature_cols if feature_cols is not None else FEATURE_COLS
    df = df.dropna(subset=["home_win"]).copy()
    last_target = last_target or int(df["season"].max())
    out = []
    for s in range(first_target, last_target + 1):
        train = df[df["season"] < s]
        test = df[df["season"] == s].copy()
        if train.empty or test.empty:
            continue
        clf = LogisticRegression(C=1.0, max_iter=1000)
        clf.fit(train[cols], train["home_win"].astype(int))
        test["p_home_win"] = clf.predict_proba(test[cols])[:, 1]
        reg = Ridge(alpha=1.0)
        reg.fit(train[cols], train["home_margin"])
        test["pred_margin"] = reg.predict(test[cols])
        out.append(test)
    return pd.concat(out, ignore_index=True)


def brier(y, p) -> float:
    return float(np.mean((np.asarray(p) - np.asarray(y)) ** 2))


def log_loss_(y, p) -> float:
    p = np.clip(np.asarray(p, dtype=float), 1e-6, 1 - 1e-6)
    y = np.asarray(y, dtype=float)
    return float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))


def calibration_table(y, p, bins: int = 10) -> pd.DataFrame:
    d = pd.DataFrame({"y": np.asarray(y, dtype=float), "p": np.asarray(p, dtype=float)})
    d["bin"] = np.clip((d["p"] * bins).astype(int), 0, bins - 1)
    t = (
        d.groupby("bin")
        .agg(n=("y", "size"), predicted=("p", "mean"), actual=("y", "mean"))
        .reset_index()
    )
    t["gap"] = t["actual"] - t["predicted"]
    return t


def ats_record(df: pd.DataFrame, thresholds=(0.5, 1.0, 2.0, 3.0)) -> pd.DataFrame:
    """Against-the-spread record where model disagrees with the closing line
    by >= t points. Bet home when pred_margin > spread_line; win if actual
    margin beats the spread on the chosen side. Pushes excluded."""
    d = df.dropna(subset=["spread_line", "pred_margin", "home_margin"]).copy()
    rows = []
    for t in thresholds:
        bets = d[(d["pred_margin"] - d["spread_line"]).abs() >= t].copy()
        bets = bets[bets["home_margin"] != bets["spread_line"]]  # drop pushes
        bet_home = bets["pred_margin"] > bets["spread_line"]
        home_covers = bets["home_margin"] > bets["spread_line"]
        wins = int((bet_home == home_covers).sum())
        n = len(bets)
        rows.append(
            {
                "threshold": t,
                "bets": n,
                "wins": wins,
                "win_pct": round(wins / n, 4) if n else None,
                "breakeven": 0.524,
                "profitable": (wins / n > 0.524) if n else None,
            }
        )
    return pd.DataFrame(rows)


def summarize(pred: pd.DataFrame, holdout_start: int, holdout_end: int) -> dict:
    """Headline metrics on the untouched holdout, vs baselines."""
    h = pred[(pred["season"] >= holdout_start) & (pred["season"] <= holdout_end)]
    h = h.dropna(subset=["home_win"])
    y = h["home_win"].astype(float)
    core = h.dropna(subset=["market_home_prob"])
    yc = core["home_win"].astype(float)
    return {
        "n_games": len(h),
        "n_with_market": len(core),
        "brier_model": brier(y, h["p_home_win"]),
        "brier_market": brier(yc, core["market_home_prob"]),
        "brier_model_on_market_games": brier(yc, core["p_home_win"]),
        "brier_home_always": brier(y, np.full(len(h), y.mean())),
        "logloss_model": log_loss_(y, h["p_home_win"]),
        "logloss_market": log_loss_(yc, core["market_home_prob"]),
        "margin_mae_model": float((h["pred_margin"] - h["home_margin"]).abs().mean()),
        "margin_mae_spread": float(
            (
                h.dropna(subset=["spread_line"])["spread_line"]
                - h.dropna(subset=["spread_line"])["home_margin"]
            )
            .abs()
            .mean()
        ),
        "calibration": calibration_table(y, h["p_home_win"]),
        "ats": ats_record(h),
        "ats_late_season": ats_record(h[h["week"] >= 4]),
    }
