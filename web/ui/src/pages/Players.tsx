import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../lib/api";
import { PageHeader } from "../components/ui";

type Hit = { gsis_id: string; name: string; pos: string; team: string };

export default function Players() {
  const nav = useNavigate();
  const [q, setQ] = useState("");
  const [hits, setHits] = useState<Hit[]>([]);

  useEffect(() => {
    if (q.length < 3) { setHits([]); return; }
    const id = setTimeout(() =>
      api.playerSearch(q).then((r) => setHits(r.hits)).catch(console.error), 250);
    return () => clearTimeout(id);
  }, [q]);

  return (
    <div className="space-y-4">
      <PageHeader
        title="Player explorer"
        subtitle="Search any player since 2007 — or click a name anywhere in the app."
      />
      <div className="relative max-w-xl">
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="search any player since 2007…"
          aria-label="Search players"
          className="w-full rounded-[var(--radius-control)] border border-border bg-surface px-4 py-3 text-body text-ink outline-none transition-colors placeholder:text-faint hover:border-border-strong"
        />
        {hits.length > 0 && (
          <div className="absolute z-10 mt-1 w-full overflow-hidden rounded-[var(--radius-control)] border border-border bg-surface-2 shadow-lg">
            {hits.map((h) => (
              <button
                key={h.gsis_id}
                onClick={() => nav(`/player/${h.gsis_id}`)}
                className="block w-full px-4 py-2 text-left text-body transition-colors hover:bg-surface-3"
              >
                <span className="font-medium text-ink">{h.name}</span>
                <span className="ml-2 text-muted">{h.pos} · {h.team}</span>
              </button>
            ))}
          </div>
        )}
        {q.length >= 3 && hits.length === 0 && (
          <p className="mt-2 text-label text-muted">No player matches “{q}”.</p>
        )}
      </div>
    </div>
  );
}
