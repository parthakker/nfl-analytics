import { expect, test } from "@playwright/test";

test("betting board renders game cards with lines", async ({ page }) => {
  await page.goto("/betting");
  await expect(page.getByText("Betting intelligence")).toBeVisible();
  await expect(page.getByText(/@/).first()).toBeVisible();  // AWY @ HOME header
});
