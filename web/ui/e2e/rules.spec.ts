import { expect, test } from "@playwright/test";

// The first /api/rules call builds + grades the 1999+ history frame server-side
// (cached for an hour after), so the opening wait gets a generous timeout.
// Tests in this file share one worker (no fullyParallel), so the warm-up
// happens once.

async function openRules(page: import("@playwright/test").Page) {
  await page.goto("/betting");
  await page.getByRole("button", { name: "My Rules", exact: true }).click();
  await page.getByTestId("rule-card").first().waitFor({ timeout: 25_000 });
}

test("my rules tab renders the full rule catalog", async ({ page }) => {
  await openRules(page);
  expect(await page.getByTestId("rule-card").count()).toBeGreaterThanOrEqual(8);
  // header note points at the hand-curated source file
  await expect(page.getByText(/data\/betting_rules\.json/)).toBeVisible();
});

test("a graded rule shows its backtest record", async ({ page }) => {
  await openRules(page);
  const bt = page.getByTestId("rule-backtest").first();
  await expect(bt).toBeVisible();
  await expect(bt).toContainText(/\d+–\d+–\d+/); // W–L–P record
  await expect(bt).toContainText("breakeven");
});

test("live-only rules show the tracking-since state", async ({ page }) => {
  await openRules(page);
  const nb = page.getByTestId("rule-no-backtest").first();
  await expect(nb).toBeVisible();
  await expect(nb).toContainText(/live-only signal, tracking since/);
});

test("a graded rule labels its signal strength and sample size", async ({ page }) => {
  await openRules(page);
  const sig = page.getByTestId("rule-signal").first();
  await expect(sig).toBeVisible();
  await expect(sig).toContainText(/noise|weak|strong/);
  await expect(sig).toContainText(/z [+−]\d+\.\d{2}, n=\d+/);
});
