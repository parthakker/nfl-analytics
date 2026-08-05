"""Team colour tokens are computed, so the checks are computed too.

Eyeballing 32 colours does not scale and does not catch a 4.4:1 near-miss.
"""

import pytest

from nfl_analytics import teams_meta
from web.api.deps import _hex_to_oklab, _luminance, hue_of, team_pair_tokens, team_tokens

SURFACE = "#161b22"  # --color-surface, what team ink actually sits on


def contrast(fg: str, bg: str = SURFACE) -> float:
    a, b = _luminance(fg), _luminance(bg)
    hi, lo = max(a, b), min(a, b)
    return (hi + 0.05) / (lo + 0.05)


def chroma(hex_color: str) -> float:
    _, a, b = _hex_to_oklab(hex_color)
    return (a * a + b * b) ** 0.5


TEAM_COLORS = [(code, t[5]) for code, t in teams_meta.TEAMS.items()]


def test_luminance_bounds():
    assert _luminance("#000000") == 0.0
    assert abs(_luminance("#ffffff") - 1.0) < 1e-9


@pytest.mark.parametrize(("code", "src"), TEAM_COLORS)
def test_all_team_inks_meet_contrast(code, src):
    """Every team's ink must be readable as TEXT on the panel surface."""
    ink = team_tokens(src)["ink"]
    ratio = contrast(ink)
    assert ratio >= 4.5, f"{code} ink {ink} is {ratio:.2f}:1 on {SURFACE}"


@pytest.mark.parametrize(("code", "src"), TEAM_COLORS)
def test_ink_keeps_the_team_hue(code, src):
    """The clamp moves lightness and chroma; it must NOT move the hue. That is
    what made glow_safe collapse Ravens purple and Seahawks navy into the same
    lavender-grey -- blending toward white desaturates as it lightens."""
    if chroma(src) < 0.01:
        pytest.skip(f"{code} is achromatic, deliberately rendered neutral")
    drift = abs(hue_of(src) - hue_of(team_tokens(src)["ink"])) % 360
    assert min(drift, 360 - drift) <= 2.0, f"{code} hue moved {drift:.2f} deg"


def test_greyscale_team_stays_neutral():
    """LV is literally #000000. Inventing a hue for it would be a lie, so it
    renders neutral and the logo carries the identity."""
    tok = team_tokens("#000000")
    assert chroma(tok["ink"]) < 0.01
    assert contrast(tok["ink"]) >= 4.5


def test_distinct_sources_get_distinct_inks():
    """A colour that identifies everyone identifies no one. Two teams may only
    share an ink if they literally share a source hex (DEN/CIN both #FB4F14)."""
    by_ink: dict[str, list[str]] = {}
    for code, src in TEAM_COLORS:
        by_ink.setdefault(team_tokens(src)["ink"], []).append(code)
    sources = dict(TEAM_COLORS)
    for ink, codes in by_ink.items():
        if len(codes) == 1:
            continue
        distinct = {sources[c].lower() for c in codes}
        assert len(distinct) == 1, f"{codes} collapsed to {ink} from {distinct}"


def test_pair_collision_demotes_to_neutral():
    """DEN and CIN are both #FB4F14. Painting both sides of a matchup the same
    colour makes the page unreadable, so the away side goes neutral."""
    away, home = team_pair_tokens(teams_meta.TEAMS["DEN"][5], teams_meta.TEAMS["CIN"][5])
    assert away["ink"] != home["ink"]
    assert "muted" in away["ink"], f"expected a neutral demotion, got {away['ink']}"


def test_pair_with_distinct_hues_keeps_both():
    kc = teams_meta.TEAMS["KC"][5]  # red
    phi = teams_meta.TEAMS["PHI"][5]  # midnight green
    away, home = team_pair_tokens(kc, phi)
    assert away["ink"].startswith("#") and home["ink"].startswith("#")
    assert away["ink"] != home["ink"]


@pytest.mark.parametrize(("code", "src"), TEAM_COLORS)
def test_token_shape(code, src):
    tok = team_tokens(src)
    assert set(tok) == {"ink", "solid", "wash"}
    assert tok["ink"].startswith("#") and len(tok["ink"]) == 7
    assert tok["solid"].startswith("#") and len(tok["solid"]) == 7
