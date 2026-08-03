---
name: refresh-data
description: Refresh the warehouse from nflverse and verify the result.
disable-model-invocation: true
argument-hint: "[--full | --bootstrap]"
---

# Refresh data

1. Preflight: make sure nothing holds a write lock — explore.cmd (DuckDB UI)
   must be closed; check `logs/refresh.log` tail for an already-running refresh.
2. Run `python -m nfl_analytics.cli refresh $ARGUMENTS`
   - no flag: weekly mode (current + last season assets + schedules)
   - `--full`: every season in the manifest
   - `--bootstrap`: fresh-clone download (~2 GB, resumable)
   This downloads, runs fetch_weather, rebuilds warehouse + views, snapshots
   Vegas lines.
3. Verify: the build output must end with "All tables loaded" and
   "travel sanity OK"; then run `python -m pytest -m warehouse -q`.
4. Report: assets fetched, any FAILURES lines, row-count anomalies, and the
   refresh.log line. If a download failed with "no candidate matched",
   nflverse likely renamed an asset — check their releases page before
   editing the manifest in scripts/refresh_data.py.
