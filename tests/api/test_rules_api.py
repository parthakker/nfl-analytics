"""Shape contracts for the betting-rules endpoints."""

import pytest

pytestmark = pytest.mark.api


@pytest.fixture(scope="module")
def rules_payload(client):
    r = client.get("/api/rules")
    assert r.status_code == 200
    return r.json()


def test_rules_index_shape(rules_payload):
    js = rules_payload
    assert isinstance(js["season"], int) and isinstance(js["week"], int)
    rules = js["rules"]
    assert len(rules) >= 8
    ids = [r["id"] for r in rules]
    assert len(ids) == len(set(ids)) and "wind-under-15" in ids
    for r in rules:
        assert set(r) >= {
            "id",
            "family",
            "label",
            "enabled",
            "market",
            "side",
            "live_only",
            "when",
            "scope",
            "week_hits",
            "backtest_summary",
        }
        assert isinstance(r["week_hits"], list)
        # every rule carries a verdict: a graded summary or insufficient_history
        bt = r["backtest_summary"]
        assert isinstance(bt, dict)
        assert bt.get("insufficient_history") in (True, False)
        if not bt["insufficient_history"]:
            assert set(bt) >= {"bets", "wins", "losses", "pushes", "win_pct", "roi", "breakeven"}


def test_live_only_rules_have_no_backtest(rules_payload):
    live = [r for r in rules_payload["rules"] if r["live_only"]]
    assert live, "seed set should contain live-only rules"
    for r in live:
        assert r["backtest_summary"]["insufficient_history"] is True
        assert "tracking_since" in r["backtest_summary"]


def test_week_hits_are_flat_resolved_bets(rules_payload):
    for r in rules_payload["rules"]:
        for h in r["week_hits"]:
            assert set(h) >= {"game_id", "matchup", "side", "facts"}
            assert h["side"] in ("home", "away", "over", "under")
            if r["market"] != "total" and h["side"] in ("home", "away"):
                assert h["bet_team"] in h["matchup"]


def test_rule_backtest_detail(client):
    r = client.get("/api/rules/wind-under-15/backtest")
    assert r.status_code == 200
    js = r.json()
    assert js["rule"]["id"] == "wind-under-15"
    assert len(js["seasons"]) > 0
    row = js["seasons"][0]
    assert set(row) >= {"season", "bets", "wins", "losses", "pushes", "win_pct"}
    assert js["summary"]["bets"] == sum(s["bets"] for s in js["seasons"])
    assert isinstance(js["hits"], list) and js["hits"]
    assert {"game_id", "side", "outcome"} <= set(js["hits"][0])


def test_backtested_rules_report_significance(rules_payload):
    """A backtest without its sample size invites reading noise as an edge."""
    graded = [
        r for r in rules_payload["rules"] if not r["backtest_summary"].get("insufficient_history")
    ]
    assert graded
    for r in graded:
        bt = r["backtest_summary"]
        assert bt["signal"] in ("noise", "weak", "strong", "unknown")
        assert bt["decided"] == bt["wins"] + bt["losses"]
        if r["market"] != "moneyline":
            assert isinstance(bt["z_score"], float)


def test_disabled_rules_stay_in_the_catalog(rules_payload):
    """Rules a backtest killed are kept, disabled, so they aren't re-seeded."""
    by_id = {r["id"]: r for r in rules_payload["rules"]}
    dead = by_id["short-week-road-fav-fade"]
    assert dead["enabled"] is False
    assert not dead["week_hits"]


def test_unknown_rule_404(client):
    assert client.get("/api/rules/not-a-rule/backtest").status_code == 404


def test_explicit_week_param(client, max_season):
    js = client.get("/api/rules?week=1").json()
    assert js["week"] == 1
    assert js["season"] >= max_season
