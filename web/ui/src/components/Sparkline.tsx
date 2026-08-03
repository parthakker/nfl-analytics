/* Minimal hand-rolled SVG sparkline for market cards. */
export default function Sparkline({ points, width = 96, height = 28 }: {
  points: (number | null)[];
  width?: number;
  height?: number;
}) {
  const vals = points.filter((p): p is number => p != null);
  if (vals.length < 2) return null;
  const min = Math.min(...vals);
  const max = Math.max(...vals);
  const span = max - min || 1;
  const step = width / (vals.length - 1);
  const d = vals
    .map((v, i) => `${i === 0 ? "M" : "L"}${(i * step).toFixed(1)},${(height - 3 - ((v - min) / span) * (height - 6)).toFixed(1)}`)
    .join(" ");
  return (
    <svg width={width} height={height} aria-hidden>
      <path d={d} fill="none" stroke="var(--accent)" strokeWidth="1.5"
            style={{ filter: "drop-shadow(0 0 3px var(--accent-glow))" }} />
    </svg>
  );
}
