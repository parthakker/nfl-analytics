import { useEffect, useState } from "react";
import { api, type MarketRow } from "../lib/api";
import GlassPanel from "../components/GlassPanel";
import GlowLineChart from "../components/GlowLineChart";
import Sparkline from "../components/Sparkline";
import { useMeta } from "../lib/MetaContext";

const KINDS = [["game", "Games"], ["spread", "Spreads"], ["total", "Totals"],
               ["win_totals", "Win totals"], ["superbowl", "Super Bowl"]] as const;

export default function Markets() {
  const meta = useMeta();
  const [kind, setKind] = useState("game");
  const [rows, setRows] = useState<MarketRow[]>([]);
  const [hist, setHist] = useState<{ title: string; points: { ts: string; prob: number | null }[] } | null>(null);

  useEffect(() => {
    setHist(null);
    api.markets(kind).then((r) => setRows(r.markets)).catch(console.error);
  }, [kind]);

  const openHistory = (ticker: string) =>
    api.marketHistory(ticker).then(setHist).catch(console.error);

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Prediction markets</h1>
        <p className="text-sm" style={{ color: "var(--muted)" }}>
          Live Kalshi prices, snapshotted every 6h — click a card for its price history.
          Implied probability = market's chance the YES side wins.
        </p>
      </div>
      <div className="flex flex-wrap gap-2">
        {KINDS.map(([k, name]) => (
          <button key={k} onClick={() => setKind(k)}
            className="rounded-full border px-3 py-1 text-sm font-semibold"
            style={{ borderColor: kind === k ? "var(--arc)" : "var(--stroke)",
                     color: kind === k ? "var(--arc)" : "var(--muted)" }}>
            {name}
          </button>
        ))}
      </div>

      {hist && (
        <GlassPanel title={hist.title}>
          <GlowLineChart
            data={hist.points.map((p) => ({ ts: p.ts.slice(5, 16).replace("T", " "), prob: p.prob }))}
            xKey="ts"
            series={[{ key: "prob", name: "implied probability", color: "var(--arc)" }]} />
        </GlassPanel>
      )}

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {rows.map((m) => {
          const logo = (code: string | null) => code && meta?.teams[code]?.logo;
          return (
            <button key={m.ticker} onClick={() => openHistory(m.ticker)}
                    className="glass p-4 text-left transition-shadow hover:shadow-[0_0_28px_-6px_var(--accent-glow)]">
              <div className="flex items-center gap-2">
                {logo(m.away_team) && <img src={logo(m.away_team)!} className="h-6 w-6" alt="" />}
                {logo(m.home_team) && <img src={logo(m.home_team)!} className="h-6 w-6" alt="" />}
                <span className="truncate text-xs" style={{ color: "var(--muted)" }}>
                  {m.event_date ?? ""}
                </span>
                <span className="ml-auto"><Sparkline points={m.spark} /></span>
              </div>
              <div className="mt-2 line-clamp-2 text-sm font-medium">{m.title}</div>
              <div className="mt-2 flex items-baseline gap-3">
                <span className="glow-text text-2xl font-bold tabular-nums"
                      style={{ color: "var(--arc)" }}>
                  {m.prob != null ? `${Math.round(m.prob * 100)}%` : "—"}
                </span>
                {m.delta_24h != null && (
                  <span className="text-xs tabular-nums"
                        style={{ color: m.delta_24h >= 0 ? "#0ca30c" : "#d03b3b" }}>
                    {m.delta_24h >= 0 ? "▲" : "▼"} {Math.abs(m.delta_24h * 100).toFixed(1)} / 24h
                  </span>
                )}
                <span className="ml-auto text-xs" style={{ color: "var(--muted)" }}>
                  vol {m.volume ? Math.round(m.volume).toLocaleString() : "—"}
                </span>
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}
