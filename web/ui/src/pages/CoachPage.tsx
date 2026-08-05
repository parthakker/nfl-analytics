import { useEffect, useMemo, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { LineChart, Radar } from "../components/charts";
import { Chip, DataTable, PageHeader, Panel } from "../components/ui";
import type { Column } from "../components/ui";
import { useMeta } from "../lib/MetaContext";
import { useTeamTokens } from "../lib/useTeamTokens";

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
    <Link to={`/knowledge/${scheme.knowledge}`} className="block h-full">
      <Panel title={title} className="h-full transition-colors hover:border-accent/50 hover:bg-surface-2">
        <div className="text-h2 font-semibold text-accent">{scheme.family}</div>
        <p className="mt-1 text-body text-muted">{scheme.fact || "—"}</p>
        <p className="mt-2 text-label font-semibold text-accent">learn this scheme →</p>
      </Panel>
    </Link>
  );
}

function StaffCard({ role, block, team }: { role: string; block: StaffBlock | null; team: string | null }) {
  if (!block) {
    return (
      <Panel title={`${role === "OC" ? "Offensive" : "Defensive"} coordinator`}>
        <p className="text-body text-muted">
          No {role} title on this staff — the head coach runs the unit himself.
        </p>
      </Panel>
    );
  }
  return (
    <Panel title={`${role === "OC" ? "Offensive" : "Defensive"} coordinator`}>
      <div className="flex flex-wrap items-center gap-2">
        <Link to={`/coach/${encodeURIComponent(block.name)}?role=${role}`}
              className="text-h2 font-semibold text-accent hover:underline">
          {block.name}
        </Link>
        {block.playcaller && <Chip tone="accent">calls plays</Chip>}
        <span className="ml-auto text-micro text-muted">
          since {block.since}{team ? ` · ${team}` : ""}
        </span>
      </div>
      <p className="mt-2 text-body text-muted">{block.about}</p>
    </Panel>
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

  // hooks must run before any early return
  const { style: teamStyle } = useTeamTokens(d?.current_team ?? null);

  const unitColumns = useMemo<Column<{ season: number; epa: number; rank: number }>[]>(() => [
    {
      key: "season", label: "Season", numeric: true,
      help: "The arrow marks the first season of this coordinator's tenure.",
      render: (s) => <>{s.season}{s.season === d?.since ? " ←" : ""}</>,
    },
    {
      key: "epa", label: "EPA/play", numeric: true,
      help: "Expected points added per play by this unit, regular season.",
      render: (s) => (s.epa > 0 ? `+${s.epa}` : s.epa),
    },
    {
      key: "rank", label: "League rank", numeric: true,
      help: "Where that EPA ranked among all 32 teams.",
      render: (s) => `#${s.rank}`,
    },
  ], [d?.since]);

  const seasonColumns = useMemo<Column<Record<string, number | string | null>>[]>(() => [
    { key: "season", label: "Season", numeric: true, help: "Season coached." },
    { key: "team", label: "Team", help: "Team coached that season." },
    {
      key: "record", label: "Record", numeric: true,
      value: (s) => (Number(s.reg_games) ? Number(s.reg_wins) / Number(s.reg_games) : 0),
      help: "Regular-season wins and losses, sorted by win percentage.",
      render: (s) => `${s.reg_wins}\u2013${Number(s.reg_games) - Number(s.reg_wins)}`,
    },
    {
      key: "playoffs", label: "Playoffs", numeric: true, value: (s) => Number(s.post_wins) || 0,
      help: "Postseason wins and losses that year.",
      render: (s) => (Number(s.post_games) > 0
        ? `${s.post_wins}\u2013${Number(s.post_games) - Number(s.post_wins)}` : "\u2014"),
    },
    { key: "ppg", label: "PPG", numeric: true, help: "Points scored per game." },
    {
      key: "ats", label: "ATS", numeric: true,
      value: (s) => (Number(s.ats_games) ? Number(s.ats_wins) / Number(s.ats_games) : 0),
      help: "Record against the closing spread. Pushes are excluded.",
      render: (s) => (Number(s.ats_games) > 0
        ? `${s.ats_wins}\u2013${Number(s.ats_games) - Number(s.ats_wins)}` : "\u2014"),
    },
    {
      key: "go_rate", label: "4th-down", numeric: true,
      help: "How often this coach went for it on 4th down where the analytics say go.",
      render: (s) => (s.go_rate != null ? `${Math.round(Number(s.go_rate) * 100)}%` : "\u2014"),
    },
    {
      key: "proe", label: "PROE", numeric: true,
      help: "Pass rate over expected: how much more this coach passed than the league would in the same situation.",
      render: (s) => (s.proe != null
        ? `${Number(s.proe) > 0 ? "+" : ""}${(Number(s.proe) * 100).toFixed(1)}%` : "\u2014"),
    },
  ], []);

  if (err) return <p className="text-muted">No record found. {err}</p>;
  if (!d) return null;
  const t = d.current_team ? meta?.teams[d.current_team] : null;

  /* ───────────────────────── coordinator view ───────────────────────── */
  if (d.role !== "HC") {
    const scheme = d.scheme as Scheme;
    return (
      <div className="space-y-6" style={teamStyle}>
        <div className="rail-team rounded-[var(--radius-panel)] border border-border bg-surface p-6">
          <PageHeader
            crumbs={[{ label: "Coaches", to: "/coaches" }, { label: d.coach }]}
            media={t ? <img src={t.logo} alt={t.name} className="h-14 w-14" /> : undefined}
            title={d.coach}
            subtitle={
              <>
                {t?.name} · since {d.since} · head coach{" "}
                <Link to={`/coach/${encodeURIComponent(d.head_coach ?? "")}`}
                      className="text-accent hover:underline">
                  {d.head_coach}
                </Link>
              </>
            }
            meta={
              <>
                <Chip tone="accent">
                  {d.role === "OC" ? "Offensive coordinator" : "Defensive coordinator"}
                </Chip>
                {d.playcaller && <Chip tone="warning">calls plays</Chip>}
              </>
            } />
        </div>

        {d.team_note && <p className="text-body italic text-muted">⚑ {d.team_note}</p>}

        <div className="grid gap-4 lg:grid-cols-2">
          <Panel title="About">
            <p className="text-body leading-relaxed text-ink">{d.about}</p>
          </Panel>
          <SchemePanel title={d.role === "OC" ? "Offensive identity" : "Defensive identity"}
                       scheme={scheme} />
        </div>

        <Panel
          title={`Unit performance — ${d.unit_label}`}
          note={`Team ${d.role === "OC" ? "offense" : "defense"} by season, ranked out of 32${
            d.role === "DC" ? ". Lower EPA allowed is better" : ""}. Tenure starts ${d.since}; the season before is shown for contrast.`}
        >
          <LineChart
            data={(d.unit_seasons ?? []).map((s) => ({ ...s }))} xKey="season"
            xLabel="Season"
            series={[{ key: "epa", name: d.unit_label ?? "EPA" }]} />
          <div className="mt-3">
            <DataTable
              columns={unitColumns}
              rows={d.unit_seasons ?? []}
              rowKey={(s) => String(s.season)}
              defaultSort={{ key: "season", dir: "desc" }}
              empty="No seasons on record for this unit." />
          </div>
        </Panel>
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
    <div className="space-y-6" style={teamStyle}>
      <div className="rail-team rounded-[var(--radius-panel)] border border-border bg-surface p-6">
        <PageHeader
          crumbs={[{ label: "Coaches", to: "/coaches" }, { label: d.coach }]}
          media={t ? <img src={t.logo} alt={t.name} className="h-14 w-14" /> : undefined}
          title={d.coach}
          subtitle={
            <>
              {seasons.length > 0
                ? `${career.w}–${career.g - career.w} regular season · ${career.pw}–${career.pg - career.pw} playoffs`
                : `first NFL head-coaching season: ${d.since ?? "—"}`}
              {t && ` · ${t.name}`}
            </>
          }
          meta={<Chip tone="accent">Head coach</Chip>} />
      </div>

      {d.team_note && <p className="text-body italic text-muted">⚑ {d.team_note}</p>}

      {d.about && (
        <Panel title="About">
          <p className="text-body leading-relaxed text-ink">{d.about}</p>
        </Panel>
      )}

      {scheme && (
        <div className="grid gap-4 sm:grid-cols-2">
          <SchemePanel title="Offensive identity" scheme={scheme.offense_scheme} />
          <SchemePanel title="Defensive identity" scheme={scheme.defense_scheme} />
        </div>
      )}

      {seasons.length > 0 && (
        <div className="grid gap-4 lg:grid-cols-2">
          <Panel
            title={`Scheme fingerprint — ${d.fingerprint_note}`}
            note="Each axis is a league percentile, where 100 is the most extreme. Pass defense is inverted, so further out is always better."
          >
            <Radar data={d.fingerprint ?? []} />
          </Panel>

          <Panel title="Head-to-head rivals (3+ games)">
            <ul className="space-y-2 text-body">
              {(d.rivals ?? []).length === 0 && (
                <li className="text-muted">No opponent faced three or more times.</li>
              )}
              {(d.rivals ?? []).map((r) => (
                <li key={r.opp_coach} className="flex items-center gap-3">
                  <Link to={`/coach/${encodeURIComponent(r.opp_coach)}`}
                        className="font-medium text-accent hover:underline">{r.opp_coach}</Link>
                  <span className={`ml-auto tabular-nums ${
                    r.wins * 2 > r.games ? "text-positive"
                      : r.wins * 2 < r.games ? "text-negative" : "text-muted"}`}>
                    {r.wins}–{r.games - r.wins}
                  </span>
                </li>
              ))}
            </ul>
          </Panel>
        </div>
      )}

      {seasons.length > 0 && (
        <Panel title="Season by season" flush>
          <DataTable
            columns={seasonColumns}
            rows={seasons}
            rowKey={(s) => `${s.season}-${s.team}`}
            defaultSort={{ key: "season", dir: "desc" }}
            stickyCols={1}
            maxHeight="24rem"
            caption={`${d.coach} season by season`}
            empty="No seasons on record." />
        </Panel>
      )}

      {d.staff && (
        <div>
          <h2 className="mb-3 text-label font-bold uppercase tracking-[0.14em] text-muted">
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
