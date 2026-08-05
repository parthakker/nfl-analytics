import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMeta } from "../lib/MetaContext";
import { useChat } from "../lib/ChatContext";
import { api } from "../lib/api";
import { useDensity, type Density } from "../lib/useDensity";

interface Item {
  id: string;
  label: string;
  hint?: string;
  group: string;
  icon?: string;
  run: () => void;
}

const PAGES: { label: string; path: string; hint: string }[] = [
  { label: "Today", path: "/", hint: "league overview and week 1 lines" },
  { label: "Scores & schedule", path: "/scores", hint: "every game with its closing market" },
  { label: "Teams & standings", path: "/teams", hint: "records, scoring, differential" },
  { label: "Players", path: "/players", hint: "search any player since 2007" },
  { label: "Stat leaders", path: "/leaders", hint: "league leaders by stat family" },
  { label: "Betting board", path: "/betting", hint: "Vegas vs Kalshi, dislocations" },
  { label: "Prediction markets", path: "/markets", hint: "live Kalshi prices" },
  { label: "Learn", path: "/knowledge", hint: "the NFL knowledge book" },
  { label: "Coaches", path: "/coaches", hint: "head coaches and coordinators" },
  { label: "Referees", path: "/refs", hint: "crew tendencies and bias" },
  { label: "Head-to-head", path: "/h2h", hint: "any two franchises, every meeting" },
  { label: "News", path: "/news", hint: "the league wire" },
];

/** Ctrl-K. Three modes so one keystroke covers navigate / do / ask:
 *    (nothing)  jump to a page, team or player
 *    >          run a command
 *    ?          hand the rest of the line to the analyst
 *
 *  This is the one place a blur material is still justified — see the scrim.
 */
export default function CommandPalette({ open, onClose }: {
  open: boolean;
  onClose: () => void;
}) {
  const nav = useNavigate();
  const meta = useMeta();
  const chat = useChat();
  const [, setDensity] = useDensity();
  const [q, setQ] = useState("");
  const [cursor, setCursor] = useState(0);
  const [players, setPlayers] = useState<{ gsis_id: string; name: string; pos: string; team: string }[]>([]);
  const listRef = useRef<HTMLDivElement>(null);

  useEffect(() => { if (open) { setQ(""); setCursor(0); setPlayers([]); } }, [open]);

  const mode = q.startsWith(">") ? "command" : q.startsWith("?") ? "ask" : "search";
  const term = mode === "search" ? q.trim() : q.slice(1).trim();

  // player search is the only remote lookup; pages and teams are local
  useEffect(() => {
    if (mode !== "search" || term.length < 3) { setPlayers([]); return; }
    const id = setTimeout(() => {
      api.playerSearch(term).then((r) => setPlayers(r.hits.slice(0, 5))).catch(() => setPlayers([]));
    }, 200);
    return () => clearTimeout(id);
  }, [term, mode]);

  const items = useMemo<Item[]>(() => {
    const go = (path: string) => () => { nav(path); onClose(); };
    const match = (s: string) => s.toLowerCase().includes(term.toLowerCase());

    if (mode === "ask") {
      return [{
        id: "ask", group: "Analyst", icon: "◉",
        label: term ? `Ask the analyst: “${term}”` : "Ask the analyst…",
        hint: "runs real warehouse queries — 20–60s",
        run: () => { onClose(); chat.open(); },
      }];
    }

    if (mode === "command") {
      const cmds: Item[] = [
        { id: "c-ask", group: "Commands", icon: "◉", label: "Ask the analyst",
          hint: "opens the chat", run: () => { onClose(); chat.open(); } },
        ...(["compact", "default", "comfortable"] as Density[]).map((d) => ({
          id: `c-den-${d}`, group: "Commands", icon: "▤",
          label: `Density: ${d}`, hint: "table row height",
          run: () => { setDensity(d); onClose(); },
        })),
        { id: "c-top", group: "Commands", icon: "↑", label: "Scroll to top",
          run: () => { window.scrollTo({ top: 0, behavior: "smooth" }); onClose(); } },
      ];
      return cmds.filter((c) => !term || match(c.label));
    }

    const out: Item[] = [];
    for (const p of PAGES) {
      if (!term || match(p.label) || match(p.hint)) {
        out.push({ id: `p-${p.path}`, group: "Go to", label: p.label, hint: p.hint, run: go(p.path) });
      }
    }
    if (meta && term) {
      for (const [code, t] of Object.entries(meta.teams)) {
        if (match(code) || match(t.name)) {
          out.push({ id: `t-${code}`, group: "Teams", label: t.name, hint: code, run: go(`/team/${code}`) });
        }
      }
    }
    for (const pl of players) {
      out.push({
        id: `pl-${pl.gsis_id}`, group: "Players", label: pl.name,
        hint: `${pl.pos} · ${pl.team}`, run: go(`/player/${pl.gsis_id}`),
      });
    }
    if (term) {
      out.push({
        id: "ask-fallback", group: "Analyst", icon: "◉",
        label: `Ask the analyst: “${term}”`,
        hint: "when the answer needs a real query",
        run: () => { onClose(); chat.open(); },
      });
    }
    return out.slice(0, 24);
  }, [mode, term, meta, players, nav, onClose, chat, setDensity]);

  useEffect(() => { setCursor((c) => Math.min(c, Math.max(0, items.length - 1))); }, [items.length]);

  if (!open) return null;

  const onKey = (e: React.KeyboardEvent) => {
    if (e.key === "ArrowDown") { e.preventDefault(); setCursor((c) => Math.min(c + 1, items.length - 1)); }
    else if (e.key === "ArrowUp") { e.preventDefault(); setCursor((c) => Math.max(c - 1, 0)); }
    else if (e.key === "Enter") { e.preventDefault(); items[cursor]?.run(); }
    else if (e.key === "Escape") { e.preventDefault(); onClose(); }
  };

  let lastGroup = "";

  return (
    // token-ok: a modal scrim is the one legitimate blur material left — it
    // separates a transient overlay from the page, and nothing underneath is
    // meant to be read through it.
    <div className="fixed inset-0 z-50 flex items-start justify-center bg-canvas/70 p-4 pt-24 backdrop-blur-sm"
         onClick={onClose}>
      <div role="dialog" aria-modal="true" aria-label="Command palette"
           className="w-full max-w-xl overflow-hidden rounded-[var(--radius-panel)] border border-border-strong bg-surface shadow-2xl"
           onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center gap-2 border-b border-border px-3">
          <span className="text-muted">{mode === "command" ? ">" : mode === "ask" ? "◉" : "⌕"}</span>
          <input
            autoFocus
            value={q}
            onChange={(e) => { setQ(e.target.value); setCursor(0); }}
            onKeyDown={onKey}
            aria-label="Search pages, teams and players"
            placeholder="Jump to a page, team or player…   › for commands   ? to ask"
            className="flex-1 bg-transparent py-3 text-body text-ink outline-none placeholder:text-faint" />
          <kbd className="rounded-[var(--radius-chip)] border border-border px-1.5 py-0.5 text-micro text-muted">esc</kbd>
        </div>

        <div ref={listRef} className="max-h-80 overflow-y-auto py-1">
          {items.length === 0 && (
            <p className="px-4 py-6 text-center text-body text-muted">
              Nothing matches. Press <kbd className="text-ink">?</kbd> to ask the analyst instead.
            </p>
          )}
          {items.map((it, i) => {
            const header = it.group !== lastGroup ? it.group : null;
            lastGroup = it.group;
            return (
              <div key={it.id}>
                {header && (
                  <div className="px-3 pb-1 pt-2 text-micro font-semibold uppercase tracking-[0.12em] text-faint">
                    {header}
                  </div>
                )}
                <button
                  type="button"
                  onMouseEnter={() => setCursor(i)}
                  onClick={it.run}
                  aria-selected={i === cursor}
                  className={`flex w-full items-center gap-2 px-3 py-2 text-left text-body ${
                    i === cursor ? "bg-accent-bg text-accent" : "text-ink hover:bg-surface-2"}`}
                >
                  {it.icon && <span aria-hidden>{it.icon}</span>}
                  <span className="font-medium">{it.label}</span>
                  {it.hint && <span className="ml-auto truncate pl-4 text-micro text-muted">{it.hint}</span>}
                </button>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
