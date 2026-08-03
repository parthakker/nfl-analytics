import { expect, test } from "@playwright/test";

test("knowledge book lists chapters and renders one", async ({ page }) => {
  await page.goto("/knowledge");
  await expect(page.getByText("The NFL Knowledge Book")).toBeVisible();
  await page.getByText("The Analytics Primer").click();
  await expect(page).toHaveURL(/\/knowledge\/analytics-primer/);
  await expect(page.locator("article h1")).toBeVisible();
  await expect(page.locator("article p").first()).toBeVisible();  // markdown rendered
});

test("prev/next navigation walks the book", async ({ page }) => {
  await page.goto("/knowledge/the-game");
  await page.getByText(/→$/).click();
  await expect(page).toHaveURL(/\/knowledge\/positions-offense/);
});
