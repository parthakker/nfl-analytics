/* POST + parse a text/event-stream by hand (EventSource can't POST).
 * Twin of useChatStream.ts — same parse, different event vocabulary. */

export type JobStreamLine = { text: string; stream: "stdout" | "stderr" | "ops" };

export interface JobDone {
  exit_code: number;
  duration_s: number;
  lines: number;
  truncated: boolean;
}

export interface JobCallbacks {
  onLine?: (line: JobStreamLine) => void;
  onDone?: (done: JobDone) => void;
  onError?: (message: string) => void;
}

/** Run one maintenance job and stream its output.
 *
 * `signal` backs the Stop button: aborting closes the response, which unwinds
 * the server's timeout wrapper into its finally and kills the subprocess —
 * rather than leaving an orphaned rebuild running.
 */
export async function streamJob(
  job: string,
  variant: string,
  cb: JobCallbacks,
  signal?: AbortSignal,
): Promise<void> {
  let res: Response;
  try {
    res = await fetch(`/api/ops/run/${encodeURIComponent(job)}`, {
      method: "POST",
      // required: the server rejects anything else with 415, so a no-preflight
      // form post from another page cannot start a rebuild
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ variant }),
      signal,
    });
  } catch (e) {
    if ((e as Error).name === "AbortError") return;
    cb.onError?.((e as Error).message || "could not reach the server");
    return;
  }
  if (!res.ok) {
    const js = await res.json().catch(() => ({}) as Record<string, string>);
    cb.onError?.(js.error || `HTTP ${res.status}`);
    return;
  }

  const reader = res.body!.getReader();
  const decoder = new TextDecoder();
  let buf = "";
  let sawDone = false;

  const handle = (block: string) => {
    let event = "message";
    let data = "";
    for (const line of block.split("\n")) {
      if (line.startsWith("event:")) event = line.slice(6).trim();
      else if (line.startsWith("data:")) data += line.slice(5).trim();
    }
    if (!data) return;
    let js: Record<string, never> = {};
    try {
      js = JSON.parse(data);
    } catch {
      return;
    }
    if (event === "line") cb.onLine?.(js as unknown as JobStreamLine);
    else if (event === "done") {
      sawDone = true;
      cb.onDone?.(js as unknown as JobDone);
    } else if (event === "error") {
      sawDone = true;
      cb.onError?.((js as Record<string, string>).message || "unknown error");
    }
    // "ping" is a keepalive while a job is quiet — nothing to render
  };

  try {
    for (;;) {
      const { value, done } = await reader.read();
      if (done) break;
      // SSE line endings are \r\n or \n depending on the server library
      // (sse-starlette 3.x switched to \r\n) — normalize before splitting,
      // safe because data payloads are JSON and never carry a raw CR
      buf += decoder.decode(value, { stream: true }).replace(/\r\n/g, "\n");
      let idx;
      while ((idx = buf.indexOf("\n\n")) >= 0) {
        handle(buf.slice(0, idx));
        buf = buf.slice(idx + 2);
      }
    }
  } catch (e) {
    if ((e as Error).name === "AbortError") return; // Stop button, not a fault
    cb.onError?.((e as Error).message || "stream failed");
    return;
  }
  if (!sawDone) cb.onError?.("connection closed early");
}
