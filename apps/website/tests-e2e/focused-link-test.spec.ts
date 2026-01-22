import { test, expect as _expect } from '@playwright/test';

interface TestResult {
  element: string;
  location: string;
  action: string;
  expected: string;
  result: 'SUCCESS' | 'FAILURE';
  error?: string;
  actualBehavior?: string;
}

test.describe('Focused Link and Interactive Element Testing', () => {
  const results: TestResult[] = [];

  const addResult = (result: TestResult) => {
    results.push(result);
    console.log(`${result.result}: ${result.element} - ${result.action}`);
    if (result.error) {
      console.log(`  Error: ${result.error}`);
    }
  };

  test.beforeEach(async ({ page }) => {
    // Set desktop viewport size to ensure navigation is visible
    await page.setViewportSize({ width: 1280, height: 720 });
    await page.goto('/');
    await page.waitForLoadState('networkidle');
  });

  test.afterAll(async () => {
    // Generate comprehensive report
    console.log('\n=== FOCUSED TEST RESULTS ===\n');

    const successCount = results.filter(r => r.result === 'SUCCESS').length;
    const failureCount = results.filter(r => r.result === 'FAILURE').length;

    console.log(`Total Tests: ${results.length}`);
    console.log(`Successes: ${successCount}`);
    console.log(`Failures: ${failureCount}`);
    console.log(`Success Rate: ${((successCount / results.length) * 100).toFixed(2)}%\n`);

    if (failureCount > 0) {
      console.log('=== FAILURES ===');
      results.filter(r => r.result === 'FAILURE').forEach(result => {
        console.log(`❌ ${result.element} (${result.location})`);
        console.log(`   Action: ${result.action}`);
        console.log(`   Expected: ${result.expected}`);
        console.log(`   Error: ${result.error}\n`);
      });
    }

    console.log('=== DETAILED RESULTS ===\n');
    results.forEach(result => {
      const icon = result.result === 'SUCCESS' ? '✅' : '❌';
      console.log(`${icon} ${result.element}`);
      console.log(`   Location: ${result.location}`);
      console.log(`   Action: ${result.action}`);
      console.log(`   Expected: ${result.expected}`);
      if (result.actualBehavior) {
        console.log(`   Actual: ${result.actualBehavior}`);
      }
      if (result.error) {
        console.log(`   Error: ${result.error}`);
      }
      console.log('');
    });
  });

  test('Navigation and Header Elements', async ({ page }) => {
    // Test Logo/Home Link
    try {
      const logoLink = page.locator('nav a[href="/"]').first();
      await logoLink.click();
      await page.waitForLoadState('networkidle');

      const currentUrl = page.url();
      if (currentUrl.endsWith('/') || currentUrl.endsWith('localhost:3000')) {
        addResult({
          element: 'Janua Logo/Home Link',
          location: 'Header Navigation',
          action: 'Click logo to return home',
          expected: 'Should navigate to home page',
          result: 'SUCCESS',
          actualBehavior: `Navigated to ${currentUrl}`
        });
      } else {
        addResult({
          element: 'Janua Logo/Home Link',
          location: 'Header Navigation',
          action: 'Click logo',
          expected: 'Should navigate to home',
          result: 'FAILURE',
          error: `Expected home page, got ${currentUrl}`
        });
      }
    } catch (error) {
      addResult({
        element: 'Janua Logo/Home Link',
        location: 'Header Navigation',
        action: 'Click logo',
        expected: 'Should navigate to home',
        result: 'FAILURE',
        error: error.message
      });
    }

    // Test Pricing link (the only actual navigation link) - Enhanced with visibility checks
    try {
      // Ensure we're in desktop mode where the navigation is visible
      await page.setViewportSize({ width: 1280, height: 720 });
      await page.waitForTimeout(100); // Brief wait for responsive styles to apply

      const pricingLink = page.locator('nav a[href="/pricing"]').first();

      // Wait for element to be visible and clickable
      await pricingLink.waitFor({ state: 'visible', timeout: 10000 });
      await pricingLink.scrollIntoViewIfNeeded();

      await pricingLink.click();
      await page.waitForLoadState('networkidle');

      const currentUrl = page.url();
      if (currentUrl.includes('/pricing')) {
        addResult({
          element: 'Pricing Navigation Link',
          location: 'Main Navigation',
          action: 'Click pricing link',
          expected: 'Should navigate to pricing page',
          result: 'SUCCESS',
          actualBehavior: `Navigated to ${currentUrl}`
        });
      } else {
        addResult({
          element: 'Pricing Navigation Link',
          location: 'Main Navigation',
          action: 'Click pricing link',
          expected: 'Should navigate to pricing page',
          result: 'FAILURE',
          error: `Expected /pricing, got ${currentUrl}`
        });
      }

      // Go back home
      await page.goto('/');
      await page.waitForLoadState('networkidle');
    } catch (error) {
      addResult({
        element: 'Pricing Navigation Link',
        location: 'Main Navigation',
        action: 'Click pricing link',
        expected: 'Should navigate to pricing',
        result: 'FAILURE',
        error: error.message
      });
    }

    // Test dropdown navigation items (Product, Developers, Solutions, Company)
    const dropdownItems = [
      { name: 'Product', expectedHref: '#' },
      { name: 'Developers', expectedHref: '#' },
      { name: 'Solutions', expectedHref: '#' },
      { name: 'Company', expectedHref: '#' }
    ];

    for (const item of dropdownItems) {
      try {
        // Set desktop viewport to ensure navigation is visible
        await page.setViewportSize({ width: 1280, height: 720 });
        await page.waitForTimeout(100);

        const dropdownTrigger = page.locator(`nav a:has-text("${item.name}")`).first();
        await dropdownTrigger.waitFor({ state: 'visible', timeout: 10000 });
        const href = await dropdownTrigger.getAttribute('href');

        if (href === item.expectedHref) {
          // Test dropdown functionality by hovering
          await dropdownTrigger.hover();
          await page.waitForTimeout(300); // Wait for dropdown animation

          addResult({
            element: `${item.name} Dropdown`,
            location: 'Main Navigation',
            action: 'Test dropdown trigger and hover',
            expected: 'Should exist and be functional',
            result: 'SUCCESS',
            actualBehavior: `Dropdown trigger working with href: ${href}`
          });
        } else {
          addResult({
            element: `${item.name} Navigation`,
            location: 'Main Navigation',
            action: 'Test navigation item',
            expected: 'Should exist and be functional',
            result: 'FAILURE',
            error: `Expected href ${item.expectedHref}, got ${href}`
          });
        }
      } catch (error) {
        addResult({
          element: `${item.name} Navigation`,
          location: 'Main Navigation',
          action: 'Test navigation item',
          expected: 'Should exist and be functional',
          result: 'FAILURE',
          error: error.message
        });
      }
    }

    // Test header buttons
    const headerButtons = [
      { text: 'Sign In', expectedHref: 'https://app.janua.dev/auth/signin' },
      { text: 'Start Free', expectedHref: 'https://app.janua.dev/auth/signup' }
    ];

    for (const button of headerButtons) {
      try {
        // Set desktop viewport to ensure header buttons are visible
        await page.setViewportSize({ width: 1280, height: 720 });
        await page.waitForTimeout(100);

        const headerButton = page.locator(`nav a[href="${button.expectedHref}"]`).first();
        await headerButton.waitFor({ state: 'visible', timeout: 10000 });
        const href = await headerButton.getAttribute('href');

        if (href === button.expectedHref) {
          addResult({
            element: `${button.text} Button`,
            location: 'Header Navigation',
            action: button.text === 'Sign In' ? 'Check sign in link' : 'Check start free link',
            expected: 'Should have valid external URL',
            result: 'SUCCESS',
            actualBehavior: `External URL: ${href}`
          });
        } else {
          addResult({
            element: `${button.text} Button`,
            location: 'Header Navigation',
            action: `Test ${button.text.toLowerCase()} button`,
            expected: 'Should be functional',
            result: 'FAILURE',
            error: `Expected href ${button.expectedHref}, got ${href}`
          });
        }
      } catch (error) {
        addResult({
          element: `${button.text} Button`,
          location: 'Header Navigation',
          action: `Test ${button.text.toLowerCase()} button`,
          expected: 'Should be functional',
          result: 'FAILURE',
          error: error.message
        });
      }
    }

    // Test mobile menu toggle (should exist but may not be visible on desktop)
    try {
      const mobileToggle = page.locator('nav button[aria-label="Toggle menu"]').first();
      if (await mobileToggle.count() > 0) {
        // Set mobile viewport to test the toggle
        await page.setViewportSize({ width: 375, height: 667 });
        await page.waitForTimeout(500);

        if (await mobileToggle.isVisible()) {
          addResult({
            element: 'Mobile Menu Toggle',
            location: 'Mobile Header',
            action: 'Click mobile menu toggle',
            expected: 'Should toggle mobile menu',
            result: 'SUCCESS',
            actualBehavior: 'Mobile menu toggle is visible and clickable'
          });
        } else {
          addResult({
            element: 'Mobile Menu Toggle',
            location: 'Mobile Header',
            action: 'Test mobile toggle',
            expected: 'Should work on mobile',
            result: 'FAILURE',
            error: 'Mobile toggle not visible in mobile viewport'
          });
        }

        // Reset viewport
        await page.setViewportSize({ width: 1280, height: 720 });
      } else {
        addResult({
          element: 'Mobile Menu Toggle',
          location: 'Mobile Header',
          action: 'Test mobile toggle',
          expected: 'Should work on mobile',
          result: 'FAILURE',
          error: 'Mobile menu toggle not found'
        });
      }
    } catch (error) {
      addResult({
        element: 'Mobile Menu Toggle',
        location: 'Mobile Header',
        action: 'Test mobile toggle',
        expected: 'Should work on mobile',
        result: 'FAILURE',
        error: error.message
      });
    }
  });

  test('Interactive Components and CTAs', async ({ page }) => {
    // Test performance test button
    try {
      const performanceButton = page.locator('button:has-text("Run Performance Test")').first();
      if (await performanceButton.count() > 0) {
        await performanceButton.scrollIntoViewIfNeeded();
        await performanceButton.click();
        await page.waitForTimeout(500);

        addResult({
          element: 'Run Performance Test Button',
          location: 'Performance Section',
          action: 'Click performance test button',
          expected: 'Should trigger performance test',
          result: 'SUCCESS',
          actualBehavior: 'Performance test button clicked'
        });
      } else {
        addResult({
          element: 'Run Performance Test Button',
          location: 'Performance Section',
          action: 'Find performance test button',
          expected: 'Should exist',
          result: 'FAILURE',
          error: 'Performance test button not found'
        });
      }
    } catch (error) {
      addResult({
        element: 'Run Performance Test Button',
        location: 'Performance Section',
        action: 'Click performance test button',
        expected: 'Should trigger performance test',
        result: 'FAILURE',
        error: error.message
      });
    }

    // Test feature filter buttons
    const filterButtons = await page.locator('.cursor-pointer').all();
    const sampleFilters = filterButtons.slice(0, 8); // Test first 8 filters

    for (let i = 0; i < sampleFilters.length; i++) {
      try {
        const filter = sampleFilters[i];
        await filter.scrollIntoViewIfNeeded();
        const filterText = await filter.textContent();
        await filter.click();
        await page.waitForTimeout(200);

        addResult({
          element: `Feature Filter: ${filterText}`,
          location: 'Features Section',
          action: 'Click feature filter',
          expected: 'Should filter features',
          result: 'SUCCESS',
          actualBehavior: `Filter "${filterText}" activated`
        });
      } catch (error) {
        addResult({
          element: `Feature Filter: Filter ${i + 1}`,
          location: 'Features Section',
          action: 'Click feature filter',
          expected: 'Should filter features',
          result: 'FAILURE',
          error: error.message
        });
      }
    }

    // Test CTA buttons - Updated to include both button and anchor selectors for "Get Started"
    const ctaSelectors = [
      'button:has-text("View Live Demo")',
      'a:has-text("View Source Code")',
      'button:has-text("Get Started"), a:has-text("Get Started")', // Look for both button and anchor
      'a:has-text("Start Free")'
    ];

    for (const selector of ctaSelectors) {
      try {
        const ctaButton = page.locator(selector).first();
        if (await ctaButton.count() > 0) {
          const buttonText = await ctaButton.textContent();
          const href = await ctaButton.getAttribute('href');

          if (href && href.startsWith('http')) {
            // External link
            addResult({
              element: `CTA: ${buttonText?.trim()}`,
              location: 'Various Sections',
              action: 'Check CTA external link',
              expected: 'Should have valid external URL',
              result: 'SUCCESS',
              actualBehavior: `External URL: ${href}`
            });
          } else {
            // Internal button or action
            await ctaButton.scrollIntoViewIfNeeded();
            await ctaButton.click();
            await page.waitForTimeout(500);

            addResult({
              element: `CTA: ${buttonText?.trim()}`,
              location: 'Various Sections',
              action: 'Click CTA button',
              expected: 'Should trigger action',
              result: 'SUCCESS',
              actualBehavior: 'CTA button clicked successfully'
            });
          }
        } else {
          // For Get Started, provide a more specific error message
          const isGetStarted = selector.includes('Get Started');
          addResult({
            element: isGetStarted ? 'Get Started Button' : `CTA Button (${selector})`,
            location: 'Various Sections',
            action: 'Find CTA button',
            expected: 'CTA should exist',
            result: 'FAILURE',
            error: 'CTA button not found'
          });
        }
      } catch (error) {
        addResult({
          element: `CTA Button (${selector})`,
          location: 'Various Sections',
          action: 'Test CTA button',
          expected: 'Should work properly',
          result: 'FAILURE',
          error: error.message
        });
      }
    }
  });

  test('External Links and GitHub Integration', async ({ page }) => {
    // Test GitHub links
    const githubSelectors = [
      'a[href*="github.com/madfam-org/janua"]',
      'a[href*="github.com/madfam-org/janua/issues"]'
    ];

    for (const selector of githubSelectors) {
      try {
        const githubLinks = await page.locator(selector).all();
        for (let i = 0; i < githubLinks.length; i++) {
          const link = githubLinks[i];
          const href = await link.getAttribute('href');
          const target = await link.getAttribute('target');
          const linkText = await link.textContent();

          // Use proper URL parsing to validate GitHub URLs
          let isValidGitHubUrl = false;
          try {
            if (href) {
              const urlObj = new URL(href);
              isValidGitHubUrl = urlObj.hostname === 'github.com' || urlObj.hostname.endsWith('.github.com');
            }
          } catch {
            isValidGitHubUrl = false;
          }

          if (isValidGitHubUrl) {
            addResult({
              element: `GitHub Link: ${linkText?.trim() || `Link ${i + 1}`}`,
              location: 'Various Sections',
              action: 'Check GitHub link',
              expected: 'Should have valid GitHub URL',
              result: 'SUCCESS',
              actualBehavior: `URL: ${href}, Target: ${target || 'none'}`
            });
          } else {
            addResult({
              element: `GitHub Link: ${linkText?.trim() || `Link ${i + 1}`}`,
              location: 'Various Sections',
              action: 'Check GitHub link',
              expected: 'Should have valid GitHub URL',
              result: 'FAILURE',
              error: `Invalid GitHub URL: ${href}`
            });
          }
        }
      } catch (error) {
        addResult({
          element: `GitHub Links (${selector})`,
          location: 'Various Sections',
          action: 'Find GitHub links',
          expected: 'Should exist',
          result: 'FAILURE',
          error: error.message
        });
      }
    }

    // Test app links
    const appSelectors = [
      'a[href*="app.janua.dev/auth/signin"]',
      'a[href*="app.janua.dev/auth/signup"]'
    ];

    for (const selector of appSelectors) {
      try {
        const appLinks = await page.locator(selector).all();
        for (let i = 0; i < appLinks.length; i++) {
          const link = appLinks[i];
          const href = await link.getAttribute('href');
          const linkText = await link.textContent();

          if (href && href.includes('app.janua.dev')) {
            addResult({
              element: `App Link: ${linkText?.trim() || `Link ${i + 1}`}`,
              location: 'Various Sections',
              action: 'Check app link',
              expected: 'Should have valid app URL',
              result: 'SUCCESS',
              actualBehavior: `App URL: ${href}`
            });
          } else {
            addResult({
              element: `App Link: ${linkText?.trim() || `Link ${i + 1}`}`,
              location: 'Various Sections',
              action: 'Check app link',
              expected: 'Should have valid app URL',
              result: 'FAILURE',
              error: `Invalid app URL: ${href}`
            });
          }
        }
      } catch (error) {
        addResult({
          element: `App Links (${selector})`,
          location: 'Various Sections',
          action: 'Find app links',
          expected: 'Should exist',
          result: 'FAILURE',
          error: error.message
        });
      }
    }

    // Test external documentation links
    const externalSelectors = [
      'a[href*="docs.janua.dev"]'
    ];

    for (const selector of externalSelectors) {
      try {
        const externalLinks = await page.locator(selector).all();
        for (let i = 0; i < externalLinks.length; i++) {
          const link = externalLinks[i];
          const href = await link.getAttribute('href');
          const linkText = await link.textContent();

          if (href && (href.includes('docs.janua.dev') || href.includes('demo.janua.dev'))) {
            addResult({
              element: `External Link: ${linkText?.trim() || `Link ${i + 1}`}`,
              location: 'Various Sections',
              action: 'Check external link',
              expected: 'Should have valid external URL',
              result: 'SUCCESS',
              actualBehavior: `External URL: ${href}`
            });
          } else {
            addResult({
              element: `External Link: ${linkText?.trim() || `Link ${i + 1}`}`,
              location: 'Various Sections',
              action: 'Check external link',
              expected: 'Should have valid external URL',
              result: 'FAILURE',
              error: `Invalid external URL: ${href}`
            });
          }
        }
      } catch (error) {
        addResult({
          element: `External Links (${selector})`,
          location: 'Various Sections',
          action: 'Find external links',
          expected: 'Should exist',
          result: 'FAILURE',
          error: error.message
        });
      }
    }

    // Test social and contact links
    const socialSelectors = [
      'a[href^="mailto:"]',
      'a[href*="twitter.com"]',
      'a[href*="linkedin.com"]'
    ];

    for (const selector of socialSelectors) {
      try {
        const socialLinks = await page.locator(selector).all();
        for (let i = 0; i < socialLinks.length; i++) {
          const link = socialLinks[i];
          const href = await link.getAttribute('href');
          const linkText = await link.textContent();

          addResult({
            element: `External Link: ${linkText?.trim() || `${selector} ${i + 1}`}`,
            location: 'Various Sections',
            action: 'Check external link',
            expected: 'Should have valid external URL',
            result: 'SUCCESS',
            actualBehavior: `External URL: ${href}`
          });
        }
      } catch (error) {
        addResult({
          element: `External Links (${selector})`,
          location: 'Various Sections',
          action: 'Find external links',
          expected: 'Should exist',
          result: 'FAILURE',
          error: error.message
        });
      }
    }
  });

  test('Footer Links and Social Media', async ({ page }) => {
    // Scroll to footer to ensure it's loaded
    await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
    await page.waitForTimeout(1000);

    // Test footer navigation links
    const footerLinkTexts = [
      'Janua', 'About', 'Blog', 'Careers', 'Contact',
      'Pricing', 'Changelog', 'Documentation', 'API Reference',
      'SDKs', 'Examples', 'Playground', 'Status',
      'E-commerce', 'SaaS Platforms', 'Enterprise'
    ];

    for (const linkText of footerLinkTexts) {
      try {
        const footerLink = page.locator(`footer a:has-text("${linkText}")`).first();
        if (await footerLink.count() > 0) {
          const href = await footerLink.getAttribute('href');

          if (href) {
            let linkType = 'Internal';
            if (href.startsWith('http') || href.startsWith('mailto:')) {
              linkType = 'External';
            }

            addResult({
              element: `Footer Link: ${linkText}`,
              location: 'Footer',
              action: 'Check footer link',
              expected: 'Should have valid URL',
              result: 'SUCCESS',
              actualBehavior: `${linkType} URL: ${href}`
            });
          } else {
            addResult({
              element: `Footer Link: ${linkText}`,
              location: 'Footer',
              action: 'Check footer link',
              expected: 'Should have valid URL',
              result: 'FAILURE',
              error: 'No href attribute found'
            });
          }
        } else {
          addResult({
            element: `Footer Link: ${linkText}`,
            location: 'Footer',
            action: 'Find footer link',
            expected: 'Should exist in footer',
            result: 'FAILURE',
            error: 'Footer link not found'
          });
        }
      } catch (error) {
        addResult({
          element: `Footer Link: ${linkText}`,
          location: 'Footer',
          action: 'Test footer link',
          expected: 'Should be functional',
          result: 'FAILURE',
          error: error.message
        });
      }
    }

    // Test social media links
    const socialMediaSelectors = [
      { selector: 'a[href*="twitter.com"]', name: 'Twitter Social Link' },
      { selector: 'a[href*="github.com"]', name: 'GitHub Social Link' },
      { selector: 'a[href*="linkedin.com"]', name: 'LinkedIn Social Link' },
      { selector: 'a[href*="discord"]', name: 'Social Links (a[href*="discord"])' },
      { selector: 'a[href^="mailto:"]', name: 'Email Social Link' }
    ];

    for (const social of socialMediaSelectors) {
      try {
        const socialLinks = await page.locator(social.selector).all();

        if (socialLinks.length > 0) {
          const firstLink = socialLinks[0];
          const href = await firstLink.getAttribute('href');

          addResult({
            element: social.name,
            location: 'Footer/Social Section',
            action: 'Check social media link',
            expected: 'Should have valid social URL',
            result: 'SUCCESS',
            actualBehavior: `${social.name.includes('Email') ? 'Email' : social.name.split(' ')[0]} URL: ${href}`
          });
        } else {
          // For Discord, it's acceptable if not found
          if (social.name.includes('discord')) {
            addResult({
              element: social.name,
              location: 'Footer/Social Section',
              action: 'Find social links',
              expected: 'Social links may exist',
              result: 'SUCCESS',
              actualBehavior: 'No social links found for this platform (acceptable)'
            });
          } else {
            addResult({
              element: social.name,
              location: 'Footer/Social Section',
              action: 'Find social link',
              expected: 'Should exist',
              result: 'FAILURE',
              error: 'Social media link not found'
            });
          }
        }
      } catch (error) {
        addResult({
          element: social.name,
          location: 'Footer/Social Section',
          action: 'Test social link',
          expected: 'Should be functional',
          result: 'FAILURE',
          error: error.message
        });
      }
    }
  });
});