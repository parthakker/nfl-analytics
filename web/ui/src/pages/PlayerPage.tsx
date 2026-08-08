import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, type NewsItem } from "../lib/api";
import { LineChart } from "../components/charts";
import { DataTable, PageHeader, Panel, Select } from "../components/ui";
import type { Column } from "../components/ui";
import { useMeta } from "../lib/MetaContext";
import { useTeamTokens } from "../lib/useTeamTokens";

type Info = {
  name: string; pos: string; team: string; headshot: string | null;
  rookie_season: number | null; last_season: number | null;
  draft_year: number | null; draft_round: number | null;
};

type SeasonRow = Record<string, string | number | null>;

const num = (v: string | number | null | undefined) =>
  typeof v === "number" ? v.toLocaleString() : (v ?? "—");

export default function PlayerPage() {
  const { gsis = "" } = useParams();
  const meta = useMeta();
  const [info, setInfo] = useState<Info | null>(null);
  const [seasons, setSeasons] = useState<SeasonRow[]>([]);
  const [allWeekly, setAllWeekly] = useState<{ season: number; week: number; ppr: number | null }[]>([]);
  const [news, setNews] = useState<NewsItem[]>([]);
  const [chartSeason, setChartSeason] = useState<number | null>(null);
  const [err, setErr] = useState("");

  useEffect(() => {
    setErr(""); setInfo(null);
    api.player(gsis).then((d) => {
      setInfo(d.info as Info);
      setSeasons(d.seasons);
      setAllWeekly(d.weekly);
      setNews(d.news);
      setChartSeason((d.seasons[0]?.season as number | undefined) ?? null);
      window.scrollTo(0, 0);
    }).catch((e) => setErr(String(e)));
  }, [gsis]);

  // hooks must run before any early return
  const { style: teamStyle } = useTeamTokens(info?.team ?? null);

  const columns = useMemo<Column<SeasonRow>[]>(() => [
    { key: "season", label: "Season", numeric: true, help: "Regular season only. Playoff lines are excluded." },
    { key: "games", label: "G", numeric: true, help: "Games in which this player recorded a stat line." },
    { key: "pass_yds", label: "Pass yds", numeric: true, help: "Passing yards.", render: (s) => num(s.pass_yds) },
    { key: "rush_yds", label: "Rush yds", numeric: true, help: "Rushing yards.", render: (s) => num(s.rush_yds) },
    { key: "rec", label: "Rec", numeric: true, help: "Receptions." },
    { key: "rec_yds", label: "Rec yds", numeric: true, help: "Receiving yards.", render: (s) => num(s.rec_yds) },
    { key: "std", label: "Std", numeric: true, help: "Standard fantasy points: no reception bonus." },
    { key: "half_ppr", label: "½PPR", numeric: true, help: "Half-PPR fantasy points: 0.5 per reception." },
    {
      key: "ppr", label: "PPR", numeric: true,
      help: "Full-PPR fantasy points: 1 point per reception.",
      render: (s) => <span className="font-semibold text-accent">{s.ppr ?? "—"}</span>,
    },
  ], []);

  if (err) return <p className="text-muted">Player not found. {err}</p>;
  if (!info) return null;
  const t = meta?.teams[info.team];
  const weekly = allWeekly.filter((w) => w.season === chartSeason);
  const chartSeasons = [...new Set(allWeekly.map((w) => w.season))].sort((a, b) => b - a);

  return (
    <div className="space-y-4" style={teamStyle}>
      <div className="rail-team relative overflow-hidden rounded-[var(--radius-panel)] border border-border bg-surface p-6">
        {t && <div aria-hidden className="bg-team-wash absolute inset-0" />}
        {t && <img src={t.logo} alt="" aria-hidden
                   className="pointer-events-none absolute -right-6 -top-8 h-40 w-40 opacity-10" />}
        <div className="relative">
        <PageHeader
          title={info.name}
          media={info.headshot ? (
            <img src={info.headshot} alt="" className="h-20 w-20 rounded-full object-cover"
                 onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }} />
          ) : undefined}
          subtitle={
            <>
              {info.pos}
              {t ? <> · <Link to={`/team/${info.team}`} className="text-accent hover:underline">{t.name}</Link></>
                 : info.team ? ` · ${info.team}` : ""}
              {info.draft_year != null && (
                <> · drafted {info.draft_year}{info.draft_round != null ? ` (round ${info.draft_round})` : ""}</>
              )}
              {info.rookie_season != null && <> · {info.rookie_season}–{info.last_season ?? "now"}</>}
            </>
          }
        />
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <Panel title="Season lines (regular season)" span={2} flush>
          <DataTable
            columns={columns}
            rows={seasons}
            rowKey={(s) => String(s.season)}
            stickyCols={1}
            maxHeight="18rem"
            caption={`${info.name} season totals`}
            empty="No season lines on record." />

          <div className="p-4">
            <div className="mb-2 flex items-center justify-between">
              <span className="text-label text-muted">Weekly PPR points</span>
              <Select
                size="sm" ariaLabel="Chart season"
                value={chartSeason ?? ""}
                onChange={(v) => setChartSeason(+v)}
                options={chartSeasons.map((s) => ({ value: s, label: String(s) }))} />
            </div>
            <LineChart data={weekly} xKey="week" xLabel="Week"
              series={[{ key: "ppr", name: "PPR points" }]} digits={1} />
          </div>
        </Panel>

        <Panel title="Recent news">
          <ul className="space-y-3">
            {news.length === 0 && <li className="text-body text-muted">No recent items.</li>}
            {news.map((n, i) => (
              <li key={i}>
                <a href={n.url} target="_blank" rel="noreferrer"
                   className="text-body font-medium text-ink hover:text-accent hover:underline">
                  {n.headline}
                </a>
                <div className="text-micro text-muted">{n.ts?.slice(0, 10)}</div>
              </li>
            ))}
          </ul>
        </Panel>
      </div>
    </div>
  );
}
