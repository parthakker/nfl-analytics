import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api, type DivisionStanding } from "../lib/api";
import { useMeta } from "../lib/MetaContext";
import { DataTable, PageHeader, Panel, PillGroup } from "../components/ui";
import type { Column } from "../components/ui";

interface Row {
  code: string; division: string; conf: string;
  w: number; l: number; pf_pg: number | null; pa_pg: number | null;
}

export default function Teams() {
  const meta = useMeta();
  const [divs, setDivs] = useState<DivisionStanding[]>([]);
  const [season, setSeason] = useState<number | null>(null);
  const [conf, setConf] = useState("");

  useEffect(() => {
    api.overview()
      .then((r) => { setDivs(r.divisions); setSeason(r.season ?? null); })
      .catch(console.error);
  }, []);

  const rows = useMemo<Row[]>(() =>
    divs.flatMap((d) => d.teams.map((t) => ({
      code: t.code,
      division: d.name,
      conf: d.name.slice(0, 3),
      w: t.w, l: t.l,
      pf_pg: t.pf_pg ?? null,
      pa_pg: t.pa_pg ?? null,
    }))), [divs]);

  const filtered = conf ? rows.filter((r) => r.conf === conf) : rows;

  const columns = useMemo<Column<Row>[]>(() => [
    {
      key: "code", label: "Team", width: "12rem",
      help: "Click through to that team's page.",
      render: (r) => (
        <Link to={`/team/${r.code}`} className="flex items-center gap-2 font-medium text-accent hover:underline">
          {meta?.teams[r.code] && <img src={meta.teams[r.code].logo} alt="" className="h-5 w-5" />}
          {meta?.teams[r.code]?.name ?? r.code}
        </Link>
      ),
    },
    { key: "division", label: "Division", help: "Conference and division." },
    {
      key: "record", label: "W–L", numeric: true, value: (r) => r.w,
      help: "Regular-season wins and losses.",
      render: (r) => `${r.w}–${r.l}`,
    },
    {
      key: "pct", label: "PCT", numeric: true,
      value: (r) => (r.w + r.l ? r.w / (r.w + r.l) : 0),
      help: "Win percentage. Ties count as half a win.",
      render: (r) => (r.w + r.l ? (r.w / (r.w + r.l)).toFixed(3).replace(/^0/, "") : "—"),
    },
    {
      key: "pf_pg", label: "PF/G", numeric: true,
      help: "Points scored per game.",
      // diverging tint centred on a ~22-point league average
      tint: (r) => (r.pf_pg == null ? null : (r.pf_pg - 22) / 8),
      render: (r) => r.pf_pg?.toFixed(1) ?? "—",
    },
    {
      key: "pa_pg", label: "PA/G", numeric: true,
      help: "Points allowed per game. Fewer is better, so the tint is inverted.",
      tint: (r) => (r.pa_pg == null ? null : (22 - r.pa_pg) / 8),
      render: (r) => r.pa_pg?.toFixed(1) ?? "—",
    },
    {
      key: "diff", label: "Diff", numeric: true,
      value: (r) => (r.pf_pg != null && r.pa_pg != null ? r.pf_pg - r.pa_pg : null),
      help: "Point differential per game — usually a better signal of team strength than record.",
      render: (r) => {
        if (r.pf_pg == null || r.pa_pg == null) return "—";
        const d = r.pf_pg - r.pa_pg;
        return (
          <span className={d > 0 ? "text-positive" : d < 0 ? "text-negative" : ""}>
            {d > 0 ? "+" : ""}{d.toFixed(1)}
          </span>
        );
      },
    },
  ], [meta]);

  return (
    <div className="space-y-4">
      <PageHeader
        title="Teams & standings"
        subtitle={`Every team's ${season ?? ""} record, scoring and differential. Sort any column; click a team for its full page.`}
      />

      <PillGroup
        ariaLabel="Conference"
        clearable
        options={[{ value: "AFC", label: "AFC" }, { value: "NFC", label: "NFC" }]}
        value={conf}
        onChange={setConf} />

      <Panel flush>
        <DataTable
          columns={columns}
          rows={filtered}
          rowKey={(r) => r.code}
          defaultSort={{ key: "pct", dir: "desc" }}
          stickyCols={1}
          caption={`${season ?? ""} standings`}
          empty="Standings not loaded." />
      </Panel>
    </div>
  );
}
