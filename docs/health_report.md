# Nightly Health Report

**Run:** 2026-08-07T06:46:32 · **Verdict: HEALTHY**

| Step | Result | Key number |
|---|---|---|
| Audit | ✅ pass | Real gaps found: 0 |
| Tests (warehouse + api) | ✅ pass | 132/132 passed |
| Smoke (live HTTP) | ✅ pass | 34/34 passed |
| Scheduler + logs | ✅ pass | 5/5 tasks last result 0 (NightlyHealth = this run, in progress) |
| Freshness | ✅ ok | news published 02:30 today · kalshi snapshot 06:30 today · 2026 schedule loaded (272 games) |

## Detail

- **Audit:** `nfl audit` clean — 0 real gaps; written to `docs/data_audit.md`.
- **Tests:** `pytest -m "warehouse or api"` → 132 passed, 0 failed
  (132/259 collected, 127 deselected). Up from 118 yesterday — the new
  `test_coach_def_tendencies` / `test_redzone_usage` warehouse suites and API
  additions are in the run.
- **Smoke:** 34/34 against the live HTTP surface at 06:45 (up from 31 —
  new endpoint CHECKs included).
- **Scheduler:** NFL-WeeklyRefresh (8/4 08:00, rc 0, next 8/11), NFL-NewsPoll
  (06:00 today, rc 0, next 12:00), NFL-KalshiSnapshot (06:30 today, rc 0, next
  12:30), NFL-SmokeTest (8/6 07:30, rc 0 — next run 07:30 today),
  NFL-NightlyHealth (06:45 today, code 267009 = still running, i.e. this run).
  All five Enabled.
- **Logs:** no errors in any tail. Latest lines: refresh `mode=weekly
  fetched=44 failures=0 rc=0` (8/4); news `fetched=2749 new=30 total=4445
  gsis_matched=2279/2286` (06:00); kalshi `markets=1304 total_rows=22642`
  (06:30); smoke `34/34 passed`. `health_runner.log` shows yesterday's
  headless run exiting 0.
- **Freshness:** offseason — latest completed game 2026-02-08 (SB LX);
  `games` tops out at season 2025 and `schedules` carries 2026 (272 games),
  so the in-season <8-day trailing check is not applicable. **News checked
  directly this run** (no proxy): `league_news` latest `published_ts`
  2026-08-07T02:30:44 — ~4h old, well under 24h. Kalshi checked via
  `kalshi_markets`: 64 open game markets returned with live prices (2026
  preseason + week 1); latest snapshot 06:30 today.

The news MCP tools (`league_news`) worked headlessly this run — the
poll-log-proxy fallback noted in the previous four reports is resolved.
