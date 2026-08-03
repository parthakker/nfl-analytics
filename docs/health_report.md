# Nightly Health Report

**Run:** 2026-08-03T14:36:02 · **Verdict: DEGRADED**

| Step | Result | Key number |
|---|---|---|
| Audit | ✅ pass | Real gaps found: 0 |
| Tests (warehouse + api) | ✅ pass | 71/71 passed |
| Smoke (live HTTP) | ✅ pass | 26/26 passed |
| Scheduler + logs | ⚠️ 1 task failed last run | NFL-SmokeTest last result 0x800710E0 |
| Freshness | ✅ ok | kalshi 12:30 today · news poll 12:00 today (+140) · games through 2026-02-08 (offseason) |

## Detail

- **Scheduler:** NFL-WeeklyRefresh (Sat 18:01, rc 0), NFL-NewsPoll (12:00 today, rc 0),
  NFL-KalshiSnapshot (12:30 today, rc 0) all green. NFL-NightlyHealth has never run via
  the scheduler (created 2026-08-03; first scheduled run 2026-08-04 06:45) — expected, not
  a failure. Log tails (refresh/news/kalshi/smoke/jarvis) show no errors; refresh 78 fetched
  0 failures, news gsis match 2139/2144.
- **Freshness:** latest completed game 2026-02-08 (SB LX) with 2026 schedules loaded —
  in offseason, no staleness. Kalshi latest snapshot 2026-08-03 12:30 (<24h). News poll
  added 140 articles at 2026-08-03 12:00 (<24h).

## ACTION NEEDED

**NFL-SmokeTest** scheduled task's last run (2026-08-03 09:12) returned
`-2147020576` (0x800710E0 — "the operator or administrator has refused the
request"), which usually means the 07:30 start was missed (machine asleep) and
the task isn't set to run when available. The smoke surface itself is fine —
manual runs at 12:57, 12:59, and 14:34 today all passed 26/26 — so this is a
scheduling miss, not a product failure.

Suggested next command:

```
schtasks /Run /TN NFL-SmokeTest
```

then confirm `Last Result: 0`, and consider enabling "Run task as soon as
possible after a scheduled start is missed" in Task Scheduler so overnight
sleep doesn't skip the 07:30 run.
