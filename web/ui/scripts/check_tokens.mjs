/**
 * Token discipline gate. Runs as part of `npm run lint`.
 *
 * The drift this prevents is the reason the overhaul was needed: colours got
 * typed inline one page at a time until there were three accents, nine glow
 * filters and two tooltip styles. Every rule below is something that was
 * actually in the codebase.
 *
 * Escape hatch: a line with `token-ok:` is exempt (use it for the handful of
 * places that legitimately need a literal, and say why).
 */
import { readFileSync, readdirSync, statSync } from "node:fs";
import { join, relative } from "node:path";

const SRC = "src";

// files allowed to define raw colour values
const ALLOW_FILES = [
  "src/styles/tokens.css",
  "src/lib/color.ts",
];

const RULES = [
  {
    // a hex literal anywhere but the token file
    test: /#[0-9a-fA-F]{3,8}\b/,
    msg: "hard-coded hex — use a --color-* token",
    skip: (f) => ALLOW_FILES.includes(f) || f.endsWith(".css") === false && false,
  },
  {
    test: /\brgba?\(\s*\d/,
    msg: "hard-coded rgb()/rgba() — use a token or color-mix()",
  },
  {
    test: /var\(--(arc|accent|accent-glow|stroke|glass|muted|text|bg-0|bg-1)\)/,
    msg: "legacy variable name — these were deleted in wave 5",
  },
  {
    test: /\bbackdrop-filter\b|\bbackdrop-blur\b/,
    msg: "backdrop blur — only the command palette may use a blur material",
  },
  {
    test: /drop-shadow\(0 0|text-shadow:\s*0 0|shadow-\[0_0_/,
    msg: "glow effect — the dark theme was rebuilt specifically to remove halation",
  },
  {
    test: /className="[^"]*\bglass\b|\bglow-text\b|\blogo-glow\b/,
    msg: "legacy class — replaced by <Panel> and the token layer",
  },
  {
    test: /\bbg-white\/\d|\btext-white\b|\bborder-white\//,
    msg: "raw white — use a surface/ink token so the elevation ladder stays consistent",
  },
];

function walk(dir, out = []) {
  for (const name of readdirSync(dir)) {
    const p = join(dir, name);
    if (statSync(p).isDirectory()) walk(p, out);
    else if (/\.(tsx?|css)$/.test(p)) out.push(p);
  }
  return out;
}

let failures = 0;
for (const file of walk(SRC)) {
  const rel = relative(".", file).replace(/\\/g, "/");
  const lines = readFileSync(file, "utf8").split("\n");
  let inBlockComment = false;
  lines.forEach((raw, i) => {
    // Strip comments before matching: prose about a colour is not a use of it,
    // and the alternative is littering explanations with token-ok markers.
    let line = raw;
    if (inBlockComment) {
      const end = line.indexOf("*/");
      if (end === -1) return;
      line = line.slice(end + 2);
      inBlockComment = false;
    }
    line = line.replace(/\/\*[\s\S]*?\*\//g, "");
    const open = line.indexOf("/*");
    if (open !== -1) { inBlockComment = true; line = line.slice(0, open); }
    line = line.replace(/(^|[^:])\/\/.*$/, "$1");
    if (!line.trim()) return;
    // The marker may sit on the line itself or anywhere in the comment block
    // directly above it, so a real justification can be a few sentences rather
    // than a cramped trailing note.
    if (raw.includes("token-ok:")) return;
    let j = i - 1;
    while (j >= 0 && /^\s*(\/\/|\*|\/\*)/.test(lines[j])) {
      if (lines[j].includes("token-ok:")) return;
      j--;
    }

    for (const rule of RULES) {
      if (rule.skip?.(rel)) continue;
      if (ALLOW_FILES.includes(rel)) continue;
      if (rule.test.test(line)) {
        console.error(`${rel}:${i + 1}  ${rule.msg}\n    ${line.trim().slice(0, 110)}`);
        failures++;
        break;
      }
    }
  });
}

if (failures) {
  console.error(`\ncheck_tokens: ${failures} violation${failures === 1 ? "" : "s"}.`);
  console.error("Add a token in src/styles/tokens.css, or mark the line `token-ok: <reason>`.");
  process.exit(1);
}
console.log("check_tokens: clean");
