import { expect, test } from "@playwright/test";

test("team overview: clickable HC, staff, leaders, standings", async ({ page }) => {
  await page.goto("/team/KC");
  await expect(page.getByText("team leaders", { exact: false })).toBeVisible();
  // standings row links to another team
  await expect(page.locator("a[href='/team/LAC']").first()).toBeVisible();
  // leaders card links to a player
  await expect(page.locator("a[href^='/player/']").first()).toBeVisible();
  // HC link in banner
  await page.locator("a[href^='/coach/']").first().click();
  await expect(page).toHaveURL(/\/coach\//);
});

test("results tab: season log with click-through to matchup", async ({ page }) => {
  await page.goto("/team/KC?tab=results");
  await page.locator("tbody tr").first().waitFor();
  await expect(page.getByText(/ATS \d+–\d+/)).toBeVisible();
  // pick 2024 and wait for the refetch to land before clicking
  const resp = page.waitForResponse((r) => r.url().includes("results?season=2024"));
  await page.locator("select").first().selectOption("2024");
  await resp;
  await page.locator("tbody tr").first().waitFor();
  await page.locator("tbody tr").first().click();
  await expect(page).toHaveURL(/\/matchup\/2024_/);
  await expect(page.getByText("Travel, rest & form")).toBeVisible();
});

test("historical roster: 2016 Steelers has clickable Antonio Brown", async ({ page }) => {
  await page.goto("/team/PIT?tab=roster");
  await page.locator("tbody tr").first().waitFor();
  await page.locator("select").first().selectOption("2016");
  await page.getByRole("link", { name: "Antonio Brown" }).waitFor();
  await page.getByRole("link", { name: "Antonio Brown" }).click();
  await expect(page).toHaveURL(/\/player\/00-/);
});

test("franchise strip jumps to that season's results", async ({ page }) => {
  await page.goto("/team/KC");
  await page.getByText("Franchise, season by season").waitFor();
  await page.getByRole("button", { name: /2023/ }).first().click();
  await expect(page).toHaveURL(/tab=results/);
  await page.locator("tbody tr").first().waitFor();
});
