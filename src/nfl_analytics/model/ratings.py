"""Opponent-adjusted EWMA EPA team ratings, strictly causal.

For every game, each team's four raw per-play EPA aggregates (off pass/rush,
def pass/rush) are adjusted by the opponent's rating *entering* that game,
then folded into an exponentially weighted average. Ratings recorded for a
game are always the pre-game values, so downstream features can never leak
the game's own result. Season boundaries shrink ratings toward the league
mean (0) by `carryover`.

Rating units are EPA/play relative to league average. Because model features
are home-away diffs, any league-wide level drift cancels and no explicit
centering is needed.
"""

from dataclasses import dataclass, field

import duckdb
import pandas as pd

GAME_EPA_SQL = """
    SELECT p.game_id, p.season, p.week, g.game_date,
           p.posteam AS team, p.defteam AS opponent,
           avg(p.epa) FILTER (WHERE p.pass = 1) AS off_pass,
           avg(p.epa) FILTER (WHERE p.rush = 1) AS off_rush
    FROM play_by_play p
    JOIN games g USING (game_id)
    WHERE p.play_type IN ('pass', 'run') AND p.posteam IS NOT NULL
    GROUP BY ALL
    ORDER BY g.game_date, p.game_id
"""

DIMS = ("off_pass", "off_rush", "def_pass", "def_rush")


@dataclass
class RatingBook:
    half_life: float = 8.0
    carryover: float = 0.5
    ratings: dict = field(default_factory=dict)  # team -> {dim: value}
    _season: dict = field(default_factory=dict)  # team -> last season seen

    @property
    def alpha(self) -> float:
        return 1.0 - 0.5 ** (1.0 / self.half_life)

    def entering(self, team: str) -> dict:
        return dict(self.ratings.get(team, {d: 0.0 for d in DIMS}))

    def _roll_season(self, team: str, season: int) -> None:
        if self._season.get(team) is not None and season > self._season[team]:
            r = self.ratings.get(team)
            if r:
                for d in DIMS:
                    r[d] *= self.carryover
        self._season[team] = season

    def update(
        self, team: str, opponent: str, season: int, off_pass: float, off_rush: float
    ) -> None:
        """Fold one game's offensive performance into `team`'s offense and
        `opponent`'s defense. Caller must have taken `entering()` snapshots
        for both sides BEFORE any update() calls for the game."""
        self._roll_season(team, season)
        self._roll_season(opponent, season)
        tr = self.ratings.setdefault(team, {d: 0.0 for d in DIMS})
        orr = self.ratings.setdefault(opponent, {d: 0.0 for d in DIMS})
        a = self.alpha
        for dim, raw in (("pass", off_pass), ("rush", off_rush)):
            if raw is None or pd.isna(raw):
                continue
            adj_off = raw - orr[f"def_{dim}"]  # credit vs opponent D entering
            adj_def = raw - tr[f"off_{dim}"]  # opponent D debited vs team O entering
            tr[f"off_{dim}"] = (1 - a) * tr[f"off_{dim}"] + a * adj_off
            orr[f"def_{dim}"] = (1 - a) * orr[f"def_{dim}"] + a * adj_def


def compute_ratings(
    con: duckdb.DuckDBPyConnection,
    half_life: float = 8.0,
    carryover: float = 0.5,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Returns (per-game entering ratings, current end-state ratings).

    Per-game frame: one row per team-game with the four ratings ENTERING
    that game. End-state frame: one row per team, ratings after the last
    game played — what predictions for upcoming games should use."""
    rows = con.execute(GAME_EPA_SQL).fetchdf()
    book = RatingBook(half_life=half_life, carryover=carryover)
    out = []
    for game_id, grp in rows.groupby("game_id", sort=False):
        # snapshot entering ratings for both teams before any updates
        snaps = {}
        for _, r in grp.iterrows():
            book._roll_season(r["team"], int(r["season"]))
            snaps[r["team"]] = book.entering(r["team"])
        for _, r in grp.iterrows():
            e = snaps[r["team"]]
            out.append(
                {
                    "game_id": game_id,
                    "season": int(r["season"]),
                    "week": int(r["week"]),
                    "team": r["team"],
                    "opponent": r["opponent"],
                    **{f"r_{d}": e[d] for d in DIMS},
                }
            )
        for _, r in grp.iterrows():
            book.update(r["team"], r["opponent"], int(r["season"]), r["off_pass"], r["off_rush"])
    current = pd.DataFrame(
        [{"team": t, **{f"r_{d}": v[d] for d in DIMS}} for t, v in sorted(book.ratings.items())]
    )
    return pd.DataFrame(out), current
