/**
 * Shared authentication helpers for Playwright E2E tests.
 *
 * Uses the UniMonitor test admin account which the backend seeds
 * when UNIMONITOR_ENV=test (or when seeded via `unimonitor admin create`).
 */
import { type Page, expect } from '@playwright/test'

export const TEST_ADMIN = {
  email: 'admin@test.local',
  password: 'TestAdmin123!',
}

/**
 * Log in through the UI and wait until the dashboard is visible.
 */
export async function loginAsAdmin(page: Page): Promise<void> {
  await page.goto('/login')
  await expect(page.getByRole('heading', { name: /UniMonitor|Sign in/i })).toBeVisible()

  await page.getByLabel(/email/i).fill(TEST_ADMIN.email)
  await page.getByLabel(/password/i).fill(TEST_ADMIN.password)
  await page.getByRole('button', { name: /sign in|log in/i }).click()

  // Wait for redirect away from /login
  await page.waitForURL((url) => !url.pathname.startsWith('/login'), { timeout: 15_000 })
}

/**
 * Set auth token directly via localStorage (skips the login UI).
 * Use this when the test focuses on something OTHER than the login flow.
 */
export async function loginViaApi(page: Page): Promise<void> {
  // Hit the API login endpoint and store the token
  const response = await page.request.post('/api/v1/auth/login', {
    form: {
      username: TEST_ADMIN.email,
      password: TEST_ADMIN.password,
    },
  })

  if (response.ok()) {
    const data = await response.json()
    await page.addInitScript((token: string) => {
      localStorage.setItem('unimonitor_token', token)
    }, data.access_token)
  }
  // Navigate to trigger the React router guard with the token set
  await page.goto('/')
  await page.waitForURL((url) => !url.pathname.startsWith('/login'), { timeout: 15_000 })
}
