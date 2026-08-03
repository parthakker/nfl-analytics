export default function Chip({ children, tone = "muted" }: { children: React.ReactNode; tone?: string }) {
  const color = tone === "hot" ? "#ec835a" : tone === "arc" ? "var(--arc)" : "var(--muted)";
  return (
    <span className="rounded-full border px-2 py-0.5 text-[11px]"
          style={{ borderColor: "var(--stroke)", color }}>
      {children}
    </span>
  );
}
