import { useEffect, useMemo, useState } from "react";
import { LineChart } from "../components/charts";
import { Chip, DataTable, PageHeader, Panel } from "../components/ui";
import type { Column } from "../components/ui";

interface Ref {
  official_id: string; name: string; games: number;
  first_season: number; last_season: number;
  pen_per_game: number; home_pen_bias: number; avg_total: number;
  over_rate: number; home_win_rate: number; home_cover_rate: number;
}

const pct = (v: number) => `${Math.round(v * 100)}%`;

async function j<T>(p: string): Promise<T> {
  const r = await fetch(p);
  if (!r.ok) throw new Error(`${p}: ${r.status}`);
  return r.json();
}

export default function Referees() {
  const [refs, setRefs] = useState<Ref[]>([]);
  const [leagueAvg, setLeagueAvg] = useState<number | null>(null);
  const [detail, setDetail] = useState<{ name: string; seasons: Record<string, number>[] } | null>(null);

  useEffect(() => {
    j<{ league_avg_pen_per_game: number; referees: Ref[] }>("/api/referees")
      .then((r) => { setRefs(r.referees); setLeagueAvg(r.league_avg_pen_per_game); })
      .catch(console.error);
  }, []);

  const columns = useMemo<Column<Ref>[]>(() => [
    {
      key: "name", label: "Referee",
      help: "Head referee (white hat). One row per referee: careers are stitched across the 2015 boundary where the officials feed begins, and across the 2023 id reissue.",
      render: (r) => <span className="font-medium text-ink">{r.name}</span>,
    },
    { key: "games", label: "G", numeric: true, help: "Regular-season and playoff games worked as head referee, 1999–2025. Only referees with 30 or more are listed." },
    {
      key: "era", label: "Era", value: (r) => r.first_season,
      help: "First and last season on record as a head referee.",
      render: (r) => <span className="text-muted">{r.first_season}–{r.last_season}</span>,
    },
    {
      key: "pen_per_game", label: "Pen/gm", numeric: true,
      help: "Accepted penalties per game, both teams combined. Compare against the league average shown above the table.",
      // above average = orange (more flags), below = blue. Ledge is ~1.5 flags wide.
      tint: (r) => (leagueAvg ? (leagueAvg - r.pen_per_game) / 1.5 : null),
      render: (r) => <span className="font-semibold">{r.pen_per_game}</span>,
    },
    {
      key: "home_pen_bias", label: "Home bias", numeric: true,
      help: "Home-team flags minus away-team flags per game. Negative favors the home team.",
      render: (r) => `${r.home_pen_bias > 0 ? "+" : ""}${r.home_pen_bias}`,
    },
    { key: "avg_total", label: "Avg total", numeric: true, help: "Average combined points scored in this referee's games." },
    {
      key: "over_rate", label: "Over %", numeric: true,
      help: "Share of games that finished above the closing total. 50% is neutral.",
      render: (r) => pct(r.over_rate),
    },
    {
      key: "home_win_rate", label: "Home win %", numeric: true,
      help: "Share of games won by the home team. The league baseline is about 55%.",
      render: (r) => pct(r.home_win_rate),
    },
    {
      key: "home_cover_rate", label: "Home cover %", numeric: true,
      help: "Share of games in which the home team covered the closing spread.",
      render: (r) => pct(r.home_cover_rate),
    },
  ], [leagueAvg]);

  return (
    <div className="space-y-4">
      <PageHeader
        title="Referee intelligence"
        subtitle="Head referees, 1999–2025. Click a row for that crew's season-by-season trend."
        meta={
          <>
            {leagueAvg && <Chip tone="neutral">league avg {leagueAvg} pen/gm</Chip>}
            <Chip tone="neutral">{refs.length} referees</Chip>
            <Chip tone="neutral">negative home bias favors the home team</Chip>
          </>
        }
      />

      {detail && (
        <Panel
          title={`${detail.name} — season trends`}
          actions={
            <button type="button" onClick={() => setDetail(null)}
                    className="text-label text-muted hover:text-ink">
              close
            </button>
          }
        >
          <LineChart
            data={detail.seasons}
            xKey="season" xLabel="Season"
            series={[{ key: "pen_per_game", name: "penalties / game" },
                     { key: "avg_total_points", name: "avg total points" }]}
            digits={1} />
        </Panel>
      )}

      <Panel flush>
        <DataTable
          columns={columns}
          rows={refs}
          rowKey={(r) => r.official_id}
          defaultSort={{ key: "games", dir: "desc" }}
          stickyCols={1}
          caption="Head referee tendencies, 1999–2025"
          empty="No referee data loaded."
          /* official_id is the canonical NAME key, so it must be encoded */
          onRowClick={(r) =>
            j<{ name: string; seasons: Record<string, number>[] }>(
              `/api/referees/${encodeURIComponent(r.official_id)}`)
              .then(setDetail).catch(console.error)}
        />
      </Panel>
    </div>
  );
}
