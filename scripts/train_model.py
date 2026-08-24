"""Tune, walk-forward validate, gate, and persist the game model (v2).

Protocol (leak-free by construction):
  1. Hyperparameters (EWMA half-life/carryover; ridge half-life/alpha/
     carryover) tuned ONLY on walk-forward predictions of 2012-2018.
  2. Headline metrics reported on the untouched 2019-2024 holdout — ONE
     holdout evaluation per candidate configuration (2025 reported
     separately as a bonus out-of-sample season).
  3. Causality asserts recompute EVERY model input (EWMA ratings, ridge
     ratings, QB flags) on truncated history and verify entering values
     are identical for all earlier games.
  4. Gates decide what ships:
       step 1 (ridge ratings): holdout Brier <= 0.2224 AND margin MAE not
         worse than the EWMA baseline — else EWMA stays the shipped source.
       step 2 (QB flag): holdout Brier improves >= 0.0010 over the step-1
         shipped configuration — else the flag stays off the registry.
  5. Production fit of the gated-in configuration on all completed games;
     coefficients + current ratings persisted to DuckDB for serve-time
     prediction (no sklearn in the request path).

Run:  python scripts/train_model.py            (~4-6 min)
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
from nfl_analytics.model import qb_flag as qbf  # noqa: E402
from nfl_analytics.model import ratings_ridge as rr  # noqa: E402
from nfl_analytics.model.features import BASE_FEATURE_COLS, build_features  # noqa: E402
from nfl_analytics.model.ratings import compute_ratings  # noqa: E402

DB = ROOT / "nfl.duckdb"
REPORT = ROOT / "docs" / "model_report.md"

TUNE_SEASONS = (2012, 2018)
HOLDOUT_SEASONS = (2019, 2024)
EWMA_GRID = [(h, c) for h in (6.0, 8.0, 10.0, 12.0) for c in (0.4, 0.5, 0.6)]
RIDGE_GRID = [
    (h, a, c) for h in (6.0, 9.0, 12.0) for a in (3.0, 10.0, 30.0) for c in (0.5, 0.7, 0.9)
]
GATE1_BRIER = 0.2224  # step-1 absolute holdout gate
GATE2_IMPROVE = 0.0010  # step-2 required Brier improvement
CUTOFF = 2015  # causality-check truncation season
QB_COLS = BASE_FEATURE_COLS + ["d_qb_out"]


def causality_check(con, half_life, carryover) -> None:
    """EWMA ratings entering games before season S must be identical whether
    or not later data exists. Recompute on truncated history and compare."""
    full, _ = compute_ratings(con, half_life, carryover)
    truncated_rows = con.execute(
        "SELECT count(*) FROM play_by_play WHERE season < " + str(CUTOFF)
    ).fetchone()[0]
    assert truncated_rows > 0
    # recompute from a truncated frame by narrowing the SQL compute_ratings
    # runs — post-cutoff data must not affect earlier entering ratings
    import nfl_analytics.model.ratings as R

    orig_sql = R.GAME_EPA_SQL
    R.GAME_EPA_SQL = orig_sql.replace(
        "WHERE p.play_type", f"WHERE p.season < {CUTOFF} AND p.play_type"
    )
    try:
        trunc, _ = compute_ratings(con, half_life, carryover)
    finally:
        R.GAME_EPA_SQL = orig_sql
    key = ["game_id", "team"]
    m = full[full["season"] < CUTOFF].merge(trunc, on=key, suffixes=("_f", "_t"))
    for d in ("off_pass", "off_rush", "def_pass", "def_rush"):
        diff = (m[f"r_{d}_f"] - m[f"r_{d}_t"]).abs().max()
        assert diff < 1e-12, f"LEAKAGE: r_{d} differs by {diff} on pre-{CUTOFF} games"
    print(f"  EWMA causality check passed ({len(m):,} team-games, max diff < 1e-12)")


def ridge_causality_check(obs, per_game_full, half_life, alpha, carryover) -> None:
    """Same truncate-and-diff pattern for the ridge ratings input frame."""
    trunc, _ = rr.ridge_ratings(obs[obs["season"] < CUTOFF], half_life, alpha, carryover)
    m = per_game_full[per_game_full["season"] < CUTOFF].merge(
        trunc, on=["game_id", "team"], suffixes=("_f", "_t")
    )
    assert len(m) == len(trunc), "ridge truncation changed the pre-cutoff game set"
    for c in rr.RATING_COLS:
        diff = (m[f"{c}_f"] - m[f"{c}_t"]).abs().max()
        assert diff < 1e-9, f"LEAKAGE: ridge {c} differs by {diff} on pre-{CUTOFF} games"
    print(f"  ridge causality check passed ({len(m):,} team-games, max diff < 1e-9)")


def qb_causality_check(con, dropbacks, flags_full) -> None:
    """Same truncate-and-diff pattern for the QB-flag input frame."""
    trunc = qbf.qb_out_flags(con, dropbacks[dropbacks["season"] < CUTOFF])
    pre = flags_full[flags_full["game_id"].str[:4].astype(int) < CUTOFF]
    m = pre.merge(trunc, on=["game_id", "team"], suffixes=("_f", "_t"))
    assert len(m) == len(pre) == len(trunc), "qb-flag truncation changed the game set"
    bad = int((m["qb_out_f"] != m["qb_out_t"]).sum())
    assert bad == 0, f"LEAKAGE: {bad} qb_out flags differ on pre-{CUTOFF} games"
    print(f"  qb-flag causality check passed ({len(m):,} team-games, 0 diffs)")


def tune_ll(pred: pd.DataFrame) -> float:
    """Walk-forward log loss on the tuning window (2012-2018)."""
    t = pred[(pred["season"] >= TUNE_SEASONS[0]) & (pred["season"] <= TUNE_SEASONS[1])]
    return bt.log_loss_(t["home_win"].astype(float), t["p_home_win"])


def main() -> int:
    t0 = time.time()
    con = duckdb.connect(str(DB), read_only=True)

    # QB availability flags (step 2 input; harmless extra column otherwise)
    dropbacks = con.execute(qbf.DROPBACKS_SQL).fetchdf()
    qb_flags = qbf.qb_out_flags(con, dropbacks)

    print("Tuning EWMA on walk-forward 2012-2018 log loss:")
    ewma_results = []
    feats_cache = {}
    for h, c in EWMA_GRID:
        pg, _ = compute_ratings(con, h, c)
        df = build_features(con, pg, qb_flags)
        feats_cache[(h, c)] = df
        pred = bt.walk_forward(df, *TUNE_SEASONS, feature_cols=BASE_FEATURE_COLS)
        ll = bt.log_loss_(pred["home_win"].astype(float), pred["p_home_win"])
        ewma_results.append({"half_life": h, "carryover": c, "logloss": ll})
        print(f"  h={h:4.0f} c={c:.1f}  logloss={ll:.5f}")
    best_e = min(ewma_results, key=lambda r: r["logloss"])
    eh, ec = best_e["half_life"], best_e["carryover"]
    print(f"Best EWMA: half_life={eh}, carryover={ec}")

    print("Tuning ridge on walk-forward 2012-2018 log loss:")
    obs = rr.load_observations(con)
    obs_tune = obs[obs["season"] <= TUNE_SEASONS[1]]
    ridge_results = []
    for i, (rh, ra, rc) in enumerate(RIDGE_GRID):
        pg, _ = rr.ridge_ratings(obs_tune, rh, ra, rc)
        df = build_features(con, pg, qb_flags)
        pred = bt.walk_forward(df, *TUNE_SEASONS, feature_cols=BASE_FEATURE_COLS)
        ll = bt.log_loss_(pred["home_win"].astype(float), pred["p_home_win"])
        ridge_results.append({"half_life": rh, "alpha": ra, "carryover": rc, "logloss": ll})
        print(
            f"  [{i + 1:2d}/{len(RIDGE_GRID)}] h={rh:4.0f} a={ra:5.0f} c={rc:.1f}  logloss={ll:.5f}"
        )
    best_r = min(ridge_results, key=lambda r: r["logloss"])
    rh, ra, rc = best_r["half_life"], best_r["alpha"], best_r["carryover"]
    print(f"Best ridge: half_life={rh}, alpha={ra}, carryover={rc}")

    print("Causality checks (truncate inputs at a cutoff, diff entering values):")
    causality_check(con, eh, ec)
    pg_ridge, cur_ridge = rr.ridge_ratings(obs, rh, ra, rc)
    ridge_causality_check(obs, pg_ridge, rh, ra, rc)
    qb_causality_check(con, dropbacks, qb_flags)

    # ---- ONE holdout evaluation per configuration ----
    df_ewma = feats_cache[(eh, ec)]
    pred_ewma = bt.walk_forward(df_ewma, TUNE_SEASONS[0], 2025, feature_cols=BASE_FEATURE_COLS)
    s_ewma = bt.summarize(pred_ewma, *HOLDOUT_SEASONS)

    df_ridge = build_features(con, pg_ridge, qb_flags)
    pred_ridge = bt.walk_forward(df_ridge, TUNE_SEASONS[0], 2025, feature_cols=BASE_FEATURE_COLS)
    s_ridge = bt.summarize(pred_ridge, *HOLDOUT_SEASONS)

    gate1 = (
        s_ridge["brier_model"] <= GATE1_BRIER
        and s_ridge["margin_mae_model"] <= s_ewma["margin_mae_model"]
    )
    print(
        f"Step 1 gate (Brier <= {GATE1_BRIER:.4f} and margin MAE <= baseline): "
        f"ridge Brier {s_ridge['brier_model']:.4f} vs EWMA {s_ewma['brier_model']:.4f}, "
        f"MAE {s_ridge['margin_mae_model']:.2f} vs {s_ewma['margin_mae_model']:.2f} "
        f"-> {'SHIP ridge' if gate1 else 'keep EWMA'}"
    )
    if gate1:
        source = "ridge"
        df_ship, pred_ship, s_ship = df_ridge, pred_ridge, s_ridge
        _, cur_ship = pg_ridge, cur_ridge
        src_hp = {"half_life": rh, "carryover": rc, "ridge_alpha": ra}
    else:
        source = "ewma"
        df_ship, pred_ship, s_ship = df_ewma, pred_ewma, s_ewma
        _, cur_ship = compute_ratings(con, eh, ec)
        src_hp = {"half_life": eh, "carryover": ec, "ridge_alpha": None}

    # ---- step 2: QB flag on top of the step-1 shipped source ----
    pred_qb = bt.walk_forward(df_ship, TUNE_SEASONS[0], 2025, feature_cols=QB_COLS)
    s_qb = bt.summarize(pred_qb, *HOLDOUT_SEASONS)
    gate2 = (s_ship["brier_model"] - s_qb["brier_model"]) >= GATE2_IMPROVE

    def _qb_subset_brier(pred):
        hq = pred[
            (pred["season"] >= HOLDOUT_SEASONS[0])
            & (pred["season"] <= HOLDOUT_SEASONS[1])
            & (pred["d_qb_out"] != 0)
        ]
        return bt.brier(hq["home_win"].astype(float), hq["p_home_win"]), len(hq)

    qb_sub_without, n_qb = _qb_subset_brier(pred_ship)
    qb_sub_with, _ = _qb_subset_brier(pred_qb)
    print(
        f"Step 2 gate (holdout Brier -{GATE2_IMPROVE:.4f}): {source}+qb "
        f"{s_qb['brier_model']:.4f} vs {s_ship['brier_model']:.4f} "
        f"-> {'SHIP qb flag' if gate2 else 'no-ship'}; d_qb_out!=0 subset "
        f"({n_qb} games): {qb_sub_with:.4f} with vs {qb_sub_without:.4f} without"
    )

    if gate2:
        ship_cols, pred_final, s_final = QB_COLS, pred_qb, s_qb
    else:
        ship_cols, pred_final, s_final = list(BASE_FEATURE_COLS), pred_ship, s_ship
    s25 = bt.summarize(pred_final, 2025, 2025)

    # ---- production fit of the gated-in configuration only ----
    done = df_ship.dropna(subset=["home_win"])
    clf = LogisticRegression(C=1.0, max_iter=1000)
    clf.fit(done[ship_cols], done["home_win"].astype(int))
    reg = Ridge(alpha=1.0)
    reg.fit(done[ship_cols], done["home_margin"])
    current = cur_ship  # noqa: F841 — read by duckdb replacement scan below
    con.close()

    wcon = duckdb.connect(str(DB))
    wcon.execute("CREATE OR REPLACE TABLE model_ratings AS SELECT * FROM current")
    params = pd.DataFrame(  # noqa: F841 — read by duckdb replacement scan below
        [
            {
                "fitted_at": pd.Timestamp.now().isoformat(),
                "ratings_source": source,
                "half_life": src_hp["half_life"],
                "carryover": src_hp["carryover"],
                "ridge_alpha": src_hp["ridge_alpha"],
                "qb_flag": gate2,
                "feature_cols": json.dumps(ship_cols),
                "win_intercept": float(clf.intercept_[0]),
                "win_coefs": json.dumps(clf.coef_[0].tolist()),
                "margin_intercept": float(reg.intercept_),
                "margin_coefs": json.dumps(reg.coef_.tolist()),
                "train_games": len(done),
                "holdout_brier": s_final["brier_model"],
                "holdout_logloss": s_final["logloss_model"],
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
    mp = pred_final[keep]  # noqa: F841 — read by duckdb replacement scan below
    wcon.execute("CREATE OR REPLACE TABLE model_predictions AS SELECT * FROM mp")
    wcon.close()

    # ---- report ----
    s = s_final
    ship_desc = f"{source} ratings" + (" + QB flag" if gate2 else "")
    comparison = pd.DataFrame(
        [
            {
                "config": f"EWMA baseline (h={eh:.0f}, c={ec:.1f})",
                "tune_logloss": tune_ll(pred_ewma),
                "holdout_brier": s_ewma["brier_model"],
                "holdout_margin_mae": s_ewma["margin_mae_model"],
                "vs_market_gap": s_ewma["brier_model_on_market_games"] - s_ewma["brier_market"],
                "ship": "SHIP" if (source == "ewma" and not gate2) else "no",
            },
            {
                "config": f"Ridge (h={rh:.0f}, a={ra:.0f}, c={rc:.1f})",
                "tune_logloss": tune_ll(pred_ridge),
                "holdout_brier": s_ridge["brier_model"],
                "holdout_margin_mae": s_ridge["margin_mae_model"],
                "vs_market_gap": s_ridge["brier_model_on_market_games"] - s_ridge["brier_market"],
                "ship": "SHIP"
                if (source == "ridge" and not gate2)
                else ("no" if not gate1 else "base for qb"),
            },
            {
                "config": f"{source} + QB flag",
                "tune_logloss": tune_ll(pred_qb),
                "holdout_brier": s_qb["brier_model"],
                "holdout_margin_mae": s_qb["margin_mae_model"],
                "vs_market_gap": s_qb["brier_model_on_market_games"] - s_qb["brier_market"],
                "ship": "SHIP" if gate2 else "no",
            },
        ]
    )
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
    hp_desc = (
        f"decayed ridge (half-life **{src_hp['half_life']:.0f}** games, alpha "
        f"**{src_hp['ridge_alpha']:.0f}**, season carryover **{src_hp['carryover']:.1f}**)"
        if source == "ridge"
        else f"EWMA (half-life **{src_hp['half_life']:.0f}** games, season "
        f"carryover **{src_hp['carryover']:.1f}**)"
    )
    REPORT.write_text(
        f"""# Model Report (v2)

Fitted {pd.Timestamp.now():%Y-%m-%d %H:%M}. Shipped configuration: **{ship_desc}** —
opponent-adjusted EPA ratings via {hp_desc} -> logistic win prob + ridge margin{
            " + causal QB-availability flag (expected starter Out/Doubtful/reserve)"
            if gate2
            else ""
        }.
Walk-forward by season; hyperparams tuned on 2012-2018 only; **2019-2024 is
the untouched holdout**; 2025 reported as bonus. Causality asserts cover every
input: EWMA ratings, ridge ratings, and QB flags are recomputed on truncated
history and diffed.

## Configuration comparison (one holdout evaluation each)

{comparison.to_markdown(index=False, floatfmt=".4f")}

Gates: step 1 ships ridge only if holdout Brier <= {GATE1_BRIER:.4f} AND margin MAE
is not worse than the EWMA baseline ({"passed" if gate1 else "failed"}). Step 2 ships the
QB flag only if it improves holdout Brier by >= {GATE2_IMPROVE:.4f} over the step-1
result ({"passed" if gate2 else "failed"}). Only the gated-in configuration is persisted.

On the {n_qb} holdout games where d_qb_out != 0, Brier is {qb_sub_with:.4f} with
the flag vs {qb_sub_without:.4f} without.

## Holdout 2019-2024 ({s["n_games"]} games, {s["n_with_market"]} with moneylines)

| Metric | Model | Market (devigged ML) | Home-always |
|---|---|---|---|
| Brier | {s["brier_model_on_market_games"]:.4f} | {s["brier_market"]:.4f} | {
            s["brier_home_always"]:.4f} |
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

## Tuning grid — EWMA (2012-2018 walk-forward log loss)

{pd.DataFrame(ewma_results).to_markdown(index=False, floatfmt=".5f")}

## Tuning grid — decayed ridge (2012-2018 walk-forward log loss)

{pd.DataFrame(ridge_results).to_markdown(index=False, floatfmt=".5f")}
""",
        encoding="utf-8",
    )
    print(f"\nReport: {REPORT}  ({time.time() - t0:.0f}s total)")
    print(verdict)
    return 0


if __name__ == "__main__":
    sys.exit(main())
