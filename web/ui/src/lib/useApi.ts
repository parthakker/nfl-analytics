import { useEffect, useState } from "react";
import { apiGet } from "./api";

interface ApiState<T> {
  data: T | null;
  error: string | null;
  loading: boolean;
}

/** Fetch JSON for a page. Replaces the raw `fetch().then(r => r.json())`
 *  pattern that silently rendered a blank page on any failure.
 *
 *  - `url === null` means "don't fetch" (param not ready, tab not active).
 *  - the in-flight request is aborted on unmount and whenever the url (or a
 *    dep) changes, and late responses from a superseded request are ignored —
 *    fast team-to-team nav can no longer paint stale data.
 *  - non-2xx responses surface as `error` instead of an unhandled rejection;
 *    503s reuse `apiGet`'s single retry (a collector briefly holds the store).
 *  - `deps` re-runs the fetch for inputs that are not part of the url
 *    (rare — the url string itself is already a dependency).
 */
export function useApi<T>(url: string | null, deps?: unknown[]): ApiState<T> {
  const [state, setState] = useState<ApiState<T>>({
    data: null, error: null, loading: url != null,
  });

  useEffect(() => {
    if (url == null) {
      setState({ data: null, error: null, loading: false });
      return;
    }
    const ctl = new AbortController();
    let stale = false;
    setState({ data: null, error: null, loading: true });
    apiGet<T>(url, ctl.signal)
      .then((d) => {
        if (!stale) setState({ data: d, error: null, loading: false });
      })
      .catch((e: unknown) => {
        if (stale || ctl.signal.aborted) return; // superseded — never report
        setState({
          data: null,
          error: e instanceof Error ? e.message : String(e),
          loading: false,
        });
      });
    return () => { stale = true; ctl.abort(); };
    // the url string is the real dependency; deps covers non-url inputs
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [url, ...(deps ?? [])]);

  return state;
}
