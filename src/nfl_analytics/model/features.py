"""Assemble game-level model features from ratings + game context.

One row per completed game: rating diffs (home - away, four components),
rest-day diff, timezone-shift diff, division flag; targets (home win, home
margin); market reference (devigged home moneyline prob, closing spread).
"""

import duckdb
import pandas as pd

FEATURE_COLS = [
    "d_off_pass",
    "d_off_rush",
    "d_def_pass",
    "d_def_rush",
    "d_rest",
    "d_tz",
    "div_game",
]

GAME_CONTEXT_SQL = """
    WITH ctx AS (
        SELECT game_id, team, rest_days, tz_shift_hours, is_home
        FROM v_team_games
    )
    SELECT g.game_id, g.season, g.week, g.season_type,
           g.home_team, g.away_team,
           g.home_score - g.away_score AS home_margin,
           CASE WHEN g.home_score > g.away_score THEN 1
                WHEN g.home_score < g.away_score THEN 0 ELSE NULL END AS home_win,
           g.div_game, g.spread_line,
           h.rest_days AS home_rest, a.rest_days AS away_rest,
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


def build_features(con: duckdb.DuckDBPyConnection, per_game_ratings: pd.DataFrame) -> pd.DataFrame:
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

    for d in ("off_pass", "off_rush"):
        df[f"d_{d}"] = df[f"h_r_{d}"] - df[f"a_r_{d}"]
    # defensive ratings: lower = better, so away - home puts "home advantage" positive
    for d in ("def_pass", "def_rush"):
        df[f"d_{d}"] = df[f"a_r_{d}"] - df[f"h_r_{d}"]

    df["d_rest"] = df["home_rest"].fillna(7).clip(3, 14) - df["away_rest"].fillna(7).clip(3, 14)
    # away team traveling east = positive shift; home team is at home (shift 0)
    df["d_tz"] = df["away_tz_shift"].fillna(0)
    df["div_game"] = df["div_game"].fillna(0).astype(int)

    ph = df["home_moneyline"].map(moneyline_prob)
    pa = df["away_moneyline"].map(moneyline_prob)
    df["market_home_prob"] = ph / (ph + pa)  # devig by normalization

    return df
