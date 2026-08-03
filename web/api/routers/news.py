from fastapi import APIRouter, HTTPException

from ..deps import read_conn, rows_to_dicts

router = APIRouter()

SOURCES = {
    "all": "source IN ('espn_news', 'team_site')",
    "espn": "source = 'espn_news'",
    "team": "source = 'team_site'",
}


@router.get("/api/news")
def news(source: str = "all", limit: int = 50) -> dict:
    if source not in SOURCES:
        raise HTTPException(400, f"source must be one of {list(SOURCES)}")
    with read_conn(attach_news=True) as con:
        items = rows_to_dicts(con, f"""
            SELECT published_ts AS ts, source, teams, headline, url
            FROM newsdb.news WHERE {SOURCES[source]}
            ORDER BY published_ts DESC NULLS LAST LIMIT ?
        """, [min(limit, 200)])
    return {"items": items}
