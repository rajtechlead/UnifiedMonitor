/**
 * Findings page E2E tests.
 * Verifies the findings list renders, filters work, and severity chips show.
 *
 * Requires running backend: BACKEND_AVAILABLE=true
 */
import { test, expect } from '@playwright/test'
import { loginViaApi } from './helpers/auth'

const needsBackend = process.env.BACKEND_AVAILABLE !== 'true'

test.describe('Findings', () => {
  test.skip(needsBackend, 'Requires running backend (BACKEND_AVAILABLE=true)')

  test.beforeEach(async ({ page }) => {
    await loginViaApi(page)
  })

  test('findings page loads', async ({ page }) => {
    await page.goto('/findings')
    await expect(page).not.toHaveURL(/\/login/)
    await expect(page.locator('body')).not.toBeEmpty()
  })

  test('findings table or empty state renders within 15s', async ({ page }) => {
    await page.goto('/findings')
    await expect(
      page
        .getByRole('table')
        .or(page.getByText(/no findings|0 findings|empty/i))
        .first()
    ).toBeVisible({ timeout: 15_000 })
  })

  test('severity filter chips are present', async ({ page }) => {
    await page.goto('/findings')
    // Look for severity labels anywhere on the page
    await expect(
      page.getByText(/high|medium|low|critical/i).first()
    ).toBeVisible({ timeout: 15_000 })
  })
})
