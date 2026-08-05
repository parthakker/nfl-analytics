import type { NewsItem } from "../lib/api";

export default function Ticker({ items }: { items: NewsItem[] }) {
  if (!items.length) return null;
  const row = items.slice(0, 20);
  return (
    <div className="rounded-[var(--radius-panel)] border border-border bg-surface overflow-hidden py-2">
      <div className="ticker-track flex gap-10 whitespace-nowrap">
        {[...row, ...row].map((n, i) => (
          <a key={i} href={n.url} target="_blank" rel="noreferrer"
             className="text-sm transition-colors hover:text-accent"
             style={{ color: "var(--color-muted)" }}>
            <span className="mr-2" style={{ color: "var(--color-accent)" }}>▸</span>
            {n.headline}
          </a>
        ))}
      </div>
    </div>
  );
}
