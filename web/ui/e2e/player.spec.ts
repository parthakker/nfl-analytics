import { expect, test } from "@playwright/test";

test("search navigates to a routed player page", async ({ page }) => {
  await page.goto("/players");
  await page.getByPlaceholder(/search any player/).fill("mahomes");
  await page.locator("button", { hasText: "Mahomes" }).first().click();
  await expect(page).toHaveURL(/\/player\/00-/);
  await expect(page.locator("h1")).toContainText("Mahomes");
  await expect(page.locator("img[src*='nfl.com']").first()).toBeVisible(); // headshot
  await expect(page.getByText("Recent news")).toBeVisible();
});

test("player page deep-link renders directly", async ({ page }) => {
  await page.goto("/player/00-0033873"); // Mahomes gsis
  await expect(page.locator("h1")).toContainText("Mahomes");
  await expect(page.getByText("Season lines")).toBeVisible();
});

test("roster names on the team page link to players", async ({ page }) => {
  await page.goto("/team/KC");
  await page.getByText(/roster/i).first().waitFor();
  const link = page.locator("table a[href^='/player/']").first();
  await link.waitFor();
  await link.click();
  await expect(page).toHaveURL(/\/player\/00-/);
});
