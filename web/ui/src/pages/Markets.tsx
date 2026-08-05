import { useEffect, useState } from "react";
import { api, type MarketRow } from "../lib/api";
import { LineChart, Sparkline } from "../components/charts";
import { PageHeader, Panel, PillGroup } from "../components/ui";
import { useMeta } from "../lib/MetaContext";

const KINDS = [
  { value: "game", label: "Games" },
  { value: "spread", label: "Spreads" },
  { value: "total", label: "Totals" },
  { value: "win_totals", label: "Win totals" },
  { value: "superbowl", label: "Super Bowl" },
];

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

  const logo = (code: string | null) => code && meta?.teams[code]?.logo;

  return (
    <div className="space-y-4">
      <PageHeader
        title="Prediction markets"
        subtitle="Live Kalshi prices, snapshotted every 6 hours. Implied probability is the market's chance the YES side wins. Click a card for its price history."
      />

      <PillGroup ariaLabel="Market type" options={KINDS} value={kind} onChange={setKind} />

      {hist && (
        <Panel
          title={hist.title}
          actions={
            <button type="button" onClick={() => setHist(null)}
                    className="text-label text-muted hover:text-ink">
              close
            </button>
          }
        >
          <LineChart
            data={hist.points.map((p) => ({ ts: p.ts.slice(5, 16).replace("T", " "), prob: p.prob }))}
            xKey="ts" xLabel="Snapshot"
            series={[{ key: "prob", name: "implied probability" }]}
            reference={{ y: 0.5, label: "coin flip" }} />
        </Panel>
      )}

      {rows.length === 0 && (
        <p className="text-body text-muted">No open markets in this category right now.</p>
      )}

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {rows.map((m) => (
          <button
            key={m.ticker}
            onClick={() => openHistory(m.ticker)}
            className="rounded-[var(--radius-panel)] border border-border bg-surface p-4 text-left transition-colors hover:border-border-strong hover:bg-surface-2"
          >
            <div className="flex items-center gap-2">
              {logo(m.away_team) && <img src={logo(m.away_team)!} className="h-6 w-6" alt="" />}
              {logo(m.home_team) && <img src={logo(m.home_team)!} className="h-6 w-6" alt="" />}
              <span className="truncate text-micro text-muted">{m.event_date ?? ""}</span>
              <span className="ml-auto"><Sparkline points={m.spark} /></span>
            </div>
            <div className="mt-2 line-clamp-2 text-body font-medium text-ink">{m.title}</div>
            <div className="mt-2 flex items-baseline gap-3">
              <span className="font-display text-h1 font-bold text-accent">
                {m.prob != null ? `${Math.round(m.prob * 100)}%` : "—"}
              </span>
              {m.delta_24h != null && (
                <span className={`text-micro tabular-nums ${
                  m.delta_24h >= 0 ? "text-positive" : "text-negative"
                }`}>
                  {m.delta_24h >= 0 ? "▲" : "▼"} {Math.abs(m.delta_24h * 100).toFixed(1)} / 24h
                </span>
              )}
              <span className="ml-auto text-micro text-muted">
                vol {m.volume ? Math.round(m.volume).toLocaleString() : "—"}
              </span>
            </div>
          </button>
        ))}
      </div>
    </div>
  );
}
