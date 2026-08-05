import type { ReactNode } from "react";

interface Props {
  children: ReactNode;
  /** right-aligned trailing slot (result count, export, density) */
  trailing?: ReactNode;
  /** sticks under the page header while a long table scrolls */
  sticky?: boolean;
  className?: string;
}

/** One row of filters above the data — never a sidebar, never a modal.
 *  Filters live in the URL; this is only their presentation. */
export default function Toolbar({ children, trailing, sticky, className = "" }: Props) {
  return (
    <div
      className={`mb-3 flex flex-wrap items-center gap-x-4 gap-y-2 rounded-[var(--radius-panel)] border border-border bg-surface px-3 py-2 ${
        sticky ? "sticky top-0 z-30" : ""
      } ${className}`}
    >
      {children}
      {trailing && <div className="ml-auto flex items-center gap-2">{trailing}</div>}
    </div>
  );
}

/** A labelled cluster inside the toolbar. Keeps the label attached to its
 *  control without every page reinventing the markup. */
export function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex items-center gap-2">
      <span className="text-micro uppercase tracking-[0.1em] text-muted">{label}</span>
      {children}
    </div>
  );
}
