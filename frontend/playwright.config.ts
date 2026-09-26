import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  testMatch: "*.spec.ts",
  timeout: 90000,
  // One shared real service/database: specs must not run concurrently.
  fullyParallel: false,
  workers: 1,
  reporter: "list",
  use: {
    baseURL: process.env.BOUSSLA_E2E_URL || "http://127.0.0.1:8000",
    browserName: "chromium",
    channel: "msedge",
    viewport: { width: 1440, height: 900 },
    headless: true,
  },
});
