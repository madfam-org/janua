import { Page, expect } from '@playwright/test'

/**
 * Test helper utilities for Plinto E2E tests
 */

/**
 * Generate unique test email address
 */
export function generateTestEmail(): string {
  const timestamp = Date.now()
  const random = Math.floor(Math.random() * 10000)
  return `test-${timestamp}-${random}@plinto.dev`
}

/**
 * Generate test phone number
 */
export function generateTestPhone(): string {
  const random = Math.floor(Math.random() * 1000000000)
  return `+1555${String(random).padStart(7, '0').slice(0, 7)}`
}

/**
 * Generate strong test password
 */
export function generateTestPassword(): string {
  return `Test${Date.now()}!Pass`
}

/**
 * Wait for navigation and verify URL
 */
export async function waitForUrl(page: Page, urlPattern: string | RegExp) {
  await page.waitForURL(urlPattern, { timeout: 10000 })
}

/**
 * Fill input field by label
 */
export async function fillByLabel(page: Page, label: string | RegExp, value: string) {
  await page.getByLabel(label).fill(value)
}

/**
 * Click button by role and name
 */
export async function clickButton(page: Page, name: string | RegExp) {
  await page.getByRole('button', { name }).click()
}

/**
 * Wait for toast notification
 */
export async function waitForToast(page: Page, message: string | RegExp) {
  await expect(page.getByRole('status').getByText(message)).toBeVisible({ timeout: 5000 })
}

/**
 * Wait for error message
 */
export async function waitForError(page: Page, message: string | RegExp) {
  await expect(page.getByRole('alert').getByText(message)).toBeVisible({ timeout: 5000 })
}

/**
 * Check if user is authenticated by verifying protected page access
 */
export async function isAuthenticated(page: Page): Promise<boolean> {
  const url = page.url()
  return !url.includes('/auth/signin') && !url.includes('/auth/signup')
}

/**
 * Simulate email verification (mock backend interaction)
 */
export async function simulateEmailVerification(email: string): Promise<string> {
  // In real tests, this would interact with test email service or mock API
  // For now, return a mock verification code
  return '123456'
}

/**
 * Simulate SMS verification code
 */
export async function simulateSMSCode(phone: string): Promise<string> {
  // In real tests, this would interact with test SMS service or mock API
  return '654321'
}

/**
 * Clear all cookies and local storage
 */
export async function clearAuth(page: Page) {
  await page.context().clearCookies()
  await page.evaluate(() => {
    localStorage.clear()
    sessionStorage.clear()
  })
}
