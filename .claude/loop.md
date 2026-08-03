# Maintenance loop for this repo

Each iteration, in order — small fixes are yours, big findings get reported:

1. `git status` — uncommitted work piling up? Note it, don't commit unasked.
2. Tail `logs/health.log`, `logs/refresh.log`, `logs/smoke.log` — any new
   failures since last iteration? Investigate the first one.
3. `python -m pytest tests/unit -q` — fix trivial breaks (imports, renamed
   columns); report anything structural.
4. In-season freshness: max(season/week) in games vs the calendar; stale >8
   days during the season means the Tuesday refresh failed — check
   refresh.log, do NOT auto-run a refresh while other work may be running.
5. Docs drift: does CLAUDE.md still match reality (task list, table coverage)?
   Fix one-liners; flag rewrites.

Keep iterations short. If everything is green, say so in one line and stop.
