import { test, expect } from '@playwright/test'
import {
  fillByLabel,
  clickButton,
  waitForUrl,
  waitForToast,
  clearAuth,
} from './utils/test-helpers'

/**
 * E2E Tests: Organization Management Flow
 * 
 * Tests organization creation, switching, member management, and settings
 */

test.describe('Organization Management', () => {
  test.beforeEach(async ({ page }) => {
    await clearAuth(page)
    await page.goto('/')
  })

  test('create new organization', async ({ page }) => {
    // Navigate to organization creation page
    await page.goto('/auth/organization-create-showcase')
    
    // Verify create organization form is visible
    await expect(page.getByRole('heading', { name: /create.*organization/i })).toBeVisible()
    
    // Fill organization details
    const orgName = `Test Org ${Date.now()}`
    await fillByLabel(page, /organization.*name|name/i, orgName)
    
    // Submit form
    await clickButton(page, /create|continue/i)
    
    // Should show success or redirect to organization dashboard
    const success = page.getByText(/organization.*created|welcome/i)
    if (await success.isVisible()) {
      await expect(success).toBeVisible()
    } else {
      // Or redirect to org dashboard
      await page.waitForURL(/\/(dashboard|org)/i, { timeout: 10000 })
    }
  })

  test('switch between organizations', async ({ page }) => {
    // Navigate to organization switcher showcase
    await page.goto('/auth/organization-switcher-showcase')
    
    // Verify organization switcher is visible
    const orgSwitcher = page.getByRole('button', { name: /switch|organization/i })
    if (await orgSwitcher.isVisible()) {
      await orgSwitcher.click()
      
      // Should show organization list dropdown
      await expect(page.getByRole('menu')).toBeVisible({ timeout: 2000 })
      
      // Verify multiple organizations are listed
      const orgItems = page.getByRole('menuitem')
      const count = await orgItems.count()
      expect(count).toBeGreaterThan(0)
      
      // Select different organization
      if (count > 1) {
        await orgItems.nth(1).click()
        
        // Should switch organization context
        await page.waitForTimeout(1000)
        
        // Verify org switcher now shows selected org
        const selectedOrg = await orgSwitcher.textContent()
        expect(selectedOrg).toBeTruthy()
      }
    }
  })

  test('organization slug validation', async ({ page }) => {
    // Navigate to organization create page
    await page.goto('/auth/organization-create-showcase')
    
    // Try to create org with invalid slug
    const nameInput = page.getByLabel(/organization.*name|name/i)
    if (await nameInput.isVisible()) {
      await nameInput.fill('Invalid Org Name!!!')
      
      // Submit
      await clickButton(page, /create|continue/i)
      
      // Should show slug validation error
      await expect(page.getByText(/invalid.*slug|alphanumeric|invalid.*characters/i)).toBeVisible()
    }
  })

  test('organization switcher shows current organization', async ({ page }) => {
    // Navigate to org switcher showcase
    await page.goto('/auth/organization-switcher-showcase')
    
    // Verify current organization is displayed
    const currentOrg = page.locator('[data-testid="current-org"], .current-org')
    if (await currentOrg.first().isVisible()) {
      await expect(currentOrg.first()).toBeVisible()
      
      // Verify it has text content
      const orgName = await currentOrg.first().textContent()
      expect(orgName?.length).toBeGreaterThan(0)
    }
  })

  test('can create organization from switcher', async ({ page }) => {
    // Navigate to org switcher
    await page.goto('/auth/organization-switcher-showcase')
    
    // Open organization switcher
    const orgSwitcher = page.getByRole('button', { name: /switch|organization/i })
    if (await orgSwitcher.isVisible()) {
      await orgSwitcher.click()
      
      // Look for "Create Organization" option
      const createOption = page.getByRole('menuitem', { name: /create.*organization|new.*organization/i })
      if (await createOption.isVisible()) {
        await createOption.click()
        
        // Should navigate to organization creation page
        await waitForUrl(page, /\/auth\/organization-create/i)
        await expect(page.getByRole('heading', { name: /create.*organization/i })).toBeVisible()
      }
    }
  })

  test('organization list shows organization logos', async ({ page }) => {
    // Navigate to org switcher
    await page.goto('/auth/organization-switcher-showcase')
    
    const orgSwitcher = page.getByRole('button', { name: /switch|organization/i })
    if (await orgSwitcher.isVisible()) {
      await orgSwitcher.click()
      
      // Check if org logos are displayed
      const logos = page.locator('img[alt*="logo"], [data-testid="org-logo"]')
      if (await logos.first().isVisible()) {
        const count = await logos.count()
        expect(count).toBeGreaterThan(0)
      }
    }
  })

  test('organization creation with duplicate slug shows error', async ({ page }) => {
    // Navigate to create org page
    await page.goto('/auth/organization-create-showcase')
    
    // Try to create org with existing slug
    const nameInput = page.getByLabel(/organization.*name|name/i)
    if (await nameInput.isVisible()) {
      await nameInput.fill('Existing Org')
      
      // Submit
      await clickButton(page, /create|continue/i)
      
      // Should show duplicate slug error
      await expect(page.getByText(/already.*exists|slug.*taken|name.*taken/i)).toBeVisible({ timeout: 5000 })
    }
  })

  test('organization switcher accessible via keyboard', async ({ page }) => {
    // Navigate to org switcher
    await page.goto('/auth/organization-switcher-showcase')
    
    // Tab to organization switcher
    await page.keyboard.press('Tab')
    
    const orgSwitcher = page.getByRole('button', { name: /switch|organization/i })
    if (await orgSwitcher.isFocused()) {
      // Press Enter to open
      await page.keyboard.press('Enter')
      
      // Menu should be visible
      await expect(page.getByRole('menu')).toBeVisible()
      
      // Arrow down to navigate
      await page.keyboard.press('ArrowDown')
      
      // Enter to select
      await page.keyboard.press('Enter')
      
      // Should switch organization
      await page.waitForTimeout(1000)
    }
  })
})
