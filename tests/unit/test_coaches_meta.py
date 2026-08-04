"""coaches_meta.json v2 completeness + knowledge-link integrity.

Keeps the hand-curated staff db honest: every team fully populated, every
scheme deep-link pointing at a chapter slug and heading that actually exist.
"""

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
META = json.loads((ROOT / "data" / "coaches_meta.json").read_text(encoding="utf-8"))
KNOWLEDGE = ROOT / "docs" / "knowledge"

# teams where the HC personally holds the defense with no DC title
DC_NULL_ALLOWED = {"TB"}

TEAMS = {k: v for k, v in META.items() if not k.startswith("_")}


def slugify(text: str) -> str:
    """Must match the TS slugify in Knowledge.tsx."""
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def test_thirty_two_teams():
    assert len(TEAMS) == 32


def test_hc_blocks_complete():
    for team, v in TEAMS.items():
        assert v["head_coach"], team
        assert v["hc"]["about"].strip(), f"{team}: empty hc.about"
        assert isinstance(v["hc"]["since"], int), team


def test_coordinators_populated():
    for team, v in TEAMS.items():
        oc = v["oc"]
        assert oc and oc["name"].strip() and oc["about"].strip(), f"{team}: OC incomplete"
        assert isinstance(oc["playcaller"], bool), team
        dc = v["dc"]
        if dc is None:
            assert team in DC_NULL_ALLOWED, f"{team}: dc null but not a known HC-called defense"
            assert "no DC" in v["defense_scheme"]["fact"], f"{team}: null dc needs explanation"
        else:
            assert dc["name"].strip() and dc["about"].strip(), f"{team}: DC incomplete"


def test_knowledge_links_resolve():
    index = {c["slug"] for c in json.loads((KNOWLEDGE / "index.json").read_text(encoding="utf-8"))}
    heading_cache: dict[str, set] = {}
    for team, v in TEAMS.items():
        for side in ("offense_scheme", "defense_scheme"):
            link = v[side].get("knowledge", "")
            assert link, f"{team}: {side} missing knowledge link"
            slug, _, anchor = link.partition("#")
            assert slug in index, f"{team}: unknown chapter {slug!r}"
            if anchor:
                if slug not in heading_cache:
                    md = (KNOWLEDGE / f"{slug}.md").read_text(encoding="utf-8")
                    heading_cache[slug] = {
                        slugify(m.group(1)) for m in re.finditer(r"^#{2,3} (.+)$", md, re.MULTILINE)
                    }
                assert anchor in heading_cache[slug], (
                    f"{team}: anchor #{anchor} not a heading in {slug}.md"
                )


def test_scheme_families_named():
    for team, v in TEAMS.items():
        assert v["offense_scheme"]["family"] not in ("", "unclassified"), team
        assert v["defense_scheme"]["family"] not in ("", "varies by coordinator"), team
