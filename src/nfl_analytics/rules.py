"""Betting rules engine: hand-curated rules evaluated over a per-game facts frame.

Rules live in data/betting_rules.json (hand-curated, like stadiums.json).
The field/op/side vocabulary is a CLOSED namespace: every rule is validated
against it at load time and predicates are evaluated in pandas over a facts
DataFrame — rule content is NEVER interpolated into SQL.

Two facts frames share one column contract:
  build_facts(con, season, week)    one live week incl. kalshi / line-movement
  build_facts_history(con, seasons) completed games; live-only columns are NaN
                                    so live-only rules never match history.

`betting_rules_payload()` is the single entry point the API router and the
(future) MCP tool both call.

Devig / Kalshi-fee math is replicated faithfully from
web/api/routers/betting.py (_ml_prob, FEE, the `actionable` inequality) —
src/ cannot import from web/, so keep the two in sync by hand.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

from .config import DATA_DIR
from .db import read_conn

log = logging.getLogger(__name__)

RULES_PATH = DATA_DIR / "betting_rules.json"

# ── closed vocabulary ────────────────────────────────────────────────────────

FAMILIES = frozenset({"situational", "line_movement", "environment", "dislocation"})
MARKETS = frozenset({"spread", "moneyline", "total", "kalshi"})
TEAM_SIDES = frozenset({"home", "away", "favorite", "underdog", "rested", "cheap_side"})
TOTAL_SIDES = frozenset({"over", "under"})
SIDES = TEAM_SIDES | TOTAL_SIDES
OPS = frozenset(
    {"==", "!=", ">", ">=", "<", "<=", "in", "between", "abs_gte", "is_null", "not_null"}
)
_NUMERIC_OPS = frozenset({">", ">=", "<", "<=", "between", "abs_gte"})

# field -> kind ("num" | "bool" | "str"). This is the whole predicate
# namespace; anything else in a rule is a hard load error.
FIELDS: dict[str, str] = {
    # identity / situation (schedules)
    "season": "num",
    "week": "num",
    "season_type": "str",  # REG | POST
    "home_team": "str",
    "away_team": "str",
    "div_game": "bool",
    "referee": "str",
    "roof": "str",
    "surface": "str",
    "kickoff_et_hour": "num",
    "is_primetime": "bool",
    "favorite": "str",  # 'home' | 'away' from spread sign (+ = home favored)
    # closing lines (schedules)
    "spread_line": "num",
    "total_line": "num",
    "home_moneyline": "num",
    "away_moneyline": "num",
    # rest / travel (schedules rest + venue tables; matches v_team_games defs)
    "home_rest_days": "num",
    "away_rest_days": "num",
    "rest_edge_days": "num",  # home minus away
    "home_travel_miles": "num",
    "away_travel_miles": "num",
    "home_tz_shift_hours": "num",  # positive = traveling east
    "away_tz_shift_hours": "num",
    # weather (v_game_weather)
    "wx_wind_mph": "num",
    "wx_temp_f": "num",
    "wx_precip": "num",
    "wx_is_indoor": "bool",
    # referee career, as-of PRIOR seasons only (v_referee_seasons)
    "ref_games": "num",
    "ref_over_rate": "num",
    "ref_pen_per_game": "num",
    "ref_home_cover_rate": "num",
    # live market state (kalshi sidecar) — NaN in history frames
    "kalshi_home_prob": "num",
    "vegas_home_prob": "num",
    "dislocation_gap": "num",
    "dislocation_fee": "num",
    "dislocation_actionable": "bool",
    "spread_open": "num",
    "spread_now": "num",
    "spread_move": "num",  # now - open; positive = toward home
    "total_open": "num",
    "total_now": "num",
    "total_move": "num",
}

LIVE_ONLY_FIELDS = frozenset(
    {
        "kalshi_home_prob",
        "vegas_home_prob",
        "dislocation_gap",
        "dislocation_fee",
        "dislocation_actionable",
        "spread_open",
        "spread_now",
        "spread_move",
        "total_open",
        "total_now",
        "total_move",
    }
)
# sides whose resolution needs a live-only column
_LIVE_ONLY_SIDES = frozenset({"cheap_side"})

TRACKING_SINCE = "2026-08"  # line_snapshots / kalshi history starts 2026-08-03
BREAKEVEN = 0.524  # -110 both ways

# A rule's ROI means nothing without its sample size: +7% on 100 bets is a
# coin that landed well, +7% on 700 is an edge. Score every backtest by how
# many standard errors its win rate sits above breakeven, and grade it
# conservatively — with ~6 backtestable rules in the catalog, a Bonferroni
# correction puts the "this survives having looked at several rules" bar
# near z=2.6, not the usual 1.96.
Z_WEAK = 1.64  # below this the result is indistinguishable from noise
Z_STRONG = 2.58  # multiple-comparison-safe across a catalog of this size


def _significance(win_pct: float | None, decided: int) -> tuple[float | None, str]:
    """Standard errors above breakeven, plus a plain-language grade."""
    if win_pct is None or decided < 1:
        return None, "unknown"
    z = (win_pct - BREAKEVEN) / ((0.25 / decided) ** 0.5)
    if abs(z) < Z_WEAK:
        grade = "noise"
    elif abs(z) < Z_STRONG:
        grade = "weak"
    else:
        grade = "strong"
    return round(z, 2), grade
_VIG_PROFIT = 100.0 / 110.0

FEE = 0.07  # kalshi fee factor: fee = 0.07 * P * (1-P)  (betting.py)


# ── rule model + validation ──────────────────────────────────────────────────


@dataclass(frozen=True)
class Clause:
    field: str
    op: str
    value: object = None


@dataclass(frozen=True)
class Rule:
    id: str
    family: str
    label: str
    market: str
    side: str
    when: tuple[Clause, ...]
    enabled: bool = True
    scope: dict = field(default_factory=dict)
    notes: str = ""

    @property
    def live_only(self) -> bool:
        return self.side in _LIVE_ONLY_SIDES or any(c.field in LIVE_ONLY_FIELDS for c in self.when)


def _err(rule_id: str, msg: str) -> ValueError:
    return ValueError(f"betting rule '{rule_id}': {msg}")


def _validate_clause(rule_id: str, raw: dict) -> Clause:
    if not isinstance(raw, dict) or "field" not in raw or "op" not in raw:
        raise _err(rule_id, f"clause must have field/op keys, got {raw!r}")
    f, op, v = raw["field"], raw["op"], raw.get("value")
    if f not in FIELDS:
        raise _err(rule_id, f"unknown field '{f}' (not in the facts namespace)")
    if op not in OPS:
        raise _err(rule_id, f"unknown op '{op}'")
    kind = FIELDS[f]
    if op in _NUMERIC_OPS and kind != "num":
        raise _err(rule_id, f"op '{op}' requires a numeric field, '{f}' is {kind}")
    if op == "between":
        if not (isinstance(v, (list, tuple)) and len(v) == 2):
            raise _err(rule_id, f"'between' needs a [lo, hi] pair, got {v!r}")
    elif op == "in":
        if not (isinstance(v, (list, tuple)) and v):
            raise _err(rule_id, f"'in' needs a non-empty list, got {v!r}")
    elif op in ("is_null", "not_null"):
        if v is not None:
            raise _err(rule_id, f"'{op}' takes no value, got {v!r}")
    elif op == "abs_gte":
        if not isinstance(v, (int, float)) or isinstance(v, bool):
            raise _err(rule_id, f"'abs_gte' needs a number, got {v!r}")
    elif isinstance(v, (list, tuple, dict)) or v is None:
        raise _err(rule_id, f"op '{op}' needs a scalar value, got {v!r}")
    return Clause(f, op, v)


def parse_rules(doc: dict) -> list[Rule]:
    """Validate a betting_rules document. Unknown anything is a hard error
    naming the offending rule id."""
    if not isinstance(doc, dict) or "rules" not in doc:
        raise ValueError("betting rules doc must be a dict with a 'rules' list")
    out: list[Rule] = []
    seen: set[str] = set()
    for raw in doc["rules"]:
        rid = raw.get("id")
        if not rid or not isinstance(rid, str):
            raise ValueError(f"betting rule missing a string id: {raw!r}")
        if rid in seen:
            raise _err(rid, "duplicate id")
        seen.add(rid)
        fam = raw.get("family")
        if fam not in FAMILIES:
            raise _err(rid, f"unknown family '{fam}' (allowed: {sorted(FAMILIES)})")
        bet = raw.get("bet") or {}
        market, side = bet.get("market"), bet.get("side")
        if market not in MARKETS:
            raise _err(rid, f"unknown market '{market}' (allowed: {sorted(MARKETS)})")
        if side not in SIDES:
            raise _err(rid, f"unknown side '{side}' (allowed: {sorted(SIDES)})")
        if market == "total" and side not in TOTAL_SIDES:
            raise _err(rid, f"market 'total' needs side over/under, got '{side}'")
        if market != "total" and side in TOTAL_SIDES:
            raise _err(rid, f"side '{side}' only makes sense on market 'total'")
        when_raw = raw.get("when")
        if not isinstance(when_raw, list) or not when_raw:
            raise _err(rid, "'when' must be a non-empty list of clauses")
        clauses = tuple(_validate_clause(rid, c) for c in when_raw)
        scope = raw.get("scope") or {}
        if not isinstance(scope, dict) or not set(scope) <= {"season_type"}:
            raise _err(rid, f"scope may only contain season_type, got {scope!r}")
        out.append(
            Rule(
                id=rid,
                family=fam,
                label=raw.get("label", rid),
                market=market,
                side=side,
                when=clauses,
                enabled=bool(raw.get("enabled", True)),
                scope=scope,
                notes=raw.get("notes", ""),
            )
        )
    return out


def load_rules(path: Path | str | None = None) -> list[Rule]:
    p = Path(path) if path else RULES_PATH
    return parse_rules(json.loads(p.read_text(encoding="utf-8")))


# ── predicate evaluation (pandas, never SQL) ─────────────────────────────────


def _col(df: pd.DataFrame, name: str) -> pd.Series:
    if name in df.columns:
        return df[name]
    return pd.Series(np.nan, index=df.index)


def _clause_mask(df: pd.DataFrame, c: Clause) -> pd.Series:
    s = _col(df, c.field)
    if c.op == "is_null":
        return s.isna()
    if c.op == "not_null":
        return s.notna()
    valid = s.notna()
    if c.op == "==":
        m = s == c.value
    elif c.op == "!=":
        m = s != c.value
    elif c.op == ">":
        m = s > c.value
    elif c.op == ">=":
        m = s >= c.value
    elif c.op == "<":
        m = s < c.value
    elif c.op == "<=":
        m = s <= c.value
    elif c.op == "in":
        m = s.isin(list(c.value))
    elif c.op == "between":
        lo, hi = c.value
        m = (s >= lo) & (s <= hi)
    elif c.op == "abs_gte":
        m = s.abs() >= c.value
    else:  # pragma: no cover — parse_rules guarantees op membership
        raise ValueError(f"unknown op {c.op}")
    return (m & valid).fillna(False).astype(bool)


def _rule_mask(rule: Rule, df: pd.DataFrame) -> pd.Series:
    mask = pd.Series(True, index=df.index)
    st = rule.scope.get("season_type")
    if st:
        mask &= (_col(df, "season_type") == st).fillna(False)
    for c in rule.when:
        mask &= _clause_mask(df, c)
    return mask


def _resolve_side(rule: Rule, df: pd.DataFrame) -> pd.Series:
    """Concrete side per row: 'home'/'away' (team markets) or 'over'/'under'.
    None where the side is unresolvable (e.g. pick'em for favorite/underdog)."""
    if rule.side in TOTAL_SIDES or rule.side in ("home", "away"):
        return pd.Series(rule.side, index=df.index)
    if rule.side in ("favorite", "underdog"):
        # spread_line POSITIVE = home favored (gotcha #6)
        sl = _col(df, "spread_line")
        fav = np.where(sl > 0, "home", np.where(sl < 0, "away", None))
        if rule.side == "favorite":
            return pd.Series(fav, index=df.index, dtype=object)
        flip = {"home": "away", "away": "home"}
        return pd.Series([flip.get(x) for x in fav], index=df.index, dtype=object)
    if rule.side == "rested":
        edge = _col(df, "rest_edge_days")  # home minus away
        return pd.Series(
            np.where(edge > 0, "home", np.where(edge < 0, "away", None)),
            index=df.index,
            dtype=object,
        )
    if rule.side == "cheap_side":
        # gap = kalshi_home_prob - vegas_home_prob; negative gap = home is
        # cheaper on Kalshi (betting.py 'cheaper_side' convention)
        gap = _col(df, "dislocation_gap")
        return pd.Series(
            np.where(gap < 0, "home", np.where(gap > 0, "away", None)),
            index=df.index,
            dtype=object,
        )
    raise ValueError(f"unresolvable side {rule.side}")  # pragma: no cover


_HIT_FACTS = [
    "spread_line",
    "total_line",
    "wx_wind_mph",
    "rest_edge_days",
    "ref_over_rate",
    "spread_move",
    "total_move",
    "dislocation_gap",
    "kalshi_home_prob",
    "vegas_home_prob",
]


def _py(v):
    """numpy/pandas scalar -> JSON-safe python value."""
    if v is None or (isinstance(v, float) and v != v) or v is pd.NaT:
        return None
    if isinstance(v, (np.bool_,)):
        return bool(v)
    if isinstance(v, np.integer):
        return int(v)
    if isinstance(v, np.floating):
        return round(float(v), 4)
    return v


def _hit_dict(row: pd.Series, side: str, market: str) -> dict:
    d = {
        "game_id": row.get("game_id"),
        "season": _py(row.get("season")),
        "week": _py(row.get("week")),
        "date": row.get("date"),
        "matchup": f"{row.get('away_team')} @ {row.get('home_team')}",
        "side": side,
        "bet_team": (row.get("home_team") if side == "home" else row.get("away_team"))
        if side in ("home", "away") and market != "total"
        else None,
        "facts": {k: _py(row.get(k)) for k in _HIT_FACTS if _py(row.get(k)) is not None},
    }
    return d


def evaluate(rules: list[Rule], facts: pd.DataFrame) -> list[dict]:
    """Per-rule hits over a facts frame. Disabled rules get an empty hit list."""
    out = []
    for rule in rules:
        hits: list[dict] = []
        if rule.enabled and len(facts):
            mask = _rule_mask(rule, facts)
            sides = _resolve_side(rule, facts)
            for idx in facts.index[mask]:
                side = sides.loc[idx]
                if side is None:
                    continue  # unresolvable (pick'em / no market data)
                hits.append(_hit_dict(facts.loc[idx], side, rule.market))
        out.append({"rule_id": rule.id, "hits": hits})
    return out


# ── grading / backtest ───────────────────────────────────────────────────────


def _ml_prob(ml) -> float | None:
    """Moneyline -> implied probability. Replicated from betting.py."""
    if ml is None or ml != ml:
        return None
    ml = float(ml)
    return 100.0 / (ml + 100.0) if ml > 0 else -ml / (-ml + 100.0)


def _ml_profit(ml: float) -> float:
    """Flat-stake profit units on a winning moneyline bet."""
    ml = float(ml)
    return ml / 100.0 if ml > 0 else 100.0 / (-ml)


def _grade_row(row: pd.Series, market: str, side: str) -> tuple[str, float] | None:
    """('win'|'loss'|'push', profit_units) at flat 1u stake; None = ungradeable.
    Spread/total priced at -110; moneyline at the actual closing odds."""
    margin = row.get("result")  # home_score - away_score (verified in schedules)
    if market == "total":
        pts, line = row.get("total"), row.get("total_line")
        if pts is None or pts != pts or line is None or line != line:
            return None
        diff = (pts - line) if side == "over" else (line - pts)
        if diff == 0:
            return ("push", 0.0)
        return ("win", _VIG_PROFIT) if diff > 0 else ("loss", -1.0)
    if margin is None or margin != margin:
        return None
    if market == "spread":
        line = row.get("spread_line")
        if line is None or line != line:
            return None
        # home covers when margin > spread_line (positive line = home favored)
        diff = (margin - line) if side == "home" else (line - margin)
        if diff == 0:
            return ("push", 0.0)
        return ("win", _VIG_PROFIT) if diff > 0 else ("loss", -1.0)
    if market == "moneyline":
        ml = row.get("home_moneyline") if side == "home" else row.get("away_moneyline")
        if ml is None or ml != ml:
            return None
        if margin == 0:
            return ("push", 0.0)
        won = margin > 0 if side == "home" else margin < 0
        return ("win", _ml_profit(ml)) if won else ("loss", -1.0)
    return None  # kalshi market has no graded history


def backtest(rule: Rule, facts_hist: pd.DataFrame, include_hits: bool = False) -> dict:
    """Grade a rule against the history frame. Live-only rules (kalshi /
    line-movement fields) have no history by construction."""
    if rule.live_only or rule.market == "kalshi":
        return {"insufficient_history": True, "tracking_since": TRACKING_SINCE}

    mask = _rule_mask(rule, facts_hist)
    sides = _resolve_side(rule, facts_hist)
    graded: list[tuple[int, str, str, float]] = []  # (idx, side, outcome, profit)
    for idx in facts_hist.index[mask]:
        side = sides.loc[idx]
        if side is None:
            continue
        g = _grade_row(facts_hist.loc[idx], rule.market, side)
        if g is None:
            continue
        graded.append((idx, side, g[0], g[1]))

    if not graded:
        return {"insufficient_history": True, "reason": "no gradeable games in history"}

    gdf = pd.DataFrame(graded, columns=["idx", "side", "outcome", "profit"])
    gdf["season"] = facts_hist.loc[gdf["idx"], "season"].to_numpy()

    def _summ(d: pd.DataFrame) -> dict:
        wins = int((d["outcome"] == "win").sum())
        losses = int((d["outcome"] == "loss").sum())
        pushes = int((d["outcome"] == "push").sum())
        decided = wins + losses
        profit = float(d["profit"].sum())
        return {
            "bets": len(d),
            "wins": wins,
            "losses": losses,
            "pushes": pushes,
            "win_pct": round(wins / decided, 4) if decided else None,
            "profit_units": round(profit, 2),
            "roi": round(profit / len(d), 4) if len(d) else None,
        }

    summary = _summ(gdf)
    summary.update(
        {
            "insufficient_history": False,
            "market": rule.market,
            "breakeven": BREAKEVEN,
            "profitable": (
                (summary["win_pct"] is not None and summary["win_pct"] > BREAKEVEN)
                if rule.market != "moneyline"
                else (summary["roi"] is not None and summary["roi"] > 0)
            ),
            "coverage_start": int(gdf["season"].min()),
            "coverage_end": int(gdf["season"].max()),
        }
    )
    # moneyline pays variable prices, so a fixed-breakeven z would lie
    z, grade = (
        _significance(summary["win_pct"], summary["wins"] + summary["losses"])
        if rule.market != "moneyline"
        else (None, "unknown")
    )
    summary["decided"] = summary["wins"] + summary["losses"]
    summary["z_score"] = z
    summary["signal"] = grade
    out = {
        "summary": summary,
        "seasons": [
            {"season": int(s), **_summ(d)}
            for s, d in sorted(gdf.groupby("season"), key=lambda kv: kv[0])
        ],
    }
    if include_hits:
        recent = gdf.sort_values("idx").tail(200)
        out["hits"] = [
            {
                **_hit_dict(facts_hist.loc[r.idx], r.side, rule.market),
                "outcome": r.outcome,
                "profit": round(r.profit, 3),
            }
            for r in recent.itertuples()
        ]
        out["hits_truncated"] = len(gdf) > 200
    return out


_run_backtest = backtest  # alias: betting_rules_payload's `backtest` kwarg shadows it


# ── facts frames ─────────────────────────────────────────────────────────────

# Shared per-game SELECT. Venue/travel/tz mirrors v_team_games (which only
# covers COMPLETED games) so the same SQL serves upcoming weeks: home-base
# haversine, tz_shift positive = east. Referee career numbers are an AS-OF
# join — a game in season S aggregates v_referee_seasons rows with
# season < S only, so no rule ever sees a ref's future.
_FACTS_SQL = """
WITH sched AS (
    SELECT game_id, season, week,
           CASE WHEN game_type = 'REG' THEN 'REG' ELSE 'POST' END AS season_type,
           strftime(gameday, '%a %b %d') AS date,
           gameday, gametime, away_team, home_team,
           result, total, spread_line, total_line,
           home_moneyline, away_moneyline,
           div_game::BOOLEAN AS div_game, referee, roof, surface,
           home_rest AS home_rest_days, away_rest AS away_rest_days
    FROM schedules
    WHERE {where}
),
refkeys AS (
    SELECT s.game_id, s.season,
           coalesce(rg.ref_key, upper(trim(s.referee))) AS ref_key
    FROM sched s
    LEFT JOIN v_referee_games rg ON rg.game_id = s.game_id
    WHERE coalesce(rg.ref_key, upper(trim(s.referee))) IS NOT NULL
),
ref_asof AS (
    SELECT k.game_id,
           sum(r.games)::INT AS ref_games,
           round(sum(r.over_rate * r.games) FILTER (WHERE r.over_rate IS NOT NULL)
                 / nullif(sum(r.games) FILTER (WHERE r.over_rate IS NOT NULL), 0), 4)
               AS ref_over_rate,
           round(sum(r.pen_per_game * r.games) FILTER (WHERE r.pen_per_game IS NOT NULL)
                 / nullif(sum(r.games) FILTER (WHERE r.pen_per_game IS NOT NULL), 0), 2)
               AS ref_pen_per_game,
           round(sum(r.home_cover_rate * r.games) FILTER (WHERE r.home_cover_rate IS NOT NULL)
                 / nullif(sum(r.games) FILTER (WHERE r.home_cover_rate IS NOT NULL), 0), 4)
               AS ref_home_cover_rate
    FROM refkeys k
    JOIN v_referee_seasons r ON r.ref_key = k.ref_key AND r.season < k.season
    GROUP BY k.game_id
)
SELECT s.*,
       EXTRACT(hour FROM s.gametime)::INT AS kickoff_et_hour,
       (EXTRACT(hour FROM s.gametime) >= 20) AS is_primetime,
       CASE WHEN s.spread_line > 0 THEN 'home'
            WHEN s.spread_line < 0 THEN 'away' END AS favorite,
       s.home_rest_days - s.away_rest_days AS rest_edge_days,
       CAST(round(haversine_miles(hh.lat, hh.lon, gv.lat, gv.lon)) AS INT)
           AS home_travel_miles,
       CAST(round(haversine_miles(ha.lat, ha.lon, gv.lat, gv.lon)) AS INT)
           AS away_travel_miles,
       hh.et_offset - gv.venue_et_offset AS home_tz_shift_hours,
       ha.et_offset - gv.venue_et_offset AS away_tz_shift_hours,
       w.wind_mph AS wx_wind_mph, w.temp_f AS wx_temp_f,
       w.precip_in AS wx_precip,
       coalesce(w.is_indoor, s.roof IN ('dome', 'closed'), false) AS wx_is_indoor,
       ra.ref_games, ra.ref_over_rate, ra.ref_pen_per_game, ra.ref_home_cover_rate
FROM sched s
LEFT JOIN game_venues gv ON gv.game_id = s.game_id
LEFT JOIN team_home_venues thh ON thh.team = s.home_team AND thh.season = s.season
LEFT JOIN stadiums hh ON hh.venue_id = thh.venue_id
LEFT JOIN team_home_venues tha ON tha.team = s.away_team AND tha.season = s.season
LEFT JOIN stadiums ha ON ha.venue_id = tha.venue_id
LEFT JOIN v_game_weather w ON w.game_id = s.game_id
LEFT JOIN ref_asof ra ON ra.game_id = s.game_id
ORDER BY s.gameday, s.gametime
"""

_LIVE_COLS = sorted(LIVE_ONLY_FIELDS)


def _base_frame(con, where: str, params: list) -> pd.DataFrame:
    df = con.execute(_FACTS_SQL.format(where=where), params).fetchdf()
    df["gametime"] = df["gametime"].astype(str)
    df = df.drop(columns=["gameday"])
    return df


def build_facts(con, season: int, week: int) -> pd.DataFrame:
    """One row per game for a live (or any single) week, with kalshi and
    line-movement columns. Sidecar blocks degrade to NaN if kalshi is
    busy/absent (api.md convention)."""
    df = _base_frame(con, "season = ? AND week = ?", [season, week])
    for c in _LIVE_COLS:
        df[c] = np.nan
    df["dislocation_actionable"] = pd.Series([None] * len(df), dtype=object)
    if df.empty:
        return df

    # line movement (kalshi.line_snapshots, earliest data 2026-08-03)
    try:
        moves = con.execute(
            """
            SELECT game_id,
                   arg_min(spread_line, snapshot_ts) AS spread_open,
                   arg_max(spread_line, snapshot_ts) AS spread_now,
                   arg_min(total_line, snapshot_ts)  AS total_open,
                   arg_max(total_line, snapshot_ts)  AS total_now
            FROM kalshi.line_snapshots
            WHERE season = ? AND week = ? GROUP BY game_id
            """,
            [season, week],
        ).fetchdf()
        if not moves.empty:
            moves["spread_move"] = moves["spread_now"] - moves["spread_open"]
            moves["total_move"] = moves["total_now"] - moves["total_open"]
            df = df.drop(
                columns=[
                    "spread_open",
                    "spread_now",
                    "spread_move",
                    "total_open",
                    "total_now",
                    "total_move",
                ]
            ).merge(moves, on="game_id", how="left")
    except Exception as e:
        log.warning("rules facts s%s w%s: line_snapshots block failed: %s", season, week, e)

    # latest kalshi game-winner price + devigged Vegas prob + dislocation.
    # Math replicated from web/api/routers/betting.py board().
    kalshi_rows: list[dict] = []
    try:
        cur = con.execute(
            """
            WITH latest AS (
                SELECT *, row_number() OVER (PARTITION BY ticker
                                             ORDER BY snapshot_ts DESC) rn
                FROM kalshi.kalshi_snapshots)
            SELECT d.away_team, d.home_team, d.yes_team, l.ticker,
                   l.implied_prob_mid AS prob, l.yes_bid, l.yes_ask
            FROM latest l JOIN kalshi.kalshi_markets_dim d USING (ticker)
            WHERE l.rn = 1 AND d.kind = 'game' AND l.status = 'active'
            """
        )
        cols = [d[0] for d in cur.description]
        kalshi_rows = [dict(zip(cols, r, strict=False)) for r in cur.fetchall()]
    except Exception as e:
        log.warning("rules facts s%s w%s: kalshi block failed: %s", season, week, e)

    for i in df.index:
        ph = _ml_prob(df.at[i, "home_moneyline"])
        pa = _ml_prob(df.at[i, "away_moneyline"])
        vegas_home = ph / (ph + pa) if ph and pa else None
        if vegas_home is not None:
            df.at[i, "vegas_home_prob"] = round(vegas_home, 4)
        km = next(
            (
                m
                for m in kalshi_rows
                if m["away_team"] == df.at[i, "away_team"]
                and m["home_team"] == df.at[i, "home_team"]
            ),
            None,
        )
        if km is None or km["prob"] is None:
            continue
        is_home_market = km["ticker"].endswith(f"-{df.at[i, 'home_team']}")
        prob_home = km["prob"] if is_home_market else 1 - km["prob"]
        df.at[i, "kalshi_home_prob"] = round(prob_home, 4)
        if vegas_home is None:
            continue
        gap = prob_home - vegas_home
        fee = FEE * prob_home * (1 - prob_home)
        width = (
            km["yes_ask"] - km["yes_bid"]
            if km["yes_ask"] is not None and km["yes_bid"] is not None
            else None
        )
        df.at[i, "dislocation_gap"] = round(gap, 4)
        df.at[i, "dislocation_fee"] = round(fee, 4)
        df.at[i, "dislocation_actionable"] = bool(abs(gap) > fee + (width or 0.02) / 2)
    return df


def build_facts_history(con, seasons: range | None = None) -> pd.DataFrame:
    """Facts for COMPLETED games. Live-only columns exist but are all-NaN, so
    live-only rules can never match history (their clauses require non-null)."""
    if seasons is None:
        lo, hi = con.execute(
            "SELECT min(season), max(season) FROM schedules WHERE result IS NOT NULL"
        ).fetchone()
        seasons = range(int(lo), int(hi) + 1)
    df = _base_frame(
        con,
        "result IS NOT NULL AND season BETWEEN ? AND ?",
        [seasons.start, seasons.stop - 1],
    )
    for c in _LIVE_COLS:
        df[c] = np.nan
    return df


# ── payload (API router + future MCP tool both call this) ────────────────────

_HIST_TTL_S = 3600.0
_hist_cache: dict[str, tuple[float, pd.DataFrame]] = {}


def _history_cached(con) -> pd.DataFrame:
    key = "hist"
    hit = _hist_cache.get(key)
    if hit and time.monotonic() - hit[0] < _HIST_TTL_S:
        return hit[1]
    df = build_facts_history(con)
    _hist_cache[key] = (time.monotonic(), df)
    return df


def _rule_public(rule: Rule) -> dict:
    return {
        "id": rule.id,
        "family": rule.family,
        "label": rule.label,
        "enabled": rule.enabled,
        "market": rule.market,
        "side": rule.side,
        "live_only": rule.live_only,
        "when": [{"field": c.field, "op": c.op, "value": c.value} for c in rule.when],
        "scope": rule.scope,
        "notes": rule.notes,
    }


def betting_rules_payload(week: int = 0, rule_id: str = "", backtest: bool = False) -> dict:
    """Evaluate the curated betting rules against the current (or given) week,
    optionally with historical backtests. Single entry point for the API
    router and the future MCP tool.

    week=0 -> next unplayed week; rule_id -> restrict to one rule (KeyError if
    unknown); backtest=True -> attach graded history per rule.
    """
    rules = load_rules()
    if rule_id:
        rules = [r for r in rules if r.id == rule_id]
        if not rules:
            raise KeyError(f"unknown rule id: {rule_id}")

    with read_conn(attach_kalshi=True) as con:
        season = int(
            con.execute(
                """
                SELECT coalesce(max(season) FILTER (WHERE result IS NULL), max(season))
                FROM schedules
                """
            ).fetchone()[0]
        )
        if week <= 0:
            row = con.execute(
                "SELECT min(week) FROM schedules WHERE season = ? AND result IS NULL",
                [season],
            ).fetchone()
            week = int(row[0]) if row and row[0] is not None else 1
        facts = build_facts(con, season, week)
        hist = _history_cached(con) if backtest else None

    hits_by_rule = {h["rule_id"]: h["hits"] for h in evaluate(rules, facts)}
    out_rules = []
    for rule in rules:
        entry = _rule_public(rule)
        entry["week_hits"] = hits_by_rule.get(rule.id, [])
        if backtest:
            bt = _run_backtest(rule, hist)  # param `backtest` shadows the function
            entry["backtest_summary"] = bt if bt.get("insufficient_history") else bt["summary"]
            entry["backtest_seasons"] = bt.get("seasons", [])
        else:
            entry["backtest_summary"] = None
        out_rules.append(entry)
    return {"season": season, "week": week, "rules": out_rules}


def rule_backtest_detail(rule_id: str) -> dict:
    """Full backtest for one rule: summary + per-season rows + graded hits."""
    rules = [r for r in load_rules() if r.id == rule_id]
    if not rules:
        raise KeyError(f"unknown rule id: {rule_id}")
    rule = rules[0]
    with read_conn() as con:
        hist = _history_cached(con)
    bt = backtest(rule, hist, include_hits=True)
    out = {"rule": _rule_public(rule)}
    if bt.get("insufficient_history"):
        out.update({"summary": bt, "seasons": [], "hits": []})
    else:
        out.update(
            {
                "summary": bt["summary"],
                "seasons": bt["seasons"],
                "hits": bt.get("hits", []),
                "hits_truncated": bt.get("hits_truncated", False),
            }
        )
    return out
