import type { ReactNode } from "react";
import { Link } from "react-router-dom";

interface Props {
  /** breadcrumb trail; the last entry is the current page and is not linked */
  crumbs?: { label: string; to?: string }[];
  title: ReactNode;
  subtitle?: ReactNode;
  /** logo / headshot to the left of the title */
  media?: ReactNode;
  /** right-aligned: season select, view toggles */
  actions?: ReactNode;
  /** chips under the subtitle */
  meta?: ReactNode;
}

/** Every page opens the same way, so "where am I" never has to be re-learned. */
export default function PageHeader({
  crumbs, title, subtitle, media, actions, meta,
}: Props) {
  return (
    <header className="mb-4">
      {crumbs && crumbs.length > 0 && (
        <nav aria-label="Breadcrumb" className="mb-1.5 flex flex-wrap items-center gap-1 text-micro text-muted">
          {crumbs.map((c, i) => (
            <span key={`${c.label}-${i}`} className="flex items-center gap-1">
              {i > 0 && <span className="text-faint">/</span>}
              {c.to ? (
                <Link to={c.to} className="hover:text-ink">{c.label}</Link>
              ) : (
                <span className="text-ink">{c.label}</span>
              )}
            </span>
          ))}
        </nav>
      )}
      <div className="flex flex-wrap items-center gap-3">
        {media}
        <div className="min-w-0">
          <h1 className="font-display truncate text-h1 font-bold text-ink">{title}</h1>
          {subtitle && <p className="mt-0.5 text-body text-muted">{subtitle}</p>}
        </div>
        {actions && <div className="ml-auto flex flex-wrap items-center gap-2">{actions}</div>}
      </div>
      {meta && <div className="mt-2 flex flex-wrap items-center gap-1.5">{meta}</div>}
    </header>
  );
}
