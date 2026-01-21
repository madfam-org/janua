import { test, expect } from '@playwright/test';
import { BusinessDecisionMakerPersona } from '../fixtures/personas';
import { JourneyMetricsTracker } from '../helpers/journey-metrics';

test.describe('Business Decision Maker Journey', () => {
  let metrics: JourneyMetricsTracker;

  test.beforeEach(() => {
    metrics = new JourneyMetricsTracker();
  });

  test.afterEach(async () => {
    const result = metrics.endJourney(true);
    console.log('Business Decision Maker Journey metrics:', result);
  });

  test('Stage 1: Problem Recognition - Landing Page Assessment', async ({ page }) => {
    metrics.startJourney('bdm-problem-recognition');

    // Navigate to landing page
    await page.goto('http://localhost:3000');
    metrics.checkpoint('landing-page-loaded');

    // Verify value proposition is visible
    await expect(page.getByTestId('hero-section')).toBeVisible();
    const hero = page.getByTestId('hero-section');

    // Should communicate value
    await expect(hero.locator('h1')).toBeVisible();
    await expect(hero.locator('p')).toBeVisible();

    // Should have clear CTAs
    await expect(page.getByTestId('get-started-button')).toBeVisible();
    await expect(page.getByTestId('view-docs-button')).toBeVisible();

    metrics.checkpoint('value-proposition-assessed');
  });

  test('Stage 2: Research - Feature Discovery', async ({ page }) => {
    metrics.startJourney('bdm-research');

    await page.goto('http://localhost:3000');
    metrics.checkpoint('landing-page-loaded');

    // Verify features section
    await expect(page.getByTestId('features-section')).toBeVisible();
    metrics.checkpoint('features-section-found');

    // Verify all key features are highlighted
    const features = [
      'feature-signup',
      'feature-login',
      'feature-mfa',
      'feature-passkey',
      'feature-profile',
      'feature-security'
    ];

    for (const feature of features) {
      await expect(page.getByTestId(feature)).toBeVisible();
      metrics.checkpoint(`feature-${feature}-verified`);
    }

    // Verify feature descriptions exist
    const featureCards = page.locator('.feature-card');
    const count = await featureCards.count();
    expect(count).toBeGreaterThanOrEqual(6);

    metrics.checkpoint('feature-discovery-complete');
  });

  test('Stage 3: Evaluation - Quick Trial Signup', async ({ page }) => {
    metrics.startJourney('bdm-evaluation');

    const persona = BusinessDecisionMakerPersona.createCTO();

    // Navigate to signup
    await page.goto('http://localhost:3001/signup');
    metrics.checkpoint('signup-page-loaded');

    // Evaluate signup simplicity
    const formFields = [
      'name-input',
      'email-input',
      'password-input'
    ];

    for (const field of formFields) {
      await expect(page.getByTestId(field)).toBeVisible();
    }

    // Quick signup (evaluating ease of onboarding)
    await page.getByTestId('name-input').fill(persona.name);
    await page.getByTestId('email-input').fill(persona.email);
    await page.getByTestId('password-input').fill(persona.password);

    const startTime = Date.now();
    await page.getByTestId('signup-submit').click();
    await page.waitForURL('**/dashboard', { timeout: 10000 });
    const signupTime = Date.now() - startTime;

    metrics.checkpoint('signup-completed');

    // Evaluate time to value (should be quick)
    console.log(`Time to signup: ${signupTime}ms`);
    expect(signupTime).toBeLessThan(5000); // Should complete in <5 seconds

    // Verify immediate access to dashboard
    await expect(page.getByTestId('dashboard')).toBeVisible();
    metrics.checkpoint('immediate-access-verified');
  });

  test('Stage 4: Comparison - Feature Completeness', async ({ page }) => {
    metrics.startJourney('bdm-comparison');

    const persona = BusinessDecisionMakerPersona.createProductManager();

    // Create account to access features
    await page.goto('http://localhost:3001/signup');
    await page.getByTestId('name-input').fill(persona.name);
    await page.getByTestId('email-input').fill(persona.email);
    await page.getByTestId('password-input').fill(persona.password);
    await page.getByTestId('signup-submit').click();
    await page.waitForURL('**/dashboard');
    metrics.checkpoint('account-created');

    // Evaluate feature availability
    const _expectedFeatures = {
      'dashboard': true,
      'profile-management': true,
      'security-settings': true,
      'mfa': true,
      'passkey': true,
      'password-change': true
    };

    // Verify dashboard access
    await expect(page.getByTestId('dashboard')).toBeVisible();
    metrics.checkpoint('dashboard-verified');

    // Verify profile management
    await page.getByTestId('profile-link').click();
    await page.waitForURL('**/profile');
    await expect(page.getByTestId('profile-form')).toBeVisible();
    metrics.checkpoint('profile-management-verified');

    // Verify security settings
    await page.getByTestId('security-link').click();
    await page.waitForURL('**/security');
    await expect(page.getByTestId('mfa-section')).toBeVisible();
    await expect(page.getByTestId('password-section')).toBeVisible();
    await expect(page.getByTestId('passkey-section')).toBeVisible();
    metrics.checkpoint('security-features-verified');

    // Feature completeness score
    console.log('Feature completeness: 100%');
  });

  test('Stage 5: Trial - User Experience Testing', async ({ page }) => {
    metrics.startJourney('bdm-trial');

    const persona = BusinessDecisionMakerPersona.createCTO();

    // Complete signup
    await page.goto('http://localhost:3001/signup');
    await page.getByTestId('name-input').fill(persona.name);
    await page.getByTestId('email-input').fill(persona.email);
    await page.getByTestId('password-input').fill(persona.password);
    await page.getByTestId('signup-submit').click();
    await page.waitForURL('**/dashboard');
    metrics.checkpoint('onboarding-complete');

    // Test core workflows
    // 1. Profile update
    await page.getByTestId('profile-link').click();
    await page.waitForURL('**/profile');
    await page.getByTestId('name-input').clear();
    await page.getByTestId('name-input').fill('Updated CTO Name');
    await page.getByTestId('update-profile-button').click();
    await page.waitForSelector('[data-testid="success-message"]');
    metrics.checkpoint('profile-update-successful');

    // 2. Security enhancement
    await page.getByTestId('security-link').click();
    await page.waitForURL('**/security');
    await page.getByTestId('enable-mfa-button').click();
    await page.waitForSelector('[data-testid="mfa-setup"]');
    await expect(page.getByTestId('mfa-qr-code')).toBeVisible();
    metrics.checkpoint('mfa-setup-successful');

    // 3. Password management
    await page.getByTestId('current-password-input').fill(persona.password);
    await page.getByTestId('new-password-input').fill('NewCTOPass123!');
    await page.getByTestId('change-password-button').click();
    await page.waitForSelector('[data-testid="success-message"]');
    metrics.checkpoint('password-change-successful');

    // Evaluate UX: All workflows completed successfully
    console.log('User experience: Positive - All workflows functional');
  });

  test('Stage 6: Purchase Decision - Production Readiness', async ({ page }) => {
    metrics.startJourney('bdm-purchase-decision');

    const persona = BusinessDecisionMakerPersona.createVPEngineering();

    // Evaluate production readiness factors
    await page.goto('http://localhost:3000');
    metrics.checkpoint('evaluation-started');

    // 1. Performance (page load time)
    const startTime = Date.now();
    await page.waitForLoadState('networkidle');
    const loadTime = Date.now() - startTime;
    console.log(`Page load time: ${loadTime}ms`);
    expect(loadTime).toBeLessThan(3000); // Should load quickly
    metrics.checkpoint('performance-evaluated');

    // 2. Security features availability
    await expect(page.getByTestId('feature-mfa')).toBeVisible();
    await expect(page.getByTestId('feature-passkey')).toBeVisible();
    await expect(page.getByTestId('feature-security')).toBeVisible();
    metrics.checkpoint('security-features-confirmed');

    // 3. Create account to test reliability
    await page.goto('http://localhost:3001/signup');
    await page.getByTestId('name-input').fill(persona.name);
    await page.getByTestId('email-input').fill(persona.email);
    await page.getByTestId('password-input').fill(persona.password);
    await page.getByTestId('signup-submit').click();
    await page.waitForURL('**/dashboard');
    metrics.checkpoint('reliability-tested');

    // 4. Test error handling (logout and retry login with wrong password)
    await page.getByTestId('logout-button').click();
    await page.waitForURL('**/');

    await page.goto('http://localhost:3001/login');
    await page.getByTestId('email-input').fill(persona.email);
    await page.getByTestId('password-input').fill('WrongPassword123!');
    await page.getByTestId('login-submit').click();

    // Should show error gracefully
    await expect(page.getByTestId('error-message')).toBeVisible();
    metrics.checkpoint('error-handling-verified');

    console.log('Production readiness: APPROVED');
  });

  test('Stage 7: Onboarding - Implementation Simplicity', async ({ page }) => {
    metrics.startJourney('bdm-onboarding');

    const persona = BusinessDecisionMakerPersona.createCTO();

    // Evaluate onboarding simplicity (time to first successful auth)
    const onboardingStart = Date.now();

    await page.goto('http://localhost:3001/signup');

    await page.getByTestId('name-input').fill(persona.name);
    await page.getByTestId('email-input').fill(persona.email);
    await page.getByTestId('password-input').fill(persona.password);
    await page.getByTestId('signup-submit').click();
    await page.waitForURL('**/dashboard');

    const onboardingTime = Date.now() - onboardingStart;
    metrics.checkpoint('onboarding-complete');

    console.log(`Time to first auth: ${onboardingTime}ms`);

    // Onboarding should be quick (<30 seconds total)
    expect(onboardingTime).toBeLessThan(30000);

    // Verify immediate functionality
    await expect(page.getByTestId('dashboard')).toBeVisible();
    await expect(page.getByTestId('user-info-card')).toBeVisible();
    await expect(page.getByTestId('quick-actions-card')).toBeVisible();
    await expect(page.getByTestId('security-status-card')).toBeVisible();

    metrics.checkpoint('immediate-value-confirmed');

    console.log('Onboarding assessment: SIMPLE and FAST');
  });

  test('Complete Business Decision Maker Journey', async ({ page }) => {
    metrics.startJourney('bdm-complete');

    const persona = BusinessDecisionMakerPersona.createProductManager();

    // 1. Problem Recognition
    await page.goto('http://localhost:3000');
    await expect(page.getByTestId('hero-section')).toBeVisible();
    metrics.checkpoint('problem-recognized');

    // 2. Research
    await expect(page.getByTestId('features-section')).toBeVisible();
    const featureCards = page.locator('.feature-card');
    expect(await featureCards.count()).toBeGreaterThanOrEqual(6);
    metrics.checkpoint('research-completed');

    // 3. Evaluation (Quick Trial)
    await page.goto('http://localhost:3001/signup');
    await page.getByTestId('name-input').fill(persona.name);
    await page.getByTestId('email-input').fill(persona.email);
    await page.getByTestId('password-input').fill(persona.password);

    const signupStart = Date.now();
    await page.getByTestId('signup-submit').click();
    await page.waitForURL('**/dashboard');
    const signupTime = Date.now() - signupStart;

    expect(signupTime).toBeLessThan(5000);
    metrics.checkpoint('evaluation-completed');

    // 4. Comparison (Feature Testing)
    await page.getByTestId('profile-link').click();
    await page.waitForURL('**/profile');
    await expect(page.getByTestId('profile-form')).toBeVisible();

    await page.getByTestId('security-link').click();
    await page.waitForURL('**/security');
    await expect(page.getByTestId('mfa-section')).toBeVisible();
    metrics.checkpoint('comparison-completed');

    // 5. Trial (Comprehensive Testing)
    await page.getByTestId('enable-mfa-button').click();
    await page.waitForSelector('[data-testid="mfa-setup"]');
    await expect(page.getByTestId('mfa-qr-code')).toBeVisible();
    metrics.checkpoint('trial-completed');

    // 6. Purchase Decision (Production Readiness Check)
    // All features working = Production Ready
    await page.getByTestId('dashboard-link').click();
    await page.waitForURL('**/dashboard');
    await expect(page.getByTestId('security-status-card')).toBeVisible();
    metrics.checkpoint('production-readiness-confirmed');

    // 7. Decision: APPROVED
    console.log('='.repeat(60));
    console.log('BUSINESS DECISION MAKER ASSESSMENT: APPROVED');
    console.log('- Fast onboarding: ✓');
    console.log('- Complete features: ✓');
    console.log('- Production ready: ✓');
    console.log('- User experience: Positive');
    console.log('='.repeat(60));

    metrics.checkpoint('decision-made');
  });
});
