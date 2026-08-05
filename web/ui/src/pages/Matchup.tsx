import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import Chip from "../components/Chip";
import GlassPanel from "../components/GlassPanel";
import { LineChart } from "../components/charts";
import { hexToRgba } from "../lib/color";
import { useMeta } from "../lib/MetaContext";
import { useTeamPairTokens } from "../lib/useTeamTokens";

interface Side {
  code: string; coach: string | null; qb: string | null;
  record: { w: number; l: number; t: number };
  rest_days: number | null; is_off_bye: boolean; short_week: boolean;
  travel_miles: number | null; tz_shift_hours: number | null;
  form_last5: { game_id: string; opponent: string; site: string; win: number;
                team_score: number; opp_score: number }[];
  epa: { off_epa: number; off_rank: number; def_epa: number; def_rank: number } | null;
}
interface Data {
  game: { game_id: string; season: number; week: number; season_type: string;
          game_type: string; date: string; gametime: string | null; final: boolean;
          away_team: string; home_team: string;
          away_score: number | null; home_score: number | null;
          overtime: number | null; div_game: boolean; surface: string | null };
  venue: { venue_name: string | null; venue_city: string | null;
           venue_country: string | null; roof: string | null;
           neutral_site: boolean; is_international: boolean };
  teams: { away: Side; home: Side };
  coach_h2h: { away_coach: string; home_coach: string; games: number; wins: number;
               avg_pf: number; avg_pa: number; first_season: number;
               last_season: number; ats_games: number; ats_wins: number;
               meetings: { game_id: string; season: number; week: number;
                           away_coach_pts: number; home_coach_pts: number; win: number }[] } | null;
  referee: { name: string | null; note?: string;
             career: { games: number; pen_per_game: number; over_rate: number;
                       home_cover_rate: number; home_win_rate: number } | null;
             team_splits: Record<string, { games: number; team_wins: number;
               team_win_pct: number; team_covers: number; ats_games: number;
               pen_on_team_pg: number; pen_diff_pg: number; over_rate: number }> } | null;
  weather: { is_indoor: boolean; weather_source: string | null; temp_f: number | null;
             wind_mph: number | null; humidity_pct: number | null; gust_mph: number | null;
             wind_dir: string | null; precip_prob_pct: number | null; sky: string | null;
             roof: string | null } | null;
  market: { spread_line: number | null; total_line: number | null;
            home_moneyline: number | null; away_moneyline: number | null;
            line_history: { ts: string; spread: number | null; total: number | null }[];
            kalshi: { prob_home: number | null; ticker: string; volume: number | null } | null };
  injuries: { away: InjuryRow[]; home: InjuryRow[] };
  series: { games: number; away_wins: number; home_wins: number; ties: number;
            avg_margin: number; avg_total: number; current_streak: number;
            first_meeting_season: number; ats_wins: number; ats_games: number;
            last5: { game_id: string; season: number; site: string; date: string;
                     venue_name: string | null; away_pts: number; home_pts: number;
                     away_win: number }[] } | null;
}
interface InjuryRow { player: string; position: string | null; status: string;
                      injury: string | null; practice_status: string | null }

const pct = (v: number | null | undefined, d = 1) =>
  v != null ? `${(v * 100).toFixed(d)}%` : "—";

function SideCol({ s, accent, meetsLeft }: { s: Side; accent: string; meetsLeft?: boolean }) {
  return (
    <div className={`flex-1 space-y-1.5 ${meetsLeft ? "text-right" : ""}`}>
      <div className="flex flex-wrap items-center gap-1.5"
           style={{ justifyContent: meetsLeft ? "flex-end" : "flex-start" }}>
        <Chip tone="arc">{s.travel_miles != null ? `${s.travel_miles.toLocaleString()} mi` : "— mi"}</Chip>
        {s.tz_shift_hours != null && s.tz_shift_hours !== 0 && (
          <Chip>{s.tz_shift_hours > 0 ? `${s.tz_shift_hours}h east` : `${-s.tz_shift_hours}h west`}</Chip>
        )}
        <Chip>{s.rest_days != null ? `${s.rest_days}d rest` : "rest —"}</Chip>
        {s.is_off_bye && <Chip tone="hot">off bye</Chip>}
        {s.short_week && <Chip tone="hot">short week</Chip>}
      </div>
      <p className="text-xs" style={{ color: "var(--muted)" }}>
        {s.coach ?? "—"}{s.qb ? ` · ${s.qb}` : ""}
      </p>
      {s.epa && (
        <p className="text-xs tabular-nums" style={{ color: accent }}>
          off EPA {s.epa.off_epa > 0 ? "+" : ""}{s.epa.off_epa} (#{s.epa.off_rank}) ·
          def {s.epa.def_epa > 0 ? "+" : ""}{s.epa.def_epa} (#{s.epa.def_rank})
        </p>
      )}
      <div className="flex gap-1 text-[11px]"
           style={{ justifyContent: meetsLeft ? "flex-end" : "flex-start" }}>
        {[...s.form_last5].reverse().map((f) => (
          <Link key={f.game_id} to={`/matchup/${f.game_id}`}
                title={`${f.site === "home" ? "vs" : "@"} ${f.opponent} ${f.team_score}–${f.opp_score}`}
                className="flex h-5 w-5 items-center justify-center rounded-full font-bold"
                style={{ background: f.win === 1 ? "rgba(12,163,12,.25)" : f.win === 0 ? "rgba(208,59,59,.25)" : "var(--glass)",
                         color: f.win === 1 ? "#4ade80" : f.win === 0 ? "#f87171" : "var(--muted)" }}>
            {f.win === 1 ? "W" : f.win === 0 ? "L" : "T"}
          </Link>
        ))}
      </div>
    </div>
  );
}

export default function Matchup() {
  const { gameId = "" } = useParams();
  const meta = useMeta();
  const [d, setD] = useState<Data | null>(null);
  const [err, setErr] = useState("");

  useEffect(() => {
    setD(null); setErr("");
    fetch(`/api/matchup/${encodeURIComponent(gameId)}`)
      .then((r) => (r.ok ? r.json() : Promise.reject(r.status)))
      .then(setD).catch((e) => setErr(String(e)));
  }, [gameId]);

  // hooks before early returns; the pair hook demotes the away side to
  // neutral when the two hues collide (DEN and CIN are both #FB4F14)
  const pair = useTeamPairTokens(d?.game.away_team ?? null, d?.game.home_team ?? null);

  if (err) return <p className="text-muted">No matchup found. {err}</p>;
  if (!d || !meta) return null;
  const ta = meta.teams[d.game.away_team];
  const th = meta.teams[d.game.home_team];
  const aGlow = pair.away.ink;
  const hGlow = pair.home.ink;
  const s = d.series;
  const w = d.weather;

  return (
    <div className="space-y-6">
      {/* split banner: away color -> glass -> home color */}
      <div className="relative overflow-hidden rounded-[var(--radius-panel)] border border-border p-7" style={{
        background: `linear-gradient(105deg, ${hexToRgba(ta?.color ?? "#123", 0.3)}, var(--color-surface) 40%, var(--color-surface) 60%, ${hexToRgba(th?.color ?? "#123", 0.3)})` }}>
        <div className="relative flex items-center gap-5">
          <Link to={`/team/${d.game.away_team}`} className="flex items-center gap-4">
            <img src={ta?.logo} alt={d.game.away_team} className="h-16 w-16"
                 />
            <div>
              <div className="text-xl font-bold tracking-tight">{ta?.name ?? d.game.away_team}</div>
              <div className="text-xs tabular-nums" style={{ color: "var(--muted)" }}>
                {d.teams.away.record.w}–{d.teams.away.record.l}
                {d.teams.away.record.t ? `–${d.teams.away.record.t}` : ""}
              </div>
            </div>
          </Link>
          <div className="mx-auto text-center">
            {d.game.final ? (
              <div className="text-3xl font-bold tabular-nums tracking-tight">
                {d.game.away_score}–{d.game.home_score}
                {d.game.overtime ? <span className="ml-1 text-sm" style={{ color: "var(--muted)" }}>OT</span> : null}
              </div>
            ) : (
              <div className="text-lg font-semibold" style={{ color: "var(--arc)" }}>
                {d.game.gametime ?? "TBD"} ET
              </div>
            )}
            <div className="text-xs" style={{ color: "var(--muted)" }}>
              {d.game.season} · {d.game.season_type === "POST" ? d.game.game_type : `Week ${d.game.week}`} · {d.game.date}
            </div>
            <div className="mt-0.5 text-xs" style={{ color: "var(--muted)" }}>
              {d.venue.venue_name ?? "—"}{d.venue.venue_city ? ` · ${d.venue.venue_city}` : ""}
              {d.venue.is_international && <span style={{ color: "var(--arc)" }}> · international</span>}
              {d.venue.neutral_site && !d.venue.is_international && " · neutral site"}
            </div>
          </div>
          <Link to={`/team/${d.game.home_team}`} className="flex items-center gap-4 text-right">
            <div>
              <div className="text-xl font-bold tracking-tight">{th?.name ?? d.game.home_team}</div>
              <div className="text-xs tabular-nums" style={{ color: "var(--muted)" }}>
                {d.teams.home.record.w}–{d.teams.home.record.l}
                {d.teams.home.record.t ? `–${d.teams.home.record.t}` : ""}
              </div>
            </div>
            <img src={th?.logo} alt={d.game.home_team} className="h-16 w-16"
                 />
          </Link>
        </div>
      </div>

      <GlassPanel title="Travel, rest & form">
        <div className="flex flex-wrap items-start gap-6">
          <SideCol s={d.teams.away} accent={aGlow} />
          <SideCol s={d.teams.home} accent={hGlow} meetsLeft />
        </div>
      </GlassPanel>

      <div className="grid gap-6 lg:grid-cols-3">
        <GlassPanel title={`All-time series (since ${s?.first_meeting_season ?? "—"})`}>
          {s ? (
            <div className="space-y-2 text-sm">
              <div className="flex items-baseline gap-3">
                <span className="text-2xl font-bold tabular-nums">{s.away_wins}–{s.home_wins}{s.ties ? `–${s.ties}` : ""}</span>
                <span style={{ color: "var(--muted)" }}>{d.game.away_team} leads?
                  {s.away_wins > s.home_wins ? ` yes` : s.away_wins < s.home_wins ? ` no` : " tied"}</span>
              </div>
              <p className="text-xs" style={{ color: "var(--muted)" }}>
                {s.games} meetings · avg margin {s.avg_margin > 0 ? "+" : ""}{s.avg_margin} ({d.game.away_team}) ·
                avg total {s.avg_total} · streak: {s.current_streak > 0
                  ? `${d.game.away_team} won ${s.current_streak}`
                  : s.current_streak < 0 ? `${d.game.home_team} won ${-s.current_streak}` : "—"}
              </p>
              <ul className="space-y-1 text-xs">
                {s.last5.map((m) => (
                  <li key={m.game_id}>
                    <Link to={`/matchup/${m.game_id}`} className="flex gap-2 hover:underline">
                      <span style={{ color: "var(--muted)" }}>{m.date}</span>
                      <span className="tabular-nums">{m.away_pts}–{m.home_pts}</span>
                      <span style={{ color: m.away_win === 1 ? aGlow : hGlow }}>
                        {m.away_win === 1 ? d.game.away_team : m.away_win === 0 ? d.game.home_team : "tie"}
                      </span>
                      <span className="ml-auto truncate" style={{ color: "var(--muted)" }}>{m.venue_name}</span>
                    </Link>
                  </li>
                ))}
              </ul>
              <Link to={`/h2h/${d.game.away_team}/${d.game.home_team}`}
                    className="inline-block text-xs font-semibold hover:underline"
                    style={{ color: "var(--arc)" }}>
                full series history →
              </Link>
            </div>
          ) : <p className="text-sm" style={{ color: "var(--muted)" }}>First ever meeting.</p>}
        </GlassPanel>

        <GlassPanel title="Coaching matchup">
          {d.coach_h2h ? (
            <div className="space-y-2 text-sm">
              <p>
                <Link to={`/coach/${encodeURIComponent(d.coach_h2h.away_coach)}`}
                      className="font-semibold hover:underline">{d.coach_h2h.away_coach}</Link>
                <span style={{ color: "var(--muted)" }}> vs </span>
                <Link to={`/coach/${encodeURIComponent(d.coach_h2h.home_coach)}`}
                      className="font-semibold hover:underline">{d.coach_h2h.home_coach}</Link>
              </p>
              <p className="text-2xl font-bold tabular-nums">
                {Math.round(d.coach_h2h.wins)}–{Math.round(d.coach_h2h.games - d.coach_h2h.wins)}
              </p>
              <p className="text-xs" style={{ color: "var(--muted)" }}>
                {d.coach_h2h.games} meetings since {d.coach_h2h.first_season} ·
                {" "}{d.coach_h2h.away_coach.split(" ").slice(-1)} ATS {d.coach_h2h.ats_wins}–{d.coach_h2h.ats_games - d.coach_h2h.ats_wins} ·
                avg score {d.coach_h2h.avg_pf}–{d.coach_h2h.avg_pa}
              </p>
              <div className="flex gap-1 text-[11px]">
                {[...d.coach_h2h.meetings].reverse().map((m) => (
                  <Link key={m.game_id} to={`/matchup/${m.game_id}`}
                        title={`${m.season} wk ${m.week}: ${m.away_coach_pts}–${m.home_coach_pts}`}
                        className="flex h-5 w-5 items-center justify-center rounded-full font-bold"
                        style={{ background: m.win === 1 ? "rgba(12,163,12,.25)" : "rgba(208,59,59,.25)",
                                 color: m.win === 1 ? "#4ade80" : "#f87171" }}>
                    {m.win === 1 ? "W" : "L"}
                  </Link>
                ))}
              </div>
            </div>
          ) : <p className="text-sm" style={{ color: "var(--muted)" }}>
                No prior meetings between these coaches.</p>}
        </GlassPanel>

        <GlassPanel title="Weather">
          {w && (w.is_indoor ? (
            <p className="text-sm" style={{ color: "var(--muted)" }}>
              Indoors ({w.roof}) — climate controlled, call it 68° and calm.
            </p>
          ) : w.temp_f != null ? (
            <div className="space-y-1 text-sm">
              <p className="text-2xl font-bold tabular-nums">{Math.round(w.temp_f)}°F
                {w.wind_mph != null && <span className="ml-2 text-base font-semibold">
                  {w.wind_dir ?? ""} {Math.round(w.wind_mph)} mph</span>}
              </p>
              <p className="text-xs" style={{ color: "var(--muted)" }}>
                {w.sky ? `${w.sky} · ` : ""}
                {w.humidity_pct != null ? `humidity ${Math.round(w.humidity_pct)}% · ` : ""}
                {w.gust_mph != null ? `gusts ${Math.round(w.gust_mph)} · ` : ""}
                {w.precip_prob_pct != null ? `precip ${Math.round(w.precip_prob_pct)}% · ` : ""}
                source: {w.weather_source}
              </p>
            </div>
          ) : (
            <p className="text-sm" style={{ color: "var(--muted)" }}>
              Outdoors — forecast lands within 16 days of kickoff.
            </p>
          ))}
        </GlassPanel>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <GlassPanel title="Referee">
          {d.referee?.name ? (
            <div className="space-y-2 text-sm">
              <p className="font-semibold">{d.referee.name}</p>
              {d.referee.career && (
                <p className="text-xs" style={{ color: "var(--muted)" }}>
                  {d.referee.career.games} games · {d.referee.career.pen_per_game} pen/gm ·
                  over rate {pct(d.referee.career.over_rate)} ·
                  home cover {pct(d.referee.career.home_cover_rate)}
                </p>
              )}
              <table className="w-full text-left text-xs">
                <thead><tr style={{ color: "var(--muted)" }}>
                  {["Team", "G", "W%", "ATS", "Pen/gm", "Pen diff", "Over%"].map((h) =>
                    <th key={h} className="py-1 pr-2 font-medium">{h}</th>)}
                </tr></thead>
                <tbody>
                  {[d.game.away_team, d.game.home_team].map((t) => {
                    const r = d.referee!.team_splits[t];
                    return (
                      <tr key={t} className="border-t tabular-nums" style={{ borderColor: "var(--stroke)" }}>
                        <td className="py-1 pr-2 font-semibold">{t}</td>
                        {r ? (<>
                          <td className="py-1 pr-2">{r.games}</td>
                          <td className="py-1 pr-2">{pct(r.team_win_pct, 0)}</td>
                          <td className="py-1 pr-2">{r.team_covers}–{r.ats_games - r.team_covers}</td>
                          <td className="py-1 pr-2">{r.pen_on_team_pg}</td>
                          <td className="py-1 pr-2">{r.pen_diff_pg > 0 ? `+${r.pen_diff_pg}` : r.pen_diff_pg}</td>
                          <td className="py-1">{pct(r.over_rate, 0)}</td>
                        </>) : <td colSpan={6} className="py-1" style={{ color: "var(--muted)" }}>no history with this crew</td>}
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="text-sm" style={{ color: "var(--muted)" }}>
              {d.referee?.note ?? "No referee recorded."}
            </p>
          )}
        </GlassPanel>

        <GlassPanel title="Market">
          <div className="space-y-2 text-sm">
            <div className="flex flex-wrap gap-2">
              <Chip tone="arc">{d.market.spread_line != null
                ? `${d.game.home_team} ${d.market.spread_line > 0 ? "-" : "+"}${Math.abs(d.market.spread_line)}`
                : "no line"}</Chip>
              <Chip>O/U {d.market.total_line ?? "—"}</Chip>
              <Chip>ML {d.market.home_moneyline ?? "—"} / {d.market.away_moneyline ?? "—"}</Chip>
              {d.market.kalshi?.prob_home != null && (
                <Chip tone="hot">Kalshi {pct(d.market.kalshi.prob_home)} home</Chip>
              )}
            </div>
            {d.market.line_history.length > 1 && (
              <LineChart data={d.market.line_history} xKey="ts" xLabel="Snapshot"
                title="Line movement"
                series={[{ key: "spread", name: "Spread (home)" },
                         { key: "total", name: "Total" }]}
                digits={1} />
            )}
            {s && s.ats_games > 0 && (
              <p className="text-xs" style={{ color: "var(--muted)" }}>
                Series ATS: {d.game.away_team} {s.ats_wins}–{s.ats_games - s.ats_wins} in lined meetings.
              </p>
            )}
          </div>
        </GlassPanel>
      </div>

      {(d.injuries.away.length > 0 || d.injuries.home.length > 0) && (
        <GlassPanel title={`Injury report — week ${d.game.week}`}>
          <div className="grid gap-6 sm:grid-cols-2">
            {(["away", "home"] as const).map((side) => (
              <div key={side}>
                <p className="mb-1 text-xs font-bold" style={{ color: side === "away" ? aGlow : hGlow }}>
                  {side === "away" ? d.game.away_team : d.game.home_team}
                </p>
                <ul className="space-y-1 text-xs">
                  {d.injuries[side].map((r, i) => (
                    <li key={i} className="flex gap-2">
                      <span className="font-medium">{r.player}</span>
                      <span style={{ color: "var(--muted)" }}>{r.position}</span>
                      <span className="ml-auto" style={{
                        color: r.status === "Out" ? "#f87171" :
                               r.status === "Questionable" ? "#facc15" : "var(--muted)" }}>
                        {r.status}{r.injury ? ` (${r.injury})` : ""}
                      </span>
                    </li>
                  ))}
                  {d.injuries[side].length === 0 && (
                    <li style={{ color: "var(--muted)" }}>none reported</li>)}
                </ul>
              </div>
            ))}
          </div>
        </GlassPanel>
      )}
    </div>
  );
}
