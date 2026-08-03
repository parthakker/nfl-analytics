"""The NFL Knowledge book: chapters live as markdown in docs/knowledge/ and are
served raw — edit a chapter file and refresh the page, no UI rebuild needed.
index.json (hand-ordered) drives the table of contents."""

import json
from pathlib import Path

from fastapi import APIRouter, HTTPException

from ..deps import ROOT

router = APIRouter()

KNOWLEDGE = ROOT / "docs" / "knowledge"


def _manifest() -> list[dict]:
    try:
        return json.loads((KNOWLEDGE / "index.json").read_text(encoding="utf-8"))
    except FileNotFoundError:
        return []


@router.get("/api/knowledge")
def chapters() -> dict:
    return {"chapters": _manifest()}


@router.get("/api/knowledge/{slug}")
def chapter(slug: str) -> dict:
    manifest = _manifest()
    idx = next((i for i, c in enumerate(manifest) if c["slug"] == slug), None)
    if idx is None:  # manifest is the whitelist — no path traversal
        raise HTTPException(404, "unknown chapter")
    md = (KNOWLEDGE / f"{slug}.md").read_text(encoding="utf-8")
    return {**manifest[idx], "markdown": md,
            "prev": ({k: manifest[idx - 1][k] for k in ("slug", "title")}
                     if idx > 0 else None),
            "next": ({k: manifest[idx + 1][k] for k in ("slug", "title")}
                     if idx < len(manifest) - 1 else None)}
