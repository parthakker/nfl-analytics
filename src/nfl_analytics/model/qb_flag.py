"""QB availability flag, strictly causal.

Expected starter for team T entering game G = the passer_player_id with the
most qb_dropback plays for T in T's most recent COMPLETED game (game_date
strictly before G's). Fallback: when that last-game leader had fewer than 10
dropbacks (injury-shortened game), use the most dropbacks summed across T's
last 3 completed games. The ACTUAL game-G passer is never consulted — that
would leak the very absence we are trying to predict.

qb_out = 1 iff the expected starter is listed Out/Doubtful on the injury
report for that (season, week) — team join through canon_team() because
injuries carries legacy codes — OR rosters_weekly.status in ('RES','CUT')
that week. 'INA' is deliberately NOT used (inactives timing unverifiable
historically) and depth_charts is deliberately NOT used (dead after 2024 —
serve/train skew). Before the 2009 injuries floor everything is NULL -> 0.
"""

import pandas as pd

# per (game, team, passer): dropback count, with game date for sequencing
DROPBACKS_SQL = """
    SELECT p.game_id, g.game_date, p.season, p.week, p.posteam AS team,
           p.passer_player_id, count(*) AS dropbacks
    FROM play_by_play p
    JOIN games g USING (game_id)
    WHERE p.qb_dropback = 1 AND p.passer_player_id IS NOT NULL
      AND p.posteam IS NOT NULL
    GROUP BY ALL
    ORDER BY g.game_date, p.game_id
"""

INJURIES_SQL = """
    SELECT season, week, canon_team(team) AS team_c, gsis_id
    FROM injuries
    WHERE report_status IN ('Out', 'Doubtful')
"""

ROSTER_OUT_SQL = """
    SELECT DISTINCT season, week, gsis_id
    FROM rosters_weekly
    WHERE status IN ('RES', 'CUT')
"""

MIN_LAST_GAME_DROPBACKS = 10
FALLBACK_GAMES = 3


def expected_starters(dropbacks: pd.DataFrame) -> pd.DataFrame:
    """One row per (game_id, team) with the expected starter ENTERING that
    game. Pure pandas so unit tests can feed synthetic frames.

    dropbacks: one row per (game_id, team, passer_player_id) with columns
    game_id, game_date, season, week, team, passer_player_id, dropbacks."""
    d = dropbacks.copy()
    d["game_date"] = pd.to_datetime(d["game_date"])
    d = d.sort_values(
        ["team", "game_date", "game_id", "dropbacks", "passer_player_id"],
        kind="mergesort",
    )
    out = []
    for team, tg in d.groupby("team", sort=False):
        # per-game passer tallies, in this team's completed-game order
        games = []  # list of (game_id, season, week, {passer: dropbacks})
        for (gid, season, week), g in tg.groupby(["game_id", "season", "week"], sort=False):
            games.append(
                (gid, season, week, dict(zip(g["passer_player_id"], g["dropbacks"], strict=True)))
            )
        for i, (gid, season, week, _tally) in enumerate(games):
            exp = None
            if i > 0:
                last = games[i - 1][3]
                leader = max(sorted(last), key=lambda p: last[p])
                if last[leader] >= MIN_LAST_GAME_DROPBACKS:
                    exp = leader
                else:  # injury-shortened last game: widen to last 3 games
                    pool: dict = {}
                    for _, _, _, tally in games[max(0, i - FALLBACK_GAMES) : i]:
                        for p, n in tally.items():
                            pool[p] = pool.get(p, 0) + n
                    exp = max(sorted(pool), key=lambda p: pool[p])
            out.append(
                {
                    "game_id": gid,
                    "season": int(season),
                    "week": int(week),
                    "team": team,
                    "expected_starter": exp,
                }
            )
    return pd.DataFrame(out)


def flags_from_frames(
    exp: pd.DataFrame, injuries: pd.DataFrame, roster_out: pd.DataFrame
) -> pd.DataFrame:
    """Join expected starters against Out/Doubtful reports + RES/CUT roster
    rows. Team codes must already be canonical on BOTH sides (`team_c`);
    the DB path applies canon_team() before calling this. Pure pandas.

    exp: game_id, season, week, team, team_c, expected_starter
    injuries: season, week, team_c, gsis_id (already filtered Out/Doubtful)
    roster_out: season, week, gsis_id (already filtered RES/CUT)
    Returns game_id, team, qb_out (0/1; missing data -> 0, incl. pre-2009)."""
    e = exp.copy()
    inj = injuries.drop_duplicates().assign(_inj=1)
    ros = roster_out.drop_duplicates().assign(_ros=1)
    e = e.merge(
        inj,
        left_on=["season", "week", "team_c", "expected_starter"],
        right_on=["season", "week", "team_c", "gsis_id"],
        how="left",
    ).merge(
        ros,
        left_on=["season", "week", "expected_starter"],
        right_on=["season", "week", "gsis_id"],
        how="left",
    )
    e["qb_out"] = (((e["_inj"] == 1) | (e["_ros"] == 1)) & e["expected_starter"].notna()).astype(
        int
    )
    return e[["game_id", "team", "qb_out"]]


def qb_out_flags(con, dropbacks: pd.DataFrame | None = None) -> pd.DataFrame:
    """DB entry point: one row per (game_id, team) with qb_out in {0, 1}.
    `dropbacks` may be injected (already-loaded or truncated frame) so the
    causality check can diff against truncated history."""
    if dropbacks is None:
        dropbacks = con.execute(DROPBACKS_SQL).fetchdf()
    exp = expected_starters(dropbacks)
    # canonicalize team codes for the injuries join (legacy codes both sides)
    exp = con.execute("SELECT *, canon_team(team) AS team_c FROM exp").fetchdf()
    injuries = con.execute(INJURIES_SQL).fetchdf()
    roster_out = con.execute(ROSTER_OUT_SQL).fetchdf()
    return flags_from_frames(exp, injuries, roster_out)


def current_qb_out(con, team: str) -> dict:
    """Serve-time flag for a team's NEXT scheduled game (schedules-only path
    for upcoming games, live DB at call time). Expected starter comes from
    the last completed games in pbp — same rule as training; status comes
    from injuries/rosters_weekly at the upcoming (season, week)."""
    last = con.execute(
        f"""
        WITH recent AS (
            SELECT DISTINCT p.game_id, g.game_date
            FROM play_by_play p JOIN games g USING (game_id)
            WHERE p.posteam = canon_team(?) AND p.qb_dropback = 1
            ORDER BY g.game_date DESC LIMIT {FALLBACK_GAMES}
        )
        SELECT p.game_id, g.game_date, p.passer_player_id, count(*) AS dropbacks
        FROM play_by_play p
        JOIN games g USING (game_id)
        JOIN recent r ON r.game_id = p.game_id
        WHERE p.posteam = canon_team(?) AND p.qb_dropback = 1
          AND p.passer_player_id IS NOT NULL
        GROUP BY ALL
        ORDER BY g.game_date DESC
        """,
        [team, team],
    ).fetchdf()
    if last.empty:
        return {"team": team, "expected_starter": None, "qb_out": 0, "why": "no pbp history"}

    last_gid = last.iloc[0]["game_id"]
    lg = last[last["game_id"] == last_gid]
    # ties break to the lowest id — same as expected_starters()
    leader = lg.sort_values(["dropbacks", "passer_player_id"], ascending=[False, True]).iloc[0]
    if leader["dropbacks"] >= MIN_LAST_GAME_DROPBACKS:
        exp = leader["passer_player_id"]
    else:
        pool = last.groupby("passer_player_id")["dropbacks"].sum().sort_index()
        exp = pool.idxmax()

    nxt = con.execute(
        """
        SELECT season, week FROM schedules
        WHERE (home_team = canon_team(?) OR away_team = canon_team(?))
          AND result IS NULL
        ORDER BY gameday LIMIT 1
        """,
        [team, team],
    ).fetchone()
    if nxt is None:
        return {"team": team, "expected_starter": exp, "qb_out": 0, "why": "no upcoming game"}
    season, week = int(nxt[0]), int(nxt[1])

    hit = con.execute(
        """
        SELECT
          coalesce((SELECT max(1) FROM injuries
            WHERE season = ? AND week = ? AND gsis_id = ?
              AND canon_team(team) = canon_team(?)
              AND report_status IN ('Out', 'Doubtful')), 0)
          + coalesce((SELECT max(1) FROM rosters_weekly
            WHERE season = ? AND week = ? AND gsis_id = ?
              AND status IN ('RES', 'CUT')), 0)
        """,
        [season, week, exp, team, season, week, exp],
    ).fetchone()[0]
    return {
        "team": team,
        "expected_starter": exp,
        "season": season,
        "week": week,
        "qb_out": int(hit > 0),
    }
