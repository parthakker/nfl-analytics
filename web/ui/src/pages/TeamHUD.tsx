import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  api, type NewsItem, type RosterPlayer, type TeamDetail, type TeamScheduleGame,
} from "../lib/api";
import { hexToRgba } from "../lib/color";
import { useMeta } from "../lib/MetaContext";
import GlassPanel from "../components/GlassPanel";
import GlowLineChart from "../components/GlowLineChart";
import StatRing from "../components/StatRing";

const SEASONS = Array.from({ length: 2025 - 2007 + 1 }, (_, i) => 2025 - i);

export default function TeamHUD() {
  const { code = "" } = useParams();
  const meta = useMeta();
  const t = meta?.teams[code.toUpperCase()];
  const [season, setSeason] = useState(2025);
  const [detail, setDetail] = useState<TeamDetail | null>(null);
  const [epa, setEpa] = useState<{ week: number; off: number | null; def: number | null }[]>([]);
  const [roster, setRoster] = useState<RosterPlayer[]>([]);
  const [posFilter, setPosFilter] = useState("");
  const [sched, setSched] = useState<TeamScheduleGame[]>([]);
  const [news, setNews] = useState<NewsItem[]>([]);

  const c = code.toUpperCase();
  useEffect(() => {
    if (!c) return;
    api.team(c, season).then(setDetail).catch(console.error);
    api.teamEpa(c, season).then((r) => setEpa(r.weeks)).catch(console.error);
  }, [c, season]);
  useEffect(() => {
    if (!c) return;
    api.teamRoster(c).then((r) => setRoster(r.players)).catch(console.error);
    api.teamSchedule(c).then((r) => setSched(r.games)).catch(console.error);
    api.teamNews(c).then((r) => setNews(r.items)).catch(console.error);
  }, [c]);

  const positions = useMemo(
    () => [...new Set(roster.map((p) => p.pos).filter(Boolean))].sort() as string[],
    [roster]);

  if (!t) return null;
  const rec = detail?.record;
  const games = (rec?.w ?? 0) + (rec?.l ?? 0);

  return (
    <div className="space-y-6"
         style={{ ["--accent" as string]: t.glow,
                  ["--accent-glow" as string]: hexToRgba(t.glow, 0.5) }}>
      {/* full-bleed header */}
      <div className="glass relative overflow-hidden p-8"
           style={{ background: `linear-gradient(120deg, ${hexToRgba(t.color, 0.55)}, var(--glass) 65%)` }}>
        <img src={t.logo} alt="" aria-hidden
             className="pointer-events-none absolute -right-10 -top-14 h-64 w-64 opacity-15" />
        <div className="relative flex items-center gap-6">
          <img src={t.logo} alt={t.name} className="logo-glow h-20 w-20" />
          <div>
            <h1 className="text-3xl font-bold tracking-tight">{t.name}</h1>
            <p className="text-sm" style={{ color: "var(--muted)" }}>
              {t.conf} {t.div} · head coach {detail?.coach.current ?? "—"}
            </p>
          </div>
          <div className="ml-auto flex gap-6">
            <StatRing label={`${season} record`} value={rec ? `${rec.w}–${rec.l}` : "—"}
                      fraction={games ? (rec!.w / games) : 0} />
            <StatRing label="points / game" value={rec?.pf_pg?.toFixed(1) ?? "—"}
                      fraction={(rec?.pf_pg ?? 0) / 35} />
            <StatRing label="allowed / game" value={rec?.pa_pg?.toFixed(1) ?? "—"}
                      fraction={1 - (rec?.pa_pg ?? 35) / 35} />
            <StatRing label="sched difficulty" value={detail?.sos ? `#${detail.sos.rank}` : "—"}
                      sub="of 32" fraction={detail?.sos ? 1 - (detail.sos.rank - 1) / 31 : 0} />
          </div>
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <GlassPanel title="Weekly efficiency (EPA per play)" className="lg:col-span-2">
          <div className="mb-2 flex items-center justify-between">
            <span className="text-xs" style={{ color: "var(--muted)" }}>
              Offense: higher is better · Defense: lower is better (what they allowed)
            </span>
            <select value={season} onChange={(e) => setSeason(+e.target.value)}
                    className="rounded-lg border bg-transparent px-2 py-1 text-sm"
                    style={{ borderColor: "var(--stroke)", color: "var(--text)" }}>
              {SEASONS.map((s) => <option key={s} value={s} style={{ color: "#000" }}>{s}</option>)}
            </select>
          </div>
          <GlowLineChart data={epa} xKey="week"
            series={[{ key: "off", name: "Offense", color: "var(--accent)" },
                     { key: "def", name: "Defense", color: "#7d93a8" }]} />
        </GlassPanel>

        <GlassPanel title="Coach lineage">
          <ol className="max-h-72 space-y-2 overflow-y-auto pr-1 text-sm">
            {detail?.coach.history.map((h) => (
              <li key={h.season} className="flex items-center gap-3">
                <span className="tabular-nums" style={{ color: "var(--muted)" }}>{h.season}</span>
                <span className="h-1.5 w-1.5 rounded-full" style={{ background: "var(--accent)" }} />
                <Link to={`/coach/${encodeURIComponent(h.coach)}`}
                      className="font-medium hover:underline">{h.coach}</Link>
                <span className="ml-auto tabular-nums" style={{ color: "var(--muted)" }}>
                  {h.wins}–{h.games - h.wins}
                </span>
              </li>
            ))}
          </ol>
        </GlassPanel>
      </div>

      <GlassPanel title="2026 schedule">
        <div className="flex gap-2 overflow-x-auto pb-1">
          {sched.map((g) => (
            <Link key={g.week} to={`/matchup/${g.game_id}`}
                  className="min-w-32 rounded-xl border p-2.5 text-center text-xs transition-colors hover:bg-white/5"
                  style={{ borderColor: "var(--stroke)" }}>
              <div className="font-bold" style={{ color: "var(--muted)" }}>WK {g.week}</div>
              <div className="mt-1 font-semibold">{g.home ? "vs" : "@"} {g.opponent}</div>
              <div className="mt-0.5" style={{ color: "var(--muted)" }}>{g.date}</div>
              {g.line_text && (
                <div className="mt-1" style={{ color: "var(--accent)" }}>{g.line_text}</div>
              )}
            </Link>
          ))}
        </div>
      </GlassPanel>

      <div className="grid gap-6 lg:grid-cols-2">
        <GlassPanel title={`2026 roster (${roster.length})`}>
          <div className="mb-2 flex flex-wrap gap-1.5">
            {positions.map((p) => (
              <button key={p} onClick={() => setPosFilter(posFilter === p ? "" : p)}
                className="rounded-full border px-2.5 py-0.5 text-xs font-semibold transition-colors"
                style={{
                  borderColor: posFilter === p ? "var(--accent)" : "var(--stroke)",
                  color: posFilter === p ? "var(--accent)" : "var(--muted)",
                }}>
                {p}
              </button>
            ))}
          </div>
          <div className="max-h-80 overflow-y-auto">
            <table className="w-full text-left text-sm">
              <thead className="sticky top-0" style={{ background: "var(--bg-1)" }}>
                <tr style={{ color: "var(--muted)" }}>
                  <th className="py-1 pr-2 font-medium">#</th>
                  <th className="py-1 pr-2 font-medium">Player</th>
                  <th className="py-1 pr-2 font-medium">Pos</th>
                  <th className="py-1 font-medium">College</th>
                </tr>
              </thead>
              <tbody>
                {roster.filter((p) => !posFilter || p.pos === posFilter).map((p) => (
                  <tr key={p.gsis ?? p.name} className="border-t transition-colors hover:bg-white/5"
                      style={{ borderColor: "var(--stroke)" }}>
                    <td className="py-1.5 pr-2 tabular-nums" style={{ color: "var(--muted)" }}>{p.num ?? ""}</td>
                    <td className="py-1.5 pr-2 font-medium">
                      {p.gsis ? (
                        <Link to={`/player/${p.gsis}`} className="hover:underline">{p.name}</Link>
                      ) : p.name}
                    </td>
                    <td className="py-1.5 pr-2">{p.pos}</td>
                    <td className="py-1.5 text-xs" style={{ color: "var(--muted)" }}>{p.college}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </GlassPanel>

        <GlassPanel title="Team feed">
          <ul className="max-h-96 space-y-3 overflow-y-auto pr-1">
            {news.map((n, i) => (
              <li key={i}>
                <a href={n.url} target="_blank" rel="noreferrer"
                   className="text-sm font-medium transition-colors hover:text-white">
                  {n.headline}
                </a>
                <div className="text-xs" style={{ color: "var(--muted)" }}>
                  {n.ts?.slice(0, 16).replace("T", " ")} · {n.source === "team_site" ? "team site" : "ESPN"}
                </div>
              </li>
            ))}
          </ul>
        </GlassPanel>
      </div>
    </div>
  );
}
