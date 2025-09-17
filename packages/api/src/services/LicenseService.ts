/**
 * License Management Service
 * Handles license generation, validation, and tracking
 */

import { randomBytes, createHash, createHmac } from 'crypto';
import { addDays, isAfter, isBefore } from 'date-fns';
import { PrismaClient } from '@prisma/client';
import { RedisService } from './RedisService';
import { logger } from '../utils/logger';
import { NotFoundError, ValidationError } from '../utils/errors';

interface LicenseValidationContext {
  sdk?: string;
  version?: string;
  environment?: string;
  domain?: string;
  ip?: string;
  userAgent?: string;
}

interface LicenseInfo {
  valid: boolean;
  plan: 'community' | 'pro' | 'enterprise';
  features: string[];
  organizationId: string;
  expiresAt?: Date;
  seats?: number;
  customLimits?: Record<string, any>;
  limits: Record<string, number>;
  currentUsage: Record<string, number>;
}

interface UsageStatistics {
  period: {
    start: Date;
    end: Date;
  };
  metrics: {
    validations: number;
    uniqueIps: number;
    apiCalls: number;
    features: Record<string, number>;
  };
  timeline: Array<{
    timestamp: Date;
    validations: number;
    apiCalls: number;
  }>;
}

export class LicenseService {
  private prisma: PrismaClient;
  private redis: RedisService;
  private licenseSecret: string;

  constructor() {
    this.prisma = new PrismaClient();
    this.redis = new RedisService();
    this.licenseSecret = process.env.LICENSE_SECRET || 'plinto-license-secret';
  }

  /**
   * Generate a new license key
   */
  async generateLicense(data: {
    organizationId: string;
    plan: 'pro' | 'enterprise';
    features: string[];
    expiresAt?: string;
    seats?: number;
    customLimits?: Record<string, any>;
    metadata?: Record<string, any>;
  }) {
    const licenseId = randomBytes(16).toString('hex');
    const keyPrefix = data.plan === 'enterprise' ? 'ent' : 'pro';
    const environment = process.env.NODE_ENV === 'production' ? 'live' : 'test';

    // Generate license key: {prefix}_{env}_{id}_{checksum}
    const baseKey = `${keyPrefix}_${environment}_${licenseId}`;
    const checksum = this.generateChecksum(baseKey);
    const licenseKey = `${baseKey}_${checksum}`;

    // Create license in database
    const license = await this.prisma.license.create({
      data: {
        id: licenseId,
        key: licenseKey,
        organizationId: data.organizationId,
        plan: data.plan,
        features: data.features,
        expiresAt: data.expiresAt ? new Date(data.expiresAt) : null,
        seats: data.seats,
        customLimits: data.customLimits || {},
        metadata: data.metadata || {},
        status: 'active',
        createdAt: new Date(),
        updatedAt: new Date()
      }
    });

    // Initialize usage tracking
    await this.initializeUsageTracking(licenseId);

    return license;
  }

  /**
   * Validate a license key
   */
  async validateLicense(key: string, context: LicenseValidationContext = {}): Promise<LicenseInfo> {
    try {
      // Check cache first
      const cacheKey = `license:${key}`;
      const cached = await this.redis.get(cacheKey);

      if (cached) {
        const licenseInfo = JSON.parse(cached);
        await this.trackUsage(key, 'validation', context);
        return licenseInfo;
      }

      // Validate key format
      if (!this.isValidKeyFormat(key)) {
        return this.getCommunityLicense();
      }

      // Extract license ID from key
      const parts = key.split('_');
      if (parts.length !== 4) {
        return this.getCommunityLicense();
      }

      const [prefix, environment, licenseId, checksum] = parts;

      // Verify checksum
      const expectedChecksum = this.generateChecksum(`${prefix}_${environment}_${licenseId}`);
      if (checksum !== expectedChecksum) {
        return this.getCommunityLicense();
      }

      // Get license from database
      const license = await this.prisma.license.findUnique({
        where: { id: licenseId },
        include: {
          organization: true
        }
      });

      if (!license) {
        return this.getCommunityLicense();
      }

      // Check license status
      if (license.status !== 'active') {
        logger.warn('License validation failed - inactive', {
          licenseId,
          status: license.status,
          context
        });
        return this.getCommunityLicense();
      }

      // Check expiration
      if (license.expiresAt && isAfter(new Date(), license.expiresAt)) {
        logger.warn('License validation failed - expired', {
          licenseId,
          expiresAt: license.expiresAt,
          context
        });
        return this.getCommunityLicense();
      }

      // Get current usage
      const currentUsage = await this.getCurrentUsage(licenseId);
      const limits = this.getPlanLimits(license.plan as 'pro' | 'enterprise', license.customLimits);

      // Check usage limits
      const usageLimitExceeded = this.checkUsageLimits(currentUsage, limits);
      if (usageLimitExceeded) {
        logger.warn('License validation failed - usage limit exceeded', {
          licenseId,
          currentUsage,
          limits,
          context
        });
        return this.getCommunityLicense();
      }

      const licenseInfo: LicenseInfo = {
        valid: true,
        plan: license.plan as 'pro' | 'enterprise',
        features: license.features,
        organizationId: license.organizationId,
        expiresAt: license.expiresAt,
        seats: license.seats,
        customLimits: license.customLimits as Record<string, any>,
        limits,
        currentUsage
      };

      // Cache for 5 minutes
      await this.redis.setex(cacheKey, 300, JSON.stringify(licenseInfo));

      // Track usage
      await this.trackUsage(key, 'validation', context);

      return licenseInfo;

    } catch (error) {
      logger.error('License validation error', { error, key, context });
      return this.getCommunityLicense();
    }
  }

  /**
   * Track license usage
   */
  async trackUsage(key: string, event: string, context: any = {}) {
    try {
      const parts = key.split('_');
      if (parts.length !== 4) return;

      const licenseId = parts[2];
      const today = new Date().toISOString().split('T')[0];

      // Update usage counters
      await Promise.all([
        // Daily usage
        this.redis.hincrby(`usage:${licenseId}:${today}`, event, 1),
        this.redis.expire(`usage:${licenseId}:${today}`, 86400 * 32), // 32 days

        // Monthly usage
        this.redis.hincrby(`usage:${licenseId}:${today.slice(0, 7)}`, event, 1),
        this.redis.expire(`usage:${licenseId}:${today.slice(0, 7)}`, 86400 * 365), // 1 year

        // Track unique IPs
        context.ip && this.redis.sadd(`ips:${licenseId}:${today}`, context.ip),
        context.ip && this.redis.expire(`ips:${licenseId}:${today}`, 86400 * 32)
      ]);

      // Store detailed event
      await this.prisma.licenseUsage.create({
        data: {
          licenseId,
          event,
          context: context || {},
          ip: context.ip,
          userAgent: context.userAgent,
          timestamp: new Date()
        }
      });

    } catch (error) {
      logger.error('Error tracking license usage', { error, key, event, context });
    }
  }

  /**
   * Get license by ID
   */
  async getLicenseById(licenseId: string) {
    const license = await this.prisma.license.findUnique({
      where: { id: licenseId },
      include: {
        organization: true
      }
    });

    if (!license) {
      return null;
    }

    return {
      ...license,
      maskedKey: this.maskLicenseKey(license.key),
      currentUsage: await this.getCurrentUsage(licenseId)
    };
  }

  /**
   * Update license
   */
  async updateLicense(licenseId: string, data: {
    features?: string[];
    expiresAt?: string;
    seats?: number;
    customLimits?: Record<string, any>;
    status?: 'active' | 'suspended' | 'expired';
    metadata?: Record<string, any>;
  }) {
    const license = await this.prisma.license.update({
      where: { id: licenseId },
      data: {
        ...data,
        expiresAt: data.expiresAt ? new Date(data.expiresAt) : undefined,
        updatedAt: new Date()
      }
    });

    // Clear cache
    const fullLicense = await this.prisma.license.findUnique({
      where: { id: licenseId }
    });

    if (fullLicense) {
      await this.redis.del(`license:${fullLicense.key}`);
    }

    return license;
  }

  /**
   * Revoke license
   */
  async revokeLicense(licenseId: string) {
    const license = await this.prisma.license.update({
      where: { id: licenseId },
      data: {
        status: 'revoked',
        updatedAt: new Date()
      }
    });

    // Clear cache
    await this.redis.del(`license:${license.key}`);

    return license;
  }

  /**
   * Suspend license
   */
  async suspendLicense(licenseId: string, reason?: string) {
    const license = await this.prisma.license.update({
      where: { id: licenseId },
      data: {
        status: 'suspended',
        metadata: {
          suspensionReason: reason,
          suspendedAt: new Date().toISOString()
        },
        updatedAt: new Date()
      }
    });

    // Clear cache
    await this.redis.del(`license:${license.key}`);

    return license;
  }

  /**
   * Reactivate license
   */
  async reactivateLicense(licenseId: string) {
    const license = await this.prisma.license.update({
      where: { id: licenseId },
      data: {
        status: 'active',
        updatedAt: new Date()
      }
    });

    // Clear cache
    await this.redis.del(`license:${license.key}`);

    return license;
  }

  /**
   * Get usage statistics
   */
  async getUsageStatistics(licenseId: string, options: {
    startDate?: string;
    endDate?: string;
    granularity?: 'hour' | 'day' | 'week' | 'month';
  } = {}): Promise<UsageStatistics> {
    const {
      startDate = new Date(Date.now() - 30 * 24 * 60 * 60 * 1000).toISOString(),
      endDate = new Date().toISOString(),
      granularity = 'day'
    } = options;

    const usage = await this.prisma.licenseUsage.findMany({
      where: {
        licenseId,
        timestamp: {
          gte: new Date(startDate),
          lte: new Date(endDate)
        }
      },
      orderBy: {
        timestamp: 'asc'
      }
    });

    // Aggregate metrics
    const metrics = {
      validations: usage.filter(u => u.event === 'validation').length,
      uniqueIps: new Set(usage.map(u => u.ip).filter(Boolean)).size,
      apiCalls: usage.filter(u => u.event !== 'validation').length,
      features: {} as Record<string, number>
    };

    // Count feature usage
    usage.forEach(u => {
      if (u.context && u.context.feature) {
        metrics.features[u.context.feature] = (metrics.features[u.context.feature] || 0) + 1;
      }
    });

    // Generate timeline based on granularity
    const timeline = this.generateTimeline(usage, granularity, new Date(startDate), new Date(endDate));

    return {
      period: {
        start: new Date(startDate),
        end: new Date(endDate)
      },
      metrics,
      timeline
    };
  }

  // Private helper methods

  private generateChecksum(data: string): string {
    return createHmac('sha256', this.licenseSecret)
      .update(data)
      .digest('hex')
      .slice(0, 8);
  }

  private isValidKeyFormat(key: string): boolean {
    const parts = key.split('_');
    return parts.length === 4 &&
           ['pro', 'ent'].includes(parts[0]) &&
           ['live', 'test'].includes(parts[1]);
  }

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
      ],
      organizationId: '',
      limits: {
        users: 100,
        organizations: 1,
        apiRequests: 1000,
        webhooks: 5
      },
      currentUsage: {}
    };
  }

  private async getCurrentUsage(licenseId: string): Promise<Record<string, number>> {
    const today = new Date().toISOString().split('T')[0];
    const month = today.slice(0, 7);

    const [dailyUsage, monthlyUsage, uniqueIps] = await Promise.all([
      this.redis.hgetall(`usage:${licenseId}:${today}`),
      this.redis.hgetall(`usage:${licenseId}:${month}`),
      this.redis.scard(`ips:${licenseId}:${today}`)
    ]);

    return {
      dailyValidations: parseInt(dailyUsage.validation || '0'),
      monthlyValidations: parseInt(monthlyUsage.validation || '0'),
      dailyApiCalls: Object.values(dailyUsage).reduce((sum, val) => sum + parseInt(val), 0),
      monthlyApiCalls: Object.values(monthlyUsage).reduce((sum, val) => sum + parseInt(val), 0),
      uniqueIpsToday: uniqueIps
    };
  }

  private getPlanLimits(plan: 'pro' | 'enterprise', customLimits?: Record<string, any>): Record<string, number> {
    const baseLimits = {
      pro: {
        users: 10000,
        organizations: 10,
        apiRequests: 10000,
        webhooks: 50,
        dailyValidations: 5000
      },
      enterprise: {
        users: -1, // unlimited
        organizations: -1,
        apiRequests: -1,
        webhooks: -1,
        dailyValidations: -1
      }
    };

    return { ...baseLimits[plan], ...customLimits };
  }

  private checkUsageLimits(currentUsage: Record<string, number>, limits: Record<string, number>): boolean {
    for (const [key, limit] of Object.entries(limits)) {
      if (limit === -1) continue; // unlimited

      const current = currentUsage[key] || 0;
      if (current >= limit) {
        return true; // limit exceeded
      }
    }
    return false;
  }

  private maskLicenseKey(key: string): string {
    const parts = key.split('_');
    if (parts.length !== 4) return key;

    return `${parts[0]}_${parts[1]}_${'*'.repeat(8)}_${parts[3]}`;
  }

  private async initializeUsageTracking(licenseId: string) {
    const today = new Date().toISOString().split('T')[0];
    await this.redis.hset(`usage:${licenseId}:${today}`, 'initialized', '1');
    await this.redis.expire(`usage:${licenseId}:${today}`, 86400 * 32);
  }

  private generateTimeline(
    usage: any[],
    granularity: 'hour' | 'day' | 'week' | 'month',
    startDate: Date,
    endDate: Date
  ) {
    // Implementation for timeline generation based on granularity
    // This would group usage data by time periods
    const timeline: Array<{ timestamp: Date; validations: number; apiCalls: number }> = [];

    // For now, return empty timeline - implement based on specific needs
    return timeline;
  }
}