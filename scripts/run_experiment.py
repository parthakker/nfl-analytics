"""Run ONE model configuration through the walk-forward holdout — in seconds.

  nfl experiment                                  # shipped config, as a baseline
  nfl experiment --features -d_qb_out --note "no QB flag"
  nfl experiment --features +d_rest_sched,-d_rest
  nfl experiment --half-life 12 --carryover 0.5
  nfl experiment --source ridge --ridge-alpha 3
  nfl experiment --recency 6 --calib-window 6    # the gated-out drift controls
  nfl experiment --json                          # print the record for scripts/agents

Nothing is persisted to the warehouse — the shipped model is untouched. Each
run prints a scorecard against the shipped model and the market, and appends
one line to logs/model_experiments.jsonl (skip with --no-log). The Model Lab
page's Experiments tab reads that log.

--features takes either relative edits (`+col,-col`, applied to the shipped
list) or a full replacement list (`a,b,c`). Names are validated against the
feature frame, so a typo fails loudly, not deep inside sklearn.
"""

import argparse
import json
import sys
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from nfl_analytics.config import NFL_DB  # noqa: E402
from nfl_analytics.model import experiment as ex  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--features", help="+col,-col edits or a full a,b,c list")
    ap.add_argument("--half-life", type=float, help="ratings half-life in games")
    ap.add_argument("--carryover", type=float, help="season carryover 0-1")
    ap.add_argument("--source", choices=("ewma", "ridge"), help="ratings backend")
    ap.add_argument("--ridge-alpha", type=float, help="ridge penalty (ridge source only)")
    ap.add_argument("--recency", type=float, help="recency half-life in seasons (drift control)")
    ap.add_argument("--calib-window", type=int, help="Platt window in seasons (drift control)")
    ap.add_argument("--note", default="", help="what you were testing — shows in the log")
    ap.add_argument("--no-log", action="store_true", help="don't append to the experiment log")
    ap.add_argument("--json", action="store_true", help="print the JSON record instead of text")
    args = ap.parse_args()

    con = duckdb.connect(str(NFL_DB), read_only=True)
    try:
        cfg = ex.shipped_config(con)
        shipped = ex.shipped_metrics(con)
        cfg = ex.ExperimentConfig(
            features=ex.apply_feature_edits(cfg.features, args.features),
            half_life=args.half_life if args.half_life is not None else cfg.half_life,
            carryover=args.carryover if args.carryover is not None else cfg.carryover,
            ratings_source=args.source or cfg.ratings_source,
            ridge_alpha=args.ridge_alpha if args.ridge_alpha is not None else cfg.ridge_alpha,
            recency_half_life=args.recency,
            calibration_window=args.calib_window,
            note=args.note,
        )
        if not args.json:
            print(f"building features for {cfg.describe()} ...", flush=True)
        frame, _, _ = ex.build_frame(con, cfg)
        try:
            result = ex.run(con, cfg, frame)
        except ValueError as e:
            print(f"error: {e}", file=sys.stderr)
            return 2
    finally:
        con.close()

    record = ex.to_record(result, source="experiment", shipped=shipped)
    if not args.no_log:
        ex.append_log(record)
    if args.json:
        print(json.dumps(record, indent=1))
    else:
        print()
        print(ex.scorecard(result, shipped))
        if not args.no_log:
            print(f"\nlogged -> {ex.EXPERIMENT_LOG.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
