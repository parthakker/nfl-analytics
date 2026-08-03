export interface TeamMeta {
  name: string;
  conf: string;
  div: string;
  color: string;
  glow: string;
  logo: string;
}

export interface Meta {
  teams: Record<string, TeamMeta>;
  divisions: Record<string, string[]>;
  kickoff_2026: string | null;
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
  num: number | null; name: string; pos: string | null;
  status: string | null; college: string | null; exp: number | null;
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

async function get<T>(path: string, retried = false): Promise<T> {
  const r = await fetch(path);
  if (r.status === 503 && !retried) {
    // a scheduled data collector briefly holds the store — wait it out once
    await new Promise((res) => setTimeout(res, 3000));
    return get<T>(path, true);
  }
  if (!r.ok) throw new Error(`${path}: HTTP ${r.status}`);
  return r.json() as Promise<T>;
}

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
    info: { name: string; pos: string; team: string; headshot: string | null };
    seasons: Record<string, number | string | null>[];
    weekly: { season: number; week: number; ppr: number | null; opp: string }[];
    news: NewsItem[];
  }>(`/api/players/${gsis}`),
  leaders: (season: number, cat: string, minGames: number) =>
    get<{ label: string; rows: Record<string, string | number | null>[] }>(
      `/api/leaders?season=${season}&cat=${cat}&min_games=${minGames}`),
  markets: (kind = "game") => get<{ kind: string; markets: MarketRow[] }>(`/api/markets?kind=${kind}`),
  marketHistory: (ticker: string) =>
    get<{ ticker: string; title: string; points: { ts: string; prob: number | null }[] }>(
      `/api/markets/${ticker}/history`),
};
