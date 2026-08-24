import { Chip, DataTable, LinkCell, Panel } from "../components/ui";
import type { ChipTone, Column } from "../components/ui";
import { useApi } from "../lib/useApi";

// Content for the Betting page's "My Rules" view (route stays /betting).
// Shapes mirror src/nfl_analytics/rules.py::betting_rules_payload.

interface RuleClause { field: string; op: string; value: unknown }

interface RuleHit {
  game_id: string;
  season: number | null;
  week: number | null;
  date: string | null;
  matchup: string;
  side: string; // resolved: home | away | over | under
  bet_team: string | null;
  facts: Record<string, number | string | null>;
}

interface BacktestSummary {
  insufficient_history: boolean;
  tracking_since?: string; // "2026-08" on live-only rules
  reason?: string;         // "no gradeable games in history"
  bets?: number; wins?: number; losses?: number; pushes?: number;
  win_pct?: number | null; profit_units?: number; roi?: number | null;
  breakeven?: number; profitable?: boolean; market?: string;
  coverage_start?: number; coverage_end?: number;
}

interface BettingRule {
  id: string;
  family: string; // situational | line_movement | environment | dislocation
  label: string;
  enabled: boolean;
  market: string; // spread | moneyline | total | kalshi
  side: string;   // home | away | favorite | underdog | rested | cheap_side | over | under
  live_only: boolean;
  when: RuleClause[];
  scope: { season_type?: string };
  notes: string;
  week_hits: RuleHit[];
  backtest_summary: BacktestSummary | null;
}

interface RulesPayload { season: number; week: number; rules: BettingRule[] }

const FAMILY_TONE: Record<string, ChipTone> = {
  situational: "neutral",
  line_movement: "accent",
  environment: "positive",
  dislocation: "warning",
};

// field id -> plain-English phrase for the predicate line
const FIELD_TEXT: Record<string, string> = {
  div_game: "division game",
  spread_line: "spread",
  total_line: "total line",
  home_moneyline: "home moneyline",
  away_moneyline: "away moneyline",
  favorite: "favorite",
  home_rest_days: "home rest days",
  away_rest_days: "away rest days",
  rest_edge_days: "rest edge (home − away days)",
  home_travel_miles: "home travel miles",
  away_travel_miles: "away travel miles",
  home_tz_shift_hours: "home tz shift (hrs east)",
  away_tz_shift_hours: "away tz shift (hrs east)",
  wx_wind_mph: "wind (mph)",
  wx_temp_f: "temperature (°F)",
  wx_precip: "precipitation (in)",
  wx_is_indoor: "indoors",
  kickoff_et_hour: "kickoff hour (ET)",
  is_primetime: "primetime",
  ref_games: "ref career games",
  ref_over_rate: "ref career over rate",
  ref_pen_per_game: "ref penalties/game",
  ref_home_cover_rate: "ref home cover rate",
  kalshi_home_prob: "Kalshi home prob",
  vegas_home_prob: "devigged Vegas home prob",
  dislocation_gap: "Kalshi − Vegas gap",
  dislocation_fee: "Kalshi fee",
  dislocation_actionable: "dislocation actionable",
  spread_open: "opening spread",
  spread_now: "current spread",
  spread_move: "spread move since open",
  total_open: "opening total",
  total_now: "current total",
  total_move: "total move since open",
};

const fieldText = (f: string) => FIELD_TEXT[f] ?? f.replace(/_/g, " ");

function clauseText(c: RuleClause): string {
  const f = fieldText(c.field);
  switch (c.op) {
    case "==":
      if (c.value === true) return f;
      if (c.value === false) return `not ${f}`;
      return `${f} is ${String(c.value)}`;
    case "!=": return `${f} is not ${String(c.value)}`;
    case ">": return `${f} > ${String(c.value)}`;
    case ">=": return `${f} ≥ ${String(c.value)}`;
    case "<": return `${f} < ${String(c.value)}`;
    case "<=": return `${f} ≤ ${String(c.value)}`;
    case "abs_gte": return `|${f}| ≥ ${String(c.value)}`;
    case "between": {
      const [lo, hi] = Array.isArray(c.value) ? c.value : ["?", "?"];
      return `${f} between ${String(lo)} and ${String(hi)}`;
    }
    case "in":
      return `${f} in [${Array.isArray(c.value) ? c.value.map(String).join(", ") : String(c.value)}]`;
    case "is_null": return `${f} missing`;
    case "not_null": return `${f} known`;
    default: return `${f} ${c.op} ${String(c.value)}`;
  }
}

const sideText = (s: string) => s.replace(/_/g, " ");

// clause field -> the week_hits facts key that best evidences it (facts only
// carries the _HIT_FACTS subset server-side)
const TRIGGER_FACT: Record<string, string> = {
  div_game: "spread_line",
  favorite: "spread_line",
  home_rest_days: "rest_edge_days",
  away_rest_days: "rest_edge_days",
  wx_is_indoor: "wx_wind_mph",
  ref_games: "ref_over_rate",
  kickoff_et_hour: "spread_line",
  away_tz_shift_hours: "spread_line",
  home_tz_shift_hours: "spread_line",
  dislocation_actionable: "dislocation_gap",
  dislocation_fee: "dislocation_gap",
  spread_open: "spread_move",
  spread_now: "spread_move",
  total_open: "total_move",
  total_now: "total_move",
};

const FACT_TEXT: Record<string, string> = {
  spread_line: "spread",
  total_line: "total",
  wx_wind_mph: "wind",
  rest_edge_days: "rest edge",
  ref_over_rate: "ref over%",
  spread_move: "spread move",
  total_move: "total move",
  dislocation_gap: "gap",
  kalshi_home_prob: "kalshi",
  vegas_home_prob: "vegas",
};

const PCT_FACTS = new Set(["ref_over_rate", "dislocation_gap", "kalshi_home_prob", "vegas_home_prob"]);

const pct = (v: number | null | undefined, digits = 1) =>
  v != null ? `${(v * 100).toFixed(digits)}%` : "—";

const fmtFact = (k: string, v: number | string | null) => {
  if (v == null) return "—";
  if (typeof v === "number" && PCT_FACTS.has(k)) return pct(v);
  return String(v);
};

function triggersText(rule: BettingRule, h: RuleHit): string {
  const wanted = new Set(rule.when.map((c) => TRIGGER_FACT[c.field] ?? c.field));
  let pairs = Object.entries(h.facts).filter(([k]) => wanted.has(k));
  if (!pairs.length) pairs = Object.entries(h.facts);
  if (!pairs.length) return "—";
  return pairs.map(([k, v]) => `${FACT_TEXT[k] ?? fieldText(k)} ${fmtFact(k, v)}`).join(" · ");
}

const homeOf = (matchup: string) => matchup.split(" @ ")[1] ?? "";
const awayOf = (matchup: string) => matchup.split(" @ ")[0] ?? "";

// spread_line positive = home favored (gotcha #6)
function lineText(rule: BettingRule, h: RuleHit): string {
  if (rule.market === "spread") {
    const sl = h.facts.spread_line;
    if (typeof sl !== "number") return "—";
    if (sl === 0) return "PK";
    return sl > 0 ? `${homeOf(h.matchup)} −${sl}` : `${awayOf(h.matchup)} −${Math.abs(sl)}`;
  }
  if (rule.market === "total") {
    const tl = h.facts.total_line;
    return typeof tl === "number" ? `o/u ${tl}` : "—";
  }
  if (rule.market === "kalshi") {
    const k = h.facts.kalshi_home_prob, v = h.facts.vegas_home_prob;
    if (typeof k !== "number") return "—";
    return `K ${pct(k)} vs V ${typeof v === "number" ? pct(v) : "—"} home`;
  }
  return "—"; // moneyline odds aren't in the hit facts
}

const lineValue = (rule: BettingRule, h: RuleHit): number | null => {
  const v = rule.market === "total" ? h.facts.total_line
    : rule.market === "kalshi" ? h.facts.dislocation_gap
    : h.facts.spread_line;
  return typeof v === "number" ? v : null;
};

const hitColumns = (rule: BettingRule): Column<RuleHit>[] => [
  {
    key: "matchup", label: "Matchup", sortable: false,
    help: "Away @ home — click through to the matchup page.",
    render: (h) => <LinkCell to={`/matchup/${h.game_id}`}>{h.matchup}</LinkCell>,
  },
  {
    key: "date", label: "Date", sortable: false,
    help: "Scheduled kickoff date (ET).",
    render: (h) => <span className="text-muted">{h.date ?? "—"}</span>,
  },
  {
    key: "triggers", label: "Triggering values", sortable: false,
    help: "This game's values for the fields the rule tests.",
    value: (h) => triggersText(rule, h),
    render: (h) => <span className="text-muted">{triggersText(rule, h)}</span>,
  },
  {
    key: "side", label: "Bet side",
    help: "The side the rule resolves to for this game — a team for spread/moneyline/Kalshi rules, over/under for totals.",
    value: (h) => h.bet_team ?? h.side,
    render: (h) => (
      <span className="font-medium text-ink">
        {h.bet_team ? `${h.bet_team} (${h.side})` : h.side}
      </span>
    ),
  },
  {
    key: "line", label: "Line", numeric: true,
    help: "Closing market for the bet: the spread (favorite − points), the total, or Kalshi vs devigged Vegas home probability.",
    value: (h) => lineValue(rule, h),
    render: (h) => <span className="tabular-nums">{lineText(rule, h)}</span>,
  },
];

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const fmtSince = (s?: string) => {
  if (!s) return "";
  const [y, m] = s.split("-");
  return `${MONTHS[+m - 1] ?? m} ${y}`;
};

const fmtUnits = (u?: number) =>
  u == null ? "—" : `${u > 0 ? "+" : u < 0 ? "−" : ""}${Math.abs(u).toFixed(1)}u`;

function BacktestLine({ bt }: { bt: BacktestSummary }) {
  if (bt.insufficient_history) {
    return (
      <p data-testid="rule-no-backtest" className="mt-3 border-t border-border pt-2 text-micro italic text-muted">
        {bt.tracking_since
          ? `no backtest — live-only signal, tracking since ${fmtSince(bt.tracking_since)}`
          : `no backtest — ${bt.reason ?? "insufficient history"}`}
      </p>
    );
  }
  const breakeven = bt.breakeven ?? 0.524;
  const winCls =
    bt.win_pct == null ? "text-muted"
      : bt.win_pct > breakeven ? "text-positive"
      : bt.win_pct < breakeven ? "text-negative" : "text-muted";
  return (
    <p data-testid="rule-backtest" className="mt-3 border-t border-border pt-2 text-micro text-muted">
      Backtest{" "}
      <span className="font-semibold tabular-nums text-ink">
        {bt.wins}–{bt.losses}–{bt.pushes}
      </span>
      {" · "}
      <span className={`font-semibold tabular-nums ${winCls}`}>{pct(bt.win_pct)} win</span>
      {" vs "}{pct(breakeven)} breakeven
      {" · "}
      <span className="tabular-nums">{fmtUnits(bt.profit_units)} flat (ROI {pct(bt.roi)})</span>
      {" · "}
      <span className="tabular-nums">{bt.coverage_start}–{bt.coverage_end}, {bt.bets} bets</span>
    </p>
  );
}

function RuleCard({ rule, week }: { rule: BettingRule; week: number }) {
  const predicate = rule.when.map(clauseText).join(" and ");
  const scope = rule.scope.season_type ? ` · ${rule.scope.season_type} only` : "";
  const bet = `${rule.market === "kalshi" ? "Kalshi" : rule.market} — ${sideText(rule.side)}`;

  const header = (
    <div className="flex flex-wrap items-center gap-2">
      <span className="font-semibold text-ink">{rule.label}</span>
      <Chip tone={FAMILY_TONE[rule.family] ?? "neutral"}>{rule.family.replace(/_/g, " ")}</Chip>
      {rule.live_only && <Chip>live-only</Chip>}
      {!rule.enabled && <Chip>disabled</Chip>}
    </div>
  );

  // disabled rules collapse to their header + predicate, muted
  if (!rule.enabled) {
    return (
      <div data-testid="rule-card" className="opacity-60">
        <Panel>
          {header}
          <p className="mt-1.5 text-micro text-muted">
            when {predicate}{scope} → bet {bet} · not evaluated while disabled
          </p>
        </Panel>
      </div>
    );
  }

  return (
    <div data-testid="rule-card">
      <Panel>
        {header}
        <p className="mt-1.5 text-micro text-muted">
          when {predicate}{scope} <span className="text-ink">→ bet {bet}</span>
        </p>
        {rule.notes && <p className="mt-1 text-micro italic text-muted">{rule.notes}</p>}

        <div className="mt-3 border-t border-border">
          <div className="-mx-4">
            <DataTable
              columns={hitColumns(rule)}
              rows={rule.week_hits}
              rowKey={(h) => h.game_id}
              caption={`Week ${week} games triggering ${rule.label}`}
              empty={<>No week {week} games trigger this rule.</>}
            />
          </div>
        </div>

        {rule.backtest_summary && <BacktestLine bt={rule.backtest_summary} />}
      </Panel>
    </div>
  );
}

export default function BettingRules() {
  const { data, error, loading } = useApi<RulesPayload>("/api/rules");

  if (error) {
    return (
      <Panel>
        <p className="py-4 text-center text-body text-muted">
          Couldn't load the rules — {error}
        </p>
      </Panel>
    );
  }
  if (loading || !data) {
    return (
      <Panel>
        <p className="py-4 text-center text-body text-muted">
          Evaluating rules against the week and 1999+ history…
        </p>
      </Panel>
    );
  }

  return (
    <div className="space-y-4">
      <p className="text-micro text-muted">
        {data.rules.length} hand-curated rules from <code>data/betting_rules.json</code> —
        edit the file, not the app. Evaluated against {data.season} week {data.week};
        backtests grade closing lines at −110 (moneylines at actual odds), breakeven 52.4%.
      </p>
      <div className="grid gap-4 xl:grid-cols-2">
        {data.rules.map((rule) => (
          <RuleCard key={rule.id} rule={rule} week={data.week} />
        ))}
      </div>
    </div>
  );
}
