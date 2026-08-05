import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { DataTable, Field, PageHeader, Panel, Select, Toolbar } from "../components/ui";
import type { Column } from "../components/ui";
import { hexToRgba } from "../lib/color";
import { useMeta } from "../lib/MetaContext";
import { useTeamPairTokens } from "../lib/useTeamTokens";

interface Summary {
  games: number; a_wins: number; b_wins: number; ties: number;
  a_home_games: number; a_home_wins: number; a_away_games: number;
  a_away_wins: number; neutral_games: number; avg_margin_a: number;
  avg_total: number; a_covers: number; ats_games: number;
  first_season: number; last_season: number;
}
interface GameRow {
  game_id: string; season: number; week: number; season_type: string;
  game_type: string; date: string; site: string; venue_name: string | null;
  venue_country: string | null; a_score: number; b_score: number;
  margin_a: number; a_win: number; overtime: boolean;
  spread_line_a: number | null; covered_a: boolean | null; total_line: number | null;
  a_coach: string; b_coach: string; a_qb: string | null; b_qb: string | null;
  referee: string | null;
}
interface Data {
  teams: [string, string]; summary: Summary;
  streak: { current_streak: number; last_meeting_game_id: string } | null;
  splits: { by_decade: { era: number; g: number; a_wins: number }[];
            by_venue: { venue: string; g: number; a_wins: number }[];
            by_season_type: { season_type: string; g: number; a_wins: number }[] };
  games: GameRow[];
}

const TYPE_OPTS = [
  { value: "", label: "All games" },
  { value: "REG", label: "Regular season" },
  { value: "POST", label: "Playoffs" },
];
const SITE_OPTS = [
  { value: "", label: "Any site" },
  { value: "a_home", label: "at first team" },
  { value: "b_home", label: "at second team" },
  { value: "neutral", label: "Neutral" },
];

export default function H2HExplorer() {
  const { a = "", b = "" } = useParams();
  const nav = useNavigate();
  const meta = useMeta();
  const [pa, setPa] = useState(a.toUpperCase());
  const [pb, setPb] = useState(b.toUpperCase());
  const [stype, setStype] = useState("");
  const [site, setSite] = useState("");
  const [d, setD] = useState<Data | null>(null);

  useEffect(() => { setPa(a.toUpperCase()); setPb(b.toUpperCase()); }, [a, b]);
  useEffect(() => {
    if (!a || !b) { setD(null); return; }
    const q = new URLSearchParams();
    if (stype) q.set("season_type", stype);
    if (site) q.set("site", site);
    fetch(`/api/matchup/h2h/${a}/${b}?${q}`)
      .then((r) => (r.ok ? r.json() : Promise.reject(r.status)))
      .then(setD).catch(console.error);
  }, [a, b, stype, site]);

  const pair = useTeamPairTokens(d?.teams[0] ?? null, d?.teams[1] ?? null);

  const codes = meta ? Object.keys(meta.teams).sort() : [];
  const ta = meta?.teams[d?.teams[0] ?? ""];
  const tb = meta?.teams[d?.teams[1] ?? ""];
  const sum = d?.summary;
  const [A, B] = d?.teams ?? ["", ""];

  const gameColumns = useMemo<Column<GameRow>[]>(() => [
    {
      key: "date", label: "Date", width: "8rem",
      help: "Kickoff date. Playoff meetings are tagged with the round.",
      render: (g) => (
        <span className="text-muted">
          {g.date}
          {g.season_type === "POST" && (
            <span className="ml-1 font-bold text-accent">{g.game_type}</span>
          )}
        </span>
      ),
    },
    {
      key: "site", label: "Site",
      help: "Which team hosted. Neutral covers international and Super Bowl sites.",
      render: (g) => (g.site === "home" ? `at ${A}` : g.site === "away" ? `at ${B}` : "neutral"),
    },
    {
      key: "score", label: "Score", numeric: true, value: (g) => g.margin_a,
      help: `Final score, ${A} first. Sorted by margin.`,
      render: (g) => `${g.a_score}–${g.b_score}${g.overtime ? " OT" : ""}`,
    },
    {
      key: "winner", label: "Winner", value: (g) => g.a_win,
      help: "Team colour marks the winner; a tie shows as muted text.",
      render: (g) => (
        <span className="font-semibold" style={{
          color: g.a_win === 1 ? pair.away.ink : g.a_win === 0 ? pair.home.ink : "var(--color-muted)",
        }}>
          {g.a_win === 1 ? A : g.a_win === 0 ? B : "tie"}
        </span>
      ),
    },
    {
      key: "spread_line_a", label: "Spread", numeric: true,
      help: `Closing spread from ${A}'s side, with a tick for covered and a cross for not.`,
      render: (g) => (
        <span className="text-muted">
          {g.spread_line_a != null
            ? `${A} ${g.spread_line_a > 0 ? "-" : "+"}${Math.abs(g.spread_line_a)}${
                g.covered_a == null ? "" : g.covered_a ? " ✓" : " ✗"}`
            : "—"}
        </span>
      ),
    },
    {
      key: "venue_name", label: "Venue", help: "Stadium the game was played in.",
      render: (g) => <span className="block max-w-36 truncate text-muted">{g.venue_name ?? "—"}</span>,
    },
    {
      key: "qbs", label: "QBs", sortable: false,
      help: "Starting quarterbacks, first team then second.",
      render: (g) => (
        <span className="block max-w-44 truncate text-muted">{g.a_qb ?? "—"} / {g.b_qb ?? "—"}</span>
      ),
    },
    {
      key: "referee", label: "Ref", help: "Head referee for the game.",
      render: (g) => <span className="block max-w-28 truncate text-muted">{g.referee ?? "—"}</span>,
    },
  ], [A, B, pair]);

  const splitRow = (label: string, right: React.ReactNode) => (
    <tr className="border-t border-border">
      <td className="py-1.5 pr-3 text-muted">{label}</td>
      <td className="py-1.5 tabular-nums text-ink">{right}</td>
    </tr>
  );

  return (
    <div className="space-y-4">
      <PageHeader
        title="Head-to-head explorer"
        subtitle="Any two franchises, every meeting since 1999. Relocations are merged (STL→LA, SD→LAC, OAK→LV). Click a game for the full matchup card." />

      <Toolbar>
        <Field label="First">
          <Select size="sm" ariaLabel="First team" value={pa} onChange={setPa}
                  options={[{ value: "", label: "first team…" },
                            ...codes.map((c) => ({ value: c, label: c }))]} />
        </Field>
        <Field label="Second">
          <Select size="sm" ariaLabel="Second team" value={pb} onChange={setPb}
                  options={[{ value: "", label: "second team…" },
                            ...codes.map((c) => ({ value: c, label: c }))]} />
        </Field>
        <button onClick={() => pa && pb && pa !== pb && nav(`/h2h/${pa}/${pb}`)}
                disabled={!pa || !pb || pa === pb}
                className="rounded-full border border-accent/50 bg-accent-bg px-4 py-1 text-body font-semibold text-accent disabled:opacity-40">
          Compare
        </button>
        {d && (
          <>
            <Field label="Type">
              <Select size="sm" ariaLabel="Season type" value={stype}
                      onChange={setStype} options={TYPE_OPTS} />
            </Field>
            <Field label="Site">
              <Select size="sm" ariaLabel="Site" value={site}
                      onChange={setSite} options={SITE_OPTS} />
            </Field>
          </>
        )}
      </Toolbar>

      {d && sum && ta && tb && (
        <>
          <div className="relative overflow-hidden rounded-[var(--radius-panel)] border border-border p-6" style={{
            background: `linear-gradient(105deg, ${hexToRgba(ta.color, 0.3)}, var(--color-surface) 42%, var(--color-surface) 58%, ${hexToRgba(tb.color, 0.3)})` }}>
            <div className="flex flex-wrap items-center gap-5">
              <Link to={`/team/${A}`}><img src={ta.logo} alt={ta.name} className="h-14 w-14" /></Link>
              <div className="text-h2 font-bold text-ink">{ta.name}</div>
              <div className="mx-auto text-center">
                <div className="font-display text-display font-bold tabular-nums text-ink">
                  {sum.a_wins}–{sum.b_wins}{sum.ties ? `–${sum.ties}` : ""}
                </div>
                <div className="text-micro text-muted">
                  {sum.games} meetings · {sum.first_season}–{sum.last_season}
                  {d.streak && d.streak.current_streak !== 0 && (
                    <> · {d.streak.current_streak > 0 ? A : B} won last{" "}
                      {Math.abs(d.streak.current_streak)}</>
                  )}
                </div>
              </div>
              <div className="text-right text-h2 font-bold text-ink">{tb.name}</div>
              <Link to={`/team/${B}`}><img src={tb.logo} alt={tb.name} className="h-14 w-14" /></Link>
            </div>
          </div>

          <div className="grid gap-4 lg:grid-cols-3">
            <Panel title="Site splits">
              <table className="w-full text-left text-table">
                <tbody>
                  {splitRow(`at ${A}`, `${sum.a_home_games} g · ${A} ${sum.a_home_wins}–${sum.a_home_games - sum.a_home_wins}`)}
                  {splitRow(`at ${B}`, `${sum.a_away_games} g · ${A} ${sum.a_away_wins}–${sum.a_away_games - sum.a_away_wins}`)}
                  {splitRow("neutral", `${sum.neutral_games} g`)}
                  {splitRow("avg margin",
                    `${sum.avg_margin_a > 0 ? `${A} +${sum.avg_margin_a}`
                      : sum.avg_margin_a < 0 ? `${B} +${-sum.avg_margin_a}` : "even"} · total ${sum.avg_total}`)}
                  {splitRow(`ATS (${A})`, `${sum.a_covers}–${sum.ats_games - sum.a_covers}`)}
                </tbody>
              </table>
            </Panel>

            <Panel title="By era">
              <div className="max-h-56 overflow-y-auto">
                <table className="w-full text-left text-table">
                  <tbody>
                    {d.splits.by_decade.map((r) => (
                      <tr key={r.era} className="border-t border-border">
                        <td className="py-1 pr-3 text-muted">{r.era}</td>
                        <td className="py-1 pr-3 tabular-nums">{r.g} g</td>
                        <td className="py-1 tabular-nums">{A} {r.a_wins}–{r.g - r.a_wins}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Panel>

            <Panel title="By venue">
              <div className="max-h-56 overflow-y-auto">
                <table className="w-full text-left text-table">
                  <tbody>
                    {d.splits.by_venue.map((r) => (
                      <tr key={r.venue} className="border-t border-border">
                        <td className="max-w-40 truncate py-1 pr-3 text-muted">{r.venue}</td>
                        <td className="py-1 pr-3 tabular-nums">{r.g} g</td>
                        <td className="py-1 tabular-nums">{A} {r.a_wins}–{r.g - r.a_wins}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Panel>
          </div>

          <Panel title={`Every meeting (${d.games.length})`} flush>
            <DataTable
              columns={gameColumns}
              rows={d.games}
              rowKey={(g) => g.game_id}
              stickyCols={1}
              maxHeight="32rem"
              caption={`${A} versus ${B}, every meeting`}
              empty="No meetings match these filters."
              rowHref={(g) => `/matchup/${g.game_id}`} />
          </Panel>
        </>
      )}
      {!d && a && b && <p className="text-muted">Loading…</p>}
    </div>
  );
}
