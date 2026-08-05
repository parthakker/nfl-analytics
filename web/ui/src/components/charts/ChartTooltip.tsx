import { fmt } from "./chartTheme";

interface Item {
  name?: string | number;
  value?: number | string;
  color?: string;
  dataKey?: string | number;
}

/** The app's one tooltip. A colored swatch carries series identity; the text
 *  itself stays in ink tokens, so the label never has to be read as color. */
export default function ChartTooltip({
  active, payload, label, labelFormatter, digits = 2,
}: {
  active?: boolean;
  payload?: Item[];
  label?: string | number;
  labelFormatter?: (l: string | number) => string;
  digits?: number;
}) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-[var(--radius-control)] border border-border-strong bg-surface-3 px-2.5 py-1.5 text-label shadow-lg">
      {label != null && (
        <div className="mb-1 font-semibold text-muted">
          {labelFormatter ? labelFormatter(label) : label}
        </div>
      )}
      {payload.map((p, i) => (
        <div key={i} className="flex items-center gap-2 whitespace-nowrap text-ink">
          <span className="h-2 w-2 shrink-0 rounded-full" style={{ background: p.color }} />
          <span className="text-muted">{p.name ?? p.dataKey}</span>
          <span className="ml-auto pl-3 font-semibold tabular-nums">
            {fmt(p.value as number, digits)}
          </span>
        </div>
      ))}
    </div>
  );
}
