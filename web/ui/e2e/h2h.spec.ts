import { expect, test } from "@playwright/test";

test("h2h explorer shows the full BUF-MIA series", async ({ page }) => {
  await page.goto("/h2h/BUF/MIA");
  await expect(page.getByText(/\d+ meetings/)).toBeVisible();
  const rows = page.locator("tbody tr");
  await expect(async () => {
    expect(await rows.count()).toBeGreaterThan(50);
  }).toPass();
});

test("h2h game row links to the matchup card", async ({ page }) => {
  await page.goto("/h2h/BUF/MIA");
  await page.getByText(/Every meeting/).waitFor();
  await page.locator("table tbody tr").last().click();
  await expect(page).toHaveURL(/\/matchup\/\d{4}_/);
  await expect(page.getByText("Travel, rest & form")).toBeVisible();
});
