"""PostToolUse hook (Write|Edit): per-file lint/format, advisory only.

- *.py outside legacy/: ruff format + ruff check --fix; leftover issues go to
  stderr so Claude sees them, but exit stays 0 (the Stop gate is the blocker).
- web/ui/src/**: oxlint on the file.

Pure Python, no shell syntax — portable across Windows hook shells.
"""

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent


def run(cmd: list[str], cwd: Path = ROOT) -> tuple[int, str]:
    try:
        p = subprocess.run(
            cmd, cwd=str(cwd), capture_output=True, text=True, timeout=60, shell=False
        )
        return p.returncode, (p.stdout + p.stderr).strip()
    except Exception as e:  # tool missing etc. — never break the session
        return 0, f"(post_edit: {cmd[0]} unavailable: {e})"


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0
    fp = (payload.get("tool_input") or {}).get("file_path") or ""
    if not fp:
        return 0
    path = Path(fp)
    try:
        rel = path.resolve().relative_to(ROOT)
    except ValueError:
        return 0  # outside the repo

    parts = rel.parts
    if path.suffix == ".py" and parts[0] not in ("legacy",):
        run([sys.executable, "-m", "ruff", "format", str(path)])
        rc, out = run([sys.executable, "-m", "ruff", "check", "--fix", str(path)])
        if rc != 0 and out:
            print(f"ruff (advisory) on {rel}:\n{out[-1500:]}", file=sys.stderr)
    elif str(rel).replace("\\", "/").startswith("web/ui/src/"):
        rc, out = run(["npx.cmd", "oxlint", str(path)], cwd=ROOT / "web" / "ui")
        if rc != 0 and out:
            print(f"oxlint (advisory) on {rel}:\n{out[-1500:]}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
