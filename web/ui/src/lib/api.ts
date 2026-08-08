export interface TeamTokens {
  /** text and rules on a dark surface — contrast-clamped, hue preserved */
  ink: string;
  /** a filled chip, bar or rail */
  solid: string;
  /** 10% tint for a banner or a selected row */
  wash: string;
}

export interface TeamMeta {
  name: string;
  conf: string;
  div: string;
  /** the brand hex, unmodified — for a logo backdrop, never for text */
  color: string;
  tokens: TeamTokens;
  logo: string;
}

export interface Meta {
  teams: Record<string, TeamMeta>;
  divisions: Record<string, string[]>;
  kickoff: string | null;
}

export interface DivisionStanding {
  name: string;
  teams: { code: string; w: number; l: number; pf_pg: number | null; pa_pg: number | null }[];
}

export interface ScheduleGame {
  game_id: string;
  date: string;
  gametime: string | null;
  away: string;
  away_score: number | null;
  home: string;
  home_score: number | null;
  spread: number | null;
  total: number | null;
  home_ml: number | null;
}

export interface NewsItem {
  ts: string | null;
  source: string;
  teams?: string[];
  headline: string;
  url: string;
}

export interface TeamDetail {
  code: string;
  season: number;
  record: { w: number; l: number; pf_pg: number | null; pa_pg: number | null };
  sos: { rank: number; value: number } | null;
  coach: {
    current: string | null;
    history: { season: number; coach: string; games: number; wins: number; ppg: number }[];
  };
}

export interface RosterPlayer {
  gsis: string | null; num: number | null; name: string; pos: string | null;
  status: string | null; college: string | null; exp: number | null;
  headshot: string | null;
}

export interface LeaderColumn {
  key: string; label: string; kind: "count" | "count_g" | "rate" | "pct";
  help: string;
}
export interface LeaderRow {
  player_id: string; player: string; pos: string | null; team: string;
  headshot: string | null; games: number;
  [stat: string]: string | number | null;
}
export interface LeadersResponse {
  family: string; season: number; season_type: string; position: string | null;
  sort: string; dir: string; label: string; qual: number; qual_key: string;
  limit: number; seasons: number[]; total_players: number; qualified: number;
  columns: LeaderColumn[]; league_avg: Record<string, number | null>;
  p10: Record<string, number | null>; p90: Record<string, number | null>;
  rows: LeaderRow[];
}

export interface TeamScheduleGame {
  game_id: string; week: number; date: string; opponent: string; home: boolean;
  home_score: number | null; away_score: number | null;
  line_text: string | null; total: number | null;
}

export interface MarketRow {
  ticker: string; title: string; yes_team: string;
  away_team: string | null; home_team: string | null; event_date: string | null;
  yes_bid: number | null; yes_ask: number | null; prob: number | null;
  last_price: number | null; volume: number | null; open_interest: number | null;
  delta_24h: number | null; as_of: string; spark: (number | null)[];
}

async function get<T>(path: string, signal?: AbortSignal, retried = false): Promise<T> {
  const r = await fetch(path, { signal });
  if (r.status === 503 && !retried) {
    // a scheduled data collector briefly holds the store — wait it out once
    await new Promise((res) => setTimeout(res, 3000));
    return get<T>(path, signal, true);
  }
  if (!r.ok) throw new Error(`${path}: HTTP ${r.status}`);
  return r.json() as Promise<T>;
}

/** The one JSON getter — 503-retry included. Pages consume it via useApi. */
export { get as apiGet };

export const api = {
  meta: () => get<Meta>("/api/meta"),
  overview: (season = 2025) =>
    get<{ season: number; divisions: DivisionStanding[] }>(`/api/league/overview?season=${season}`),
  schedule: (season = 2026, week?: number) =>
    get<{ season: number; week: number; weeks: number[]; games: ScheduleGame[] }>(
      `/api/schedule?season=${season}${week ? `&week=${week}` : ""}`),
  news: (source = "all", limit = 50) =>
    get<{ items: NewsItem[] }>(`/api/news?source=${source}&limit=${limit}`),
  team: (code: string, season = 2025) => get<TeamDetail>(`/api/teams/${code}?season=${season}`),
  teamEpa: (code: string, season = 2025) =>
    get<{ season: number; weeks: { week: number; off: number | null; def: number | null }[] }>(
      `/api/teams/${code}/epa?season=${season}`),
  teamRoster: (code: string) =>
    get<{ season: number; players: RosterPlayer[] }>(`/api/teams/${code}/roster`),
  teamSchedule: (code: string, season = 2026) =>
    get<{ season: number; games: TeamScheduleGame[] }>(`/api/teams/${code}/schedule?season=${season}`),
  teamNews: (code: string, limit = 20) =>
    get<{ items: NewsItem[] }>(`/api/teams/${code}/news?limit=${limit}`),
  playerSearch: (q: string) =>
    get<{ hits: { gsis_id: string; name: string; pos: string; team: string }[] }>(
      `/api/players/search?q=${encodeURIComponent(q)}`),
  player: (gsis: string) => get<{
    info: { name: string; pos: string; team: string; headshot: string | null;
            rookie_season: number | null; last_season: number | null;
            draft_year: number | null; draft_round: number | null };
    seasons: Record<string, number | string | null>[];
    weekly: { season: number; week: number; ppr: number | null; opp: string }[];
    news: NewsItem[];
  }>(`/api/players/${gsis}`),
  leaders: (p: { family: string; season?: number; seasonType?: string;
                 position?: string; sort?: string; dir?: string;
                 qual?: number; limit?: number }) => {
    const q = new URLSearchParams({ family: p.family });
    if (p.season != null) q.set("season", String(p.season));
    if (p.seasonType) q.set("season_type", p.seasonType);
    if (p.position) q.set("position", p.position);
    if (p.sort) q.set("sort", p.sort);
    if (p.dir) q.set("dir", p.dir);
    if (p.qual != null) q.set("qual", String(p.qual));
    if (p.limit != null) q.set("limit", String(p.limit));
    return get<LeadersResponse>(`/api/leaders?${q}`);
  },
  markets: (kind = "game") => get<{ kind: string; markets: MarketRow[] }>(`/api/markets?kind=${kind}`),
  marketHistory: (ticker: string) =>
    get<{ ticker: string; title: string; points: { ts: string; prob: number | null }[] }>(
      `/api/markets/${ticker}/history`),
};
