import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, type NewsItem } from "../lib/api";
import GlassPanel from "../components/GlassPanel";
import { LineChart } from "../components/charts";
import { hexToRgba } from "../lib/color";
import { useMeta } from "../lib/MetaContext";
import { useTeamTokens } from "../lib/useTeamTokens";

type Info = {
  name: string; pos: string; team: string; headshot: string | null;
  rookie_season: number | null; last_season: number | null;
  draft_year: number | null; draft_round: number | null;
};

export default function PlayerPage() {
  const { gsis = "" } = useParams();
  const meta = useMeta();
  const [info, setInfo] = useState<Info | null>(null);
  const [seasons, setSeasons] = useState<Record<string, string | number | null>[]>([]);
  const [allWeekly, setAllWeekly] = useState<{ season: number; week: number; ppr: number | null }[]>([]);
  const [news, setNews] = useState<NewsItem[]>([]);
  const [chartSeason, setChartSeason] = useState<number | null>(null);
  const [err, setErr] = useState("");

  useEffect(() => {
    setErr(""); setInfo(null);
    api.player(gsis).then((d) => {
      setInfo(d.info as Info);
      setSeasons(d.seasons);
      setAllWeekly(d.weekly);
      setNews(d.news);
      setChartSeason((d.seasons[0]?.season as number | undefined) ?? null);
      window.scrollTo(0, 0);
    }).catch((e) => setErr(String(e)));
  }, [gsis]);

  // hooks must run before any early return
  const { style: teamStyle } = useTeamTokens(info?.team ?? null);

  if (err) return <p className="text-muted">Player not found. {err}</p>;
  if (!info) return null;
  const t = meta?.teams[info.team];
  const weekly = allWeekly.filter((w) => w.season === chartSeason);

  return (
    <div className="space-y-6" style={teamStyle}>
      <div className="rail-team relative overflow-hidden rounded-[var(--radius-panel)] border border-border bg-surface p-6"
           style={t ? { background: `linear-gradient(120deg, ${hexToRgba(t.color, 0.3)}, var(--color-surface) 60%)` } : undefined}>
        <div className="flex flex-wrap items-center gap-5">
          {info.headshot && (
            <img src={info.headshot} alt={info.name}
                 className="h-20 w-20 rounded-full object-cover"
                 onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }} />
          )}
          <div>
            <h1 className="text-2xl font-bold tracking-tight">{info.name}</h1>
            <p className="text-sm" style={{ color: "var(--muted)" }}>
              {info.pos}
              {t ? <> · <Link to={`/team/${info.team}`} className="hover:underline"
                              style={{ color: "var(--accent)" }}>{t.name}</Link></>
                 : info.team ? ` · ${info.team}` : ""}
              {info.draft_year != null && (
                <> · drafted {info.draft_year}{info.draft_round != null ? ` (round ${info.draft_round})` : ""}</>
              )}
              {info.rookie_season != null && <> · {info.rookie_season}–{info.last_season ?? "now"}</>}
            </p>
          </div>
          {t && <img src={t.logo} alt="" aria-hidden
                     className="pointer-events-none absolute -right-6 -top-8 h-40 w-40 opacity-10" />}
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <GlassPanel title="Season lines (regular season)" className="lg:col-span-2">
          <div className="max-h-72 overflow-y-auto">
            <table className="w-full text-left text-sm">
              <thead className="sticky top-0" style={{ background: "var(--bg-1)" }}>
                <tr style={{ color: "var(--muted)" }}>
                  {["Season", "G", "Pass yds", "Rush yds", "Rec", "Rec yds", "Std", "½PPR", "PPR"].map((h) => (
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
                    <td className="py-1.5 pr-2">{s.std}</td>
                    <td className="py-1.5 pr-2">{s.half_ppr}</td>
                    <td className="py-1.5 font-semibold" style={{ color: "var(--accent)" }}>{s.ppr}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="mt-4">
            <div className="mb-1 flex items-center justify-between">
              <span className="text-xs" style={{ color: "var(--muted)" }}>weekly PPR points</span>
              <select value={chartSeason ?? ""} onChange={(e) => setChartSeason(+e.target.value)}
                      className="rounded-lg border bg-transparent px-2 py-1 text-xs"
                      style={{ borderColor: "var(--stroke)" }}>
                {[...new Set(allWeekly.map((w) => w.season))].sort((a, b) => b - a)
                  .map((s) => <option key={s} value={s} style={{ color: "#000" }}>{s}</option>)}
              </select>
            </div>
            <LineChart data={weekly} xKey="week" xLabel="Week"
              series={[{ key: "ppr", name: "PPR points" }]} digits={1} />
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
                <div className="text-xs" style={{ color: "var(--muted)" }}>{n.ts?.slice(0, 10)}</div>
              </li>
            ))}
          </ul>
        </GlassPanel>
      </div>
    </div>
  );
}
