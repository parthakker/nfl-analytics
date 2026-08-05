import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, type DivisionStanding, type NewsItem, type ScheduleGame } from "../lib/api";
import { useMeta } from "../lib/MetaContext";
import { useChat } from "../lib/ChatContext";
import GlassPanel from "../components/GlassPanel";
import Countdown from "../components/Countdown";
import Ticker from "../components/Ticker";
import Omnibox from "../components/Omnibox";

function TeamNode({ code, w, l }: { code: string; w: number; l: number }) {
  const meta = useMeta();
  const nav = useNavigate();
  const t = meta?.teams[code];
  if (!t) return null;
  return (
    <button onClick={() => nav(`/team/${code}`)}
      className="group flex flex-col items-center gap-1 rounded-[var(--radius-control)] p-2 transition-colors hover:bg-surface-2">
      <img src={t.logo} alt={t.name} className="h-12 w-12 transition-transform group-hover:scale-110" />
      <span className="text-xs font-bold">{code}</span>
      <span className="text-[11px] tabular-nums" style={{ color: "var(--muted)" }}>
        {w}–{l}
      </span>
    </button>
  );
}

export default function CommandCenter() {
  const meta = useMeta();
  const { open } = useChat();
  const [divs, setDivs] = useState<DivisionStanding[]>([]);
  const [games, setGames] = useState<ScheduleGame[]>([]);
  const [news, setNews] = useState<NewsItem[]>([]);

  useEffect(() => {
    api.overview().then((r) => setDivs(r.divisions)).catch(console.error);
    api.schedule().then((r) => setGames(r.games)).catch(console.error);
    api.news("all", 20).then((r) => setNews(r.items)).catch(console.error);
  }, []);

  const conf = (c: string) => divs.filter((d) => d.name.startsWith(c));

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-6">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">The League</h1>
          <p className="text-sm" style={{ color: "var(--muted)" }}>
            2025 final records — click a team to open its HUD
          </p>
        </div>
        {meta?.kickoff_2026 && (
          <GlassPanel className="px-6">
            <div className="flex items-center gap-5">
              <span className="text-[10px] font-bold uppercase tracking-widest"
                    style={{ color: "var(--muted)" }}>
                2026 kickoff
              </span>
              <Countdown iso={meta.kickoff_2026} />
            </div>
          </GlassPanel>
        )}
      </div>

      <Omnibox onOpen={() => open()} />
      <Ticker items={news} />

      <div className="grid gap-6 lg:grid-cols-2">
        {(["AFC", "NFC"] as const).map((c) => (
          <div key={c} className="space-y-4">
            <h2 className="glow-text text-lg font-bold" style={{ color: "var(--arc)" }}>{c}</h2>
            <div className="grid grid-cols-2 gap-4">
              {conf(c).map((d) => (
                <GlassPanel key={d.name} title={d.name}>
                  <div className="grid grid-cols-2 gap-1">
                    {d.teams.map((t) => (
                      <TeamNode key={t.code} code={t.code} w={t.w} l={t.l} />
                    ))}
                  </div>
                </GlassPanel>
              ))}
            </div>
          </div>
        ))}
      </div>

      <GlassPanel title="Season openers — week 1 lines">
        <div className="flex gap-3 overflow-x-auto pb-1">
          {games.map((g, i) => (
            <div key={i} className="min-w-44 rounded-xl border p-3 text-sm"
                 style={{ borderColor: "var(--stroke)" }}>
              <div className="font-semibold">{g.away} @ {g.home}</div>
              <div className="mt-1 text-xs" style={{ color: "var(--muted)" }}>{g.date}</div>
              <div className="mt-2 text-xs tabular-nums" style={{ color: "var(--arc)" }}>
                {g.spread != null
                  ? `${g.spread > 0 ? g.home : g.away} -${Math.abs(g.spread)} · o/u ${g.total ?? "—"}`
                  : "lines pending"}
              </div>
            </div>
          ))}
        </div>
      </GlassPanel>
    </div>
  );
}
