import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, type DivisionStanding, type NewsItem, type ScheduleGame } from "../lib/api";
import { useMeta } from "../lib/MetaContext";
import { useChat } from "../lib/ChatContext";
import { PageHeader, Panel } from "../components/ui";
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
      <span className="text-micro tabular-nums text-muted">{w}–{l}</span>
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
      <PageHeader
        title="The League"
        subtitle="2025 final records — click a team to open its page."
        actions={meta?.kickoff_2026 ? (
          <div className="flex items-center gap-4 rounded-[var(--radius-panel)] border border-border bg-surface px-4 py-2">
            <span className="text-micro font-bold uppercase tracking-[0.12em] text-muted">
              2026 kickoff
            </span>
            <Countdown iso={meta.kickoff_2026} />
          </div>
        ) : undefined} />

      <Omnibox onOpen={() => open()} />
      <Ticker items={news} />

      <div className="grid gap-6 lg:grid-cols-2">
        {(["AFC", "NFC"] as const).map((c) => (
          <div key={c} className="space-y-4">
            <h2 className="text-h2 font-bold text-ink">{c}</h2>
            <div className="grid grid-cols-2 gap-4">
              {conf(c).map((d) => (
                <Panel key={d.name} title={d.name}>
                  <div className="grid grid-cols-2 gap-1">
                    {d.teams.map((t) => (
                      <TeamNode key={t.code} code={t.code} w={t.w} l={t.l} />
                    ))}
                  </div>
                </Panel>
              ))}
            </div>
          </div>
        ))}
      </div>

      <Panel title="Season openers — week 1 lines" flush>
        <div className="scroll-x flex gap-3 px-4 pb-4">
          {games.map((g, i) => (
            <Link key={i} to={g.game_id ? `/matchup/${g.game_id}` : "/schedule"}
                  className="min-w-44 rounded-[var(--radius-control)] border border-border p-3 text-body transition-colors hover:border-border-strong hover:bg-surface-2">
              <div className="font-semibold text-ink">{g.away} @ {g.home}</div>
              <div className="mt-1 text-micro text-muted">{g.date}</div>
              <div className="mt-2 text-micro tabular-nums text-accent">
                {g.spread != null
                  ? `${g.spread > 0 ? g.home : g.away} -${Math.abs(g.spread)} · o/u ${g.total ?? "—"}`
                  : "lines pending"}
              </div>
            </Link>
          ))}
        </div>
      </Panel>
    </div>
  );
}
