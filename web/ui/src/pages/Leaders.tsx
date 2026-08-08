import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ScatterPlot, type ScatterPoint } from "../components/charts";
import { DataTable, Field, PageHeader, Panel, PillGroup, Select, Toolbar } from "../components/ui";
import type { Column } from "../components/ui";
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

/** Reads a token's computed value. recharts and hexToRgba need a real colour
 *  string, not a var() reference — this keeps the value single-sourced in
 *  tokens.css instead of duplicating the hex here, where it would drift. */
const token = (name: string) =>
  getComputedStyle(document.documentElement).getPropertyValue(name).trim();

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

  // DataTable's native `tint` slot wants -1..1; the board tints only the
  // top/bottom decile of the qualified field, so it's a step, not a gradient.
  const columns = useMemo<Column<LeaderRow>[]>(() => {
    if (!d) return [];
    const rank: Column<LeaderRow> = {
      key: "rank", label: "#", width: "2.5rem", sortable: false,
      help: "Rank in the current sort order",
      render: (_r, i) => <span className="text-micro tabular-nums text-muted">{i + 1}</span>,
    };
    const player: Column<LeaderRow> = {
      key: "player", label: "Player", sortable: false,
      help: "Click a name to open the player page",
      render: (r) => (
        <span className="flex min-w-56 items-center gap-2">
          {r.headshot && (
            <img src={r.headshot} alt="" className="h-7 w-7 rounded-full object-cover"
                 onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }} />
          )}
          <span className="min-w-0">
            <Link to={`/player/${r.player_id}`} className="font-medium hover:underline">
              {r.player}
            </Link>
            <span className="ml-1.5 text-micro text-muted">{r.pos} · {r.team}</span>
          </span>
        </span>
      ),
    };
    const stats = d.columns.map((col): Column<LeaderRow> => {
      const isSort = col.key === activeSort;
      const rateLike = col.kind === "rate" || col.kind === "pct";
      return {
        key: col.key, label: col.label, help: col.help, numeric: true,
        value: (r) => num(r[col.key]),
        // sorted column gets the in-cell leader bar…
        bar: isSort
          ? (r) => {
              const v = num(r[col.key]);
              return v != null && colMax[col.key] > 0 ? Math.max(0, v / colMax[col.key]) : null;
            }
          : undefined,
        // …every other rate column gets the decile tint
        tint: !isSort && rateLike
          ? (r) => {
              const v = num(r[col.key]);
              const lo = num(d.p10[col.key]);
              const hi = num(d.p90[col.key]);
              if (v == null || lo == null || hi == null) return null;
              return v >= hi ? 0.25 : v <= lo ? -0.25 : null;
            }
          : undefined,
        render: (r) => {
          const v = num(r[col.key]);
          const leader = v != null && v === colMax[col.key];
          return (
            <span className={`${isSort ? "text-accent" : ""}${leader ? " font-bold" : ""}`}>
              {display(r, col.key, col.kind === "count_g" ? "rate" : col.kind)}
            </span>
          );
        },
      };
    });
    return [rank, player, ...stats];
    // display closes over perGame; colMax over the filtered rows
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [d, activeSort, colMax, perGame]);

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
        color: hexToRgba(meta?.teams[r.team]?.tokens?.ink?.startsWith("#")
          ? meta.teams[r.team].tokens.ink : token("--color-chart-1"), 0.85),
      }))
      .filter((r) => r.x != null && r.y != null) as unknown as ScatterPoint[];
  }, [d, scatterCfg, meta]);

  if (!d) return <PageHeader title="Stat leaders" subtitle="Loading…" />;
  const qcfg = QUAL[family];
  const sortLabel = d.columns.find((c) => c.key === activeSort)?.label ?? activeSort;

  return (
    // breakout: this page earns more width than the shell's max-w-7xl column
    <div className="space-y-5" style={{ marginInline: "calc(50% - min(48vw, 55rem))" }}>
      <PageHeader
        title="Stat leaders"
        subtitle="Click a column to sort it, a name to open the player. Rate columns are tinted against the qualified field: blue is the top 10%, orange the bottom 10%." />

      <div className="flex flex-wrap items-center gap-3">
        <PillGroup
          ariaLabel="Stat family"
          options={FAMILIES.map(([value, label]) => ({ value, label }))}
          value={family}
          onChange={pickFamily} />
        {POSITIONS[family].length > 0 && (
          <PillGroup
            ariaLabel="Position" size="sm" clearable
            options={POSITIONS[family].map((x) => ({ value: x, label: x }))}
            value={position}
            onChange={setPosition} />
        )}
      </div>

      <Toolbar
        trailing={
          <input value={query} onChange={(e) => setQuery(e.target.value)}
                 placeholder="find player…"
                 aria-label="Find player"
                 className="rounded-[var(--radius-control)] border border-border bg-surface-2 px-2 py-1 text-body text-ink outline-none placeholder:text-faint" />
        }
      >
        <Select
          size="sm" ariaLabel="Season" value={d.season}
          onChange={(v) => setSeason(+v)}
          options={d.seasons.map((x) => ({ value: x, label: String(x) }))} />
        <PillGroup
          ariaLabel="Season type" size="sm"
          options={[
            { value: "REG", label: "REG", help: "Regular season only" },
            { value: "POST", label: "POST", help: "Playoffs only" },
            { value: "ALL", label: "ALL", help: "Regular season + playoffs" },
          ]}
          value={seasonType}
          onChange={(v) => setSeasonType(v as "REG" | "POST" | "ALL")} />
        <PillGroup
          ariaLabel="View" size="sm"
          options={[{ value: "table", label: "Table" }, { value: "scatter", label: "Chart" }]}
          value={view}
          onChange={(v) => setView(v as "table" | "scatter")} />
        <PillGroup
          ariaLabel="Per game" size="sm"
          options={[{ value: "per", label: "Per game",
                      help: "Show counting stats (yards, TDs, receptions…) per game played. True rates like Y/A are unaffected." }]}
          value={perGame ? "per" : ""}
          clearable
          onChange={() => setPerGame(!perGame)} />
        <Field label="Show">
          <Select
            size="sm" ariaLabel="Row limit" value={limit}
            onChange={(v) => setLimit(+v)}
            options={[25, 50, 100].map((l) => ({ value: l, label: `Top ${l}` }))} />
        </Field>
      </Toolbar>

      {/* leader cards */}
      <div className="grid gap-3 sm:grid-cols-5">
        {d.rows.slice(0, 5).map((r, i) => (
          <Link key={r.player_id} to={`/player/${r.player_id}`}
                className="flex items-center gap-3 rounded-[var(--radius-panel)] border border-border bg-surface p-3 transition-colors hover:border-accent/50 hover:bg-surface-2">
            {r.headshot ? (
              <img src={r.headshot} alt="" className="h-10 w-10 rounded-full object-cover"
                   onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }} />
            ) : <span className="flex h-10 w-10 items-center justify-center rounded-full bg-surface-2 text-h2 font-bold text-muted">{i + 1}</span>}
            <div className="min-w-0">
              <div className="truncate text-body font-semibold text-ink">{r.player}</div>
              <div className="text-micro text-muted">
                {r.team} · <span className="font-semibold tabular-nums text-accent">
                  {display(r, activeSort, d.columns.find((c) => c.key === activeSort)?.kind ?? "count")}
                </span> {sortLabel}
              </div>
            </div>
          </Link>
        ))}
      </div>

      {view === "scatter" ? (
        <Panel title={`${d.label} — ${scatterCfg.x} vs ${scatterCfg.y} (qualified, ${d.season})`}>
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
        </Panel>
      ) : (
        <Panel title={`Top ${d.limit} — ${d.label}, ${d.season} ${seasonType === "ALL" ? "REG+POST" : seasonType}`} flush>
          <div className="relative mb-2 flex items-center gap-2 px-4 text-xs text-muted">
            <span>
              {d.qualified.toLocaleString()} of {d.total_players.toLocaleString()} players qualify
              {qual > 0 ? ` (min ${qual} ${qcfg.label.replace("min ", "")})` : ""}
            </span>
            <button onClick={() => setQualOpen(!qualOpen)} className="text-accent hover:underline">
              adjust
            </button>
            {qualOpen && (
              <div className="absolute left-4 top-5 z-40 rounded-xl border border-border bg-surface p-3">
                <label className="flex items-center gap-2">
                  {qcfg.label}
                  <input type="range" min={0} max={qcfg.max} step={qcfg.step} value={qual}
                         onChange={(e) => setQual(+e.target.value)} className="w-40" />
                  <span className="tabular-nums font-semibold text-ink">{qual}</span>
                </label>
                <div className="mt-1.5 flex gap-3">
                  <button onClick={() => setQual(QUAL[family].auto)}
                          className="text-accent hover:underline">auto ({QUAL[family].auto})</button>
                  <button onClick={() => setQual(0)}
                          className="text-muted hover:underline">everyone</button>
                  <button onClick={() => setQualOpen(false)}
                          className="ml-auto text-muted hover:underline">done</button>
                </div>
              </div>
            )}
          </div>
          <DataTable
            columns={columns}
            rows={rows}
            rowKey={(r) => r.player_id}
            sort={{ key: activeSort, dir: d.dir === "asc" ? "asc" : "desc" }}
            onSort={pickSort}
            stickyCols={2}
            caption={`${d.label} leaders, ${d.season}`}
            empty="No players qualify — lower the minimum."
            footRow={
              <tr className="row-h italic text-muted">
                <td className="sticky left-0 z-10 border-t border-border bg-surface pl-3 pr-4" />
                <td className="sticky z-10 border-t border-border bg-surface pr-4 text-micro"
                    style={{ left: "2.5rem" }}>
                  Lg avg (qualified)
                </td>
                {d.columns.map((c) => {
                  const v = num(d.league_avg[c.key]);
                  const shown = v == null ? "—"
                    : perGame && c.kind === "count" && num(d.league_avg.games)
                      ? (v / d.league_avg.games!).toFixed(1)
                      : v.toLocaleString();
                  return (
                    <td key={c.key} className="border-t border-border pr-4 text-right text-micro tabular-nums">
                      {shown}
                    </td>
                  );
                })}
                <td aria-hidden className="border-t border-border" />
              </tr>
            } />
        </Panel>
      )}
    </div>
  );
}
