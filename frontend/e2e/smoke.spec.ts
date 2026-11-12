/**
 * Smoke tests — fast, no auth required.
 * Verify the app loads, shows the login page, and key assets respond.
 */
import { test, expect } from '@playwright/test'

test.describe('Smoke — public pages', () => {
  test('root redirects to /login when unauthenticated', async ({ page }) => {
    await page.goto('/')
    await expect(page).toHaveURL(/\/login/)
  })

  test('login page renders', async ({ page }) => {
    await page.goto('/login')
    // Title should include UniMonitor
    await expect(page).toHaveTitle(/UniMonitor/i)
    // Should have an email field, password field and a submit button
    await expect(page.getByLabel(/email/i)).toBeVisible()
    await expect(page.getByLabel(/password/i)).toBeVisible()
    await expect(page.getByRole('button', { name: /sign in|log in/i })).toBeVisible()
  })

  test('login page shows "Sign in with Microsoft" button', async ({ page }) => {
    await page.goto('/login')
    await expect(
      page.getByRole('button', { name: /microsoft|entra|azure/i })
    ).toBeVisible()
  })

  test('invalid login shows error message', async ({ page }) => {
    await page.goto('/login')
    await page.getByLabel(/email/i).fill('nobody@nowhere.invalid')
    await page.getByLabel(/password/i).fill('wrongpassword')
    await page.getByRole('button', { name: /sign in|log in/i }).click()
    // Should show an error — not redirect
    await expect(page).toHaveURL(/\/login/)
    await expect(
      page.getByText(/invalid|incorrect|credentials|error/i)
    ).toBeVisible({ timeout: 10_000 })
  })
})
