# Chat analyst evals

The living use-case suite for the Jarvis analyst: 28 questions across the four
usage moments (pregame research, gameday companion, postgame/learning,
fantasy). `questions.json` is the suite, `rubric.md` is the human scoring
pass, `runs/` holds transcripts (gitignored — each run is point-in-time).

## Running

```
python scripts/run_chat_evals.py --dry-run           # list + cost estimate
python scripts/run_chat_evals.py                     # full run (~$3-8, ~30-60 min)
python scripts/run_chat_evals.py --moment postgame   # one slice
python scripts/run_chat_evals.py --ids pre-01,day-07
python scripts/run_chat_evals.py --compare evals/runs/<older-dir>
```

**Costs real API money** — every question is a live `claude -p` call with the
chat endpoint's exact flags (imported from `web/api/routers/chat.py`, so flag
drift is impossible). Manual-only; never schedule it.

## When to re-run

- After ANY edit to `CLAUDE.md` (it is the chat's system prompt),
  `src/nfl_analytics/mcp_server.py`, or `web/api/routers/chat.py` → re-run the
  affected `--moment` slice with `--compare` against the last good run.
- Full run at the end of a feature wave.
- Keep the previous run's directory until the compare is clean.

## Reading a run

`summary.md` — pass/fail table with auto-check detail and cost. Auto checks
are cheap heuristics (mentions, tool selection, filter citation, latency);
they catch regressions, not quality. For quality, spot-read transcripts
against `rubric.md` (~10 min for a full run).

Questions tagged `expected_fail_until` document known gaps on purpose — they
should flip to passing when that phase lands, and their failure is annotated
(not counted as a regression) in the summary.
