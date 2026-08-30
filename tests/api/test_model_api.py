"""/api/model/* — the Model Lab's read surface.

Shapes, the empty-state contract, and one parity check: the report card's
holdout Brier must equal what train_model.py wrote to model_params, which
proves the router summarises model_predictions the same way training did.
"""

import pytest

from nfl_analytics.model import experiment as ex
from nfl_analytics.model.features import FEATURE_COLS

pytestmark = pytest.mark.api


def _needs_model(client):
    js = client.get("/api/model/report").json()
    if not js.get("available"):
        pytest.skip("no trained model in this DB (run `nfl train`, then `nfl fixture`)")
    return js


def test_report_card_shape_and_parity_with_model_params(client):
    js = _needs_model(client)
    h = js["holdout"]
    assert h["seasons"] == [2019, 2024]
    assert h["n_games"] > 500
    for k in ("brier_model", "brier_market", "brier_home_always", "calibration_gap"):
        assert isinstance(h[k], float), k
    assert 0.15 < h["brier_model"] < 0.30
    assert len(js["calibration"]) >= 8
    assert {r["season"] for r in js["by_season"]} >= set(range(2019, 2025))
    assert [c["feature"] for c in js["coefs"]] == js["config"]["features"]
    assert all(c["label"] and c["help"] for c in js["coefs"])
    assert js["config"]["features"][: len(FEATURE_COLS) - 1] == FEATURE_COLS[:-1]
    # parity: router's summarize() == the number training persisted
    from nfl_analytics.db import read_conn

    with read_conn() as con:
        persisted = con.execute("SELECT holdout_brier FROM model_params").fetchone()[0]
    assert h["brier_model"] == pytest.approx(persisted, abs=1e-6)


def test_week_predicts_every_game_with_contributions(client):
    _needs_model(client)
    js = client.get("/api/model/week").json()
    assert js["available"] and js["season"] and js["week"]
    games = js["games"]
    assert len(games) >= 10
    g = next(x for x in games if x["error"] is None)
    assert 0 < g["p_home_win"] < 1
    assert [c["feature"] for c in g["contributions"]] == client.get("/api/model/report").json()[
        "config"
    ]["features"]
    assert all(c["label"] for c in g["contributions"])
    assert "edge_pts" in g and "market_home_prob" in g
    # explicit season/week round-trips
    js2 = client.get(f"/api/model/week?season={js['season']}&week={js['week']}").json()
    assert [x["game_id"] for x in js2["games"]] == [x["game_id"] for x in games]


def test_ratings_all_32_teams_ranked(client):
    _needs_model(client)
    js = client.get("/api/model/ratings").json()
    teams = js["teams"]
    assert len(teams) == 32
    assert [t["rank"] for t in teams] == list(range(1, 33))
    assert teams[0]["net"] >= teams[-1]["net"]
    assert all(k in teams[0] for k in ("off_pass", "off_rush", "def_pass", "def_rush"))


def test_rating_history_rows_and_404(client):
    _needs_model(client)
    team = client.get("/api/model/ratings").json()["teams"][0]["team"]
    js = client.get(f"/api/model/ratings/{team}/history").json()
    if not js.get("available"):
        pytest.skip("model_rating_history not in this DB yet")
    assert js["team"] == team and len(js["rows"]) > 16
    r = js["rows"][-1]
    assert {"season", "week", "opponent", "net"} <= set(r)
    assert client.get("/api/model/ratings/ZZZ/history").status_code == 404


def test_experiments_tolerates_missing_log(client, monkeypatch, tmp_path):
    monkeypatch.setattr(ex, "EXPERIMENT_LOG", tmp_path / "none.jsonl")
    js = client.get("/api/model/experiments").json()
    assert js["available"] and js["runs"] == [] and js["best"] is None
    assert "nfl experiment" in js["how_to"]


def test_experiments_reads_runs_newest_first_and_picks_best(client, monkeypatch, tmp_path):
    path = tmp_path / "exp.jsonl"
    ex.append_log({"ts": "1", "note": "a", "metrics": {"brier_model": 0.23}}, path)
    ex.append_log({"ts": "2", "note": "b", "metrics": {"brier_model": 0.21}}, path)
    ex.append_log({"ts": "3", "note": "c", "metrics": {}}, path)
    monkeypatch.setattr(ex, "EXPERIMENT_LOG", path)
    js = client.get("/api/model/experiments?limit=2").json()
    assert [r["note"] for r in js["runs"]] == ["c", "b"]
    assert js["best"]["note"] == "b"
