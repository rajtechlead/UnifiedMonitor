/**
 * Reports page E2E tests.
 * Verifies report listing and download/export buttons render correctly.
 *
 * Requires running backend: BACKEND_AVAILABLE=true
 */
import { test, expect } from '@playwright/test'
import { loginViaApi } from './helpers/auth'

const needsBackend = process.env.BACKEND_AVAILABLE !== 'true'

test.describe('Reports', () => {
  test.skip(needsBackend, 'Requires running backend (BACKEND_AVAILABLE=true)')

  test.beforeEach(async ({ page }) => {
    await loginViaApi(page)
  })

  test('reports page loads', async ({ page }) => {
    await page.goto('/reports')
    await expect(page).not.toHaveURL(/\/login/)
    await expect(page.locator('body')).not.toBeEmpty()
  })

  test('reports page shows table or empty state', async ({ page }) => {
    await page.goto('/reports')
    await expect(
      page
        .getByRole('table')
        .or(page.getByText(/no reports|run an assessment/i))
        .first()
    ).toBeVisible({ timeout: 15_000 })
  })

  test('generate/run report button is present', async ({ page }) => {
    await page.goto('/reports')
    await expect(
      page.getByRole('button', { name: /generate|run|new report/i })
    ).toBeVisible({ timeout: 15_000 })
  })
})
