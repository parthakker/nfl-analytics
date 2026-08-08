import {
  createContext, useContext, useEffect, useRef, useState, type ReactNode,
} from "react";
import { streamChat } from "./useChatStream";

interface Msg { role: "user" | "assistant"; text: string }

interface ChatCtl {
  open: () => void;
  close: () => void;
  /** Open the chat and submit `question` through the normal send path.
   *  If a reply is already streaming, the question lands in the draft box. */
  ask: (question: string) => void;
  isOpen: boolean;
}

const Ctx = createContext<ChatCtl>({
  open: () => {}, close: () => {}, ask: () => {}, isOpen: false,
});
export function useChat(): ChatCtl { return useContext(Ctx); }

function ThinkingHUD({ hint, startedAt }: { hint: string; startedAt: number }) {
  const [, tick] = useState(0);
  useEffect(() => {
    const id = setInterval(() => tick((v) => v + 1), 1000);
    return () => clearInterval(id);
  }, []);
  const secs = Math.floor((Date.now() - startedAt) / 1000);
  return (
    <div className="flex items-center gap-3 text-body text-muted">
      <span className="pulse text-accent">◉</span>
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
  const boxRef = useRef<HTMLDivElement>(null);

  // The overlay is modal, so Tab must cycle inside it rather than reach the
  // page underneath.
  const trapTab = (e: React.KeyboardEvent) => {
    if (e.key !== "Tab" || !boxRef.current) return;
    const focusables = Array.from(boxRef.current.querySelectorAll<HTMLElement>(
      'button:not([disabled]), input:not([disabled]), [href], [tabindex]:not([tabindex="-1"])'));
    if (focusables.length === 0) return;
    const first = focusables[0];
    const last = focusables[focusables.length - 1];
    if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
    else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
  };

  // Ctrl-K now belongs to the command palette, which can hand off to chat.
  // Chat keeps Escape so it can be dismissed on its own — listener mounted
  // only while the overlay is open, so it never swallows Escape elsewhere.
  useEffect(() => {
    if (!isOpen) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") setOpen(false); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [isOpen]);

  useEffect(() => {
    listRef.current?.scrollTo({ top: listRef.current.scrollHeight });
  }, [msgs, busy]);

  /** The one submission path — send() and ask() both land here. */
  const submit = async (q: string) => {
    if (!q || busy) return;
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
          if (full) {
            setLast(full);
            if (id) sessionStorage.setItem("chat_session", id);
          } else {
            // resuming a session the CLI no longer knows returns an instant
            // empty result — drop the dud id so the next ask starts fresh
            sessionStorage.removeItem("chat_session");
            setLast("⚠ that conversation has expired — ask again to start a new one");
          }
        },
        onError: (e) => setLast(`⚠ ${e}`),
      });
    } catch (e) {
      setLast(`⚠ ${String(e)}`);
    } finally {
      setBusy(false);
    }
  };

  const send = () => {
    const q = draft.trim();
    if (!q || busy) return;
    setDraft("");
    void submit(q);
  };

  const ask = (question: string) => {
    const q = question.trim();
    setOpen(true);
    if (!q) return;
    if (busy) { setDraft(q); return; } // a reply is streaming — park it in the box
    void submit(q);
  };

  const newConversation = () => {
    sessionStorage.removeItem("chat_session");
    setMsgs([]);
  };

  return (
    <Ctx.Provider value={{ open: () => setOpen(true), close: () => setOpen(false), ask, isOpen }}>
      {children}
      {isOpen && (
        // token-ok: a modal scrim is the one place blur is still a material.
        // It separates a transient overlay from the page, and nothing is being
        // read through it — unlike the stat tables blur used to sit behind.
        <div className="fixed inset-0 z-50 flex items-start justify-center bg-canvas/70 p-4 pt-16 backdrop-blur-sm"
             onClick={() => setOpen(false)}>
          <div ref={boxRef} role="dialog" aria-modal="true" aria-label="Analyst chat"
               className="rounded-[var(--radius-panel)] border border-border bg-surface flex max-h-[80vh] w-full max-w-3xl flex-col p-5"
               onClick={(e) => e.stopPropagation()} onKeyDown={trapTab}>
            <div className="mb-3 flex items-center gap-3">
              <span className="font-bold text-accent">◉ ANALYST LINK</span>
              <button onClick={newConversation}
                className="ml-auto rounded-[var(--radius-chip)] border border-border px-2.5 py-1 text-micro text-muted transition-colors hover:bg-surface-2 hover:text-ink">
                new conversation
              </button>
              <button onClick={() => setOpen(false)}
                className="rounded-[var(--radius-chip)] border border-border px-2.5 py-1 text-micro text-muted transition-colors hover:bg-surface-2 hover:text-ink">
                esc
              </button>
            </div>

            <div ref={listRef} className="min-h-40 flex-1 space-y-4 overflow-y-auto pr-2">
              {msgs.length === 0 && (
                <p className="text-body text-muted">
                  Direct line to your NFL analyst — full access to the warehouse,
                  news, and market tracker. Answers take 20–60 seconds because it
                  runs real queries. Try: <em>"Who led the league in rushing in 2025?"</em>
                </p>
              )}
              {msgs.map((m, i) => (
                <div key={i} className={m.role === "user" ? "text-right" : ""}>
                  <div className={`inline-block max-w-[85%] whitespace-pre-wrap rounded-2xl px-4 py-2.5 text-left text-sm leading-relaxed ${
                    m.role === "user" ? "bg-accent-bg" : "border border-border bg-surface-2"}`}>
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
                className="flex-1 rounded-[var(--radius-control)] border border-border bg-surface-2 px-4 py-2.5 text-body text-ink outline-none placeholder:text-faint" />
              <button onClick={send} disabled={busy || !draft.trim()}
                className="rounded-[var(--radius-control)] border border-accent/50 bg-accent-bg px-4 py-2.5 text-body font-semibold text-accent transition-colors hover:border-accent disabled:opacity-40">
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
