import type { CSSProperties, ReactNode } from "react";

export default function GlassPanel({ title, children, className = "", style }: {
  title?: string;
  children: ReactNode;
  className?: string;
  style?: CSSProperties;
}) {
  return (
    <section className={`glass p-4 ${className}`} style={style}>
      {title && (
        <h3 className="mb-3 text-xs font-bold uppercase tracking-[0.14em]"
            style={{ color: "var(--muted)" }}>
          {title}
        </h3>
      )}
      {children}
    </section>
  );
}
