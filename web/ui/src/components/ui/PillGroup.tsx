import Tip from "./Tip";

export interface PillOption {
  value: string;
  label: string;
  help?: string;
}

interface Props {
  options: PillOption[];
  value: string | string[];
  onChange: (value: string) => void;
  /** toggling the active pill clears the selection (position filters) */
  clearable?: boolean;
  size?: "sm" | "md";
  ariaLabel: string;
  className?: string;
}

/** Filter pills. Renders <button aria-pressed>, NOT role="radio" — the e2e
 *  suite locates these with getByRole("button", {name}) and radios are not
 *  buttons to the accessibility tree. */
export default function PillGroup({
  options, value, onChange, clearable, size = "md", ariaLabel, className = "",
}: Props) {
  const selected = Array.isArray(value) ? value : [value];
  const pad = size === "md" ? "px-3 py-1 text-body" : "px-2.5 py-0.5 text-label";

  return (
    <div role="group" aria-label={ariaLabel} className={`flex flex-wrap gap-1.5 ${className}`}>
      {options.map((o) => {
        const active = selected.includes(o.value);
        const btn = (
          <button
            key={o.value}
            type="button"
            aria-pressed={active}
            onClick={() => onChange(clearable && active ? "" : o.value)}
            className={`rounded-full border font-semibold transition-colors ${pad} ${
              active
                ? "border-accent/50 bg-accent-bg text-accent"
                : "border-border text-muted hover:border-border-strong hover:text-ink"
            }`}
          >
            {o.label}
          </button>
        );
        return o.help ? <Tip key={o.value} text={o.help}>{btn}</Tip> : btn;
      })}
    </div>
  );
}
