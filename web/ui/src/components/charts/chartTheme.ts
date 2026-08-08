/* One chart configuration for the whole app.
 *
 * Before this file there were three unrelated recharts setups with two
 * different tooltips, and every chart carried a drop-shadow glow. The rules
 * below come from the dataviz procedure:
 *
 *  - categorical hues are assigned in FIXED SLOT ORDER and never cycled; a
 *    9th series folds into "other" or becomes small multiples
 *  - the first three slots are the only trio that passes all-pairs CVD
 *    separation, so scatter caps at 3
 *  - --color-chart-ref is a reference line, never a data series
 *  - grid and axes are recessive; the data is the only bright thing
 */

/** Fixed slot order. Index by series position, never by rank or by hash. */
export const SERIES = [
  "var(--color-chart-1)", "var(--color-chart-2)", "var(--color-chart-3)",
  "var(--color-chart-4)", "var(--color-chart-5)", "var(--color-chart-6)",
  "var(--color-chart-7)", "var(--color-chart-8)",
] as const;

export const MAX_SERIES = SERIES.length;
/** Scatter overlays marks, so it needs the stricter all-pairs-safe trio. */
export const MAX_SCATTER_SERIES = 3;

export const REFERENCE = "var(--color-chart-ref)";
export const GRID = "var(--color-chart-grid)";

/** Slot i's hue. Out-of-range clamps to the last slot instead of cycling —
 *  wrapping around would silently hand slot 9 the colour of slot 1 and break
 *  the fixed-slot rule above. Callers cap series counts (MAX_SERIES /
 *  MAX_SCATTER_SERIES) before ever indexing past the end. */
export const seriesColor = (i: number) =>
  SERIES[Math.min(Math.max(i, 0), SERIES.length - 1)];

export const axis = {
  tick: { fill: "var(--color-muted)", fontSize: 11 },
  axisLine: { stroke: GRID },
  tickLine: false,
} as const;

export const grid = { stroke: GRID, vertical: false } as const;

/** Shared by every chart's <Tooltip cursor>. */
export const cursor = { stroke: "var(--color-border-strong)", strokeWidth: 1 } as const;

/** A number the reader will compare against another number on the same axis. */
export const fmt = (v: number | string | null | undefined, digits = 2): string => {
  if (v == null) return "—";
  if (typeof v === "string") return v;
  return Number.isInteger(v) ? String(v) : v.toFixed(digits);
};
