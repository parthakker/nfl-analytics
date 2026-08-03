import { useEffect, useState } from "react";
import { api } from "../lib/api";
import GlassPanel from "../components/GlassPanel";

const CATS = [["ppr", "Fantasy (PPR)"], ["passing", "Passing"],
              ["rushing", "Rushing"], ["receiving", "Receiving"]] as const;
const SEASONS = Array.from({ length: 19 }, (_, i) => 2025 - i);

export default function Leaders() {
  const [season, setSeason] = useState(2025);
  const [cat, setCat] = useState("ppr");
  const [minGames, setMinGames] = useState(8);
  const [label, setLabel] = useState("");
  const [rows, setRows] = useState<Record<string, string | number | null>[]>([]);

  useEffect(() => {
    api.leaders(season, cat, minGames)
      .then((r) => { setRows(r.rows); setLabel(r.label); })
      .catch(console.error);
  }, [season, cat, minGames]);

  return (
    <div className="space-y-5">
      <h1 className="text-2xl font-bold tracking-tight">League leaders</h1>
      <div className="flex flex-wrap items-center gap-3">
        <select value={season} onChange={(e) => setSeason(+e.target.value)}
                className="rounded-lg border bg-transparent px-2 py-1.5 text-sm"
                style={{ borderColor: "var(--stroke)" }}>
          {SEASONS.map((s) => <option key={s} style={{ color: "#000" }}>{s}</option>)}
        </select>
        {CATS.map(([k, name]) => (
          <button key={k} onClick={() => setCat(k)}
            className="rounded-full border px-3 py-1 text-sm font-semibold"
            style={{ borderColor: cat === k ? "var(--arc)" : "var(--stroke)",
                     color: cat === k ? "var(--arc)" : "var(--muted)" }}>
            {name}
          </button>
        ))}
        <label className="ml-auto flex items-center gap-2 text-sm" style={{ color: "var(--muted)" }}>
          min games {minGames}
          <input type="range" min={1} max={17} value={minGames}
                 onChange={(e) => setMinGames(+e.target.value)} />
        </label>
      </div>
      <GlassPanel title={`Top 25 — ${label}, ${season} regular season`}>
        <table className="w-full text-left text-sm">
          <thead>
            <tr style={{ color: "var(--muted)" }}>
              <th className="py-1.5 pr-2 font-medium">#</th>
              <th className="py-1.5 pr-2 font-medium">Player</th>
              <th className="py-1.5 pr-2 font-medium">Pos</th>
              <th className="py-1.5 pr-2 font-medium">Team</th>
              <th className="py-1.5 pr-2 font-medium">G</th>
              <th className="py-1.5 text-right font-medium">{label}</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={i} className="border-t transition-colors hover:bg-white/5"
                  style={{ borderColor: "var(--stroke)" }}>
                <td className="py-1.5 pr-2 tabular-nums" style={{ color: "var(--muted)" }}>{i + 1}</td>
                <td className="py-1.5 pr-2 font-medium">{r.player}</td>
                <td className="py-1.5 pr-2">{r.pos}</td>
                <td className="py-1.5 pr-2">{r.team}</td>
                <td className="py-1.5 pr-2 tabular-nums">{r.games}</td>
                <td className="py-1.5 text-right font-semibold tabular-nums"
                    style={{ color: "var(--arc)" }}>{r.value?.toLocaleString?.() ?? r.value}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </GlassPanel>
    </div>
  );
}
