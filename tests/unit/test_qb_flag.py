"""Leakage traps for the QB availability flag, on synthetic frames (no DB):
(a) the causally-expected starter wins even when the actual game passer
differs, (b) the injury-shortened fallback path, (c) truncation invariance —
future games must not change earlier flags — plus roster-status and
missing-data (pre-2009) behavior."""

import pandas as pd

from nfl_analytics.model.qb_flag import expected_starters, flags_from_frames

QB1, QB2, QB3 = "00-0000001", "00-0000002", "00-0000003"


def _db_rows(rows):
    """rows: (game_id, week, team, passer, dropbacks) in season 2023."""
    return pd.DataFrame(
        [
            {
                "game_id": gid,
                "game_date": pd.Timestamp("2023-09-07") + pd.Timedelta(days=7 * (wk - 1)),
                "season": 2023,
                "week": wk,
                "team": team,
                "passer_player_id": passer,
                "dropbacks": db,
            }
            for gid, wk, team, passer, db in rows
        ]
    )


def _exp_for(exp_df, gid, team):
    row = exp_df[(exp_df["game_id"] == gid) & (exp_df["team"] == team)]
    assert len(row) == 1
    return row.iloc[0]["expected_starter"]


def test_causal_expected_starter_beats_actual_passer():
    """Game 2's actual passer is QB2 (35 dropbacks) — but entering game 2 the
    only causal information is game 1, where QB1 led. QB1 must win."""
    d = _db_rows(
        [
            ("2023_01_PHI_DAL", 1, "PHI", QB1, 30),
            ("2023_02_PHI_NYG", 2, "PHI", QB2, 35),  # actual passer differs
        ]
    )
    exp = expected_starters(d)
    assert _exp_for(exp, "2023_02_PHI_NYG", "PHI") == QB1

    # ...and if QB1 is Out that week, the flag fires even though QB2 played
    exp["team_c"] = exp["team"]
    inj = pd.DataFrame([{"season": 2023, "week": 2, "team_c": "PHI", "gsis_id": QB1}])
    ros = pd.DataFrame(columns=["season", "week", "gsis_id"])
    flags = flags_from_frames(exp, inj, ros).set_index(["game_id", "team"])
    assert flags.loc[("2023_02_PHI_NYG", "PHI"), "qb_out"] == 1
    assert flags.loc[("2023_01_PHI_DAL", "PHI"), "qb_out"] == 0  # no prior game -> no starter


def test_fallback_when_last_game_leader_under_10_dropbacks():
    """Game 2 was injury-shortened (leader had 9 dropbacks) — entering game 3
    the fallback aggregates the last 3 games, where QB1 dominates."""
    d = _db_rows(
        [
            ("2023_01_PHI_DAL", 1, "PHI", QB1, 30),
            ("2023_02_PHI_NYG", 2, "PHI", QB2, 9),
            ("2023_03_PHI_WAS", 3, "PHI", QB3, 20),
        ]
    )
    exp = expected_starters(d)
    # last-game leader (QB2, 9 dropbacks) is under the floor -> 3-game window
    assert _exp_for(exp, "2023_03_PHI_WAS", "PHI") == QB1
    # no fallback when the last-game leader is healthy-sized
    assert _exp_for(exp, "2023_02_PHI_NYG", "PHI") == QB1


def test_no_fallback_when_leader_has_10_plus():
    d = _db_rows(
        [
            ("2023_01_PHI_DAL", 1, "PHI", QB1, 40),
            ("2023_02_PHI_NYG", 2, "PHI", QB2, 12),  # real (if short) start
            ("2023_03_PHI_WAS", 3, "PHI", QB1, 30),
        ]
    )
    exp = expected_starters(d)
    assert _exp_for(exp, "2023_03_PHI_WAS", "PHI") == QB2


def test_truncation_invariance():
    """Flags for early games are identical with and without future games in
    the input frame — the causality property train_model asserts on real data."""
    rows = [
        ("2023_01_PHI_DAL", 1, "PHI", QB1, 30),
        ("2023_02_PHI_NYG", 2, "PHI", QB1, 8),
        ("2023_02_PHI_NYG", 2, "PHI", QB2, 25),
        ("2023_03_PHI_WAS", 3, "PHI", QB2, 33),
        ("2023_04_PHI_SF", 4, "PHI", QB3, 28),
    ]
    full, trunc = _db_rows(rows), _db_rows(rows[:3])
    inj = pd.DataFrame([{"season": 2023, "week": 2, "team_c": "PHI", "gsis_id": QB1}])
    ros = pd.DataFrame(columns=["season", "week", "gsis_id"])

    def flags(frame):
        e = expected_starters(frame)
        e["team_c"] = e["team"]
        return flags_from_frames(e, inj, ros)

    f_full = flags(full).set_index(["game_id", "team"])["qb_out"]
    f_trunc = flags(trunc).set_index(["game_id", "team"])["qb_out"]
    assert (f_full.loc[f_trunc.index] == f_trunc).all()


def test_roster_reserve_counts_as_out():
    d = _db_rows(
        [
            ("2023_01_PHI_DAL", 1, "PHI", QB1, 30),
            ("2023_02_PHI_NYG", 2, "PHI", QB2, 35),
        ]
    )
    exp = expected_starters(d)
    exp["team_c"] = exp["team"]
    inj = pd.DataFrame(columns=["season", "week", "team_c", "gsis_id"])
    ros = pd.DataFrame([{"season": 2023, "week": 2, "gsis_id": QB1}])  # RES/CUT that week
    flags = flags_from_frames(exp, inj, ros).set_index(["game_id", "team"])
    assert flags.loc[("2023_02_PHI_NYG", "PHI"), "qb_out"] == 1


def test_missing_data_means_zero():
    """No injury/roster rows at all (e.g. pre-2009) -> flag is 0, never NULL."""
    d = _db_rows(
        [
            ("2008_01_PHI_DAL", 1, "PHI", QB1, 30),
            ("2008_02_PHI_NYG", 2, "PHI", QB1, 32),
        ]
    )
    exp = expected_starters(d)
    exp["team_c"] = exp["team"]
    empty_inj = pd.DataFrame(columns=["season", "week", "team_c", "gsis_id"])
    empty_ros = pd.DataFrame(columns=["season", "week", "gsis_id"])
    flags = flags_from_frames(exp, empty_inj, empty_ros)
    assert flags["qb_out"].isin([0]).all()
