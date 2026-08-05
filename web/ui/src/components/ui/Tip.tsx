import { useId } from "react";
import type { ReactNode } from "react";

/** Pure-CSS hover tooltip. Also fires on keyboard focus and exposes the text
 *  via aria-describedby, so the explanation is not mouse-only. */
export default function Tip({ text, children }: { text: string; children: ReactNode }) {
  const id = useId();
  return (
    <span className="group relative inline-block" title={text} aria-describedby={id}>
      {children}
      <span
        id={id}
        role="tooltip"
        className="pointer-events-none absolute left-1/2 top-full z-50 mt-1 hidden w-max max-w-56 -translate-x-1/2 rounded-[var(--radius-control)] border border-border-strong bg-surface-3 px-2.5 py-1.5 text-left text-micro font-normal normal-case leading-snug text-ink shadow-lg group-hover:block group-focus-within:block"
      >
        {text}
      </span>
    </span>
  );
}
