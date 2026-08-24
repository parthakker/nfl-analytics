"""Decayed ridge ratings on a tiny synthetic 3-team season: causality
(future games must not move earlier entering ratings) and sign sanity
(good offense rates above bad offense). No DB — pure frames."""

import numpy as np
import pandas as pd
import pytest

from nfl_analytics.model.ratings_ridge import RATING_COLS, ridge_ratings

# rotating schedule, one game per week; A = strong offense, B = weak
SCHEDULE = [  # (week, home, away)
    (1, "AAA", "BBB"),
    (2, "BBB", "CCC"),
    (3, "CCC", "AAA"),
    (4, "AAA", "BBB"),
    (5, "BBB", "CCC"),
    (6, "CCC", "AAA"),
]
OFF_EPA = {"AAA": 0.30, "BBB": -0.30, "CCC": 0.00}


def synthetic_obs(max_week: int = 6) -> pd.DataFrame:
    rows = []
    for week, home, away in SCHEDULE:
        if week > max_week:
            continue
        gid = f"2023_{week:02d}_{away}_{home}"
        date = pd.Timestamp("2023-09-07") + pd.Timedelta(days=7 * (week - 1))
        for team, opp, off_home in ((home, away, 1), (away, home, -1)):
            rows.append(
                {
                    "game_id": gid,
                    "season": 2023,
                    "week": week,
                    "game_date": date,
                    "team": team,
                    "opponent": opp,
                    "off_home": off_home,
                    "off_pass": OFF_EPA[team],
                    "off_rush": OFF_EPA[team] / 2,
                }
            )
    return pd.DataFrame(rows)


def test_entering_ratings_ignore_future_games():
    """Causality: entering ratings for weeks <= 4 are identical whether or
    not the week 5-6 games exist in the input frame."""
    full, _ = ridge_ratings(synthetic_obs(6), half_life=4.0, alpha=1.0, carryover=0.7)
    trunc, _ = ridge_ratings(synthetic_obs(4), half_life=4.0, alpha=1.0, carryover=0.7)
    m = full[full["week"] <= 4].merge(trunc, on=["game_id", "team"], suffixes=("_f", "_t"))
    assert len(m) == len(trunc)
    for c in RATING_COLS:
        assert np.allclose(m[f"{c}_f"], m[f"{c}_t"], atol=1e-9), c


def test_positive_epa_team_outrates_negative():
    per_game, current = ridge_ratings(synthetic_obs(6), half_life=4.0, alpha=1.0, carryover=0.7)
    # entering week 4 (both A and B play), A has 2 strong games, B 2 weak ones
    wk4 = per_game[per_game["week"] == 4].set_index("team")
    assert wk4.loc["AAA", "r_off_pass"] > wk4.loc["BBB", "r_off_pass"]
    assert wk4.loc["AAA", "r_off_rush"] > wk4.loc["BBB", "r_off_rush"]
    # end-state agrees
    cur = current.set_index("team")
    assert cur.loc["AAA", "r_off_pass"] > cur.loc["BBB", "r_off_pass"]


def test_week1_ratings_are_zero():
    per_game, _ = ridge_ratings(synthetic_obs(6), half_life=4.0, alpha=1.0, carryover=0.7)
    wk1 = per_game[per_game["week"] == 1]
    assert (wk1[list(RATING_COLS)] == 0.0).all().all()


def test_output_shape_matches_ewma_contract():
    per_game, current = ridge_ratings(synthetic_obs(6))
    assert list(per_game.columns) == ["game_id", "season", "week", "team", "opponent"] + list(
        RATING_COLS
    )
    assert list(current.columns) == ["team", *RATING_COLS]
    assert len(per_game) == 12  # 6 games x 2 teams


@pytest.mark.parametrize("carryover", [0.2, 1.0])
def test_carryover_only_scales_weights_not_causality(carryover):
    full, _ = ridge_ratings(synthetic_obs(6), half_life=4.0, alpha=1.0, carryover=carryover)
    trunc, _ = ridge_ratings(synthetic_obs(3), half_life=4.0, alpha=1.0, carryover=carryover)
    m = full[full["week"] <= 3].merge(trunc, on=["game_id", "team"], suffixes=("_f", "_t"))
    for c in RATING_COLS:
        assert np.allclose(m[f"{c}_f"], m[f"{c}_t"], atol=1e-9), c
