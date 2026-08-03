import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import Chip from "../components/Chip";
import GlassPanel from "../components/GlassPanel";
import { useMeta } from "../lib/MetaContext";

interface BoardGame {
  game_id: string; date: string; away_team: string; home_team: string;
  spread_line: number | null; total_line: number | null;
  home_moneyline: number | null; away_moneyline: number | null;
  vegas_home_prob: number | null;
  kalshi: { prob_home: number | null; volume: number | null; spread_width: number | null } | null;
  dislocation: { gap: number; fee: number; actionable: boolean; cheaper_side: string } | null;
  angles: {
    rest_diff: number | null; div_game: boolean;
    referee: { name: string; over_rate: number; pen_per_game: number } | null;
    home_coach_ats: { coach: string; pct: number } | null;
    roof: string | null;
  };
}

const pct = (v: number | null | undefined) =>
  v != null ? `${(v * 100).toFixed(1)}%` : "—";

export default function Betting() {
  const meta = useMeta();
  const [week, setWeek] = useState<number | undefined>();
  const [games, setGames] = useState<BoardGame[]>([]);
  const [tab, setTab] = useState<"board" | "situations">("board");
  const [sit, setSit] = useState<Record<string, Record<string, string | number | null>[]> | null>(null);

  useEffect(() => {
    fetch(`/api/betting/board${week ? `?week=${week}` : ""}`)
      .then((r) => r.json())
      .then((r) => { setGames(r.games); if (!week) setWeek(r.week); })
      .catch(console.error);
  }, [week]);
  useEffect(() => {
    if (tab === "situations" && !sit)
      fetch("/api/betting/situations").then((r) => r.json()).then(setSit).catch(console.error);
  }, [tab, sit]);

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Betting intelligence</h1>
        <p className="text-sm" style={{ color: "var(--muted)" }}>
          Vegas lines vs live Kalshi prices — a dislocation flag means the two
          markets disagree by more than fees + spread. Market-vs-market only;
          no model opinions. Not betting advice.
        </p>
      </div>

      <div className="flex items-center gap-2">
        {(["board", "situations"] as const).map((t) => (
          <button key={t} onClick={() => setTab(t)}
            className="rounded-full border px-3 py-1 text-sm font-semibold capitalize"
            style={{ borderColor: tab === t ? "var(--arc)" : "var(--stroke)",
                     color: tab === t ? "var(--arc)" : "var(--muted)" }}>
            {t}
          </button>
        ))}
        {tab === "board" && (
          <select value={week ?? 1} onChange={(e) => setWeek(+e.target.value)}
                  className="ml-auto rounded-lg border bg-transparent px-2 py-1 text-sm"
                  style={{ borderColor: "var(--stroke)" }}>
            {Array.from({ length: 18 }, (_, i) => i + 1).map((w) => (
              <option key={w} value={w} style={{ color: "#000" }}>week {w}</option>
            ))}
          </select>
        )}
      </div>

      {tab === "board" && (
        <div className="grid gap-4 lg:grid-cols-2">
          {games.map((g) => {
            const logo = (c: string) => meta?.teams[c]?.logo;
            return (
              <GlassPanel key={g.game_id}>
                <div className="flex items-center gap-3">
                  {logo(g.away_team) && <img src={logo(g.away_team)} className="h-8 w-8" alt="" />}
                  <Link to={`/matchup/${g.game_id}`} className="font-semibold hover:underline">
                    {g.away_team} @ {g.home_team}
                  </Link>
                  {logo(g.home_team) && <img src={logo(g.home_team)} className="h-8 w-8" alt="" />}
                  <span className="ml-auto text-xs" style={{ color: "var(--muted)" }}>{g.date}</span>
                </div>

                <div className="mt-3 grid grid-cols-3 gap-3 text-center text-sm">
                  <div>
                    <div className="text-[10px] uppercase tracking-widest" style={{ color: "var(--muted)" }}>Spread</div>
                    <div className="font-semibold tabular-nums">
                      {g.spread_line != null
                        ? `${g.spread_line > 0 ? g.home_team : g.away_team} -${Math.abs(g.spread_line)}`
                        : "—"}
                    </div>
                  </div>
                  <div>
                    <div className="text-[10px] uppercase tracking-widest" style={{ color: "var(--muted)" }}>Vegas home %</div>
                    <div className="font-semibold tabular-nums">{pct(g.vegas_home_prob)}</div>
                  </div>
                  <div>
                    <div className="text-[10px] uppercase tracking-widest" style={{ color: "var(--muted)" }}>Kalshi home %</div>
                    <div className="font-semibold tabular-nums" style={{ color: "var(--arc)" }}>
                      {pct(g.kalshi?.prob_home)}
                    </div>
                  </div>
                </div>

                {g.dislocation?.actionable && (
                  <div className="mt-3 rounded-xl border px-3 py-2 text-sm"
                       style={{ borderColor: "#ec835a", color: "#ec835a" }}>
                    ⚡ markets disagree by {(Math.abs(g.dislocation.gap) * 100).toFixed(1)} pts
                    (fee ≈ {(g.dislocation.fee * 100).toFixed(1)}) — {g.dislocation.cheaper_side} is cheaper
                  </div>
                )}

                <div className="mt-3 flex flex-wrap gap-1.5">
                  {g.total_line != null && <Chip>o/u {g.total_line}</Chip>}
                  {g.angles.rest_diff != null && g.angles.rest_diff !== 0 && (
                    <Chip tone={Math.abs(g.angles.rest_diff) >= 3 ? "hot" : "muted"}>
                      rest {g.angles.rest_diff > 0 ? "+" : ""}{g.angles.rest_diff}d home
                    </Chip>
                  )}
                  {g.angles.div_game && <Chip>division</Chip>}
                  {g.angles.roof && g.angles.roof !== "outdoors" && <Chip>{g.angles.roof}</Chip>}
                  {g.angles.referee && (
                    <Chip tone="arc">
                      ref {g.angles.referee.name}: {Math.round(g.angles.referee.over_rate * 100)}% over
                    </Chip>
                  )}
                  {g.angles.home_coach_ats && (
                    <Chip>
                      {g.angles.home_coach_ats.coach} {Math.round(g.angles.home_coach_ats.pct * 100)}% ATS
                    </Chip>
                  )}
                  {g.kalshi?.volume != null && <Chip>kalshi vol {Math.round(g.kalshi.volume).toLocaleString()}</Chip>}
                </div>
              </GlassPanel>
            );
          })}
        </div>
      )}

      {tab === "situations" && sit && (
        <div className="grid gap-6 lg:grid-cols-3">
          {[["rest_mismatches", "Rest mismatches (3+ days)"],
            ["long_travel", "Long travel (2+ time zones)"],
            ["division_dogs", "Division dogs (3+ pts)"]].map(([key, title]) => (
            <GlassPanel key={key} title={title}>
              <ul className="space-y-2 text-sm">
                {(sit[key] ?? []).slice(0, 15).map((r, i) => (
                  <li key={i} className="flex items-center gap-2">
                    <span className="tabular-nums text-xs" style={{ color: "var(--muted)" }}>wk{r.week}</span>
                    <span className="font-medium">{r.game}</span>
                    <span className="ml-auto text-xs tabular-nums" style={{ color: "var(--arc)" }}>
                      {key === "rest_mismatches" ? `${r.edge_days}d` :
                       key === "long_travel" ? `${r.hours_east}h` : r.underdog}
                    </span>
                  </li>
                ))}
              </ul>
            </GlassPanel>
          ))}
        </div>
      )}
    </div>
  );
}
