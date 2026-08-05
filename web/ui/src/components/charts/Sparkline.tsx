/** Inline trend for a market card. Detoxed: no glow filter, and the last
 *  point is marked so "where does it end up" does not need a hover. */
export default function Sparkline({
  points, width = 96, height = 28, color = "var(--color-chart-1)", label,
}: {
  points: (number | null)[];
  width?: number;
  height?: number;
  color?: string;
  label?: string;
}) {
  const vals = points.filter((p): p is number => p != null);
  if (vals.length < 2) return null;

  const min = Math.min(...vals);
  const max = Math.max(...vals);
  const span = max - min || 1;
  const step = width / (vals.length - 1);
  const y = (v: number) => height - 3 - ((v - min) / span) * (height - 6);
  const d = vals
    .map((v, i) => `${i === 0 ? "M" : "L"}${(i * step).toFixed(1)},${y(v).toFixed(1)}`)
    .join(" ");

  return (
    <svg width={width} height={height} role="img"
         aria-label={label ?? `trend from ${vals[0]} to ${vals[vals.length - 1]}`}>
      <path d={d} fill="none" stroke={color} strokeWidth="1.5"
            strokeLinecap="round" strokeLinejoin="round" />
      <circle cx={width} cy={y(vals[vals.length - 1])} r="2" fill={color} />
    </svg>
  );
}
