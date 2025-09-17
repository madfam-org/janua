/**
 * Usage Tracking and Limits Service
 * Tracks and enforces usage limits for licenses and organizations
 */

import { PrismaClient } from '@prisma/client';
import { RedisService } from './RedisService';
import { LicenseService } from './LicenseService';
import { TelemetryService } from './TelemetryService';
import { logger } from '../utils/logger';

interface UsageMetrics {
  apiCalls: number;
  validations: number;
  users: number;
  organizations: number;
  webhooks: number;
  storage: number; // in bytes
  bandwidth: number; // in bytes
}

interface UsageLimits {
  apiCallsPerHour: number;
  apiCallsPerDay: number;
  apiCallsPerMonth: number;
  validationsPerDay: number;
  validationsPerMonth: number;
  maxUsers: number;
  maxOrganizations: number;
  maxWebhooks: number;
  maxStorageBytes: number;
  maxBandwidthPerMonth: number;
}

interface UsageStatus {
  current: UsageMetrics;
  limits: UsageLimits;
  percentageUsed: Record<string, number>;
  violations: Array<{
    metric: string;
    current: number;
    limit: number;
    severity: 'warning' | 'critical';
  }>;
  resetTimes: {
    hourly: Date;
    daily: Date;
    monthly: Date;
  };
}

interface RateLimitResult {
  allowed: boolean;
  remaining: number;
  resetTime: Date;
  retryAfter?: number; // seconds
}

export class UsageTrackingService {
  private prisma: PrismaClient;
  private redis: RedisService;
  private licenseService: LicenseService;
  private telemetryService: TelemetryService;

  constructor() {
    this.prisma = new PrismaClient();
    this.redis = new RedisService();
    this.licenseService = new LicenseService();
    this.telemetryService = new TelemetryService();
  }

  /**
   * Check rate limits for API calls
   */
  async checkRateLimit(
    licenseId: string,
    endpoint: string,
    identifier: string // IP, user ID, etc.
  ): Promise<RateLimitResult> {
    const license = await this.licenseService.getLicenseById(licenseId);
    if (!license) {
      return {
        allowed: false,
        remaining: 0,
        resetTime: new Date()
      };
    }

    const limits = this.getLimitsForPlan(license.plan as 'pro' | 'enterprise', license.customLimits);

    // Check multiple rate limit windows
    const [hourlyResult, dailyResult] = await Promise.all([
      this.checkRateLimitWindow(licenseId, 'hour', limits.apiCallsPerHour),
      this.checkRateLimitWindow(licenseId, 'day', limits.apiCallsPerDay)
    ]);

    // Also check IP-based rate limiting
    const ipResult = await this.checkIpRateLimit(identifier);

    const isAllowed = hourlyResult.allowed && dailyResult.allowed && ipResult.allowed;

    if (!isAllowed) {
      await this.telemetryService.trackEvent({
        eventType: 'rate_limit_exceeded',
        licenseId,
        properties: {
          endpoint,
          identifier,
          hourlyRemaining: hourlyResult.remaining,
          dailyRemaining: dailyResult.remaining,
          ipRemaining: ipResult.remaining
        },
        context: {
          timestamp: new Date()
        }
      });
    }

    // Return the most restrictive limit
    const mostRestrictive = [hourlyResult, dailyResult, ipResult]
      .find(result => !result.allowed) || hourlyResult;

    return mostRestrictive;
  }

  /**
   * Track usage for a license
   */
  async trackUsage(
    licenseId: string,
    metric: keyof UsageMetrics,
    amount: number = 1,
    metadata?: Record<string, any>
  ): Promise<void> {
    const now = new Date();
    const hour = this.getTimeWindow(now, 'hour');
    const day = this.getTimeWindow(now, 'day');
    const month = this.getTimeWindow(now, 'month');

    // Track in Redis for real-time metrics
    await Promise.all([
      // Hourly tracking
      this.redis.hincrby(`usage:${licenseId}:hour:${hour}`, metric, amount),
      this.redis.expire(`usage:${licenseId}:hour:${hour}`, 3600 * 25), // 25 hours

      // Daily tracking
      this.redis.hincrby(`usage:${licenseId}:day:${day}`, metric, amount),
      this.redis.expire(`usage:${licenseId}:day:${day}`, 86400 * 32), // 32 days

      // Monthly tracking
      this.redis.hincrby(`usage:${licenseId}:month:${month}`, metric, amount),
      this.redis.expire(`usage:${licenseId}:month:${month}`, 86400 * 370) // ~1 year
    ]);

    // Store in database for long-term tracking
    await this.prisma.usageLog.create({
      data: {
        licenseId,
        metric,
        amount,
        metadata: metadata || {},
        timestamp: now
      }
    });

    // Check for limit violations
    await this.checkUsageViolations(licenseId);
  }

  /**
   * Get current usage status for a license
   */
  async getUsageStatus(licenseId: string): Promise<UsageStatus> {
    const license = await this.licenseService.getLicenseById(licenseId);
    if (!license) {
      throw new Error('License not found');
    }

    const limits = this.getLimitsForPlan(license.plan as 'pro' | 'enterprise', license.customLimits);

    // Get current usage from Redis
    const now = new Date();
    const currentHour = this.getTimeWindow(now, 'hour');
    const currentDay = this.getTimeWindow(now, 'day');
    const currentMonth = this.getTimeWindow(now, 'month');

    const [hourlyUsage, dailyUsage, monthlyUsage] = await Promise.all([
      this.redis.hgetall(`usage:${licenseId}:hour:${currentHour}`),
      this.redis.hgetall(`usage:${licenseId}:day:${currentDay}`),
      this.redis.hgetall(`usage:${licenseId}:month:${currentMonth}`)
    ]);

    // Get organization-level usage
    const orgUsage = await this.getOrganizationUsage(license.organizationId);

    const current: UsageMetrics = {
      apiCalls: parseInt(dailyUsage.apiCalls || '0'),
      validations: parseInt(dailyUsage.validations || '0'),
      users: orgUsage.users,
      organizations: orgUsage.organizations,
      webhooks: orgUsage.webhooks,
      storage: orgUsage.storage,
      bandwidth: parseInt(monthlyUsage.bandwidth || '0')
    };

    // Calculate percentage used
    const percentageUsed: Record<string, number> = {};
    Object.entries(current).forEach(([key, value]) => {
      const limitKey = this.getLimitKeyForMetric(key);
      const limit = (limits as any)[limitKey];
      percentageUsed[key] = limit > 0 ? Math.min((value / limit) * 100, 100) : 0;
    });

    // Check for violations
    const violations = this.detectViolations(current, limits);

    // Calculate reset times
    const resetTimes = {
      hourly: this.getNextResetTime('hour'),
      daily: this.getNextResetTime('day'),
      monthly: this.getNextResetTime('month')
    };

    return {
      current,
      limits,
      percentageUsed,
      violations,
      resetTimes
    };
  }

  /**
   * Enforce usage limits
   */
  async enforceUsageLimits(licenseId: string): Promise<{
    enforced: boolean;
    actions: string[];
    violations: Array<{ metric: string; severity: string }>;
  }> {
    const usageStatus = await this.getUsageStatus(licenseId);
    const actions: string[] = [];
    let enforced = false;

    for (const violation of usageStatus.violations) {
      if (violation.severity === 'critical') {
        // Critical violations: suspend license temporarily
        await this.licenseService.suspendLicense(
          licenseId,
          `Usage limit exceeded: ${violation.metric}`
        );
        actions.push(`Suspended license due to ${violation.metric} limit exceeded`);
        enforced = true;

        // Send alert
        await this.sendUsageAlert(licenseId, violation);
      } else if (violation.severity === 'warning') {
        // Warning violations: send notification
        await this.sendUsageWarning(licenseId, violation);
        actions.push(`Sent warning for ${violation.metric} approaching limit`);
      }
    }

    return {
      enforced,
      actions,
      violations: usageStatus.violations
    };
  }

  /**
   * Get usage analytics for a time period
   */
  async getUsageAnalytics(
    licenseId: string,
    startDate: Date,
    endDate: Date,
    granularity: 'hour' | 'day' | 'month' = 'day'
  ): Promise<{
    timeline: Array<{
      timestamp: Date;
      metrics: UsageMetrics;
    }>;
    totals: UsageMetrics;
    averages: UsageMetrics;
    peaks: UsageMetrics;
  }> {
    const logs = await this.prisma.usageLog.findMany({
      where: {
        licenseId,
        timestamp: {
          gte: startDate,
          lte: endDate
        }
      },
      orderBy: {
        timestamp: 'asc'
      }
    });

    // Aggregate by time window
    const aggregated = this.aggregateUsageByTime(logs, granularity);

    // Calculate totals, averages, and peaks
    const totals = this.calculateTotals(aggregated);
    const averages = this.calculateAverages(aggregated);
    const peaks = this.calculatePeaks(aggregated);

    return {
      timeline: aggregated,
      totals,
      averages,
      peaks
    };
  }

  /**
   * Reset usage for a license (admin only)
   */
  async resetUsage(
    licenseId: string,
    metrics: Array<keyof UsageMetrics>,
    window: 'hour' | 'day' | 'month' = 'day'
  ): Promise<void> {
    const now = new Date();
    const timeWindow = this.getTimeWindow(now, window);

    for (const metric of metrics) {
      await this.redis.hdel(`usage:${licenseId}:${window}:${timeWindow}`, metric);
    }

    logger.info('Usage reset for license', {
      licenseId,
      metrics,
      window,
      resetAt: now
    });
  }

  // Private helper methods

  private async checkRateLimitWindow(
    licenseId: string,
    window: 'hour' | 'day' | 'month',
    limit: number
  ): Promise<RateLimitResult> {
    const now = new Date();
    const timeWindow = this.getTimeWindow(now, window);
    const key = `usage:${licenseId}:${window}:${timeWindow}`;

    const current = parseInt(await this.redis.hget(key, 'apiCalls') || '0');
    const allowed = current < limit;
    const remaining = Math.max(0, limit - current);

    return {
      allowed,
      remaining,
      resetTime: this.getNextResetTime(window),
      retryAfter: allowed ? undefined : this.getSecondsUntilReset(window)
    };
  }

  private async checkIpRateLimit(ip: string): Promise<RateLimitResult> {
    const now = new Date();
    const minute = Math.floor(now.getTime() / 60000);
    const key = `ip_rate_limit:${ip}:${minute}`;

    const current = parseInt(await this.redis.get(key) || '0');
    const limit = 100; // 100 requests per minute per IP

    if (current >= limit) {
      return {
        allowed: false,
        remaining: 0,
        resetTime: new Date((minute + 1) * 60000),
        retryAfter: 60
      };
    }

    // Increment and set expiration
    await this.redis.incr(key);
    await this.redis.expire(key, 60);

    return {
      allowed: true,
      remaining: limit - current - 1,
      resetTime: new Date((minute + 1) * 60000)
    };
  }

  private async checkUsageViolations(licenseId: string): Promise<void> {
    const usageStatus = await this.getUsageStatus(licenseId);

    if (usageStatus.violations.length > 0) {
      // Log violations
      await this.telemetryService.trackEvent({
        eventType: 'usage_violation',
        licenseId,
        properties: {
          violations: usageStatus.violations
        },
        context: {
          timestamp: new Date()
        }
      });

      // Check if automatic enforcement is enabled
      const shouldEnforce = await this.shouldEnforceAutomatically(licenseId);
      if (shouldEnforce) {
        await this.enforceUsageLimits(licenseId);
      }
    }
  }

  private async getOrganizationUsage(organizationId: string): Promise<{
    users: number;
    organizations: number;
    webhooks: number;
    storage: number;
  }> {
    // Get actual usage from database
    const [userCount, webhookCount] = await Promise.all([
      this.prisma.user.count({
        where: { organizationId }
      }),
      this.prisma.webhook.count({
        where: { organizationId }
      })
    ]);

    // Storage would be calculated from actual file storage
    const storage = 0; // Placeholder

    return {
      users: userCount,
      organizations: 1, // This organization
      webhooks: webhookCount,
      storage
    };
  }

  private getLimitsForPlan(plan: 'pro' | 'enterprise', customLimits?: Record<string, any>): UsageLimits {
    const baseLimits = {
      pro: {
        apiCallsPerHour: 1000,
        apiCallsPerDay: 10000,
        apiCallsPerMonth: 300000,
        validationsPerDay: 5000,
        validationsPerMonth: 150000,
        maxUsers: 10000,
        maxOrganizations: 10,
        maxWebhooks: 50,
        maxStorageBytes: 10 * 1024 * 1024 * 1024, // 10 GB
        maxBandwidthPerMonth: 100 * 1024 * 1024 * 1024 // 100 GB
      },
      enterprise: {
        apiCallsPerHour: -1, // unlimited
        apiCallsPerDay: -1,
        apiCallsPerMonth: -1,
        validationsPerDay: -1,
        validationsPerMonth: -1,
        maxUsers: -1,
        maxOrganizations: -1,
        maxWebhooks: -1,
        maxStorageBytes: -1,
        maxBandwidthPerMonth: -1
      }
    };

    return { ...baseLimits[plan], ...customLimits };
  }

  private detectViolations(current: UsageMetrics, limits: UsageLimits): Array<{
    metric: string;
    current: number;
    limit: number;
    severity: 'warning' | 'critical';
  }> {
    const violations = [];

    // Check each metric
    Object.entries(current).forEach(([metric, value]) => {
      const limitKey = this.getLimitKeyForMetric(metric);
      const limit = (limits as any)[limitKey];

      if (limit > 0) { // -1 means unlimited
        const percentage = (value / limit) * 100;

        if (percentage >= 100) {
          violations.push({
            metric,
            current: value,
            limit,
            severity: 'critical' as const
          });
        } else if (percentage >= 80) {
          violations.push({
            metric,
            current: value,
            limit,
            severity: 'warning' as const
          });
        }
      }
    });

    return violations;
  }

  private getLimitKeyForMetric(metric: string): string {
    const mapping: Record<string, string> = {
      apiCalls: 'apiCallsPerDay',
      validations: 'validationsPerDay',
      users: 'maxUsers',
      organizations: 'maxOrganizations',
      webhooks: 'maxWebhooks',
      storage: 'maxStorageBytes',
      bandwidth: 'maxBandwidthPerMonth'
    };

    return mapping[metric] || metric;
  }

  private getTimeWindow(date: Date, window: 'hour' | 'day' | 'month'): string {
    switch (window) {
      case 'hour':
        return `${date.getFullYear()}-${date.getMonth() + 1}-${date.getDate()}-${date.getHours()}`;
      case 'day':
        return `${date.getFullYear()}-${date.getMonth() + 1}-${date.getDate()}`;
      case 'month':
        return `${date.getFullYear()}-${date.getMonth() + 1}`;
    }
  }

  private getNextResetTime(window: 'hour' | 'day' | 'month'): Date {
    const now = new Date();
    const next = new Date(now);

    switch (window) {
      case 'hour':
        next.setHours(next.getHours() + 1, 0, 0, 0);
        break;
      case 'day':
        next.setDate(next.getDate() + 1);
        next.setHours(0, 0, 0, 0);
        break;
      case 'month':
        next.setMonth(next.getMonth() + 1, 1);
        next.setHours(0, 0, 0, 0);
        break;
    }

    return next;
  }

  private getSecondsUntilReset(window: 'hour' | 'day' | 'month'): number {
    const now = new Date();
    const reset = this.getNextResetTime(window);
    return Math.ceil((reset.getTime() - now.getTime()) / 1000);
  }

  private async shouldEnforceAutomatically(licenseId: string): Promise<boolean> {
    // Check if automatic enforcement is enabled for this license
    // This could be configurable per license or plan
    return true; // Default to enabled
  }

  private async sendUsageAlert(licenseId: string, violation: any): Promise<void> {
    // Send critical usage alert (email, webhook, etc.)
    logger.warn('Critical usage violation', {
      licenseId,
      violation
    });
  }

  private async sendUsageWarning(licenseId: string, violation: any): Promise<void> {
    // Send usage warning notification
    logger.info('Usage warning', {
      licenseId,
      violation
    });
  }

  private aggregateUsageByTime(logs: any[], granularity: 'hour' | 'day' | 'month'): Array<{
    timestamp: Date;
    metrics: UsageMetrics;
  }> {
    // Implement time-based aggregation
    return []; // Placeholder
  }

  private calculateTotals(aggregated: any[]): UsageMetrics {
    // Calculate total usage across all time periods
    return {
      apiCalls: 0,
      validations: 0,
      users: 0,
      organizations: 0,
      webhooks: 0,
      storage: 0,
      bandwidth: 0
    }; // Placeholder
  }

  private calculateAverages(aggregated: any[]): UsageMetrics {
    // Calculate average usage per time period
    return {
      apiCalls: 0,
      validations: 0,
      users: 0,
      organizations: 0,
      webhooks: 0,
      storage: 0,
      bandwidth: 0
    }; // Placeholder
  }

  private calculatePeaks(aggregated: any[]): UsageMetrics {
    // Calculate peak usage across all time periods
    return {
      apiCalls: 0,
      validations: 0,
      users: 0,
      organizations: 0,
      webhooks: 0,
      storage: 0,
      bandwidth: 0
    }; // Placeholder
  }
}