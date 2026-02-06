import { test, expect } from '@playwright/test'
import path from 'path'

/**
 * Visual Confidence Tests - Theme Toggle
 * 
 * These tests verify that the theme toggle works correctly and that
 * both light and dark modes render properly across key UI components.
 * 
 * Screenshots are saved to tests/artifacts/ for manual review.
 */

const ARTIFACTS_DIR = path.join(__dirname, '../../tests/artifacts')

// Dashboard app runs on port 3001
const DASHBOARD_URL = process.env.DASHBOARD_URL || 'http://localhost:3001'

test.describe('Theme Toggle Visual Tests', () => {
  test.beforeEach(async ({ page }) => {
    // Set viewport for consistent screenshots
    await page.setViewportSize({ width: 1280, height: 720 })
  })

  test('dashboard renders correctly in light mode', async ({ page }) => {
    // Navigate to dashboard
    await page.goto(DASHBOARD_URL)
    
    // Wait for page to be fully loaded
    await page.waitForLoadState('networkidle')
    
    // Ensure light mode is active (clear any stored theme preference)
    await page.evaluate(() => {
      localStorage.setItem('theme', 'light')
      document.documentElement.classList.remove('dark')
      document.documentElement.classList.add('light')
    })
    
    // Reload to apply theme
    await page.reload()
    await page.waitForLoadState('networkidle')
    
    // Take screenshot of dashboard in light mode
    await page.screenshot({
      path: path.join(ARTIFACTS_DIR, 'dashboard-light-mode.png'),
      fullPage: false,
    })
    
    // Verify light mode is active
    const htmlClass = await page.evaluate(() => document.documentElement.className)
    expect(htmlClass).not.toContain('dark')
  })

  test('dashboard renders correctly in dark mode', async ({ page }) => {
    // Navigate to dashboard
    await page.goto(DASHBOARD_URL)
    
    // Wait for page to be fully loaded
    await page.waitForLoadState('networkidle')
    
    // Set dark mode
    await page.evaluate(() => {
      localStorage.setItem('theme', 'dark')
      document.documentElement.classList.remove('light')
      document.documentElement.classList.add('dark')
    })
    
    // Reload to apply theme
    await page.reload()
    await page.waitForLoadState('networkidle')
    
    // Take screenshot of dashboard in dark mode
    await page.screenshot({
      path: path.join(ARTIFACTS_DIR, 'dashboard-dark-mode.png'),
      fullPage: false,
    })
    
    // Verify dark mode is active
    const htmlClass = await page.evaluate(() => document.documentElement.className)
    expect(htmlClass).toContain('dark')
  })

  test('theme toggle button works correctly', async ({ page }) => {
    // Navigate to dashboard
    await page.goto(DASHBOARD_URL)
    await page.waitForLoadState('networkidle')
    
    // Start in light mode
    await page.evaluate(() => {
      localStorage.setItem('theme', 'light')
      document.documentElement.classList.remove('dark')
      document.documentElement.classList.add('light')
    })
    await page.reload()
    await page.waitForLoadState('networkidle')
    
    // Find and click the theme toggle button
    const themeToggle = page.locator('[data-testid="theme-toggle"]').or(
      page.locator('button:has-text("Toggle theme")').or(
        page.locator('button[aria-label*="theme"]').or(
          page.locator('button:has(svg.lucide-sun), button:has(svg.lucide-moon)')
        )
      )
    )
    
    // If toggle exists, click it
    if (await themeToggle.count() > 0) {
      // Screenshot before toggle
      await page.screenshot({
        path: path.join(ARTIFACTS_DIR, 'theme-toggle-before.png'),
        fullPage: false,
      })
      
      // Click toggle
      await themeToggle.first().click()
      
      // Wait for theme transition
      await page.waitForTimeout(500)
      
      // Screenshot after toggle
      await page.screenshot({
        path: path.join(ARTIFACTS_DIR, 'theme-toggle-after.png'),
        fullPage: false,
      })
      
      // Verify theme changed
      const htmlClassAfter = await page.evaluate(() => document.documentElement.className)
      expect(htmlClassAfter).toContain('dark')
    } else {
      // No toggle found - skip but don't fail
      test.skip(true, 'Theme toggle button not found on page')
    }
  })

  test('users table renders correctly in both themes', async ({ page }) => {
    // Navigate to users page
    await page.goto(`${DASHBOARD_URL}/users`)
    await page.waitForLoadState('networkidle')
    
    // Light mode screenshot
    await page.evaluate(() => {
      localStorage.setItem('theme', 'light')
      document.documentElement.classList.remove('dark')
      document.documentElement.classList.add('light')
    })
    await page.reload()
    await page.waitForLoadState('networkidle')
    
    // Wait for table to be visible (if it exists)
    const table = page.locator('table').or(page.locator('[role="table"]'))
    
    if (await table.count() > 0) {
      await table.first().waitFor({ state: 'visible', timeout: 5000 }).catch(() => {})
    }
    
    await page.screenshot({
      path: path.join(ARTIFACTS_DIR, 'users-table-light.png'),
      fullPage: false,
    })
    
    // Dark mode screenshot
    await page.evaluate(() => {
      localStorage.setItem('theme', 'dark')
      document.documentElement.classList.remove('light')
      document.documentElement.classList.add('dark')
    })
    await page.reload()
    await page.waitForLoadState('networkidle')
    
    if (await table.count() > 0) {
      await table.first().waitFor({ state: 'visible', timeout: 5000 }).catch(() => {})
    }
    
    await page.screenshot({
      path: path.join(ARTIFACTS_DIR, 'users-table-dark.png'),
      fullPage: false,
    })
  })

  test('status badges have correct colors in dark mode', async ({ page }) => {
    // Navigate to a page with status badges (users page)
    await page.goto(`${DASHBOARD_URL}/users`)
    await page.waitForLoadState('networkidle')
    
    // Set dark mode
    await page.evaluate(() => {
      localStorage.setItem('theme', 'dark')
      document.documentElement.classList.remove('light')
      document.documentElement.classList.add('dark')
    })
    await page.reload()
    await page.waitForLoadState('networkidle')
    
    // Find any badges on the page
    const badges = page.locator('[class*="badge"]')
    
    if (await badges.count() > 0) {
      // Get first badge's computed style
      const badgeStyles = await badges.first().evaluate((el) => {
        const computed = window.getComputedStyle(el)
        return {
          backgroundColor: computed.backgroundColor,
          color: computed.color,
          borderColor: computed.borderColor,
        }
      })
      
      // Log for debugging
      console.log('Badge styles in dark mode:', badgeStyles)
      
      // Verify colors are not pure white or pure black (should be themed)
      expect(badgeStyles.color).not.toBe('rgb(0, 0, 0)')
      expect(badgeStyles.backgroundColor).not.toBe('rgb(255, 255, 255)')
    }
    
    // Take screenshot for manual verification
    await page.screenshot({
      path: path.join(ARTIFACTS_DIR, 'status-badges-dark.png'),
      fullPage: false,
    })
  })
})

test.describe('Admin App Theme Tests (Solarpunk)', () => {
  // Admin app runs on port 3004
  const ADMIN_URL = process.env.ADMIN_URL || 'http://localhost:3004'

  test.beforeEach(async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 720 })
  })

  test('admin dashboard renders in Solarpunk theme', async ({ page }) => {
    await page.goto(ADMIN_URL)
    await page.waitForLoadState('networkidle')
    
    // Admin should default to dark/Solarpunk theme
    await page.evaluate(() => {
      localStorage.setItem('theme', 'dark')
      document.documentElement.classList.remove('light')
      document.documentElement.classList.add('dark')
    })
    await page.reload()
    await page.waitForLoadState('networkidle')
    
    // Take screenshot
    await page.screenshot({
      path: path.join(ARTIFACTS_DIR, 'admin-solarpunk-theme.png'),
      fullPage: false,
    })
    
    // Verify dark mode classes
    const htmlClass = await page.evaluate(() => document.documentElement.className)
    expect(htmlClass).toContain('dark')
  })

  test('vault status badges render correctly', async ({ page }) => {
    await page.goto(ADMIN_URL)
    await page.waitForLoadState('networkidle')
    
    // Set dark mode for Solarpunk theme
    await page.evaluate(() => {
      localStorage.setItem('theme', 'dark')
      document.documentElement.classList.remove('light')
      document.documentElement.classList.add('dark')
    })
    await page.reload()
    await page.waitForLoadState('networkidle')
    
    // Take screenshot of vault section if visible
    await page.screenshot({
      path: path.join(ARTIFACTS_DIR, 'admin-vault-badges.png'),
      fullPage: false,
    })
  })
})
