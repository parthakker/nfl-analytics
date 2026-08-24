"""Run the chat analyst eval suite (evals/questions.json) through the real
claude CLI with the exact flags the Jarvis chat endpoint uses.

  python scripts/run_chat_evals.py --dry-run          # list + cost estimate, no calls
  python scripts/run_chat_evals.py --moment pregame   # one slice
  python scripts/run_chat_evals.py --ids pre-01,fan-03
  python scripts/run_chat_evals.py --compare evals/runs/<older>

Each question is a fresh conversation, run sequentially (mirrors the server's
one-at-a-time lock). Costs real API dollars — a full 28-question run is
roughly $3-8. Transcripts land in evals/runs/<timestamp>/ (gitignored);
summary.md is the human entry point, summary.json feeds --compare.
"""

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# the chat endpoint's exact argv builder — flag parity with the product forever
from web.api.routers.chat import _claude_cmd  # noqa: E402

QUESTIONS = ROOT / "evals" / "questions.json"
RUNS_DIR = ROOT / "evals" / "runs"
TIMEOUT_S = 300  # mirrors chat.py TIMEOUT_S
EST_COST_PER_Q = 0.20  # dry-run estimate only; summaries report actuals


def load_questions(args) -> list[dict]:
    qs = json.loads(QUESTIONS.read_text(encoding="utf-8"))["questions"]
    if args.moment:
        qs = [q for q in qs if q["moment"] == args.moment]
    if args.ids:
        wanted = set(args.ids.split(","))
        qs = [q for q in qs if q["id"] in wanted]
        missing = wanted - {q["id"] for q in qs}
        if missing:
            sys.exit(f"unknown question ids: {sorted(missing)}")
    if args.limit:
        qs = qs[: args.limit]
    return qs


def ask_claude(question: str) -> dict:
    """One fresh-session invocation. Returns transcript facts; never raises."""
    cmd = _claude_cmd(session_id=None, streaming=True)
    if cmd is None:
        sys.exit("claude CLI not found on PATH")
    # Faithfulness: production chat is spawned by uvicorn with no Claude Code
    # session in its environment. Running evals from inside a Claude Code
    # session leaks CLAUDE* vars into the child, which changes its permission
    # behavior (observed: session-approved Bash instead of MCP tools).
    env = {k: v for k, v in os.environ.items() if not k.startswith("CLAUDE")}
    env["NFL_CHAT_CHILD"] = "1"  # mirror chat.py: skip the dev stop gate
    try:
        proc = subprocess.run(
            cmd,
            input=question.encode("utf-8"),
            capture_output=True,
            cwd=str(ROOT),
            timeout=TIMEOUT_S,
            env=env,
        )
    except subprocess.TimeoutExpired:
        return {
            "answer": "",
            "tools": [],
            "seconds": TIMEOUT_S,
            "cost": 0.0,
            "error": f"timeout after {TIMEOUT_S}s",
        }

    tools: list[str] = []
    answer, cost, dur_ms, err = "", 0.0, 0, ""
    for line in proc.stdout.decode("utf-8", errors="replace").splitlines():
        try:
            js = json.loads(line)
        except json.JSONDecodeError:
            continue
        t = js.get("type")
        if t == "assistant":
            for block in (js.get("message", {}) or {}).get("content", []):
                if isinstance(block, dict) and block.get("type") == "tool_use":
                    tools.append(block.get("name", "").replace("mcp__nfl__", ""))
        elif t == "result":
            answer = js.get("result", "") or ""
            cost = js.get("total_cost_usd", 0.0) or 0.0
            dur_ms = js.get("duration_ms", 0) or 0
            if js.get("is_error"):
                err = answer or "claude returned is_error"
    if not answer and not err:
        err = (
            proc.stderr.decode("utf-8", errors="replace")[-300:].strip()
            or "stream ended without a result"
        )
    return {
        "answer": answer,
        "tools": tools,
        "seconds": round(dur_ms / 1000, 1),
        "cost": cost,
        "error": err,
    }


def run_checks(q: dict, r: dict) -> dict[str, bool]:
    auto, text = q.get("auto", {}), r["answer"].lower()
    checks: dict[str, bool] = {}
    if r["error"]:
        return {"completed": False}
    checks["completed"] = True
    if "must_mention_any" in auto:
        checks["mentions"] = any(re.search(p.lower(), text) for p in auto["must_mention_any"])
    if auto.get("must_cite_filters"):
        # heuristic for the CLAUDE.md convention: a concrete season plus filter language
        checks["cites_filters"] = bool(re.search(r"(19|20)\d{2}", text)) and any(
            w in text for w in ("reg", "regular", "playoff", "post", "season", "filter", "minimum")
        )
    if "expect_tools_any" in auto:
        checks["right_tools"] = bool(set(auto["expect_tools_any"]) & set(r["tools"]))
    if "max_seconds" in auto:
        checks["fast_enough"] = r["seconds"] <= auto["max_seconds"]
    return checks


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--moment", choices=["pregame", "gameday", "postgame", "fantasy"])
    ap.add_argument("--ids")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--compare", help="older run dir to diff check results against")
    args = ap.parse_args()

    qs = load_questions(args)
    if args.dry_run:
        for q in qs:
            gap = (
                f"  [expected gap until {q['expected_fail_until']}]"
                if q.get("expected_fail_until")
                else ""
            )
            print(f"{q['id']:8} {q['moment']:9} {q['question'][:80]}{gap}")
        print(f"\n{len(qs)} questions, estimated ${len(qs) * EST_COST_PER_Q:.2f}")
        return

    run_dir = RUNS_DIR / datetime.now().strftime("%Y-%m-%dT%H-%M")
    run_dir.mkdir(parents=True, exist_ok=True)
    rows, total_cost = [], 0.0

    for i, q in enumerate(qs, 1):
        print(f"[{i}/{len(qs)}] {q['id']} ...", end="", flush=True)
        r = ask_claude(q["question"])
        checks = run_checks(q, r)
        total_cost += r["cost"]
        ok = all(checks.values())
        print(f" {'PASS' if ok else 'FAIL'} ({r['seconds']}s, ${r['cost']:.2f})")

        (run_dir / f"{q['id']}.md").write_text(
            f"# {q['id']} — {q['moment']}\n\n**Q:** {q['question']}\n\n"
            f"**Tools:** {' → '.join(r['tools']) or '(none)'}\n\n"
            f"**Checks:** {json.dumps(checks)}\n\n"
            f"**{r['seconds']}s · ${r['cost']:.3f}**"
            + (f" · ERROR: {r['error']}" if r["error"] else "")
            + f"\n\n---\n\n{r['answer']}\n",
            encoding="utf-8",
        )
        rows.append(
            {
                "id": q["id"],
                "moment": q["moment"],
                "checks": checks,
                "ok": ok,
                "seconds": r["seconds"],
                "cost": round(r["cost"], 3),
                "tools": r["tools"],
                "error": r["error"],
                "expected_fail_until": q.get("expected_fail_until"),
                "head": r["answer"][:110].replace("\n", " "),
            }
        )

    passed = sum(1 for x in rows if x["ok"])
    expected_gaps = sum(1 for x in rows if not x["ok"] and x["expected_fail_until"])
    lines = [
        f"# Eval run {run_dir.name}",
        f"\n**{passed}/{len(rows)} passed** ({expected_gaps} failures are documented gaps) · total ${total_cost:.2f}\n",
        "| id | moment | ok | checks failed | secs | $ | answer head |",
        "|---|---|---|---|---|---|---|",
    ]
    for x in rows:
        failed = ", ".join(k for k, v in x["checks"].items() if not v) or "—"
        gap = (
            f" *(gap: {x['expected_fail_until']})*"
            if x["expected_fail_until"] and not x["ok"]
            else ""
        )
        lines.append(
            f"| {x['id']} | {x['moment']} | {'✅' if x['ok'] else '❌'}{gap} | {failed} "
            f"| {x['seconds']} | {x['cost']:.2f} | {x['head']} |"
        )
    (run_dir / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (run_dir / "summary.json").write_text(json.dumps(rows, indent=1), encoding="utf-8")

    if args.compare:
        old = {
            x["id"]: x
            for x in json.loads((Path(args.compare) / "summary.json").read_text(encoding="utf-8"))
        }
        regressions = [
            x["id"] for x in rows if x["id"] in old and old[x["id"]]["ok"] and not x["ok"]
        ]
        fixed = [x["id"] for x in rows if x["id"] in old and not old[x["id"]]["ok"] and x["ok"]]
        print(
            f"\nvs {args.compare}: {len(fixed)} newly passing {fixed}, {len(regressions)} REGRESSED {regressions}"
        )

    print(f"\n{passed}/{len(rows)} passed · ${total_cost:.2f} · {run_dir}")


if __name__ == "__main__":
    main()
