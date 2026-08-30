"""The experiment loop's pure parts: config edits, per-season rows, records
and the JSONL log. No warehouse — synthetic frames only."""

import json

import duckdb
import numpy as np
import pandas as pd
import pytest

from nfl_analytics.model import backtest as bt
from nfl_analytics.model import experiment as ex
from nfl_analytics.model.config import NET_RATING_SQL, net_rating
from nfl_analytics.model.features import FEATURE_COLS


def frame(seasons=range(2005, 2026), per_season=60, seed=1):
    rng = np.random.default_rng(seed)
    rows = []
    for s in seasons:
        for i in range(per_season):
            strength = rng.normal()
            p = 1 / (1 + np.exp(-(0.8 * strength + 0.3)))
            margin = 3 * strength + 1.5 + rng.normal(0, 10)
            rows.append(
                {
                    "game_id": f"{s}_{i:02d}",
                    "season": s,
                    "week": (i % 17) + 1,
                    "home_win": int(rng.random() < p),
                    "home_margin": margin,
                    "spread_line": round(3 * strength + rng.normal(0, 2)),
                    "market_home_prob": float(np.clip(p + rng.normal(0, 0.05), 0.05, 0.95)),
                    "d_off_pass": strength,
                    **{c: 0.0 for c in FEATURE_COLS if c != "d_off_pass"},
                }
            )
    return pd.DataFrame(rows)


def result(cfg=None):
    cfg = cfg or ex.ExperimentConfig()
    pred = bt.walk_forward(frame(), 2012, 2025, feature_cols=list(cfg.features))
    return ex.ExperimentResult(
        cfg, pred, bt.summarize(pred, 2019, 2024), bt.summarize(pred, 2025, 2025), 0.4
    )


def test_feature_edits_relative_and_absolute():
    base = ("a", "b", "c")
    assert ex.apply_feature_edits(base, None) == base
    assert ex.apply_feature_edits(base, "-b") == ("a", "c")
    assert ex.apply_feature_edits(base, "+d,-a") == ("b", "c", "d")
    assert ex.apply_feature_edits(base, "+b") == base  # idempotent add
    assert ex.apply_feature_edits(base, "x, y") == ("x", "y")


def test_validate_features_rejects_targets_and_unknowns():
    f = frame()
    ex.validate_features(f, tuple(FEATURE_COLS))
    with pytest.raises(ValueError, match="unknown"):
        ex.validate_features(f, ("d_off_pass", "d_weather"))
    with pytest.raises(ValueError, match="target/leak"):
        ex.validate_features(f, ("d_off_pass", "home_margin"))


def test_by_season_one_row_per_season_with_reused_metrics():
    r = result()
    rows = ex.by_season(r.pred)
    assert [x["season"] for x in rows] == list(range(2012, 2026))
    s = rows[0]
    g = r.pred[r.pred["season"] == 2012]
    assert s["games"] == len(g)
    assert s["brier_model"] == pytest.approx(
        bt.brier(g["home_win"].astype(float), g["p_home_win"]), abs=1e-4
    )
    assert s["gap"] == pytest.approx(s["brier_model"] - s["brier_market"], abs=1e-4)
    assert s["ats3_bets"] >= s["ats3_wins"] >= 0


def test_record_is_json_native_and_carries_delta(tmp_path):
    r = result(ex.ExperimentConfig(note="try it"))
    rec = ex.to_record(r, source="experiment", shipped={"brier_model": 0.25})
    text = json.dumps(rec)  # would raise on numpy scalars
    back = json.loads(text)
    assert back["note"] == "try it"
    assert back["source"] == "experiment"
    assert back["config"]["features"] == list(FEATURE_COLS)
    assert back["metrics"]["n_games"] == r.holdout["n_games"]
    assert back["delta_vs_shipped"]["brier"] == pytest.approx(
        r.holdout["brier_model"] - 0.25, abs=1e-5
    )
    assert back["metrics"]["bonus_brier"] is not None
    assert "note" not in back["config"]


def test_log_round_trip_newest_first_and_skips_corrupt_lines(tmp_path):
    path = tmp_path / "exp.jsonl"
    assert ex.read_log(path) == []
    ex.append_log({"ts": "1", "note": "first"}, path)
    path.open("a", encoding="utf-8").write("{not json\n")
    ex.append_log({"ts": "2", "note": "second"}, path)
    got = ex.read_log(path)
    assert [g["note"] for g in got] == ["second", "first"]
    assert ex.read_log(path, limit=1)[0]["note"] == "second"


def test_scorecard_mentions_shipped_delta():
    r = result()
    text = ex.scorecard(r, shipped={"brier_model": r.holdout["brier_model"] + 0.01})
    assert "better" in text and "market" in text and "holdout  2019-2024" in text


def test_net_rating_python_matches_sql():
    con = duckdb.connect()
    vals = {"r_off_pass": 0.12, "r_off_rush": -0.03, "r_def_pass": -0.05, "r_def_rush": 0.02}
    sql = (
        f"SELECT {NET_RATING_SQL} FROM (SELECT "
        + ", ".join(f"{v} AS {k}" for k, v in vals.items())
        + ")"
    )
    assert con.execute(sql).fetchone()[0] == pytest.approx(net_rating(*vals.values()))


def test_shipped_config_defaults_without_model_tables():
    con = duckdb.connect()
    cfg = ex.shipped_config(con)
    assert cfg.features == tuple(FEATURE_COLS)
    assert ex.shipped_metrics(con) is None
