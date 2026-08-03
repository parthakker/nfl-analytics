import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, type ScheduleGame } from "../lib/api";
import GlassPanel from "../components/GlassPanel";

const SEASONS = Array.from({ length: 20 }, (_, i) => 2026 - i);

export default function SchedulePage() {
  const nav = useNavigate();
  const [season, setSeason] = useState(2026);
  const [week, setWeek] = useState<number | undefined>(undefined);
  const [weeks, setWeeks] = useState<number[]>([]);
  const [games, setGames] = useState<ScheduleGame[]>([]);

  useEffect(() => {
    api.schedule(season, week).then((r) => {
      setWeeks(r.weeks);
      setGames(r.games);
      if (week === undefined) setWeek(r.week);
    }).catch(console.error);
  }, [season, week]);

  return (
    <div className="space-y-5">
      <h1 className="text-2xl font-bold tracking-tight">Schedule & lines</h1>
      <div className="flex flex-wrap items-center gap-3">
        <select value={season}
                onChange={(e) => { setSeason(+e.target.value); setWeek(undefined); }}
                className="rounded-lg border bg-transparent px-2 py-1.5 text-sm"
                style={{ borderColor: "var(--stroke)" }}>
          {SEASONS.map((s) => <option key={s} style={{ color: "#000" }}>{s}</option>)}
        </select>
        <div className="flex flex-wrap gap-1">
          {weeks.map((w) => (
            <button key={w} onClick={() => setWeek(w)}
              className="rounded-lg border px-2.5 py-1 text-xs font-semibold tabular-nums"
              style={{ borderColor: week === w ? "var(--arc)" : "var(--stroke)",
                       color: week === w ? "var(--arc)" : "var(--muted)" }}>
              {w}
            </button>
          ))}
        </div>
      </div>
      <GlassPanel>
        <table className="w-full text-left text-sm">
          <thead>
            <tr style={{ color: "var(--muted)" }}>
              {["Date", "Matchup", "Score", "Spread (home)", "O/U", "Home ML"].map((h) => (
                <th key={h} className="py-1.5 pr-3 font-medium">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {games.map((g, i) => (
              <tr key={i} onClick={() => g.game_id && nav(`/matchup/${g.game_id}`)}
                  className="cursor-pointer border-t transition-colors hover:bg-white/5"
                  style={{ borderColor: "var(--stroke)" }}>
                <td className="py-2 pr-3 text-xs" style={{ color: "var(--muted)" }}>{g.date}</td>
                <td className="py-2 pr-3 font-medium">{g.away} @ {g.home}</td>
                <td className="py-2 pr-3 tabular-nums">
                  {g.away_score != null ? `${g.away_score}–${g.home_score}` : "—"}
                </td>
                <td className="py-2 pr-3 tabular-nums" style={{ color: "var(--arc)" }}>
                  {g.spread != null ? (g.spread > 0 ? `-${g.spread}` : `+${-g.spread}`) : "—"}
                </td>
                <td className="py-2 pr-3 tabular-nums">{g.total ?? "—"}</td>
                <td className="py-2 tabular-nums">{g.home_ml ?? "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </GlassPanel>
    </div>
  );
}
