import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { LineChart } from "../components/charts";
import {
  AskAnalyst, Chip, DataTable, PageHeader, Panel, StatTile, Tabs, Tip,
} from "../components/ui";
import type { Column } from "../components/ui";
import { useApi } from "../lib/useApi";

/* ── types (single-page endpoints → local interfaces) ─────────────────── */

interface Contribution {
  feature: string; label: string; value: number;
  win_coef: number; margin_coef: number; logit: number; margin_pts: number;
}
interface WeekGame {
  game_id: string; date: string | null; time: string | null;
  away_team: string; home_team: string; played: boolean;
  spread_line: number | null; total_line: number | null;
  market_home_prob: number | null;
  p_home_win: number | null; pred_margin: number | null;
  edge_prob: number | null; edge_pts: number | null;
  contributions?: Contribution[];
  intercept?: { logit: number; margin_pts: number };
  error: string | null;
}
interface Week { available: boolean; season: number | null; week: number | null; games: WeekGame[] }

interface Summary {
  n_games: number; brier_model: number; brier_market: number; brier_home_always: number;
  logloss_model: number; logloss_market: number;
  margin_mae_model: number; margin_mae_spread: number;
  calibration_gap: number | null; mean_predicted: number; actual_rate: number;
}
interface Report {
  available: boolean; reason?: string; fitted_at: string;
  config: { ratings_source: string; half_life: number; carryover: number; qb_flag: boolean; features: string[]; train_games: number };
  holdout: Summary & { seasons: [number, number] };
  bonus: (Summary & { season: number }) | null;
  calibration: { bin: number; n: number; predicted: number; actual: number; gap: number }[];
  ats: { threshold: number; bets: number; wins: number; win_pct: number | null; breakeven: number }[];
  by_season: { season: number; games: number; brier_model: number; brier_market: number | null; gap: number | null; margin_mae: number; ats3_wins: number; ats3_bets: number }[];
  coefs: { feature: string; label: string; help: string; win_coef: number; margin_coef: number }[];
  intercept: { win: number; margin: number };
}
interface RatingRow { team: string; rank: number; net: number; off_pass: number; off_rush: number; def_pass: number; def_rush: number }
interface Ratings { available: boolean; as_of: string | null; teams: RatingRow[] }
interface History { available: boolean; team: string; rows: { game_id: string; season: number; week: number; opponent: string; net: number; off_pass: number; off_rush: number; def_pass: number; def_rush: number }[] }

interface Run {
  ts: string; git_sha: string | null; source: string; note: string;
  config: { features: string[]; half_life: number; carryover: number; ratings_source: string; recency_half_life: number | null; calibration_window: number | null };
  metrics: { brier_model: number | null; brier_market?: number | null; calibration_gap?: number | null; ats3_win_pct?: number | null; bonus_brier?: number | null };
  delta_vs_shipped: { brier: number } | null; seconds: number;
}
interface Experiments {
  available: boolean;
  shipped: { metrics: { brier_model: number; fitted_at: string }; config: { features: string[]; half_life: number; carryover: number; ratings_source: string } } | null;
  runs: Run[]; best: Run | null; how_to: string;
}

/* ── helpers ──────────────────────────────────────────────────────────── */

const pct = (v: number | null | undefined) => (v == null ? "—" : `${Math.round(v * 100)}%`);
const f4 = (v: number | null | undefined) => (v == null ? "—" : v.toFixed(4));
const signed = (v: number, d = 1) => `${v > 0 ? "+" : ""}${v.toFixed(d)}`;
const TABS = [
  { value: "week", label: "This week" },
  { value: "report", label: "Report card" },
  { value: "ratings", label: "Power ratings" },
  { value: "experiments", label: "Experiments" },
];

/** Diverging bars: one row per feature, the bar grows from a centre line
 *  to the right (helps home) or left (helps away). Plain divs on purpose —
 *  it is a list with a bar in it, not a chart, and every value is printed. */
function ContributionBars({ rows, help }: { rows: Contribution[]; help: Record<string, string> }) {
  const max = Math.max(0.5, ...rows.map((r) => Math.abs(r.margin_pts)));
  return (
    <ul className="space-y-1">
      {rows.map((r) => {
        const w = (Math.abs(r.margin_pts) / max) * 50;
        const pos = r.margin_pts >= 0;
        return (
          <li key={r.feature} className="grid grid-cols-[minmax(0,1fr)_88px_52px] items-center gap-2 text-micro">
            <Tip text={help[r.feature] ?? r.label}>
              <span className="truncate text-muted">{r.label}</span>
            </Tip>
            <div className="relative h-2 rounded-full bg-surface-3">
              <span className="absolute inset-y-0 left-1/2 w-px bg-border-strong" />
              <span
                className={`absolute inset-y-0 rounded-full ${pos ? "bg-positive" : "bg-negative"}`}
                style={pos ? { left: "50%", width: `${w}%` } : { right: "50%", width: `${w}%` }}
              />
            </div>
            <span className={`text-right tabular-nums ${pos ? "text-positive" : "text-negative"}`}>
              {signed(r.margin_pts)}
            </span>
          </li>
        );
      })}
    </ul>
  );
}

/* ── tabs ─────────────────────────────────────────────────────────────── */

function ThisWeek({ help }: { help: Record<string, string> }) {
  const { data, error } = useApi<Week>("/api/model/week");
  if (error) return <p className="text-body text-muted">Couldn't load the week — {error}</p>;
  if (!data) return <p className="text-body text-muted">Loading…</p>;
  const games = data.games.filter((g) => !g.played);
  return (
    <div className="space-y-3">
      <p className="text-micro text-muted">
        {data.season} week {data.week} · model vs market on every game. Bars show how many
        points each input adds to the home margin; the market number is the devigged
        moneyline. A disagreement of 3+ points is chipped, because that is the only ATS
        cell that has ever cleared breakeven on the holdout — and only barely.
      </p>
      <div className="grid gap-3 sm:grid-cols-2">
        {games.map((g) => (
          <Panel
            key={g.game_id}
            title={`${g.away_team} @ ${g.home_team}`}
            actions={
              <Link to={`/matchup/${g.game_id}`} className="text-micro text-accent hover:underline">
                matchup →
              </Link>
            }
            note={g.date ? `${g.date}${g.time ? ` · ${g.time}` : ""}` : undefined}
          >
            {g.error ? (
              <p className="text-micro text-negative">{g.error}</p>
            ) : (
              <>
                <div className="grid grid-cols-2 gap-2">
                  <StatTile
                    label={`${g.home_team} win — model`} value={pct(g.p_home_win)}
                    meter={g.p_home_win} tone="accent"
                    help="The model's home win probability from current ratings, rest, travel, division and QB availability."
                  />
                  <StatTile
                    label={`${g.home_team} win — market`} value={pct(g.market_home_prob)}
                    meter={g.market_home_prob}
                    help="Devigged closing moneyline: the market's home win probability with the bookmaker's margin removed."
                  />
                </div>
                <div className="mt-2 flex flex-wrap items-center gap-1.5">
                  <Chip>model {g.pred_margin != null ? signed(g.pred_margin) : "—"}</Chip>
                  <Chip>spread {g.spread_line != null ? signed(g.spread_line) : "—"}</Chip>
                  {g.edge_pts != null && Math.abs(g.edge_pts) >= 3 && (
                    <Chip tone={g.edge_pts > 0 ? "positive" : "negative"}>
                      {signed(g.edge_pts)} vs spread
                    </Chip>
                  )}
                  {g.edge_prob != null && (
                    <Chip tone="neutral">{signed(g.edge_prob * 100, 0)} pts vs market</Chip>
                  )}
                </div>
                {g.contributions && (
                  <div className="mt-3">
                    <div className="mb-1 text-micro uppercase tracking-[0.12em] text-muted">
                      why it leans this way (margin points)
                    </div>
                    <ContributionBars rows={g.contributions} help={help} />
                    {g.intercept && (
                      <p className="mt-1 text-micro text-faint">
                        + {signed(g.intercept.margin_pts)} home-field baseline
                      </p>
                    )}
                  </div>
                )}
              </>
            )}
          </Panel>
        ))}
      </div>
    </div>
  );
}

function ReportCard({ r }: { r: Report }) {
  const h = r.holdout;
  const cal = useMemo(
    () => r.calibration.map((c) => ({ predicted: c.predicted.toFixed(2), actual: c.actual, perfect: c.predicted, games: c.n })),
    [r.calibration],
  );
  const seasons = useMemo(
    () => r.by_season.map((s) => ({ season: s.season, model: s.brier_model, market: s.brier_market })),
    [r.by_season],
  );
  const coefCols: Column<Report["coefs"][number]>[] = [
    { key: "label", label: "Input", help: "What the feature measures, in words.", render: (c) => <Tip text={c.help}><span className="text-ink">{c.label}</span></Tip> },
    { key: "feature", label: "Column", help: "The feature column name as it appears in the code and in `nfl experiment --features`.", render: (c) => <code className="text-micro text-muted">{c.feature}</code> },
    { key: "margin_coef", label: "Pts / unit", numeric: true, help: "Ridge coefficient: how many points of home margin one unit of this input is worth.", bar: (c) => Math.abs(c.margin_coef) / Math.max(...r.coefs.map((x) => Math.abs(x.margin_coef))), render: (c) => signed(c.margin_coef, 2) },
    { key: "win_coef", label: "Logit / unit", numeric: true, help: "Logistic coefficient: change in the log-odds of a home win per unit of this input.", render: (c) => signed(c.win_coef, 3) },
  ];
  const seasonCols: Column<Report["by_season"][number]>[] = [
    { key: "season", label: "Season", help: "Walk-forward: the model that predicted this season was trained only on earlier seasons." },
    { key: "games", label: "G", numeric: true, help: "Games with a result." },
    { key: "brier_model", label: "Model Brier", numeric: true, help: "Mean squared error of the model's win probability. 0.25 is a coin flip; lower is better.", render: (s) => f4(s.brier_model) },
    { key: "brier_market", label: "Market Brier", numeric: true, help: "Same score for the devigged moneyline.", render: (s) => f4(s.brier_market) },
    { key: "gap", label: "Gap", numeric: true, help: "Model minus market. Positive means the market was better that season.", tint: (s) => (s.gap == null ? null : -s.gap / 0.02), render: (s) => (s.gap == null ? "—" : signed(s.gap, 4)) },
    { key: "margin_mae", label: "Margin MAE", numeric: true, help: "Mean absolute error of the predicted margin, in points." },
    { key: "ats", label: "ATS 3+", value: (s) => (s.ats3_bets ? s.ats3_wins / s.ats3_bets : null), numeric: true, help: "Against the closing spread when the model disagrees by 3+ points. Breakeven at -110 is 52.4%.", render: (s) => (s.ats3_bets ? `${s.ats3_wins}/${s.ats3_bets} (${pct(s.ats3_wins / s.ats3_bets)})` : "—") },
  ];
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-2 md:grid-cols-5">
        <StatTile label="Model Brier" value={f4(h.brier_model)} tone="accent" help={`Holdout ${h.seasons[0]}–${h.seasons[1]}, ${h.n_games} games the model never saw during tuning. Lower is better; 0.25 is a coin flip.`} />
        <StatTile label="Market Brier" value={f4(h.brier_market)} help="The devigged closing moneyline on the same games. The market wins — this is the bar." />
        <StatTile label="Home-always" value={f4(h.brier_home_always)} help="Always predicting the base home-win rate. The model must beat this to be worth anything." />
        <StatTile label="Calibration gap" value={f4(h.calibration_gap)} sub={`predicts ${pct(h.mean_predicted)} home, actual ${pct(h.actual_rate)}`} help="Sample-weighted |actual − predicted| across the 35–70% range. The model leans home because it trains on every season back to 1999, when home field was worth more." />
        <StatTile label="Margin MAE" value={h.margin_mae_model.toFixed(2)} unit="pts" sub={`spread ${h.margin_mae_spread.toFixed(2)}`} help="Average miss on the predicted margin, vs the closing spread's miss on the same games." />
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        <Panel title="Calibration" note="When the model says 60%, does the home team win 60% of the time? Perfect calibration is the diagonal.">
          <LineChart data={cal} xKey="predicted" xLabel="Predicted home win %" digits={3}
            series={[{ key: "actual", name: "actual win rate" }, { key: "perfect", name: "perfect" }]} />
        </Panel>
        <Panel title="Brier by season" note="Walk-forward, so every point is out of sample. The dashed line is a coin flip.">
          <LineChart data={seasons} xKey="season" xLabel="Season" digits={4}
            series={[{ key: "model", name: "model" }, { key: "market", name: "market" }]}
            reference={{ y: 0.25, label: "coin flip" }} />
        </Panel>
      </div>
      <Panel flush title="What each input is worth" note={`Fitted on ${r.config.train_games} games. Home-field baseline: ${signed(r.intercept.margin, 2)} pts before any input.`}>
        <DataTable columns={coefCols} rows={r.coefs} rowKey={(c) => c.feature} caption="Model coefficients" />
      </Panel>
      <Panel flush title="Season by season">
        <DataTable columns={seasonCols} rows={r.by_season} rowKey={(s) => String(s.season)} defaultSort={{ key: "season", dir: "desc" }} caption="Walk-forward results by season"
          footNote={r.bonus ? `${r.bonus.season} was never touched during tuning: model ${f4(r.bonus.brier_model)} vs market ${f4(r.bonus.brier_market)} on ${r.bonus.n_games} games.` : undefined} />
      </Panel>
    </div>
  );
}

function PowerRatings() {
  const { data, error } = useApi<Ratings>("/api/model/ratings");
  const [team, setTeam] = useState<string | null>(null);
  const { data: hist } = useApi<History>(team ? `/api/model/ratings/${team}/history` : null);
  const cols: Column<RatingRow>[] = [
    { key: "rank", label: "#", numeric: true, help: "Rank by net rating." },
    { key: "team", label: "Team", help: "Click for the rating's game-by-game history.", render: (t) => <Link to={`/team/${t.team}`} className="font-medium text-ink hover:text-accent" onClick={(e) => e.stopPropagation()}>{t.team}</Link> },
    { key: "net", label: "Net", numeric: true, help: "Mean of the two offense ratings minus mean of the two defense ratings. EPA per play vs league average, entering the next game.", tint: (t) => t.net / 0.15, render: (t) => signed(t.net, 3) },
    { key: "off_pass", label: "Off pass", numeric: true, help: "Opponent-adjusted passing EPA/play, exponentially weighted (half-life 8 games). Positive is good.", render: (t) => signed(t.off_pass, 3) },
    { key: "off_rush", label: "Off rush", numeric: true, help: "Same for rushing.", render: (t) => signed(t.off_rush, 3) },
    { key: "def_pass", label: "Def pass", numeric: true, help: "EPA/play ALLOWED through the air, opponent-adjusted. Negative is good.", tint: (t) => -t.def_pass / 0.15, render: (t) => signed(t.def_pass, 3) },
    { key: "def_rush", label: "Def rush", numeric: true, help: "EPA/play allowed on the ground. Negative is good.", tint: (t) => -t.def_rush / 0.15, render: (t) => signed(t.def_rush, 3) },
  ];
  if (error) return <p className="text-body text-muted">Couldn't load ratings — {error}</p>;
  const histData = hist?.rows.map((h) => ({ game: `${h.season} wk${h.week}`, net: h.net, offense: (h.off_pass + h.off_rush) / 2, defense: (h.def_pass + h.def_rush) / 2 })) ?? [];
  return (
    <div className="space-y-4">
      {team && hist && (
        <Panel title={`${team} — rating entering each game`} actions={<button type="button" onClick={() => setTeam(null)} className="text-label text-muted hover:text-ink">close</button>}
          note="Every point is the rating BEFORE that game, which is what the model used. Season boundaries shrink toward zero (carryover).">
          <LineChart data={histData.slice(-60)} xKey="game" digits={3}
            series={[{ key: "net", name: "net" }, { key: "offense", name: "offense" }, { key: "defense", name: "defense (lower = better)" }]}
            reference={{ y: 0, label: "league avg" }} />
        </Panel>
      )}
      <Panel flush note={data?.as_of ? `Ratings entering the next game, fitted ${data.as_of.slice(0, 10)}. Click a row for its history.` : undefined}>
        <DataTable columns={cols} rows={data?.teams ?? []} rowKey={(t) => t.team} defaultSort={{ key: "net", dir: "desc" }} stickyCols={2} caption="Model power ratings" onRowClick={(t) => setTeam(t.team)} empty="No ratings — run Train model from /ops." />
      </Panel>
    </div>
  );
}

function ExperimentsTab() {
  const { data, error } = useApi<Experiments>("/api/model/experiments");
  const shippedFeatures = data?.shipped?.config.features ?? [];
  const diff = (run: Run) => {
    const f = new Set(run.config.features);
    const s = new Set(shippedFeatures);
    return [...[...f].filter((x) => !s.has(x)).map((x) => `+${x}`), ...[...s].filter((x) => !f.has(x)).map((x) => `−${x}`)];
  };
  const cols: Column<Run>[] = [
    { key: "ts", label: "When", help: "UTC timestamp of the run.", render: (r) => <span className="text-muted">{r.ts.slice(0, 16).replace("T", " ")}</span> },
    { key: "note", label: "Note", help: "The --note you passed. Say what you were testing.", render: (r) => <span className="text-ink">{r.note || <span className="text-faint">—</span>}</span> },
    { key: "source", label: "Source", help: "`experiment` = nfl experiment; `train` = the full protocol that shipped a model." },
    { key: "config", label: "Config", value: (r) => `${r.config.ratings_source} h${r.config.half_life} c${r.config.carryover}`, help: "Ratings source, half-life (games), carryover; plus drift controls if set.",
      render: (r) => <span className="text-muted">{r.config.ratings_source} h{r.config.half_life} c{r.config.carryover}{r.config.recency_half_life ? ` rec${r.config.recency_half_life}` : ""}{r.config.calibration_window ? ` platt${r.config.calibration_window}` : ""}</span> },
    { key: "features", label: "Features vs shipped", value: (r) => diff(r).join(" "), help: "Only the differences from the shipped feature list are shown.",
      render: (r) => <span className="flex flex-wrap gap-1">{diff(r).length ? diff(r).map((d) => <Chip key={d} tone={d.startsWith("+") ? "positive" : "warning"}>{d}</Chip>) : <span className="text-faint">same</span>}</span> },
    { key: "brier", label: "Brier", numeric: true, value: (r) => r.metrics.brier_model, help: "Holdout Brier for this configuration.", render: (r) => f4(r.metrics.brier_model) },
    { key: "delta", label: "vs shipped", numeric: true, value: (r) => r.delta_vs_shipped?.brier ?? null, help: "Brier minus the shipped model's. Negative is an improvement; the ship gate is −0.0010.", tint: (r) => (r.delta_vs_shipped ? -r.delta_vs_shipped.brier / 0.002 : null), render: (r) => (r.delta_vs_shipped ? signed(r.delta_vs_shipped.brier, 4) : "—") },
    { key: "gap", label: "Cal gap", numeric: true, value: (r) => r.metrics.calibration_gap ?? null, help: "Mid-range calibration gap. Brier barely moves when a lean is fixed, so this gets its own column.", render: (r) => f4(r.metrics.calibration_gap) },
    { key: "sha", label: "Code", help: "Git commit the run was made from.", render: (r) => <code className="text-micro text-muted">{r.git_sha ?? "—"}</code> },
  ];
  if (error) return <p className="text-body text-muted">Couldn't load experiments — {error}</p>;
  const best = data?.best;
  const shipped = data?.shipped?.metrics.brier_model;
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-2 md:grid-cols-3">
        <StatTile label="Shipped Brier" value={f4(shipped)} tone="accent" help="What the model in production scores on the holdout." />
        <StatTile label="Best logged run" value={f4(best?.metrics.brier_model)} sub={best?.note || best?.config.ratings_source} help="Lowest holdout Brier in the log so far." />
        <StatTile label="Best vs shipped" value={best && shipped != null && best.metrics.brier_model != null ? signed(best.metrics.brier_model - shipped, 4) : "—"} tone={best && shipped != null && best.metrics.brier_model != null && best.metrics.brier_model - shipped <= -0.001 ? "positive" : "neutral"} help="Ship gate is an improvement of 0.0010 or more. Anything smaller is within the noise of one holdout." />
      </div>
      <Panel flush note={<>Run one from a terminal — <code className="text-ink">{data?.how_to ?? "nfl experiment --note '…'"}</code> — or a canned variant from <Link to="/ops" className="text-accent">Ops → Model experiment</Link>. Each run takes a few seconds and lands here.</>}>
        <DataTable columns={cols} rows={data?.runs ?? []} rowKey={(r) => `${r.ts}-${r.note}`} caption="Experiment log" empty="No experiments yet. Try: nfl experiment --features -d_qb_out --note 'without QB flag'" />
      </Panel>
    </div>
  );
}

/* ── page ─────────────────────────────────────────────────────────────── */

export default function ModelLab() {
  const { data: report, error } = useApi<Report>("/api/model/report");
  const [tab, setTab] = useState("week");
  const help = useMemo(() => Object.fromEntries((report?.coefs ?? []).map((c) => [c.feature, c.help])), [report]);

  if (error) return <p className="text-body text-muted">Couldn't load the model — {error}</p>;
  if (report && !report.available) {
    return (
      <div className="space-y-4">
        <PageHeader title="Model Lab" subtitle="No trained model in this warehouse yet." />
        <Panel><p className="text-body text-muted">Run <code className="text-ink">Train model</code> from <Link to="/ops" className="text-accent">Ops</Link> (about five minutes), then come back.</p></Panel>
      </div>
    );
  }
  const h = report?.holdout;
  return (
    <div className="space-y-4">
      <PageHeader
        title="Model Lab"
        subtitle="How the Jarvis prediction model thinks, and how it scores — a yardstick, not an oracle."
        actions={<AskAnalyst question="Explain the Jarvis model's holdout report card to a first-time modeler: what Brier means, why the market wins, and what the calibration gap is telling us." />}
        meta={report && h ? (
          <>
            <Chip tone="accent">{report.config.ratings_source} ratings · h{report.config.half_life} c{report.config.carryover}{report.config.qb_flag ? " · QB flag" : ""}</Chip>
            <Chip>fitted {report.fitted_at.slice(0, 10)}</Chip>
            <Chip>holdout Brier {f4(h.brier_model)} vs market {f4(h.brier_market)}</Chip>
            <Link to="/knowledge/model-primer" className="text-micro text-accent hover:underline">how it works →</Link>
          </>
        ) : undefined}
      />
      <Tabs items={TABS} value={tab} onChange={setTab} ariaLabel="Model Lab sections" />
      {tab === "week" && <ThisWeek help={help} />}
      {tab === "report" && (report ? <ReportCard r={report} /> : <p className="text-body text-muted">Loading…</p>)}
      {tab === "ratings" && <PowerRatings />}
      {tab === "experiments" && <ExperimentsTab />}
    </div>
  );
}
