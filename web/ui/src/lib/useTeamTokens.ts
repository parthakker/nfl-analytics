import { useMemo } from "react";
import type { CSSProperties } from "react";
import { useMeta } from "./MetaContext";
import type { TeamTokens } from "./api";

const NEUTRAL: TeamTokens = {
  ink: "var(--color-muted)",
  solid: "var(--color-surface-3)",
  wash: "rgba(152,162,176,0.10)",
};

/** Style object for a page root: publishes --team-ink / --team-solid /
 *  --team-wash so the `text-team` / `bg-team` / `rail-team` utilities resolve.
 *
 *  It does NOT set --accent. That was the old behaviour and it meant the
 *  app's interactive language changed per team: blue meant "clickable" on one
 *  page and red on the next, so a link stopped being recognisable as a link.
 *  Accent is fixed forever; team colour is identity only, budgeted to under
 *  5% of the viewport — a rail, a chip, a logo backdrop.
 */
export function useTeamTokens(code: string | null | undefined): {
  tokens: TeamTokens;
  style: CSSProperties;
} {
  const meta = useMeta();
  return useMemo(() => {
    const t = (code && meta?.teams[code]?.tokens) || NEUTRAL;
    return {
      tokens: t,
      style: {
        ["--team-ink" as string]: t.ink,
        ["--team-solid" as string]: t.solid,
        ["--team-wash" as string]: t.wash,
      } as CSSProperties,
    };
  }, [code, meta]);
}

/** Two-team pages. When the hues are within 25 degrees the AWAY side is
 *  demoted to neutral — DEN and CIN are both literally #FB4F14, and rendering
 *  both rails in the same colour tells the reader nothing. */
export function useTeamPairTokens(away: string | null, home: string | null): {
  away: TeamTokens;
  home: TeamTokens;
} {
  const meta = useMeta();
  return useMemo(() => {
    const a = (away && meta?.teams[away]?.tokens) || NEUTRAL;
    const h = (home && meta?.teams[home]?.tokens) || NEUTRAL;
    const srcA = away ? meta?.teams[away]?.color : null;
    const srcH = home ? meta?.teams[home]?.color : null;
    if (srcA && srcH && collides(srcA, srcH)) return { away: NEUTRAL, home: h };
    return { away: a, home: h };
  }, [away, home, meta]);
}

/** Oklab hue distance. Mirrors deps.team_pair_tokens so the client and the
 *  server agree about what counts as a collision. */
function collides(a: string, b: string): boolean {
  const d = Math.abs(hue(a) - hue(b)) % 360;
  return Math.min(d, 360 - d) < 25;
}

function hue(hex: string): number {
  const h = hex.replace("#", "");
  const lin = [0, 2, 4].map((i) => {
    const c = parseInt(h.slice(i, i + 2), 16) / 255;
    return c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
  });
  const [r, g, bl] = lin;
  const cb = (v: number) => (v > 0 ? Math.cbrt(v) : -Math.cbrt(-v));
  const l = cb(0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * bl);
  const m = cb(0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * bl);
  const s = cb(0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * bl);
  const A = 1.9779984951 * l - 2.428592205 * m + 0.4505937099 * s;
  const B = 0.0259040371 * l + 0.7827717662 * m - 0.808675766 * s;
  return ((Math.atan2(B, A) * 180) / Math.PI + 360) % 360;
}
