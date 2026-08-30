import { expect, test } from "@playwright/test";

/* The Model Lab is read-only over the model_* tables; nothing here trains. */

test("model lab opens on this week with model-vs-market cards", async ({ page }) => {
  await page.goto("/model");
  await expect(page.locator("h1")).toContainText(/model lab/i);
  await expect(page.getByRole("tab", { name: "This week" })).toHaveAttribute("aria-selected", "true");
  // every game card shows the reason bars
  await expect(page.getByText(/why it leans this way/i).first()).toBeVisible();
});

test("report card tabs carry the holdout numbers and a table view", async ({ page }) => {
  await page.goto("/model");
  await page.getByRole("tab", { name: "Report card" }).click();
  // the stat tiles (the column headers repeat the labels with a sort glyph)
  await expect(page.getByText("Model Brier", { exact: true })).toBeVisible();
  await expect(page.getByText("Market Brier", { exact: true })).toBeVisible();
  // every chart has a table view — a tooltip is never the only way to read a value
  await page.getByRole("button", { name: "Table" }).first().click();
  await expect(page.getByRole("table").first()).toBeVisible();
});

test("power ratings list all 32 teams and open a history", async ({ page }) => {
  await page.goto("/model");
  await page.getByRole("tab", { name: "Power ratings" }).click();
  const rows = page.getByRole("table").locator("tbody tr");
  await expect(rows).toHaveCount(32);
  await rows.first().click();
  await expect(page.getByText(/rating entering each game/i)).toBeVisible();
});

test("experiments tab explains how to run one", async ({ page }) => {
  await page.goto("/model");
  await page.getByRole("tab", { name: "Experiments" }).click();
  await expect(page.getByText(/nfl experiment/).first()).toBeVisible();
});

test("/model-lab redirects to /model", async ({ page }) => {
  await page.goto("/model-lab");
  await expect(page).toHaveURL(/\/model$/);
});
