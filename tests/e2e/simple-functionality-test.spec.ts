import { test, expect } from '@playwright/test';

test.describe('Marketing Site Functionality', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('http://localhost:3002');
    await page.waitForLoadState('networkidle');
  });

  test('Core functionality works', async ({ page }) => {
    // Test home page loads
    await expect(page).toHaveTitle(/Janua/);
    
    // Test hero section exists
    await expect(page.locator('h1')).toContainText('Authentication at the');
    
    // Test pricing link works (direct navigation)
    const pricingLink = page.locator('a[href="/pricing"]').first();
    await expect(pricingLink).toBeVisible();
    
    // Test performance demo button
    const perfButton = page.locator('button:has-text("Run Performance Test")');
    await expect(perfButton).toBeVisible();
    await perfButton.click();
    
    // Test external GitHub links
    const githubLinks = page.locator('a[href*="github.com"]');
    await expect(githubLinks.first()).toBeVisible();
    
    // Test app links
    const signUpLinks = page.locator('a[href*="app.janua.dev/auth/signup"]');
    await expect(signUpLinks.first()).toBeVisible();
    
    // Test Get Started button exists
    const getStartedButton = page.locator('a:has-text("Get Started")').first();
    await expect(getStartedButton).toBeVisible();
    
    // Test footer links exist
    const footerLinks = page.locator('footer a');
    await expect(footerLinks.first()).toBeVisible();
  });

  test('Interactive components work', async ({ page }) => {
    // Test SDK tabs (use role selector to be more specific)
    const typescriptTab = page.getByRole('tab', { name: 'TypeScript' });
    if (await typescriptTab.isVisible()) {
      await typescriptTab.click();
    }

    // Test pricing toggle (if exists)
    const monthlyButton = page.locator('button:has-text("Monthly")').first();
    if (await monthlyButton.isVisible()) {
      await monthlyButton.click();
    }

    // Test comparison filters
    const allFilter = page.locator('button:has-text("All")').first();
    if (await allFilter.isVisible()) {
      await allFilter.click();
    }
  });

  test('Navigation structure exists', async ({ page }) => {
    // Check that main navigation elements exist (even if dropdowns)
    const nav = page.locator('nav');
    await expect(nav).toBeVisible();
    
    // Check logo exists
    const logo = page.locator('a[href="/"]').first();
    await expect(logo).toBeVisible();
    
    // Check navigation has Product, Developers, etc. (as buttons or links)
    const navText = await nav.textContent();
    expect(navText).toContain('Product');
    expect(navText).toContain('Developers');
    expect(navText).toContain('Pricing');
  });
});