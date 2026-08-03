"""Launch the Jarvis web app: uvicorn on :8000 + open the browser.

Run:  python web/run_web.py   (or double-click "NFL Jarvis.cmd")
"""

import threading
import webbrowser
from pathlib import Path

import uvicorn

DIST = Path(__file__).resolve().parent / "ui" / "dist"


def main() -> None:
    if not (DIST / "index.html").exists():
        print("UI not built yet. Run:")
        print("  cd web/ui && npm install && npm run build")
        raise SystemExit(1)
    threading.Timer(1.5, webbrowser.open, ["http://localhost:8000"]).start()
    print("NFL Jarvis online -> http://localhost:8000  (Ctrl+C to stop)")
    uvicorn.run("web.api.main:app", host="127.0.0.1", port=8000, log_level="warning")


if __name__ == "__main__":
    main()
