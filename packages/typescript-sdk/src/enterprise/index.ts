/**
 * Enterprise License Management for Plinto SDK
 * This module handles license validation and feature gating for enterprise features
 */

export interface LicenseInfo {
  valid: boolean;
  plan: 'community' | 'pro' | 'enterprise';
  features: string[];
  organizationId?: string;
  expiresAt?: Date;
  seats?: number;
  customLimits?: Record<string, any>;
}

export interface EnterpriseConfig {
  licenseKey?: string;
  apiUrl?: string;
  cacheTimeout?: number;
}

export class EnterpriseFeatures {
  private licenseKey?: string;
  private apiUrl: string;
  private licenseCache?: LicenseInfo;
  private cacheExpiry?: Date;
  private cacheTimeout: number;

  constructor(config: EnterpriseConfig = {}) {
    this.licenseKey = config.licenseKey;
    this.apiUrl = config.apiUrl || 'https://api.plinto.dev';
    this.cacheTimeout = config.cacheTimeout || 3600000; // 1 hour default
  }

  /**
   * Set or update the license key
   */
  setLicenseKey(key: string): void {
    this.licenseKey = key;
    this.clearCache();
  }

  /**
   * Validate the current license key
   */
  async validateLicense(): Promise<LicenseInfo> {
    // Return cached license if still valid
    if (this.licenseCache && this.cacheExpiry && new Date() < this.cacheExpiry) {
      return this.licenseCache;
    }

    if (!this.licenseKey) {
      return this.getCommunityLicense();
    }

    try {
      const response = await fetch(`${this.apiUrl}/v1/license/validate`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-License-Key': this.licenseKey
        },
        body: JSON.stringify({
          key: this.licenseKey,
          sdk: '@plinto/typescript-sdk',
          version: '1.0.0'
        })
      });

      if (!response.ok) {
        if (response.status === 402) {
          throw new EnterpriseError('License expired or invalid', 'LICENSE_EXPIRED');
        }
        throw new EnterpriseError('License validation failed', 'LICENSE_INVALID');
      }

      const data = await response.json();

      this.licenseCache = {
        valid: true,
        plan: data.plan,
        features: data.features,
        organizationId: data.organizationId,
        expiresAt: data.expiresAt ? new Date(data.expiresAt) : undefined,
        seats: data.seats,
        customLimits: data.customLimits
      };

      this.cacheExpiry = new Date(Date.now() + this.cacheTimeout);
      return this.licenseCache;

    } catch (error) {
      // Fallback to community if can't validate
      console.warn('License validation failed, falling back to community features', error);
      return this.getCommunityLicense();
    }
  }

  /**
   * Check if a specific feature is available
   */
  async hasFeature(feature: string): Promise<boolean> {
    const license = await this.validateLicense();
    return license.features.includes(feature);
  }

  /**
   * Require enterprise license for a feature
   */
  async requireEnterprise(feature: string): Promise<void> {
    const license = await this.validateLicense();

    if (license.plan === 'community') {
      throw new EnterpriseError(
        `${feature} requires an enterprise license. Visit https://plinto.dev/pricing or contact sales@plinto.dev`,
        'ENTERPRISE_REQUIRED',
        { feature, upgradeUrl: 'https://plinto.dev/pricing' }
      );
    }

    if (!license.features.includes(feature)) {
      throw new EnterpriseError(
        `Your ${license.plan} plan doesn't include ${feature}. Please upgrade your plan.`,
        'FEATURE_NOT_AVAILABLE',
        { feature, currentPlan: license.plan, upgradeUrl: 'https://plinto.dev/pricing' }
      );
    }
  }

  /**
   * Get community license (default for open source)
   */
  private getCommunityLicense(): LicenseInfo {
    return {
      valid: true,
      plan: 'community',
      features: [
        'basic_auth',
        'user_management',
        'mfa',
        'password_reset',
        'email_verification',
        'basic_organizations',
        'basic_webhooks'
      ]
    };
  }

  /**
   * Clear the license cache
   */
  private clearCache(): void {
    this.licenseCache = undefined;
    this.cacheExpiry = undefined;
  }

  /**
   * Check rate limits for current plan
   */
  async checkRateLimit(operation: string): Promise<{ allowed: boolean; limit: number; remaining: number; resetAt: Date }> {
    const license = await this.validateLicense();

    const limits = {
      community: { requests: 1000, per: 'hour' },
      pro: { requests: 10000, per: 'hour' },
      enterprise: { requests: -1, per: 'hour' } // unlimited
    };

    const planLimits = limits[license.plan];

    // For enterprise with custom limits
    if (license.customLimits && license.customLimits[operation]) {
      planLimits.requests = license.customLimits[operation];
    }

    // This would typically check against a rate limiting service
    // For now, return mock data
    return {
      allowed: true,
      limit: planLimits.requests,
      remaining: planLimits.requests,
      resetAt: new Date(Date.now() + 3600000)
    };
  }
}

/**
 * Enterprise-specific error class
 */
export class EnterpriseError extends Error {
  public code: string;
  public details?: any;

  constructor(message: string, code: string, details?: any) {
    super(message);
    this.name = 'EnterpriseError';
    this.code = code;
    this.details = details;
    Object.setPrototypeOf(this, EnterpriseError.prototype);
  }
}

/**
 * Feature flags for different plans
 */
export const FEATURES = {
  // Community features (always available)
  BASIC_AUTH: 'basic_auth',
  USER_MANAGEMENT: 'user_management',
  MFA: 'mfa',
  PASSWORD_RESET: 'password_reset',
  EMAIL_VERIFICATION: 'email_verification',
  BASIC_ORGANIZATIONS: 'basic_organizations',
  BASIC_WEBHOOKS: 'basic_webhooks',

  // Pro features
  ADVANCED_MFA: 'advanced_mfa',
  TEAM_MANAGEMENT: 'team_management',
  API_KEYS: 'api_keys',
  CUSTOM_DOMAINS: 'custom_domains',
  PRIORITY_SUPPORT: 'priority_support',
  ANALYTICS: 'analytics',

  // Enterprise features
  SSO_SAML: 'sso_saml',
  SSO_OIDC: 'sso_oidc',
  AUDIT_LOGS: 'audit_logs',
  CUSTOM_ROLES: 'custom_roles',
  WHITE_LABELING: 'white_labeling',
  ON_PREMISE: 'on_premise',
  COMPLIANCE_REPORTS: 'compliance_reports',
  ADVANCED_SECURITY: 'advanced_security',
  DEDICATED_SUPPORT: 'dedicated_support',
  SLA: 'sla',
  CUSTOM_INTEGRATIONS: 'custom_integrations'
} as const;

export type FeatureKey = typeof FEATURES[keyof typeof FEATURES];

/**
 * Plan definitions
 */
export const PLANS = {
  community: {
    name: 'Community',
    features: [
      FEATURES.BASIC_AUTH,
      FEATURES.USER_MANAGEMENT,
      FEATURES.MFA,
      FEATURES.PASSWORD_RESET,
      FEATURES.EMAIL_VERIFICATION,
      FEATURES.BASIC_ORGANIZATIONS,
      FEATURES.BASIC_WEBHOOKS
    ],
    limits: {
      users: 100,
      organizations: 1,
      apiRequests: 1000,
      webhooks: 5
    }
  },
  pro: {
    name: 'Professional',
    features: [
      ...PLANS.community.features,
      FEATURES.ADVANCED_MFA,
      FEATURES.TEAM_MANAGEMENT,
      FEATURES.API_KEYS,
      FEATURES.CUSTOM_DOMAINS,
      FEATURES.PRIORITY_SUPPORT,
      FEATURES.ANALYTICS
    ],
    limits: {
      users: 10000,
      organizations: 10,
      apiRequests: 10000,
      webhooks: 50
    }
  },
  enterprise: {
    name: 'Enterprise',
    features: [
      ...PLANS.pro.features,
      FEATURES.SSO_SAML,
      FEATURES.SSO_OIDC,
      FEATURES.AUDIT_LOGS,
      FEATURES.CUSTOM_ROLES,
      FEATURES.WHITE_LABELING,
      FEATURES.ON_PREMISE,
      FEATURES.COMPLIANCE_REPORTS,
      FEATURES.ADVANCED_SECURITY,
      FEATURES.DEDICATED_SUPPORT,
      FEATURES.SLA,
      FEATURES.CUSTOM_INTEGRATIONS
    ],
    limits: {
      users: -1, // unlimited
      organizations: -1,
      apiRequests: -1,
      webhooks: -1
    }
  }
} as const;