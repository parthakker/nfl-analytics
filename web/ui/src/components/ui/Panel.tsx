import type { CSSProperties, ReactNode } from "react";

interface Props {
  title?: string;
  /** right-aligned controls in the header row */
  actions?: ReactNode;
  /** muted line under the title — the place for qualification notes, caveats */
  note?: ReactNode;
  /** no padding: for a DataTable that owns its own edges */
  flush?: boolean;
  span?: 1 | 2 | 3;
  className?: string;
  style?: CSSProperties;
  children: ReactNode;
}

const SPAN = { 1: "", 2: "lg:col-span-2", 3: "lg:col-span-3" } as const;

/** The universal surface. Replaces GlassPanel: flat fill + hairline border,
 *  no blur, no glow — blur behind a scrolling stat table is noise. */
export default function Panel({
  title, actions, note, flush, span = 1, className = "", style, children,
}: Props) {
  return (
    <section
      className={`rounded-[var(--radius-panel)] border border-border bg-surface ${
        flush ? "" : "p-4"
      } ${SPAN[span]} ${className}`}
      style={style}
    >
      {(title || actions) && (
        <header
          className={`flex items-center gap-3 ${flush ? "px-4 pt-4" : ""} ${
            note ? "mb-1" : "mb-3"
          }`}
        >
          {title && (
            <h3 className="text-label font-semibold uppercase tracking-[0.12em] text-muted">
              {title}
            </h3>
          )}
          {actions && <div className="ml-auto flex items-center gap-2">{actions}</div>}
        </header>
      )}
      {note && (
        <p className={`mb-3 text-micro text-muted ${flush ? "px-4" : ""}`}>{note}</p>
      )}
      {children}
    </section>
  );
}
