import {
  PolarAngleAxis, PolarGrid, Radar, RadarChart, ResponsiveContainer,
} from "recharts";

export interface FingerprintPoint { metric: string; pct: number | null }

export default function FingerprintRadar({ data, height = 280 }:
  { data: FingerprintPoint[]; height?: number }) {
  return (
    <div style={{ filter: "drop-shadow(0 0 6px var(--accent-glow))" }}>
      <ResponsiveContainer width="100%" height={height}>
        <RadarChart data={data.filter((f) => f.pct != null)}>
          <PolarGrid stroke="var(--stroke)" />
          <PolarAngleAxis dataKey="metric"
                          tick={{ fill: "var(--muted)", fontSize: 11 }} />
          <Radar dataKey="pct" stroke="var(--accent)"
                 fill="var(--accent)" fillOpacity={0.25} />
        </RadarChart>
      </ResponsiveContainer>
    </div>
  );
}
