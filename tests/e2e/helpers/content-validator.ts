/**
 * Content-Functionality Alignment Validator
 * 
 * Validates that marketing claims, documentation, and pricing
 * accurately reflect the actual implemented functionality.
 */

import { Page } from '@playwright/test';
import { execSync } from 'child_process';
import * as fs from 'fs';
import * as path from 'path';

export interface FeatureValidationResult {
  claimed: string;
  implemented: boolean;
  implementationPaths: string[];
  confidence: 'high' | 'medium' | 'low';
}

export interface PricingValidationResult {
  tier: string;
  claimedLimit: string;
  actualLimit: string;
  matches: boolean;
  source: string;
}

/**
 * Content Validator
 */
export class ContentValidator {
  
  /**
   * Validate claimed feature exists in codebase
   */
  static async validateFeatureClaim(
    page: Page,
    featureSelector: string,
    searchPaths: string[] = ['apps/', 'packages/']
  ): Promise<FeatureValidationResult> {
    // Get claimed feature from page
    const claimedFeature = await page.locator(featureSelector).textContent();
    
    if (!claimedFeature) {
      return {
        claimed: '',
        implemented: false,
        implementationPaths: [],
        confidence: 'low'
      };
    }

    // Extract key terms from feature description
    const searchTerms = this.extractSearchTerms(claimedFeature);
    
    // Search codebase for implementation evidence
    const implementationPaths: string[] = [];
    
    for (const term of searchTerms) {
      const paths = searchPaths.join(' ');
      const searchCmd = `grep -r "${term}" ${paths} --include="*.ts" --include="*.tsx" --include="*.py" -l`;
      
      try {
        const result = execSync(searchCmd, { encoding: 'utf-8', cwd: process.cwd() });
        const foundFiles = result.trim().split('\n').filter(f => f);
        implementationPaths.push(...foundFiles);
      } catch {
        // No matches found for this term
      }
    }

    // Deduplicate paths
    const uniquePaths = [...new Set(implementationPaths)];
    
    return {
      claimed: claimedFeature,
      implemented: uniquePaths.length > 0,
      implementationPaths: uniquePaths,
      confidence: this.assessConfidence(claimedFeature, uniquePaths)
    };
  }

  /**
   * Validate pricing tier limits match billing service
   */
  static async validatePricingClaims(page: Page): Promise<PricingValidationResult[]> {
    const results: PricingValidationResult[] = [];
    
    await page.goto('http://localhost:3000/pricing');
    
    // Extract tier information from page
    const tiers = await page.locator('[data-testid*="tier"]').count();
    
    for (let i = 0; i < tiers; i++) {
      const tierElement = page.locator('[data-testid*="tier"]').nth(i);
      const tierName = await tierElement.getAttribute('data-testid');
      const userLimit = await tierElement.locator('[data-testid*="users"]').textContent();
      
      if (tierName && userLimit) {
        // Extract numeric limit from text (e.g., "1,000 users" → 1000)
        const claimedLimit = userLimit.replace(/[^0-9]/g, '');
        
        // Read actual limit from billing service code
        const actualLimit = this.getBillingServiceLimit(tierName);
        
        results.push({
          tier: tierName,
          claimedLimit: userLimit,
          actualLimit: actualLimit.toString(),
          matches: claimedLimit === actualLimit.toString(),
          source: 'apps/api/app/services/billing.py'
        });
      }
    }
    
    return results;
  }

  /**
   * Validate API examples in docs actually work
   */
  static async validateCodeExamples(page: Page, exampleSelector: string): Promise<boolean> {
    // Get code example from documentation
    const exampleCode = await page.locator(exampleSelector).textContent();
    
    if (!exampleCode) {
      return false;
    }

    // Write to temp file
    const tempFile = path.join('/tmp', `test-example-${Date.now()}.ts`);
    fs.writeFileSync(tempFile, exampleCode);
    
    try {
      // Attempt to compile (validates syntax and types)
      execSync(`npx tsc ${tempFile} --noEmit --skipLibCheck`, { 
        encoding: 'utf-8',
        cwd: process.cwd()
      });
      
      // Clean up temp file
      fs.unlinkSync(tempFile);
      
      return true; // Code example is valid TypeScript
    } catch (error) {
      // Clean up temp file even on failure
      if (fs.existsSync(tempFile)) {
        fs.unlinkSync(tempFile);
      }
      
      console.error(`Code example validation failed:`, error);
      return false;
    }
  }

  /**
   * Validate documentation matches SDK signatures
   */
  static async validateSDKDocumentation(
    documentedAPI: string,
    sdkPath: string
  ): Promise<boolean> {
    try {
      const sdkContent = fs.readFileSync(sdkPath, 'utf-8');
      
      // Extract function/method signatures from documentation
      const docSignatures = this.extractSignatures(documentedAPI);
      
      // Check if each signature exists in SDK
      for (const signature of docSignatures) {
        if (!sdkContent.includes(signature)) {
          console.warn(`Signature not found in SDK: ${signature}`);
          return false;
        }
      }
      
      return true;
    } catch (error) {
      console.error(`SDK documentation validation failed:`, error);
      return false;
    }
  }

  /**
   * Compare feature set across marketing, docs, and implementation
   */
  static async validateFeatureConsistency(
    marketingPage: Page,
    docsPage: Page
  ): Promise<{ consistent: boolean; mismatches: string[] }> {
    const mismatches: string[] = [];
    
    // Get features from marketing page
    await marketingPage.goto('http://localhost:3000/features');
    const marketingFeatures = await marketingPage
      .locator('[data-testid="feature-name"]')
      .allTextContents();
    
    // Get features from documentation
    await docsPage.goto('http://localhost:3000/docs');
    const docFeatures = await docsPage
      .locator('[data-testid="documented-feature"]')
      .allTextContents();
    
    // Check for features in marketing but not in docs
    for (const feature of marketingFeatures) {
      const normalizedFeature = this.normalizeFeatureName(feature);
      const inDocs = docFeatures.some(df => 
        this.normalizeFeatureName(df) === normalizedFeature
      );
      
      if (!inDocs) {
        mismatches.push(`Feature "${feature}" marketed but not documented`);
      }
    }
    
    return {
      consistent: mismatches.length === 0,
      mismatches
    };
  }

  /**
   * Validate performance claims against actual measurements
   */
  static async validatePerformanceClaim(
    claimedTime: number,
    actualTime: number,
    tolerance: number = 0.2 // 20% tolerance
  ): Promise<{ valid: boolean; claimed: number; actual: number; difference: number }> {
    const difference = Math.abs(actualTime - claimedTime);
    const maxDifference = claimedTime * tolerance;
    
    return {
      valid: difference <= maxDifference,
      claimed: claimedTime,
      actual: actualTime,
      difference
    };
  }

  /**
   * Extract search terms from feature description
   * @private
   */
  private static extractSearchTerms(featureText: string): string[] {
    // Remove common words and extract key technical terms
    const stopWords = ['the', 'and', 'or', 'with', 'for', 'in', 'on', 'at'];
    const words = featureText
      .toLowerCase()
      .replace(/[^a-z0-9\s]/g, '')
      .split(/\s+/)
      .filter(word => word.length > 3 && !stopWords.includes(word));
    
    // Also look for camelCase/PascalCase versions
    const camelCaseTerms = words.map(word => 
      word.charAt(0).toUpperCase() + word.slice(1)
    );
    
    return [...words, ...camelCaseTerms];
  }

  /**
   * Assess confidence level based on evidence
   * @private
   */
  private static assessConfidence(
    claim: string,
    implementationPaths: string[]
  ): 'high' | 'medium' | 'low' {
    if (implementationPaths.length === 0) return 'low';
    if (implementationPaths.length >= 3) return 'high';
    return 'medium';
  }

  /**
   * Get billing service limit from code
   * @private
   */
  private static getBillingServiceLimit(tierName: string): number {
    try {
      const billingFile = path.join(process.cwd(), 'apps/api/app/services/billing.py');
      
      if (!fs.existsSync(billingFile)) {
        console.warn('Billing service file not found');
        return -1;
      }

      const billingCode = fs.readFileSync(billingFile, 'utf-8');
      
      // Extract limit constants based on tier name
      const tierKey = tierName.toUpperCase().replace(/-/g, '_');
      const limitPattern = new RegExp(`${tierKey}_USER_LIMIT\\s*=\\s*(\\d+)`);
      const match = billingCode.match(limitPattern);
      
      return match ? parseInt(match[1], 10) : -1;
    } catch (error) {
      console.error('Failed to read billing service limits:', error);
      return -1;
    }
  }

  /**
   * Extract function/method signatures from documentation
   * @private
   */
  private static extractSignatures(docText: string): string[] {
    // Simple extraction of function-like patterns
    const signaturePattern = /(?:function|const|export)\s+([a-zA-Z0-9_]+)\s*\(/g;
    const signatures: string[] = [];
    
    let match;
    while ((match = signaturePattern.exec(docText)) !== null) {
      signatures.push(match[1]);
    }
    
    return signatures;
  }

  /**
   * Normalize feature name for comparison
   * @private
   */
  private static normalizeFeatureName(name: string): string {
    return name
      .toLowerCase()
      .replace(/[^a-z0-9]/g, '')
      .trim();
  }
}

/**
 * Batch validation runner
 */
export class BatchValidator {
  private results: Map<string, any> = new Map();

  /**
   * Run all validation checks
   */
  async runAll(page: Page): Promise<Map<string, any>> {
    this.results.clear();
    
    // Validate features
    const features = await page.locator('[data-testid="feature"]').all();
    for (let i = 0; i < features.length; i++) {
      const result = await ContentValidator.validateFeatureClaim(
        page,
        `[data-testid="feature"]:nth-child(${i + 1})`
      );
      this.results.set(`feature-${i}`, result);
    }
    
    // Validate pricing
    const pricingResults = await ContentValidator.validatePricingClaims(page);
    this.results.set('pricing', pricingResults);
    
    return this.results;
  }

  /**
   * Generate validation report
   */
  generateReport(): { passed: number; failed: number; warnings: string[] } {
    let passed = 0;
    let failed = 0;
    const warnings: string[] = [];
    
    for (const [_key, value] of this.results.entries()) {
      if (Array.isArray(value)) {
        // Pricing results
        for (const item of value) {
          if (item.matches) {
            passed++;
          } else {
            failed++;
            warnings.push(`Pricing mismatch for ${item.tier}: claimed ${item.claimedLimit}, actual ${item.actualLimit}`);
          }
        }
      } else {
        // Feature results
        if (value.implemented) {
          passed++;
        } else {
          failed++;
          warnings.push(`Feature not implemented: ${value.claimed}`);
        }
      }
    }
    
    return { passed, failed, warnings };
  }
}
