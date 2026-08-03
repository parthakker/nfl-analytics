import { defineConfig } from "@playwright/test";

// E2E against the real FastAPI server serving the built SPA (run `npm run
// build` first). Reuses a server already on :8123; otherwise boots one from
// the repo root. Local-only for now — CI runs lint/tsc/unit tiers instead.
export default defineConfig({
  testDir: "./e2e",
  timeout: 30_000,
  retries: 0,
  use: { baseURL: "http://127.0.0.1:8123" },
  projects: [{ name: "chromium", use: { browserName: "chromium" } }],
  webServer: {
    command: "python -m uvicorn web.api.main:app --port 8123 --log-level warning",
    cwd: "../..",
    url: "http://127.0.0.1:8123/api/health",
    reuseExistingServer: true,
    timeout: 30_000,
  },
});
