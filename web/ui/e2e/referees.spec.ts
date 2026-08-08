import { expect, test } from "@playwright/test";

// the refs list requires 50+ career games; the CI fixture carries one pbp
// season (18 games max), so every ref falls under the floor and the list is
// legitimately empty. Real-DB runs (local `npm run e2e`) still cover these.
test.skip(!!process.env.NFL_TEST_USE_FIXTURE, "refs need multi-season pbp the fixture can't carry");

test("referee careers are one row per person, not one per id", async ({ page }) => {
  await page.goto("/refs");
  await page.locator("tbody tr").first().waitFor();

  const names = await page.locator("tbody tr td:first-child").allInnerTexts();
  const seen = new Set<string>();
  for (const n of names) {
    expect(seen.has(n), `${n} appears twice — ref_key split the career again`).toBe(false);
    seen.add(n);
  }

  // Ed Hochuli worked 1999-2017: the era must span the 2015 officials-feed
  // boundary rather than stopping at it.
  const hochuli = page.locator("tbody tr", { hasText: "Ed Hochuli" });
  await expect(hochuli).toHaveCount(1);
  await expect(hochuli).toContainText("1999–2017");
});

test("DataTable sorts on a header click and explains its stats", async ({ page }) => {
  await page.goto("/refs");
  await page.locator("tbody tr").first().waitFor();

  await page.getByRole("button", { name: /^Pen\/gm/ }).click();
  const first = await page.locator("tbody tr td:nth-child(4)").first().innerText();
  const second = await page.locator("tbody tr td:nth-child(4)").nth(1).innerText();
  expect(Number(first)).toBeGreaterThanOrEqual(Number(second));

  await page.getByRole("button", { name: /^Home bias/ }).hover();
  await expect(page.getByText(/Negative favors the home team/)).toBeVisible();
});

test("row click opens that referee's season trend", async ({ page }) => {
  await page.goto("/refs");
  await page.locator("tbody tr").first().waitFor();
  const name = await page.locator("tbody tr td:first-child").first().innerText();
  await page.locator("tbody tr").first().click();
  await expect(page.getByText(`${name} — season trends`)).toBeVisible();
});
