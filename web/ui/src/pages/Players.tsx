import { useEffect, useState } from "react";
import { api, type NewsItem } from "../lib/api";
import GlassPanel from "../components/GlassPanel";
import GlowLineChart from "../components/GlowLineChart";

type Hit = { gsis_id: string; name: string; pos: string; team: string };

export default function Players() {
  const [q, setQ] = useState("");
  const [hits, setHits] = useState<Hit[]>([]);
  const [picked, setPicked] = useState<Hit | null>(null);
  const [seasons, setSeasons] = useState<Record<string, string | number | null>[]>([]);
  const [weekly, setWeekly] = useState<{ week: number; ppr: number | null }[]>([]);
  const [news, setNews] = useState<NewsItem[]>([]);
  const [chartSeason, setChartSeason] = useState<number | null>(null);
  const [allWeekly, setAllWeekly] = useState<{ season: number; week: number; ppr: number | null }[]>([]);

  useEffect(() => {
    if (q.length < 3) { setHits([]); return; }
    const id = setTimeout(() =>
      api.playerSearch(q).then((r) => setHits(r.hits)).catch(console.error), 250);
    return () => clearTimeout(id);
  }, [q]);

  const pick = async (h: Hit) => {
    setPicked(h);
    setHits([]);
    setQ(h.name);
    const d = await api.player(h.gsis_id);
    setSeasons(d.seasons);
    setAllWeekly(d.weekly);
    setNews(d.news);
    const latest = d.seasons[0]?.season as number | undefined;
    setChartSeason(latest ?? null);
  };

  useEffect(() => {
    setWeekly(allWeekly.filter((w) => w.season === chartSeason));
  }, [chartSeason, allWeekly]);

  return (
    <div className="space-y-5">
      <h1 className="text-2xl font-bold tracking-tight">Player explorer</h1>
      <div className="relative max-w-xl">
        <input value={q} onChange={(e) => { setQ(e.target.value); setPicked(null); }}
          placeholder="search any player since 2007…"
          className="glass w-full px-4 py-3 text-sm outline-none"
          style={{ color: "var(--text)" }} />
        {hits.length > 0 && !picked && (
          <div className="glass absolute z-10 mt-1 w-full overflow-hidden">
            {hits.map((h) => (
              <button key={h.gsis_id} onClick={() => pick(h)}
                className="block w-full px-4 py-2 text-left text-sm transition-colors hover:bg-white/10">
                <span className="font-medium">{h.name}</span>
                <span className="ml-2" style={{ color: "var(--muted)" }}>{h.pos} · {h.team}</span>
              </button>
            ))}
          </div>
        )}
      </div>

      {picked && (
        <div className="grid gap-6 lg:grid-cols-3">
          <GlassPanel title="Season lines (regular season)" className="lg:col-span-2">
            <div className="max-h-72 overflow-y-auto">
              <table className="w-full text-left text-sm">
                <thead className="sticky top-0" style={{ background: "var(--bg-1)" }}>
                  <tr style={{ color: "var(--muted)" }}>
                    {["Season", "G", "Pass yds", "Rush yds", "Rec", "Rec yds", "PPR"].map((h) => (
                      <th key={h} className="py-1.5 pr-2 font-medium">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {seasons.map((s, i) => (
                    <tr key={i} className="border-t tabular-nums"
                        style={{ borderColor: "var(--stroke)" }}>
                      <td className="py-1.5 pr-2">{s.season}</td>
                      <td className="py-1.5 pr-2">{s.games}</td>
                      <td className="py-1.5 pr-2">{s.pass_yds?.toLocaleString?.()}</td>
                      <td className="py-1.5 pr-2">{s.rush_yds?.toLocaleString?.()}</td>
                      <td className="py-1.5 pr-2">{s.rec}</td>
                      <td className="py-1.5 pr-2">{s.rec_yds?.toLocaleString?.()}</td>
                      <td className="py-1.5 font-semibold" style={{ color: "var(--arc)" }}>{s.ppr}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="mt-4">
              <div className="mb-1 flex items-center justify-between">
                <span className="text-xs" style={{ color: "var(--muted)" }}>
                  weekly PPR points
                </span>
                <select value={chartSeason ?? ""} onChange={(e) => setChartSeason(+e.target.value)}
                        className="rounded-lg border bg-transparent px-2 py-1 text-xs"
                        style={{ borderColor: "var(--stroke)" }}>
                  {[...new Set(allWeekly.map((w) => w.season))].sort((a, b) => b - a)
                    .map((s) => <option key={s} value={s} style={{ color: "#000" }}>{s}</option>)}
                </select>
              </div>
              <GlowLineChart data={weekly} xKey="week"
                series={[{ key: "ppr", name: "PPR points", color: "var(--arc)" }]} />
            </div>
          </GlassPanel>
          <GlassPanel title="Recent news">
            <ul className="space-y-3">
              {news.length === 0 && (
                <li className="text-sm" style={{ color: "var(--muted)" }}>no recent items</li>
              )}
              {news.map((n, i) => (
                <li key={i}>
                  <a href={n.url} target="_blank" rel="noreferrer"
                     className="text-sm font-medium hover:text-white">{n.headline}</a>
                  <div className="text-xs" style={{ color: "var(--muted)" }}>
                    {n.ts?.slice(0, 10)}
                  </div>
                </li>
              ))}
            </ul>
          </GlassPanel>
        </div>
      )}
    </div>
  );
}
