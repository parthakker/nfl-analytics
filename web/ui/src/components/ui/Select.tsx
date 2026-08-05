interface Props {
  value: string | number;
  onChange: (v: string) => void;
  options: { value: string | number; label: string }[];
  label?: string;
  size?: "sm" | "md";
  ariaLabel?: string;
  className?: string;
}

/** Wraps a NATIVE <select> — the e2e suite drives these with
 *  selectOption(), and native pickers are better on touch anyway.
 *  Option colours come from styles/base.css, which is what retired the
 *  old per-site style={{color:"#000"}} workaround. */
export default function Select({
  value, onChange, options, label, size = "md", ariaLabel, className = "",
}: Props) {
  const el = (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      aria-label={ariaLabel ?? label}
      className={`rounded-[var(--radius-control)] border border-border bg-surface-2 text-ink transition-colors hover:border-border-strong ${
        size === "md" ? "px-2 py-1.5 text-body" : "px-2 py-1 text-label"
      } ${className}`}
    >
      {options.map((o) => (
        <option key={o.value} value={o.value}>
          {o.label}
        </option>
      ))}
    </select>
  );

  if (!label) return el;
  return (
    <label className="flex items-center gap-1.5 text-label text-muted">
      {label}
      {el}
    </label>
  );
}
