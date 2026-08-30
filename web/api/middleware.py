"""Maintenance gate: hold API reads off the warehouse while a job rebuilds it.

`scripts/build_warehouse.py` builds into `nfl.duckdb.building` and finishes
with `os.replace`. On Windows that rename raises PermissionError if any
process still has the target open — and this server opens a short-lived read
connection per request (`nfl_analytics.db.read_conn`). A single page load
landing in that millisecond would throw away a rebuild that took minutes.

So before a warehouse-writing job spawns, the /ops runner raises this gate and
waits for in-flight readers to reach zero. While it is up, warehouse-backed
endpoints return the same 503 shape the StoreBusyError handler already uses,
which `apiGet` in the SPA retries once on its own.

Written as a raw ASGI class rather than `@app.middleware("http")`: Starlette's
BaseHTTPMiddleware buffers responses, and it would sit in front of the SSE
streams at /api/chat/stream and /api/ops/run/*.

The counter needs no lock. Both the increment and the decrement happen on the
event loop with no await between the check and the change; sync endpoints run
in a threadpool but are entered and left through this same async wrapper.
"""

from contextlib import contextmanager

from fastapi.responses import JSONResponse

# /api/ops must stay reachable so the page driving the rebuild can still poll
# and stream. /api/health is how you check whether the server is alive at all.
EXEMPT_PREFIXES = ("/api/ops", "/api/health")


class _Gate:
    def __init__(self) -> None:
        self.job: str | None = None
        self._readers = 0

    def active(self) -> bool:
        return self.job is not None

    def raise_for(self, job: str) -> None:
        self.job = job

    def lower(self) -> None:
        self.job = None

    @property
    def readers(self) -> int:
        return self._readers

    @contextmanager
    def reader(self):
        self._readers += 1
        try:
            yield
        finally:
            self._readers -= 1


gate = _Gate()


class MaintenanceGate:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        path = scope.get("path", "")
        if not path.startswith("/api/") or path.startswith(EXEMPT_PREFIXES):
            return await self.app(scope, receive, send)
        if gate.active():
            response = JSONResponse(
                {
                    "error": (
                        f"maintenance: {gate.job} is rebuilding the warehouse — "
                        "this page will load once it finishes"
                    ),
                    "retryable": True,
                },
                status_code=503,
            )
            return await response(scope, receive, send)
        with gate.reader():
            await self.app(scope, receive, send)
