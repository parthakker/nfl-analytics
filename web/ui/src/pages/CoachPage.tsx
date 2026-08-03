import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import FingerprintRadar from "../components/FingerprintRadar";
import GlassPanel from "../components/GlassPanel";
import { useMeta } from "../lib/MetaContext";
import { hexToRgba } from "../lib/color";

interface Detail {
  coach: string;
  current_team: string | null;
  scheme: {
    head_coach: string;
    offensive_coordinator: string | null;
    defensive_coordinator: string | null;
    offense_scheme: { family: string; fact: string };
    defense_scheme: { family: string; fact: string };
  } | null;
  seasons: Record<string, number | string | null>[];
  fingerprint: { metric: string; pct: number | null }[];
  fingerprint_note: string;
  rivals: { opp_coach: string; games: number; wins: number }[];
}

export default function CoachPage() {
  const { name = "" } = useParams();
  const meta = useMeta();
  const [d, setD] = useState<Detail | null>(null);
  const [err, setErr] = useState("");

  useEffect(() => {
    fetch(`/api/coaches/${encodeURIComponent(name)}`)
      .then((r) => (r.ok ? r.json() : Promise.reject(r.status)))
      .then(setD).catch((e) => setErr(String(e)));
  }, [name]);

  if (err) return <p style={{ color: "var(--muted)" }}>No record found. {err}</p>;
  if (!d) return null;
  const t = d.current_team ? meta?.teams[d.current_team] : null;
  const glow = t?.glow;

  const career: { w: number; g: number; pw: number; pg: number } =
    d.seasons.reduce(
      (a: { w: number; g: number; pw: number; pg: number }, s) => ({
        w: a.w + (Number(s.reg_wins) || 0), g: a.g + (Number(s.reg_games) || 0),
        pw: a.pw + (Number(s.post_wins) || 0), pg: a.pg + (Number(s.post_games) || 0),
      }), { w: 0, g: 0, pw: 0, pg: 0 });

  return (
    <div className="space-y-6"
         style={glow ? { ["--accent" as string]: glow,
                         ["--accent-glow" as string]: hexToRgba(glow, 0.5) } : undefined}>
      <div className="glass flex flex-wrap items-center gap-5 p-6">
        {t && <img src={t.logo} alt="" className="logo-glow h-14 w-14" />}
        <div>
          <h1 className="text-2xl font-bold tracking-tight">{d.coach}</h1>
          <p className="text-sm" style={{ color: "var(--muted)" }}>
            {career.w}–{career.g - career.w} regular season · {career.pw}–{career.pg - career.pw} playoffs
            {t && ` · ${t.name}`}
          </p>
        </div>
      </div>

      {d.scheme && (
        <div className="grid gap-4 sm:grid-cols-2">
          <GlassPanel title="Offensive identity">
            <div className="glow-text text-lg font-semibold" style={{ color: "var(--accent)" }}>
              {d.scheme.offense_scheme.family}
            </div>
            <p className="mt-1 text-sm" style={{ color: "var(--muted)" }}>
              {d.scheme.offense_scheme.fact || "—"}
            </p>
            <p className="mt-2 text-xs" style={{ color: "var(--muted)" }}>
              OC: {d.scheme.offensive_coordinator ?? "unrecorded — editable in data/coaches_meta.json"}
            </p>
          </GlassPanel>
          <GlassPanel title="Defensive identity">
            <div className="glow-text text-lg font-semibold" style={{ color: "var(--accent)" }}>
              {d.scheme.defense_scheme.family}
            </div>
            <p className="mt-1 text-sm" style={{ color: "var(--muted)" }}>
              {d.scheme.defense_scheme.fact || "—"}
            </p>
            <p className="mt-2 text-xs" style={{ color: "var(--muted)" }}>
              DC: {d.scheme.defensive_coordinator ?? "unrecorded — editable in data/coaches_meta.json"}
            </p>
          </GlassPanel>
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-2">
        <GlassPanel title={`Scheme fingerprint — ${d.fingerprint_note}`}>
          <FingerprintRadar data={d.fingerprint} />
          <p className="text-xs" style={{ color: "var(--muted)" }}>
            Each axis is a league percentile (100 = most extreme). Pass defense
            is inverted: higher = better defense.
          </p>
        </GlassPanel>

        <GlassPanel title="Head-to-head rivals (3+ games)">
          <ul className="space-y-2 text-sm">
            {d.rivals.map((r) => (
              <li key={r.opp_coach} className="flex items-center gap-3">
                <Link to={`/coach/${encodeURIComponent(r.opp_coach)}`}
                      className="font-medium hover:underline">{r.opp_coach}</Link>
                <span className="ml-auto tabular-nums"
                      style={{ color: r.wins * 2 > r.games ? "#0ca30c" : r.wins * 2 < r.games ? "#d03b3b" : "var(--muted)" }}>
                  {r.wins}–{r.games - r.wins}
                </span>
              </li>
            ))}
          </ul>
        </GlassPanel>
      </div>

      <GlassPanel title="Season by season">
        <div className="max-h-96 overflow-y-auto">
          <table className="w-full text-left text-sm">
            <thead className="sticky top-0" style={{ background: "var(--bg-1)" }}>
              <tr style={{ color: "var(--muted)" }}>
                {["Season", "Team", "Record", "Playoffs", "PPG", "ATS", "4th-down", "PROE"].map((h) => (
                  <th key={h} className="py-1.5 pr-3 font-medium">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {[...d.seasons].reverse().map((s, i) => (
                <tr key={i} className="border-t tabular-nums" style={{ borderColor: "var(--stroke)" }}>
                  <td className="py-1.5 pr-3">{s.season}</td>
                  <td className="py-1.5 pr-3">{s.team}</td>
                  <td className="py-1.5 pr-3">{s.reg_wins}–{Number(s.reg_games) - Number(s.reg_wins)}</td>
                  <td className="py-1.5 pr-3">
                    {Number(s.post_games) > 0 ? `${s.post_wins}–${Number(s.post_games) - Number(s.post_wins)}` : "—"}
                  </td>
                  <td className="py-1.5 pr-3">{s.ppg}</td>
                  <td className="py-1.5 pr-3">
                    {Number(s.ats_games) > 0 ? `${s.ats_wins}–${Number(s.ats_games) - Number(s.ats_wins)}` : "—"}
                  </td>
                  <td className="py-1.5 pr-3">
                    {s.go_rate != null ? `${Math.round(Number(s.go_rate) * 100)}%` : "—"}
                  </td>
                  <td className="py-1.5">
                    {s.proe != null ? `${Number(s.proe) > 0 ? "+" : ""}${(Number(s.proe) * 100).toFixed(1)}%` : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </GlassPanel>
    </div>
  );
}
