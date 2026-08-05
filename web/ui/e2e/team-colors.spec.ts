import { expect, test } from "@playwright/test";

const ACCENT = "rgb(76, 141, 255)"; // --color-accent #4c8dff

/** The whole point of wave 4: a link must look like a link on every page.
 *  Before this, team pages reassigned --accent to the team colour, so
 *  "clickable" was blue on one page and red on the next. */
for (const code of ["KC", "PHI", "LV", "MIA", "BAL"]) {
  test(`${code} page keeps the fixed accent for interactive elements`, async ({ page }) => {
    await page.goto(`/team/${code}`);
    await page.getByRole("heading", { level: 1 }).waitFor();

    const accent = await page.evaluate(() =>
      getComputedStyle(document.documentElement).getPropertyValue("--color-accent").trim());
    expect(accent.toLowerCase()).toBe("#4c8dff");

    const active = page.getByRole("button", { name: "Overview" });
    await expect(active).toHaveCSS("color", ACCENT);
  });
}

test("team identity survives as a token, distinct per team", async ({ page }) => {
  const inks: Record<string, string> = {};
  for (const code of ["BAL", "SEA", "KC", "MIA"]) {
    await page.goto(`/team/${code}`);
    await page.getByRole("heading", { level: 1 }).waitFor();
    inks[code] = await page.evaluate(() => {
      const root = document.querySelector("main > div") as HTMLElement;
      return getComputedStyle(root).getPropertyValue("--team-ink").trim();
    });
  }
  // glow_safe blended toward white, which desaturates: Ravens purple and
  // Seahawks navy both came out the same lavender-grey.
  expect(new Set(Object.values(inks)).size).toBe(4);
  for (const [code, ink] of Object.entries(inks)) {
    expect(ink, `${code} has no team ink`).toMatch(/^#|^rgb/);
  }
});
