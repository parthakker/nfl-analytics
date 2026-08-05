import { openPalette } from "../lib/palette";

/** The front door on Today. Opens the palette rather than jumping straight
 *  into chat: most of what gets typed here is "take me to X", and the palette
 *  answers that instantly instead of spending 30s on a warehouse query. The
 *  analyst is still one keystroke away — `?` inside the palette. */
export default function Omnibox() {
  return (
    <button onClick={openPalette}
      className="flex w-full items-center gap-3 rounded-[var(--radius-panel)] border border-border bg-surface px-5 py-3.5 text-left transition-colors hover:border-border-strong hover:bg-surface-2">
      <span className="pulse text-h2 text-accent">◉</span>
      <span className="text-muted">
        Search a team, player or page — or ask the analyst anything
      </span>
      <kbd className="ml-auto rounded-[var(--radius-chip)] border border-border px-2 py-0.5 text-micro text-muted">
        Ctrl K
      </kbd>
    </button>
  );
}
