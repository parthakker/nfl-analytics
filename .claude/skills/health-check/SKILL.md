---
name: health-check
description: Nightly project health run — data audit, warehouse+api tests, smoke, log triage, freshness check. Writes docs/health_report.md and one line to logs/health.log.
disable-model-invocation: true
allowed-tools: Bash(python -m pytest:*), Bash(python -m nfl_analytics.cli:*), Bash(pytest:*), Bash(nfl:*), Bash(git status:*), Bash(git log:*), Bash(schtasks /Query:*), PowerShell(python -m pytest:*), PowerShell(python -m nfl_analytics.cli:*), PowerShell(schtasks /Query:*), Read, Grep, Glob, Write, Edit, mcp__nfl__query_warehouse, mcp__nfl__data_status
---

# Nightly health check

Run every step even if an earlier one fails — the report must cover all of
them. Collect results, then write the report. Keep total runtime under ~10
minutes.

1. **Audit:** `python -m nfl_analytics.cli audit` — note "Real gaps found: N".
2. **Tests:** `python -m pytest -m "warehouse or api" -q` against the real DB.
3. **Smoke:** `python -m nfl_analytics.cli smoke` (live-HTTP surface).
4. **Scheduler + logs:** `schtasks /Query /TN <each NFL-* task> /FO LIST` for
   last-run results; read the tail of each `logs/*.log` for errors.
5. **Freshness:** via `mcp__nfl__query_warehouse` — max(season, week) in
   games vs today's date (in-season, data should trail by <8 days); latest
   kalshi snapshot_ts and news published_ts should be <24h old.

**Report — overwrite `docs/health_report.md`:**
- Header: timestamp + one-word verdict (HEALTHY / DEGRADED / BROKEN).
- Status table: one row per step with pass/fail + the key number.
- **Only if something failed:** an "ACTION NEEDED" section — what broke, the
  exact error tail, and the suggested next command. No such section when green.

**Log line — append to `logs/health.log`:**
`<ISO timestamp> health: <verdict> audit=<n_gaps> tests=<pass>/<total> smoke=<pass>/<total> freshness=<ok|stale>`

If any step failed, end the run by stating the failure clearly (nonzero
outcome). Do NOT attempt fixes that write to databases or git — report only;
trivial fixes (e.g. a stale doc line) are allowed via Edit.
