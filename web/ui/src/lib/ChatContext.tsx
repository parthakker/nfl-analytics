import {
  createContext, useContext, useEffect, useRef, useState, type ReactNode,
} from "react";
import { streamChat } from "./useChatStream";

interface Msg { role: "user" | "assistant"; text: string }

interface ChatCtl {
  open: () => void;
  close: () => void;
  isOpen: boolean;
}

const Ctx = createContext<ChatCtl>({ open: () => {}, close: () => {}, isOpen: false });
export function useChat(): ChatCtl { return useContext(Ctx); }

function ThinkingHUD({ hint, startedAt }: { hint: string; startedAt: number }) {
  const [, tick] = useState(0);
  useEffect(() => {
    const id = setInterval(() => tick((v) => v + 1), 1000);
    return () => clearInterval(id);
  }, []);
  const secs = Math.floor((Date.now() - startedAt) / 1000);
  return (
    <div className="flex items-center gap-3 text-sm" style={{ color: "var(--muted)" }}>
      <span className="pulse text-base" style={{ color: "var(--arc)" }}>◉</span>
      <span>{hint}</span>
      <span className="ml-auto tabular-nums">{secs}s</span>
    </div>
  );
}

export function ChatProvider({ children }: { children: ReactNode }) {
  const [isOpen, setOpen] = useState(false);
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [hint, setHint] = useState("connecting to the analyst…");
  const [startedAt, setStartedAt] = useState(0);
  const listRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setOpen((v) => !v);
      }
      if (e.key === "Escape") setOpen(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  useEffect(() => {
    listRef.current?.scrollTo({ top: listRef.current.scrollHeight });
  }, [msgs, busy]);

  const send = async () => {
    const q = draft.trim();
    if (!q || busy) return;
    setDraft("");
    setBusy(true);
    setHint("connecting to the analyst…");
    setStartedAt(Date.now());
    setMsgs((m) => [...m, { role: "user", text: q }, { role: "assistant", text: "" }]);
    const sid = sessionStorage.getItem("chat_session");

    const appendToLast = (t: string) =>
      setMsgs((m) => {
        const copy = [...m];
        copy[copy.length - 1] = { role: "assistant", text: copy[copy.length - 1].text + t };
        return copy;
      });
    const setLast = (t: string) =>
      setMsgs((m) => {
        const copy = [...m];
        copy[copy.length - 1] = { role: "assistant", text: t };
        return copy;
      });

    try {
      await streamChat(q, sid, {
        onSession: (id) => sessionStorage.setItem("chat_session", id),
        onToken: (t) => appendToLast(t),
        onTool: (h) => setHint(`${h}…`),
        onDone: (full, id) => {
          if (full) setLast(full);
          if (id) sessionStorage.setItem("chat_session", id);
        },
        onError: (e) => setLast(`⚠ ${e}`),
      });
    } catch (e) {
      setLast(`⚠ ${String(e)}`);
    } finally {
      setBusy(false);
    }
  };

  const newConversation = () => {
    sessionStorage.removeItem("chat_session");
    setMsgs([]);
  };

  return (
    <Ctx.Provider value={{ open: () => setOpen(true), close: () => setOpen(false), isOpen }}>
      {children}
      {isOpen && (
        <div className="fixed inset-0 z-50 flex items-start justify-center bg-black/60 p-4 pt-16 backdrop-blur-sm"
             onClick={() => setOpen(false)}>
          <div className="glass flex max-h-[80vh] w-full max-w-3xl flex-col p-5"
               onClick={(e) => e.stopPropagation()}>
            <div className="mb-3 flex items-center gap-3">
              <span className="glow-text font-bold" style={{ color: "var(--arc)" }}>
                ◉ ANALYST LINK
              </span>
              <button onClick={newConversation}
                className="ml-auto rounded-lg border px-2.5 py-1 text-xs transition-colors hover:bg-white/5"
                style={{ borderColor: "var(--stroke)", color: "var(--muted)" }}>
                new conversation
              </button>
              <button onClick={() => setOpen(false)}
                className="rounded-lg border px-2.5 py-1 text-xs transition-colors hover:bg-white/5"
                style={{ borderColor: "var(--stroke)", color: "var(--muted)" }}>
                esc
              </button>
            </div>

            <div ref={listRef} className="min-h-40 flex-1 space-y-4 overflow-y-auto pr-2">
              {msgs.length === 0 && (
                <p className="text-sm" style={{ color: "var(--muted)" }}>
                  Direct line to your NFL analyst — full access to the warehouse,
                  news, and market tracker. Answers take 20–60 seconds because it
                  runs real queries. Try: <em>"Who led the league in rushing in 2025?"</em>
                </p>
              )}
              {msgs.map((m, i) => (
                <div key={i} className={m.role === "user" ? "text-right" : ""}>
                  <div className={`inline-block max-w-[85%] whitespace-pre-wrap rounded-2xl px-4 py-2.5 text-left text-sm leading-relaxed ${
                    m.role === "user" ? "bg-white/10" : "glass"}`}>
                    {m.text || (busy && i === msgs.length - 1 ? "…" : "")}
                  </div>
                </div>
              ))}
              {busy && <ThinkingHUD hint={hint} startedAt={startedAt} />}
            </div>

            <div className="mt-4 flex items-center gap-2">
              <input value={draft} onChange={(e) => setDraft(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && send()}
                disabled={busy} autoFocus
                placeholder={busy ? "analyzing…" : "ask about any team, player, game, or market"}
                className="flex-1 rounded-xl border bg-transparent px-4 py-2.5 text-sm outline-none transition-shadow focus:shadow-[0_0_20px_-4px_var(--accent-glow)]"
                style={{ borderColor: "var(--stroke)", color: "var(--text)" }} />
              <button onClick={send} disabled={busy || !draft.trim()}
                className="rounded-xl border px-4 py-2.5 text-sm font-semibold transition-colors hover:bg-white/5 disabled:opacity-40"
                style={{ borderColor: "var(--stroke)", color: "var(--arc)" }}>
                send
              </button>
              {/* reserved: mic button slot (voice phase) */}
            </div>
          </div>
        </div>
      )}
    </Ctx.Provider>
  );
}
