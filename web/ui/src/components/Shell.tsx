import { NavLink, Outlet } from "react-router-dom";

const LINKS = [
  ["/", "Command"],
  ["/leaders", "Leaders"],
  ["/players", "Players"],
  ["/coaches", "Coaches"],
  ["/refs", "Refs"],
  ["/schedule", "Schedule"],
  ["/betting", "Betting"],
  ["/markets", "Markets"],
  ["/news", "News"],
] as const;

export default function Shell() {
  return (
    <>
      <div className="shell-bg" />
      <header className="sticky top-0 z-40 border-b backdrop-blur-md"
              style={{ borderColor: "var(--stroke)", background: "rgba(4,7,12,.7)" }}>
        <nav className="mx-auto flex max-w-7xl items-center gap-6 px-6 py-3">
          <NavLink to="/" className="glow-text flex items-center gap-2 text-lg font-bold tracking-tight"
                   style={{ color: "var(--arc)" }}>
            <span className="pulse">◉</span> NFL COMMAND
          </NavLink>
          <div className="ml-auto flex items-center gap-1 text-sm">
            {LINKS.map(([to, label]) => (
              <NavLink key={to} to={to} end={to === "/"}
                className={({ isActive }) =>
                  `rounded-lg px-3 py-1.5 transition-colors ${
                    isActive ? "font-semibold" : "hover:bg-white/5"}`}
                style={({ isActive }) => ({
                  color: isActive ? "var(--arc)" : "var(--muted)",
                  textShadow: isActive ? "0 0 14px var(--accent-glow)" : undefined,
                })}>
                {label}
              </NavLink>
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
