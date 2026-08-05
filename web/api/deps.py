"""Shared helpers for the Jarvis API: package bootstrap, row shaping, colors."""

import sys
from pathlib import Path

WEB_DIR = Path(__file__).resolve().parent.parent
ROOT = WEB_DIR.parent
sys.path.insert(0, str(ROOT / "src"))

from nfl_analytics import teams_meta  # noqa: E402,F401
from nfl_analytics.db import read_conn  # noqa: E402,F401  (re-exported)


def rows_to_dicts(con, sql: str, params=None) -> list[dict]:
    cur = con.execute(sql, params or [])
    cols = [d[0] for d in cur.description]
    out = []
    for row in cur.fetchall():
        d = {}
        for k, v in zip(cols, row, strict=False):
            if v != v:  # NaN
                v = None
            elif hasattr(v, "isoformat"):
                v = v.isoformat()
            elif hasattr(v, "item"):  # numpy scalar
                v = v.item()
            d[k] = v
        out.append(d)
    return out


def _luminance(hex_color: str) -> float:
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i : i + 2], 16) / 255 for i in (0, 2, 4))
    lin = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in (r, g, b)]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


# ── team colour tokens ───────────────────────────────────────────────────────
#
# glow_safe() blended every dark team colour toward WHITE, which desaturates as
# it lightens: Ravens purple, Seahawks navy and Texans deep blue all converged
# on the same lavender-grey, and LV's #000000 came out a flat grey with no
# team identity left in it at all.
#
# team_tokens() instead works in Oklab, where lightness and chroma are separate
# axes. It clamps L into a band that is readable on our dark surface and holds
# chroma above a floor so the hue survives -- and it NEVER touches the hue
# angle, so a team's colour still reads as that team's colour.
#
# Pure stdlib on purpose: this runs per request and must not add a dependency.

# 0.64 is not a round number by accident: at 0.62 the deep reds (KC, ARI, ATL,
# SF, TB) land at 4.41-4.44 on #161B22, just under the 4.5 text minimum.
_L_MIN, _L_MAX = 0.64, 0.78
_C_MIN, _C_MAX = 0.06, 0.15  # below the floor a hue reads as grey


def _srgb_to_linear(c: float) -> float:
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _linear_to_srgb(c: float) -> float:
    return 12.92 * c if c <= 0.0031308 else 1.055 * (c ** (1 / 2.4)) - 0.055


def _hex_to_oklab(hex_color: str) -> tuple[float, float, float]:
    h = hex_color.lstrip("#")
    r, g, b = (_srgb_to_linear(int(h[i : i + 2], 16) / 255) for i in (0, 2, 4))
    l = 0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b  # noqa: E741
    m = 0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b
    s = 0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b
    l_, m_, s_ = (v ** (1 / 3) if v > 0 else -((-v) ** (1 / 3)) for v in (l, m, s))
    return (
        0.2104542553 * l_ + 0.7936177850 * m_ - 0.0040720468 * s_,
        1.9779984951 * l_ - 2.4285922050 * m_ + 0.4505937099 * s_,
        0.0259040371 * l_ + 0.7827717662 * m_ - 0.8086757660 * s_,
    )


def _oklab_to_hex(L: float, a: float, b: float) -> str:
    l_ = L + 0.3963377774 * a + 0.2158037573 * b
    m_ = L - 0.1055613458 * a - 0.0638541728 * b
    s_ = L - 0.0894841775 * a - 1.2914855480 * b
    l, m, s = (v**3 for v in (l_, m_, s_))  # noqa: E741
    r = +4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s
    g = -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s
    bl = -0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s
    out = []
    for c in (r, g, bl):
        v = round(max(0.0, min(1.0, _linear_to_srgb(max(0.0, min(1.0, c))))) * 255)
        out.append(v)
    return "#{:02x}{:02x}{:02x}".format(*out)


def _polar(a: float, b: float) -> tuple[float, float]:
    import math

    return math.hypot(a, b), math.degrees(math.atan2(b, a)) % 360


def _from_polar(L: float, C: float, h_deg: float) -> str:
    import math

    rad = math.radians(h_deg)
    return _oklab_to_hex(L, C * math.cos(rad), C * math.sin(rad))


def team_tokens(hex_color: str) -> dict[str, str]:
    """Three tokens per team, for identity only -- never a background or a CTA.

    ink    text/rules on a dark surface; L and C clamped, hue untouched
    solid  a filled chip or bar; the brand colour, only floor-lifted
    wash    a 10% tint for a banner or a selected row
    """
    L, a, b = _hex_to_oklab(hex_color)
    C, h = _polar(a, b)

    # A pure greyscale source (LV #000000, raiders silver) has NO hue to keep.
    # Inventing one would be a lie, so it stays neutral and the logo carries
    # the identity.
    if C < 0.01:
        ink = _from_polar(_L_MIN + 0.08, 0.0, 0.0)
        return {"ink": ink, "solid": ink, "wash": "rgba(230,237,243,0.08)"}

    ink = _from_polar(min(_L_MAX, max(_L_MIN, L)), min(_C_MAX, max(_C_MIN, C)), h)
    solid = _from_polar(max(0.45, L), min(_C_MAX + 0.05, max(_C_MIN, C)), h)
    return {"ink": ink, "solid": solid, "wash": f"{ink}1a"}  # 1a = 10% alpha


def hue_of(hex_color: str) -> float:
    """Oklab hue angle in degrees. Used to detect two-team collisions."""
    _, a, b = _hex_to_oklab(hex_color)
    return _polar(a, b)[1]


def team_pair_tokens(a_hex: str, b_hex: str) -> tuple[dict, dict]:
    """Tokens for a two-team page.

    DEN and CIN are both literally #FB4F14. Rendering both sides in the same
    colour makes the page unreadable, so when the hues are within 25 degrees
    the AWAY side is demoted to neutral and the logo does the identifying.
    """
    ta, tb = team_tokens(a_hex), team_tokens(b_hex)
    delta = abs(hue_of(a_hex) - hue_of(b_hex)) % 360
    if min(delta, 360 - delta) < 25:
        ta = {
            "ink": "var(--color-muted)",
            "solid": "var(--color-surface-3)",
            "wash": "rgba(152,162,176,0.10)",
        }
    return ta, tb
