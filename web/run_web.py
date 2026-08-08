"""Launch the Jarvis web app: uvicorn on :8000 + open the browser.

Run:  python web/run_web.py   (or double-click "NFL Jarvis.cmd")
"""

import sys
import threading
import webbrowser
from pathlib import Path

import uvicorn

# running as a script puts web/ (not the project root) on sys.path — fix that
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

DIST = Path(__file__).resolve().parent / "ui" / "dist"


def main() -> None:
    if not (DIST / "index.html").exists():
        print("UI not built yet. Run:")
        print("  cd web/ui && npm ci && npm run build")
        raise SystemExit(1)

    # everything the server does lands in logs/jarvis.log for post-mortems
    logs = ROOT / "logs"
    logs.mkdir(exist_ok=True)
    import logging

    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
    handler = logging.FileHandler(logs / "jarvis.log", encoding="utf-8")
    handler.setFormatter(fmt)
    console = logging.StreamHandler()
    console.setFormatter(fmt)
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access", "web"):
        lg = logging.getLogger(name)
        lg.addHandler(handler)
        lg.addHandler(console)
        lg.setLevel(logging.INFO)
        # uvicorn.access/.error are children of uvicorn — without this every
        # record fires the handlers twice (child's copy, then the parent's)
        lg.propagate = False
    logging.getLogger("web").info("=== Jarvis starting ===")

    threading.Timer(1.5, webbrowser.open, ["http://localhost:8000"]).start()
    print("NFL Jarvis online -> http://localhost:8000  (Ctrl+C to stop)")
    try:
        # log_config=None: uvicorn's default dictConfig would REPLACE the
        # handlers above on its three loggers, sending requests to the
        # console only — that blindness is why the 2026-08-07 chat outage
        # left no trace in jarvis.log
        uvicorn.run(
            "web.api.main:app", host="127.0.0.1", port=8000, log_level="info", log_config=None
        )
    except Exception:
        logging.getLogger("web").exception("Jarvis crashed")
        raise


if __name__ == "__main__":
    main()
