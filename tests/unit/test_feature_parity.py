"""Train/serve parity: the feature arithmetic in build_features (training)
and predict_game (serving) must be the same function of the same inputs —
especially the defense sign flip, which is the easiest thing to get wrong.
An in-memory DuckDB stands in for the warehouse."""

import json

import duckdb
import numpy as np
import pandas as pd
import pytest
from sklearn.linear_model import LogisticRegression, Ridge

from nfl_analytics.model import predict as pr
from nfl_analytics.model.features import (
    FEATURE_COLS,
    build_features,
    feature_row,
    rest_clip,
)

HOME = {"r_off_pass": 0.12, "r_off_rush": -0.02, "r_def_pass": -0.06, "r_def_rush": 0.01}
AWAY = {"r_off_pass": 0.03, "r_off_rush": 0.05, "r_def_pass": 0.04, "r_def_rush": -0.03}


def _warehouse():
    """games + v_team_games + schedules for ONE game, as tables."""
    con = duckdb.connect()
    con.execute("""
        CREATE TABLE games AS SELECT
            '2024_05_AAA_HHH' AS game_id, 2024 AS season, 5 AS week, 'REG' AS season_type,
            'HHH' AS home_team, 'AAA' AS away_team, 27 AS home_score, 20 AS away_score,
            1 AS div_game, 3.5 AS spread_line
    """)
    con.execute("""
        CREATE TABLE v_team_games AS
        SELECT '2024_05_AAA_HHH' AS game_id, 'HHH' AS team, 10 AS rest_days,
               9 AS rest_days_sched, 0.0 AS tz_shift_hours, true AS is_home
        UNION ALL
        SELECT '2024_05_AAA_HHH', 'AAA', 6, 6, 2.0, false
    """)
    con.execute("""
        CREATE TABLE schedules AS SELECT '2024_05_AAA_HHH' AS game_id,
               -150 AS home_moneyline, 130 AS away_moneyline
    """)
    return con


def _per_game():
    return pd.DataFrame(
        [
            {"game_id": "2024_05_AAA_HHH", "team": "HHH", **HOME},
            {"game_id": "2024_05_AAA_HHH", "team": "AAA", **AWAY},
        ]
    )


def _flags():
    return pd.DataFrame(
        [
            {"game_id": "2024_05_AAA_HHH", "team": "HHH", "qb_out": 0},
            {"game_id": "2024_05_AAA_HHH", "team": "AAA", "qb_out": 1},
        ]
    )


def test_build_features_equals_feature_row_on_every_feature():
    df = build_features(_warehouse(), _per_game(), _flags())
    assert len(df) == 1
    trained = df.iloc[0]
    served = feature_row(
        HOME,
        AWAY,
        rest_diff=rest_clip(10) - rest_clip(6),
        away_tz_shift=2.0,
        div_game=1,
        d_qb_out=0 - 1,
        rest_diff_sched=rest_clip(9) - rest_clip(6),
    )
    for c in FEATURE_COLS + ["d_rest_sched"]:
        assert trained[c] == pytest.approx(served[c]), c
    assert trained["d_rest"] == 4 and trained["d_rest_sched"] == 3
    assert feature_row(HOME, AWAY, rest_diff=2.0)["d_rest_sched"] == 2.0


def test_defense_sign_flip_puts_better_home_defense_positive():
    # home allows -0.06 EPA/play (good), away allows +0.04 (bad)
    row = feature_row(HOME, AWAY)
    assert row["d_def_pass"] == pytest.approx(0.04 - (-0.06))
    assert row["d_def_pass"] > 0
    assert row["d_def_rush"] == pytest.approx(-0.03 - 0.01)
    assert row["d_def_rush"] < 0
    assert row["d_off_pass"] == pytest.approx(0.12 - 0.03)


def test_rest_clip_matches_training_fillna_and_clip():
    assert rest_clip(None) == 7 and rest_clip(float("nan")) == 7
    assert rest_clip(1) == 3 and rest_clip(20) == 14 and rest_clip(9) == 9


def test_predict_game_reproduces_sklearn_from_persisted_coefs():
    """Fit on synthetic rows, persist the coefficients the way train_model
    does, and check the sklearn-free serve path lands on the same number."""
    rng = np.random.default_rng(0)
    n = 400
    X = pd.DataFrame(rng.normal(size=(n, len(FEATURE_COLS))), columns=FEATURE_COLS)
    y = (X["d_off_pass"] * 2 + rng.normal(size=n) > 0).astype(int)
    m = 6 * X["d_off_pass"] + rng.normal(scale=8, size=n)
    clf = LogisticRegression(C=1.0, max_iter=1000).fit(X, y)
    reg = Ridge(alpha=1.0).fit(X, m)

    con = duckdb.connect()
    con.execute("CREATE MACRO canon_team(t) AS t")
    params = pd.DataFrame(  # noqa: F841 — duckdb replacement scan
        [
            {
                "fitted_at": "test",
                "ratings_source": "ewma",
                "half_life": 8.0,
                "carryover": 0.6,
                "qb_flag": True,
                "feature_cols": json.dumps(FEATURE_COLS),
                "win_intercept": float(clf.intercept_[0]),
                "win_coefs": json.dumps(clf.coef_[0].tolist()),
                "margin_intercept": float(reg.intercept_),
                "margin_coefs": json.dumps(reg.coef_.tolist()),
                "holdout_brier": 0.22,
            }
        ]
    )
    con.execute("CREATE TABLE model_params AS SELECT * FROM params")
    ratings = pd.DataFrame(  # noqa: F841
        [{"team": "HHH", **HOME}, {"team": "AAA", **AWAY}]
    )
    con.execute("CREATE TABLE model_ratings AS SELECT * FROM ratings")

    out = pr.predict_game(
        con, "HHH", "AAA", rest_diff=4.0, away_tz_shift=2.0, div_game=1, d_qb_out=-1.0
    )
    x = pd.DataFrame([[out["inputs"][c] for c in FEATURE_COLS]], columns=FEATURE_COLS)
    assert out["p_home_win"] == pytest.approx(clf.predict_proba(x)[0, 1], abs=1e-9)
    assert out["pred_margin"] == pytest.approx(reg.predict(x)[0], abs=1e-9)

    # contributions are an exact decomposition of the prediction
    z = out["intercept"]["logit"] + sum(r["logit"] for r in out["contributions"])
    assert 1 / (1 + np.exp(-z)) == pytest.approx(out["p_home_win"], abs=1e-12)
    pts = out["intercept"]["margin_pts"] + sum(r["margin_pts"] for r in out["contributions"])
    assert pts == pytest.approx(out["pred_margin"], abs=1e-12)
    assert [r["feature"] for r in out["contributions"]] == FEATURE_COLS
    assert all(r["label"] for r in out["contributions"])
