import { expect, test } from "@playwright/test";

test("six top-level sections route correctly", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByText("NFL COMMAND")).toBeVisible();
  for (const [label, marker] of [
    ["Scores", "Schedule"],
    ["Teams", "standings"],
    ["Players", "Player explorer"],
    ["Betting", "Betting"],
    ["Learn", "Knowledge"],
    ["Today", "The League"],
  ] as const) {
    await page.getByRole("navigation").getByRole("link", { name: label, exact: true }).click();
    await expect(page.locator("h1")).toContainText(new RegExp(marker, "i"));
  }
});

test("secondary sections live under More", async ({ page }) => {
  await page.goto("/");
  // "More" is a disclosure of plain nav links, not an ARIA menu
  const more = page.getByRole("button", { name: "More ▾" });
  await more.click();
  await expect(more).toHaveAttribute("aria-expanded", "true");
  await page.getByRole("navigation").getByRole("link", { name: "Refs" }).click();
  await expect(page.locator("h1")).toContainText(/referee/i);
});

test("old paths redirect instead of 404ing", async ({ page }) => {
  // /schedule is in Parth's history and in shared links
  await page.goto("/schedule");
  await expect(page).toHaveURL(/\/scores$/);
  await expect(page.locator("h1")).toContainText(/Schedule/i);

  await page.goto("/definitely-not-a-page");
  await expect(page).toHaveURL(/\/$/);
});

test("matchup deep links still work — knowledge chapters point at them", async ({ page }) => {
  await page.goto("/matchup/2024_01_BAL_KC");
  await expect(page.getByText("Travel, rest & form")).toBeVisible();
});
