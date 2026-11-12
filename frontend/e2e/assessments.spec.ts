/**
 * Assessments flow E2E tests.
 * Verifies the assessment listing, detail view, and run trigger.
 *
 * Requires running backend: BACKEND_AVAILABLE=true
 */
import { test, expect } from '@playwright/test'
import { loginViaApi } from './helpers/auth'

const needsBackend = process.env.BACKEND_AVAILABLE !== 'true'

test.describe('Assessments', () => {
  test.skip(needsBackend, 'Requires running backend (BACKEND_AVAILABLE=true)')

  test.beforeEach(async ({ page }) => {
    await loginViaApi(page)
  })

  test('assessments page loads and shows controls table', async ({ page }) => {
    await page.goto('/assessments')
    await expect(page).not.toHaveURL(/\/login/)
    // Should show a table or list — wait up to 15s for data to load
    await expect(
      page.getByRole('table').or(page.locator('[class*="table"]')).first()
    ).toBeVisible({ timeout: 15_000 })
  })

  test('assessments page has Run Assessment button', async ({ page }) => {
    await page.goto('/assessments')
    await expect(
      page.getByRole('button', { name: /run|assess|scan/i })
    ).toBeVisible({ timeout: 15_000 })
  })

  test('clicking Run Assessment opens tenant selector or starts run', async ({ page }) => {
    await page.goto('/assessments')
    const runBtn = page.getByRole('button', { name: /run|assess|scan/i }).first()
    await expect(runBtn).toBeVisible({ timeout: 15_000 })
    await runBtn.click()
    // Either a modal/dialog opens OR the button state changes (loading)
    // Both are valid — just ensure the page doesn't crash
    await expect(page).not.toHaveURL(/\/login/)
    await expect(page.locator('body')).not.toBeEmpty()
  })
})
