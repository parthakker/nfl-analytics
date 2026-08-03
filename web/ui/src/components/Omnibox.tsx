export default function Omnibox({ onOpen }: { onOpen: () => void }) {
  return (
    <button onClick={onOpen}
      className="glass flex w-full items-center gap-3 px-5 py-3.5 text-left transition-shadow hover:shadow-[0_0_34px_-6px_var(--accent-glow)]">
      <span className="pulse text-lg" style={{ color: "var(--arc)" }}>◉</span>
      <span style={{ color: "var(--muted)" }}>
        Ask me anything about the NFL…
      </span>
      <kbd className="ml-auto rounded-md border px-2 py-0.5 text-xs"
           style={{ borderColor: "var(--stroke)", color: "var(--muted)" }}>
        Ctrl K
      </kbd>
    </button>
  );
}
