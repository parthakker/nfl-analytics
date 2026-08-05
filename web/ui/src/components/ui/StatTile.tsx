import type { ReactNode } from "react";
import Tip from "./Tip";

interface Props {
  label: string;
  value: ReactNode;
  unit?: string;
  /** league rank, rendered as a muted #N beside the value */
  rank?: number | null;
  sub?: ReactNode;
  /** 0..1 — a 4px bar under the value (replaces the glowing progress ring) */
  meter?: number | null;
  tone?: "neutral" | "positive" | "negative" | "accent" | "team";
  help?: string;
}

const TONE = {
  neutral: "text-ink",
  positive: "text-positive",
  negative: "text-negative",
  accent: "text-accent",
  team: "text-team",
} as const;

/** A number that IS the chart. Value uses proportional figures — equal-width
 *  digits make large standalone numbers look loose (tabular-nums belongs in
 *  columns that align vertically, not here). */
export default function StatTile({
  label, value, unit, rank, sub, meter, tone = "neutral", help,
}: Props) {
  const body = (
    <div className="rounded-[var(--radius-panel)] border border-border bg-surface p-3">
      <div className="text-micro uppercase tracking-[0.12em] text-muted">{label}</div>
      <div className={`font-display mt-1 text-h1 font-bold ${TONE[tone]}`}>
        {value}
        {unit && <span className="ml-0.5 text-h3 text-muted">{unit}</span>}
        {rank != null && (
          <span className="ml-1.5 text-h3 font-semibold text-muted">#{rank}</span>
        )}
      </div>
      {meter != null && (
        <div className="mt-2 h-1 w-full overflow-hidden rounded-full bg-surface-3">
          <div
            className="h-full rounded-full bg-accent transition-[width] duration-700"
            style={{ width: `${Math.max(0, Math.min(1, meter)) * 100}%` }}
          />
        </div>
      )}
      {sub && <div className="mt-1 text-micro text-muted">{sub}</div>}
    </div>
  );
  return help ? <Tip text={help}>{body}</Tip> : body;
}
