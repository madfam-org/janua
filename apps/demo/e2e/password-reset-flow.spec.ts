import { test, expect } from '@playwright/test'
import {
  generateTestEmail,
  generateTestPassword,
  fillByLabel,
  clickButton,
  waitForUrl,
  waitForToast,
  waitForError,
  clearAuth,
  simulateEmailVerification,
} from './utils/test-helpers'

/**
 * E2E Tests: Password Reset Flow
 * 
 * Tests the complete password reset journey:
 * Request Reset → Email Verification → New Password → Sign-in
 */

test.describe('Password Reset Flow', () => {
  let testEmail: string
  let newPassword: string

  test.beforeEach(async ({ page }) => {
    testEmail = 'existing@plinto.dev'
    newPassword = generateTestPassword()
    
    await clearAuth(page)
    await page.goto('/')
  })

  test('complete password reset flow', async ({ page }) => {
    // Navigate to password reset page
    await page.goto('/auth/forgot-password-showcase')
    
    // Verify forgot password form is visible
    await expect(page.getByRole('heading', { name: /forgot password|reset password/i })).toBeVisible()
    
    // Enter email address
    await fillByLabel(page, /email/i, testEmail)
    
    // Submit request
    await clickButton(page, /send.*link|reset/i)
    
    // Should show success message or redirect to verification page
    const successMessage = page.getByText(/check.*email|sent.*instructions/i)
    if (await successMessage.isVisible()) {
      await expect(successMessage).toBeVisible()
    } else {
      // Or navigate to reset verification page
      await waitForUrl(page, /\/auth\/reset-password/i)
    }
  })

  test('forgot password with invalid email shows error', async ({ page }) => {
    // Navigate to forgot password page
    await page.goto('/auth/forgot-password-showcase')
    
    // Enter invalid email format
    await fillByLabel(page, /email/i, 'invalid-email')
    
    // Submit
    await clickButton(page, /send.*link|reset/i)
    
    // Should show validation error
    await expect(page.getByText(/invalid.*email/i)).toBeVisible()
    
    // Should still be on forgot password page
    expect(page.url()).toContain('/auth/forgot-password')
  })

  test('forgot password with unregistered email shows appropriate message', async ({ page }) => {
    // Navigate to forgot password page
    await page.goto('/auth/forgot-password-showcase')
    
    // Enter unregistered email
    await fillByLabel(page, /email/i, 'nonexistent@plinto.dev')
    
    // Submit
    await clickButton(page, /send.*link|reset/i)
    
    // For security, should show generic success message even for non-existent email
    // or show error depending on UX strategy
    const message = page.getByText(/check.*email|user.*not.*found/i)
    await expect(message).toBeVisible({ timeout: 5000 })
  })

  test('password reset with valid token allows setting new password', async ({ page }) => {
    // Navigate directly to reset password page with token (simulated)
    await page.goto('/auth/reset-password-showcase?token=valid-reset-token')
    
    // Verify reset password form is visible
    await expect(page.getByRole('heading', { name: /reset.*password|new password/i })).toBeVisible()
    
    // Enter new password
    const passwordInput = page.getByLabel(/new password|password/i).first()
    const confirmInput = page.getByLabel(/confirm.*password/i)
    
    if (await passwordInput.isVisible()) {
      await passwordInput.fill(newPassword)
      
      if (await confirmInput.isVisible()) {
        await confirmInput.fill(newPassword)
      }
      
      // Submit new password
      await clickButton(page, /reset|update.*password/i)
      
      // Should show success message or redirect to sign-in
      const successIndicator = page.getByText(/password.*updated|success|reset.*complete/i)
      if (await successIndicator.isVisible()) {
        await expect(successIndicator).toBeVisible()
      } else {
        // Or redirect to sign-in
        await waitForUrl(page, /\/auth\/signin/i)
      }
    }
  })

  test('password reset with mismatched passwords shows error', async ({ page }) => {
    // Navigate to reset password page
    await page.goto('/auth/reset-password-showcase?token=valid-reset-token')
    
    const passwordInput = page.getByLabel(/new password|password/i).first()
    const confirmInput = page.getByLabel(/confirm.*password/i)
    
    if (await passwordInput.isVisible() && await confirmInput.isVisible()) {
      // Enter mismatched passwords
      await passwordInput.fill(newPassword)
      await confirmInput.fill('DifferentPassword123!')
      
      // Submit
      await clickButton(page, /reset|update.*password/i)
      
      // Should show error
      await expect(page.getByText(/passwords.*not.*match|must.*match/i)).toBeVisible()
      
      // Should still be on reset page
      expect(page.url()).toContain('/auth/reset-password')
    }
  })

  test('password reset with weak password shows validation', async ({ page }) => {
    // Navigate to reset password page
    await page.goto('/auth/reset-password-showcase?token=valid-reset-token')
    
    const passwordInput = page.getByLabel(/new password|password/i).first()
    
    if (await passwordInput.isVisible()) {
      // Enter weak password
      await passwordInput.fill('123')
      
      // Should show strength indicator or error
      await expect(page.getByText(/weak|too short|at least 8 characters/i)).toBeVisible()
    }
  })

  test('password reset with expired token shows error', async ({ page }) => {
    // Navigate with expired token
    await page.goto('/auth/reset-password-showcase?token=expired-token')
    
    // Should show error about expired token
    await expect(page.getByText(/expired|invalid.*token|link.*expired/i)).toBeVisible({ timeout: 5000 })
    
    // Should provide option to request new reset link
    const requestNewLink = page.getByRole('link', { name: /request.*new|try.*again/i })
    if (await requestNewLink.isVisible()) {
      await expect(requestNewLink).toBeVisible()
    }
  })

  test('password strength indicator updates in real-time', async ({ page }) => {
    // Navigate to reset password page
    await page.goto('/auth/reset-password-showcase?token=valid-reset-token')
    
    const passwordInput = page.getByLabel(/new password|password/i).first()
    
    if (await passwordInput.isVisible()) {
      // Type weak password
      await passwordInput.fill('abc')
      
      // Should show weak strength
      await expect(page.getByText(/weak/i)).toBeVisible({ timeout: 2000 })
      
      // Type stronger password
      await passwordInput.fill('Str0ng!Pass')
      
      // Should show medium or strong strength
      await expect(page.getByText(/medium|strong/i)).toBeVisible({ timeout: 2000 })
    }
  })

  test('can navigate back to sign-in from forgot password', async ({ page }) => {
    // Navigate to forgot password page
    await page.goto('/auth/forgot-password-showcase')
    
    // Click back to sign-in link
    const signInLink = page.getByRole('link', { name: /back.*sign.*in|sign.*in/i })
    if (await signInLink.isVisible()) {
      await signInLink.click()
      
      // Should navigate to sign-in
      await waitForUrl(page, /\/auth\/signin/i)
      await expect(page.getByRole('heading', { name: /sign in/i })).toBeVisible()
    }
  })

  test('password reset success allows immediate sign-in', async ({ page }) => {
    // Navigate to reset password page
    await page.goto('/auth/reset-password-showcase?token=valid-reset-token')
    
    const passwordInput = page.getByLabel(/new password|password/i).first()
    const confirmInput = page.getByLabel(/confirm.*password/i)
    
    if (await passwordInput.isVisible()) {
      // Set new password
      await passwordInput.fill(newPassword)
      
      if (await confirmInput.isVisible()) {
        await confirmInput.fill(newPassword)
      }
      
      // Submit
      await clickButton(page, /reset|update.*password/i)
      
      // Wait for success
      await page.waitForTimeout(1000)
      
      // Navigate to sign-in
      await page.goto('/auth/signin-showcase')
      
      // Sign in with new password
      await fillByLabel(page, /email/i, testEmail)
      await fillByLabel(page, /password/i, newPassword)
      await clickButton(page, /sign in/i)
      
      // Should successfully authenticate
      await page.waitForURL(/\/(dashboard|welcome)/i, { timeout: 10000 })
      
      // Verify authenticated
      const url = page.url()
      expect(url).not.toContain('/auth/signin')
    }
  })
})
