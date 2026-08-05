# Nightly Health Report

**Run:** 2026-08-04T06:47:21 · **Verdict: HEALTHY**

| Step | Result | Key number |
|---|---|---|
| Audit | ✅ pass | Real gaps found: 0 |
| Tests (warehouse + api) | ✅ pass | 116/116 passed |
| Smoke (live HTTP) | ✅ pass | 31/31 passed |
| Scheduler + logs | ✅ pass | 5/5 tasks last result 0 (NightlyHealth = this run, in progress) |
| Freshness | ✅ ok | kalshi 06:30 today · news +121 at 06:23 today · games through 2026-02-08 (offseason) |

## Detail

- **Scheduler:** NFL-WeeklyRefresh (8/2 18:01, rc 0), NFL-NewsPoll (06:28 today, rc 0),
  NFL-KalshiSnapshot (06:30 today, rc 0), NFL-SmokeTest (8/3 14:36, rc 0 — yesterday's
  0x800710E0 miss is resolved), NFL-NightlyHealth (06:45 today, code 267009 = still
  running, i.e. this run). Log tails (refresh/news/kalshi/smoke/jarvis) show no errors;
  last refresh mode=bootstrap fetched=78 failures=0, news gsis match 2175/2180.
- **Freshness:** latest completed game 2026-02-08 (SB LX); 2026 schedule loaded
  (272 games) — offseason, no staleness. Kalshi latest snapshot 2026-08-04 06:30
  (<24h, 6,544 rows). News poll ingested 121 new articles at 06:23 today (<24h;
  used as published-recency proxy — direct news.duckdb read not permitted headless).
