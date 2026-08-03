import { expect, test } from "@playwright/test";

test("leaders table renders with clickable players", async ({ page }) => {
  await page.goto("/leaders");
  await expect(page.getByText("Stat leaders")).toBeVisible();
  await page.locator("tbody tr").first().waitFor();
  await expect(page.getByText(/of .* qualify/)).toBeVisible();
  // leader cards
  await expect(page.locator("a[href^='/player/']").first()).toBeVisible();
});

test("position chip filters and family tabs switch", async ({ page }) => {
  await page.goto("/leaders");
  await page.locator("tbody tr").first().waitFor();
  await page.getByRole("button", { name: "RB", exact: true }).click();
  await expect(page.locator("tbody tr").first()).toContainText("RB");
  await page.getByRole("button", { name: "Passing", exact: true }).click();
  await expect(page.getByRole("button", { name: /Cmp%/ })).toBeVisible();
});

test("scatter view renders team-colored dots", async ({ page }) => {
  await page.goto("/leaders");
  await page.locator("tbody tr").first().waitFor();
  await page.getByRole("button", { name: "scatter", exact: true }).click();
  await expect(page.locator(".recharts-scatter circle").first()).toBeVisible();
});

test("player name links to the player page", async ({ page }) => {
  await page.goto("/leaders");
  await page.locator("tbody tr").first().waitFor();
  await page.locator("tbody a[href^='/player/']").first().click();
  await expect(page).toHaveURL(/\/player\/00-/);
  await expect(page.getByText("Season lines")).toBeVisible();
});
