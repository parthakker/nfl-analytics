"""Drift controls on walk_forward: recency weighting + Platt recalibration.

Both default OFF; these pin the mechanics so a future retrain cannot enable
them by accident or silently change what the defaults mean.
"""

import numpy as np
import pandas as pd
import pytest

from nfl_analytics.model import backtest as bt
from nfl_analytics.model.features import FEATURE_COLS


def frame(seasons=range(2000, 2026), per_season=40, home_edge_recent=0.0, seed=0):
    """Synthetic games: one informative feature plus a home-field level that
    can be made to shift partway through, which is the real-world failure."""
    rng = np.random.default_rng(seed)
    rows = []
    for s in seasons:
        for i in range(per_season):
            strength = rng.normal()
            edge = home_edge_recent if s >= 2019 else 1.0
            p = 1 / (1 + np.exp(-(0.8 * strength + edge)))
            rows.append(
                {
                    "game_id": f"{s}_{i}",
                    "season": s,
                    "week": (i % 17) + 1,
                    "home_win": int(rng.random() < p),
                    "home_margin": 3 * strength + 3 * edge + rng.normal(0, 10),
                    "d_off_pass": strength,
                    **{c: 0.0 for c in FEATURE_COLS if c != "d_off_pass"},
                }
            )
    return pd.DataFrame(rows)


def test_defaults_are_unweighted_and_uncalibrated():
    df = frame()
    a = bt.walk_forward(df, 2020, 2022)
    b = bt.walk_forward(df, 2020, 2022, recency_half_life=None, calibration_window=None)
    pd.testing.assert_series_equal(a["p_home_win"], b["p_home_win"])


def test_season_weights_favour_recent_rows_and_keep_total_mass():
    seasons = np.array([2015, 2019, 2020])
    w = bt._season_weights(seasons, 2021, half_life=2.0)
    assert w[2] > w[1] > w[0]
    assert w.sum() == pytest.approx(len(seasons))
    assert bt._season_weights(seasons, 2021, None) is None


def test_recency_weighting_tracks_a_home_field_regime_shift():
    # home edge vanishes in 2019; an unweighted fit keeps averaging in the
    # pre-2019 seasons and should overstate the home team by more
    df = frame(home_edge_recent=0.0)
    plain = bt.walk_forward(df, 2021, 2025)
    recent = bt.walk_forward(df, 2021, 2025, recency_half_life=3.0)
    actual = plain["home_win"].mean()
    assert abs(recent["p_home_win"].mean() - actual) < abs(plain["p_home_win"].mean() - actual)


def test_platt_layer_shrinks_the_calibration_gap():
    # per_season is large enough that the warm-up window clears
    # MIN_CALIBRATION_GAMES — below it the layer deliberately passes through
    df = frame(home_edge_recent=0.0, per_season=80)
    plain = bt.walk_forward(df, 2021, 2025)
    cald = bt.walk_forward(df, 2021, 2025, calibration_window=4)
    gap = lambda p: bt.mid_range_gap(  # noqa: E731
        bt.calibration_table(p["home_win"].astype(float), p["p_home_win"])
    )
    assert gap(cald) < gap(plain)


def test_thin_history_passes_through_instead_of_fitting_noise():
    df = frame(per_season=20)  # 4 warm-up seasons = 80 games < MIN_CALIBRATION_GAMES
    plain = bt.walk_forward(df, 2021, 2021)
    cald = bt.walk_forward(df, 2021, 2021, calibration_window=4)
    pd.testing.assert_series_equal(plain["p_home_win"], cald["p_home_win"])


def test_calibration_warmup_does_not_leak_extra_seasons_into_output():
    df = frame()
    out = bt.walk_forward(df, 2021, 2023, calibration_window=3)
    assert set(out["season"]) == {2021, 2022, 2023}


def test_mid_range_gap_ignores_the_thin_tails():
    cal = pd.DataFrame(
        {
            "predicted": [0.05, 0.50, 0.95],
            "actual": [0.90, 0.50, 0.10],  # huge tail errors, perfect middle
            "n": [2, 500, 2],
        }
    )
    cal["gap"] = cal["actual"] - cal["predicted"]
    assert bt.mid_range_gap(cal) == pytest.approx(0.0)
    assert bt.mid_range_gap(cal.iloc[[0]]) is None
