import { useCallback, useEffect, useRef, useState } from "react";
import { Chip, PageHeader, Panel, Select, StatTile } from "../components/ui";
import type { ChipTone } from "../components/ui";
import { useApi } from "../lib/useApi";
import { streamJob, type JobStreamLine } from "../lib/useJobStream";

interface JobDef {
  key: string;
  label: string;
  blurb: string;
  script: string;
  est_seconds: number;
  writes: string[];
  danger: boolean;
  timeout_s: number;
  variants: string[];
}

interface LastRun {
  ts: string | null;
  age_hours: number | null;
  summary: string;
  ok: boolean | null;
  duration_s?: number;
  source: string;
}

interface FileInfo {
  exists: boolean;
  mb: number | null;
  modified: string | null;
  age_hours: number | null;
}

interface Freshness {
  files: { nfl: FileInfo; kalshi: FileInfo; news: FileInfo };
  warehouse?: { season: number | null; week: number | null };
  schedules_season?: number | null;
  kalshi?: { snapshots?: number; latest?: string | null; error?: string };
  news?: { items?: number; latest?: string | null; error?: string };
  error?: string;
}

interface OpsStatus {
  jobs: JobDef[];
  freshness: Freshness;
  last_runs: Record<string, LastRun>;
  running: { job: string; label: string; elapsed_s: number } | null;
}

const VARIANT_LABEL: Record<string, string> = {
  "": "Standard",
  full: "Full (every season in the manifest)",
  download: "Download only (no rebuild)",
  backfill: "Backfill history",
};

/** Kalshi snapshots and Vegas line snapshots are point-in-time captures — a
 *  window that passes without a run cannot be recovered later. Everything else
 *  here is recomputable, so only these get a staleness warning. */
const PERISHABLE_STALE_HOURS = 24;

const MAX_CONSOLE_LINES = 2000;

function ageLabel(hours: number | null | undefined): string {
  if (hours === null || hours === undefined) return "never";
  if (hours < 1) return `${Math.round(hours * 60)}m ago`;
  if (hours < 48) return `${Math.round(hours)}h ago`;
  return `${Math.round(hours / 24)}d ago`;
}

function estLabel(seconds: number): string {
  return seconds < 60 ? "<1 min" : `~${Math.round(seconds / 60)} min`;
}

function runTone(run: LastRun | undefined): ChipTone {
  if (!run) return "neutral";
  if (run.ok === true) return "positive";
  if (run.ok === false) return "negative";
  return "neutral";
}

export default function Ops() {
  const [reloadKey, setReloadKey] = useState(0);
  // useApi has no refetch trigger, so a key in deps is how the panel refreshes
  const { data, error } = useApi<OpsStatus>("/api/ops/jobs", [reloadKey]);

  const [variants, setVariants] = useState<Record<string, string>>({});
  const [running, setRunning] = useState<string | null>(null);
  const [confirming, setConfirming] = useState<string | null>(null);
  const [lines, setLines] = useState<JobStreamLine[]>([]);
  const [status, setStatus] = useState<string>("");
  const [elapsed, setElapsed] = useState(0);
  const abortRef = useRef<AbortController | null>(null);
  const consoleRef = useRef<HTMLPreElement>(null);
  const pinnedRef = useRef(true);

  // elapsed clock while a job runs
  useEffect(() => {
    if (!running) return;
    const started = Date.now();
    const t = setInterval(() => setElapsed(Math.round((Date.now() - started) / 1000)), 1000);
    return () => clearInterval(t);
  }, [running]);

  // keep the console pinned to the bottom unless the reader scrolled up
  useEffect(() => {
    const el = consoleRef.current;
    if (el && pinnedRef.current) el.scrollTop = el.scrollHeight;
  }, [lines]);

  const onScroll = useCallback(() => {
    const el = consoleRef.current;
    if (!el) return;
    pinnedRef.current = el.scrollHeight - el.scrollTop - el.clientHeight < 40;
  }, []);

  const push = useCallback((line: JobStreamLine) => {
    setLines((prev) => {
      const next = prev.length >= MAX_CONSOLE_LINES ? prev.slice(-MAX_CONSOLE_LINES + 1) : prev;
      return [...next, line];
    });
  }, []);

  const run = useCallback(
    async (job: JobDef) => {
      if (running) return;
      const variant = variants[job.key] ?? "";
      setConfirming(null);
      setRunning(job.key);
      setElapsed(0);
      setLines([{ text: `$ ${job.label}${variant ? ` (${variant})` : ""}`, stream: "ops" }]);
      setStatus("running");
      pinnedRef.current = true;
      const ac = new AbortController();
      abortRef.current = ac;
      await streamJob(
        job.key,
        variant,
        {
          onLine: push,
          onDone: (d) => {
            setStatus(
              d.exit_code === 0
                ? `finished in ${d.duration_s}s`
                : `exited ${d.exit_code} after ${d.duration_s}s`,
            );
            push({
              text:
                d.exit_code === 0
                  ? `— done in ${d.duration_s}s —`
                  : `— FAILED, exit ${d.exit_code} —`,
              stream: d.exit_code === 0 ? "ops" : "stderr",
            });
          },
          onError: (m) => {
            setStatus(`error: ${m}`);
            push({ text: m, stream: "stderr" });
          },
        },
        ac.signal,
      );
      abortRef.current = null;
      setRunning(null);
      setReloadKey((k) => k + 1);
    },
    [running, variants, push],
  );

  const stop = useCallback(() => {
    abortRef.current?.abort();
    setStatus("stopped");
  }, []);

  const jobs = data?.jobs ?? [];
  const fresh = data?.freshness;
  const lastRuns = data?.last_runs ?? {};
  const kalshiAge = fresh?.files?.kalshi?.age_hours ?? null;

  return (
    <>
      <PageHeader
        title="Operations"
        subtitle="Run maintenance by hand. Nothing is scheduled — the Task Scheduler jobs were removed because they all fired at once when the machine woke up."
        meta={
          fresh?.warehouse ? (
            <div className="flex flex-wrap gap-1.5">
              <Chip>
                warehouse {fresh.warehouse.season} · wk {fresh.warehouse.week}
              </Chip>
              <Chip>schedule {fresh.schedules_season}</Chip>
              <Chip tone={(fresh.files.nfl.age_hours ?? 0) > 24 * 8 ? "warning" : "neutral"}>
                nfl.duckdb {ageLabel(fresh.files.nfl.age_hours)}
              </Chip>
            </div>
          ) : undefined
        }
      />

      {error && (
        <Panel title="Error">
          <p className="text-body text-negative">{String(error)}</p>
        </Panel>
      )}

      <div className="mb-4 grid grid-cols-2 gap-3 lg:grid-cols-4">
        <StatTile
          label="Warehouse"
          value={fresh?.warehouse?.season ?? "—"}
          sub={`week ${fresh?.warehouse?.week ?? "—"} · ${fresh?.files.nfl.mb ?? "—"} MB`}
          help="Latest season and week present in play_by_play, and the size of nfl.duckdb."
        />
        <StatTile
          label="Last refresh"
          value={ageLabel(lastRuns.refresh?.age_hours)}
          tone={lastRuns.refresh?.ok === false ? "negative" : "neutral"}
          sub={lastRuns.refresh?.ok === false ? "last run failed" : undefined}
          help="When scripts/refresh_data.py last completed, from logs/refresh.log or logs/ops_runs.jsonl."
        />
        <StatTile
          label="Kalshi snapshots"
          value={fresh?.kalshi?.snapshots?.toLocaleString() ?? "—"}
          tone={kalshiAge !== null && kalshiAge > PERISHABLE_STALE_HOURS ? "negative" : "neutral"}
          sub={ageLabel(kalshiAge)}
          help="Market snapshots are a point-in-time capture. A window that passes without a run cannot be backfilled later — unlike the warehouse, which is always rebuildable."
        />
        <StatTile
          label="News items"
          value={fresh?.news?.items?.toLocaleString() ?? "—"}
          sub={ageLabel(fresh?.files.news.age_hours)}
          help="Rows in news.duckdb and when the file was last written."
        />
      </div>

      <Panel
        title="Console"
        note={
          running
            ? `${running} · ${elapsed}s elapsed`
            : status || "Output from the last job you ran appears here."
        }
        actions={
          running ? (
            <button
              onClick={stop}
              className="rounded-[var(--radius-control)] border border-negative/40 px-2.5 py-1 text-label text-negative transition-colors hover:bg-surface-2"
            >
              Stop
            </button>
          ) : lines.length > 0 ? (
            <button
              onClick={() => setLines([])}
              className="rounded-[var(--radius-control)] border border-border px-2.5 py-1 text-label text-muted transition-colors hover:bg-surface-2 hover:text-ink"
            >
              Clear
            </button>
          ) : undefined
        }
        span={3}
        className="mb-4"
      >
        <pre
          ref={consoleRef}
          onScroll={onScroll}
          className="max-h-80 overflow-auto whitespace-pre-wrap break-words rounded-[var(--radius-control)] bg-canvas p-3 font-mono text-micro leading-relaxed"
        >
          {lines.length === 0 ? (
            <span className="text-faint">idle</span>
          ) : (
            lines.map((l, i) => (
              <div key={i} className={l.stream === "stderr" ? "text-negative" : "text-muted"}>
                {l.text}
              </div>
            ))
          )}
        </pre>
      </Panel>

      <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
        {jobs.map((job) => {
          const last = lastRuns[job.key];
          const isRunning = running === job.key;
          const needsConfirm = job.danger && confirming !== job.key;
          return (
            <Panel key={job.key} title={job.label}>
              <p className="mb-2 text-label text-muted">{job.blurb}</p>
              <div className="mb-3 flex flex-wrap items-center gap-1.5">
                <Chip tone={runTone(last)}>
                  {last ? `last ${ageLabel(last.age_hours)}` : "never run here"}
                </Chip>
                <Chip>{estLabel(job.est_seconds)}</Chip>
                {job.writes.includes("nfl") && <Chip tone="warning">locks warehouse</Chip>}
              </div>
              {last?.summary && (
                <p className="mb-3 break-words font-mono text-micro text-faint">{last.summary}</p>
              )}
              <div className="flex items-center gap-2">
                {job.variants.length > 1 && (
                  <Select
                    size="sm"
                    ariaLabel={`${job.label} mode`}
                    value={variants[job.key] ?? ""}
                    onChange={(v) => setVariants((s) => ({ ...s, [job.key]: v }))}
                    options={job.variants.map((v) => ({
                      value: v,
                      label: VARIANT_LABEL[v] ?? v,
                    }))}
                  />
                )}
                <button
                  disabled={!!running && !isRunning}
                  onClick={() => (needsConfirm ? setConfirming(job.key) : run(job))}
                  className={`rounded-[var(--radius-control)] border px-3 py-1.5 text-label transition-colors disabled:cursor-not-allowed disabled:opacity-40 ${
                    confirming === job.key
                      ? "border-negative/40 text-negative hover:bg-surface-2"
                      : "border-accent/40 bg-accent-bg text-accent hover:border-accent"
                  }`}
                >
                  {isRunning
                    ? `Running… ${elapsed}s`
                    : confirming === job.key
                      ? "Confirm — this rewrites data"
                      : "Run"}
                </button>
                {confirming === job.key && (
                  <button
                    onClick={() => setConfirming(null)}
                    className="text-label text-muted transition-colors hover:text-ink"
                  >
                    Cancel
                  </button>
                )}
              </div>
            </Panel>
          );
        })}
      </div>

      <p className="mt-4 text-micro text-faint">
        While a warehouse job runs, other pages briefly return “store busy” and retry on their own.
      </p>
    </>
  );
}
