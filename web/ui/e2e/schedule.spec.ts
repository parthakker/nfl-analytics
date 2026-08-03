import { expect, test } from "@playwright/test";

test("schedule row click opens the matchup card", async ({ page }) => {
  await page.goto("/schedule");
  await page.locator("tbody tr").first().waitFor();
  await page.locator("tbody tr").first().click();
  await expect(page).toHaveURL(/\/matchup\/\d{4}_/);
  await expect(page.getByText("Travel, rest & form")).toBeVisible();
});
