import { useEffect, useState } from "react";
import GlassPanel from "../components/GlassPanel";
import { useMeta } from "../lib/MetaContext";

interface Item {
  ts: string | null; source: string; category?: string;
  teams?: string[]; headline: string; url: string; score?: number;
}

const SOURCES = [["all", "All"], ["espn", "ESPN"], ["team", "Team sites"],
                 ["wire", "PFT + Yahoo"]] as const;
const CATS = [["", "Everything"], ["injury", "Injuries"],
              ["trade-signing", "Trades & signings"], ["depth-chart", "Depth chart"],
              ["legal", "Legal"]] as const;

const SRC_LABEL: Record<string, string> = {
  espn_news: "ESPN", espn_injuries: "ESPN inj", team_site: "team site",
  pft: "PFT", yahoo: "Yahoo",
};

export default function NewsPage() {
  const meta = useMeta();
  const [source, setSource] = useState("all");
  const [cat, setCat] = useState("");
  const [q, setQ] = useState("");
  const [items, setItems] = useState<Item[]>([]);
  const [searching, setSearching] = useState(false);

  useEffect(() => {
    if (searching) return;
    fetch(`/api/news?source=${source}&category=${cat}&limit=60`)
      .then((r) => r.json()).then((r) => setItems(r.items)).catch(console.error);
  }, [source, cat, searching]);

  const runSearch = () => {
    if (!q.trim()) { setSearching(false); return; }
    setSearching(true);
    fetch(`/api/news/search?q=${encodeURIComponent(q)}`)
      .then((r) => r.json()).then((r) => setItems(r.items)).catch(console.error);
  };

  return (
    <div className="space-y-5">
      <h1 className="text-2xl font-bold tracking-tight">League wire</h1>

      <div className="flex flex-wrap items-center gap-2">
        <input value={q} onChange={(e) => setQ(e.target.value)}
               onKeyDown={(e) => e.key === "Enter" && runSearch()}
               placeholder="search all stored news… (e.g. Gibbs hamstring)"
               className="glass w-72 px-3 py-2 text-sm outline-none" />
        <button onClick={runSearch}
                className="rounded-lg border px-3 py-2 text-sm font-semibold"
                style={{ borderColor: "var(--stroke)", color: "var(--arc)" }}>
          search
        </button>
        {searching && (
          <button onClick={() => { setQ(""); setSearching(false); }}
                  className="text-xs underline" style={{ color: "var(--muted)" }}>
            clear search
          </button>
        )}
        <span className="mx-2 h-5 w-px" style={{ background: "var(--stroke)" }} />
        {SOURCES.map(([k, name]) => (
          <button key={k} onClick={() => { setSource(k); setSearching(false); }}
            className="rounded-full border px-3 py-1 text-sm font-semibold"
            style={{ borderColor: source === k && !searching ? "var(--arc)" : "var(--stroke)",
                     color: source === k && !searching ? "var(--arc)" : "var(--muted)" }}>
            {name}
          </button>
        ))}
      </div>
      <div className="flex flex-wrap gap-2">
        {CATS.map(([k, name]) => (
          <button key={k} onClick={() => { setCat(k); setSearching(false); }}
            className="rounded-full border px-2.5 py-0.5 text-xs font-semibold"
            style={{ borderColor: cat === k && !searching ? "var(--arc)" : "var(--stroke)",
                     color: cat === k && !searching ? "var(--arc)" : "var(--muted)" }}>
            {name}
          </button>
        ))}
      </div>

      <GlassPanel>
        <ul className="space-y-4">
          {items.map((n, i) => {
            const code = n.teams?.[0];
            const logo = code && meta?.teams[code]?.logo;
            return (
              <li key={i} className="flex items-start gap-3">
                {logo
                  ? <img src={logo} alt="" className="mt-0.5 h-6 w-6" />
                  : <span className="mt-0.5 w-6 text-center" style={{ color: "var(--arc)" }}>▸</span>}
                <div>
                  <a href={n.url} target="_blank" rel="noreferrer"
                     className="text-sm font-medium hover:text-white">{n.headline}</a>
                  <div className="text-xs" style={{ color: "var(--muted)" }}>
                    {n.ts?.slice(0, 16).replace("T", " ")} · {SRC_LABEL[n.source] ?? n.source}
                    {n.category && n.category !== "general" && (
                      <span className="ml-2 rounded-full border px-1.5 py-0.5 text-[10px]"
                            style={{ borderColor: "var(--stroke)", color: "var(--arc)" }}>
                        {n.category}
                      </span>
                    )}
                  </div>
                </div>
              </li>
            );
          })}
        </ul>
      </GlassPanel>
    </div>
  );
}
