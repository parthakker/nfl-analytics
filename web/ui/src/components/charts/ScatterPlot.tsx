import {
  CartesianGrid, ReferenceLine, ResponsiveContainer, Scatter,
  ScatterChart, Tooltip, XAxis, YAxis,
} from "recharts";
import type { ReactNode } from "react";
import ChartFrame from "./ChartFrame";
import { MAX_SCATTER_SERIES, REFERENCE, axis, grid, seriesColor } from "./chartTheme";

export interface ScatterPoint {
  x: number;
  y: number;
  label: string;
  /** per-point identity colour (team ink); overrides the series colour */
  color?: string;
  [k: string]: unknown;
}

export interface ScatterSeries {
  name: string;
  points: ScatterPoint[];
  color?: string;
}

interface Props {
  series: ScatterSeries[];
  xLabel: string;
  yLabel: string;
  title?: string;
  note?: ReactNode;
  height?: number;
  /** crosshair at the field average */
  meanX?: number | null;
  meanY?: number | null;
  onPointClick?: (p: ScatterPoint) => void;
  renderTooltip?: (p: ScatterPoint) => ReactNode;
}

/** Overlapping marks are the hardest CVD case, so this caps at three series:
 *  only the first three slots pass ALL-pairs separation, not just adjacent.
 *
 *  Marks stay a recharts <Scatter> drawing a real <circle>. A second
 *  transparent circle of r=12 sits under each one as the hit target, because
 *  a 5px dot is far below the 24px minimum for a click target. */
export default function ScatterPlot({
  series, xLabel, yLabel, title, note, height = 380,
  meanX, meanY, onPointClick, renderTooltip,
}: Props) {
  const resolved = series.slice(0, MAX_SCATTER_SERIES).map((s, i) => ({
    ...s, color: s.color ?? seriesColor(i),
  }));

  return (
    <ChartFrame title={title} note={note} series={resolved.map((s, i) => ({
      key: String(i), name: s.name, color: s.color,
    }))}>
      <ResponsiveContainer width="100%" height={height}>
        <ScatterChart margin={{ top: 10, right: 24, bottom: 24, left: 4 }}>
          <CartesianGrid {...grid} vertical />
          <XAxis type="number" dataKey="x" name={xLabel} domain={["auto", "auto"]} {...axis}
                 label={{ value: xLabel, position: "insideBottom", offset: -14,
                          fill: "var(--color-muted)", fontSize: 11 }} />
          <YAxis type="number" dataKey="y" name={yLabel} domain={["auto", "auto"]} {...axis}
                 label={{ value: yLabel, angle: -90, position: "insideLeft",
                          fill: "var(--color-muted)", fontSize: 11 }} />
          <Tooltip
            cursor={{ strokeDasharray: "3 3", stroke: "var(--color-border-strong)" }}
            content={({ active, payload }) => {
              if (!active || !payload?.length) return null;
              const p = payload[0].payload as ScatterPoint;
              return (
                <div className="rounded-[var(--radius-control)] border border-border-strong bg-surface-3 px-2.5 py-1.5 text-label text-ink shadow-lg">
                  {renderTooltip ? renderTooltip(p) : (
                    <>
                      <div className="font-semibold">{p.label}</div>
                      <div className="text-muted">{xLabel}: <span className="tabular-nums text-ink">{p.x}</span></div>
                      <div className="text-muted">{yLabel}: <span className="tabular-nums text-ink">{p.y}</span></div>
                    </>
                  )}
                </div>
              );
            }} />

          {meanX != null && <ReferenceLine x={meanX} stroke={REFERENCE} strokeDasharray="4 4" />}
          {meanY != null && <ReferenceLine y={meanY} stroke={REFERENCE} strokeDasharray="4 4" />}

          {resolved.map((s, si) => (
            <Scatter
              key={si} name={s.name} data={s.points}
              onClick={(p) => onPointClick?.(p as unknown as ScatterPoint)}
              shape={(props: { cx?: number; cy?: number; payload?: ScatterPoint }) => (
                <g style={{ cursor: onPointClick ? "pointer" : undefined }}>
                  {/* 24px hit layer: the visible dot is far too small to click */}
                  <circle cx={props.cx} cy={props.cy} r={12} fill="transparent" />
                  <circle cx={props.cx} cy={props.cy} r={5}
                          fill={props.payload?.color ?? s.color}
                          fillOpacity={0.85}
                          stroke="var(--color-surface)" strokeWidth={1.5} />
                </g>
              )} />
          ))}
        </ScatterChart>
      </ResponsiveContainer>
    </ChartFrame>
  );
}
