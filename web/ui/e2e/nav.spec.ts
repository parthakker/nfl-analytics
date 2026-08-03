import { expect, test } from "@playwright/test";

test("shell nav routes to every top-level page", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByText("NFL COMMAND")).toBeVisible();
  for (const [label, marker] of [
    ["Leaders", "Leaders"],
    ["Coaches", "coach"],
    ["Refs", "referee"],
    ["Schedule", "Schedule"],
    ["Betting", "Betting"],
    ["Knowledge", "Knowledge"],
  ] as const) {
    await page.getByRole("navigation").getByText(label, { exact: true }).click();
    await expect(page.locator("h1")).toContainText(new RegExp(marker, "i"));
  }
});
