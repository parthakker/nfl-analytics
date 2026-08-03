import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import GlassPanel from "../components/GlassPanel";
import { useMeta } from "../lib/MetaContext";

interface CoachRow {
  coach: string; first_season: number; last_season: number;
  g: number; w: number; post_g: number; post_w: number;
  ats_pct: number | null; go_rate: number | null; proe: number | null;
  current_team: string | null;
}

export default function Coaches() {
  const meta = useMeta();
  const [rows, setRows] = useState<CoachRow[]>([]);
  useEffect(() => {
    fetch("/api/coaches").then((r) => r.json())
      .then((r) => setRows(r.coaches)).catch(console.error);
  }, []);

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Coach hub</h1>
        <p className="text-sm" style={{ color: "var(--muted)" }}>
          Head coaches since 2007 · ATS = record against the closing spread ·
          4th-down = go rate in go territory · PROE = pass rate over expected
        </p>
      </div>
      <GlassPanel>
        <table className="w-full text-left text-sm">
          <thead>
            <tr style={{ color: "var(--muted)" }}>
              {["Coach", "Team", "Era", "Record", "Playoffs", "ATS %", "4th-down", "PROE"].map((h) => (
                <th key={h} className="py-1.5 pr-3 font-medium">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((c) => (
              <tr key={c.coach} className="border-t transition-colors hover:bg-white/5"
                  style={{ borderColor: "var(--stroke)" }}>
                <td className="py-2 pr-3">
                  <Link to={`/coach/${encodeURIComponent(c.coach)}`}
                        className="font-medium hover:underline" style={{ color: "var(--arc)" }}>
                    {c.coach}
                  </Link>
                </td>
                <td className="py-2 pr-3">
                  {c.current_team && meta?.teams[c.current_team] && (
                    <img src={meta.teams[c.current_team].logo} alt={c.current_team}
                         className="h-6 w-6" title={c.current_team} />
                  )}
                </td>
                <td className="py-2 pr-3 text-xs" style={{ color: "var(--muted)" }}>
                  {c.first_season}–{c.last_season}
                </td>
                <td className="py-2 pr-3 tabular-nums">{c.w}–{c.g - c.w}</td>
                <td className="py-2 pr-3 tabular-nums">{c.post_w}–{c.post_g - c.post_w}</td>
                <td className="py-2 pr-3 tabular-nums">
                  {c.ats_pct != null ? `${Math.round(c.ats_pct * 100)}%` : "—"}
                </td>
                <td className="py-2 pr-3 tabular-nums">
                  {c.go_rate != null ? `${Math.round(c.go_rate * 100)}%` : "—"}
                </td>
                <td className="py-2 tabular-nums">
                  {c.proe != null ? `${c.proe > 0 ? "+" : ""}${(c.proe * 100).toFixed(1)}%` : "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </GlassPanel>
    </div>
  );
}
