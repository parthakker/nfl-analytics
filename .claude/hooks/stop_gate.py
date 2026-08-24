"""Stop hook: fast deterministic gate before a turn may end.

Keyed off what actually changed (git diff vs HEAD + untracked):
  - any .py changed  -> pytest tests/unit -x -q   (no DB, ~5-10s)
  - any web/ui/src changed -> tsc -b in web/ui    (~10s)
Nothing relevant changed -> exit 0 instantly (chat/SQL/doc turns pay ~1s).

Exit 2 blocks the turn and feeds the failure tail back to Claude.
NEVER add warehouse/api/e2e tiers here — they run nightly and in CI.
"""

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent


def changed_files() -> list[str]:
    out = []
    for args in (
        ["git", "diff", "--name-only", "HEAD"],
        ["git", "ls-files", "--others", "--exclude-standard"],
    ):
        p = subprocess.run(args, cwd=str(ROOT), capture_output=True, text=True, timeout=15)
        out += p.stdout.splitlines()
    return [f.strip().replace("\\", "/") for f in out if f.strip()]


def main() -> int:
    # The Jarvis chat product (and its eval runner) spawn headless claude
    # children in this repo — they only read, never edit, and a dirty dev
    # tree must not make every chat answer pay for a unit-test run (or leak
    # test-runner commentary into user-facing answers, which happened).
    if os.environ.get("NFL_CHAT_CHILD") == "1":
        return 0
    try:
        files = changed_files()
    except Exception:
        return 0  # git unavailable — do not wedge the session

    py_changed = any(f.endswith(".py") and not f.startswith("legacy/") for f in files)
    ui_changed = any(f.startswith("web/ui/src/") for f in files)
    failures = []

    if py_changed:
        p = subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                "tests/unit",
                "-x",
                "-q",
                "--no-header",
                "-p",
                "no:cacheprovider",
            ],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=120,
        )
        if p.returncode != 0:
            failures.append("unit tests FAILED:\n" + (p.stdout + p.stderr)[-2000:])

    if ui_changed:
        p = subprocess.run(
            ["npx.cmd", "tsc", "-b"],
            cwd=str(ROOT / "web" / "ui"),
            capture_output=True,
            text=True,
            timeout=120,
        )
        if p.returncode != 0:
            failures.append("tsc FAILED:\n" + (p.stdout + p.stderr)[-2000:])

    if failures:
        print("\n\n".join(failures), file=sys.stderr)
        return 2  # block turn end; Claude sees stderr
    return 0


if __name__ == "__main__":
    sys.exit(main())
