import { defineConfig } from "@playwright/test";
export default defineConfig({
  testDir: "./e2e",
  timeout: 60000,
  use: {
    baseURL: process.env.ASHEN_E2E_URL ?? "http://localhost:8180",
    headless: true,
    launchOptions: process.env.CHROME_PATH
      ? { executablePath: process.env.CHROME_PATH }
      : {},
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  workers: 1,
});
