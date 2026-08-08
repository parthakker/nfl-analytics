import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Chip, Field, PageHeader, Panel, PillGroup, Select, Toolbar } from "../components/ui";
import { useMeta } from "../lib/MetaContext";
import { useApi } from "../lib/useApi";

interface BoardGame {
  game_id: string; date: string; away_team: string; home_team: string;
  spread_line: number | null; total_line: number | null;
  home_moneyline: number | null; away_moneyline: number | null;
  vegas_home_prob: number | null;
  kalshi: { prob_home: number | null; volume: number | null; spread_width: number | null } | null;
  dislocation: { gap: number; fee: number; actionable: boolean; cheaper_side: string } | null;
  angles: {
    rest_diff: number | null; div_game: boolean;
    referee: { name: string; over_rate: number; pen_per_game: number } | null;
    home_coach_ats: { coach: string; pct: number } | null;
    roof: string | null;
  };
}

const pct = (v: number | null | undefined) =>
  v != null ? `${(v * 100).toFixed(1)}%` : "—";

export default function Betting() {
  const meta = useMeta();
  const [week, setWeek] = useState<number | undefined>();
  const [tab, setTab] = useState<"board" | "situations">("board");

  const { data: board, error: boardError } = useApi<{ week: number; games: BoardGame[] }>(
    `/api/betting/board${week ? `?week=${week}` : ""}`);
  const games = board?.games ?? [];
  // the first response tells us which week is current; lock the picker to it
  useEffect(() => {
    if (board && !week) setWeek(board.week);
  }, [board, week]);

  const { data: sit, error: sitError } =
    useApi<Record<string, Record<string, string | number | null>[]>>(
      tab === "situations" ? "/api/betting/situations" : null);

  return (
    <div className="space-y-5">
      <PageHeader
        title="Betting intelligence"
        subtitle="Vegas lines against live Kalshi prices. A dislocation flag means the two markets disagree by more than fees plus spread — market-vs-market only, no model opinions."
        meta={<Chip tone="neutral">not betting advice</Chip>} />

      <Toolbar>
        <PillGroup
          ariaLabel="Betting view"
          options={[{ value: "board", label: "Board" },
                    { value: "situations", label: "Situations" }]}
          value={tab}
          onChange={(v) => setTab(v as "board" | "situations")} />
        {tab === "board" && (
          <Field label="Week">
            <Select
              size="sm" ariaLabel="Week" value={week ?? 1}
              onChange={(v) => setWeek(+v)}
              options={Array.from({ length: 18 }, (_, i) => i + 1)
                .map((w) => ({ value: w, label: `week ${w}` }))} />
          </Field>
        )}
      </Toolbar>

      {tab === "board" && boardError && (
        <Panel>
          <p className="py-4 text-center text-body text-muted">
            Couldn't load the board — {boardError}
          </p>
        </Panel>
      )}
      {tab === "situations" && sitError && (
        <Panel>
          <p className="py-4 text-center text-body text-muted">
            Couldn't load situations — {sitError}
          </p>
        </Panel>
      )}

      {tab === "board" && (
        <div className="grid gap-4 lg:grid-cols-2">
          {games.map((g) => {
            const logo = (c: string) => meta?.teams[c]?.logo;
            return (
              <Panel key={g.game_id}>
                <div className="flex items-center gap-3">
                  {logo(g.away_team) && <img src={logo(g.away_team)} className="h-8 w-8" alt="" />}
                  <Link to={`/matchup/${g.game_id}`} className="font-semibold text-accent hover:underline">
                    {g.away_team} @ {g.home_team}
                  </Link>
                  {logo(g.home_team) && <img src={logo(g.home_team)} className="h-8 w-8" alt="" />}
                  <span className="ml-auto text-micro text-muted">{g.date}</span>
                </div>

                <div className="mt-3 grid grid-cols-3 gap-3 text-center text-body">
                  <div>
                    <div className="text-micro uppercase tracking-[0.12em] text-muted">Spread</div>
                    <div className="font-semibold tabular-nums text-ink">
                      {g.spread_line != null
                        ? `${g.spread_line > 0 ? g.home_team : g.away_team} -${Math.abs(g.spread_line)}`
                        : "—"}
                    </div>
                  </div>
                  <div>
                    <div className="text-micro uppercase tracking-[0.12em] text-muted">Vegas home %</div>
                    <div className="font-semibold tabular-nums text-ink">{pct(g.vegas_home_prob)}</div>
                  </div>
                  <div>
                    <div className="text-micro uppercase tracking-[0.12em] text-muted">Kalshi home %</div>
                    <div className="font-semibold tabular-nums text-accent">
                      {pct(g.kalshi?.prob_home)}
                    </div>
                  </div>
                </div>

                {g.dislocation?.actionable && (
                  <div className="mt-3 rounded-[var(--radius-control)] border border-warning/50 px-3 py-2 text-body text-warning">
                    ⚡ markets disagree by {(Math.abs(g.dislocation.gap) * 100).toFixed(1)} pts
                    (fee ≈ {(g.dislocation.fee * 100).toFixed(1)}) — {g.dislocation.cheaper_side} is cheaper
                  </div>
                )}

                <div className="mt-3 flex flex-wrap gap-1.5">
                  {g.total_line != null && <Chip>o/u {g.total_line}</Chip>}
                  {g.angles.rest_diff != null && g.angles.rest_diff !== 0 && (
                    <Chip tone={Math.abs(g.angles.rest_diff) >= 3 ? "warning" : "neutral"}>
                      rest {g.angles.rest_diff > 0 ? "+" : ""}{g.angles.rest_diff}d home
                    </Chip>
                  )}
                  {g.angles.div_game && <Chip>division</Chip>}
                  {g.angles.roof && g.angles.roof !== "outdoors" && <Chip>{g.angles.roof}</Chip>}
                  {g.angles.referee && (
                    <Chip tone="accent">
                      ref {g.angles.referee.name}: {Math.round(g.angles.referee.over_rate * 100)}% over
                    </Chip>
                  )}
                  {g.angles.home_coach_ats && (
                    <Chip>
                      {g.angles.home_coach_ats.coach} {Math.round(g.angles.home_coach_ats.pct * 100)}% ATS
                    </Chip>
                  )}
                  {g.kalshi?.volume != null && <Chip>kalshi vol {Math.round(g.kalshi.volume).toLocaleString()}</Chip>}
                </div>
              </Panel>
            );
          })}
        </div>
      )}

      {tab === "situations" && sit && (
        <div className="grid gap-6 lg:grid-cols-3">
          {[["rest_mismatches", "Rest mismatches (3+ days)"],
            ["long_travel", "Long travel (2+ time zones)"],
            ["division_dogs", "Division dogs (3+ pts)"]].map(([key, title]) => (
            <Panel key={key} title={title}>
              <ul className="space-y-2 text-body">
                {(sit[key] ?? []).length === 0 && (
                  <li className="text-muted">Nothing qualifies this season.</li>
                )}
                {(sit[key] ?? []).slice(0, 15).map((r, i) => (
                  <li key={i} className="flex items-center gap-2">
                    <span className="text-micro tabular-nums text-muted">wk{r.week}</span>
                    <span className="font-medium text-ink">{r.game}</span>
                    <span className="ml-auto text-micro tabular-nums text-accent">
                      {key === "rest_mismatches" ? `${r.edge_days}d` :
                       key === "long_travel" ? `${r.hours_east}h` : r.underdog}
                    </span>
                  </li>
                ))}
              </ul>
            </Panel>
          ))}
        </div>
      )}
    </div>
  );
}
