import { expect, test } from "@playwright/test";

/* The Run buttons spawn real maintenance scripts, so nothing here clicks one.
 * The streaming path is covered by tests/api/test_ops_contract.py under
 * NFL_OPS_DRY_RUN=1. */

test("ops page lists every maintenance job", async ({ page }) => {
  await page.goto("/ops");
  await expect(page.locator("h1")).toContainText(/operations/i);
  // one Run button per job in the registry (10 maintenance + experiment + recap)
  await expect(page.getByRole("button", { name: "Run" })).toHaveCount(12);
});

test("ops console starts idle", async ({ page }) => {
  await page.goto("/ops");
  await expect(page.getByText("idle")).toBeVisible();
});

test("warehouse-writing jobs are flagged and need a second click", async ({ page }) => {
  await page.goto("/ops");
  const rebuild = page.locator("section").filter({ hasText: "Rebuild warehouse" }).first();
  await expect(rebuild.getByText("locks warehouse")).toBeVisible();
  await rebuild.getByRole("button", { name: "Run" }).click();
  // first click only arms it — the job has NOT started
  await expect(rebuild.getByRole("button", { name: /Confirm/ })).toBeVisible();
  await rebuild.getByRole("button", { name: "Cancel" }).click();
  await expect(rebuild.getByRole("button", { name: "Run" })).toBeVisible();
});
