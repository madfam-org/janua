/**
 * Usage limit enforcement middleware
 */

import { Request, Response, NextFunction } from 'express';
import { UsageTrackingService } from '../services/UsageTrackingService';
import { logger } from '../utils/logger';

interface UsageLimitRequest extends Request {
  licenseId?: string;
  organizationId?: string;
  usage?: {
    allowed: boolean;
    remaining: number;
    resetTime: Date;
    retryAfter?: number;
  };
}

const usageService = new UsageTrackingService();

/**
 * Middleware to check and enforce API rate limits
 */
export const checkRateLimit = async (req: UsageLimitRequest, res: Response, next: NextFunction) => {
  try {
    // Skip rate limiting for certain endpoints
    if (shouldSkipRateLimit(req.path)) {
      return next();
    }

    // Get license ID from headers or request context
    const licenseId = req.get('X-License-ID') || req.licenseId;
    const identifier = req.ip; // Could also use user ID

    if (!licenseId) {
      // No license ID provided - apply default rate limits
      return applyDefaultRateLimit(req, res, next);
    }

    // Check rate limits for the license
    const rateLimit = await usageService.checkRateLimit(licenseId, req.path, identifier);

    // Add rate limit info to request for potential use in response
    req.usage = rateLimit;

    // Set rate limit headers
    res.set({
      'X-RateLimit-Remaining': rateLimit.remaining.toString(),
      'X-RateLimit-Reset': rateLimit.resetTime.toISOString()
    });

    if (!rateLimit.allowed) {
      // Rate limit exceeded
      if (rateLimit.retryAfter) {
        res.set('Retry-After', rateLimit.retryAfter.toString());
      }

      return res.status(429).json({
        error: 'Rate Limit Exceeded',
        message: 'API rate limit exceeded for this license',
        code: 'RATE_LIMIT_EXCEEDED',
        details: {
          remaining: rateLimit.remaining,
          resetTime: rateLimit.resetTime,
          retryAfter: rateLimit.retryAfter
        }
      });
    }

    // Track the API call for usage monitoring
    setImmediate(async () => {
      try {
        await usageService.trackUsage(licenseId, 'apiCalls', 1, {
          endpoint: req.path,
          method: req.method,
          ip: req.ip,
          userAgent: req.get('User-Agent')
        });
      } catch (error) {
        logger.error('Error tracking API usage', { error, licenseId, endpoint: req.path });
      }
    });

    next();
  } catch (error) {
    logger.error('Rate limit check failed', { error, path: req.path });
    // Continue without rate limiting on error (fail open)
    next();
  }
};

/**
 * Middleware to enforce usage limits for specific features
 */
export const enforceFeatureLimit = (feature: string, usageMetric: 'validations' | 'webhooks' | 'storage' | 'bandwidth') => {
  return async (req: UsageLimitRequest, res: Response, next: NextFunction) => {
    try {
      const licenseId = req.get('X-License-ID') || req.licenseId;

      if (!licenseId) {
        return res.status(402).json({
          error: 'License Required',
          message: 'Valid license required to use this feature',
          code: 'LICENSE_REQUIRED'
        });
      }

      // Check current usage status
      const usageStatus = await usageService.getUsageStatus(licenseId);

      // Check if this specific metric is at or over limit
      const currentUsage = usageStatus.current[usageMetric];
      const limit = getLimitForMetric(usageStatus.limits, usageMetric);

      if (limit > 0 && currentUsage >= limit) {
        return res.status(402).json({
          error: 'Usage Limit Exceeded',
          message: `${feature} usage limit exceeded`,
          code: 'USAGE_LIMIT_EXCEEDED',
          details: {
            feature,
            current: currentUsage,
            limit,
            resetTime: getResetTimeForMetric(usageMetric)
          }
        });
      }

      // Check for warnings (80% of limit)
      if (limit > 0 && currentUsage >= limit * 0.8) {
        res.set('X-Usage-Warning', 'true');
        res.set('X-Usage-Remaining', (limit - currentUsage).toString());
        res.set('X-Usage-Limit', limit.toString());
      }

      next();
    } catch (error) {
      logger.error('Feature limit enforcement failed', { error, feature });
      // Continue without limit enforcement on error (fail open)
      next();
    }
  };
};

/**
 * Middleware to track specific feature usage
 */
export const trackFeatureUsage = (metric: 'validations' | 'webhooks' | 'storage' | 'bandwidth', amount: number = 1) => {
  return async (req: UsageLimitRequest, res: Response, next: NextFunction) => {
    // Track usage after the request completes
    res.on('finish', async () => {
      try {
        const licenseId = req.get('X-License-ID') || req.licenseId;

        if (licenseId && res.statusCode < 400) {
          await usageService.trackUsage(licenseId, metric, amount, {
            endpoint: req.path,
            method: req.method,
            statusCode: res.statusCode,
            timestamp: new Date()
          });
        }
      } catch (error) {
        logger.error('Error tracking feature usage', { error, metric, amount });
      }
    });

    next();
  };
};

/**
 * Middleware to enforce organization-level limits
 */
export const enforceOrganizationLimits = async (req: UsageLimitRequest, res: Response, next: NextFunction) => {
  try {
    const organizationId = req.get('X-Organization-ID') || req.organizationId;

    if (!organizationId) {
      return next(); // No organization context
    }

    // This would check organization-specific limits like user count, storage, etc.
    // Implementation depends on specific organization limits

    next();
  } catch (error) {
    logger.error('Organization limit enforcement failed', { error });
    next();
  }
};

/**
 * Middleware to add usage information to response headers
 */
export const addUsageHeaders = async (req: UsageLimitRequest, res: Response, next: NextFunction) => {
  try {
    const licenseId = req.get('X-License-ID') || req.licenseId;

    if (licenseId) {
      const usageStatus = await usageService.getUsageStatus(licenseId);

      // Add usage headers for key metrics
      res.set({
        'X-Usage-API-Calls': usageStatus.current.apiCalls.toString(),
        'X-Usage-API-Calls-Limit': usageStatus.limits.apiCallsPerDay.toString(),
        'X-Usage-Validations': usageStatus.current.validations.toString(),
        'X-Usage-Validations-Limit': usageStatus.limits.validationsPerDay.toString(),
        'X-Usage-Reset-Daily': usageStatus.resetTimes.daily.toISOString(),
        'X-Usage-Reset-Monthly': usageStatus.resetTimes.monthly.toISOString()
      });

      // Add warning headers if approaching limits
      Object.entries(usageStatus.percentageUsed).forEach(([metric, percentage]) => {
        if (percentage >= 80) {
          res.set(`X-Usage-Warning-${metric}`, percentage.toFixed(1));
        }
      });
    }

    next();
  } catch (error) {
    logger.error('Error adding usage headers', { error });
    next();
  }
};

// Helper functions

function shouldSkipRateLimit(path: string): boolean {
  const skipPaths = [
    '/health',
    '/api/v1/license/validate', // License validation should have its own limits
    '/api/v1/analytics/track', // Telemetry tracking endpoints
    '/api/v1/billing-portal/health'
  ];

  return skipPaths.some(skipPath => path.startsWith(skipPath));
}

async function applyDefaultRateLimit(req: Request, res: Response, next: NextFunction): Promise<void> {
  // Apply a basic IP-based rate limit for requests without licenses
  const ip = req.ip;
  const now = new Date();
  const minute = Math.floor(now.getTime() / 60000);

  // This would use Redis to track IP-based limits
  // For now, just continue without limiting
  next();
}

function getLimitForMetric(limits: any, metric: string): number {
  switch (metric) {
    case 'validations':
      return limits.validationsPerDay;
    case 'webhooks':
      return limits.maxWebhooks;
    case 'storage':
      return limits.maxStorageBytes;
    case 'bandwidth':
      return limits.maxBandwidthPerMonth;
    default:
      return -1; // Unlimited
  }
}

function getResetTimeForMetric(metric: string): Date {
  const now = new Date();
  const resetTime = new Date(now);

  switch (metric) {
    case 'validations':
      // Daily reset
      resetTime.setDate(resetTime.getDate() + 1);
      resetTime.setHours(0, 0, 0, 0);
      break;
    case 'bandwidth':
      // Monthly reset
      resetTime.setMonth(resetTime.getMonth() + 1, 1);
      resetTime.setHours(0, 0, 0, 0);
      break;
    default:
      // Default to daily reset
      resetTime.setDate(resetTime.getDate() + 1);
      resetTime.setHours(0, 0, 0, 0);
  }

  return resetTime;
}