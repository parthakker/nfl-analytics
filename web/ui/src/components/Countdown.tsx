import { useEffect, useState } from "react";

function parts(target: Date) {
  const ms = Math.max(0, target.getTime() - Date.now());
  return {
    d: Math.floor(ms / 86400000),
    h: Math.floor(ms / 3600000) % 24,
    m: Math.floor(ms / 60000) % 60,
    s: Math.floor(ms / 1000) % 60,
  };
}

export default function Countdown({ iso }: { iso: string }) {
  const target = new Date(iso + "T20:20:00");
  const [t, setT] = useState(() => parts(target));
  useEffect(() => {
    const id = setInterval(() => setT(parts(target)), 1000);
    return () => clearInterval(id);
  }, [iso]);
  const cells: [number, string][] = [[t.d, "days"], [t.h, "hrs"], [t.m, "min"], [t.s, "sec"]];
  return (
    <div className="flex items-end gap-4">
      {cells.map(([v, label]) => (
        <div key={label} className="text-center">
          <div className="text-4xl font-bold tabular-nums"
               style={{ color: "var(--color-accent)" }}>
            {String(v).padStart(2, "0")}
          </div>
          <div className="text-[10px] uppercase tracking-widest" style={{ color: "var(--color-muted)" }}>
            {label}
          </div>
        </div>
      ))}
    </div>
  );
}
