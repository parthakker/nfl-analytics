import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { api, type NewsItem, type RosterPlayer, type TeamScheduleGame } from "../lib/api";
import { hexToRgba } from "../lib/color";
import { useMeta } from "../lib/MetaContext";
import Chip from "../components/Chip";
import GlassPanel from "../components/GlassPanel";
import GlowLineChart from "../components/GlowLineChart";
import StatRing from "../components/StatRing";
import Tip from "../components/Tip";

/* ── types (page-local; single-page endpoints) ─────────────────────────── */
interface StaffBlock { name: string; since: number; playcaller: boolean; about: string }
interface Scheme { family: string; fact: string; knowledge: string }
interface Overview {
  code: string; season: number; division: string | null; div_rank: number | null;
  header: { w: number; l: number; t: number; pf_pg: number | null; pa_pg: number | null;
            pf_rank: number | null; pa_rank: number | null };
  staff: { head_coach: string | null; hc: { since: number; about: string } | null;
           oc: StaffBlock | null; dc: StaffBlock | null;
           offense_scheme: Scheme | null; defense_scheme: Scheme | null; note: string | null };
  leaders: { key: string; label: string; player_id?: string; name?: string;
             headshot?: string | null; value?: number }[];
  standings: { team: string; w: number; l: number; t: number; pct: number; pf: number; pa: number }[];
  epa: { off_epa: number; off_rank: number; def_epa: number; def_rank: number;
         pass_epa: number; pass_rank: number; rush_epa: number; rush_rank: number } | null;
  travel: { total_travel_miles?: number; avg_road_trip_miles?: number; max_trip_miles?: number;
            international_games?: number; total_tz_hours?: number; short_weeks?: number; byes?: number };
  franchise: { season: number; w: number; l: number; t: number; playoffs: string | null }[];
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
  rec: "Cumulative regular-season record after this game (ESPN convention)",
  strk: "Running win/loss streak through this game",
  spread: "Closing spread from this team's perspective (negative = favored)",
  ats: "Against the spread: ✓ covered, ✗ didn't, — push or no line",
  ou: "Total (over/under) result for this game",
  rest: "Days since this team's previous game (schedules-based, populated week 1)",
  travel: "Miles from this team's home stadium to the game venue (haversine)",
  pf: "Points scored per game (league rank)",
  pa: "Points allowed per game (rank 1 = fewest allowed)",
  ats_sum: "Season record against the closing spread (pushes excluded)",
  ou_sum: "How often this team's games went over the total",
  miles: "Season travel: sum of home-base-to-venue miles across all games",
  tz: "Total timezone hours crossed this season",
} as const;

const TABS = [["overview", "Overview"], ["results", "Results"],
              ["roster", "Roster"], ["stats", "Stats"]] as const;

export default function TeamHUD() {
  const { code = "" } = useParams();
  const [params, setParams] = useSearchParams();
  const nav = useNavigate();
  const meta = useMeta();
  const c = code.toUpperCase();
  const t = meta?.teams[c];
  const tab = params.get("tab") ?? "overview";
  const setTab = (v: string, extra?: Record<string, string>) =>
    setParams({ tab: v, ...extra }, { replace: false });

  const [ov, setOv] = useState<Overview | null>(null);
  const [res, setRes] = useState<Results | null>(null);
  const [resSeason, setResSeason] = useState<number | undefined>();
  const [roster, setRoster] = useState<RosterPlayer[]>([]);
  const [rosterSeasons, setRosterSeasons] = useState<number[]>([]);
  const [rosterSeason, setRosterSeason] = useState<number>(2026);
  const [posFilter, setPosFilter] = useState("");
  const [sched, setSched] = useState<TeamScheduleGame[]>([]);
  const [news, setNews] = useState<NewsItem[]>([]);
  const [epaSeason, setEpaSeason] = useState(2025);
  const [epaWeeks, setEpaWeeks] = useState<{ week: number; off: number | null; def: number | null }[]>([]);
  const [coachHist, setCoachHist] = useState<{ season: number; coach: string; games: number; wins: number }[]>([]);

  useEffect(() => {
    if (!c) return;
    fetch(`/api/teams/${c}/overview`).then((r) => r.json()).then(setOv).catch(console.error);
    api.team(c, 2025).then((d) => setCoachHist(d.coach.history as typeof coachHist)).catch(console.error);
    api.teamSchedule(c).then((r) => setSched(r.games)).catch(console.error);
    api.teamNews(c).then((r) => setNews(r.items)).catch(console.error);
  }, [c]);

  useEffect(() => {
    if (!c || tab !== "results") return;
    const q = resSeason ? `?season=${resSeason}` : "";
    fetch(`/api/teams/${c}/results${q}`).then((r) => r.json())
      .then((r) => { setRes(r); if (!resSeason) setResSeason(r.season); })
      .catch(console.error);
  }, [c, tab, resSeason]);

  useEffect(() => {
    if (!c || tab !== "roster") return;
    fetch(`/api/teams/${c}/roster?season=${rosterSeason}`).then((r) => r.json())
      .then((r) => { setRoster(r.players); setRosterSeasons(r.seasons ?? []); })
      .catch(console.error);
  }, [c, tab, rosterSeason]);

  useEffect(() => {
    if (!c || tab !== "stats") return;
    api.teamEpa(c, epaSeason).then((r) => setEpaWeeks(r.weeks)).catch(console.error);
  }, [c, tab, epaSeason]);

  const positions = useMemo(
    () => [...new Set(roster.map((p) => p.pos).filter(Boolean))].sort() as string[],
    [roster]);

  if (!t || !ov) return null;
  const h = ov.header;
  const games = h.w + h.l + h.t;
  const s = ov.staff;

  return (
    <div className="space-y-6"
         style={{ ["--accent" as string]: t.glow,
                  ["--accent-glow" as string]: hexToRgba(t.glow, 0.5) }}>
      {/* banner */}
      <div className="glass relative overflow-hidden p-8"
           style={{ background: `linear-gradient(120deg, ${hexToRgba(t.color, 0.55)}, var(--glass) 65%)` }}>
        <img src={t.logo} alt="" aria-hidden
             className="pointer-events-none absolute -right-10 -top-14 h-64 w-64 opacity-15" />
        <div className="relative flex flex-wrap items-center gap-6">
          <img src={t.logo} alt={t.name} className="logo-glow h-20 w-20" />
          <div>
            <h1 className="text-3xl font-bold tracking-tight">{t.name}</h1>
            <p className="text-sm" style={{ color: "var(--muted)" }}>
              {ov.div_rank ? `${ov.div_rank}${["st", "nd", "rd"][ov.div_rank - 1] ?? "th"} ${ov.division}` : `${t.conf} ${t.div}`}
              {" · head coach "}
              {s.head_coach ? (
                <Link to={`/coach/${encodeURIComponent(s.head_coach)}`}
                      className="font-semibold hover:underline" style={{ color: "var(--accent)" }}>
                  {s.head_coach}
                </Link>
              ) : "—"}
              {" · "}{ov.season}
            </p>
          </div>
          <div className="ml-auto flex gap-6">
            <StatRing label={`${ov.season} record`} value={`${h.w}–${h.l}${h.t ? `–${h.t}` : ""}`}
                      fraction={games ? h.w / games : 0} />
            <Tip text={HELP.pf}>
              <StatRing label="points / game" value={h.pf_pg?.toFixed(1) ?? "—"}
                        sub={h.pf_rank ? `#${h.pf_rank}` : ""} fraction={(h.pf_pg ?? 0) / 35} />
            </Tip>
            <Tip text={HELP.pa}>
              <StatRing label="allowed / game" value={h.pa_pg?.toFixed(1) ?? "—"}
                        sub={h.pa_rank ? `#${h.pa_rank}` : ""} fraction={1 - (h.pa_pg ?? 35) / 35} />
            </Tip>
          </div>
        </div>
      </div>

      {s.note && <p className="text-sm italic" style={{ color: "var(--muted)" }}>⚑ {s.note}</p>}

      {/* tabs */}
      <div className="flex flex-wrap gap-2">
        {TABS.map(([key, label]) => (
          <button key={key} onClick={() => setTab(key)}
            className="rounded-full border px-3 py-1 text-sm font-semibold"
            style={{ borderColor: tab === key ? "var(--accent)" : "var(--stroke)",
                     color: tab === key ? "var(--accent)" : "var(--muted)" }}>
            {label}
          </button>
        ))}
      </div>

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
                  <div className="glass w-full p-3 text-center">
                    <div className="text-xs uppercase tracking-wider" style={{ color: "var(--muted)" }}>{lbl}</div>
                    <div className="mt-1 text-xl font-bold tabular-nums" style={{ color: "var(--accent)" }}>
                      {(v as number) > 0 ? "+" : ""}{v as number}
                      <span className="ml-1.5 text-sm font-semibold" style={{ color: "var(--muted)" }}>#{rank as number}</span>
                    </div>
                  </div>
                </Tip>
              ))}
            </div>
          )}

          <div className="grid gap-4 lg:grid-cols-3">
            <GlassPanel title="Head coach">
              {s.head_coach && (
                <>
                  <Link to={`/coach/${encodeURIComponent(s.head_coach)}`}
                        className="text-lg font-semibold hover:underline" style={{ color: "var(--accent)" }}>
                    {s.head_coach}
                  </Link>
                  <p className="text-xs" style={{ color: "var(--muted)" }}>since {s.hc?.since}</p>
                  <p className="mt-2 text-sm" style={{ color: "var(--muted)" }}>{s.hc?.about}</p>
                </>
              )}
            </GlassPanel>
            {(["oc", "dc"] as const).map((role) => {
              const b = s[role];
              const scheme = role === "oc" ? s.offense_scheme : s.defense_scheme;
              return (
                <GlassPanel key={role} title={role === "oc" ? "Offensive coordinator" : "Defensive coordinator"}>
                  {b ? (
                    <>
                      <span className="flex items-center gap-2">
                        <Link to={`/coach/${encodeURIComponent(b.name)}?role=${role.toUpperCase()}`}
                              className="text-lg font-semibold hover:underline" style={{ color: "var(--accent)" }}>
                          {b.name}
                        </Link>
                        {b.playcaller && <Chip tone="arc">calls plays</Chip>}
                      </span>
                      <p className="text-xs" style={{ color: "var(--muted)" }}>since {b.since}</p>
                    </>
                  ) : (
                    <p className="text-sm" style={{ color: "var(--muted)" }}>
                      No {role.toUpperCase()} title — the head coach runs this unit.
                    </p>
                  )}
                  {scheme && (
                    <Link to={`/knowledge/${scheme.knowledge}`}
                          className="mt-2 block text-sm hover:underline" style={{ color: "var(--arc)" }}>
                      {scheme.family} →
                    </Link>
                  )}
                </GlassPanel>
              );
            })}
          </div>

          <div>
            <h2 className="mb-3 text-sm font-bold uppercase tracking-widest" style={{ color: "var(--arc)" }}>
              {ov.season} team leaders
            </h2>
            <div className="grid gap-3 sm:grid-cols-5">
              {ov.leaders.map((ld) => (
                <Link key={ld.key} to={ld.player_id ? `/player/${ld.player_id}` : "#"}
                      className="glass flex items-center gap-3 p-3 transition-transform hover:-translate-y-0.5">
                  {ld.headshot && (
                    <img src={ld.headshot} alt="" className="h-10 w-10 rounded-full object-cover"
                         onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }} />
                  )}
                  <div className="min-w-0">
                    <div className="truncate text-sm font-semibold">{ld.name ?? "—"}</div>
                    <div className="text-xs" style={{ color: "var(--muted)" }}>
                      <span className="tabular-nums font-semibold" style={{ color: "var(--accent)" }}>
                        {ld.value?.toLocaleString() ?? "—"}
                      </span>{" "}{ld.label}
                    </div>
                  </div>
                </Link>
              ))}
            </div>
          </div>

          <div className="grid gap-6 lg:grid-cols-2">
            <GlassPanel title={`${ov.division ?? "Division"} standings`}>
              <table className="w-full text-left text-sm">
                <thead><tr style={{ color: "var(--muted)" }}>
                  {["Team", "W", "L", "T", "PCT", "PF", "PA"].map((hd) => (
                    <th key={hd} className="py-1 pr-3 font-medium">{hd}</th>))}
                </tr></thead>
                <tbody>
                  {ov.standings.map((row) => (
                    <tr key={row.team}
                        className={`border-t tabular-nums ${row.team === c ? "font-bold" : ""}`}
                        style={{ borderColor: "var(--stroke)",
                                 background: row.team === c ? "rgba(255,255,255,0.04)" : undefined }}>
                      <td className="py-1.5 pr-3">
                        <Link to={`/team/${row.team}`} className="flex items-center gap-2 hover:underline">
                          {meta?.teams[row.team] && (
                            <img src={meta.teams[row.team].logo} alt="" className="h-5 w-5" />)}
                          {row.team}
                        </Link>
                      </td>
                      <td className="py-1.5 pr-3">{row.w}</td>
                      <td className="py-1.5 pr-3">{row.l}</td>
                      <td className="py-1.5 pr-3">{row.t}</td>
                      <td className="py-1.5 pr-3">{row.pct?.toFixed(3)}</td>
                      <td className="py-1.5 pr-3">{row.pf}</td>
                      <td className="py-1.5">{row.pa}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </GlassPanel>

            <GlassPanel title="Travel & rest profile">
              <div className="flex flex-wrap gap-2">
                <Tip text={HELP.miles}><Chip tone="arc">{(ov.travel.total_travel_miles ?? 0).toLocaleString()} mi this season</Chip></Tip>
                <Tip text="Average one-way miles for road games"><Chip>{ov.travel.avg_road_trip_miles?.toLocaleString() ?? "—"} mi avg road trip</Chip></Tip>
                <Tip text="Longest single trip"><Chip>{ov.travel.max_trip_miles?.toLocaleString() ?? "—"} mi longest</Chip></Tip>
                <Tip text={HELP.tz}><Chip>{ov.travel.total_tz_hours ?? 0} tz hours</Chip></Tip>
                <Tip text="Games abroad"><Chip tone={ov.travel.international_games ? "hot" : "muted"}>{ov.travel.international_games ?? 0} international</Chip></Tip>
                <Tip text="Games on 5 or fewer days rest"><Chip>{ov.travel.short_weeks ?? 0} short weeks</Chip></Tip>
              </div>
              <p className="mt-3 text-xs" style={{ color: "var(--muted)" }}>
                Computed from the curated venue database — home-base haversine miles per game.
              </p>
            </GlassPanel>
          </div>

          <GlassPanel title="2026 schedule">
            <div className="flex gap-2 overflow-x-auto pb-1">
              {sched.map((g) => (
                <Link key={g.week} to={`/matchup/${g.game_id}`}
                      className="min-w-32 rounded-xl border p-2.5 text-center text-xs transition-colors hover:bg-white/5"
                      style={{ borderColor: "var(--stroke)" }}>
                  <div className="font-bold" style={{ color: "var(--muted)" }}>WK {g.week}</div>
                  <div className="mt-1 font-semibold">{g.home ? "vs" : "@"} {g.opponent}</div>
                  <div className="mt-0.5" style={{ color: "var(--muted)" }}>{g.date}</div>
                  {g.line_text && <div className="mt-1" style={{ color: "var(--accent)" }}>{g.line_text}</div>}
                </Link>
              ))}
            </div>
          </GlassPanel>

          <GlassPanel title="Franchise, season by season (2007+)">
            <div className="flex gap-1.5 overflow-x-auto pb-1">
              {ov.franchise.map((f) => (
                <button key={f.season}
                        onClick={() => { setResSeason(f.season); setTab("results"); }}
                        className="min-w-16 rounded-lg border p-1.5 text-center text-[11px] transition-colors hover:bg-white/5"
                        style={{ borderColor: f.playoffs === "SB champs" ? "var(--accent)" : "var(--stroke)" }}>
                  <div style={{ color: "var(--muted)" }}>{f.season}</div>
                  <div className="font-bold tabular-nums">{f.w}–{f.l}{f.t ? `–${f.t}` : ""}</div>
                  {f.playoffs && (
                    <div className="mt-0.5 font-semibold"
                         style={{ color: f.playoffs === "SB champs" ? "var(--accent)" : "var(--muted)" }}>
                      {f.playoffs}
                    </div>
                  )}
                </button>
              ))}
            </div>
          </GlassPanel>

          {ov.injuries.length > 0 && (
            <GlassPanel title="Injury report (latest week)">
              <ul className="grid gap-1 text-sm sm:grid-cols-2">
                {ov.injuries.map((r, i) => (
                  <li key={i} className="flex gap-2">
                    <span className="font-medium">{r.player}</span>
                    <span style={{ color: "var(--muted)" }}>{r.position}</span>
                    <span className="ml-auto" style={{
                      color: r.status === "Out" ? "#f87171" : r.status === "Questionable" ? "#facc15" : "var(--muted)" }}>
                      {r.status}{r.injury ? ` (${r.injury})` : ""}
                    </span>
                  </li>
                ))}
              </ul>
            </GlassPanel>
          )}

          <div className="grid gap-6 lg:grid-cols-2">
            <GlassPanel title="Latest news">
              <ul className="space-y-2 text-sm">
                {news.slice(0, 8).map((n, i) => (
                  <li key={i}>
                    <a href={n.url} target="_blank" rel="noreferrer" className="hover:text-white">{n.headline}</a>
                    <span className="ml-2 text-xs" style={{ color: "var(--muted)" }}>{n.ts?.slice(0, 10)}</span>
                  </li>
                ))}
              </ul>
            </GlassPanel>

            <GlassPanel title="Coach lineage">
              <ol className="max-h-72 space-y-2 overflow-y-auto pr-1 text-sm">
                {coachHist.map((hrow) => (
                  <li key={hrow.season} className="flex items-center gap-3">
                    <span className="tabular-nums" style={{ color: "var(--muted)" }}>{hrow.season}</span>
                    <span className="h-1.5 w-1.5 rounded-full" style={{ background: "var(--accent)" }} />
                    <Link to={`/coach/${encodeURIComponent(hrow.coach)}`}
                          className="font-medium hover:underline">{hrow.coach}</Link>
                    <span className="ml-auto tabular-nums" style={{ color: "var(--muted)" }}>
                      {hrow.wins}–{hrow.games - hrow.wins}
                    </span>
                  </li>
                ))}
              </ol>
            </GlassPanel>
          </div>
        </>
      )}

      {/* ───────────────────────────── RESULTS ────────────────────────────── */}
      {tab === "results" && res && (
        <>
          <div className="flex flex-wrap items-center gap-2">
            <select value={res.season} onChange={(e) => setResSeason(+e.target.value)}
                    className="rounded-lg border bg-transparent px-2 py-1.5 text-sm"
                    style={{ borderColor: "var(--stroke)" }}>
              {res.seasons.map((sn) => <option key={sn} value={sn} style={{ color: "#000" }}>{sn}</option>)}
            </select>
            <Chip tone="arc">{res.summary.w}–{res.summary.l}{res.summary.t ? `–${res.summary.t}` : ""}</Chip>
            <Tip text={HELP.ats_sum}><Chip>ATS {res.summary.ats_w}–{res.summary.ats_l}</Chip></Tip>
            <Tip text={HELP.ou_sum}><Chip>O/U {res.summary.overs}–{res.summary.unders}</Chip></Tip>
            <Chip>home {res.summary.home_w}–{res.summary.home_l}</Chip>
            <Chip>road {res.summary.away_w}–{res.summary.away_l}</Chip>
          </div>
          <GlassPanel>
            <div className="scroll-x">
              <table className="w-max min-w-full whitespace-nowrap text-left text-sm">
                <thead>
                  <tr style={{ color: "var(--muted)" }}>
                    <th className="py-1.5 pr-3 font-medium">Wk</th>
                    <th className="py-1.5 pr-3 font-medium">Date</th>
                    <th className="py-1.5 pr-3 font-medium">Opponent</th>
                    <th className="py-1.5 pr-3 font-medium">Result</th>
                    <th className="py-1.5 pr-3 font-medium"><Tip text={HELP.rec}><span>Rec</span></Tip></th>
                    <th className="py-1.5 pr-3 font-medium"><Tip text={HELP.strk}><span>Strk</span></Tip></th>
                    <th className="py-1.5 pr-3 font-medium"><Tip text={HELP.spread}><span>Spread</span></Tip></th>
                    <th className="py-1.5 pr-3 font-medium"><Tip text={HELP.ats}><span>ATS</span></Tip></th>
                    <th className="py-1.5 pr-3 font-medium"><Tip text={HELP.ou}><span>O/U</span></Tip></th>
                    <th className="py-1.5 pr-3 font-medium"><Tip text={HELP.rest}><span>Rest</span></Tip></th>
                    <th className="py-1.5 pr-3 font-medium"><Tip text={HELP.travel}><span>Travel</span></Tip></th>
                    <th className="py-1.5 pr-3 font-medium">QBs</th>
                    <th className="py-1.5 font-medium">Ref</th>
                  </tr>
                </thead>
                <tbody>
                  {res.rows.map((g) => (
                    <tr key={g.game_id} onClick={() => nav(`/matchup/${g.game_id}`)}
                        className="cursor-pointer border-t transition-colors hover:bg-white/5"
                        style={{ borderColor: "var(--stroke)" }}>
                      <td className="py-1.5 pr-3 text-xs tabular-nums" style={{ color: "var(--muted)" }}>
                        {g.season_type === "POST"
                          ? <span className="font-bold" style={{ color: "var(--arc)" }}>{g.game_type}</span>
                          : g.week}
                      </td>
                      <td className="py-1.5 pr-3 text-xs" style={{ color: "var(--muted)" }}>{g.date}</td>
                      <td className="py-1.5 pr-3">
                        <span className="flex items-center gap-1.5">
                          <span className="text-xs" style={{ color: "var(--muted)" }}>
                            {g.site === "home" ? "vs" : g.site === "away" ? "@" : "n"}
                          </span>
                          {meta?.teams[g.opponent] && (
                            <img src={meta.teams[g.opponent].logo} alt="" className="h-5 w-5" />)}
                          <span className="font-medium">{g.opponent}</span>
                        </span>
                      </td>
                      <td className="py-1.5 pr-3 tabular-nums">
                        <span className="font-bold"
                              style={{ color: g.win === 1 ? "#4ade80" : g.win === 0 ? "#f87171" : "var(--muted)" }}>
                          {g.win === 1 ? "W" : g.win === 0 ? "L" : "T"}
                        </span>{" "}
                        {g.team_score}–{g.opp_score}{g.overtime ? " OT" : ""}
                      </td>
                      <td className="py-1.5 pr-3 text-xs tabular-nums" style={{ color: "var(--muted)" }}>
                        {g.season_type === "REG" ? `${g.w_td}–${g.l_td}${g.t_td ? `–${g.t_td}` : ""}` : "—"}
                      </td>
                      <td className="py-1.5 pr-3 text-xs tabular-nums" style={{ color: "var(--muted)" }}>{g.streak ?? "—"}</td>
                      <td className="py-1.5 pr-3 text-xs tabular-nums" style={{ color: "var(--muted)" }}>
                        {g.spread_line_team != null
                          ? (g.spread_line_team > 0 ? `-${g.spread_line_team}` : `+${-g.spread_line_team}`)
                          : "—"}
                      </td>
                      <td className="py-1.5 pr-3 text-xs">
                        {g.covered == null ? "—" : g.covered
                          ? <span style={{ color: "#4ade80" }}>✓</span>
                          : <span style={{ color: "#f87171" }}>✗</span>}
                      </td>
                      <td className="py-1.5 pr-3 text-xs" style={{ color: "var(--muted)" }}>
                        {g.went_over == null ? "—" : g.went_over ? `O ${g.total_line}` : `U ${g.total_line}`}
                      </td>
                      <td className="py-1.5 pr-3 text-xs tabular-nums" style={{ color: "var(--muted)" }}>
                        {g.rest_days_sched ?? "—"}
                      </td>
                      <td className="py-1.5 pr-3 text-xs tabular-nums" style={{ color: "var(--muted)" }}>
                        {g.travel_miles != null && g.travel_miles > 25 ? `${g.travel_miles.toLocaleString()} mi` : "—"}
                      </td>
                      <td className="max-w-52 truncate py-1.5 pr-3 text-xs" style={{ color: "var(--muted)" }}>
                        {g.team_qb ?? "—"} v {g.opp_qb ?? "—"}
                      </td>
                      <td className="max-w-32 truncate py-1.5 text-xs" style={{ color: "var(--muted)" }}>
                        {g.referee ?? "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="mt-2 text-xs" style={{ color: "var(--muted)" }}>
              Click any game for the full matchup card — travel, refs, weather, market and series history.
            </p>
          </GlassPanel>
        </>
      )}

      {/* ───────────────────────────── ROSTER ─────────────────────────────── */}
      {tab === "roster" && (
        <GlassPanel title={`${rosterSeason} roster (${roster.length})`}>
          <div className="mb-2 flex flex-wrap items-center gap-1.5">
            <select value={rosterSeason} onChange={(e) => { setRosterSeason(+e.target.value); setPosFilter(""); }}
                    className="mr-2 rounded-lg border bg-transparent px-2 py-1 text-sm"
                    style={{ borderColor: "var(--stroke)" }}>
              {(rosterSeasons.length ? rosterSeasons : [2026]).map((sn) => (
                <option key={sn} value={sn} style={{ color: "#000" }}>{sn}</option>))}
            </select>
            {positions.map((p) => (
              <button key={p} onClick={() => setPosFilter(posFilter === p ? "" : p)}
                className="rounded-full border px-2.5 py-0.5 text-xs font-semibold transition-colors"
                style={{ borderColor: posFilter === p ? "var(--accent)" : "var(--stroke)",
                         color: posFilter === p ? "var(--accent)" : "var(--muted)" }}>
                {p}
              </button>
            ))}
          </div>
          <div className="max-h-[32rem] overflow-y-auto">
            <table className="w-full text-left text-sm">
              <thead className="sticky top-0" style={{ background: "var(--bg-1)" }}>
                <tr style={{ color: "var(--muted)" }}>
                  <th className="py-1 pr-2 font-medium">#</th>
                  <th className="py-1 pr-2 font-medium">Player</th>
                  <th className="py-1 pr-2 font-medium">Pos</th>
                  <th className="py-1 font-medium">College</th>
                </tr>
              </thead>
              <tbody>
                {roster.filter((p) => !posFilter || p.pos === posFilter).map((p) => (
                  <tr key={p.gsis ?? p.name} className="border-t transition-colors hover:bg-white/5"
                      style={{ borderColor: "var(--stroke)" }}>
                    <td className="py-1.5 pr-2 tabular-nums" style={{ color: "var(--muted)" }}>{p.num ?? ""}</td>
                    <td className="py-1.5 pr-2 font-medium">
                      <span className="flex items-center gap-2">
                        {p.headshot && (
                          <img src={p.headshot} alt="" className="h-6 w-6 rounded-full object-cover"
                               onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }} />)}
                        {p.gsis ? (
                          <Link to={`/player/${p.gsis}`} className="hover:underline">{p.name}</Link>
                        ) : p.name}
                      </span>
                    </td>
                    <td className="py-1.5 pr-2">{p.pos}</td>
                    <td className="py-1.5 text-xs" style={{ color: "var(--muted)" }}>{p.college}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </GlassPanel>
      )}

      {/* ───────────────────────────── STATS ──────────────────────────────── */}
      {tab === "stats" && (
        <>
          <GlassPanel title="Weekly efficiency (EPA per play)">
            <div className="mb-2 flex items-center justify-between">
              <span className="text-xs" style={{ color: "var(--muted)" }}>
                Offense: higher is better · Defense: lower is better (what they allowed)
              </span>
              <select value={epaSeason} onChange={(e) => setEpaSeason(+e.target.value)}
                      className="rounded-lg border bg-transparent px-2 py-1 text-sm"
                      style={{ borderColor: "var(--stroke)", color: "var(--text)" }}>
                {Array.from({ length: 2025 - 2007 + 1 }, (_, i) => 2025 - i).map((sn) => (
                  <option key={sn} value={sn} style={{ color: "#000" }}>{sn}</option>))}
              </select>
            </div>
            <GlowLineChart data={epaWeeks} xKey="week"
              series={[{ key: "off", name: "Offense", color: "var(--accent)" },
                       { key: "def", name: "Defense", color: "#7d93a8" }]} />
          </GlassPanel>
          <GlassPanel title="Franchise results by season">
            <table className="w-full text-left text-sm">
              <thead><tr style={{ color: "var(--muted)" }}>
                {["Season", "Record", "Playoffs"].map((hd) => (
                  <th key={hd} className="py-1 pr-3 font-medium">{hd}</th>))}
              </tr></thead>
              <tbody>
                {[...ov.franchise].reverse().map((f) => (
                  <tr key={f.season} className="cursor-pointer border-t tabular-nums transition-colors hover:bg-white/5"
                      onClick={() => { setResSeason(f.season); setTab("results"); }}
                      style={{ borderColor: "var(--stroke)" }}>
                    <td className="py-1.5 pr-3">{f.season}</td>
                    <td className="py-1.5 pr-3">{f.w}–{f.l}{f.t ? `–${f.t}` : ""}</td>
                    <td className="py-1.5" style={{ color: f.playoffs === "SB champs" ? "var(--accent)" : "var(--muted)" }}>
                      {f.playoffs ?? "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </GlassPanel>
        </>
      )}
    </div>
  );
}
