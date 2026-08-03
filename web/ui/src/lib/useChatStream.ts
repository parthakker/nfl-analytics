/* POST + parse a text/event-stream by hand (EventSource can't POST). */

export interface StreamCallbacks {
  onSession?: (sessionId: string) => void;
  onToken?: (text: string) => void;
  onTool?: (hint: string) => void;
  onDone?: (fullText: string, sessionId: string | null) => void;
  onError?: (message: string) => void;
}

export async function streamChat(
  message: string,
  sessionId: string | null,
  cb: StreamCallbacks,
): Promise<void> {
  const res = await fetch("/api/chat/stream", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, session_id: sessionId }),
  });
  if (!res.ok) {
    const js = await res.json().catch(() => ({}));
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
    let js: Record<string, string> = {};
    try { js = JSON.parse(data); } catch { return; }
    if (event === "session" && js.session_id) cb.onSession?.(js.session_id);
    else if (event === "token" && js.text) cb.onToken?.(js.text);
    else if (event === "tool") cb.onTool?.(js.hint || js.name || "working");
    else if (event === "done") { sawDone = true; cb.onDone?.(js.text ?? "", js.session_id ?? null); }
    else if (event === "error") { sawDone = true; cb.onError?.(js.message || "unknown error"); }
  };

  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });
    let idx;
    while ((idx = buf.indexOf("\n\n")) >= 0) {
      handle(buf.slice(0, idx));
      buf = buf.slice(idx + 2);
    }
  }
  if (!sawDone) cb.onError?.("connection closed early");
}
