import { useEffect, useMemo, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import type { NewsItem, RosterPlayer, TeamDetail, TeamScheduleGame } from "../lib/api";
import { useApi } from "../lib/useApi";
import { useMeta } from "../lib/MetaContext";
import { useTeamTokens } from "../lib/useTeamTokens";
import { LineChart } from "../components/charts";
import {
  Chip, DataTable, Field, PageHeader, Panel, PillGroup, Select, StatTile, Tip, Toolbar,
} from "../components/ui";
import type { Column } from "../components/ui";

/* ── types (page-local; single-page endpoints) ─────────────────────────── */
interface StaffBlock { name: string; since: number; playcaller: boolean; about: string }
interface Scheme { family: string; fact: string; knowledge: string }
interface StandingRow { team: string; w: number; l: number; t: number; pct: number; pf: number; pa: number }
interface FranchiseRow { season: number; w: number; l: number; t: number; playoffs: string | null }
interface Overview {
  code: string; season: number; division: string | null; div_rank: number | null;
  header: { w: number; l: number; t: number; pf_pg: number | null; pa_pg: number | null;
            pf_rank: number | null; pa_rank: number | null };
  staff: { head_coach: string | null; hc: { since: number; about: string } | null;
           oc: StaffBlock | null; dc: StaffBlock | null;
           offense_scheme: Scheme | null; defense_scheme: Scheme | null; note: string | null };
  leaders: { key: string; label: string; player_id?: string; name?: string;
             headshot?: string | null; value?: number }[];
  standings: StandingRow[];
  epa: { off_epa: number; off_rank: number; def_epa: number; def_rank: number;
         pass_epa: number; pass_rank: number; rush_epa: number; rush_rank: number } | null;
  travel: { total_travel_miles?: number; avg_road_trip_miles?: number; max_trip_miles?: number;
            international_games?: number; total_tz_hours?: number; short_weeks?: number; byes?: number };
  franchise: FranchiseRow[];
  injuries: { player: string; position: string | null; status: string; injury: string | null }[];
}
interface ResultRow {
  game_id: string; week: number; game_type: string; season_type: string; date: string;
  site: string; opponent: string; win: number; team_score: number; opp_score: number;
  overtime: boolean; w_td: number; l_td: number; t_td: number; streak: string | null;
  spread_line_team: number | null; covered: boolean | null; total_line: number | null;
  went_over: boolean | null; team_qb: string | null; opp_qb: string | null;
  referee: string | null; venue_name: string | null;
  rest_days_sched: number | null; travel_miles: number | null;
}
interface Results {
  season: number; seasons: number[];
  summary: { w: number; l: number; t: number; ats_w: number; ats_l: number;
             overs: number; unders: number; home_w: number; home_l: number;
             away_w: number; away_l: number };
  rows: ResultRow[];
}

const HELP = {
  epa_off: "Offensive EPA per play — expected points added by the offense each snap; league rank in parentheses",
  epa_def: "Defensive EPA per play allowed — lower is better; rank 1 = stingiest defense",
  epa_pass: "EPA per pass play (offense)",
  epa_rush: "EPA per rush play (offense)",
  wk: "Week of the season; playoff games show the round instead",
  date: "Kickoff date",
  opp: "Opponent — vs is home, @ is away, n is a neutral site",
  result: "Final score from this team's perspective",
  rec: "Cumulative regular-season record after this game (ESPN convention)",
  strk: "Running win/loss streak through this game",
  spread: "Closing spread from this team's perspective (negative = favored)",
  ats: "Against the spread: ✓ covered, ✗ didn't, — push or no line",
  ou: "Total (over/under) result for this game",
  rest: "Days since this team's previous game (schedules-based, populated week 1)",
  travel: "Miles from this team's home stadium to the game venue (haversine)",
  qbs: "Starting quarterbacks, this team first",
  ref: "Head referee assigned to the game",
  pf: "Points scored per game (league rank)",
  pa: "Points allowed per game (rank 1 = fewest allowed)",
  ats_sum: "Season record against the closing spread (pushes excluded)",
  ou_sum: "How often this team's games went over the total",
  miles: "Season travel: sum of home-base-to-venue miles across all games",
  tz: "Total timezone hours crossed this season",
  st_team: "Division rival — click through to their page",
  st_w: "Wins this season",
  st_l: "Losses this season",
  st_t: "Ties this season",
  st_pct: "Win percentage; ties count as half a win",
  st_pf: "Total points scored",
  st_pa: "Total points allowed",
  ro_num: "Jersey number",
  ro_player: "Click a player to open their page",
  ro_pos: "Position",
  ro_college: "College the player was drafted or signed out of",
  fr_season: "Season — click a row to open that season's game-by-game results",
  fr_record: "Regular-season record that year",
  fr_playoffs: "How far the postseason run went, if any",
} as const;

const TABS = [["overview", "Overview"], ["results", "Results"],
              ["roster", "Roster"], ["stats", "Stats"]] as const;

export default function TeamHUD() {
  const { code = "" } = useParams();
  const [params, setParams] = useSearchParams();
  const meta = useMeta();
  const c = code.toUpperCase();
  const t = meta?.teams[c];
  const tab = params.get("tab") ?? "overview";
  const setTab = (v: string, extra?: Record<string, string>) =>
    setParams({ tab: v, ...extra }, { replace: false });

  const [resSeason, setResSeason] = useState<number | undefined>();
  const [rosterSeason, setRosterSeason] = useState<number>(2026);
  const [rosterSeasons, setRosterSeasons] = useState<number[]>([]);
  const [posFilter, setPosFilter] = useState("");
  const [epaSeason, setEpaSeason] = useState<number | null>(null);

  const { data: ov, error: ovErr } = useApi<Overview>(c ? `/api/teams/${c}/overview` : null);
  const { data: detail, error: detailErr } =
    useApi<TeamDetail>(c ? `/api/teams/${c}?season=2025` : null);
  const { data: schedData, error: schedErr } =
    useApi<{ season: number; games: TeamScheduleGame[] }>(c ? `/api/teams/${c}/schedule?season=2026` : null);
  const { data: newsData, error: newsErr } =
    useApi<{ items: NewsItem[] }>(c ? `/api/teams/${c}/news?limit=20` : null);
  const { data: res, error: resErr } = useApi<Results>(
    c && tab === "results"
      ? `/api/teams/${c}/results${resSeason ? `?season=${resSeason}` : ""}` : null);
  const { data: rosterData, error: rosterErr } = useApi<{
    season: number; players: RosterPlayer[]; seasons?: number[];
  }>(c && tab === "roster" ? `/api/teams/${c}/roster?season=${rosterSeason}` : null);
  const { data: epaData, error: epaErr } = useApi<{
    season: number; weeks: { week: number; off: number | null; def: number | null }[];
  }>(c && tab === "stats" ? `/api/teams/${c}/epa${epaSeason ? `?season=${epaSeason}` : ""}` : null);

  // keep the season picker populated while a roster refetch is in flight
  useEffect(() => {
    if (rosterData?.seasons?.length) setRosterSeasons(rosterData.seasons);
  }, [rosterData]);

  const { style: teamStyle } = useTeamTokens(c);

  const roster = useMemo(() => rosterData?.players ?? [], [rosterData]);
  const sched = schedData?.games ?? [];
  const news = newsData?.items ?? [];
  const coachHist = detail?.coach.history ?? [];
  const epaWeeks = epaData?.weeks ?? [];

  const positions = useMemo(
    () => [...new Set(roster.map((p) => p.pos).filter(Boolean))].sort() as string[],
    [roster]);

  const standingsCols = useMemo<Column<StandingRow>[]>(() => [
    {
      key: "team", label: "Team", help: HELP.st_team,
      render: (r) => (
        <Link to={`/team/${r.team}`} className="flex items-center gap-2 hover:underline">
          {meta?.teams[r.team] && (
            <img src={meta.teams[r.team].logo} alt="" className="h-5 w-5" />)}
          {r.team}
        </Link>
      ),
    },
    { key: "w", label: "W", numeric: true, help: HELP.st_w },
    { key: "l", label: "L", numeric: true, help: HELP.st_l },
    { key: "t", label: "T", numeric: true, help: HELP.st_t },
    { key: "pct", label: "PCT", numeric: true, help: HELP.st_pct,
      render: (r) => r.pct?.toFixed(3) ?? "—" },
    { key: "pf", label: "PF", numeric: true, help: HELP.st_pf },
    { key: "pa", label: "PA", numeric: true, help: HELP.st_pa },
  ], [meta]);

  const resultCols = useMemo<Column<ResultRow>[]>(() => [
    {
      key: "week", label: "Wk", help: HELP.wk, value: (g) => g.week,
      render: (g) => g.season_type === "POST"
        ? <span className="font-bold text-accent">{g.game_type}</span>
        : <span className="text-micro tabular-nums text-muted">{g.week}</span>,
    },
    {
      key: "date", label: "Date", help: HELP.date,
      render: (g) => <span className="text-micro text-muted">{g.date}</span>,
    },
    {
      key: "opponent", label: "Opponent", help: HELP.opp,
      render: (g) => (
        <span className="flex items-center gap-1.5">
          <span className="text-micro text-muted">
            {g.site === "home" ? "vs" : g.site === "away" ? "@" : "n"}
          </span>
          {meta?.teams[g.opponent] && (
            <img src={meta.teams[g.opponent].logo} alt="" className="h-5 w-5" />)}
          <span className="font-medium">{g.opponent}</span>
        </span>
      ),
    },
    {
      key: "result", label: "Result", help: HELP.result,
      value: (g) => g.team_score - g.opp_score,
      render: (g) => (
        <span className="tabular-nums">
          <span className={`font-bold ${
            g.win === 1 ? "text-positive" : g.win === 0 ? "text-negative" : "text-muted"}`}>
            {g.win === 1 ? "W" : g.win === 0 ? "L" : "T"}
          </span>{" "}
          {g.team_score}–{g.opp_score}{g.overtime ? " OT" : ""}
        </span>
      ),
    },
    {
      key: "rec", label: "Rec", help: HELP.rec, value: (g) => g.w_td,
      render: (g) => (
        <span className="text-micro tabular-nums text-muted">
          {g.season_type === "REG" ? `${g.w_td}–${g.l_td}${g.t_td ? `–${g.t_td}` : ""}` : "—"}
        </span>
      ),
    },
    {
      key: "streak", label: "Strk", help: HELP.strk,
      render: (g) => <span className="text-micro tabular-nums text-muted">{g.streak ?? "—"}</span>,
    },
    {
      key: "spread", label: "Spread", numeric: true, help: HELP.spread,
      value: (g) => (g.spread_line_team != null ? -g.spread_line_team : null),
      render: (g) => (
        <span className="text-micro tabular-nums text-muted">
          {g.spread_line_team != null
            ? (g.spread_line_team > 0 ? `-${g.spread_line_team}` : `+${-g.spread_line_team}`)
            : "—"}
        </span>
      ),
    },
    {
      key: "ats", label: "ATS", help: HELP.ats,
      value: (g) => (g.covered == null ? null : g.covered ? 1 : 0),
      render: (g) => g.covered == null
        ? <span className="text-micro text-muted">—</span>
        : g.covered
          ? <span className="text-micro text-positive">✓</span>
          : <span className="text-micro text-negative">✗</span>,
    },
    {
      key: "ou", label: "O/U", help: HELP.ou,
      value: (g) => (g.went_over == null ? null : g.went_over ? 1 : 0),
      render: (g) => (
        <span className="text-micro text-muted">
          {g.went_over == null ? "—" : g.went_over ? `O ${g.total_line}` : `U ${g.total_line}`}
        </span>
      ),
    },
    {
      key: "rest", label: "Rest", numeric: true, help: HELP.rest,
      value: (g) => g.rest_days_sched,
      render: (g) => (
        <span className="text-micro tabular-nums text-muted">{g.rest_days_sched ?? "—"}</span>
      ),
    },
    {
      key: "travel", label: "Travel", numeric: true, help: HELP.travel,
      value: (g) => g.travel_miles,
      render: (g) => (
        <span className="text-micro tabular-nums text-muted">
          {g.travel_miles != null && g.travel_miles > 25 ? `${g.travel_miles.toLocaleString()} mi` : "—"}
        </span>
      ),
    },
    {
      key: "qbs", label: "QBs", help: HELP.qbs, sortable: false,
      render: (g) => (
        <span className="block max-w-52 truncate text-micro text-muted">
          {g.team_qb ?? "—"} v {g.opp_qb ?? "—"}
        </span>
      ),
    },
    {
      key: "referee", label: "Ref", help: HELP.ref,
      render: (g) => (
        <span className="block max-w-32 truncate text-micro text-muted">{g.referee ?? "—"}</span>
      ),
    },
  ], [meta]);

  const rosterCols = useMemo<Column<RosterPlayer>[]>(() => [
    {
      key: "num", label: "#", numeric: true, help: HELP.ro_num,
      render: (p) => <span className="tabular-nums text-muted">{p.num ?? ""}</span>,
    },
    {
      key: "name", label: "Player", help: HELP.ro_player,
      render: (p) => (
        <span className="flex items-center gap-2 font-medium">
          {p.headshot && (
            <img src={p.headshot} alt="" className="h-6 w-6 rounded-full object-cover"
                 onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }} />)}
          {p.gsis ? (
            <Link to={`/player/${p.gsis}`} className="hover:underline">{p.name}</Link>
          ) : p.name}
        </span>
      ),
    },
    { key: "pos", label: "Pos", help: HELP.ro_pos },
    {
      key: "college", label: "College", help: HELP.ro_college,
      render: (p) => <span className="text-micro text-muted">{p.college ?? "—"}</span>,
    },
  ], []);

  const franchiseCols = useMemo<Column<FranchiseRow>[]>(() => [
    { key: "season", label: "Season", help: HELP.fr_season },
    {
      key: "record", label: "Record", help: HELP.fr_record, value: (f) => f.w,
      render: (f) => <span className="tabular-nums">{f.w}–{f.l}{f.t ? `–${f.t}` : ""}</span>,
    },
    {
      key: "playoffs", label: "Playoffs", help: HELP.fr_playoffs,
      render: (f) => (
        <span className={f.playoffs === "SB champs" ? "text-accent" : "text-muted"}>
          {f.playoffs ?? "—"}
        </span>
      ),
    },
  ], []);

  if (!t) return null;
  if (ovErr) {
    return <p className="text-body text-muted">Couldn't load {c}'s overview: {ovErr}</p>;
  }
  if (!ov) return null;
  const h = ov.header;
  const games = h.w + h.l + h.t;
  const s = ov.staff;

  return (
    // team tokens are IDENTITY only: a rail, a wash, a logo backdrop.
    // --accent stays fixed so "clickable" means the same thing on every page.
    <div className="space-y-6" style={teamStyle}>
      {/* banner — the clamped team wash, not the raw brand hex */}
      <div className="rail-team relative overflow-hidden rounded-[var(--radius-panel)] border border-border bg-surface p-8">
        <div aria-hidden className="bg-team-wash absolute inset-0" />
        <img src={t.logo} alt="" aria-hidden
             className="pointer-events-none absolute -right-6 -top-8 h-40 w-40 opacity-10" />
        <div className="relative">
          <PageHeader
            crumbs={[{ label: "Teams", to: "/" }, { label: t.name }]}
            media={<img src={t.logo} alt={t.name} className="h-20 w-20" />}
            title={t.name}
            subtitle={
              <>
                {ov.div_rank ? `${ov.div_rank}${["st", "nd", "rd"][ov.div_rank - 1] ?? "th"} ${ov.division}` : `${t.conf} ${t.div}`}
                {" · head coach "}
                {s.head_coach ? (
                  <Link to={`/coach/${encodeURIComponent(s.head_coach)}`}
                        className="font-semibold text-accent hover:underline">
                    {s.head_coach}
                  </Link>
                ) : "—"}
                {" · "}{ov.season}
              </>
            } />
          <div className="grid gap-2 sm:grid-cols-3">
            <StatTile label={`${ov.season} record`}
                      value={`${h.w}–${h.l}${h.t ? `–${h.t}` : ""}`}
                      meter={games ? h.w / games : 0}
                      sub={games ? `${Math.round((h.w / games) * 100)}% win rate` : undefined} />
            <StatTile label="points / game" value={h.pf_pg?.toFixed(1) ?? "—"}
                      rank={h.pf_rank ?? null} meter={(h.pf_pg ?? 0) / 35}
                      help={HELP.pf} />
            <StatTile label="allowed / game" value={h.pa_pg?.toFixed(1) ?? "—"}
                      rank={h.pa_rank ?? null} meter={1 - (h.pa_pg ?? 35) / 35}
                      help={HELP.pa} />
          </div>
        </div>
      </div>

      {s.note && <p className="text-body italic text-muted">⚑ {s.note}</p>}

      {/* tabs */}
      <PillGroup
        ariaLabel="Team view"
        options={TABS.map(([value, label]) => ({ value, label }))}
        value={tab}
        onChange={(v) => setTab(v)} />

      {/* ───────────────────────────── OVERVIEW ───────────────────────────── */}
      {tab === "overview" && (
        <>
          {ov.epa && (
            <div className="grid gap-3 sm:grid-cols-4">
              {[["Offense EPA", ov.epa.off_epa, ov.epa.off_rank, HELP.epa_off],
                ["Defense EPA", ov.epa.def_epa, ov.epa.def_rank, HELP.epa_def],
                ["Pass EPA", ov.epa.pass_epa, ov.epa.pass_rank, HELP.epa_pass],
                ["Rush EPA", ov.epa.rush_epa, ov.epa.rush_rank, HELP.epa_rush]].map(([lbl, v, rank, help]) => (
                <Tip key={lbl as string} text={help as string}>
                  <div className="rounded-[var(--radius-panel)] border border-border bg-surface w-full p-3 text-center">
                    <div className="text-micro uppercase tracking-[0.12em] text-muted">{lbl}</div>
                    <div className="font-display mt-1 text-h1 font-bold text-ink">
                      {(v as number) > 0 ? "+" : ""}{v as number}
                      <span className="ml-1.5 text-h3 font-semibold text-muted">#{rank as number}</span>
                    </div>
                  </div>
                </Tip>
              ))}
            </div>
          )}

          <div className="grid gap-4 lg:grid-cols-3">
            <Panel title="Head coach">
              {s.head_coach && (
                <>
                  <Link to={`/coach/${encodeURIComponent(s.head_coach)}`}
                        className="text-lg font-semibold text-accent hover:underline">
                    {s.head_coach}
                  </Link>
                  <p className="text-xs text-muted">since {s.hc?.since}</p>
                  <p className="mt-2 text-sm text-muted">{s.hc?.about}</p>
                </>
              )}
            </Panel>
            {(["oc", "dc"] as const).map((role) => {
              const b = s[role];
              const scheme = role === "oc" ? s.offense_scheme : s.defense_scheme;
              return (
                <Panel key={role} title={role === "oc" ? "Offensive coordinator" : "Defensive coordinator"}>
                  {b ? (
                    <>
                      <span className="flex items-center gap-2">
                        <Link to={`/coach/${encodeURIComponent(b.name)}?role=${role.toUpperCase()}`}
                              className="text-lg font-semibold text-accent hover:underline">
                          {b.name}
                        </Link>
                        {b.playcaller && <Chip tone="accent">calls plays</Chip>}
                      </span>
                      <p className="text-xs text-muted">since {b.since}</p>
                    </>
                  ) : (
                    <p className="text-sm text-muted">
                      No {role.toUpperCase()} title — the head coach runs this unit.
                    </p>
                  )}
                  {scheme && (
                    <Link to={`/knowledge/${scheme.knowledge}`}
                          className="mt-2 block text-sm text-accent hover:underline">
                      {scheme.family} →
                    </Link>
                  )}
                </Panel>
              );
            })}
          </div>

          <div>
            <h2 className="mb-3 text-sm font-bold uppercase tracking-widest text-accent">
              {ov.season} team leaders
            </h2>
            <div className="grid gap-3 sm:grid-cols-5">
              {ov.leaders.map((ld) => (
                <Link key={ld.key} to={ld.player_id ? `/player/${ld.player_id}` : "#"}
                      className="rounded-[var(--radius-panel)] border border-border bg-surface flex items-center gap-3 p-3 transition-transform hover:-translate-y-0.5">
                  {ld.headshot && (
                    <img src={ld.headshot} alt="" className="h-10 w-10 rounded-full object-cover"
                         onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }} />
                  )}
                  <div className="min-w-0">
                    <div className="truncate text-sm font-semibold">{ld.name ?? "—"}</div>
                    <div className="text-xs text-muted">
                      <span className="tabular-nums font-semibold text-accent">
                        {ld.value?.toLocaleString() ?? "—"}
                      </span>{" "}{ld.label}
                    </div>
                  </div>
                </Link>
              ))}
            </div>
          </div>

          <div className="grid gap-6 lg:grid-cols-2">
            <Panel title={`${ov.division ?? "Division"} standings`} flush>
              <DataTable
                columns={standingsCols}
                rows={ov.standings}
                rowKey={(r) => r.team}
                rowClass={(r) => (r.team === c ? "bg-surface-2 font-bold" : "")}
                caption={`${ov.division ?? "Division"} standings, ${ov.season}`}
                empty="Standings not loaded." />
            </Panel>

            <Panel title="Travel & rest profile">
              <div className="flex flex-wrap gap-2">
                <Tip text={HELP.miles}><Chip tone="accent">{(ov.travel.total_travel_miles ?? 0).toLocaleString()} mi this season</Chip></Tip>
                <Tip text="Average one-way miles for road games"><Chip>{ov.travel.avg_road_trip_miles?.toLocaleString() ?? "—"} mi avg road trip</Chip></Tip>
                <Tip text="Longest single trip"><Chip>{ov.travel.max_trip_miles?.toLocaleString() ?? "—"} mi longest</Chip></Tip>
                <Tip text={HELP.tz}><Chip>{ov.travel.total_tz_hours ?? 0} tz hours</Chip></Tip>
                <Tip text="Games abroad"><Chip tone={ov.travel.international_games ? "warning" : "neutral"}>{ov.travel.international_games ?? 0} international</Chip></Tip>
                <Tip text="Games on 5 or fewer days rest"><Chip>{ov.travel.short_weeks ?? 0} short weeks</Chip></Tip>
              </div>
              <p className="mt-3 text-xs text-muted">
                Computed from the curated venue database — home-base haversine miles per game.
              </p>
            </Panel>
          </div>

          <Panel title="2026 schedule">
            {schedErr && <p className="text-micro text-muted">Couldn't load the schedule: {schedErr}</p>}
            <div className="flex gap-2 overflow-x-auto pb-1">
              {sched.map((g) => (
                <Link key={g.week} to={`/matchup/${g.game_id}`}
                      className="min-w-32 rounded-xl border border-border p-2.5 text-center text-xs transition-colors hover:bg-surface-2">
                  <div className="font-bold text-muted">WK {g.week}</div>
                  <div className="mt-1 font-semibold">{g.home ? "vs" : "@"} {g.opponent}</div>
                  <div className="mt-0.5 text-muted">{g.date}</div>
                  {g.line_text && <div className="mt-1 text-accent">{g.line_text}</div>}
                </Link>
              ))}
            </div>
          </Panel>

          <Panel title="Franchise, season by season (2007+)">
            <div className="flex gap-1.5 overflow-x-auto pb-1">
              {ov.franchise.map((f) => (
                <button key={f.season}
                        onClick={() => { setResSeason(f.season); setTab("results"); }}
                        className={`min-w-16 rounded-lg border p-1.5 text-center text-[11px] transition-colors hover:bg-surface-2 ${
                          f.playoffs === "SB champs" ? "border-accent" : "border-border"}`}>
                  <div className="text-muted">{f.season}</div>
                  <div className="font-bold tabular-nums">{f.w}–{f.l}{f.t ? `–${f.t}` : ""}</div>
                  {f.playoffs && (
                    <div className={`mt-0.5 font-semibold ${
                      f.playoffs === "SB champs" ? "text-accent" : "text-muted"}`}>
                      {f.playoffs}
                    </div>
                  )}
                </button>
              ))}
            </div>
          </Panel>

          {ov.injuries.length > 0 && (
            <Panel title="Injury report (latest week)">
              <ul className="grid gap-1 text-sm sm:grid-cols-2">
                {ov.injuries.map((r, i) => (
                  <li key={i} className="flex gap-2">
                    <span className="font-medium">{r.player}</span>
                    <span className="text-muted">{r.position}</span>
                    <span className={`ml-auto ${
                      r.status === "Out" ? "text-negative"
                        : r.status === "Questionable" ? "text-warning" : "text-muted"}`}>
                      {r.status}{r.injury ? ` (${r.injury})` : ""}
                    </span>
                  </li>
                ))}
              </ul>
            </Panel>
          )}

          <div className="grid gap-6 lg:grid-cols-2">
            <Panel title="Latest news">
              {newsErr && <p className="text-micro text-muted">Couldn't load news: {newsErr}</p>}
              <ul className="space-y-2 text-sm">
                {news.slice(0, 8).map((n, i) => (
                  <li key={i}>
                    <a href={n.url} target="_blank" rel="noreferrer" className="hover:text-accent">{n.headline}</a>
                    <span className="ml-2 text-xs text-muted">{n.ts?.slice(0, 10)}</span>
                  </li>
                ))}
              </ul>
            </Panel>

            <Panel title="Coach lineage">
              {detailErr && <p className="text-micro text-muted">Couldn't load coach history: {detailErr}</p>}
              <ol className="max-h-72 space-y-2 overflow-y-auto pr-1 text-sm">
                {coachHist.map((hrow) => (
                  <li key={hrow.season} className="flex items-center gap-3">
                    <span className="tabular-nums text-muted">{hrow.season}</span>
                    <span className="h-1.5 w-1.5 rounded-full bg-accent" />
                    <Link to={`/coach/${encodeURIComponent(hrow.coach)}`}
                          className="font-medium hover:underline">{hrow.coach}</Link>
                    <span className="ml-auto tabular-nums text-muted">
                      {hrow.wins}–{hrow.games - hrow.wins}
                    </span>
                  </li>
                ))}
              </ol>
            </Panel>
          </div>
        </>
      )}

      {/* ───────────────────────────── RESULTS ────────────────────────────── */}
      {tab === "results" && resErr && (
        <p className="text-body text-muted">Couldn't load results: {resErr}</p>
      )}
      {tab === "results" && res && (
        <>
          <Toolbar>
            <Field label="Season">
              <Select
                size="sm" ariaLabel="Results season" value={res.season}
                onChange={(v) => setResSeason(+v)}
                options={res.seasons.map((sn) => ({ value: sn, label: String(sn) }))} />
            </Field>
            <Chip tone="accent">{res.summary.w}–{res.summary.l}{res.summary.t ? `–${res.summary.t}` : ""}</Chip>
            <Tip text={HELP.ats_sum}><Chip>ATS {res.summary.ats_w}–{res.summary.ats_l}</Chip></Tip>
            <Tip text={HELP.ou_sum}><Chip>O/U {res.summary.overs}–{res.summary.unders}</Chip></Tip>
            <Chip>home {res.summary.home_w}–{res.summary.home_l}</Chip>
            <Chip>road {res.summary.away_w}–{res.summary.away_l}</Chip>
          </Toolbar>
          <Panel flush>
            <DataTable
              columns={resultCols}
              rows={res.rows}
              rowKey={(g) => g.game_id}
              rowHref={(g) => `/matchup/${g.game_id}`}
              caption={`${c} game results, ${res.season}`}
              footNote="Click any game for the full matchup card — travel, refs, weather, market and series history."
              empty="No games on record for this season." />
          </Panel>
        </>
      )}

      {/* ───────────────────────────── ROSTER ─────────────────────────────── */}
      {tab === "roster" && (
        <Panel title={`${rosterSeason} roster (${roster.length})`} flush>
          <div className="mb-3 flex flex-wrap items-center gap-3 px-4">
            <Field label="Season">
              <Select
                size="sm" ariaLabel="Roster season" value={rosterSeason}
                onChange={(v) => { setRosterSeason(+v); setPosFilter(""); }}
                options={(rosterSeasons.length ? rosterSeasons : [2026])
                  .map((sn) => ({ value: sn, label: String(sn) }))} />
            </Field>
            <PillGroup
              ariaLabel="Position filter" size="sm" clearable
              options={positions.map((x) => ({ value: x, label: x }))}
              value={posFilter}
              onChange={setPosFilter} />
          </div>
          {rosterErr && <p className="px-4 pb-4 text-body text-muted">Couldn't load the roster: {rosterErr}</p>}
          <DataTable
            columns={rosterCols}
            rows={roster.filter((p) => !posFilter || p.pos === posFilter)}
            rowKey={(p) => p.gsis ?? p.name}
            maxHeight="32rem"
            caption={`${c} roster, ${rosterSeason}`}
            empty={rosterErr ? " " : "No roster for this season."} />
        </Panel>
      )}

      {/* ───────────────────────────── STATS ──────────────────────────────── */}
      {tab === "stats" && (
        <>
          <Panel title="Weekly efficiency (EPA per play)">
            <div className="mb-2 flex items-center justify-between">
              <span className="text-xs text-muted">
                Offense: higher is better · Defense: lower is better (what they allowed)
              </span>
              <Select
                size="sm" ariaLabel="EPA season" value={epaSeason ?? epaData?.season ?? ""}
                onChange={(v) => setEpaSeason(+v)}
                options={[...ov.franchise].reverse()
                  .map((f) => ({ value: f.season, label: String(f.season) }))} />
            </div>
            {epaErr && <p className="text-micro text-muted">Couldn't load EPA: {epaErr}</p>}
            <LineChart data={epaWeeks} xKey="week" xLabel="Week"
              series={[{ key: "off", name: "Offense" },
                       { key: "def", name: "Defense" }]} digits={3} />
          </Panel>
          <Panel title="Franchise results by season" flush>
            <DataTable
              columns={franchiseCols}
              rows={[...ov.franchise].reverse()}
              rowKey={(f) => String(f.season)}
              onRowClick={(f) => { setResSeason(f.season); setTab("results"); }}
              caption={`${c} franchise results by season`}
              empty="No franchise history loaded." />
          </Panel>
        </>
      )}
    </div>
  );
}
