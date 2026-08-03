/* SVG progress ring: `fraction` fills the arc (0..1), `value` is the label. */
export default function StatRing({ value, label, fraction, sub }: {
  value: string;
  label: string;
  fraction: number; // 0..1
  sub?: string;
}) {
  const R = 34;
  const C = 2 * Math.PI * R;
  const filled = C * Math.min(1, Math.max(0, fraction));
  return (
    <div className="flex flex-col items-center gap-1">
      <div className="relative h-24 w-24">
        <svg viewBox="0 0 84 84" className="h-full w-full -rotate-90">
          <circle cx="42" cy="42" r={R} fill="none" strokeWidth="5"
                  stroke="var(--stroke)" />
          <circle cx="42" cy="42" r={R} fill="none" strokeWidth="5"
                  strokeLinecap="round" stroke="var(--accent)"
                  strokeDasharray={`${filled} ${C - filled}`}
                  style={{ filter: "drop-shadow(0 0 6px var(--accent-glow))",
                           transition: "stroke-dasharray 900ms ease" }} />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="text-lg font-bold tabular-nums">{value}</span>
          {sub && <span className="text-[10px]" style={{ color: "var(--muted)" }}>{sub}</span>}
        </div>
      </div>
      <span className="text-[10px] font-semibold uppercase tracking-widest"
            style={{ color: "var(--muted)" }}>
        {label}
      </span>
    </div>
  );
}
