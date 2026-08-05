import {
  CartesianGrid, Line, LineChart as RLineChart, ReferenceLine,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import type { ReactNode } from "react";
import ChartFrame from "./ChartFrame";
import ChartTooltip from "./ChartTooltip";
import { MAX_SERIES, REFERENCE, axis, cursor, grid, seriesColor } from "./chartTheme";

export interface LineSeries {
  key: string;
  name: string;
  /** omit to take the next fixed slot colour */
  color?: string;
}

interface Props {
  data: Record<string, number | string | null>[];
  xKey: string;
  xLabel?: string;
  series: LineSeries[];
  title?: string;
  note?: ReactNode;
  height?: number;
  /** horizontal rule (league average, break-even, 50%) */
  reference?: { y: number; label?: string };
  digits?: number;
  xTickFormatter?: (v: string | number) => string;
  actions?: ReactNode;
}

/** The house line chart. 2px strokes, no dots until hover, recessive grid,
 *  no glow — the glow was manufacturing exactly the halation the dark theme
 *  was redesigned to remove. */
export default function LineChart({
  data, xKey, xLabel, series, title, note, height = 260, reference,
  digits = 2, xTickFormatter, actions,
}: Props) {
  const resolved = series.slice(0, MAX_SERIES).map((s, i) => ({
    ...s, color: s.color ?? seriesColor(i),
  }));

  return (
    <ChartFrame title={title} note={note} series={resolved} data={data}
                xKey={xKey} xLabel={xLabel} actions={actions}>
      <ResponsiveContainer width="100%" height={height}>
        <RLineChart data={data} margin={{ top: 4, right: 12, bottom: 0, left: -18 }}>
          <CartesianGrid {...grid} />
          <XAxis dataKey={xKey} {...axis} tickFormatter={xTickFormatter} />
          <YAxis {...axis} axisLine={false} />
          <Tooltip content={<ChartTooltip digits={digits} />} cursor={cursor} />
          {reference && (
            <ReferenceLine y={reference.y} stroke={REFERENCE} strokeDasharray="4 4"
                           label={reference.label
                             ? { value: reference.label, fill: "var(--color-muted)", fontSize: 10, position: "right" }
                             : undefined} />
          )}
          {resolved.map((s) => (
            <Line key={s.key} dataKey={s.key} name={s.name} type="monotone"
                  stroke={s.color} strokeWidth={2} dot={false}
                  activeDot={{ r: 4, strokeWidth: 0 }} connectNulls />
          ))}
        </RLineChart>
      </ResponsiveContainer>
    </ChartFrame>
  );
}
