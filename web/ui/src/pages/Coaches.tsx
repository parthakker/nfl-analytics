import { useCallback, useMemo, useState } from "react";
import { Chip, DataTable, LinkCell, PageHeader, Panel, PillGroup } from "../components/ui";
import type { Column } from "../components/ui";
import { useMeta } from "../lib/MetaContext";
import { useApi } from "../lib/useApi";

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
  { value: "HC", label: "Head coaches" },
  { value: "OC", label: "Offensive coordinators" },
  { value: "DC", label: "Defensive coordinators" },
];

const TAB_BLURBS: Record<string, string> = {
  HC: "Head coaches since 2007. ATS is the record against the closing spread, 4th-down is the go rate in go territory, PROE is pass rate over expected.",
  OC: "The offensive coordinator owns the game plan and (sometimes) the play sheet — half the league's head coaches keep the calls themselves. 'Calls plays' marks the real play-callers.",
  DC: "The defensive coordinator picks the fronts, coverages and pressures every snap. Where the head coach runs the defense himself, the DC leads install and the defensive room.",
};

const pct = (v: number | null) => (v != null ? `${Math.round(v * 100)}%` : "—");

export default function Coaches() {
  const meta = useMeta();
  const [tab, setTab] = useState<"HC" | "OC" | "DC">("HC");
  const { data, error } = useApi<{ coaches: CoachRow[]; staff?: StaffRow[] }>("/api/coaches");
  const rows = data?.coaches ?? [];
  const staff = data?.staff ?? [];

  const logo = useCallback(
    (team: string | null) =>
      team && meta?.teams[team] ? (
        <img src={meta.teams[team].logo} alt={team} title={team} className="h-6 w-6" />
      ) : null,
    [meta],
  );

  const hcColumns = useMemo<Column<CoachRow>[]>(() => [
    {
      key: "coach", label: "Coach",
      help: "Head coach of record for the game, from the schedule feed. Interim coaches appear as their own row.",
      render: (c) => (
        <LinkCell to={`/coach/${encodeURIComponent(c.coach)}`}>{c.coach}</LinkCell>
      ),
    },
    {
      key: "current_team", label: "Team", sortable: false,
      help: "Team currently coached. Blank means the coach is not on a sideline this season.",
      render: (c) => logo(c.current_team),
    },
    {
      key: "era", label: "Era", value: (c) => c.first_season,
      help: "First and last season as a head coach within our 2007+ coverage.",
      render: (c) => <span className="text-muted">{c.first_season}–{c.last_season}</span>,
    },
    {
      key: "record", label: "Record", numeric: true, value: (c) => (c.g ? c.w / c.g : 0),
      help: "Regular-season wins and losses, sorted by win percentage.",
      render: (c) => `${c.w}–${c.g - c.w}`,
    },
    {
      key: "playoffs", label: "Playoffs", numeric: true, value: (c) => c.post_w,
      help: "Postseason wins and losses.",
      render: (c) => `${c.post_w}–${c.post_g - c.post_w}`,
    },
    {
      key: "ats_pct", label: "ATS %", numeric: true,
      help: "Share of games covering the closing spread. 50% is break-even before juice.",
      render: (c) => pct(c.ats_pct),
    },
    {
      key: "go_rate", label: "4th-down", numeric: true,
      help: "How often this coach goes for it on 4th down in situations where the analytics say go.",
      render: (c) => pct(c.go_rate),
    },
    {
      key: "proe", label: "PROE", numeric: true,
      help: "Pass rate over expected: how much more (or less) this coach passes than the league would in the same down, distance, time and score.",
      render: (c) =>
        c.proe != null ? `${c.proe > 0 ? "+" : ""}${(c.proe * 100).toFixed(1)}%` : "—",
    },
  ], [logo]);

  const staffColumns = useMemo<Column<StaffRow>[]>(() => [
    {
      key: "name", label: "Coordinator",
      help: "Current coordinator as recorded in our hand-maintained staff file.",
      render: (s) => (
        <LinkCell to={`/coach/${encodeURIComponent(s.name)}?role=${s.role}`}>{s.name}</LinkCell>
      ),
    },
    { key: "team", label: "Team", sortable: false, help: "Team employing this coordinator.", render: (s) => logo(s.team) },
    {
      key: "since", label: "Since", numeric: true,
      help: "First season in this role with this team.",
      render: (s) => <span className="text-muted">{s.since ?? "—"}</span>,
    },
    {
      key: "playcaller", label: "Play calls", sortable: false,
      help: "Whether this coordinator actually calls the plays, rather than the head coach.",
      render: (s) => (s.playcaller ? <Chip tone="accent">calls plays</Chip> : null),
    },
    {
      key: "scheme_family", label: "Scheme",
      help: "Scheme family this unit belongs to. The Learn section explains each one.",
    },
    {
      key: "about", label: "About", sortable: false,
      help: "One-line background on the coordinator: where they came from and what they run.",
      render: (s) => (
        <span className="block max-w-md truncate text-muted" title={s.about}>{s.about}</span>
      ),
    },
  ], [logo]);

  const coordinators = staff.filter((s) => s.role === tab);

  return (
    <div className="space-y-4">
      <PageHeader title="Coach hub" subtitle={TAB_BLURBS[tab]} />

      <PillGroup
        ariaLabel="Coaching role"
        options={TABS}
        value={tab}
        onChange={(v) => setTab(v as "HC" | "OC" | "DC")}
      />

      <Panel flush>
        {error ? (
          <p className="px-4 py-6 text-center text-body text-muted">
            Couldn't load coaches — {error}
          </p>
        ) : tab === "HC" ? (
          <DataTable
            columns={hcColumns}
            rows={rows}
            rowKey={(c) => c.coach}
            defaultSort={{ key: "record", dir: "desc" }}
            stickyCols={1}
            caption="Head coach records, 2007–2025"
            empty="No coaches loaded."
          />
        ) : (
          <DataTable
            columns={staffColumns}
            rows={coordinators}
            rowKey={(s) => `${s.team}-${s.name}`}
            defaultSort={{ key: "team", dir: "asc" }}
            stickyCols={1}
            caption={`Current ${tab === "OC" ? "offensive" : "defensive"} coordinators`}
            empty="No coordinators loaded."
            /* footNote lands in <tfoot>: the caveat is not one of the 32
               teams' rows, and in <tbody> it would corrupt every row count */
            footNote={
              tab === "DC"
                ? "Tampa Bay carries no DC title — Todd Bowles runs the defense himself."
                : undefined
            }
          />
        )}
      </Panel>
    </div>
  );
}
