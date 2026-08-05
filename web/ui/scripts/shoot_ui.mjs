/**
 * Visual capture harness for the UI overhaul.
 *
 *   node scripts/shoot_ui.mjs before      → test-results/shots/before/*.png
 *   node scripts/shoot_ui.mjs wave1
 *
 * Requires the app served on :8000 (python web/run_web.py). Shots are for
 * human/agent review, not assertions — Playwright `toHaveScreenshot`
 * baselines only start after the IA wave, since everything legitimately
 * moves before then.
 *
 * The route list deliberately includes the worst cases for the team-color
 * clamp: LV (#000000), CLE (#311D00) and a DEN-CIN matchup (both teams are
 * literally #FB4F14 — the hue-collision path).
 */
import { chromium } from "@playwright/test";
import { mkdirSync } from "node:fs";

const BASE = process.env.UI_BASE ?? "http://127.0.0.1:8000";
const label = process.argv[2] ?? "shot";
const outDir = `test-results/shots/${label}`;

const ROUTES = [
  ["command", "/"],
  ["leaders-table", "/leaders"],
  ["team-KC", "/team/KC"],
  ["team-LV", "/team/LV"],
  ["team-CLE", "/team/CLE"],
  ["team-results", "/team/KC?tab=results"],
  ["team-roster", "/team/KC?tab=roster"],
  ["matchup-DEN-CIN", "/matchup/2025_11_DEN_CIN"],
  ["matchup-BAL-KC", "/matchup/2024_01_BAL_KC"],
  ["player", "/player/00-0033873"],
  ["coaches", "/coaches"],
  ["coach", "/coach/Andy%20Reid"],
  ["h2h", "/h2h/BUF/MIA"],
  ["schedule", "/schedule"],
  ["betting", "/betting"],
  ["markets", "/markets"],
  ["news", "/news"],
  ["referees", "/refs"],
  ["knowledge-index", "/knowledge"],
  ["knowledge-chapter", "/knowledge/coverage-shells"],
  ["players", "/players"],
];

mkdirSync(outDir, { recursive: true });
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1600, height: 1000 } });

for (const [name, route] of ROUTES) {
  try {
    await page.goto(BASE + route, { waitUntil: "networkidle", timeout: 20000 });
    await page.waitForTimeout(500);
    await page.screenshot({ path: `${outDir}/${name}.png` });
    process.stdout.write(`  ✓ ${name}\n`);
  } catch (e) {
    process.stdout.write(`  ✗ ${name} — ${String(e).split("\n")[0]}\n`);
  }
}

// the Leaders scatter view needs an interaction
try {
  await page.goto(BASE + "/leaders", { waitUntil: "networkidle" });
  await page.getByRole("button", { name: "Chart", exact: true }).click();
  await page.waitForTimeout(700);
  await page.screenshot({ path: `${outDir}/leaders-scatter.png` });
  process.stdout.write("  ✓ leaders-scatter\n");
} catch (e) {
  process.stdout.write(`  ✗ leaders-scatter — ${String(e).split("\n")[0]}\n`);
}

await browser.close();
process.stdout.write(`\nshots → web/ui/${outDir}\n`);
