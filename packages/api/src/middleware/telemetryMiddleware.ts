/**
 * Telemetry middleware for automatic API tracking
 */

import { Request, Response, NextFunction } from 'express';
import { TelemetryService } from '../services/TelemetryService';
import { logger } from '../utils/logger';

const telemetryService = new TelemetryService();

interface TelemetryRequest extends Request {
  startTime?: number;
  telemetry?: {
    userId?: string;
    organizationId?: string;
    licenseId?: string;
    sdk?: string;
    version?: string;
  };
}

/**
 * Middleware to automatically track API calls
 */
export const telemetryMiddleware = (req: TelemetryRequest, res: Response, next: NextFunction) => {
  // Skip telemetry for health checks and internal endpoints
  if (req.path.includes('/health') ||
      req.path.includes('/analytics/track') ||
      req.path.startsWith('/api/v1/analytics/track')) {
    return next();
  }

  // Record start time
  req.startTime = Date.now();

  // Extract telemetry context from headers
  req.telemetry = {
    userId: req.get('X-User-ID'),
    organizationId: req.get('X-Organization-ID'),
    licenseId: req.get('X-License-ID'),
    sdk: req.get('X-SDK-Name'),
    version: req.get('X-SDK-Version')
  };

  // Override response.end to capture response data
  const originalEnd = res.end;
  res.end = function(chunk?: any, encoding?: any, cb?: () => void) {
    // Calculate response time
    const responseTime = req.startTime ? Date.now() - req.startTime : 0;

    // Track the API call asynchronously (don't block response)
    setImmediate(async () => {
      try {
        await telemetryService.trackApiCall({
          endpoint: req.path,
          method: req.method,
          statusCode: res.statusCode,
          responseTime,
          userId: req.telemetry?.userId,
          organizationId: req.telemetry?.organizationId,
          licenseId: req.telemetry?.licenseId,
          sdk: req.telemetry?.sdk,
          version: req.telemetry?.version,
          ip: req.ip
        });
      } catch (error) {
        logger.error('Error tracking API call', { error, path: req.path });
      }
    });

    // Call original end method
    originalEnd.call(this, chunk, encoding, cb);
  };

  next();
};

/**
 * Middleware to track feature usage
 */
export const trackFeature = (feature: string, action: string = 'used') => {
  return async (req: TelemetryRequest, res: Response, next: NextFunction) => {
    try {
      await telemetryService.trackFeatureUsage({
        feature,
        action,
        userId: req.telemetry?.userId,
        organizationId: req.telemetry?.organizationId,
        licenseId: req.telemetry?.licenseId,
        sdk: req.telemetry?.sdk,
        version: req.telemetry?.version
      });
    } catch (error) {
      logger.error('Error tracking feature usage', { error, feature, action });
    }

    next();
  };
};

/**
 * Middleware to track errors
 */
export const errorTrackingMiddleware = (error: any, req: TelemetryRequest, res: Response, next: NextFunction) => {
  // Track error asynchronously
  setImmediate(async () => {
    try {
      await telemetryService.trackError({
        errorType: error.constructor.name,
        errorMessage: error.message,
        stackTrace: error.stack,
        userId: req.telemetry?.userId,
        organizationId: req.telemetry?.organizationId,
        licenseId: req.telemetry?.licenseId,
        sdk: req.telemetry?.sdk,
        version: req.telemetry?.version,
        context: {
          endpoint: req.path,
          method: req.method,
          userAgent: req.get('User-Agent'),
          ip: req.ip
        }
      });
    } catch (trackingError) {
      logger.error('Error tracking error event', {
        originalError: error.message,
        trackingError: trackingError.message
      });
    }
  });

  // Continue with normal error handling
  next(error);
};