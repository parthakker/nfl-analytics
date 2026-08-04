import { expect, test } from "@playwright/test";

test("coach hub tabs switch between HC, OC and DC", async ({ page }) => {
  await page.goto("/coaches");
  await page.locator("tbody tr").first().waitFor();
  await page.getByRole("button", { name: "Offensive coordinators" }).click();
  await expect(page.locator("tbody tr")).toHaveCount(32);
  await page.getByRole("button", { name: "Defensive coordinators" }).click();
  await expect(page.getByText(/Tampa Bay carries no DC title/)).toBeVisible();
});

test("coordinator page renders about + unit performance", async ({ page }) => {
  await page.goto("/coaches");
  await page.getByRole("button", { name: "Defensive coordinators" }).click();
  await page.getByRole("link", { name: "Steve Spagnuolo" }).click();
  await expect(page).toHaveURL(/role=DC/);
  await expect(page.getByText("Defensive coordinator").first()).toBeVisible();
  await expect(page.getByText("About", { exact: true })).toBeVisible();
  await expect(page.getByText(/Unit performance/)).toBeVisible();
});

test("scheme identity panel deep-links into the knowledge book", async ({ page }) => {
  await page.goto("/coach/Andy%20Reid");
  await page.getByText("Offensive identity").waitFor();
  await page.getByText("West Coast (Reid tree)").click();
  await expect(page).toHaveURL(/\/knowledge\/offensive-scheme-families#reid/);
  await expect(page.locator("article h1")).toContainText("Offensive Scheme Families");
});

test("HC page shows current staff cards", async ({ page }) => {
  await page.goto("/coach/Andy%20Reid");
  await expect(page.getByText("Current staff")).toBeVisible();
  await expect(page.getByRole("link", { name: "Eric Bieniemy" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Steve Spagnuolo" })).toBeVisible();
});
