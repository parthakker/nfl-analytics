"""Shared helpers for the Jarvis API: package bootstrap, row shaping, colors."""

import sys
from pathlib import Path

WEB_DIR = Path(__file__).resolve().parent.parent
ROOT = WEB_DIR.parent
sys.path.insert(0, str(ROOT / "src"))

from nfl_analytics.db import read_conn  # noqa: E402,F401  (re-exported)
from nfl_analytics import teams_meta  # noqa: E402,F401


def rows_to_dicts(con, sql: str, params=None) -> list[dict]:
    cur = con.execute(sql, params or [])
    cols = [d[0] for d in cur.description]
    out = []
    for row in cur.fetchall():
        d = {}
        for k, v in zip(cols, row):
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
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    lin = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
           for c in (r, g, b)]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def glow_safe(hex_color: str, floor: float = 0.35) -> str:
    """Lighten near-black team colors until they can visibly glow."""
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    for _ in range(12):
        if _luminance(f"#{r:02x}{g:02x}{b:02x}") >= floor:
            break
        r, g, b = (min(255, int(c + (255 - c) * 0.18)) for c in (r, g, b))
    return f"#{r:02x}{g:02x}{b:02x}"
