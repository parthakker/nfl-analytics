import { useChat } from "../../lib/ChatContext";

/** One-click handoff to the analyst chat, pre-loaded with a page-aware
 *  question. Styled like an active filter pill (accent border + wash) so it
 *  reads as interactive without competing with the page's data. */
export default function AskAnalyst({
  question, label = "Ask the analyst",
}: {
  question: string;
  label?: string;
}) {
  const { ask } = useChat();
  return (
    <button
      type="button"
      title={question}
      onClick={() => ask(question)}
      className="inline-flex items-center gap-1.5 rounded-full border border-accent/50 bg-accent-bg px-2.5 py-1 text-label font-semibold text-accent transition-colors hover:border-accent"
    >
      <span aria-hidden>◉</span>
      {label}
    </button>
  );
}
