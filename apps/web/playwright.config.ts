import { defineConfig, devices } from "@playwright/test";

/**
 * End-to-end tests against a running stack (docker compose up, or `npm run dev`).
 * They exercise the real pipeline and the real indexed corpus — nothing is mocked except the
 * browser's speech engine in the voice test (browsers cannot be driven by real speech in CI).
 */
export default defineConfig({
  testDir: "./e2e",
  timeout: 180_000,
  // LLM-mode answers (classifier + generation + verification) take several seconds.
  expect: { timeout: 60_000 },
  fullyParallel: false,
  reporter: [["list"]],
  use: {
    baseURL: process.env.E2E_BASE_URL ?? "http://localhost:3000",
    trace: "retain-on-failure",
  },
  projects: [
    { name: "desktop", use: { ...devices["Desktop Chrome"] } },
    { name: "mobile", use: { ...devices["Pixel 7"] }, grep: /@mobile/ },
  ],
});
