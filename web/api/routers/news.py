import logging

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

# import once at module load — the old per-request sys.path.insert grew
# sys.path with a duplicate entry on every search call
from nfl_analytics.news import search as fts_search

from ..deps import read_conn, rows_to_dicts  # deps puts src/ on sys.path

log = logging.getLogger(__name__)

router = APIRouter()

SOURCES = {
    "all": "source IN ('espn_news', 'team_site', 'pft', 'yahoo')",
    "espn": "source = 'espn_news'",
    "team": "source = 'team_site'",
    "wire": "source IN ('pft', 'yahoo')",
}

CATEGORIES = ("injury", "trade-signing", "depth-chart", "legal", "general")


@router.get("/api/news/search")
def news_search(q: str, limit: int = 25) -> dict:
    try:
        return {"query": q, "items": fts_search(q, min(limit, 50))}
    except Exception as e:
        return {"query": q, "items": [], "error": str(e)}


@router.get("/api/news")
def news(source: str = "all", category: str = "", limit: int = 50) -> dict:
    if source not in SOURCES:
        raise HTTPException(400, f"source must be one of {list(SOURCES)}")
    cat_clause = ""
    if category:
        if category not in CATEGORIES:
            raise HTTPException(400, f"category must be one of {CATEGORIES}")
        cat_clause = f"AND category = '{category}'"
    try:
        with read_conn(attach_news=True) as con:
            items = rows_to_dicts(
                con,
                f"""
                SELECT published_ts AS ts, source, category, teams, headline, url
                FROM newsdb.news WHERE {SOURCES[source]} {cat_clause}
                ORDER BY published_ts DESC NULLS LAST LIMIT ?
            """,
                [min(limit, 200)],
            )
    except Exception:
        # missing/locked news.duckdb: a clean 503 the UI can message, not a
        # raw traceback — this is the news page itself, so don't fake success
        log.warning("news: newsdb query failed", exc_info=True)
        return JSONResponse({"items": [], "error": "news store unavailable"}, status_code=503)
    return {"items": items}
