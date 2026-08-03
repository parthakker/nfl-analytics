---
paths:
  - "web/ui/**"
---
# Jarvis SPA rules (web/ui)

- **Rebuild after every edit session:** `cd web/ui && npm run build`
  (runs `tsc -b` first — the Stop hook also runs tsc when ui files changed).
  Dev mode: `npm run dev` (:5173 proxies /api).
- Routing: hub + detail pairs (`/coaches` + `/coach/:name`, `/h2h` +
  `/h2h/:a/:b`, `/matchup/:gameId`). Add routes in `App.tsx`; nav is the
  `LINKS` tuple in `components/Shell.tsx` (top-level tabs only — detail routes
  stay out).
- Theming: everything reads CSS vars `--arc/--accent/--accent-glow/--stroke/
  --muted/--text`. Team accent = `t.glow` (server-side glow_safe) +
  `hexToRgba(t.glow, 0.5)` set as `--accent`/`--accent-glow` on the page root.
  Dual-team pages scope two divs or use explicit per-side colors (see
  Matchup.tsx banner gradient idiom).
- Reusable components: `GlassPanel` (universal card), `Chip`, `StatRing`,
  `GlowLineChart` (recharts house style), `Sparkline`, `FingerprintRadar`,
  `Countdown`. Extract before duplicating a third time.
- Tables: `w-full text-left text-sm`, muted thead, `border-t` rows with
  `hover:bg-white/5`, `tabular-nums` numerics, `—` for nulls, sticky header +
  `max-h overflow-y-auto` for long ones.
- `<option>` needs `style={{color:"#000"}}` (dark-theme workaround).
- Data fetching: typed `lib/api.ts` for shared endpoints; page-local
  interfaces + raw fetch acceptable for single-page endpoints.
- New page ⇒ Playwright spec in `web/ui/e2e/`. Legacy Streamlit (`legacy/`)
  is frozen — never extend it.
- Knowledge content: chapters are `docs/knowledge/*.md` served by the API
  (edit → refresh, no rebuild); diagrams in `web/ui/public/knowledge/*.svg`
  (transparent bg, #94a3b8 strokes, #22d3ee accent).
