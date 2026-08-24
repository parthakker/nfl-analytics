"""Betting rules: curated angles from data/betting_rules.json, evaluated
against the live week and graded against 1999+ history.

Thin HTTP shell — all logic lives in nfl_analytics.rules.betting_rules_payload
(shared with the future MCP tool). Kalshi/line-movement blocks degrade to NaN
inside build_facts (try/except per api.md), so a busy sidecar never 500s here.
"""

from fastapi import APIRouter, HTTPException

from nfl_analytics.rules import betting_rules_payload, rule_backtest_detail

router = APIRouter()


@router.get("/api/rules")
def rules_index(week: int = 0) -> dict:
    """All rules with this week's hits and a career backtest summary each."""
    return betting_rules_payload(week=week, backtest=True)


@router.get("/api/rules/{rule_id}/backtest")
def rule_backtest(rule_id: str) -> dict:
    """Per-season backtest rows + graded hit list for one rule."""
    try:
        return rule_backtest_detail(rule_id)
    except KeyError:
        raise HTTPException(404, f"unknown rule: {rule_id}") from None
