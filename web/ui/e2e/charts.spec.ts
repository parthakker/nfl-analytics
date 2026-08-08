import { expect, test } from "@playwright/test";

test("a line chart has a table twin so values are readable without hovering", async ({ page }) => {
  // the team EPA chart exists in fixture mode too (the refs trend chart,
  // this test's old target, needs multi-season pbp the fixture can't carry)
  await page.goto("/team/KC?tab=stats");

  // Panel owns the title; ChartFrame renders the <figure> inside it
  const figure = page.locator("figure").first();
  await expect(figure.locator(".recharts-line-curve").first()).toBeVisible();

  // legend names both series as text — identity is never colour-alone
  await expect(figure.getByText("Offense")).toBeVisible();
  await expect(figure.getByText("Defense")).toBeVisible();

  await figure.getByRole("button", { name: "Table" }).click();
  await expect(figure.locator("table thead")).toContainText("Week");
  await expect(figure.locator("table thead")).toContainText("Offense");
  await expect(figure.locator("table tbody tr").first()).toBeVisible();

  await figure.getByRole("button", { name: "Chart" }).click();
  await expect(figure.locator(".recharts-line-curve").first()).toBeVisible();
});

test("scatter dots carry a 24px hit layer under the visible mark", async ({ page }) => {
  await page.goto("/leaders");
  await page.locator("tbody tr").first().waitFor();
  await page.getByRole("button", { name: "Chart", exact: true }).click();

  const dot = page.locator(".recharts-scatter-symbol").first();
  await expect(dot.locator("circle")).toHaveCount(2);
  // the transparent target must be the larger of the two
  const radii = await dot.locator("circle").evaluateAll(
    (els) => els.map((e) => Number(e.getAttribute("r"))));
  expect(Math.max(...radii)).toBeGreaterThanOrEqual(12);
  expect(Math.min(...radii)).toBeLessThan(12);
});
