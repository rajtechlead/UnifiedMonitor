import { defineConfig, devices } from '@playwright/test'

/**
 * Playwright E2E configuration for UniMonitor frontend.
 *
 * Tests run against:
 *   - A locally-started Vite dev server (port 3000) with the backend at 8000
 *   - In CI: the app is served via `npm run preview` after `npm run build`
 *
 * @see https://playwright.dev/docs/test-configuration
 */
export default defineConfig({
  testDir: './e2e',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: process.env.CI
    ? [['html', { open: 'never' }], ['github']]
    : [['html', { open: 'on-failure' }]],

  use: {
    baseURL: process.env.PLAYWRIGHT_BASE_URL || 'http://localhost:3000',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
    // Increase timeout for slower CI runners
    actionTimeout: 15_000,
    navigationTimeout: 30_000,
  },

  projects: [
    // Desktop browsers
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
    {
      name: 'firefox',
      use: { ...devices['Desktop Firefox'] },
    },
    // Mobile viewport smoke test
    {
      name: 'mobile-chrome',
      use: { ...devices['Pixel 5'] },
      testMatch: '**/smoke.spec.ts',
    },
  ],

  // Start vite dev server for local runs; in CI the app is pre-built & served
  webServer: process.env.CI
    ? {
        command: 'npm run preview -- --port 3000',
        port: 3000,
        reuseExistingServer: false,
        timeout: 60_000,
      }
    : {
        command: 'npm run dev',
        port: 3000,
        reuseExistingServer: true,
        timeout: 60_000,
      },
})
