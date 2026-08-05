import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ScatterPlot, type ScatterPoint } from "../components/charts";
import GlassPanel from "../components/GlassPanel";
import Tip from "../components/Tip";
import { api, type LeaderRow, type LeadersResponse } from "../lib/api";
import { hexToRgba } from "../lib/color";
import { useMeta } from "../lib/MetaContext";

const FAMILIES = [
  ["fantasy", "Fantasy"], ["passing", "Passing"], ["rushing", "Rushing"],
  ["receiving", "Receiving"], ["defense", "Defense"], ["kicking", "Kicking"],
] as const;

const POSITIONS: Record<string, string[]> = {
  passing: ["QB", "RB", "WR", "TE"],
  rushing: ["QB", "RB", "WR", "TE", "FB"],
  receiving: ["RB", "WR", "TE", "FB"],
  fantasy: ["QB", "RB", "WR", "TE"],
  defense: ["DL", "LB", "DB"],
  kicking: [],
};

// qualification slider config + the auto-bump default when sorting a rate col
const QUAL: Record<string, { label: string; max: number; step: number; auto: number }> = {
  passing: { label: "min attempts", max: 400, step: 10, auto: 100 },
  rushing: { label: "min carries", max: 300, step: 5, auto: 50 },
  receiving: { label: "min targets", max: 150, step: 5, auto: 25 },
  fantasy: { label: "min games", max: 18, step: 1, auto: 4 },
  defense: { label: "min games", max: 18, step: 1, auto: 4 },
  kicking: { label: "min FG att", max: 40, step: 1, auto: 10 },
};

// scatter axes per family: x = volume, y = signature rate
const SCATTER: Record<string, { x: string; y: string }> = {
  passing: { x: "att", y: "epa_db" },
  rushing: { x: "att", y: "epa_rush" },
  receiving: { x: "tgt", y: "epa_tgt" },
  fantasy: { x: "touches", y: "ppr_pg" },
  defense: { x: "games", y: "tkl_pg" },
  kicking: { x: "fg_att", y: "fg_pct" },
};

const num = (v: unknown): number | null =>
  typeof v === "number" && Number.isFinite(v) ? v : null;

// Literal copies of tokens, needed where a hex (not a CSS var) is required:
// hexToRgba() maths and recharts fill props. TODO(wave 5): read these from
// the chart theme when this page migrates to <DataTable>/<ScatterPlot>.
const ACCENT_HEX = "#4c8dff"; // --color-accent
const CHART_1_HEX = "#3987e5"; // --color-chart-1

export default function Leaders() {
  const meta = useMeta();
  const nav = useNavigate();
  const [family, setFamily] = useState("fantasy");
  const [season, setSeason] = useState<number | undefined>();
  const [seasonType, setSeasonType] = useState("REG");
  const [position, setPosition] = useState("");
  const [sort, setSort] = useState<string | undefined>();
  const [dir, setDir] = useState("desc");
  const [qual, setQual] = useState(0);
  const [limit, setLimit] = useState(25);
  const [perGame, setPerGame] = useState(false);
  const [query, setQuery] = useState("");
  const [view, setView] = useState<"table" | "scatter">("table");
  const [qualOpen, setQualOpen] = useState(false);
  const [d, setD] = useState<LeadersResponse | null>(null);
  const debounce = useRef<number>(undefined);

  useEffect(() => {
    window.clearTimeout(debounce.current);
    debounce.current = window.setTimeout(() => {
      api.leaders({ family, season, seasonType, position: position || undefined,
                    sort, dir, qual, limit })
        .then(setD).catch(console.error);
    }, 250);
    return () => window.clearTimeout(debounce.current);
  }, [family, season, seasonType, position, sort, dir, qual, limit]);

  const pickFamily = (f: string) => {
    setFamily(f); setSort(undefined); setDir("desc"); setQual(0);
    if (position && !POSITIONS[f].includes(position)) setPosition("");
  };

  const pickSort = (key: string) => {
    const col = d?.columns.find((c) => c.key === key);
    if (sort === key || (!sort && d?.sort === key)) {
      setDir(dir === "desc" ? "asc" : "desc");
    } else {
      setSort(key); setDir("desc");
      // rate-sort guard: a 1-carry player must not top a rate board
      if (col && (col.kind === "rate" || col.kind === "pct") && qual === 0) {
        setQual(QUAL[family].auto);
      }
    }
  };

  const activeSort = d?.sort ?? sort ?? "";
  const rows = useMemo(() => {
    if (!d) return [];
    const q = query.trim().toLowerCase();
    return q ? d.rows.filter((r) => r.player.toLowerCase().includes(q)) : d.rows;
  }, [d, query]);

  // per-column leader values (for bold) + sorted-col max (for mini-bars)
  const colMax = useMemo(() => {
    const m: Record<string, number> = {};
    if (!d) return m;
    for (const c of d.columns) {
      for (const r of rows) {
        const v = num(r[c.key]);
        if (v != null && (!(c.key in m) || v > m[c.key])) m[c.key] = v;
      }
    }
    return m;
  }, [d, rows]);

  const display = (r: LeaderRow, key: string, kind: string): string => {
    const v = num(r[key]);
    if (v == null) return "—";
    if (perGame && kind === "count" && r.games > 0) return (v / r.games).toFixed(1);
    return v.toLocaleString();
  };

  const tint = (key: string, kind: string, v: number | null): React.CSSProperties => {
    if (v == null || !d || (kind !== "rate" && kind !== "pct")) return {};
    const lo = num(d.p10[key]);
    const hi = num(d.p90[key]);
    if (lo == null || hi == null) return {};
    if (v >= hi) return { color: "var(--arc)", fontWeight: 600,
                          background: hexToRgba(ACCENT_HEX, 0.1) };
    if (v <= lo) return { color: "#fb923c", background: "rgba(251,146,60,0.07)" };
    return {};
  };

  const scatterCfg = SCATTER[family];
  const scatterData = useMemo(() => {
    if (!d) return [];
    return d.rows
      .map((r) => ({
        ...r,
        x: num(r[scatterCfg.x]),
        y: num(r[scatterCfg.y]),
        label: r.player,
        // team ink identifies the dot; ScatterPlot falls back to slot 1
        color: hexToRgba(meta?.teams[r.team]?.glow?.startsWith("#")
          ? meta.teams[r.team].glow : CHART_1_HEX, 0.85),
      }))
      .filter((r) => r.x != null && r.y != null) as unknown as ScatterPoint[];
  }, [d, scatterCfg, meta]);

  if (!d) return <div className="space-y-5"><h1 className="text-2xl font-bold tracking-tight">Stat leaders</h1></div>;
  const qcfg = QUAL[family];
  const sortLabel = d.columns.find((c) => c.key === activeSort)?.label ?? activeSort;

  return (
    // breakout: this page earns more width than the shell's max-w-7xl column
    <div className="space-y-5" style={{ marginInline: "calc(50% - min(48vw, 55rem))" }}>
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Stat leaders</h1>
        <p className="text-sm" style={{ color: "var(--muted)" }}>
          Click a column to sort it, a name to open the player. Rate columns are
          tinted vs the qualified field (blue = top 10%, orange = bottom 10%).
        </p>
      </div>

      {/* filter bar */}
      <div className="flex flex-wrap items-center gap-2">
        {FAMILIES.map(([key, label]) => (
          <button key={key} onClick={() => pickFamily(key)}
            className="rounded-full border px-3 py-1 text-sm font-semibold"
            style={{ borderColor: family === key ? "var(--arc)" : "var(--stroke)",
                     color: family === key ? "var(--arc)" : "var(--muted)" }}>
            {label}
          </button>
        ))}
        {POSITIONS[family].length > 0 && (
          <>
            <span className="mx-1 h-5 w-px" style={{ background: "var(--stroke)" }} />
            {POSITIONS[family].map((p) => (
              <button key={p} onClick={() => setPosition(position === p ? "" : p)}
                className="rounded-full border px-2.5 py-0.5 text-xs font-semibold"
                style={{ borderColor: position === p ? "var(--arc)" : "var(--stroke)",
                         color: position === p ? "var(--arc)" : "var(--muted)" }}>
                {p}
              </button>
            ))}
          </>
        )}
      </div>

      <div className="flex flex-wrap items-center gap-2 text-sm">
        <select value={d.season}
                onChange={(e) => setSeason(+e.target.value)}
                className="rounded-lg border bg-transparent px-2 py-1 text-sm"
                style={{ borderColor: "var(--stroke)" }}>
          {d.seasons.map((s) => <option key={s} value={s} style={{ color: "#000" }}>{s}</option>)}
        </select>
        {(["REG", "POST", "ALL"] as const).map((st) => (
          <Tip key={st} text={st === "REG" ? "Regular season only" : st === "POST" ? "Playoffs only" : "Regular season + playoffs"}>
            <button onClick={() => setSeasonType(st)}
              className="rounded-lg border px-2.5 py-1 text-xs font-semibold"
              style={{ borderColor: seasonType === st ? "var(--arc)" : "var(--stroke)",
                       color: seasonType === st ? "var(--arc)" : "var(--muted)" }}>
              {st}
            </button>
          </Tip>
        ))}
        <span className="mx-1 h-5 w-px" style={{ background: "var(--stroke)" }} />
        {(["table", "scatter"] as const).map((v) => (
          <button key={v} onClick={() => setView(v)}
            className="rounded-lg border px-2.5 py-1 text-xs font-semibold"
            style={{ borderColor: view === v ? "var(--arc)" : "var(--stroke)",
                     color: view === v ? "var(--arc)" : "var(--muted)" }}>
            {v === "table" ? "Table" : "Chart"}
          </button>
        ))}
        <Tip text="Show counting stats (yards, TDs, receptions…) per game played. True rates like Y/A are unaffected.">
          <button onClick={() => setPerGame(!perGame)}
            className="rounded-full border px-3 py-1 text-xs font-semibold"
            style={{ borderColor: perGame ? "var(--arc)" : "var(--stroke)",
                     color: perGame ? "var(--arc)" : "var(--muted)" }}>
            Per game
          </button>
        </Tip>
        <label className="flex items-center gap-1.5 text-xs" style={{ color: "var(--muted)" }}>
          Show
          <select value={limit} onChange={(e) => setLimit(+e.target.value)}
                  className="rounded-lg border bg-transparent px-2 py-1 text-xs"
                  style={{ borderColor: "var(--stroke)", color: "var(--text)" }}>
            {[25, 50, 100].map((l) => (
              <option key={l} value={l} style={{ color: "#000" }}>Top {l}</option>
            ))}
          </select>
        </label>
        <input value={query} onChange={(e) => setQuery(e.target.value)}
               placeholder="find player…"
               className="ml-auto rounded-lg border bg-transparent px-2 py-1 text-sm outline-none"
               style={{ borderColor: "var(--stroke)", color: "var(--text)" }} />
      </div>

      {/* leader cards */}
      <div className="grid gap-3 sm:grid-cols-5">
        {d.rows.slice(0, 5).map((r, i) => (
          <Link key={r.player_id} to={`/player/${r.player_id}`}
                className="glass flex items-center gap-3 p-3 transition-transform hover:-translate-y-0.5">
            {r.headshot ? (
              <img src={r.headshot} alt="" className="h-10 w-10 rounded-full object-cover"
                   onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }} />
            ) : <span className="flex h-10 w-10 items-center justify-center rounded-full text-lg font-bold"
                      style={{ background: "var(--glass)", color: "var(--muted)" }}>{i + 1}</span>}
            <div className="min-w-0">
              <div className="truncate text-sm font-semibold">{r.player}</div>
              <div className="text-xs" style={{ color: "var(--muted)" }}>
                {r.team} · <span style={{ color: "var(--arc)" }} className="tabular-nums font-semibold">
                  {display(r, activeSort, d.columns.find((c) => c.key === activeSort)?.kind ?? "count")}
                </span> {sortLabel}
              </div>
            </div>
          </Link>
        ))}
      </div>

      {view === "scatter" ? (
        <GlassPanel title={`${d.label} — ${scatterCfg.x} vs ${scatterCfg.y} (qualified, ${d.season})`}>
          <ScatterPlot
            series={[{ name: `${d.label} (qualified)`, points: scatterData }]}
            xLabel={scatterCfg.x}
            yLabel={scatterCfg.y}
            height={440}
            meanX={num(d.league_avg[scatterCfg.x])}
            meanY={num(d.league_avg[scatterCfg.y])}
            onPointClick={(p) => nav(`/player/${(p as unknown as LeaderRow).player_id}`)}
            renderTooltip={(p) => {
              const r = p as unknown as LeaderRow;
              return (
                <>
                  <div className="font-semibold">{r.player} ({r.team})</div>
                  <div className="text-muted">
                    {scatterCfg.x}: <span className="tabular-nums text-ink">{p.x}</span> ·{" "}
                    {scatterCfg.y}: <span className="tabular-nums text-ink">{p.y}</span>
                  </div>
                </>
              );
            }}
            note="Dashed lines are the qualified-field average. Click a dot to open that player." />
        </GlassPanel>
      ) : (
        <GlassPanel title={`Top ${d.limit} — ${d.label}, ${d.season} ${seasonType === "ALL" ? "REG+POST" : seasonType}`}>
          <div className="relative mb-2 flex items-center gap-2 text-xs" style={{ color: "var(--muted)" }}>
            <span>
              {d.qualified.toLocaleString()} of {d.total_players.toLocaleString()} players qualify
              {qual > 0 ? ` (min ${qual} ${qcfg.label.replace("min ", "")})` : ""}
            </span>
            <button onClick={() => setQualOpen(!qualOpen)} className="hover:underline"
                    style={{ color: "var(--arc)" }}>
              adjust
            </button>
            {qualOpen && (
              <div className="absolute left-0 top-5 z-40 rounded-xl border p-3"
                   style={{ background: "var(--bg-1)", borderColor: "var(--stroke)" }}>
                <label className="flex items-center gap-2">
                  {qcfg.label}
                  <input type="range" min={0} max={qcfg.max} step={qcfg.step} value={qual}
                         onChange={(e) => setQual(+e.target.value)} className="w-40" />
                  <span className="tabular-nums font-semibold" style={{ color: "var(--text)" }}>{qual}</span>
                </label>
                <div className="mt-1.5 flex gap-3">
                  <button onClick={() => setQual(QUAL[family].auto)} className="hover:underline"
                          style={{ color: "var(--arc)" }}>auto ({QUAL[family].auto})</button>
                  <button onClick={() => setQual(0)} className="hover:underline"
                          style={{ color: "var(--muted)" }}>everyone</button>
                  <button onClick={() => setQualOpen(false)} className="ml-auto hover:underline"
                          style={{ color: "var(--muted)" }}>done</button>
                </div>
              </div>
            )}
          </div>
          <div className="scroll-x">
            <table className="w-max min-w-full whitespace-nowrap text-left text-[15px]">
              <thead>
                <tr style={{ color: "var(--muted)" }}>
                  <th className="sticky left-0 z-10 w-10 min-w-10 py-2 pr-2 font-medium" style={{ background: "var(--bg-1)" }}>#</th>
                  <th className="sticky z-10 min-w-56 py-2 pr-4 font-medium"
                      style={{ left: "2.5rem", background: "var(--bg-1)",
                               boxShadow: "8px 0 12px -8px rgba(0,0,0,0.7)" }}>Player</th>
                  {d.columns.map((c) => (
                    <th key={c.key} className="py-1.5 pr-3 font-medium">
                      <Tip text={c.help}>
                        <button onClick={() => pickSort(c.key)} className="hover:underline"
                          style={{ color: activeSort === c.key ? "var(--arc)" : undefined }}>
                          {c.label}{activeSort === c.key ? (d.dir === "desc" ? " ↓" : " ↑") : ""}
                        </button>
                      </Tip>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {rows.map((r, i) => (
                  <tr key={r.player_id} className="border-t transition-colors hover:bg-white/5"
                      style={{ borderColor: "var(--stroke)" }}>
                    <td className="sticky left-0 z-10 w-10 min-w-10 py-2 pr-2 text-xs tabular-nums"
                        style={{ color: "var(--muted)", background: "var(--bg-1)" }}>{i + 1}</td>
                    <td className="sticky z-10 min-w-56 py-2 pr-4"
                        style={{ left: "2.5rem", background: "var(--bg-1)",
                                 boxShadow: "8px 0 12px -8px rgba(0,0,0,0.7)" }}>
                      <span className="flex items-center gap-2">
                        {r.headshot && (
                          <img src={r.headshot} alt="" className="h-7 w-7 rounded-full object-cover"
                               onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }} />
                        )}
                        <span className="min-w-0">
                          <Link to={`/player/${r.player_id}`} className="font-medium hover:underline">
                            {r.player}
                          </Link>
                          <span className="ml-1.5 text-xs" style={{ color: "var(--muted)" }}>
                            {r.pos} · {r.team}
                          </span>
                        </span>
                      </span>
                    </td>
                    {d.columns.map((c) => {
                      const v = num(r[c.key]);
                      const isSort = c.key === activeSort;
                      const leader = v != null && v === colMax[c.key];
                      const barPct = isSort && v != null && colMax[c.key] > 0
                        ? Math.max(0, (v / colMax[c.key]) * 100) : 0;
                      return (
                        <td key={c.key}
                            className={`py-2 pr-4 tabular-nums ${leader ? "font-bold" : ""}`}
                            style={{
                              ...(isSort ? {
                                background: `linear-gradient(90deg, ${hexToRgba(ACCENT_HEX, 0.16)} ${barPct}%, transparent ${barPct}%)`,
                                color: "var(--arc)",
                              } : tint(c.key, c.kind, v)),
                            }}>
                          {display(r, c.key, c.kind === "count_g" ? "rate" : c.kind)}
                        </td>
                      );
                    })}
                  </tr>
                ))}
                <tr className="border-t italic" style={{ borderColor: "var(--stroke)", color: "var(--muted)" }}>
                  <td className="sticky left-0 z-10 w-10 min-w-10 py-2 pr-2" style={{ background: "var(--bg-1)" }} />
                  <td className="sticky z-10 min-w-56 py-2 pr-4 text-xs"
                      style={{ left: "2.5rem", background: "var(--bg-1)" }}>
                    Lg avg (qualified)
                  </td>
                  {d.columns.map((c) => {
                    const v = num(d.league_avg[c.key]);
                    const shown = v == null ? "—"
                      : perGame && c.kind === "count" && num(d.league_avg.games)
                        ? (v / d.league_avg.games!).toFixed(1)
                        : v.toLocaleString();
                    return <td key={c.key} className="py-1.5 pr-3 text-xs tabular-nums">{shown}</td>;
                  })}
                </tr>
              </tbody>
            </table>
          </div>
        </GlassPanel>
      )}
    </div>
  );
}
