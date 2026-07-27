import { defineConfig } from '@playwright/test'

/**
 * Live audit configuration: attaches to the already-running cloud-local stack
 * (scripts/start-cloud-local.ps1) instead of starting its own dev server.
 * Run with: BRP_LIVE_AUDIT=1 npx playwright test -c playwright.live.config.ts
 */
export default defineConfig({
  testDir: './e2e',
  testMatch: /live-audit\.spec\.ts/,
  outputDir: '../output/playwright/live-results',
  reporter: 'line',
  workers: 1,
  use: {
    baseURL: process.env.BRP_LIVE_UI ?? 'http://127.0.0.1:5173',
    viewport: { width: 1440, height: 1000 },
    trace: 'retain-on-failure',
  },
})
