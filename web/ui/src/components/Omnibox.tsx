export default function Omnibox({ onOpen }: { onOpen: () => void }) {
  return (
    <button onClick={onOpen}
      className="flex w-full items-center gap-3 rounded-[var(--radius-panel)] border border-border bg-surface px-5 py-3.5 text-left transition-colors hover:border-border-strong hover:bg-surface-2">
      <span className="pulse text-h2 text-accent">◉</span>
      <span className="text-muted">Ask me anything about the NFL…</span>
      <kbd className="ml-auto rounded-[var(--radius-chip)] border border-border px-2 py-0.5 text-micro text-muted">
        Ctrl K
      </kbd>
    </button>
  );
}
