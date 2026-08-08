import { useLayoutEffect, useMemo, useRef, useState } from "react";
import type { ReactNode } from "react";
import { Link, useNavigate } from "react-router-dom";
import Tip from "./Tip";

export interface Column<R> {
  key: string;
  label: string;
  /** hover explanation on the header — every stat should say what it is */
  help?: string;
  /** right-align + tabular figures */
  numeric?: boolean;
  align?: "left" | "right";
  width?: string;
  sortable?: boolean;
  render?: (row: R, i: number) => ReactNode;
  /** sortable/exportable scalar; falls back to row[key] */
  value?: (row: R) => number | string | null;
  /** -1..1 → diverging cell tint. Dark at the centre, bright at the extremes,
   *  so "league average" recedes into the surface and outliers pop. */
  tint?: (row: R) => number | null;
  /** 0..1 → in-cell bar behind the number */
  bar?: (row: R) => number | null;
}

export interface DataTableProps<R> {
  columns: Column<R>[];
  rows: R[];
  rowKey: (row: R) => string;
  /** controlled (server-side) sort */
  sort?: { key: string; dir: "asc" | "desc" };
  onSort?: (key: string) => void;
  /** uncontrolled (client-side) sort */
  defaultSort?: { key: string; dir: "asc" | "desc" };
  rowHref?: (row: R) => string;
  onRowClick?: (row: R) => void;
  /** extra classes for a row — e.g. highlight the page's own team */
  rowClass?: (row: R) => string;
  stickyHeader?: boolean;
  /** number of leading columns to freeze; offsets are measured, not guessed */
  stickyCols?: number;
  maxHeight?: string;
  /** rendered in <tfoot> — never in <tbody>, so row-count assertions and
   *  "last row" logic aren't polluted by a summary line */
  footRow?: ReactNode;
  /** a caveat spanning the full width; wrapped in <tfoot> for you */
  footNote?: ReactNode;
  empty?: ReactNode;
  caption?: string;
  className?: string;
}

const raw = <R,>(c: Column<R>, r: R): number | string | null =>
  c.value ? c.value(r) : ((r as Record<string, unknown>)[c.key] as number | string | null);

export default function DataTable<R>({
  columns, rows, rowKey, sort, onSort, defaultSort, rowHref, onRowClick, rowClass,
  stickyHeader = true, stickyCols = 0, maxHeight, footRow, footNote, empty,
  caption, className = "",
}: DataTableProps<R>) {
  const nav = useNavigate();
  const [localSort, setLocalSort] = useState(defaultSort);
  const controlled = !!sort;
  const active = sort ?? localSort;

  // measured sticky offsets — hardcoded left values break the moment a
  // column's content changes width
  const headRefs = useRef<(HTMLTableCellElement | null)[]>([]);
  const [offsets, setOffsets] = useState<number[]>([]);
  useLayoutEffect(() => {
    if (!stickyCols) return;
    const next: number[] = [];
    let acc = 0;
    for (let i = 0; i < stickyCols; i++) {
      next.push(acc);
      acc += headRefs.current[i]?.getBoundingClientRect().width ?? 0;
    }
    setOffsets(next);
  }, [stickyCols, columns, rows.length]);

  const sorted = useMemo(() => {
    if (controlled || !localSort) return rows;
    const col = columns.find((c) => c.key === localSort.key);
    if (!col) return rows;
    const dir = localSort.dir === "asc" ? 1 : -1;
    return [...rows].sort((a, b) => {
      const x = raw(col, a), y = raw(col, b);
      if (x == null) return 1;
      if (y == null) return -1;
      return (typeof x === "number" && typeof y === "number"
        ? x - y
        : String(x).localeCompare(String(y))) * dir;
    });
  }, [rows, columns, localSort, controlled]);

  const click = (key: string) => {
    const col = columns.find((c) => c.key === key);
    if (col?.sortable === false) return;
    if (controlled) return onSort?.(key);
    setLocalSort((s) =>
      s?.key === key ? { key, dir: s.dir === "desc" ? "asc" : "desc" } : { key, dir: "desc" });
  };

  const stickyStyle = (i: number): React.CSSProperties =>
    i < stickyCols
      ? { position: "sticky", left: offsets[i] ?? 0, zIndex: 10, background: "var(--color-surface)" }
      : {};

  if (!rows.length && empty) {
    return <div className="px-4 py-8 text-center text-body text-muted">{empty}</div>;
  }

  return (
    <div className={`scroll-x ${className}`} style={maxHeight ? { maxHeight, overflowY: "auto" } : undefined}>
      <table className="w-max min-w-full whitespace-nowrap text-left text-table">
        {caption && <caption className="sr-only">{caption}</caption>}
        <thead className={stickyHeader ? "sticky top-0 z-20" : ""}>
          <tr className="bg-surface">
            {columns.map((c, i) => {
              const isActive = active?.key === c.key;
              const label = (
                <button
                  type="button"
                  onClick={() => click(c.key)}
                  aria-pressed={isActive}
                  className={`font-semibold uppercase tracking-wide transition-colors hover:text-ink ${
                    isActive ? "text-accent" : "text-muted"
                  }`}
                >
                  {c.label}
                  <span className={isActive ? "" : "opacity-30"}>
                    {isActive ? (active.dir === "desc" ? " ↓" : " ↑") : " ↕"}
                  </span>
                </button>
              );
              return (
                <th
                  key={c.key}
                  ref={(el) => { headRefs.current[i] = el; }}
                  scope="col"
                  style={{ ...stickyStyle(i), width: c.width }}
                  className={`border-b border-border py-2 text-label font-semibold ${
                    c.align === "right" || c.numeric ? "text-right" : "text-left"
                  } ${i === columns.length - 1 ? "pr-3" : "pr-4"} ${i === 0 ? "pl-3" : ""}`}
                >
                  {c.help ? <Tip text={c.help}>{label}</Tip> : label}
                </th>
              );
            })}
            {/* soaks up leftover width so the real columns stay packed left
                instead of drifting apart across a wide panel */}
            <th aria-hidden className="w-full border-b border-border" />
          </tr>
        </thead>

        <tbody>
          {sorted.map((r, ri) => {
            const cells = columns.map((c, i) => {
              const v = raw(c, r);
              const tintV = c.tint?.(r);
              const barV = c.bar?.(r);
              const style: React.CSSProperties = { ...stickyStyle(i) };
              if (tintV != null && tintV !== 0) {
                const mag = Math.min(1, Math.abs(tintV));
                const hue = tintV > 0 ? "var(--color-tint-hi)" : "var(--color-tint-lo)";
                style.background = `color-mix(in oklab, ${hue} ${(0.15 + mag * 0.2) * 100}%, transparent)`;
              }
              if (barV != null && barV > 0) {
                const pct = Math.min(1, barV) * 100;
                style.background = `linear-gradient(90deg, color-mix(in oklab, var(--color-accent) 16%, transparent) ${pct}%, transparent ${pct}%)`;
              }
              return (
                <td
                  key={c.key}
                  style={style}
                  className={`border-t border-border align-middle ${
                    c.align === "right" || c.numeric ? "text-right tabular-nums" : "text-left"
                  } ${i === columns.length - 1 ? "pr-3" : "pr-4"} ${i === 0 ? "pl-3" : ""}`}
                >
                  {c.render ? c.render(r, ri) : (v ?? "—")}
                </td>
              );
            });
            cells.push(<td key="__spacer" aria-hidden className="border-t border-border" />);

            // row-h reads --row-h, which useDensity flips on <html>
            const cls = `row-h transition-colors hover:bg-surface-2 ${rowClass?.(r) ?? ""}`;
            if (rowHref) {
              return (
                <tr key={rowKey(r)} className={`${cls} cursor-pointer`}
                    onClick={(e) => {
                      // a nested link/button owns its own destination
                      if ((e.target as HTMLElement).closest("a,button")) return;
                      const to = rowHref(r);
                      if (to) nav(to);
                    }}>
                  {cells}
                </tr>
              );
            }
            return (
              <tr
                key={rowKey(r)}
                onClick={onRowClick ? () => onRowClick(r) : undefined}
                className={`${cls} ${onRowClick ? "cursor-pointer" : ""}`}
              >
                {cells}
              </tr>
            );
          })}
        </tbody>

        {(footRow || footNote) && (
          <tfoot>
            {footRow}
            {footNote && (
              <tr>
                <td colSpan={columns.length + 1}
                    className="border-t border-border px-3 py-2 text-micro italic text-muted">
                  {footNote}
                </td>
              </tr>
            )}
          </tfoot>
        )}
      </table>
    </div>
  );
}

/** Convenience for the common "first column is a link" case. */
export function LinkCell({ to, children }: { to: string; children: ReactNode }) {
  return (
    <Link to={to} className="font-medium text-accent hover:underline">
      {children}
    </Link>
  );
}
