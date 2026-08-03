import type { NewsItem } from "../lib/api";

export default function Ticker({ items }: { items: NewsItem[] }) {
  if (!items.length) return null;
  const row = items.slice(0, 20);
  return (
    <div className="glass overflow-hidden py-2">
      <div className="ticker-track flex gap-10 whitespace-nowrap">
        {[...row, ...row].map((n, i) => (
          <a key={i} href={n.url} target="_blank" rel="noreferrer"
             className="text-sm transition-colors hover:text-white"
             style={{ color: "var(--muted)" }}>
            <span className="mr-2" style={{ color: "var(--arc)" }}>▸</span>
            {n.headline}
          </a>
        ))}
      </div>
    </div>
  );
}
