---
name: new-page
description: Scaffold a new Jarvis page end-to-end (router, client, page, nav, tests). Use when adding a page/tab/section to the web app.
argument-hint: "[page name + what it shows]"
---

# New Jarvis page checklist

Build in this order — each step has a convention doc:

1. **Router** `web/api/routers/<name>.py` — bare APIRouter, full `/api/...`
   paths, `read_conn` + `rows_to_dicts`; register in BOTH places in
   `web/api/main.py` (import tuple + for-loop). Rules: `.claude/rules/api.md`.
2. **Types/client** — shared endpoint → `web/ui/src/lib/api.ts`; single-page →
   local interface + fetch.
3. **Page** `web/ui/src/pages/<Name>.tsx` — `Panel` grid, h1 + muted
   subcaption, theme vars. Route in `App.tsx`; top-level tabs go in the
   `NAV` tuple in `Shell.tsx`, secondary pages in `MORE`. Rules: `.claude/rules/frontend.md`.
4. **Verification (all four, not optional):**
   - smoke CHECK in `scripts/smoke_test.py` (fixture-compatible predicate)
   - tests/api case (shape + 404)
   - Playwright spec in `web/ui/e2e/`
   - `cd web/ui && npm run build` green
5. If the page needs a new view/table: run /new-view first.
