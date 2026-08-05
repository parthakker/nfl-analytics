import { useState } from "react";
import type { ReactNode } from "react";

export interface FrameSeries {
  key: string;
  name: string;
  color: string;
}

interface Props {
  title?: string;
  note?: ReactNode;
  series: FrameSeries[];
  /** rows behind the chart; enables the table view */
  data?: Record<string, number | string | null>[];
  /** the category/x column, e.g. "season" */
  xKey?: string;
  xLabel?: string;
  actions?: ReactNode;
  children: ReactNode;
}

/** Legend + a TABLE VIEW of the same numbers.
 *
 *  The table is the accessibility answer and the precision answer at once:
 *  without it, a tooltip is the only way to read a value, which excludes
 *  keyboard and screen-reader users and makes "what exactly was 2019?"
 *  a hover-hunt. Identity is never color-alone — the legend names every
 *  series and the table repeats them as text.
 */
export default function ChartFrame({
  title, note, series, data, xKey, xLabel, actions, children,
}: Props) {
  const [asTable, setAsTable] = useState(false);
  const canTable = !!(data?.length && xKey);

  return (
    <figure className="m-0">
      <figcaption className="mb-2 flex flex-wrap items-center gap-x-4 gap-y-1">
        {title && <span className="text-label font-semibold text-ink">{title}</span>}
        {series.length > 0 && (
          <ul className="flex flex-wrap items-center gap-3">
            {series.map((s) => (
              <li key={s.key} className="flex items-center gap-1.5 text-micro text-muted">
                <span className="h-2 w-2 rounded-full" style={{ background: s.color }} />
                {s.name}
              </li>
            ))}
          </ul>
        )}
        <span className="ml-auto flex items-center gap-2">
          {actions}
          {canTable && (
            <button
              type="button"
              aria-pressed={asTable}
              onClick={() => setAsTable((v) => !v)}
              className="rounded-[var(--radius-chip)] border border-border px-2 py-0.5 text-micro text-muted transition-colors hover:border-border-strong hover:text-ink"
            >
              {asTable ? "Chart" : "Table"}
            </button>
          )}
        </span>
      </figcaption>

      {asTable && canTable ? (
        <div className="scroll-x">
          <table className="w-max min-w-full whitespace-nowrap text-left text-table">
            <thead>
              <tr className="bg-surface">
                <th scope="col" className="border-b border-border py-1.5 pr-4 pl-1 text-label font-semibold text-muted">
                  {xLabel ?? xKey}
                </th>
                {series.map((s) => (
                  <th key={s.key} scope="col"
                      className="border-b border-border py-1.5 pr-4 text-right text-label font-semibold text-muted">
                    {s.name}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {data!.map((row, i) => (
                <tr key={i}>
                  <td className="border-t border-border py-1.5 pr-4 pl-1 text-muted">
                    {row[xKey!] ?? "—"}
                  </td>
                  {series.map((s) => (
                    <td key={s.key} className="border-t border-border py-1.5 pr-4 text-right tabular-nums">
                      {row[s.key] ?? "—"}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        children
      )}

      {note && <p className="mt-2 text-micro text-muted">{note}</p>}
    </figure>
  );
}
