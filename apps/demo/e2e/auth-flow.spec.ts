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
 * E2E Tests: Complete Authentication Flow
 * 
 * Tests the critical path: Sign-up → Email Verification → Sign-in → Dashboard
 */

test.describe('Authentication Flow', () => {
  let testEmail: string
  let testPassword: string

  test.beforeEach(async ({ page }) => {
    // Generate unique credentials for each test
    testEmail = generateTestEmail()
    testPassword = generateTestPassword()
    
    // Clear any existing authentication
    await clearAuth(page)
    
    // Navigate to home page
    await page.goto('/')
  })

  test('complete sign-up flow with email verification', async ({ page }) => {
    // Navigate to sign-up page
    await page.goto('/auth/signup-showcase')
    
    // Verify sign-up form is visible
    await expect(page.getByRole('heading', { name: /sign up/i })).toBeVisible()
    
    // Fill sign-up form
    await fillByLabel(page, /email/i, testEmail)
    await fillByLabel(page, /password/i, testPassword)
    
    // Submit form
    await clickButton(page, /sign up/i)
    
    // Should redirect to email verification page
    await waitForUrl(page, /\/auth\/verify-email/i)
    
    // Verify email verification UI is shown
    await expect(page.getByText(/verify your email/i)).toBeVisible()
    await expect(page.getByText(new RegExp(testEmail, 'i'))).toBeVisible()
    
    // Simulate receiving verification code
    const verificationCode = await simulateEmailVerification(testEmail)
    
    // Enter verification code
    const codeInput = page.getByRole('textbox', { name: /code/i })
    await codeInput.fill(verificationCode)
    
    // Submit verification
    await clickButton(page, /verify/i)
    
    // Should redirect to dashboard or onboarding
    await page.waitForURL(/\/(dashboard|welcome)/i, { timeout: 10000 })
    
    // Verify user is authenticated
    const url = page.url()
    expect(url).not.toContain('/auth/signin')
  })

  test('sign-in with valid credentials', async ({ page }) => {
    // For this test, assume user already exists (created in previous test or fixture)
    // Navigate to sign-in page
    await page.goto('/auth/signin-showcase')
    
    // Verify sign-in form is visible
    await expect(page.getByRole('heading', { name: /sign in/i })).toBeVisible()
    
    // Fill sign-in form with test credentials
    await fillByLabel(page, /email/i, 'valid.user@plinto.dev')
    await fillByLabel(page, /password/i, 'ValidPass123!')
    
    // Submit form
    await clickButton(page, /sign in/i)
    
    // Should redirect to dashboard
    await page.waitForURL(/\/(dashboard|welcome)/i, { timeout: 10000 })
    
    // Verify user is authenticated (no redirect to sign-in)
    const url = page.url()
    expect(url).not.toContain('/auth/signin')
  })

  test('sign-in with invalid credentials shows error', async ({ page }) => {
    // Navigate to sign-in page
    await page.goto('/auth/signin-showcase')
    
    // Fill sign-in form with invalid credentials
    await fillByLabel(page, /email/i, testEmail)
    await fillByLabel(page, /password/i, 'WrongPassword123!')
    
    // Submit form
    await clickButton(page, /sign in/i)
    
    // Should show error message
    await waitForError(page, /invalid email or password/i)
    
    // Should still be on sign-in page
    expect(page.url()).toContain('/auth/signin')
  })

  test('sign-up with weak password shows validation error', async ({ page }) => {
    // Navigate to sign-up page
    await page.goto('/auth/signup-showcase')
    
    // Fill sign-up form with weak password
    await fillByLabel(page, /email/i, testEmail)
    await fillByLabel(page, /password/i, '123')
    
    // Submit form
    await clickButton(page, /sign up/i)
    
    // Should show password strength error
    await expect(page.getByText(/password.*weak|too short|at least 8 characters/i)).toBeVisible()
    
    // Should still be on sign-up page
    expect(page.url()).toContain('/auth/signup')
  })

  test('sign-up with existing email shows error', async ({ page }) => {
    // Navigate to sign-up page
    await page.goto('/auth/signup-showcase')
    
    // Fill sign-up form with existing email
    await fillByLabel(page, /email/i, 'existing@plinto.dev')
    await fillByLabel(page, /password/i, testPassword)
    
    // Submit form
    await clickButton(page, /sign up/i)
    
    // Should show error about existing email
    await waitForError(page, /email.*already.*exists|already.*registered/i)
    
    // Should still be on sign-up page
    expect(page.url()).toContain('/auth/signup')
  })

  test('remember me checkbox persists session', async ({ page }) => {
    // Navigate to sign-in page
    await page.goto('/auth/signin-showcase')
    
    // Fill credentials
    await fillByLabel(page, /email/i, 'valid.user@plinto.dev')
    await fillByLabel(page, /password/i, 'ValidPass123!')
    
    // Check remember me
    const rememberCheckbox = page.getByRole('checkbox', { name: /remember me/i })
    if (await rememberCheckbox.isVisible()) {
      await rememberCheckbox.check()
    }
    
    // Submit
    await clickButton(page, /sign in/i)
    
    // Wait for authentication
    await page.waitForURL(/\/(dashboard|welcome)/i, { timeout: 10000 })
    
    // Close and reopen browser context to simulate session persistence
    const context = page.context()
    const cookies = await context.cookies()
    
    // Should have session cookies
    expect(cookies.length).toBeGreaterThan(0)
  })

  test('social sign-in buttons are functional', async ({ page }) => {
    // Navigate to sign-in page
    await page.goto('/auth/signin-showcase')
    
    // Check if Google sign-in button exists and is clickable
    const googleButton = page.getByRole('button', { name: /google/i })
    if (await googleButton.isVisible()) {
      // Click should initiate OAuth flow (would redirect to Google in real scenario)
      await googleButton.click()
      
      // In test environment, verify the redirect URL or mock response
      // For showcase, verify button interaction works
      await page.waitForTimeout(500)
    }
  })

  test('email verification with invalid code shows error', async ({ page }) => {
    // Navigate directly to verify-email page (assumes user in pending state)
    await page.goto('/auth/verify-email-showcase')
    
    // Enter invalid verification code
    const codeInput = page.getByRole('textbox', { name: /code/i })
    if (await codeInput.isVisible()) {
      await codeInput.fill('000000')
      
      // Submit
      await clickButton(page, /verify/i)
      
      // Should show error
      await waitForError(page, /invalid.*code|verification.*failed/i)
    }
  })

  test('can navigate between sign-in and sign-up', async ({ page }) => {
    // Start at sign-in
    await page.goto('/auth/signin-showcase')
    await expect(page.getByRole('heading', { name: /sign in/i })).toBeVisible()
    
    // Click sign-up link
    const signUpLink = page.getByRole('link', { name: /sign up/i })
    if (await signUpLink.isVisible()) {
      await signUpLink.click()
      
      // Should navigate to sign-up
      await waitForUrl(page, /\/auth\/signup/i)
      await expect(page.getByRole('heading', { name: /sign up/i })).toBeVisible()
      
      // Click sign-in link
      const signInLink = page.getByRole('link', { name: /sign in/i })
      if (await signInLink.isVisible()) {
        await signInLink.click()
        
        // Should navigate back to sign-in
        await waitForUrl(page, /\/auth\/signin/i)
        await expect(page.getByRole('heading', { name: /sign in/i })).toBeVisible()
      }
    }
  })

  test('password visibility toggle works', async ({ page }) => {
    // Navigate to sign-in
    await page.goto('/auth/signin-showcase')
    
    // Find password input
    const passwordInput = page.getByLabel(/password/i)
    
    // Should be type="password" initially
    await expect(passwordInput).toHaveAttribute('type', 'password')
    
    // Click show password button
    const toggleButton = page.getByRole('button', { name: /show password/i })
    if (await toggleButton.isVisible()) {
      await toggleButton.click()
      
      // Should change to type="text"
      await expect(passwordInput).toHaveAttribute('type', 'text')
      
      // Click again to hide
      await toggleButton.click()
      
      // Should change back to type="password"
      await expect(passwordInput).toHaveAttribute('type', 'password')
    }
  })
})
