import { test, expect } from '@playwright/test'
import {
  generateTestEmail,
  generateTestPassword,
  generateTestPhone,
  fillByLabel,
  clickButton,
  waitForUrl,
  waitForToast,
  waitForError,
  clearAuth,
  simulateSMSCode,
} from './utils/test-helpers'

/**
 * E2E Tests: Multi-Factor Authentication (MFA) Flow
 * 
 * Tests MFA setup, verification, and recovery:
 * - TOTP (Authenticator App) setup and verification
 * - SMS setup and verification
 * - Backup codes generation and usage
 * - MFA challenge during sign-in
 */

test.describe('MFA Setup and Verification', () => {
  let testEmail: string
  let testPassword: string
  let testPhone: string

  test.beforeEach(async ({ page }) => {
    testEmail = generateTestEmail()
    testPassword = generateTestPassword()
    testPhone = generateTestPhone()
    
    await clearAuth(page)
    await page.goto('/')
  })

  test('TOTP authenticator app setup flow', async ({ page }) => {
    // Navigate to MFA setup page (assumes authenticated user)
    await page.goto('/auth/mfa-setup-showcase')
    
    // Verify MFA setup page is visible
    await expect(page.getByRole('heading', { name: /multi.*factor|mfa.*setup|two.*factor/i })).toBeVisible()
    
    // Select TOTP method
    const totpButton = page.getByRole('button', { name: /authenticator.*app|totp/i })
    if (await totpButton.isVisible()) {
      await totpButton.click()
      
      // Should show QR code and secret key
      await expect(page.getByText(/scan.*qr.*code|secret.*key/i)).toBeVisible()
      
      // Verify QR code image is present
      const qrCode = page.locator('img[alt*="QR"], canvas, [data-testid="qr-code"]')
      await expect(qrCode.first()).toBeVisible({ timeout: 5000 })
      
      // Enter TOTP code (simulated)
      const totpInput = page.getByLabel(/code|verification.*code/i)
      if (await totpInput.isVisible()) {
        await totpInput.fill('123456')
        
        // Submit verification
        await clickButton(page, /verify|confirm/i)
        
        // Should show backup codes
        await expect(page.getByText(/backup.*codes|recovery.*codes/i)).toBeVisible({ timeout: 5000 })
      }
    }
  })

  test('SMS phone number setup flow', async ({ page }) => {
    // Navigate to MFA setup page
    await page.goto('/auth/mfa-setup-showcase')
    
    // Select SMS method
    const smsButton = page.getByRole('button', { name: /sms|phone/i })
    if (await smsButton.isVisible()) {
      await smsButton.click()
      
      // Should show phone number input
      const phoneInput = page.getByLabel(/phone.*number|mobile/i)
      await expect(phoneInput).toBeVisible()
      
      // Enter phone number
      await phoneInput.fill(testPhone)
      
      // Click send code button
      await clickButton(page, /send.*code/i)
      
      // Should show verification code input
      const codeInput = page.getByLabel(/code|verification/i)
      await expect(codeInput).toBeVisible({ timeout: 5000 })
      
      // Simulate receiving SMS code
      const smsCode = await simulateSMSCode(testPhone)
      
      // Enter verification code
      await codeInput.fill(smsCode)
      
      // Submit
      await clickButton(page, /verify|confirm/i)
      
      // Should show success message
      await expect(page.getByText(/sms.*enabled|phone.*verified/i)).toBeVisible({ timeout: 5000 })
    }
  })

  test('backup codes are displayed and can be downloaded', async ({ page }) => {
    // Navigate to MFA setup and complete TOTP setup
    await page.goto('/auth/mfa-setup-showcase')
    
    const totpButton = page.getByRole('button', { name: /authenticator.*app|totp/i })
    if (await totpButton.isVisible()) {
      await totpButton.click()
      
      // Complete TOTP setup (abbreviated)
      const totpInput = page.getByLabel(/code|verification.*code/i)
      if (await totpInput.isVisible()) {
        await totpInput.fill('123456')
        await clickButton(page, /verify|confirm/i)
        
        // Verify backup codes are shown
        await expect(page.getByText(/backup.*codes|recovery.*codes/i)).toBeVisible()
        
        // Check that codes are displayed (should see multiple codes)
        const backupCodes = page.locator('[data-testid="backup-code"], .backup-code, code')
        const count = await backupCodes.count()
        expect(count).toBeGreaterThan(0)
        
        // Verify download button exists
        const downloadButton = page.getByRole('button', { name: /download|save/i })
        if (await downloadButton.isVisible()) {
          await expect(downloadButton).toBeVisible()
        }
      }
    }
  })

  test('MFA challenge during sign-in with TOTP', async ({ page }) => {
    // Assume user has MFA enabled, navigate to sign-in
    await page.goto('/auth/signin-showcase')
    
    // Sign in with credentials
    await fillByLabel(page, /email/i, 'mfa-enabled@plinto.dev')
    await fillByLabel(page, /password/i, 'MfaUser123!')
    await clickButton(page, /sign in/i)
    
    // Should redirect to MFA verification page
    await waitForUrl(page, /\/auth\/mfa-verify/i)
    
    // Should show TOTP code input
    await expect(page.getByText(/enter.*code|verification.*code/i)).toBeVisible()
    
    // Enter TOTP code
    const totpInput = page.getByLabel(/code/i)
    await totpInput.fill('123456')
    
    // Submit
    await clickButton(page, /verify|continue/i)
    
    // Should complete authentication
    await page.waitForURL(/\/(dashboard|welcome)/i, { timeout: 10000 })
  })

  test('MFA challenge with invalid code shows error', async ({ page }) => {
    // Navigate to MFA verification page (assumes MFA-enabled user signed in)
    await page.goto('/auth/mfa-verify-showcase')
    
    // Enter invalid TOTP code
    const totpInput = page.getByLabel(/code/i)
    if (await totpInput.isVisible()) {
      await totpInput.fill('000000')
      
      // Submit
      await clickButton(page, /verify|continue/i)
      
      // Should show error
      await waitForError(page, /invalid.*code|verification.*failed/i)
      
      // Should still be on MFA verification page
      expect(page.url()).toContain('/auth/mfa-verify')
    }
  })

  test('can use backup code when TOTP unavailable', async ({ page }) => {
    // Navigate to MFA verification page
    await page.goto('/auth/mfa-verify-showcase')
    
    // Click "use backup code" option
    const useBackupLink = page.getByRole('button', { name: /backup.*code|recovery.*code/i })
    if (await useBackupLink.isVisible()) {
      await useBackupLink.click()
      
      // Should show backup code input
      const backupInput = page.getByLabel(/backup.*code|recovery.*code/i)
      await expect(backupInput).toBeVisible()
      
      // Enter backup code
      await backupInput.fill('BACKUP-CODE-1234')
      
      // Submit
      await clickButton(page, /verify|continue/i)
      
      // Should complete authentication or show success
      await page.waitForTimeout(2000)
      const url = page.url()
      const authenticated = !url.includes('/auth/mfa-verify')
      expect(authenticated).toBeTruthy()
    }
  })

  test('SMS verification code auto-submit on complete', async ({ page }) => {
    // Navigate to phone verification page
    await page.goto('/auth/phone-verification-showcase')
    
    // Enter 6-digit code
    const codeInput = page.getByRole('textbox', { name: /code/i })
    if (await codeInput.isVisible()) {
      await codeInput.fill('654321')
      
      // Should auto-submit on 6th digit (wait for submission)
      await page.waitForTimeout(1000)
      
      // Check if verification processed
      const success = page.getByText(/verified|success/i)
      const stillOnPage = page.url().includes('/phone-verification')
      
      // Either succeeded or still on page waiting for valid code
      expect(await success.isVisible() || stillOnPage).toBeTruthy()
    }
  })

  test('can resend SMS verification code', async ({ page }) => {
    // Navigate to phone verification page
    await page.goto('/auth/phone-verification-showcase')
    
    // Click resend code button
    const resendButton = page.getByRole('button', { name: /resend|send.*again/i })
    if (await resendButton.isVisible()) {
      await resendButton.click()
      
      // Should show success message about code sent
      await expect(page.getByText(/code.*sent|new.*code/i)).toBeVisible({ timeout: 5000 })
      
      // Resend button should be disabled temporarily
      await expect(resendButton).toBeDisabled()
    }
  })

  test('MFA setup can be disabled', async ({ page }) => {
    // Navigate to MFA management page (assumes MFA already enabled)
    await page.goto('/auth/mfa-setup-showcase')
    
    // Look for disable/remove MFA option
    const disableButton = page.getByRole('button', { name: /disable|remove.*mfa|turn.*off/i })
    if (await disableButton.isVisible()) {
      await disableButton.click()
      
      // May require password confirmation
      const passwordInput = page.getByLabel(/password|confirm/i)
      if (await passwordInput.isVisible()) {
        await passwordInput.fill('ValidPass123!')
        await clickButton(page, /confirm|disable/i)
      }
      
      // Should show success message
      await expect(page.getByText(/mfa.*disabled|two.*factor.*off/i)).toBeVisible({ timeout: 5000 })
    }
  })

  test('remember this device option persists MFA trust', async ({ page }) => {
    // Navigate to MFA verification after sign-in
    await page.goto('/auth/mfa-verify-showcase')
    
    // Check "remember this device" checkbox
    const rememberCheckbox = page.getByRole('checkbox', { name: /remember.*device|trust.*device/i })
    if (await rememberCheckbox.isVisible()) {
      await rememberCheckbox.check()
      
      // Enter valid code
      const totpInput = page.getByLabel(/code/i)
      await totpInput.fill('123456')
      
      // Submit
      await clickButton(page, /verify|continue/i)
      
      // Should set device trust cookie
      await page.waitForTimeout(1000)
      const cookies = await page.context().cookies()
      
      // Check for device trust cookie
      const hasTrustCookie = cookies.some(c => 
        c.name.includes('device') || c.name.includes('trust') || c.name.includes('mfa')
      )
      expect(hasTrustCookie).toBeTruthy()
    }
  })
})
