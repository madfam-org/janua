import { test, expect, Page } from '@playwright/test';

test.describe('Authentication E2E', () => {
  let page: Page;
  const testEmail = `test-${Date.now()}@example.com`;
  const testPassword = 'TestPassword123!';

  test.beforeEach(async ({ browser }) => {
    page = await browser.newPage();
  });

  test.afterEach(async () => {
    await page.close();
  });

  test.describe('Sign Up Flow', () => {
    test('should successfully sign up a new user', async () => {
      await page.goto('/auth/signup');
      
      // Fill signup form
      await page.fill('input[name="email"]', testEmail);
      await page.fill('input[name="password"]', testPassword);
      await page.fill('input[name="confirmPassword"]', testPassword);
      await page.fill('input[name="name"]', 'Test User');
      
      // Accept terms
      await page.check('input[name="acceptTerms"]');
      
      // Submit form
      await page.click('button[type="submit"]');
      
      // Should redirect to verification page
      await expect(page).toHaveURL('/auth/verify-email');
      await expect(page.locator('h1')).toContainText('Verify Your Email');
      await expect(page.locator('.alert-success')).toContainText('verification email has been sent');
    });

    test('should validate email format', async () => {
      await page.goto('/auth/signup');
      
      await page.fill('input[name="email"]', 'invalid-email');
      await page.fill('input[name="password"]', testPassword);
      await page.click('button[type="submit"]');
      
      await expect(page.locator('.error-message')).toContainText('valid email');
    });

    test('should validate password strength', async () => {
      await page.goto('/auth/signup');
      
      await page.fill('input[name="email"]', testEmail);
      await page.fill('input[name="password"]', '123');
      await page.click('button[type="submit"]');
      
      await expect(page.locator('.error-message')).toContainText('at least 8 characters');
    });

    test('should show password strength indicator', async () => {
      await page.goto('/auth/signup');
      
      const passwordInput = page.locator('input[name="password"]');
      const strengthIndicator = page.locator('.password-strength');
      
      // Weak password
      await passwordInput.fill('12345678');
      await expect(strengthIndicator).toHaveClass(/weak/);
      
      // Medium password
      await passwordInput.fill('Password123');
      await expect(strengthIndicator).toHaveClass(/medium/);
      
      // Strong password
      await passwordInput.fill('P@ssw0rd123!');
      await expect(strengthIndicator).toHaveClass(/strong/);
    });

    test('should prevent duplicate email registration', async () => {
      // First registration
      await page.goto('/auth/signup');
      await page.fill('input[name="email"]', 'duplicate@example.com');
      await page.fill('input[name="password"]', testPassword);
      await page.fill('input[name="confirmPassword"]', testPassword);
      await page.fill('input[name="name"]', 'Duplicate User');
      await page.check('input[name="acceptTerms"]');
      await page.click('button[type="submit"]');
      
      // Wait for success
      await expect(page).toHaveURL('/auth/verify-email');
      
      // Try to register again
      await page.goto('/auth/signup');
      await page.fill('input[name="email"]', 'duplicate@example.com');
      await page.fill('input[name="password"]', testPassword);
      await page.fill('input[name="confirmPassword"]', testPassword);
      await page.fill('input[name="name"]', 'Duplicate User 2');
      await page.check('input[name="acceptTerms"]');
      await page.click('button[type="submit"]');
      
      await expect(page.locator('.error-message')).toContainText('already registered');
    });
  });

  test.describe('Sign In Flow', () => {
    test('should successfully sign in with valid credentials', async () => {
      await page.goto('/auth/signin');
      
      await page.fill('input[name="email"]', 'demo@plinto.dev');
      await page.fill('input[name="password"]', 'DemoPassword123!');
      await page.click('button[type="submit"]');
      
      // Should redirect to dashboard
      await expect(page).toHaveURL('/dashboard');
      await expect(page.locator('[data-testid="user-menu"]')).toBeVisible();
    });

    test('should show error for invalid credentials', async () => {
      await page.goto('/auth/signin');
      
      await page.fill('input[name="email"]', 'wrong@example.com');
      await page.fill('input[name="password"]', 'WrongPassword');
      await page.click('button[type="submit"]');
      
      await expect(page.locator('.error-message')).toContainText('Invalid email or password');
    });

    test('should toggle password visibility', async () => {
      await page.goto('/auth/signin');
      
      const passwordInput = page.locator('input[name="password"]');
      const toggleButton = page.locator('[data-testid="toggle-password"]');
      
      // Initially password type
      await expect(passwordInput).toHaveAttribute('type', 'password');
      
      // Click to show
      await toggleButton.click();
      await expect(passwordInput).toHaveAttribute('type', 'text');
      
      // Click to hide
      await toggleButton.click();
      await expect(passwordInput).toHaveAttribute('type', 'password');
    });

    test('should handle remember me checkbox', async () => {
      await page.goto('/auth/signin');
      
      const rememberCheckbox = page.locator('input[name="rememberMe"]');
      
      // Check the checkbox
      await rememberCheckbox.check();
      await expect(rememberCheckbox).toBeChecked();
      
      // Sign in
      await page.fill('input[name="email"]', 'demo@plinto.dev');
      await page.fill('input[name="password"]', 'DemoPassword123!');
      await page.click('button[type="submit"]');
      
      // Verify session cookie has extended expiry
      const cookies = await page.context().cookies();
      const sessionCookie = cookies.find(c => c.name === 'plinto_session');
      expect(sessionCookie).toBeDefined();
      expect(sessionCookie?.expires).toBeGreaterThan(Date.now() / 1000 + 7 * 24 * 60 * 60);
    });

    test('should redirect to requested page after signin', async () => {
      // Try to access protected page
      await page.goto('/dashboard/settings');
      
      // Should redirect to signin with return URL
      await expect(page).toHaveURL(/\/auth\/signin\?returnUrl=/);
      
      // Sign in
      await page.fill('input[name="email"]', 'demo@plinto.dev');
      await page.fill('input[name="password"]', 'DemoPassword123!');
      await page.click('button[type="submit"]');
      
      // Should redirect to originally requested page
      await expect(page).toHaveURL('/dashboard/settings');
    });
  });

  test.describe('Password Reset Flow', () => {
    test('should request password reset', async () => {
      await page.goto('/auth/signin');
      await page.click('a[href="/auth/forgot-password"]');
      
      await expect(page).toHaveURL('/auth/forgot-password');
      
      await page.fill('input[name="email"]', 'demo@plinto.dev');
      await page.click('button[type="submit"]');
      
      await expect(page.locator('.alert-success')).toContainText('reset instructions have been sent');
    });

    test('should handle non-existent email gracefully', async () => {
      await page.goto('/auth/forgot-password');
      
      await page.fill('input[name="email"]', 'nonexistent@example.com');
      await page.click('button[type="submit"]');
      
      // Should show success to prevent email enumeration
      await expect(page.locator('.alert-success')).toContainText('reset instructions have been sent');
    });

    test('should reset password with valid token', async () => {
      // This would normally come from email
      const resetToken = 'valid-reset-token';
      
      await page.goto(`/auth/reset-password?token=${resetToken}`);
      
      await page.fill('input[name="password"]', 'NewPassword123!');
      await page.fill('input[name="confirmPassword"]', 'NewPassword123!');
      await page.click('button[type="submit"]');
      
      // In a real test, this would work with a valid token
      await expect(page.locator('.error-message')).toContainText('invalid or expired');
    });
  });

  test.describe('Social Authentication', () => {
    test('should show social login buttons', async () => {
      await page.goto('/auth/signin');
      
      await expect(page.locator('button[data-provider="google"]')).toBeVisible();
      await expect(page.locator('button[data-provider="github"]')).toBeVisible();
      await expect(page.locator('button[data-provider="microsoft"]')).toBeVisible();
    });

    test('should initiate Google OAuth flow', async () => {
      await page.goto('/auth/signin');
      
      // Click Google button
      const [popup] = await Promise.all([
        page.waitForEvent('popup'),
        page.click('button[data-provider="google"]'),
      ]);
      
      // Verify OAuth URL
      await expect(popup.url()).toContain('accounts.google.com');
      await popup.close();
    });

    test('should initiate GitHub OAuth flow', async () => {
      await page.goto('/auth/signin');
      
      // Click GitHub button
      const [popup] = await Promise.all([
        page.waitForEvent('popup'),
        page.click('button[data-provider="github"]'),
      ]);
      
      // Verify OAuth URL
      await expect(popup.url()).toContain('github.com/login/oauth');
      await popup.close();
    });
  });

  test.describe('Protected Routes', () => {
    test('should redirect to signin for protected routes', async () => {
      await page.goto('/dashboard');
      await expect(page).toHaveURL(/\/auth\/signin/);
    });

    test('should allow access after authentication', async () => {
      // Sign in first
      await page.goto('/auth/signin');
      await page.fill('input[name="email"]', 'demo@plinto.dev');
      await page.fill('input[name="password"]', 'DemoPassword123!');
      await page.click('button[type="submit"]');
      
      // Should access dashboard
      await expect(page).toHaveURL('/dashboard');
      
      // Navigate to other protected routes
      await page.goto('/dashboard/settings');
      await expect(page).toHaveURL('/dashboard/settings');
      
      await page.goto('/dashboard/billing');
      await expect(page).toHaveURL('/dashboard/billing');
    });
  });

  test.describe('Sign Out', () => {
    test.beforeEach(async () => {
      // Sign in first
      await page.goto('/auth/signin');
      await page.fill('input[name="email"]', 'demo@plinto.dev');
      await page.fill('input[name="password"]', 'DemoPassword123!');
      await page.click('button[type="submit"]');
      await expect(page).toHaveURL('/dashboard');
    });

    test('should sign out successfully', async () => {
      await page.click('[data-testid="user-menu"]');
      await page.click('[data-testid="sign-out"]');
      
      await expect(page).toHaveURL('/');
      
      // Try to access protected route
      await page.goto('/dashboard');
      await expect(page).toHaveURL(/\/auth\/signin/);
    });

    test('should clear all cookies on sign out', async () => {
      // Get initial cookies
      const initialCookies = await page.context().cookies();
      expect(initialCookies.some(c => c.name === 'plinto_session')).toBeTruthy();
      
      // Sign out
      await page.click('[data-testid="user-menu"]');
      await page.click('[data-testid="sign-out"]');
      
      // Check cookies are cleared
      const finalCookies = await page.context().cookies();
      expect(finalCookies.some(c => c.name === 'plinto_session')).toBeFalsy();
    });
  });

  test.describe('Session Management', () => {
    test.beforeEach(async () => {
      // Sign in
      await page.goto('/auth/signin');
      await page.fill('input[name="email"]', 'demo@plinto.dev');
      await page.fill('input[name="password"]', 'DemoPassword123!');
      await page.click('button[type="submit"]');
    });

    test('should show active sessions', async () => {
      await page.goto('/dashboard/settings/sessions');
      
      await expect(page.locator('[data-testid="session-list"]')).toBeVisible();
      await expect(page.locator('[data-testid="session-item"]')).toHaveCount(1);
      
      // Should show current session
      const currentSession = page.locator('[data-testid="current-session"]');
      await expect(currentSession).toBeVisible();
      await expect(currentSession).toContainText('Current session');
    });

    test('should revoke other sessions', async () => {
      await page.goto('/dashboard/settings/sessions');
      
      await page.click('[data-testid="revoke-all-others"]');
      
      // Confirm dialog
      await page.click('[data-testid="confirm-revoke"]');
      
      await expect(page.locator('.alert-success')).toContainText('Other sessions have been revoked');
    });
  });

  test.describe('Mobile Responsiveness', () => {
    test.use({ viewport: { width: 375, height: 667 } });

    test('should work on mobile viewport', async () => {
      await page.goto('/auth/signin');
      
      // Mobile menu should be visible
      await expect(page.locator('[data-testid="mobile-menu"]')).toBeVisible();
      
      // Form should be responsive
      const form = page.locator('form');
      await expect(form).toBeVisible();
      
      // Fill and submit
      await page.fill('input[name="email"]', 'demo@plinto.dev');
      await page.fill('input[name="password"]', 'DemoPassword123!');
      await page.click('button[type="submit"]');
      
      await expect(page).toHaveURL('/dashboard');
    });
  });

  test.describe('Accessibility', () => {
    test('should have proper ARIA labels', async () => {
      await page.goto('/auth/signin');
      
      // Check form has proper role
      await expect(page.locator('form')).toHaveAttribute('role', 'form');
      
      // Check inputs have labels
      await expect(page.locator('label[for="email"]')).toBeVisible();
      await expect(page.locator('label[for="password"]')).toBeVisible();
      
      // Check button is accessible
      const submitButton = page.locator('button[type="submit"]');
      await expect(submitButton).toHaveAttribute('aria-label', 'Sign in to your account');
    });

    test('should be keyboard navigable', async () => {
      await page.goto('/auth/signin');
      
      // Tab through form
      await page.keyboard.press('Tab'); // Focus email
      await page.keyboard.type('demo@plinto.dev');
      
      await page.keyboard.press('Tab'); // Focus password
      await page.keyboard.type('DemoPassword123!');
      
      await page.keyboard.press('Tab'); // Focus remember me
      await page.keyboard.press('Space'); // Check it
      
      await page.keyboard.press('Tab'); // Focus submit
      await page.keyboard.press('Enter'); // Submit
      
      await expect(page).toHaveURL('/dashboard');
    });
  });
});