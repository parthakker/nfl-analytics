import { NavLink, Outlet } from "react-router-dom";
import { useDensity, type Density } from "../lib/useDensity";

const LINKS = [
  ["/", "Command"],
  ["/leaders", "Leaders"],
  ["/players", "Players"],
  ["/coaches", "Coaches"],
  ["/refs", "Refs"],
  ["/schedule", "Schedule"],
  ["/h2h", "H2H"],
  ["/betting", "Betting"],
  ["/markets", "Markets"],
  ["/news", "News"],
  ["/knowledge", "Knowledge"],
] as const;

const DENSITIES: { value: Density; label: string; title: string }[] = [
  { value: "compact", label: "S", title: "Compact rows" },
  { value: "default", label: "M", title: "Default rows" },
  { value: "comfortable", label: "L", title: "Comfortable rows" },
];

export default function Shell() {
  const [density, setDensity] = useDensity();

  return (
    <>
      <div className="shell-bg" />
      <header className="sticky top-0 z-40 border-b border-border bg-canvas">
        <nav className="mx-auto flex max-w-7xl items-center gap-6 px-6 py-3">
          <NavLink to="/" className="flex items-center gap-2 text-h2 font-bold tracking-tight text-accent">
            <span className="pulse">◉</span> NFL COMMAND
          </NavLink>
          <div className="ml-auto flex items-center gap-1 text-body">
            {LINKS.map(([to, label]) => (
              <NavLink key={to} to={to} end={to === "/"}
                className={({ isActive }) =>
                  `rounded-[var(--radius-control)] px-3 py-1.5 transition-colors ${
                    isActive
                      ? "bg-accent-bg font-semibold text-accent"
                      : "text-muted hover:bg-surface-2 hover:text-ink"
                  }`}>
                {label}
              </NavLink>
            ))}
          </div>
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
    </>
  );
}
