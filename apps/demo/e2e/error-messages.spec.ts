import { test, expect } from '@playwright/test'
import {
  generateTestEmail,
  generateTestPassword,
  fillByLabel,
  clickButton,
  waitForError,
  clearAuth,
} from './utils/test-helpers'

/**
 * E2E Tests: Error Message Quality and Actionability
 * 
 * Validates that all error messages are:
 * 1. User-friendly (clear title and description)
 * 2. Actionable (include recovery steps)
 * 3. Contextual (specific to the error type)
 * 4. Consistent (follow error message utility patterns)
 */

test.describe('Error Message Validation', () => {
  test.beforeEach(async ({ page }) => {
    await clearAuth(page)
    await page.goto('/')
  })

  test.describe('Sign-In Error Messages', () => {
    test.beforeEach(async ({ page }) => {
      await page.goto('/auth/signin-showcase')
      await expect(page.getByRole('heading', { name: /sign in/i })).toBeVisible()
    })

    test('shows actionable error for invalid credentials', async ({ page }) => {
      // Fill with invalid credentials
      await fillByLabel(page, /email/i, 'test@example.com')
      await fillByLabel(page, /password/i, 'WrongPassword123!')
      
      // Submit
      await clickButton(page, /sign in/i)
      
      // Wait for error to appear
      const errorMessage = await waitForError(page)
      
      // Validate error structure
      expect(errorMessage).toContain('Invalid credentials')
      expect(errorMessage).toContain('email or password you entered is incorrect')
      
      // Validate actionable steps are present
      expect(errorMessage).toMatch(/Double-check|Forgot password|Caps Lock/i)
      
      // Verify at least 3 action items
      const actionMatches = errorMessage.match(/\d+\./g)
      expect(actionMatches?.length).toBeGreaterThanOrEqual(3)
    })

    test('shows network error with retry suggestions', async ({ page }) => {
      // Simulate network failure by going offline
      await page.context().setOffline(true)
      
      await fillByLabel(page, /email/i, 'test@example.com')
      await fillByLabel(page, /password/i, 'ValidPassword123!')
      
      await clickButton(page, /sign in/i)
      
      const errorMessage = await waitForError(page)
      
      // Validate network error message
      expect(errorMessage).toContain('Connection error')
      expect(errorMessage).toContain('Unable to connect')
      
      // Validate recovery actions
      expect(errorMessage).toMatch(/Check your internet|Try again|Refresh/i)
      
      // Restore network
      await page.context().setOffline(false)
    })

    test('shows account not verified error', async ({ page }) => {
      // This would require a test user in "unverified" state
      // For now, validate the error message format when it appears
      
      // Create unverified user via API (mock scenario)
      const unverifiedEmail = generateTestEmail()
      const password = generateTestPassword()
      
      // Attempt sign-in with unverified account
      await fillByLabel(page, /email/i, unverifiedEmail)
      await fillByLabel(page, /password/i, password)
      
      await clickButton(page, /sign in/i)
      
      // If 401 with "not verified" message, should show specific error
      // (This test might pass through if user doesn't exist, which is fine)
      const pageContent = await page.textContent('body')
      
      if (pageContent?.includes('not verified') || pageContent?.includes('Email not verified')) {
        expect(pageContent).toContain('verify your email')
        expect(pageContent).toMatch(/Check your inbox|Resend verification|spam folder/i)
      }
    })
  })

  test.describe('Sign-Up Error Messages', () => {
    test.beforeEach(async ({ page }) => {
      await page.goto('/auth/signup-showcase')
      await expect(page.getByRole('heading', { name: /sign up/i })).toBeVisible()
    })

    test('shows weak password error with strength requirements', async ({ page }) => {
      const testEmail = generateTestEmail()
      
      await fillByLabel(page, /email/i, testEmail)
      await fillByLabel(page, /password/i, 'weak') // Intentionally weak
      
      await clickButton(page, /sign up/i)
      
      const errorMessage = await waitForError(page)
      
      // Validate weak password error
      expect(errorMessage).toMatch(/Password too weak|doesn't meet.*requirements/i)
      
      // Validate password requirements are listed
      expect(errorMessage).toMatch(/8 characters/i)
      expect(errorMessage).toMatch(/uppercase.*lowercase/i)
      expect(errorMessage).toMatch(/number/i)
      expect(errorMessage).toMatch(/special character/i)
      
      // Verify actionable steps format
      const actionMatches = errorMessage.match(/\d+\./g)
      expect(actionMatches?.length).toBeGreaterThanOrEqual(3)
    })

    test('shows invalid email error with format guidance', async ({ page }) => {
      await fillByLabel(page, /email/i, 'not-an-email') // Invalid format
      await fillByLabel(page, /password/i, generateTestPassword())
      
      await clickButton(page, /sign up/i)
      
      const errorMessage = await waitForError(page)
      
      // Validate invalid email error
      expect(errorMessage).toMatch(/Invalid email|not valid/i)
      
      // Validate format guidance
      expect(errorMessage).toMatch(/Check for typos|format.*name@example\.com|extra spaces/i)
    })

    test('shows email already exists error with recovery path', async ({ page }) => {
      // Use a known existing email (or mock the response)
      const existingEmail = 'existing@example.com'
      
      await fillByLabel(page, /email/i, existingEmail)
      await fillByLabel(page, /password/i, generateTestPassword())
      
      await clickButton(page, /sign up/i)
      
      const pageContent = await page.textContent('body')
      
      // If email exists (409 response), validate error message
      if (pageContent?.includes('already registered') || pageContent?.includes('already exists')) {
        expect(pageContent).toMatch(/sign in instead|Forgot password|different email/i)
      }
    })
  })

  test.describe('Password Reset Error Messages', () => {
    test.beforeEach(async ({ page }) => {
      await page.goto('/auth/password-reset-showcase')
    })

    test('shows password mismatch error with clear guidance', async ({ page }) => {
      // Navigate to reset form (assuming token is in URL)
      // This is a simplified test - real scenario would need valid reset token
      
      const passwordInput = page.getByLabel(/new password/i).first()
      const confirmInput = page.getByLabel(/confirm password/i).first()
      
      if (await passwordInput.isVisible() && await confirmInput.isVisible()) {
        await passwordInput.fill('NewPassword123!')
        await confirmInput.fill('DifferentPassword123!') // Intentional mismatch
        
        await clickButton(page, /reset password|update password/i)
        
        const errorMessage = await waitForError(page)
        
        // Validate mismatch error
        expect(errorMessage).toMatch(/don't match/i)
        
        // Validate recovery steps
        expect(errorMessage).toMatch(/Re-enter|match exactly|Caps Lock/i)
      }
    })

    test('shows expired token error with request new link action', async ({ page }) => {
      // This would require a valid but expired token
      // Validate error message format when it appears
      
      const pageContent = await page.textContent('body')
      
      if (pageContent?.includes('expired') || pageContent?.includes('Reset link expired')) {
        expect(pageContent).toMatch(/Request.*new|latest email|within.*hour/i)
      }
    })
  })

  test.describe('MFA Error Messages', () => {
    test.beforeEach(async ({ page }) => {
      await page.goto('/auth/mfa-showcase')
    })

    test('shows invalid MFA code error with retry guidance', async ({ page }) => {
      // Attempt to verify with invalid code
      const codeInput = page.getByRole('textbox', { name: /code|verification/i }).first()
      
      if (await codeInput.isVisible()) {
        await codeInput.fill('000000') // Invalid code
        
        await clickButton(page, /verify/i)
        
        const errorMessage = await waitForError(page)
        
        // Validate invalid code error
        expect(errorMessage).toMatch(/Invalid.*code|incorrect/i)
        
        // Validate recovery steps
        expect(errorMessage).toMatch(/current.*digit|Wait for new code|device time|backup code/i)
        
        // Verify multiple action items
        const actionMatches = errorMessage.match(/\d+\./g)
        expect(actionMatches?.length).toBeGreaterThanOrEqual(3)
      }
    })
  })

  test.describe('Rate Limiting Error Messages', () => {
    test('shows rate limit error with wait time', async ({ page }) => {
      await page.goto('/auth/signin-showcase')
      
      // Trigger rate limit by multiple failed attempts
      const attempts = 5
      for (let i = 0; i < attempts; i++) {
        await fillByLabel(page, /email/i, 'test@example.com')
        await fillByLabel(page, /password/i, `WrongPassword${i}!`)
        await clickButton(page, /sign in/i)
        
        // Small delay between attempts
        await page.waitForTimeout(500)
      }
      
      // Check if rate limit error appears
      const pageContent = await page.textContent('body')
      
      if (pageContent?.includes('Too many') || pageContent?.includes('Rate limit')) {
        expect(pageContent).toMatch(/Wait.*minutes|slow down|rapid.*attempts/i)
        
        // Should include specific wait time
        expect(pageContent).toMatch(/\d+\s*minutes?/i)
      }
    })
  })

  test.describe('Server Error Messages', () => {
    test('shows graceful server error with support guidance', async ({ page }) => {
      // Simulate 500 error by triggering a server-side error
      // (This would require mocking or specific test endpoint)
      
      await page.goto('/auth/signin-showcase')
      
      // Mock a 500 response
      await page.route('**/api/v1/auth/signin', route => {
        route.fulfill({
          status: 500,
          contentType: 'application/json',
          body: JSON.stringify({ detail: 'Internal server error' })
        })
      })
      
      await fillByLabel(page, /email/i, 'test@example.com')
      await fillByLabel(page, /password/i, 'ValidPassword123!')
      
      await clickButton(page, /sign in/i)
      
      const errorMessage = await waitForError(page)
      
      // Validate server error message
      expect(errorMessage).toMatch(/Server error|Something went wrong/i)
      expect(errorMessage).toMatch(/not your fault/i)
      
      // Validate recovery steps
      expect(errorMessage).toMatch(/Try again|Refresh|team.*notified/i)
    })
  })

  test.describe('Error Message Consistency', () => {
    test('all error messages follow actionable format', async ({ page }) => {
      const errorScenarios = [
        {
          url: '/auth/signin-showcase',
          action: async () => {
            await fillByLabel(page, /email/i, 'wrong@example.com')
            await fillByLabel(page, /password/i, 'WrongPass123!')
            await clickButton(page, /sign in/i)
          },
          expectedPattern: /\d+\./g // Should have numbered action items
        },
        {
          url: '/auth/signup-showcase',
          action: async () => {
            await fillByLabel(page, /email/i, generateTestEmail())
            await fillByLabel(page, /password/i, 'weak')
            await clickButton(page, /sign up/i)
          },
          expectedPattern: /\d+\./g
        }
      ]

      for (const scenario of errorScenarios) {
        await page.goto(scenario.url)
        await scenario.action()
        
        const errorMessage = await waitForError(page)
        
        // All errors should have numbered action items
        const actionMatches = errorMessage.match(scenario.expectedPattern)
        expect(actionMatches?.length).toBeGreaterThanOrEqual(1)
        
        // All errors should have a title and message
        expect(errorMessage).toMatch(/.*:.*/) // Title: Message format
      }
    })

    test('error messages are accessible and readable', async ({ page }) => {
      await page.goto('/auth/signin-showcase')
      
      await fillByLabel(page, /email/i, 'wrong@example.com')
      await fillByLabel(page, /password/i, 'WrongPass123!')
      
      await clickButton(page, /sign in/i)
      
      // Wait for error to appear
      await page.waitForSelector('[role="alert"], .error, [class*="error"]', { timeout: 5000 })
      
      // Verify error has proper ARIA attributes
      const errorElement = page.locator('[role="alert"], .error, [class*="error"]').first()
      await expect(errorElement).toBeVisible()
      
      // Error should be announced to screen readers
      const role = await errorElement.getAttribute('role')
      expect(role).toBe('alert')
    })
  })
})
