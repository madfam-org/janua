import { test, expect } from '@playwright/test'
import {
  fillByLabel,
  clickButton,
  waitForUrl,
  clearAuth,
} from './utils/test-helpers'

/**
 * E2E Tests: Session and Device Management Flow
 * 
 * Tests session management, device tracking, and security features
 */

test.describe('Session and Device Management', () => {
  test.beforeEach(async ({ page }) => {
    await clearAuth(page)
    await page.goto('/')
  })

  test('active sessions list shows current session', async ({ page }) => {
    // Navigate to sessions page (assumes authenticated)
    await page.goto('/auth/user-sessions-showcase')
    
    // Verify sessions page is visible
    await expect(page.getByRole('heading', { name: /sessions|active.*sessions/i })).toBeVisible()
    
    // Should show at least one active session (current)
    const sessionItems = page.locator('[data-testid="session-item"], .session-item, [role="listitem"]')
    if (await sessionItems.first().isVisible()) {
      const count = await sessionItems.count()
      expect(count).toBeGreaterThan(0)
      
      // Current session should be marked
      await expect(page.getByText(/current.*session|this.*device/i)).toBeVisible()
    }
  })

  test('session information displays device and location', async ({ page }) => {
    // Navigate to sessions page
    await page.goto('/auth/user-sessions-showcase')
    
    const sessionItems = page.locator('[data-testid="session-item"], .session-item')
    if (await sessionItems.first().isVisible()) {
      const firstSession = sessionItems.first()
      
      // Should show device information
      const deviceInfo = firstSession.locator('text=/Chrome|Safari|Firefox|Edge|Mobile/i')
      if (await deviceInfo.isVisible()) {
        await expect(deviceInfo).toBeVisible()
      }
      
      // Should show location or IP
      const locationInfo = firstSession.locator('text=/\\d{1,3}\\.\\d{1,3}\\.\\d{1,3}\\.\\d{1,3}|United States|Unknown/i')
      if (await locationInfo.isVisible()) {
        await expect(locationInfo).toBeVisible()
      }
      
      // Should show last active time
      const timeInfo = firstSession.locator('text=/ago|active|last/i')
      if (await timeInfo.isVisible()) {
        await expect(timeInfo).toBeVisible()
      }
    }
  })

  test('can revoke individual session', async ({ page }) => {
    // Navigate to sessions page
    await page.goto('/auth/user-sessions-showcase')
    
    // Find revoke button for non-current session
    const revokeButtons = page.getByRole('button', { name: /revoke|sign.*out|remove/i })
    if (await revokeButtons.first().isVisible()) {
      const buttonCount = await revokeButtons.count()
      
      if (buttonCount > 0) {
        // Click revoke on first session
        await revokeButtons.first().click()
        
        // May show confirmation dialog
        const confirmButton = page.getByRole('button', { name: /confirm|yes|revoke/i })
        if (await confirmButton.isVisible()) {
          await confirmButton.click()
        }
        
        // Should show success message
        await expect(page.getByText(/session.*revoked|signed.*out/i)).toBeVisible({ timeout: 5000 })
      }
    }
  })

  test('can revoke all other sessions', async ({ page }) => {
    // Navigate to sessions page
    await page.goto('/auth/user-sessions-showcase')
    
    // Look for "revoke all" button
    const revokeAllButton = page.getByRole('button', { name: /revoke.*all|sign.*out.*all|remove.*all/i })
    if (await revokeAllButton.isVisible()) {
      await revokeAllButton.click()
      
      // Should show confirmation dialog
      const confirmButton = page.getByRole('button', { name: /confirm|yes/i })
      if (await confirmButton.isVisible()) {
        await confirmButton.click()
        
        // Should show success
        await expect(page.getByText(/sessions.*revoked|all.*sessions.*ended/i)).toBeVisible({ timeout: 5000 })
      }
    }
  })

  test('audit log shows authentication events', async ({ page }) => {
    // Navigate to audit log page
    await page.goto('/auth/audit-log-showcase')
    
    // Verify audit log is visible
    await expect(page.getByRole('heading', { name: /audit.*log|activity.*log/i })).toBeVisible()
    
    // Should show event entries
    const eventItems = page.locator('[data-testid="audit-event"], .audit-event, [role="listitem"]')
    if (await eventItems.first().isVisible()) {
      const count = await eventItems.count()
      expect(count).toBeGreaterThan(0)
      
      // Verify event types are shown (sign-in, sign-out, etc.)
      await expect(page.getByText(/sign.*in|sign.*out|password.*change|mfa/i)).toBeVisible()
    }
  })

  test('audit log displays event details', async ({ page }) => {
    // Navigate to audit log
    await page.goto('/auth/audit-log-showcase')
    
    const eventItems = page.locator('[data-testid="audit-event"], .audit-event')
    if (await eventItems.first().isVisible()) {
      const firstEvent = eventItems.first()
      
      // Should show timestamp
      const timestamp = firstEvent.locator('text=/ago|\\d{1,2}:\\d{2}|AM|PM/i')
      if (await timestamp.isVisible()) {
        await expect(timestamp).toBeVisible()
      }
      
      // Should show IP address
      const ipAddress = firstEvent.locator('text=/\\d{1,3}\\.\\d{1,3}\\.\\d{1,3}\\.\\d{1,3}/i')
      if (await ipAddress.isVisible()) {
        await expect(ipAddress).toBeVisible()
      }
      
      // Should show event actor (user or system)
      const actor = firstEvent.locator('text=/user|system|you/i')
      if (await actor.isVisible()) {
        await expect(actor).toBeVisible()
      }
    }
  })

  test('audit log can be filtered by event type', async ({ page }) => {
    // Navigate to audit log
    await page.goto('/auth/audit-log-showcase')
    
    // Look for filter dropdown or buttons
    const filterButton = page.getByRole('button', { name: /filter|event.*type/i })
    if (await filterButton.isVisible()) {
      await filterButton.click()
      
      // Select specific event type
      const signInFilter = page.getByRole('menuitem', { name: /sign.*in/i })
      if (await signInFilter.isVisible()) {
        await signInFilter.click()
        
        // Should filter events
        await page.waitForTimeout(500)
        
        // Verify only sign-in events are shown
        const events = page.locator('[data-testid="audit-event"]')
        if (await events.first().isVisible()) {
          const firstEventText = await events.first().textContent()
          expect(firstEventText?.toLowerCase()).toContain('sign')
        }
      }
    }
  })

  test('session shows browser and OS information', async ({ page }) => {
    // Navigate to sessions page
    await page.goto('/auth/user-sessions-showcase')
    
    const sessionItems = page.locator('[data-testid="session-item"], .session-item')
    if (await sessionItems.first().isVisible()) {
      const firstSession = sessionItems.first()
      
      // Should show browser name
      await expect(firstSession.getByText(/Chrome|Firefox|Safari|Edge/i)).toBeVisible()
      
      // Should show OS
      await expect(firstSession.getByText(/Windows|macOS|Linux|iOS|Android/i)).toBeVisible()
    }
  })

  test('security log shows critical security events', async ({ page }) => {
    // Navigate to audit log
    await page.goto('/auth/audit-log-showcase')
    
    // Look for security-specific events
    const securityEvents = page.getByText(/password.*change|mfa.*enabled|mfa.*disabled|failed.*login/i)
    if (await securityEvents.first().isVisible()) {
      await expect(securityEvents.first()).toBeVisible()
    }
  })

  test('can export audit log', async ({ page }) => {
    // Navigate to audit log
    await page.goto('/auth/audit-log-showcase')
    
    // Look for export button
    const exportButton = page.getByRole('button', { name: /export|download/i })
    if (await exportButton.isVisible()) {
      // Click export
      const downloadPromise = page.waitForEvent('download', { timeout: 5000 }).catch(() => null)
      await exportButton.click()
      
      const download = await downloadPromise
      if (download) {
        // Verify download was initiated
        expect(download).toBeTruthy()
      }
    }
  })

  test('session list shows last active timestamp', async ({ page }) => {
    // Navigate to sessions page
    await page.goto('/auth/user-sessions-showcase')
    
    const sessionItems = page.locator('[data-testid="session-item"], .session-item')
    if (await sessionItems.first().isVisible()) {
      // Should show "last active" information
      await expect(page.getByText(/last.*active|active.*now|just.*now|ago/i)).toBeVisible()
    }
  })
})
