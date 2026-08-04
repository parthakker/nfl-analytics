import { useEffect, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import Chip from "../components/Chip";
import FingerprintRadar from "../components/FingerprintRadar";
import GlassPanel from "../components/GlassPanel";
import GlowLineChart from "../components/GlowLineChart";
import { useMeta } from "../lib/MetaContext";
import { hexToRgba } from "../lib/color";

interface Scheme {
  family: string;
  fact: string;
  knowledge: string;
}
interface StaffBlock {
  name: string; since: number; playcaller: boolean; about: string;
}
interface Detail {
  role: "HC" | "OC" | "DC";
  coach: string;
  current_team: string | null;
  about: string | null;
  since: number | null;
  team_note: string | null;
  // HC
  scheme: {
    head_coach: string;
    oc: StaffBlock | null;
    dc: StaffBlock | null;
    offense_scheme: Scheme;
    defense_scheme: Scheme;
    note?: string;
  } | Scheme | null;
  staff?: { oc: StaffBlock | null; dc: StaffBlock | null } | null;
  seasons?: Record<string, number | string | null>[];
  fingerprint?: { metric: string; pct: number | null }[];
  fingerprint_note?: string;
  rivals?: { opp_coach: string; games: number; wins: number }[];
  coordinator_role?: { role: string; team: string } | null;
  // coordinator
  head_coach?: string;
  playcaller?: boolean;
  unit_seasons?: { season: number; epa: number; rank: number }[];
  unit_label?: string;
}

function SchemePanel({ title, scheme }: { title: string; scheme: Scheme }) {
  return (
    <Link to={`/knowledge/${scheme.knowledge.replace("#", "#")}`} className="block">
      <GlassPanel title={title} className="h-full transition-transform hover:-translate-y-0.5">
        <div className="glow-text text-lg font-semibold" style={{ color: "var(--accent)" }}>
          {scheme.family}
        </div>
        <p className="mt-1 text-sm" style={{ color: "var(--muted)" }}>
          {scheme.fact || "—"}
        </p>
        <p className="mt-2 text-xs font-semibold" style={{ color: "var(--arc)" }}>
          learn this scheme →
        </p>
      </GlassPanel>
    </Link>
  );
}

function StaffCard({ role, block, team }: { role: string; block: StaffBlock | null; team: string | null }) {
  if (!block) {
    return (
      <GlassPanel title={`${role === "OC" ? "Offensive" : "Defensive"} coordinator`}>
        <p className="text-sm" style={{ color: "var(--muted)" }}>
          No {role} title on this staff — the head coach runs the unit himself.
        </p>
      </GlassPanel>
    );
  }
  return (
    <GlassPanel title={`${role === "OC" ? "Offensive" : "Defensive"} coordinator`}>
      <div className="flex items-center gap-2">
        <Link to={`/coach/${encodeURIComponent(block.name)}?role=${role}`}
              className="text-lg font-semibold hover:underline" style={{ color: "var(--accent)" }}>
          {block.name}
        </Link>
        {block.playcaller && <Chip tone="arc">calls plays</Chip>}
        <span className="ml-auto text-xs" style={{ color: "var(--muted)" }}>
          since {block.since}{team ? ` · ${team}` : ""}
        </span>
      </div>
      <p className="mt-2 text-sm" style={{ color: "var(--muted)" }}>{block.about}</p>
    </GlassPanel>
  );
}

export default function CoachPage() {
  const { name = "" } = useParams();
  const [params] = useSearchParams();
  const meta = useMeta();
  const [d, setD] = useState<Detail | null>(null);
  const [err, setErr] = useState("");

  useEffect(() => {
    setD(null); setErr("");
    const role = params.get("role");
    fetch(`/api/coaches/${encodeURIComponent(name)}${role ? `?role=${role}` : ""}`)
      .then((r) => (r.ok ? r.json() : Promise.reject(r.status)))
      .then(setD).catch((e) => setErr(String(e)));
  }, [name, params]);

  if (err) return <p style={{ color: "var(--muted)" }}>No record found. {err}</p>;
  if (!d) return null;
  const t = d.current_team ? meta?.teams[d.current_team] : null;
  const glow = t?.glow;

  /* ───────────────────────── coordinator view ───────────────────────── */
  if (d.role !== "HC") {
    const scheme = d.scheme as Scheme;
    return (
      <div className="space-y-6"
           style={glow ? { ["--accent" as string]: glow,
                           ["--accent-glow" as string]: hexToRgba(glow, 0.5) } : undefined}>
        <div className="glass flex flex-wrap items-center gap-5 p-6">
          {t && <img src={t.logo} alt="" className="logo-glow h-14 w-14" />}
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-2xl font-bold tracking-tight">{d.coach}</h1>
              <Chip tone="arc">{d.role === "OC" ? "Offensive coordinator" : "Defensive coordinator"}</Chip>
              {d.playcaller && <Chip tone="hot">calls plays</Chip>}
            </div>
            <p className="text-sm" style={{ color: "var(--muted)" }}>
              {t?.name} · since {d.since} · head coach{" "}
              <Link to={`/coach/${encodeURIComponent(d.head_coach ?? "")}`}
                    className="hover:underline" style={{ color: "var(--accent)" }}>
                {d.head_coach}
              </Link>
            </p>
          </div>
        </div>

        {d.team_note && (
          <p className="text-sm italic" style={{ color: "var(--muted)" }}>⚑ {d.team_note}</p>
        )}

        <div className="grid gap-6 lg:grid-cols-2">
          <GlassPanel title="About">
            <p className="text-sm leading-relaxed">{d.about}</p>
          </GlassPanel>
          <SchemePanel title={d.role === "OC" ? "Offensive identity" : "Defensive identity"}
                       scheme={scheme} />
        </div>

        <GlassPanel title={`Unit performance — ${d.unit_label}`}>
          <p className="mb-2 text-xs" style={{ color: "var(--muted)" }}>
            Team {d.role === "OC" ? "offense" : "defense"} by season (rank of 32
            {d.role === "DC" ? "; lower EPA allowed is better" : ""}). Tenure
            starts {d.since}; the season before is shown for contrast.
          </p>
          <GlowLineChart
            data={(d.unit_seasons ?? []).map((s) => ({ ...s }))} xKey="season"
            series={[{ key: "epa", name: d.unit_label ?? "EPA", color: "var(--accent)" }]} />
          <table className="mt-3 w-full text-left text-sm">
            <thead><tr style={{ color: "var(--muted)" }}>
              {["Season", "EPA/play", "League rank"].map((h) => (
                <th key={h} className="py-1 pr-3 font-medium">{h}</th>))}
            </tr></thead>
            <tbody>
              {(d.unit_seasons ?? []).map((s) => (
                <tr key={s.season} className="border-t tabular-nums" style={{ borderColor: "var(--stroke)" }}>
                  <td className="py-1 pr-3">{s.season}{s.season === d.since ? " ←" : ""}</td>
                  <td className="py-1 pr-3">{s.epa > 0 ? `+${s.epa}` : s.epa}</td>
                  <td className="py-1">#{s.rank}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </GlassPanel>
      </div>
    );
  }

  /* ─────────────────────────── head-coach view ───────────────────────── */
  const scheme = d.scheme as {
    head_coach: string; oc: StaffBlock | null; dc: StaffBlock | null;
    offense_scheme: Scheme; defense_scheme: Scheme;
  } | null;
  const seasons = d.seasons ?? [];
  const career = seasons.reduce(
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
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold tracking-tight">{d.coach}</h1>
            <Chip tone="arc">Head coach</Chip>
          </div>
          <p className="text-sm" style={{ color: "var(--muted)" }}>
            {seasons.length > 0
              ? `${career.w}–${career.g - career.w} regular season · ${career.pw}–${career.pg - career.pw} playoffs`
              : `first NFL head-coaching season: ${d.since ?? "—"}`}
            {t && ` · ${t.name}`}
          </p>
        </div>
      </div>

      {d.team_note && (
        <p className="text-sm italic" style={{ color: "var(--muted)" }}>⚑ {d.team_note}</p>
      )}

      {d.about && (
        <GlassPanel title="About">
          <p className="text-sm leading-relaxed">{d.about}</p>
        </GlassPanel>
      )}

      {scheme && (
        <div className="grid gap-4 sm:grid-cols-2">
          <SchemePanel title="Offensive identity" scheme={scheme.offense_scheme} />
          <SchemePanel title="Defensive identity" scheme={scheme.defense_scheme} />
        </div>
      )}

      {seasons.length > 0 && (
        <div className="grid gap-6 lg:grid-cols-2">
          <GlassPanel title={`Scheme fingerprint — ${d.fingerprint_note}`}>
            <FingerprintRadar data={d.fingerprint ?? []} />
            <p className="text-xs" style={{ color: "var(--muted)" }}>
              Each axis is a league percentile (100 = most extreme). Pass defense
              is inverted: higher = better defense.
            </p>
          </GlassPanel>

          <GlassPanel title="Head-to-head rivals (3+ games)">
            <ul className="space-y-2 text-sm">
              {(d.rivals ?? []).map((r) => (
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
      )}

      {seasons.length > 0 && (
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
                {[...seasons].reverse().map((s, i) => (
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
      )}

      {d.staff && (
        <div>
          <h2 className="mb-3 text-sm font-bold uppercase tracking-widest" style={{ color: "var(--arc)" }}>
            Current staff{t ? ` — ${t.name}` : ""}
          </h2>
          <div className="grid gap-4 sm:grid-cols-2">
            <StaffCard role="OC" block={d.staff.oc} team={d.current_team} />
            <StaffCard role="DC" block={d.staff.dc} team={d.current_team} />
          </div>
        </div>
      )}
    </div>
  );
}
