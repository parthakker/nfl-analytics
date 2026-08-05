import { useEffect, useMemo, useState } from "react";
import { api, type ScheduleGame } from "../lib/api";
import { DataTable, Field, PageHeader, Panel, PillGroup, Select, Toolbar } from "../components/ui";
import type { Column } from "../components/ui";

const SEASONS = Array.from({ length: 20 }, (_, i) => 2026 - i);

export default function SchedulePage() {
  const [season, setSeason] = useState(2026);
  const [week, setWeek] = useState<number | undefined>(undefined);
  const [weeks, setWeeks] = useState<number[]>([]);
  const [games, setGames] = useState<ScheduleGame[]>([]);

  useEffect(() => {
    api.schedule(season, week).then((r) => {
      setWeeks(r.weeks);
      setGames(r.games);
      if (week === undefined) setWeek(r.week);
    }).catch(console.error);
  }, [season, week]);

  const columns = useMemo<Column<ScheduleGame>[]>(() => [
    {
      key: "date", label: "Date", width: "7rem",
      help: "Kickoff date in the stadium's local calendar.",
      render: (g) => <span className="text-muted">{g.date}</span>,
    },
    {
      key: "matchup", label: "Matchup", value: (g) => g.away,
      help: "Away team at home team.",
      render: (g) => <span className="font-medium text-ink">{g.away} @ {g.home}</span>,
    },
    {
      key: "score", label: "Score", numeric: true, value: (g) => g.away_score ?? null,
      help: "Final score, away first. Dashes mean the game has not been played.",
      render: (g) => (g.away_score != null ? `${g.away_score}–${g.home_score}` : "—"),
    },
    {
      key: "spread", label: "Spread (home)", numeric: true,
      help: "Closing spread from the home team's side. Negative means the home team is favored by that many points.",
      render: (g) =>
        g.spread != null ? (g.spread > 0 ? `-${g.spread}` : `+${-g.spread}`) : "—",
    },
    {
      key: "total", label: "O/U", numeric: true,
      help: "Closing total: the combined points the market expects both teams to score.",
      render: (g) => g.total ?? "—",
    },
    {
      key: "home_ml", label: "Home ML", numeric: true,
      help: "Closing American moneyline price on the home team to win outright.",
      render: (g) => g.home_ml ?? "—",
    },
  ], []);

  return (
    <div className="space-y-4">
      <PageHeader
        title="Schedule & lines"
        subtitle="Every game with its closing market. Click a row for the full matchup card."
      />

      <Toolbar trailing={<span className="text-micro text-muted">{games.length} games</span>}>
        <Field label="Season">
          <Select
            value={season}
            onChange={(v) => { setSeason(+v); setWeek(undefined); }}
            options={SEASONS.map((s) => ({ value: s, label: String(s) }))}
            ariaLabel="Season"
            size="sm"
          />
        </Field>
        <Field label="Week">
          <PillGroup
            ariaLabel="Week"
            size="sm"
            options={weeks.map((w) => ({ value: String(w), label: String(w) }))}
            value={String(week ?? "")}
            onChange={(v) => v && setWeek(+v)}
          />
        </Field>
      </Toolbar>

      <Panel flush>
        <DataTable
          columns={columns}
          rows={games}
          rowKey={(g) => g.game_id ?? `${g.away}-${g.home}-${g.date}`}
          stickyCols={1}
          caption={`${season} week ${week ?? ""} schedule and closing lines`}
          empty="No games scheduled for this week."
          rowHref={(g) => (g.game_id ? `/matchup/${g.game_id}` : "")}
        />
      </Panel>
    </div>
  );
}
