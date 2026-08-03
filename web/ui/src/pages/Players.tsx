import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../lib/api";

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
    <div className="space-y-5">
      <h1 className="text-2xl font-bold tracking-tight">Player explorer</h1>
      <p className="text-sm" style={{ color: "var(--muted)" }}>
        Search any player since 2007 — or click a name anywhere in the app.
      </p>
      <div className="relative max-w-xl">
        <input value={q} onChange={(e) => setQ(e.target.value)}
          placeholder="search any player since 2007…"
          className="glass w-full px-4 py-3 text-sm outline-none"
          style={{ color: "var(--text)" }} />
        {hits.length > 0 && (
          <div className="glass absolute z-10 mt-1 w-full overflow-hidden">
            {hits.map((h) => (
              <button key={h.gsis_id} onClick={() => nav(`/player/${h.gsis_id}`)}
                className="block w-full px-4 py-2 text-left text-sm transition-colors hover:bg-white/10">
                <span className="font-medium">{h.name}</span>
                <span className="ml-2" style={{ color: "var(--muted)" }}>{h.pos} · {h.team}</span>
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
