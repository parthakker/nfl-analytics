/**
 * Lockfile integrity gate. Runs as part of `npm run lint`.
 *
 * WHY THIS EXISTS
 * ---------------
 * `npm install` on Windows silently produces a lockfile that `npm ci` on
 * Linux refuses. The mechanism:
 *
 *   - @tailwindcss/oxide ships per-platform binaries plus a wasm32-wasi
 *     fallback, all as OPTIONAL dependencies.
 *   - On Windows npm never downloads the wasm32 package, so it cannot read
 *     that package's own dependency tree.
 *   - `--package-lock-only` does NOT ignore the installed tree, despite the
 *     docs. With node_modules present npm reuses it and writes the wasm32
 *     subtree incompletely — @emnapi/core and @emnapi/runtime end up with no
 *     entry at all, even though @napi-rs/wasm-runtime requires them.
 *   - `npm ci` on Linux validates the whole graph, finds the dangling
 *     requirement, and exits EUSAGE. CI goes red; the dev machine sees
 *     nothing wrong, because it never installs that subtree.
 *
 * This check walks the graph the same way npm ci does and fails locally,
 * before the push, with the fix spelled out.
 *
 * THE FIX, when this trips: regenerate the lock with node_modules ABSENT.
 *
 *     cd web/ui
 *     mv node_modules ../node_modules.bak     # or delete it
 *     npm install --package-lock-only
 *     mv ../node_modules.bak node_modules
 *     node scripts/check_lock.mjs             # confirm
 *
 * Verify with `npm ci --os=linux --cpu=x64 --dry-run`, which reproduces the
 * CI check on any machine.
 */
import { readFileSync } from "node:fs";

const lock = JSON.parse(readFileSync("package-lock.json", "utf8"));
const pkgs = lock.packages ?? {};

/** npm resolution: walk up the path, checking each node_modules on the way. */
function resolves(fromPath, name) {
  let dir = fromPath;
  for (;;) {
    const candidate = dir ? `${dir}/node_modules/${name}` : `node_modules/${name}`;
    if (candidate in pkgs) return true;
    if (!dir) return false;
    const cut = dir.lastIndexOf("/node_modules/");
    if (cut === -1) {
      dir = "";
    } else {
      dir = dir.slice(0, cut);
    }
  }
}

const problems = [];
for (const [path, meta] of Object.entries(pkgs)) {
  // peerDependencies are allowed to be unmet; npm ci does not require them
  const required = { ...(meta.dependencies ?? {}), ...(meta.optionalDependencies ?? {}) };
  for (const dep of Object.keys(required)) {
    if (!resolves(path, dep)) {
      problems.push({ path: path || "(root)", dep, optional: !!meta.optional });
    }
  }
}

if (problems.length) {
  console.error("package-lock.json is incomplete — `npm ci` will fail on Linux.\n");
  for (const p of problems) {
    console.error(`  ${p.path}`);
    console.error(`    requires ${p.dep}, which has no entry in the lock` +
                  `${p.optional ? " (inside an optional platform package)" : ""}`);
  }
  console.error("\nThis is the Windows npm bug — see the header of scripts/check_lock.mjs.");
  console.error("Fix: delete node_modules, run `npm install --package-lock-only`, restore it.");
  process.exit(1);
}

console.log(`check_lock: clean (${Object.keys(pkgs).length} entries)`);
