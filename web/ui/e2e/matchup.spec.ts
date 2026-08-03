import { expect, test } from "@playwright/test";

test("matchup card renders all sections for a known game", async ({ page }) => {
  await page.goto("/matchup/2024_01_BAL_KC");
  await expect(page.getByText("Travel, rest & form")).toBeVisible();
  await expect(page.getByText(/mi$/).first()).toBeVisible();       // travel chip
  await expect(page.getByText("Referee", { exact: true })).toBeVisible();
  await expect(page.getByText("Weather", { exact: true })).toBeVisible();
  await expect(page.getByText(/All-time series/)).toBeVisible();
  await expect(page.getByText("Coaching matchup")).toBeVisible();
  // final score in the banner
  await expect(page.locator("text=/^\\d+–\\d+/").first()).toBeVisible();
});

test("upcoming game shows kickoff instead of score", async ({ page }) => {
  await page.goto("/matchup/2026_01_DEN_KC");
  await expect(page.getByText(/Week 1/)).toBeVisible();
  await expect(page.getByText("Crew assignments publish weekly in-season")).toBeVisible();
});
