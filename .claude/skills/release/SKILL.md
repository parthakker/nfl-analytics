---
name: release
description: Commit ritual — test, build, docs check, conventional commit, push.
disable-model-invocation: true
---

# Release ritual

1. `python -m ruff check .` and `python -m pytest tests/unit -q` — both green.
2. If web/ui/src changed: `cd web/ui && npm run build` (includes tsc).
3. If scripts/ or src/nfl_analytics changed: `python -m pytest -m warehouse -q`.
4. If any API endpoint changed: confirm smoke CHECK + tests/api coverage exist.
5. Docs honesty pass: does CLAUDE.md / README / the relevant
   docs/dictionary page still tell the truth about what changed? Fix drift now.
6. Commit: conventional prefix (feat/fix/chore/test/docs/ci), imperative
   subject, body listing the what+why. NEVER commit *.duckdb files or data/
   (except the three curated JSONs). `git status` must be clean after.
7. Push only when Parth asked for a push.
