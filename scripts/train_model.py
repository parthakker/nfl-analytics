"""Tune, walk-forward validate, and persist the baseline game model.

Protocol (leak-free by construction):
  1. Hyperparameters (EWMA half-life, season carryover) tuned ONLY on
     walk-forward predictions of 2012-2018.
  2. Headline metrics reported on the untouched 2019-2024 holdout
     (2025 reported separately as a bonus out-of-sample season).
  3. A causality assert recomputes ratings on truncated history and
     verifies entering ratings are identical for all earlier games.
  4. Production fit on all completed games; coefficients + current
     ratings persisted to DuckDB for serve-time prediction (no sklearn
     in the request path).

Run:  python scripts/train_model.py            (~3-5 min)
"""

import json
import sys
import time
from pathlib import Path

import duckdb
import pandas as pd
from sklearn.linear_model import LogisticRegression, Ridge

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from nfl_analytics.model import backtest as bt  # noqa: E402
from nfl_analytics.model.features import FEATURE_COLS, build_features  # noqa: E402
from nfl_analytics.model.ratings import compute_ratings  # noqa: E402

DB = ROOT / "nfl.duckdb"
REPORT = ROOT / "docs" / "model_report.md"

TUNE_SEASONS = (2012, 2018)
HOLDOUT_SEASONS = (2019, 2024)
GRID = [(h, c) for h in (6.0, 8.0, 10.0, 12.0) for c in (0.4, 0.5, 0.6)]


def causality_check(con, half_life, carryover) -> None:
    """Ratings entering games before season S must be identical whether or
    not later data exists. Recompute on truncated history and compare."""
    full, _ = compute_ratings(con, half_life, carryover)
    cutoff = 2015
    truncated_rows = con.execute(
        "SELECT count(*) FROM play_by_play WHERE season < " + str(cutoff)
    ).fetchone()[0]
    assert truncated_rows > 0
    # recompute from a truncated frame by narrowing the SQL compute_ratings
    # runs — post-cutoff data must not affect earlier entering ratings
    import nfl_analytics.model.ratings as R

    orig_sql = R.GAME_EPA_SQL
    R.GAME_EPA_SQL = orig_sql.replace(
        "WHERE p.play_type", f"WHERE p.season < {cutoff} AND p.play_type"
    )
    try:
        trunc, _ = compute_ratings(con, half_life, carryover)
    finally:
        R.GAME_EPA_SQL = orig_sql
    key = ["game_id", "team"]
    m = full[full["season"] < cutoff].merge(trunc, on=key, suffixes=("_f", "_t"))
    for d in ("off_pass", "off_rush", "def_pass", "def_rush"):
        diff = (m[f"r_{d}_f"] - m[f"r_{d}_t"]).abs().max()
        assert diff < 1e-12, f"LEAKAGE: r_{d} differs by {diff} on pre-{cutoff} games"
    print(f"  causality check passed ({len(m):,} team-games, max diff < 1e-12)")


def main() -> int:
    t0 = time.time()
    con = duckdb.connect(str(DB), read_only=True)

    print("Tuning on walk-forward 2012-2018 log loss:")
    results = []
    feats_cache = {}
    for h, c in GRID:
        pg, _ = compute_ratings(con, h, c)
        df = build_features(con, pg)
        feats_cache[(h, c)] = df
        pred = bt.walk_forward(df, TUNE_SEASONS[0], TUNE_SEASONS[1])
        ll = bt.log_loss_(pred["home_win"].astype(float), pred["p_home_win"])
        results.append({"half_life": h, "carryover": c, "logloss": ll})
        print(f"  h={h:4.0f} c={c:.1f}  logloss={ll:.5f}")
    best = min(results, key=lambda r: r["logloss"])
    h, c = best["half_life"], best["carryover"]
    print(f"Best: half_life={h}, carryover={c}")

    causality_check(con, h, c)

    df = feats_cache[(h, c)]
    pred = bt.walk_forward(df, TUNE_SEASONS[0], 2025)
    s = bt.summarize(pred, *HOLDOUT_SEASONS)
    s25 = bt.summarize(pred, 2025, 2025)

    # production fit on all completed games + current ratings
    done = df.dropna(subset=["home_win"])
    clf = LogisticRegression(C=1.0, max_iter=1000)
    clf.fit(done[FEATURE_COLS], done["home_win"].astype(int))
    reg = Ridge(alpha=1.0)
    reg.fit(done[FEATURE_COLS], done["home_margin"])
    pg, current = compute_ratings(con, h, c)
    con.close()

    wcon = duckdb.connect(str(DB))
    wcon.execute("CREATE OR REPLACE TABLE model_ratings AS SELECT * FROM current")
    params = pd.DataFrame(  # noqa: F841 — read by duckdb replacement scan below
        [
            {
                "fitted_at": pd.Timestamp.now().isoformat(),
                "half_life": h,
                "carryover": c,
                "feature_cols": json.dumps(FEATURE_COLS),
                "win_intercept": float(clf.intercept_[0]),
                "win_coefs": json.dumps(clf.coef_[0].tolist()),
                "margin_intercept": float(reg.intercept_),
                "margin_coefs": json.dumps(reg.coef_.tolist()),
                "train_games": len(done),
                "holdout_brier": s["brier_model"],
                "holdout_logloss": s["logloss_model"],
            }
        ]
    )
    wcon.execute("CREATE OR REPLACE TABLE model_params AS SELECT * FROM params")
    keep = [
        "game_id",
        "season",
        "week",
        "home_team",
        "away_team",
        "home_win",
        "home_margin",
        "spread_line",
        "market_home_prob",
        "p_home_win",
        "pred_margin",
    ]
    mp = pred[keep]  # noqa: F841 — read by duckdb replacement scan below
    wcon.execute("CREATE OR REPLACE TABLE model_predictions AS SELECT * FROM mp")
    wcon.close()

    # report
    cal = s["calibration"].to_markdown(index=False, floatfmt=".3f")
    ats = s["ats"].to_markdown(index=False)
    ats4 = s["ats_late_season"].to_markdown(index=False)
    verdict = (
        "**Verdict:** the market is better than this model, as expected. "
        f"Holdout Brier: market {s['brier_market']:.4f} vs model "
        f"{s['brier_model_on_market_games']:.4f}. Treat the model as a "
        "calibrated yardstick, not an oracle: a Kalshi price is interesting "
        "only when it disagrees with the model by MORE than the model's "
        "typical error vs the market, and after fees/spread."
        if s["brier_market"] <= s["brier_model_on_market_games"]
        else "**Verdict:** model beat the market Brier on this holdout — treat "
        "with suspicion, verify for leakage before believing it."
    )
    REPORT.write_text(
        f"""# Baseline Model Report

Fitted {pd.Timestamp.now():%Y-%m-%d %H:%M}. EWMA opponent-adjusted EPA ratings
(half-life **{h:.0f}** games, season carryover **{c:.1f}**) -> logistic win
prob + ridge margin. Walk-forward by season; hyperparams tuned on 2012-2018
only; **2019-2024 is the untouched holdout**; 2025 reported as bonus.

## Holdout 2019-2024 ({s["n_games"]} games, {s["n_with_market"]} with moneylines)

| Metric | Model | Market (devigged ML) | Home-always |
|---|---|---|---|
| Brier | {s["brier_model_on_market_games"]:.4f} | {s["brier_market"]:.4f} | {s["brier_home_always"]:.4f} |
| Log loss | {s["logloss_model"]:.4f} | {s["logloss_market"]:.4f} | — |
| Margin MAE | {s["margin_mae_model"]:.2f} | {s["margin_mae_spread"]:.2f} (closing spread) | — |

{verdict}

## Calibration (holdout)

{cal}

## ATS vs closing spread (holdout, by disagreement threshold)

{ats}

Weeks 4+ only (early-season ratings are noisy):

{ats4}

## 2025 out-of-sample (never touched during tuning)

Brier {s25["brier_model_on_market_games"]:.4f} vs market {s25["brier_market"]:.4f}
({s25["n_games"]} games). Margin MAE {s25["margin_mae_model"]:.2f} vs spread
{s25["margin_mae_spread"]:.2f}.

## Tuning grid (2012-2018 walk-forward log loss)

{pd.DataFrame(results).to_markdown(index=False, floatfmt=".5f")}
""",
        encoding="utf-8",
    )
    print(f"\nReport: {REPORT}  ({time.time() - t0:.0f}s total)")
    print(verdict)
    return 0


if __name__ == "__main__":
    sys.exit(main())
