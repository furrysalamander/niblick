import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./tests",
  timeout: 180_000,
  expect: { timeout: 180_000 },
  use: {
    baseURL: "http://127.0.0.1:4173",
    channel: "chrome",
    headless: true,
  },
  webServer: {
    command: "npm run preview -- --port 4173 --strictPort",
    port: 4173,
    reuseExistingServer: true,
    timeout: 120_000,
  },
});
