"""Constants every model consumer shares — one definition, imported everywhere.

Before this module the holdout window was typed in three files and the power
rating "net" formula in two (with different scales). Anything that train,
experiment, serve, the API or the recap all need to agree on lives here.
"""

from ..config import LOGS_DIR

# Walk-forward windows. Hyperparameters are tuned ONLY on TUNE_SEASONS; the
# headline numbers come from HOLDOUT_SEASONS, which nothing is ever tuned
# against; BONUS_SEASON is reported separately as a fully untouched season.
TUNE_SEASONS = (2012, 2018)
HOLDOUT_SEASONS = (2019, 2024)
FIRST_TARGET = 2012  # first season walk_forward predicts
BONUS_SEASON = 2025

# Every experiment and every train run appends one JSON line here.
EXPERIMENT_LOG = LOGS_DIR / "model_experiments.jsonl"

# Power-rating "net": mean of the two offensive ratings minus mean of the two
# defensive ratings (lower def = better). Units stay EPA/play. The Python and
# SQL forms are the same formula; a unit test pins them equal.
NET_RATING_SQL = "(r_off_pass + r_off_rush) / 2 - (r_def_pass + r_def_rush) / 2"


def net_rating(off_pass: float, off_rush: float, def_pass: float, def_rush: float) -> float:
    return (off_pass + off_rush) / 2 - (def_pass + def_rush) / 2


# Plain-English labels for the feature registry — the Model Lab page, the
# Learn chapter and the experiment scorecard all read these so the wording
# cannot drift between surfaces.
FEATURE_LABELS: dict[str, tuple[str, str]] = {
    "d_off_pass": (
        "Passing offense edge",
        "Home's pass-EPA rating minus away's. Opponent-adjusted, entering this game.",
    ),
    "d_off_rush": (
        "Rushing offense edge",
        "Home's rush-EPA rating minus away's. Opponent-adjusted, entering this game.",
    ),
    "d_def_pass": (
        "Pass defense edge",
        "Away's pass-defense rating minus home's (lower is better, so the sign is "
        "flipped to keep positive = good for home).",
    ),
    "d_def_rush": (
        "Rush defense edge",
        "Away's rush-defense rating minus home's (sign flipped: positive = good for home).",
    ),
    "d_rest": (
        "Rest edge (days)",
        "Home rest days minus away rest days, each clipped to 3-14; unknown = 7.",
    ),
    "d_tz": (
        "Away time-zone shift (hours)",
        "How many hours the away team travelled east (positive) or west (negative).",
    ),
    "div_game": ("Division game", "1 if the teams share a division, else 0."),
    "d_qb_out": (
        "QB availability edge",
        "Home QB-out flag minus away QB-out flag (expected starter Out/Doubtful/reserve). "
        "Negative = home is missing its QB.",
    ),
}
