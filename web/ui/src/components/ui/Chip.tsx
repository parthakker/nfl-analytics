import type { ReactNode } from "react";

/** "hot" | "arc" | "muted" are the legacy tones, accepted so existing call
 *  sites keep working during the migration. TODO(wave 8): drop them. */
export type ChipTone =
  | "neutral" | "accent" | "positive" | "negative" | "warning" | "team"
  | "hot" | "arc" | "muted";

const TONE: Record<ChipTone, string> = {
  neutral: "text-muted border-border",
  accent: "text-accent border-accent/40 bg-accent-bg",
  positive: "text-positive border-positive/40",
  negative: "text-negative border-negative/40",
  warning: "text-warning border-warning/40",
  team: "text-team border-team",
  // legacy aliases
  hot: "text-warning border-warning/40",
  arc: "text-accent border-accent/40 bg-accent-bg",
  muted: "text-muted border-border",
};

export default function Chip({
  children, tone = "neutral", size = "sm", icon,
}: {
  children: ReactNode;
  tone?: ChipTone;
  size?: "sm" | "md";
  icon?: ReactNode;
}) {
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-[var(--radius-chip)] border ${
        size === "md" ? "px-2.5 py-1 text-label" : "px-2 py-0.5 text-micro"
      } ${TONE[tone]}`}
    >
      {icon}
      {children}
    </span>
  );
}
