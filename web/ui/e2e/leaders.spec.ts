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
  await page.getByRole("button", { name: "Chart", exact: true }).click();
  await expect(page.locator(".recharts-scatter circle").first()).toBeVisible();
});

test("stat headers explain themselves on hover", async ({ page }) => {
  await page.goto("/leaders");
  await page.locator("tbody tr").first().waitFor();
  await page.getByRole("button", { name: "PPR/G", exact: true }).hover();
  await expect(page.getByText(/^PPR points per game/)).toBeVisible();
});

test("table scrolls horizontally", async ({ page }) => {
  await page.setViewportSize({ width: 1100, height: 720 });
  await page.goto("/leaders");
  await page.getByRole("button", { name: "Passing", exact: true }).click();
  await page.locator("tbody tr").first().waitFor();
  const box = page.locator(".scroll-x");
  const canScroll = await box.evaluate((el) => el.scrollWidth > el.clientWidth);
  expect(canScroll).toBe(true);
  await box.evaluate((el) => { el.scrollLeft = 300; });
  expect(await box.evaluate((el) => el.scrollLeft)).toBeGreaterThan(0);
});

test("qualification lives in the adjust popover", async ({ page }) => {
  await page.goto("/leaders");
  await page.locator("tbody tr").first().waitFor();
  await expect(page.locator("input[type='range']")).toHaveCount(0);
  await page.getByRole("button", { name: "adjust", exact: true }).click();
  await expect(page.locator("input[type='range']")).toBeVisible();
});

test("player name links to the player page", async ({ page }) => {
  await page.goto("/leaders");
  await page.locator("tbody tr").first().waitFor();
  await page.locator("tbody a[href^='/player/']").first().click();
  await expect(page).toHaveURL(/\/player\/00-/);
  await expect(page.getByText("Season lines")).toBeVisible();
});
