import { defineConfig } from "@playwright/test";

// E2E against the real FastAPI server serving the built SPA (run `npm run
// build` first). Locally it reuses a server already on :8123; in CI it always
// boots a fresh one so a stale build can't be silently tested.
// Local-only for now — CI runs lint/tsc/unit tiers instead.
export default defineConfig({
  testDir: "./e2e",
  timeout: 30_000,
  retries: 1,
  // cap parallelism when a single uvicorn+duckdb serves the suite — 10
  // workers of burst traffic can OOM duckdb on a loaded machine
  workers: process.env.CI ? 2 : 4,
  use: { baseURL: "http://127.0.0.1:8123" },
  projects: [{ name: "chromium", use: { browserName: "chromium" } }],
  webServer: {
    command: "python -m uvicorn web.api.main:app --port 8123 --log-level warning",
    cwd: "../..",
    url: "http://127.0.0.1:8123/api/health",
    reuseExistingServer: !process.env.CI,
    timeout: 30_000,
  },
});
