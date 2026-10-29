import { defineConfig } from "@playwright/test";

const API = "http://localhost:8001/api/v1";
const inCi = Boolean(process.env.CI);

export default defineConfig({
  testDir: "./tests",
  fullyParallel: false,
  workers: 1,
  retries: inCi ? 1 : 0,
  timeout: 60_000,
  expect: { timeout: 15_000 },
  reporter: inCi ? [["list"], ["html", { open: "never" }]] : "list",
  use: {
    channel: inCi ? undefined : "chrome",
    trace: "retain-on-failure",
    viewport: { width: 1280, height: 860 },
  },
  webServer: [
    {
      command: "uv run --directory ../services/api python -m app.e2e_server",
      url: `${API}/health`,
      timeout: 180_000,
      reuseExistingServer: false,
      stdout: "pipe",
    },
    {
      command: "pnpm --filter student exec vite --port 5183 --strictPort",
      url: "http://localhost:5183",
      env: { VITE_API_URL: API },
      timeout: 120_000,
      reuseExistingServer: false,
    },
    {
      command: "pnpm --filter student build && pnpm --filter student exec vite preview --port 4183 --strictPort",
      url: "http://localhost:4183",
      env: { VITE_API_URL: API },
      timeout: 240_000,
      reuseExistingServer: false,
    },
    {
      command: "pnpm --filter console exec vite --port 5184 --strictPort",
      url: "http://localhost:5184",
      env: { VITE_API_URL: API },
      timeout: 120_000,
      reuseExistingServer: false,
    },
  ],
});
