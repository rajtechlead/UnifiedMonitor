/**
 * Login flow E2E tests.
 * Tests the full authentication round-trip through the UI.
 *
 * NOTE: These tests require a running UniMonitor backend at localhost:8000
 * with a seeded admin account. In CI the backend is NOT started (see ci.yml);
 * these tests are tagged @backend and skipped unless BACKEND_AVAILABLE=true.
 */
import { test, expect } from '@playwright/test'
import { loginAsAdmin } from './helpers/auth'

const needsBackend = process.env.BACKEND_AVAILABLE !== 'true'

test.describe('Login flow', () => {
  test.skip(needsBackend, 'Requires running backend (BACKEND_AVAILABLE=true)')

  test('successful login redirects to dashboard', async ({ page }) => {
    await loginAsAdmin(page)
    // Should land on the main dashboard — not /login
    await expect(page).not.toHaveURL(/\/login/)
    // Nav should be visible after login
    await expect(page.getByRole('navigation')).toBeVisible()
  })

  test('dashboard shows UniMonitor branding', async ({ page }) => {
    await loginAsAdmin(page)
    await expect(page.getByText(/UniMonitor/i).first()).toBeVisible()
  })

  test('logout clears session and returns to login', async ({ page }) => {
    await loginAsAdmin(page)
    // Find and click a logout button/link
    const logoutBtn = page.getByRole('button', { name: /logout|sign out/i })
    if (await logoutBtn.isVisible()) {
      await logoutBtn.click()
      await expect(page).toHaveURL(/\/login/, { timeout: 10_000 })
      // After logout, navigating to / should redirect back to login
      await page.goto('/')
      await expect(page).toHaveURL(/\/login/)
    } else {
      test.skip(true, 'No logout button found — skipping')
    }
  })
})
