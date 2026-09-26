import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  timeout: 90000,
  reporter: "list",
  use: {
    baseURL: process.env.BOUSSLA_E2E_URL || "http://127.0.0.1:8000",
    browserName: "chromium",
    channel: "msedge",
    viewport: { width: 1440, height: 900 },
    headless: true,
  },
});
