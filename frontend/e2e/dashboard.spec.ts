/**
 * Dashboard rendering E2E tests.
 * Verifies that all three dashboard views render key UI elements.
 *
 * Uses API login (token injection) to avoid UI login overhead.
 * Requires running backend: BACKEND_AVAILABLE=true
 */
import { test, expect } from '@playwright/test'
import { loginViaApi } from './helpers/auth'

const needsBackend = process.env.BACKEND_AVAILABLE !== 'true'

test.describe('Executive Dashboard', () => {
  test.skip(needsBackend, 'Requires running backend (BACKEND_AVAILABLE=true)')

  test.beforeEach(async ({ page }) => {
    await loginViaApi(page)
  })

  test('renders compliance score tile', async ({ page }) => {
    await page.goto('/')
    // Should show some kind of score or percentage
    await expect(
      page.getByText(/compliance score|overall score|%/i).first()
    ).toBeVisible({ timeout: 15_000 })
  })

  test('renders at least one stat card', async ({ page }) => {
    await page.goto('/')
    // Cards / tiles should be present
    const cards = page.locator('[class*="card"], [class*="tile"], [class*="stat"]')
    await expect(cards.first()).toBeVisible({ timeout: 15_000 })
  })

  test('navigation links are present', async ({ page }) => {
    await page.goto('/')
    // These nav labels should appear for a fully-rendered app
    for (const label of ['Dashboard', 'Assessments', 'Findings']) {
      await expect(
        page.getByRole('link', { name: new RegExp(label, 'i') })
      ).toBeVisible()
    }
  })
})

test.describe('Security Dashboard', () => {
  test.skip(needsBackend, 'Requires running backend (BACKEND_AVAILABLE=true)')

  test.beforeEach(async ({ page }) => {
    await loginViaApi(page)
  })

  test('security dashboard page loads', async ({ page }) => {
    await page.goto('/security')
    await expect(page).not.toHaveURL(/\/login/)
    // Page should not throw a blank screen
    await expect(page.locator('body')).not.toBeEmpty()
  })
})

test.describe('Compliance Dashboard', () => {
  test.skip(needsBackend, 'Requires running backend (BACKEND_AVAILABLE=true)')

  test.beforeEach(async ({ page }) => {
    await loginViaApi(page)
  })

  test('compliance dashboard page loads', async ({ page }) => {
    await page.goto('/compliance')
    await expect(page).not.toHaveURL(/\/login/)
    await expect(page.locator('body')).not.toBeEmpty()
  })
})
