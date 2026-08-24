"""Betting rules engine: schema validation, predicate ops, side resolution,
grading math. No database — synthetic pandas frames only."""

import numpy as np
import pandas as pd
import pytest

from nfl_analytics import rules as R

# ── synthetic frame helpers ──────────────────────────────────────────────────

BASE_ROW = {
    "game_id": "2024_01_BUF_MIA",
    "season": 2024,
    "week": 1,
    "season_type": "REG",
    "date": "Sun Sep 08",
    "away_team": "BUF",
    "home_team": "MIA",
    "spread_line": 3.0,
    "total_line": 44.5,
    "home_moneyline": -150,
    "away_moneyline": 130,
    "result": 7,  # home margin
    "total": 41,
}


def facts(*rows: dict) -> pd.DataFrame:
    return pd.DataFrame([{**BASE_ROW, **r} for r in (rows or [{}])])


def rule(**kw) -> R.Rule:
    doc = {
        "id": kw.pop("id", "t"),
        "family": kw.pop("family", "situational"),
        "label": "test",
        "bet": {"market": kw.pop("market", "spread"), "side": kw.pop("side", "home")},
        "when": kw.pop("when"),
        "scope": kw.pop("scope", {}),
    }
    assert not kw, kw
    return R.parse_rules({"version": 1, "rules": [doc]})[0]


# ── seed file ────────────────────────────────────────────────────────────────


def test_seed_file_loads_clean_and_stays_in_namespace():
    rules = R.load_rules()
    assert len(rules) >= 8
    ids = [r.id for r in rules]
    assert len(ids) == len(set(ids))
    assert "wind-under-15" in ids  # smoke check depends on this id
    for r in rules:
        for c in r.when:
            assert c.field in R.FIELDS, f"{r.id}: {c.field}"
    fams = {r.family for r in rules}
    assert fams == R.FAMILIES  # 2-3 rules per family, all families covered


def test_seed_live_only_split():
    rules = R.load_rules()
    by_id = {r.id: r for r in rules}
    assert not by_id["wind-under-15"].live_only
    assert not by_id["div-dog-plus7"].live_only
    assert by_id["total-drop-under"].live_only
    assert by_id["kalshi-dislocation"].live_only


# ── validation errors name the rule id ───────────────────────────────────────


@pytest.mark.parametrize(
    "patch",
    [
        {"when": [{"field": "nope_field", "op": ">=", "value": 1}]},
        {"when": [{"field": "wx_wind_mph", "op": "~=", "value": 1}]},
        {"when": [{"field": "wx_wind_mph", "op": "between", "value": [1]}]},
        {"when": [{"field": "wx_wind_mph", "op": "in", "value": []}]},
        {"when": [{"field": "wx_wind_mph", "op": "is_null", "value": 5}]},
        {"when": [{"field": "season_type", "op": "abs_gte", "value": 2}]},  # str field
        {"when": []},
        {"family": "vibes"},
        {"bet": {"market": "parlay", "side": "home"}},
        {"bet": {"market": "spread", "side": "sharp"}},
        {"bet": {"market": "total", "side": "home"}},  # totals need over/under
        {"bet": {"market": "spread", "side": "under"}},  # and vice versa
        {"scope": {"week": 1}},
    ],
)
def test_bad_rule_error_names_the_rule_id(patch):
    doc = {
        "version": 1,
        "rules": [
            {
                "id": "my-broken-rule",
                "family": "situational",
                "label": "x",
                "bet": {"market": "spread", "side": "home"},
                "when": [{"field": "spread_line", "op": ">=", "value": 3}],
                **patch,
            }
        ],
    }
    with pytest.raises(ValueError, match="my-broken-rule"):
        R.parse_rules(doc)


def test_duplicate_id_rejected():
    r = {
        "id": "dup",
        "family": "situational",
        "label": "x",
        "bet": {"market": "spread", "side": "home"},
        "when": [{"field": "week", "op": ">=", "value": 1}],
    }
    with pytest.raises(ValueError, match="dup"):
        R.parse_rules({"version": 1, "rules": [r, dict(r)]})


# ── predicate ops ────────────────────────────────────────────────────────────


def hits_of(r: R.Rule, df: pd.DataFrame) -> list[str]:
    (res,) = R.evaluate([r], df)
    return [h["game_id"] for h in res["hits"]]


def test_abs_gte_matches_both_signs():
    r = rule(when=[{"field": "spread_line", "op": "abs_gte", "value": 7}])
    df = facts(
        {"game_id": "a", "spread_line": 7.5},
        {"game_id": "b", "spread_line": -9.0},
        {"game_id": "c", "spread_line": 6.5},
        {"game_id": "d", "spread_line": np.nan},
    )
    assert hits_of(r, df) == ["a", "b"]


def test_between_in_and_null_ops():
    df = facts(
        {"game_id": "a", "total_line": 40.0},
        {"game_id": "b", "total_line": 55.0},
        {"game_id": "c", "total_line": np.nan},
    )
    r = rule(when=[{"field": "total_line", "op": "between", "value": [38, 45]}])
    assert hits_of(r, df) == ["a"]
    r = rule(when=[{"field": "total_line", "op": "is_null"}])
    assert hits_of(r, df) == ["c"]
    r = rule(when=[{"field": "home_team", "op": "in", "value": ["MIA", "NYJ"]}])
    assert len(hits_of(r, df)) == 3


def test_nan_never_matches_even_not_equal():
    df = facts({"game_id": "a", "wx_wind_mph": np.nan})
    assert hits_of(rule(when=[{"field": "wx_wind_mph", "op": "!=", "value": 5}]), df) == []
    assert hits_of(rule(when=[{"field": "wx_wind_mph", "op": ">=", "value": 0}]), df) == []


def test_clauses_and_together_and_scope_filters():
    r = rule(
        when=[
            {"field": "wx_wind_mph", "op": ">=", "value": 15},
            {"field": "wx_is_indoor", "op": "==", "value": False},
        ],
        scope={"season_type": "REG"},
        market="total",
        side="under",
    )
    df = facts(
        {"game_id": "windy", "wx_wind_mph": 18, "wx_is_indoor": False},
        {"game_id": "dome", "wx_wind_mph": 18, "wx_is_indoor": True},
        {"game_id": "calm", "wx_wind_mph": 4, "wx_is_indoor": False},
        {"game_id": "post", "wx_wind_mph": 18, "wx_is_indoor": False, "season_type": "POST"},
    )
    assert hits_of(r, df) == ["windy"]


def test_missing_column_is_treated_as_nan():
    """History frames lack live columns; the clause must not blow up."""
    df = facts({"game_id": "a"}).drop(columns=["total_line"], errors="ignore")
    r = rule(when=[{"field": "spread_move", "op": "abs_gte", "value": 1.5}])
    assert hits_of(r, df) == []


# ── side resolution ──────────────────────────────────────────────────────────


def one_hit(r, df):
    got = R.evaluate([r], df)[0]["hits"]
    return got[0] if got else None


def test_favorite_underdog_from_spread_sign():
    when = [{"field": "week", "op": ">=", "value": 1}]
    home_fav = facts({"spread_line": 3.0})  # positive = home favored (gotcha #6)
    away_fav = facts({"spread_line": -3.0})
    pickem = facts({"spread_line": 0.0})
    assert one_hit(rule(when=when, side="favorite"), home_fav)["side"] == "home"
    assert one_hit(rule(when=when, side="favorite"), away_fav)["side"] == "away"
    assert one_hit(rule(when=when, side="underdog"), home_fav)["side"] == "away"
    assert one_hit(rule(when=when, side="underdog"), away_fav)["bet_team"] == BASE_ROW["home_team"]
    assert one_hit(rule(when=when, side="underdog"), pickem) is None  # unresolvable


def test_rested_side_from_rest_edge_sign():
    when = [{"field": "rest_edge_days", "op": "abs_gte", "value": 3}]
    r = rule(when=when, side="rested")
    assert one_hit(r, facts({"rest_edge_days": 4}))["side"] == "home"
    assert one_hit(r, facts({"rest_edge_days": -3}))["side"] == "away"
    assert one_hit(r, facts({"rest_edge_days": 0})) is None


def test_cheap_side_from_dislocation_gap_sign():
    # negative gap = kalshi below vegas on home = home is cheap on Kalshi
    when = [{"field": "dislocation_gap", "op": "abs_gte", "value": 0.04}]
    r = rule(when=when, market="kalshi", side="cheap_side")
    assert one_hit(r, facts({"dislocation_gap": -0.05}))["side"] == "home"
    assert one_hit(r, facts({"dislocation_gap": 0.06}))["side"] == "away"


# ── grading math ─────────────────────────────────────────────────────────────

WHEN_ALL = [{"field": "week", "op": ">=", "value": 1}]
VIG = 100.0 / 110.0


def test_spread_grading_cover_push_loss():
    r = rule(when=WHEN_ALL, market="spread", side="home")
    hist = facts(
        {"game_id": "w", "spread_line": 3.0, "result": 7},  # home covers
        {"game_id": "p", "spread_line": 3.0, "result": 3},  # push
        {"game_id": "l", "spread_line": 3.0, "result": 0},  # no cover
    )
    bt = R.backtest(r, hist)
    s = bt["summary"]
    assert (s["wins"], s["losses"], s["pushes"]) == (1, 1, 1)
    assert s["win_pct"] == 0.5  # pushes excluded
    assert s["profit_units"] == round(VIG - 1.0, 2)
    assert s["breakeven"] == 0.524 and s["profitable"] is False


def test_away_spread_grading_flips_the_line():
    r = rule(when=WHEN_ALL, market="spread", side="away")
    hist = facts({"spread_line": 3.0, "result": 0})  # home fails to cover -> away wins
    assert R.backtest(r, hist)["summary"]["wins"] == 1


def test_total_grading_and_push():
    r = rule(when=WHEN_ALL, market="total", side="under")
    hist = facts(
        {"game_id": "w", "total_line": 44.5, "total": 41},
        {"game_id": "p", "total_line": 41.0, "total": 41},
        {"game_id": "l", "total_line": 37.5, "total": 41},
    )
    s = R.backtest(r, hist)["summary"]
    assert (s["wins"], s["losses"], s["pushes"]) == (1, 1, 1)


def test_moneyline_grading_uses_actual_odds():
    r = rule(when=WHEN_ALL, market="moneyline", side="underdog")
    hist = facts(
        # away favored -> underdog = home at +150; home wins by 7
        {"game_id": "w", "spread_line": -3.0, "home_moneyline": 150, "result": 7},
        # home dog loses
        {"game_id": "l", "spread_line": -3.0, "home_moneyline": 150, "result": -7},
    )
    s = R.backtest(r, hist)["summary"]
    assert s["profit_units"] == 0.5  # +1.5 - 1.0
    assert s["roi"] == 0.25
    assert s["profitable"] is True  # ML profitability = positive ROI


def test_ungradeable_rows_are_dropped():
    r = rule(when=WHEN_ALL, market="spread", side="home")
    hist = facts({"result": np.nan}, {"spread_line": np.nan})
    assert R.backtest(r, hist)["insufficient_history"] is True


def test_live_only_rule_reports_insufficient_history():
    r = rule(when=[{"field": "spread_move", "op": "abs_gte", "value": 1.5}])
    hist = facts({"spread_move": 2.0})  # even if a column sneaks in, no grading
    bt = R.backtest(r, hist)
    assert bt["insufficient_history"] is True
    assert bt["tracking_since"] == R.TRACKING_SINCE


def test_backtest_per_season_rows():
    r = rule(when=WHEN_ALL, market="spread", side="home")
    hist = facts(
        {"game_id": "a", "season": 2023, "result": 10},
        {"game_id": "b", "season": 2024, "result": 10},
        {"game_id": "c", "season": 2024, "result": -10},
    )
    bt = R.backtest(r, hist, include_hits=True)
    assert [row["season"] for row in bt["seasons"]] == [2023, 2024]
    assert bt["seasons"][1]["bets"] == 2
    assert len(bt["hits"]) == 3
    assert {h["outcome"] for h in bt["hits"]} == {"win", "loss"}
