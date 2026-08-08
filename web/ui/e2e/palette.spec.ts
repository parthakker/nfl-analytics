import { expect, test } from "@playwright/test";

const open = async (page: import("@playwright/test").Page) => {
  await page.goto("/");
  // wait for React to mount before the keystroke — the listener is in Shell
  await page.getByRole("button", { name: "Open command palette" }).waitFor();
  await page.keyboard.press("Control+k");
  await expect(page.getByRole("dialog", { name: "Command palette" })).toBeVisible();
};

test("Ctrl-K opens the palette and jumps to a page", async ({ page }) => {
  await open(page);
  await page.getByLabel("Search pages, teams and players").fill("standings");
  await page.getByRole("option", { name: /Teams & standings/ }).click();
  await expect(page).toHaveURL(/\/teams$/);
});

test("palette finds a team by name and by code", async ({ page }) => {
  await open(page);
  await page.getByLabel("Search pages, teams and players").fill("Ravens");
  await page.getByRole("option", { name: /Baltimore Ravens/ }).click();
  await expect(page).toHaveURL(/\/team\/BAL$/);
});

test("> switches to command mode", async ({ page }) => {
  await open(page);
  await page.getByLabel("Search pages, teams and players").fill(">density");
  await expect(page.getByRole("option", { name: /Density: compact/ })).toBeVisible();
  await page.getByRole("option", { name: /Density: compact/ }).click();
  await expect(page.locator("html")).toHaveAttribute("data-density", "compact");
});

test("? hands the question to the analyst", async ({ page }) => {
  await open(page);
  await page.getByLabel("Search pages, teams and players").fill("?who led the league in rushing");
  await expect(page.getByRole("option", { name: /Ask the analyst/ })).toBeVisible();
});

test("arrow keys move the selection and Escape closes", async ({ page }) => {
  await open(page);
  await page.keyboard.press("ArrowDown");
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog", { name: "Command palette" })).toBeHidden();
});
