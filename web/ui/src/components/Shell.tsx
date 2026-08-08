import { useEffect, useRef, useState } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import { useDensity, type Density } from "../lib/useDensity";
import CommandPalette from "./CommandPalette";
import { PALETTE_OPEN } from "../lib/palette";

/** Six sections plus More. Eleven flat tabs was already at the limit of what
 *  a person can scan, and the roadmap adds surfaces; grouping keeps the top
 *  row stable as things land. Hubs are plural, details singular. */
const NAV = [
  { to: "/", label: "Today" },
  { to: "/scores", label: "Scores" },
  { to: "/teams", label: "Teams" },
  { to: "/players", label: "Players" },
  { to: "/betting", label: "Betting" },
  { to: "/knowledge", label: "Learn" },
] as const;

const MORE = [
  { to: "/leaders", label: "Leaders" },
  { to: "/coaches", label: "Coaches" },
  { to: "/refs", label: "Refs" },
  { to: "/h2h", label: "H2H" },
  { to: "/markets", label: "Markets" },
  { to: "/news", label: "News" },
] as const;

const DENSITIES: { value: Density; label: string; title: string }[] = [
  { value: "compact", label: "S", title: "Compact rows" },
  { value: "default", label: "M", title: "Default rows" },
  { value: "comfortable", label: "L", title: "Comfortable rows" },
];

const linkClass = ({ isActive }: { isActive: boolean }) =>
  `rounded-[var(--radius-control)] px-3 py-1.5 transition-colors ${
    isActive ? "bg-accent-bg font-semibold text-accent" : "text-muted hover:bg-surface-2 hover:text-ink"
  }`;

export default function Shell() {
  const [density, setDensity] = useDensity();
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [moreOpen, setMoreOpen] = useState(false);
  const moreRef = useRef<HTMLDivElement>(null);
  const location = useLocation();

  useEffect(() => { setMoreOpen(false); }, [location.pathname]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setPaletteOpen((v) => !v);
      }
    };
    const onClick = (e: MouseEvent) => {
      if (moreRef.current && !moreRef.current.contains(e.target as Node)) setMoreOpen(false);
    };
    const onAsk = () => setPaletteOpen(true);
    window.addEventListener("keydown", onKey);
    window.addEventListener("mousedown", onClick);
    window.addEventListener(PALETTE_OPEN, onAsk);
    return () => {
      window.removeEventListener("keydown", onKey);
      window.removeEventListener("mousedown", onClick);
      window.removeEventListener(PALETTE_OPEN, onAsk);
    };
  }, []);

  const moreActive = MORE.some((m) => location.pathname.startsWith(m.to));

  return (
    <>
      <div className="shell-bg" />
      <header className="sticky top-0 z-40 border-b border-border bg-canvas">
        <nav className="mx-auto flex max-w-7xl items-center gap-4 px-6 py-3">
          <NavLink to="/" className="flex items-center gap-2 text-h2 font-bold tracking-tight text-accent">
            <span className="pulse">◉</span> NFL COMMAND
          </NavLink>

          <div className="ml-auto flex items-center gap-1 text-body">
            {NAV.map((l) => (
              <NavLink key={l.to} to={l.to} end={l.to === "/"} className={linkClass}>
                {l.label}
              </NavLink>
            ))}

            {/* A disclosure of plain nav links, not an ARIA menu: menu/menuitem
                would demand full arrow-key handling, and links that Tab and
                Escape already serve don't need it. */}
            <div className="relative" ref={moreRef}
                 onKeyDown={(e) => { if (e.key === "Escape") setMoreOpen(false); }}>
              <button
                type="button"
                aria-expanded={moreOpen}
                onClick={() => setMoreOpen((v) => !v)}
                className={`rounded-[var(--radius-control)] px-3 py-1.5 transition-colors ${
                  moreActive ? "bg-accent-bg font-semibold text-accent" : "text-muted hover:bg-surface-2 hover:text-ink"
                }`}
              >
                More ▾
              </button>
              {moreOpen && (
                <div className="absolute right-0 z-50 mt-1 w-44 overflow-hidden rounded-[var(--radius-control)] border border-border-strong bg-surface-2 py-1 shadow-lg">
                  {MORE.map((m) => (
                    <NavLink key={m.to} to={m.to}
                             className={({ isActive }) =>
                               `block px-3 py-1.5 text-body transition-colors ${
                                 isActive ? "bg-accent-bg text-accent" : "text-ink hover:bg-surface-3"}`}>
                      {m.label}
                    </NavLink>
                  ))}
                </div>
              )}
            </div>
          </div>

          <button
            type="button"
            onClick={() => setPaletteOpen(true)}
            aria-label="Open command palette"
            className="flex items-center gap-2 rounded-[var(--radius-control)] border border-border px-2.5 py-1.5 text-label text-muted transition-colors hover:border-border-strong hover:text-ink"
          >
            <span aria-hidden>⌕</span>
            <kbd className="text-micro">Ctrl K</kbd>
          </button>

          <div className="flex items-center rounded-[var(--radius-control)] border border-border"
               role="group" aria-label="Row density">
            {DENSITIES.map((d) => (
              <button key={d.value} type="button" title={d.title}
                      aria-pressed={density === d.value}
                      onClick={() => setDensity(d.value)}
                      className={`px-2 py-1 text-micro font-semibold first:rounded-l-[var(--radius-control)] last:rounded-r-[var(--radius-control)] ${
                        density === d.value ? "bg-accent-bg text-accent" : "text-faint hover:text-ink"
                      }`}>
                {d.label}
              </button>
            ))}
          </div>
        </nav>
      </header>

      <main className="mx-auto max-w-7xl px-6 py-8">
        <Outlet />
      </main>

      <CommandPalette open={paletteOpen} onClose={() => setPaletteOpen(false)} />
    </>
  );
}
