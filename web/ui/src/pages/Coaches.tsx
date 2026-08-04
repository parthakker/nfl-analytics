import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import Chip from "../components/Chip";
import GlassPanel from "../components/GlassPanel";
import { useMeta } from "../lib/MetaContext";

interface CoachRow {
  coach: string; first_season: number; last_season: number;
  g: number; w: number; post_g: number; post_w: number;
  ats_pct: number | null; go_rate: number | null; proe: number | null;
  current_team: string | null;
}
interface StaffRow {
  team: string; role: "OC" | "DC"; name: string; since: number | null;
  playcaller: boolean | null; scheme_family: string; about: string;
}

const TABS = [
  ["HC", "Head coaches"],
  ["OC", "Offensive coordinators"],
  ["DC", "Defensive coordinators"],
] as const;

const TAB_BLURBS: Record<string, string> = {
  HC: "Head coaches since 2007 · ATS = record against the closing spread · 4th-down = go rate in go territory · PROE = pass rate over expected",
  OC: "The offensive coordinator owns the game plan and (sometimes) the play sheet — half the league's head coaches keep the calls themselves. 'Calls plays' marks the real play-callers.",
  DC: "The defensive coordinator picks the fronts, coverages and pressures every snap. Where the head coach runs the defense himself, the DC leads install and the defensive room.",
};

export default function Coaches() {
  const meta = useMeta();
  const [tab, setTab] = useState<"HC" | "OC" | "DC">("HC");
  const [rows, setRows] = useState<CoachRow[]>([]);
  const [staff, setStaff] = useState<StaffRow[]>([]);

  useEffect(() => {
    fetch("/api/coaches").then((r) => r.json())
      .then((r) => { setRows(r.coaches); setStaff(r.staff ?? []); })
      .catch(console.error);
  }, []);

  const coordinators = staff.filter((s) => s.role === tab);

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Coach hub</h1>
        <p className="text-sm" style={{ color: "var(--muted)" }}>{TAB_BLURBS[tab]}</p>
      </div>

      <div className="flex flex-wrap gap-2">
        {TABS.map(([key, label]) => (
          <button key={key} onClick={() => setTab(key)}
            className="rounded-full border px-3 py-1 text-sm font-semibold"
            style={{ borderColor: tab === key ? "var(--arc)" : "var(--stroke)",
                     color: tab === key ? "var(--arc)" : "var(--muted)" }}>
            {label}
          </button>
        ))}
      </div>

      {tab === "HC" ? (
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
      ) : (
        <GlassPanel>
          <table className="w-full text-left text-sm">
            <thead>
              <tr style={{ color: "var(--muted)" }}>
                {["Coordinator", "Team", "Since", "", "Scheme", "About"].map((h, i) => (
                  <th key={i} className="py-1.5 pr-3 font-medium">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {coordinators.map((s) => (
                <tr key={`${s.team}-${s.name}`} className="border-t transition-colors hover:bg-white/5"
                    style={{ borderColor: "var(--stroke)" }}>
                  <td className="py-2 pr-3">
                    <Link to={`/coach/${encodeURIComponent(s.name)}?role=${s.role}`}
                          className="font-medium hover:underline" style={{ color: "var(--arc)" }}>
                      {s.name}
                    </Link>
                  </td>
                  <td className="py-2 pr-3">
                    {meta?.teams[s.team] && (
                      <img src={meta.teams[s.team].logo} alt={s.team}
                           className="h-6 w-6" title={s.team} />
                    )}
                  </td>
                  <td className="py-2 pr-3 tabular-nums text-xs" style={{ color: "var(--muted)" }}>
                    {s.since ?? "—"}
                  </td>
                  <td className="py-2 pr-3">
                    {s.playcaller && <Chip tone="arc">calls plays</Chip>}
                  </td>
                  <td className="py-2 pr-3 text-xs">{s.scheme_family}</td>
                  <td className="max-w-md truncate py-2 text-xs" style={{ color: "var(--muted)" }}
                      title={s.about}>
                    {s.about}
                  </td>
                </tr>
              ))}
              {tab === "DC" && (
                <tr className="border-t" style={{ borderColor: "var(--stroke)" }}>
                  <td colSpan={6} className="py-2 text-xs italic" style={{ color: "var(--muted)" }}>
                    Tampa Bay carries no DC title — Todd Bowles runs the defense himself.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </GlassPanel>
      )}
    </div>
  );
}
