import { expect, test, type Page } from "@playwright/test";

/* Chat entry points: the AskAnalyst chip on pages and the starter chips in
 * the chat empty state. The chat backend is stubbed at the network edge —
 * /api/chat/stream is fulfilled with a canned SSE body — so no `claude -p`
 * subprocess ever spawns and the spec is identical in real-DB and fixture
 * modes. Navigation sticks to fixture-safe entities (DEN @ KC, week 1 2026). */

const REPLY = "Stubbed analyst reply for e2e.";
const SSE_BODY = [
  "event: session",
  'data: {"session_id": "e2e-stub"}',
  "",
  "event: token",
  'data: {"text": "Stubbed analyst reply "}',
  "",
  "event: token",
  'data: {"text": "for e2e."}',
  "",
  "event: done",
  `data: {"text": "${REPLY}", "session_id": "e2e-stub"}`,
  "",
  "",
].join("\n");

const stubChat = (page: Page) =>
  page.route("**/api/chat/stream", (route) =>
    route.fulfill({ status: 200, contentType: "text/event-stream", body: SSE_BODY }));

const dialog = (page: Page) => page.getByRole("dialog", { name: "Analyst chat" });

test("Ask-the-analyst chip renders on a matchup page and on the betting board", async ({ page }) => {
  await page.goto("/matchup/2026_01_DEN_KC");
  await expect(page.getByRole("button", { name: "Ask the analyst" })).toBeVisible();

  await page.goto("/betting");
  await expect(page.getByRole("button", { name: "Ask the analyst" })).toBeVisible();
});

test("clicking the chip opens the overlay and streams the stubbed reply", async ({ page }) => {
  await stubChat(page);
  await page.goto("/matchup/2026_01_DEN_KC");
  await page.getByRole("button", { name: "Ask the analyst" }).click();

  await expect(dialog(page)).toBeVisible();
  // the pre-baked question lands as the user message…
  await expect(dialog(page).getByText(/Break down .* @ .*: edges, injuries/)).toBeVisible();
  // …and the stubbed SSE tokens stream in as the assistant reply
  await expect(dialog(page).getByText(REPLY)).toBeVisible();
});

test("fresh chat on /betting offers 4 starter chips and a chip submits", async ({ page }) => {
  await stubChat(page);
  await page.goto("/betting");

  // open chat empty (no question) via the palette's Ask-the-analyst command
  await page.getByRole("button", { name: "Open command palette" }).waitFor();
  await page.keyboard.press("Control+k");
  await page.getByLabel("Search pages, teams and players").fill(">");
  // accessible name includes the hint ("opens the chat"), so match loosely
  await page.getByRole("option", { name: /Ask the analyst/ }).click();

  await expect(dialog(page)).toBeVisible();
  const chips = dialog(page)
    .getByRole("group", { name: "Starter questions" })
    .getByRole("button");
  await expect(chips).toHaveCount(4);

  const question = (await chips.first().innerText()).trim();
  await chips.first().click();
  // the chip's question becomes the user message and the stub replies
  await expect(dialog(page).getByText(question, { exact: true })).toBeVisible();
  await expect(dialog(page).getByText(REPLY)).toBeVisible();
});
