---
paths:
  - "web/ui/**"
---
# Jarvis SPA rules (web/ui)

- **Rebuild after every edit session:** `cd web/ui && npm run build`
  (runs `tsc -b` first — the Stop hook also runs tsc when ui files changed).
  Dev mode: `npm run dev` (:5173 proxies /api).
  `npm run lint` = oxlint + `scripts/check_tokens.mjs` + `scripts/check_lock.mjs`.

## The lockfile trap (this broke CI five times)

`npm install` on Windows writes an **incomplete** `package-lock.json`:
@tailwindcss/oxide ships a wasm32-wasi fallback as an optional dependency,
Windows never downloads it, and `--package-lock-only` does *not* ignore the
installed tree the way the docs claim — so npm reuses node_modules and omits
that package's own deps (`@emnapi/core`, `@emnapi/runtime`). Everything looks
fine locally; `npm ci` on Linux validates the whole graph and exits EUSAGE.

**Regenerate with node_modules ABSENT — that is the whole trick:**

```
cd web/ui && rm -rf node_modules
npm install --package-lock-only
npm ci                       # reinstall
```

**Reproduce CI's check on any machine:** `npm ci --os=linux --cpu=x64 --dry-run`.
`scripts/check_lock.mjs` (in `npm run lint`) walks the graph the same way and
fails locally instead of in CI. If it trips, run the block above.
- Routing: hub + detail pairs (`/coaches` + `/coach/:name`, `/h2h` +
  `/h2h/:a/:b`, `/matchup/:gameId`). Add routes in `App.tsx`; nav is the
  `LINKS` tuple in `components/Shell.tsx` (top-level tabs only — detail routes
  stay out).

## Tokens — the only place colour is defined

`src/styles/tokens.css` is the single source. Everything else consumes
`--color-*` via Tailwind utilities (`bg-surface`, `text-muted`,
`border-border`) or `var(--color-…)`. **Never type a hex, `rgba()`, or a
Tailwind `*-white` class in a component** — `check_tokens.mjs` fails the lint.
Genuine exceptions carry `token-ok: <reason>` on the line or in the comment
block above it (there are currently two, both documented in place).

- Elevation is lightness, not shadow: canvas → surface → surface-2 → surface-3.
- `--color-accent` is **fixed forever** and means "interactive". It is never
  reassigned per team; that is what made a link unrecognisable page to page.
- Team colour is identity only, ≤5% of the viewport — a rail, a wash, a logo
  backdrop. Get it from `useTeamTokens(code)` (or `useTeamPairTokens` on a
  two-team page, which demotes a colliding away side to neutral) and use the
  `text-team` / `bg-team-wash` / `rail-team` utilities. Server side this is
  `web/api/deps.py::team_tokens`, an Oklab clamp; `tests/unit/test_colors.py`
  checks all 32 teams for contrast and hue drift.
- No glow, no `backdrop-blur` outside the chat/palette scrim, no `.glass`.
  Those are lint errors now, not preferences.

## Components — extend these, don't hand-roll

`components/ui/`: `Panel` (the universal surface), `DataTable` (sticky header
+ measured sticky columns + density + sort + `tint`/`bar` cell slots +
`footNote` in `<tfoot>`), `PillGroup` (filters), `Tabs` (in-page nav),
`Select` (wraps a native `<select>`), `StatTile`, `Chip`, `Tip`, `PageHeader`,
`Toolbar` + `Field`. Import from `../components/ui`.

`components/charts/`: `LineChart`, `ScatterPlot`, `Radar`, `Sparkline`,
`ChartFrame`, `ChartTooltip`, `chartTheme`. Rules that are load-bearing:
categorical hues come from the fixed `SERIES` order and are never cycled;
scatter caps at 3 series (only the first three pass all-pairs CVD
separation); `--color-chart-ref` is reference lines only, never data; every
chart gets `ChartFrame`, which supplies the legend and the **table view** —
a tooltip must never be the only way to read a value.

Every stat column and filter gets a `help` string. Parth asked for this
explicitly and it is the main thing that makes the tables usable.

## Conventions

- Data fetching: typed `lib/api.ts` for shared endpoints; page-local
  interfaces + raw fetch acceptable for single-page endpoints.
- Density: `useDensity()` sets `data-density` on `<html>`; `DataTable` rows
  read `--row-h`. 28px is the floor (WCAG 2.2 needs 24px in-row targets).
- New page ⇒ Playwright spec in `web/ui/e2e/`. Legacy Streamlit (`legacy/`)
  is frozen — never extend it.
- Screenshots: `node scripts/shoot_ui.mjs <label>` → `web/ui/shots/<label>/`
  (NOT test-results/, which `playwright test` wipes). Look at them before
  claiming a visual change works.
- Knowledge content: chapters are `docs/knowledge/*.md` served by the API
  (edit → refresh, no rebuild). Diagrams are `web/ui/public/knowledge/*.svg`
  with transparent backgrounds and **baked** token hexes — they ship as
  `<img src>`, so a CSS variable would never reach them: `#98a2b0` strokes,
  `#e6edf3` text, `#4c8dff` accent, `#3fd08b` field, `#e96392` secondary.
  Colour inside a diagram is semantic, so keep the hues distinct if you edit.
