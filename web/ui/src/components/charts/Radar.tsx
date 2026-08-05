import {
  PolarAngleAxis, PolarGrid, PolarRadiusAxis, Radar as RRadar,
  RadarChart, ResponsiveContainer, Tooltip,
} from "recharts";
import ChartFrame from "./ChartFrame";
import { GRID, REFERENCE, seriesColor } from "./chartTheme";

export interface RadarPoint {
  metric: string;
  pct: number | null;
}

/** Percentile fingerprint. The 50th-percentile ring is drawn explicitly —
 *  without it a radar shape means nothing, since the reader has no baseline
 *  to compare the area against. */
export default function Radar({
  data, title, height = 280, name = "percentile", color,
}: {
  data: RadarPoint[];
  title?: string;
  height?: number;
  name?: string;
  color?: string;
}) {
  const rows = data.filter((d) => d.pct != null);
  const hue = color ?? seriesColor(0);

  return (
    <ChartFrame
      title={title}
      series={[{ key: "pct", name, color: hue }]}
      data={rows as unknown as Record<string, number | string | null>[]}
      xKey="metric" xLabel="metric"
      note="Ring at 50 is league average. Further out is better on every axis."
    >
      <ResponsiveContainer width="100%" height={height}>
        <RadarChart data={rows} outerRadius="72%">
          <PolarGrid stroke={GRID} />
          <PolarAngleAxis dataKey="metric" tick={{ fill: "var(--color-muted)", fontSize: 11 }} />
          <PolarRadiusAxis domain={[0, 100]} tick={false} axisLine={false} />
          <Tooltip
            cursor={false}
            content={({ active, payload }) => {
              if (!active || !payload?.length) return null;
              const p = payload[0].payload as RadarPoint;
              return (
                <div className="rounded-[var(--radius-control)] border border-border-strong bg-surface-3 px-2.5 py-1.5 text-label text-ink shadow-lg">
                  <div className="font-semibold">{p.metric}</div>
                  <div className="text-muted">
                    <span className="tabular-nums text-ink">{p.pct}</span>th percentile
                  </div>
                </div>
              );
            }} />
          <RRadar dataKey={() => 50} stroke={REFERENCE} strokeDasharray="3 3"
                  fill="none" isAnimationActive={false} />
          <RRadar dataKey="pct" name={name} stroke={hue} strokeWidth={2}
                  fill={hue} fillOpacity={0.22} />
        </RadarChart>
      </ResponsiveContainer>
    </ChartFrame>
  );
}
