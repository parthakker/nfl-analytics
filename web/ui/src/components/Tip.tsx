/** Pure-CSS hover tooltip — no deps; native title attr as fallback. */
export default function Tip({ text, children }: { text: string; children: React.ReactNode }) {
  return (
    <span className="group relative inline-block" title={text}>
      {children}
      <span className="pointer-events-none absolute left-1/2 top-full z-50 mt-1 hidden w-max max-w-56 -translate-x-1/2 rounded-lg border px-2.5 py-1.5 text-left text-[11px] font-normal normal-case leading-snug group-hover:block"
            style={{ background: "var(--bg-1)", borderColor: "var(--stroke)", color: "var(--text)" }}>
        {text}
      </span>
    </span>
  );
}
