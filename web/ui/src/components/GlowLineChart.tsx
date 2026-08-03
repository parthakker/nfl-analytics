import {
  CartesianGrid, Legend, Line, LineChart, ResponsiveContainer,
  Tooltip, XAxis, YAxis,
} from "recharts";

/* House chart style (dataviz): thin 2px lines, recessive grid/axes, top
   legend for the two series, hover tooltip, glow via CSS drop-shadow. */
export default function GlowLineChart({ data, xKey, series }: {
  data: Record<string, number | string | null>[];
  xKey: string;
  series: { key: string; name: string; color: string }[];
}) {
  return (
    <div style={{ filter: "drop-shadow(0 0 5px var(--accent-glow))" }}>
      <ResponsiveContainer width="100%" height={260}>
        <LineChart data={data} margin={{ top: 4, right: 12, bottom: 0, left: -18 }}>
          <CartesianGrid stroke="var(--stroke)" vertical={false} />
          <XAxis dataKey={xKey} tick={{ fill: "var(--muted)", fontSize: 11 }}
                 axisLine={{ stroke: "var(--stroke)" }} tickLine={false} />
          <YAxis tick={{ fill: "var(--muted)", fontSize: 11 }}
                 axisLine={false} tickLine={false} />
          <Tooltip
            contentStyle={{ background: "var(--bg-1)", border: "1px solid var(--stroke)",
                            borderRadius: 10, color: "var(--text)", fontSize: 12 }}
            labelStyle={{ color: "var(--muted)" }} />
          <Legend verticalAlign="top" height={28}
                  formatter={(v) => <span style={{ color: "var(--text)", fontSize: 12 }}>{v}</span>} />
          {series.map((s) => (
            <Line key={s.key} dataKey={s.key} name={s.name} type="monotone"
                  stroke={s.color} strokeWidth={2} dot={false}
                  activeDot={{ r: 4 }} connectNulls />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
