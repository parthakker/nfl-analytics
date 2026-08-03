import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import GlassPanel from "../components/GlassPanel";
import { hexToRgba } from "../lib/color";
import { useMeta } from "../lib/MetaContext";

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

const TYPE_OPTS = [["", "All games"], ["REG", "Regular season"], ["POST", "Playoffs"]] as const;
const SITE_OPTS = [["", "Any site"], ["a_home", "at first team"], ["b_home", "at second team"],
                   ["neutral", "Neutral"]] as const;

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

  const codes = meta ? Object.keys(meta.teams).sort() : [];
  const ta = meta?.teams[d?.teams[0] ?? ""];
  const tb = meta?.teams[d?.teams[1] ?? ""];
  const sum = d?.summary;

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Head-to-head explorer</h1>
        <p className="text-sm" style={{ color: "var(--muted)" }}>
          Any two franchises, every meeting since 1999 — relocations merged
          (STL→LA, SD→LAC, OAK→LV). Click a game for the full matchup card.
        </p>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        {[["first", pa, setPa], ["second", pb, setPb]].map(([lbl, val, set]) => (
          <select key={lbl as string} value={val as string}
                  onChange={(e) => (set as (v: string) => void)(e.target.value)}
                  className="rounded-lg border bg-transparent px-2 py-1.5 text-sm font-semibold"
                  style={{ borderColor: "var(--stroke)" }}>
            <option value="" style={{ color: "#000" }}>{lbl as string} team…</option>
            {codes.map((c) => <option key={c} value={c} style={{ color: "#000" }}>{c}</option>)}
          </select>
        ))}
        <button onClick={() => pa && pb && pa !== pb && nav(`/h2h/${pa}/${pb}`)}
                disabled={!pa || !pb || pa === pb}
                className="rounded-full border px-4 py-1.5 text-sm font-semibold disabled:opacity-40"
                style={{ borderColor: "var(--arc)", color: "var(--arc)" }}>
          Compare
        </button>
        {d && (
          <>
            <span className="mx-1 h-5 w-px" style={{ background: "var(--stroke)" }} />
            {[[TYPE_OPTS, stype, setStype], [SITE_OPTS, site, setSite]].map(([opts, val, set], i) => (
              <select key={i} value={val as string}
                      onChange={(e) => (set as (v: string) => void)(e.target.value)}
                      className="rounded-lg border bg-transparent px-2 py-1.5 text-sm"
                      style={{ borderColor: "var(--stroke)" }}>
                {(opts as readonly (readonly [string, string])[]).map(([v, l]) => (
                  <option key={v} value={v} style={{ color: "#000" }}>{l}</option>))}
              </select>
            ))}
          </>
        )}
      </div>

      {d && sum && ta && tb && (
        <>
          <div className="glass relative overflow-hidden p-6" style={{
            background: `linear-gradient(105deg, ${hexToRgba(ta.color, 0.45)}, var(--glass) 45%, var(--glass) 55%, ${hexToRgba(tb.color, 0.45)})` }}>
            <div className="flex items-center gap-5">
              <Link to={`/team/${d.teams[0]}`}><img src={ta.logo} alt="" className="logo-glow h-14 w-14" /></Link>
              <div className="text-lg font-bold">{ta.name}</div>
              <div className="mx-auto text-center">
                <div className="text-3xl font-bold tabular-nums tracking-tight">
                  {sum.a_wins}–{sum.b_wins}{sum.ties ? `–${sum.ties}` : ""}
                </div>
                <div className="text-xs" style={{ color: "var(--muted)" }}>
                  {sum.games} meetings · {sum.first_season}–{sum.last_season}
                  {d.streak && d.streak.current_streak !== 0 && (
                    <> · {d.streak.current_streak > 0 ? d.teams[0] : d.teams[1]} won last{" "}
                      {Math.abs(d.streak.current_streak)}</>
                  )}
                </div>
              </div>
              <div className="text-right text-lg font-bold">{tb.name}</div>
              <Link to={`/team/${d.teams[1]}`}><img src={tb.logo} alt="" className="logo-glow h-14 w-14" /></Link>
            </div>
          </div>

          <div className="grid gap-6 lg:grid-cols-3">
            <GlassPanel title="Site splits">
              <table className="w-full text-left text-sm">
                <tbody>
                  {[[`at ${d.teams[0]}`, sum.a_home_wins, sum.a_home_games],
                    [`at ${d.teams[1]}`, sum.a_away_wins, sum.a_away_games],
                    ["neutral", null, sum.neutral_games]].map(([lbl, w, g], i) => (
                    <tr key={i} className="border-t tabular-nums" style={{ borderColor: "var(--stroke)" }}>
                      <td className="py-1.5 pr-3" style={{ color: "var(--muted)" }}>{lbl}</td>
                      <td className="py-1.5 pr-3">{g as number} games</td>
                      <td className="py-1.5">{w != null ? `${d.teams[0]} ${w}–${(g as number) - (w as number)}` : "—"}</td>
                    </tr>
                  ))}
                  <tr className="border-t tabular-nums" style={{ borderColor: "var(--stroke)" }}>
                    <td className="py-1.5 pr-3" style={{ color: "var(--muted)" }}>avg margin</td>
                    <td className="py-1.5 pr-3" colSpan={2}>
                      {sum.avg_margin_a > 0 ? `${d.teams[0]} +${sum.avg_margin_a}` :
                       sum.avg_margin_a < 0 ? `${d.teams[1]} +${-sum.avg_margin_a}` : "even"} · total {sum.avg_total}
                    </td>
                  </tr>
                  <tr className="border-t tabular-nums" style={{ borderColor: "var(--stroke)" }}>
                    <td className="py-1.5 pr-3" style={{ color: "var(--muted)" }}>ATS ({d.teams[0]})</td>
                    <td className="py-1.5" colSpan={2}>{sum.a_covers}–{sum.ats_games - sum.a_covers}</td>
                  </tr>
                </tbody>
              </table>
            </GlassPanel>

            <GlassPanel title="By era">
              <div className="max-h-56 overflow-y-auto">
                <table className="w-full text-left text-sm">
                  <tbody>
                    {d.splits.by_decade.map((r) => (
                      <tr key={r.era} className="border-t tabular-nums" style={{ borderColor: "var(--stroke)" }}>
                        <td className="py-1 pr-3" style={{ color: "var(--muted)" }}>{r.era}</td>
                        <td className="py-1 pr-3">{r.g} g</td>
                        <td className="py-1">{d.teams[0]} {r.a_wins}–{r.g - r.a_wins}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </GlassPanel>

            <GlassPanel title="By venue">
              <div className="max-h-56 overflow-y-auto">
                <table className="w-full text-left text-sm">
                  <tbody>
                    {d.splits.by_venue.map((r) => (
                      <tr key={r.venue} className="border-t tabular-nums" style={{ borderColor: "var(--stroke)" }}>
                        <td className="max-w-40 truncate py-1 pr-3" style={{ color: "var(--muted)" }}>{r.venue}</td>
                        <td className="py-1 pr-3">{r.g} g</td>
                        <td className="py-1">{d.teams[0]} {r.a_wins}–{r.g - r.a_wins}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </GlassPanel>
          </div>

          <GlassPanel title={`Every meeting (${d.games.length})`}>
            <div className="max-h-[32rem] overflow-y-auto">
              <table className="w-full text-left text-sm">
                <thead className="sticky top-0" style={{ background: "var(--bg-1)" }}>
                  <tr style={{ color: "var(--muted)" }}>
                    {["Date", "Site", "Score", "Winner", "Spread", "Venue", "QBs", "Ref"].map((h) => (
                      <th key={h} className="py-1.5 pr-3 font-medium">{h}</th>))}
                  </tr>
                </thead>
                <tbody>
                  {d.games.map((g) => (
                    <tr key={g.game_id} onClick={() => nav(`/matchup/${g.game_id}`)}
                        className="cursor-pointer border-t transition-colors hover:bg-white/5"
                        style={{ borderColor: "var(--stroke)" }}>
                      <td className="py-1.5 pr-3 text-xs" style={{ color: "var(--muted)" }}>
                        {g.date}{g.season_type === "POST" && (
                          <span className="ml-1 font-bold" style={{ color: "var(--arc)" }}>{g.game_type}</span>)}
                      </td>
                      <td className="py-1.5 pr-3 text-xs">
                        {g.site === "home" ? `at ${d.teams[0]}` : g.site === "away" ? `at ${d.teams[1]}` : "neutral"}
                      </td>
                      <td className="py-1.5 pr-3 tabular-nums">{g.a_score}–{g.b_score}{g.overtime ? " OT" : ""}</td>
                      <td className="py-1.5 pr-3 font-semibold" style={{
                        color: g.a_win === 1 ? (ta?.glow ?? "inherit") : g.a_win === 0 ? (tb?.glow ?? "inherit") : "var(--muted)" }}>
                        {g.a_win === 1 ? d.teams[0] : g.a_win === 0 ? d.teams[1] : "tie"}
                      </td>
                      <td className="py-1.5 pr-3 text-xs tabular-nums" style={{ color: "var(--muted)" }}>
                        {g.spread_line_a != null
                          ? `${d.teams[0]} ${g.spread_line_a > 0 ? "-" : "+"}${Math.abs(g.spread_line_a)}${
                              g.covered_a == null ? "" : g.covered_a ? " ✓" : " ✗"}`
                          : "—"}
                      </td>
                      <td className="max-w-36 truncate py-1.5 pr-3 text-xs" style={{ color: "var(--muted)" }}>
                        {g.venue_name}</td>
                      <td className="max-w-44 truncate py-1.5 pr-3 text-xs" style={{ color: "var(--muted)" }}>
                        {g.a_qb ?? "—"} / {g.b_qb ?? "—"}</td>
                      <td className="max-w-28 truncate py-1.5 text-xs" style={{ color: "var(--muted)" }}>
                        {g.referee ?? "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </GlassPanel>
        </>
      )}
      {!d && a && b && <p style={{ color: "var(--muted)" }}>Loading…</p>}
    </div>
  );
}
