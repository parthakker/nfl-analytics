import { useEffect, useState } from "react";
import { api, type NewsItem } from "../lib/api";
import GlassPanel from "../components/GlassPanel";
import { useMeta } from "../lib/MetaContext";

const SOURCES = [["all", "All"], ["espn", "ESPN"], ["team", "Team sites"]] as const;

export default function NewsPage() {
  const meta = useMeta();
  const [source, setSource] = useState("all");
  const [items, setItems] = useState<NewsItem[]>([]);

  useEffect(() => {
    api.news(source, 60).then((r) => setItems(r.items)).catch(console.error);
  }, [source]);

  return (
    <div className="space-y-5">
      <h1 className="text-2xl font-bold tracking-tight">League wire</h1>
      <div className="flex gap-2">
        {SOURCES.map(([k, name]) => (
          <button key={k} onClick={() => setSource(k)}
            className="rounded-full border px-3 py-1 text-sm font-semibold"
            style={{ borderColor: source === k ? "var(--arc)" : "var(--stroke)",
                     color: source === k ? "var(--arc)" : "var(--muted)" }}>
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
                    {n.ts?.slice(0, 16).replace("T", " ")} ·{" "}
                    {n.source === "team_site" ? `${code ?? ""} team site` : "ESPN"}
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
