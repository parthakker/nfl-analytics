"""Assemble game-level model features from ratings + game context.

One row per completed game: rating diffs (home - away, four components),
rest-day diff, timezone-shift diff, division flag, QB-availability diff;
targets (home win, home margin); market reference (devigged home moneyline
prob, closing spread).
"""

import duckdb
import pandas as pd

BASE_FEATURE_COLS = [
    "d_off_pass",
    "d_off_rush",
    "d_def_pass",
    "d_def_rush",
    "d_rest",
    "d_tz",
    "div_game",
]

# FEATURE_COLS is the SHIPPED registry (what backtest defaults to and what
# train_model persists). d_qb_out gated in per docs/model_report.md.
FEATURE_COLS = BASE_FEATURE_COLS + ["d_qb_out"]

RATINGS_SOURCES = ("ewma", "ridge")


def compute_ratings_source(con, ratings_source: str = "ewma", **hyper):
    """Switchable ratings backend. Both sources return the same two frames
    (per-game entering ratings, current end-state) with identical columns,
    so backtest.py and predict.py never care which one produced them."""
    if ratings_source == "ewma":
        from .ratings import compute_ratings

        return compute_ratings(con, **hyper)
    if ratings_source == "ridge":
        from .ratings_ridge import compute_ratings_ridge

        return compute_ratings_ridge(con, **hyper)
    raise ValueError(f"ratings_source must be one of {RATINGS_SOURCES}, got {ratings_source!r}")


GAME_CONTEXT_SQL = """
    WITH ctx AS (
        SELECT game_id, team, rest_days, rest_days_sched, tz_shift_hours, is_home
        FROM v_team_games
    )
    SELECT g.game_id, g.season, g.week, g.season_type,
           g.home_team, g.away_team,
           g.home_score - g.away_score AS home_margin,
           CASE WHEN g.home_score > g.away_score THEN 1
                WHEN g.home_score < g.away_score THEN 0 ELSE NULL END AS home_win,
           g.div_game, g.spread_line,
           h.rest_days AS home_rest, a.rest_days AS away_rest,
           h.rest_days_sched AS home_rest_sched, a.rest_days_sched AS away_rest_sched,
           coalesce(a.tz_shift_hours, 0) AS away_tz_shift,
           s.home_moneyline, s.away_moneyline
    FROM games g
    LEFT JOIN ctx h ON h.game_id = g.game_id AND h.team = g.home_team AND h.is_home
    LEFT JOIN ctx a ON a.game_id = g.game_id AND a.team = g.away_team AND NOT a.is_home
    LEFT JOIN schedules s ON s.game_id = g.game_id
"""


def moneyline_prob(ml: float) -> float | None:
    if ml is None or pd.isna(ml):
        return None
    return 100.0 / (ml + 100.0) if ml > 0 else -ml / (-ml + 100.0)


def feature_row(
    home: dict,
    away: dict,
    rest_diff: float = 0.0,
    away_tz_shift: float = 0.0,
    div_game: int = 0,
    d_qb_out: float = 0.0,
    rest_diff_sched: float | None = None,
) -> dict:
    """The ONE definition of how ratings + context become model inputs.

    `home` / `away` carry r_off_pass, r_off_rush, r_def_pass, r_def_rush.
    Offense diffs are home - away. Defense ratings are "EPA allowed", so lower
    is better — those diffs are away - home to keep positive = good for home
    on every column. build_features() applies these same expressions
    vectorised and predict.py calls this directly; tests/unit/
    test_feature_parity.py pins the two equal.

    `d_rest_sched` is the same rest edge computed from the schedule's
    rest_days_sched instead of the lag-computed rest_days (an experiment
    column, not in FEATURE_COLS). At serve time the caller has one rest
    number, so it defaults to rest_diff.
    """
    return {
        "d_off_pass": home["r_off_pass"] - away["r_off_pass"],
        "d_off_rush": home["r_off_rush"] - away["r_off_rush"],
        "d_def_pass": away["r_def_pass"] - home["r_def_pass"],
        "d_def_rush": away["r_def_rush"] - home["r_def_rush"],
        "d_rest": rest_diff,
        "d_rest_sched": rest_diff if rest_diff_sched is None else rest_diff_sched,
        "d_tz": away_tz_shift,
        "div_game": int(div_game),
        "d_qb_out": d_qb_out,
    }


def rest_clip(days) -> float:
    """Rest days as the model sees them: unknown -> 7, clipped to 3-14."""
    if days is None or pd.isna(days):
        days = 7
    return float(min(14, max(3, days)))


def build_features(
    con: duckdb.DuckDBPyConnection,
    per_game_ratings: pd.DataFrame,
    qb_flags: pd.DataFrame | None = None,
) -> pd.DataFrame:
    games = con.execute(GAME_CONTEXT_SQL).fetchdf()
    r = per_game_ratings
    home = r.rename(columns={c: f"h_{c}" for c in r.columns if c.startswith("r_")})
    away = r.rename(columns={c: f"a_{c}" for c in r.columns if c.startswith("r_")})
    df = (
        games.merge(
            home[
                ["game_id", "team", "h_r_off_pass", "h_r_off_rush", "h_r_def_pass", "h_r_def_rush"]
            ],
            left_on=["game_id", "home_team"],
            right_on=["game_id", "team"],
        )
        .drop(columns="team")
        .merge(
            away[
                ["game_id", "team", "a_r_off_pass", "a_r_off_rush", "a_r_def_pass", "a_r_def_rush"]
            ],
            left_on=["game_id", "away_team"],
            right_on=["game_id", "team"],
        )
        .drop(columns="team")
    )

    # vectorised twin of feature_row() — same expressions, same signs
    for d in ("off_pass", "off_rush"):
        df[f"d_{d}"] = df[f"h_r_{d}"] - df[f"a_r_{d}"]
    # defensive ratings: lower = better, so away - home puts "home advantage" positive
    for d in ("def_pass", "def_rush"):
        df[f"d_{d}"] = df[f"a_r_{d}"] - df[f"h_r_{d}"]

    # QB availability: expected starter Out/Doubtful/reserve, causal (qb_flag.py)
    if qb_flags is not None:
        f = qb_flags[["game_id", "team", "qb_out"]]
        df = df.merge(
            f.rename(columns={"team": "home_team", "qb_out": "home_qb_out"}),
            on=["game_id", "home_team"],
            how="left",
        ).merge(
            f.rename(columns={"team": "away_team", "qb_out": "away_qb_out"}),
            on=["game_id", "away_team"],
            how="left",
        )
        df["d_qb_out"] = df["home_qb_out"].fillna(0) - df["away_qb_out"].fillna(0)
    else:
        df["d_qb_out"] = 0.0

    # Rest comes from v_team_games.rest_days (the lag-computed one, NULL in
    # week 1 and across a season boundary -> treated as 7). d_rest_sched is the
    # same edge from rest_days_sched (schedule-derived, populated week 1) so an
    # experiment can swap them with `--features +d_rest_sched,-d_rest`. The
    # shipped model trains on d_rest — see docs/knowledge/model-primer.md.
    df["d_rest"] = df["home_rest"].fillna(7).clip(3, 14) - df["away_rest"].fillna(7).clip(3, 14)
    df["d_rest_sched"] = df["home_rest_sched"].fillna(7).clip(3, 14) - df["away_rest_sched"].fillna(
        7
    ).clip(3, 14)
    # away team traveling east = positive shift; home team is at home (shift 0)
    df["d_tz"] = df["away_tz_shift"].fillna(0)
    df["div_game"] = df["div_game"].fillna(0).astype(int)

    ph = df["home_moneyline"].map(moneyline_prob)
    pa = df["away_moneyline"].map(moneyline_prob)
    df["market_home_prob"] = ph / (ph + pa)  # devig by normalization

    return df
