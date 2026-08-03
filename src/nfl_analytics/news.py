"""ESPN news + injury-report ingestion into news.duckdb.

Idempotent: rows are deduped on (source, article_id); re-polling is always
safe. Player tags resolve ESPN athlete ids to gsis_id via the players table
(espn_id column); unmatched tags are kept as 'espn:<id>' strings, never
dropped. ESPN feeds are unofficial — all parsing is wrapped so a shape
change fails loudly without corrupting stored news.
"""

import logging
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from datetime import datetime, timezone

import duckdb
import httpx

from .config import NEWS_DB, NFL_DB
from .teams_meta import TEAMS, rss_url

log = logging.getLogger("nfl-news")

NEWS_URL = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/news?limit=50"
INJURIES_URL = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/injuries"
TEAMS_URL = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/teams"

# ESPN abbreviations that differ from our canonical nflverse codes
ESPN_TEAM_FIX = {"WSH": "WAS", "LAR": "LA"}

SCHEMA = """
    CREATE TABLE IF NOT EXISTS news (
        source VARCHAR, article_id VARCHAR,
        published_ts TIMESTAMP, fetched_ts TIMESTAMP,
        headline VARCHAR, body VARCHAR, url VARCHAR,
        players VARCHAR[], teams VARCHAR[]
    )
"""


def _espn_team_map(client: httpx.Client) -> dict[str, str]:
    """ESPN numeric team id -> canonical abbreviation."""
    js = client.get(TEAMS_URL).json()
    out = {}
    for t in js["sports"][0]["leagues"][0]["teams"]:
        ab = t["team"]["abbreviation"]
        out[str(t["team"]["id"])] = ESPN_TEAM_FIX.get(ab, ab)
    return out


def _gsis_map(espn_ids: set[str]) -> dict[str, str]:
    if not espn_ids:
        return {}
    con = duckdb.connect(str(NFL_DB), read_only=True)
    try:
        rows = con.execute("""
            SELECT espn_id::varchar, gsis_id FROM players
            WHERE espn_id IS NOT NULL AND espn_id::varchar IN
            (SELECT unnest(?::varchar[]))
        """, [list(espn_ids)]).fetchall()
    finally:
        con.close()
    return dict(rows)


def _ts(s: str | None) -> datetime | None:
    """ESPN stamps vary ('2026-08-02T21:48Z', with/without seconds) — parse
    permissively to a real datetime; None if hopeless."""
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None


def _athlete_espn_id(athlete: dict) -> str | None:
    if athlete.get("id"):
        return str(athlete["id"])
    for link in athlete.get("links", []):
        href = link.get("href", "")
        if "/id/" in href:
            return href.split("/id/")[1].split("/")[0]
    return None


def poll(client: httpx.Client | None = None) -> dict:
    """Fetch both feeds, insert new rows, return counts."""
    client = client or httpx.Client(follow_redirects=True, timeout=30)
    now = datetime.now(timezone.utc)
    team_map = _espn_team_map(client)
    rows = []

    # --- news articles ---
    for a in client.get(NEWS_URL).json().get("articles", []):
        espn_ids, teams = [], []
        for cat in a.get("categories", []):
            if cat.get("type") == "athlete" and cat.get("athleteId"):
                espn_ids.append(str(cat["athleteId"]))
            elif cat.get("type") == "team" and cat.get("teamId"):
                ab = team_map.get(str(cat["teamId"]))
                if ab:
                    teams.append(ab)
        rows.append({
            "source": "espn_news", "article_id": str(a["id"]),
            "published_ts": _ts(a.get("published")), "fetched_ts": now,
            "headline": a.get("headline", ""), "body": a.get("description", ""),
            "url": (a.get("links", {}).get("web", {}) or {}).get("href", ""),
            "espn_ids": espn_ids, "teams": teams,
        })

    # --- injury report ---
    for team in client.get(INJURIES_URL).json().get("injuries", []):
        for inj in team.get("injuries", []):
            ath = inj.get("athlete", {})
            eid = _athlete_espn_id(ath)
            status = inj.get("status", "")
            date = (inj.get("date") or "")[:10]
            rows.append({
                "source": "espn_injuries",
                "article_id": f"{eid}-{date}-{status}",
                "published_ts": _ts(inj.get("date")), "fetched_ts": now,
                "headline": f"{ath.get('displayName','?')} ({team.get('displayName','')}): {status}",
                "body": inj.get("longComment") or inj.get("shortComment") or "",
                "url": next((l["href"] for l in ath.get("links", [])
                             if "playercard" in l.get("rel", [])), ""),
                "espn_ids": [eid] if eid else [], "teams": [],
            })

    # --- official team-site RSS feeds (32 clubs, standard /rss/news) ---
    for code in TEAMS:
        try:
            r = client.get(rss_url(code),
                           headers={"User-Agent": "Mozilla/5.0"})
            if r.status_code != 200:
                continue
            root = ET.fromstring(r.content)
            for item in root.iter("item"):
                link = (item.findtext("link") or "").strip()
                if not link:
                    continue
                pub = item.findtext("pubDate")
                try:
                    pub_ts = parsedate_to_datetime(pub) if pub else None
                except (TypeError, ValueError):
                    pub_ts = None
                rows.append({
                    "source": "team_site", "article_id": link,
                    "published_ts": pub_ts, "fetched_ts": now,
                    "headline": (item.findtext("title") or "").strip(),
                    "body": (item.findtext("description") or "").strip()[:1000],
                    "url": link, "espn_ids": [], "teams": [code],
                })
        except (httpx.HTTPError, ET.ParseError) as e:
            log.warning("team RSS failed for %s: %s", code, e)

    # resolve espn ids -> gsis ids in one pass
    all_ids = {i for r in rows for i in r["espn_ids"]}
    gsis = _gsis_map(all_ids)
    for r in rows:
        r["players"] = [gsis.get(i, f"espn:{i}") for i in r.pop("espn_ids")]

    con = duckdb.connect(str(NEWS_DB))
    try:
        con.execute(SCHEMA)
        before = con.execute("SELECT count(*) FROM news").fetchone()[0]
        for r in rows:
            con.execute("""
                INSERT INTO news
                SELECT ?, ?, ?, ?, ?, ?, ?, ?, ?
                WHERE NOT EXISTS (SELECT 1 FROM news
                                  WHERE source = ? AND article_id = ?)
            """, [r["source"], r["article_id"], r["published_ts"],
                  r["fetched_ts"], r["headline"], r["body"], r["url"],
                  r["players"], r["teams"],
                  r["source"], r["article_id"]])
        total = con.execute("SELECT count(*) FROM news").fetchone()[0]
        inserted = total - before
    finally:
        con.close()
    matched = sum(1 for r in rows for p in r["players"] if not p.startswith("espn:"))
    tagged = sum(len(r["players"]) for r in rows)
    return {"fetched": len(rows), "new_rows": inserted, "stored_total": total,
            "player_tags": tagged, "tags_resolved_to_gsis": matched}
