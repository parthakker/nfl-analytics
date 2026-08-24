"""Decayed ridge-regression team ratings, strictly causal.

Alternative to the EWMA book in `ratings.py`. For each prediction week the
model refits a ridge regression on ALL prior team-game EPA observations:

  one observation per (game, offense-team, dimension), dimension in
  {pass, rush}; design = one-hot offense team + one-hot defense team + HFA
  indicator (+1 offense at home, -1 offense away); target = offense EPA/play
  in that game-dimension; sample weight = 0.5 ** (games_ago / half_life)
  * carryover ** (seasons_ago)  — games_ago counted in the offense team's own
  game sequence, seasons_ago relative to the prediction week's season.

Entering ratings for week W come from the fit on games with game_date
STRICTLY earlier than W's first kickoff, so a game can never inform its own
prediction (same-week earlier games are also excluded — conservative).
Offense coefficients are the off ratings; defense coefficients are the def
ratings (lower = better, matching the EWMA convention). Output frames have
the exact same shape as `ratings.compute_ratings` so features/backtest/
predict are untouched.
"""

import numpy as np
import pandas as pd
from scipy import sparse
from sklearn.linear_model import Ridge

# Same play universe as ratings.GAME_EPA_SQL, plus the home indicator.
OBS_SQL = """
    SELECT p.game_id, p.season, p.week, g.game_date,
           p.posteam AS team, p.defteam AS opponent,
           CASE WHEN p.posteam = g.home_team THEN 1 ELSE -1 END AS off_home,
           avg(p.epa) FILTER (WHERE p.pass = 1) AS off_pass,
           avg(p.epa) FILTER (WHERE p.rush = 1) AS off_rush
    FROM play_by_play p
    JOIN games g USING (game_id)
    WHERE p.play_type IN ('pass', 'run') AND p.posteam IS NOT NULL
    GROUP BY ALL
    ORDER BY g.game_date, p.game_id
"""

DIMS = ("pass", "rush")
RATING_COLS = ("r_off_pass", "r_off_rush", "r_def_pass", "r_def_rush")


def load_observations(con) -> pd.DataFrame:
    """One row per (game, offense team): off_pass / off_rush EPA + context."""
    return con.execute(OBS_SQL).fetchdf()


def _fit_week(X, y, w, alpha):
    """One sklearn Ridge on the sparse one-hot design. Returns coef vector."""
    r = Ridge(alpha=alpha, fit_intercept=True, solver="sparse_cg", tol=1e-8)
    r.fit(X, y, sample_weight=w)
    return r.coef_


def ridge_ratings(
    obs: pd.DataFrame,
    half_life: float = 9.0,
    alpha: float = 10.0,
    carryover: float = 0.7,
    progress: bool = False,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Returns (per-game entering ratings, current end-state ratings) —
    identical shape to ratings.compute_ratings. Pure function of `obs`
    (no DB) so unit tests can feed synthetic frames."""
    obs = obs.copy()
    obs["game_date"] = pd.to_datetime(obs["game_date"])
    obs = obs.sort_values(["game_date", "game_id"], kind="mergesort").reset_index(drop=True)

    teams = sorted(set(obs["team"]) | set(obs["opponent"]))
    tidx = {t: i for i, t in enumerate(teams)}
    T = len(teams)
    n = len(obs)
    off_i = obs["team"].map(tidx).to_numpy()
    def_i = obs["opponent"].map(tidx).to_numpy()

    # sparse one-hot design: [offense teams | defense teams | HFA]
    rows = np.repeat(np.arange(n), 3)
    cols = np.stack([off_i, T + def_i, np.full(n, 2 * T)], axis=1).ravel()
    vals = np.stack([np.ones(n), np.ones(n), obs["off_home"].to_numpy(dtype=float)], axis=1).ravel()
    X = sparse.csr_matrix((vals, (rows, cols)), shape=(n, 2 * T + 1))

    dates = obs["game_date"].to_numpy().astype("int64")
    seasons = obs["season"].to_numpy()
    k = obs.groupby("team", sort=False).cumcount().to_numpy()  # per-team game index
    y = {d: obs[f"off_{d}"].to_numpy(dtype=float) for d in DIMS}
    team_dates = [dates[off_i == i] for i in range(T)]  # sorted per team

    def weights_at(wdate: int, wseason: int, m: int) -> np.ndarray:
        counts = np.array([np.searchsorted(td, wdate, side="left") for td in team_dates])
        games_ago = counts[off_i[:m]] - 1 - k[:m]  # 0 = team's most recent prior game
        return 0.5 ** (games_ago / half_life) * carryover ** (wseason - seasons[:m]).clip(min=0)

    def fit_all(wdate: int, wseason: int) -> dict | None:
        m = int(np.searchsorted(dates, wdate, side="left"))
        if m == 0:
            return None
        w = weights_at(wdate, wseason, m)
        coefs = {}
        for d in DIMS:
            valid = ~np.isnan(y[d][:m])
            coefs[d] = _fit_week(X[:m][valid], y[d][:m][valid], w[valid], alpha)
        return coefs

    out = np.zeros((n, 4))
    weeks = list(obs.groupby(["season", "week"], sort=False).groups.items())
    for wi, ((wseason, _wweek), idx) in enumerate(weeks):
        idx = np.asarray(idx)
        coefs = fit_all(int(dates[idx[0]]), int(wseason))
        if coefs is not None:
            out[idx, 0] = coefs["pass"][off_i[idx]]
            out[idx, 1] = coefs["rush"][off_i[idx]]
            out[idx, 2] = coefs["pass"][T + off_i[idx]]
            out[idx, 3] = coefs["rush"][T + off_i[idx]]
        if progress and (wi + 1) % 100 == 0:
            print(f"    ridge fit week {wi + 1}/{len(weeks)}", flush=True)

    per_game = obs[["game_id", "season", "week", "team", "opponent"]].copy()
    for j, c in enumerate(RATING_COLS):
        per_game[c] = out[:, j]

    # end-state: fit on everything, as of just after the last game
    coefs = fit_all(int(dates.max()) + 1, int(seasons.max()))
    current = pd.DataFrame(
        {
            "team": teams,
            "r_off_pass": coefs["pass"][:T],
            "r_off_rush": coefs["rush"][:T],
            "r_def_pass": coefs["pass"][T : 2 * T],
            "r_def_rush": coefs["rush"][T : 2 * T],
        }
    )
    return per_game, current


def compute_ratings_ridge(
    con,
    half_life: float = 9.0,
    alpha: float = 10.0,
    carryover: float = 0.7,
    obs: pd.DataFrame | None = None,
    progress: bool = False,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """DB entry point matching ratings.compute_ratings' contract."""
    if obs is None:
        obs = load_observations(con)
    return ridge_ratings(obs, half_life, alpha, carryover, progress=progress)
