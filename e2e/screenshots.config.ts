import { defineConfig } from "@playwright/test";

const API = "http://localhost:8001/api/v1";

export default defineConfig({
  testDir: "./screenshots",
  fullyParallel: false,
  workers: 1,
  timeout: 120_000,
  expect: { timeout: 15_000 },
  reporter: "list",
  use: { channel: process.env.CI ? undefined : "chrome", colorScheme: "light" },
  webServer: [
    {
      command: "uv run --directory ../services/api python -m app.e2e_server",
      url: `${API}/health`,
      env: { DINEMATE_E2E_HISTORY_DAYS: "21" },
      timeout: 240_000,
      reuseExistingServer: false,
    },
    {
      command: "pnpm --filter student exec vite --port 5183 --strictPort",
      url: "http://localhost:5183",
      env: { VITE_API_URL: API },
      timeout: 120_000,
      reuseExistingServer: false,
    },
    {
      command: "pnpm --filter console exec vite --port 5184 --strictPort",
      url: "http://localhost:5184",
      env: { VITE_API_URL: API },
      timeout: 120_000,
      reuseExistingServer: false,
    },
    {
      command: "pnpm --filter business exec vite --port 5185 --strictPort",
      url: "http://localhost:5185",
      env: { VITE_API_URL: API },
      timeout: 120_000,
      reuseExistingServer: false,
    },
  ],
});
