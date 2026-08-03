import { useEffect, useState } from "react";
import GlassPanel from "../components/GlassPanel";
import GlowLineChart from "../components/GlowLineChart";

interface Ref {
  official_id: string; name: string; games: number;
  first_season: number; last_season: number;
  pen_per_game: number; home_pen_bias: number; avg_total: number;
  over_rate: number; home_win_rate: number; home_cover_rate: number;
}

async function j<T>(p: string): Promise<T> {
  const r = await fetch(p);
  if (!r.ok) throw new Error(`${p}: ${r.status}`);
  return r.json();
}

export default function Referees() {
  const [refs, setRefs] = useState<Ref[]>([]);
  const [leagueAvg, setLeagueAvg] = useState<number | null>(null);
  const [detail, setDetail] = useState<{ name: string; seasons: Record<string, number>[] } | null>(null);

  useEffect(() => {
    j<{ league_avg_pen_per_game: number; referees: Ref[] }>("/api/referees")
      .then((r) => { setRefs(r.referees); setLeagueAvg(r.league_avg_pen_per_game); })
      .catch(console.error);
  }, []);

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Referee intelligence</h1>
        <p className="text-sm" style={{ color: "var(--muted)" }}>
          Head referees, 2015–2025 · league average {leagueAvg} penalties/game ·
          home bias = extra flags on the home team (negative favors home) ·
          click a ref for season trends
        </p>
      </div>

      {detail && (
        <GlassPanel title={`${detail.name} — season trends`}>
          <GlowLineChart
            data={detail.seasons}
            xKey="season"
            series={[{ key: "pen_per_game", name: "penalties / game", color: "var(--arc)" },
                     { key: "avg_total_points", name: "avg total points", color: "#7d93a8" }]} />
        </GlassPanel>
      )}

      <GlassPanel>
        <table className="w-full text-left text-sm">
          <thead>
            <tr style={{ color: "var(--muted)" }}>
              {["Referee", "Games", "Era", "Pen/gm", "Home bias", "Avg total",
                "Over %", "Home win %", "Home cover %"].map((h) => (
                <th key={h} className="py-1.5 pr-3 font-medium">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {refs.map((r) => (
              <tr key={r.official_id}
                  onClick={() => j<{ name: string; seasons: Record<string, number>[] }>(
                    `/api/referees/${r.official_id}`).then(setDetail)}
                  className="cursor-pointer border-t transition-colors hover:bg-white/5"
                  style={{ borderColor: "var(--stroke)" }}>
                <td className="py-2 pr-3 font-medium">{r.name}</td>
                <td className="py-2 pr-3 tabular-nums">{r.games}</td>
                <td className="py-2 pr-3 text-xs" style={{ color: "var(--muted)" }}>
                  {r.first_season}–{r.last_season}
                </td>
                <td className="py-2 pr-3 font-semibold tabular-nums"
                    style={{ color: leagueAvg && r.pen_per_game > leagueAvg ? "#ec835a" : "var(--arc)" }}>
                  {r.pen_per_game}
                </td>
                <td className="py-2 pr-3 tabular-nums">{r.home_pen_bias > 0 ? "+" : ""}{r.home_pen_bias}</td>
                <td className="py-2 pr-3 tabular-nums">{r.avg_total}</td>
                <td className="py-2 pr-3 tabular-nums">{Math.round(r.over_rate * 100)}%</td>
                <td className="py-2 pr-3 tabular-nums">{Math.round(r.home_win_rate * 100)}%</td>
                <td className="py-2 tabular-nums">{Math.round(r.home_cover_rate * 100)}%</td>
              </tr>
            ))}
          </tbody>
        </table>
      </GlassPanel>
    </div>
  );
}
