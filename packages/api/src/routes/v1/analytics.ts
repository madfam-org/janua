/**
 * Analytics and telemetry API endpoints
 */

import { Router } from 'express';
import { z } from 'zod';
import { authenticateApiKey, rateLimiter } from '../../middleware';
import { TelemetryService } from '../../services/TelemetryService';
import { ValidationError } from '../../utils/errors';
import { logger } from '../../utils/logger';

const router = Router();
const telemetryService = new TelemetryService();

// Validation schemas
const TrackEventSchema = z.object({
  eventType: z.string().min(1),
  userId: z.string().optional(),
  organizationId: z.string().uuid().optional(),
  licenseId: z.string().optional(),
  sessionId: z.string().optional(),
  properties: z.record(z.any()).default({}),
  context: z.object({
    sdk: z.string().optional(),
    version: z.string().optional(),
    platform: z.string().optional(),
    environment: z.string().optional(),
    ip: z.string().optional(),
    userAgent: z.string().optional(),
    country: z.string().optional()
  }).optional()
});

const AnalyticsQuerySchema = z.object({
  eventTypes: z.array(z.string()).optional(),
  organizationId: z.string().uuid().optional(),
  licenseId: z.string().optional(),
  startDate: z.string().datetime(),
  endDate: z.string().datetime(),
  granularity: z.enum(['hour', 'day', 'week', 'month']).default('day'),
  limit: z.number().min(1).max(1000).optional()
});

const TrackDownloadSchema = z.object({
  sdk: z.string().min(1),
  version: z.string().min(1),
  platform: z.string().optional(),
  ip: z.string().optional(),
  userAgent: z.string().optional(),
  country: z.string().optional()
});

const TrackApiCallSchema = z.object({
  endpoint: z.string().min(1),
  method: z.string().min(1),
  statusCode: z.number(),
  responseTime: z.number(),
  userId: z.string().optional(),
  organizationId: z.string().uuid().optional(),
  licenseId: z.string().optional(),
  sdk: z.string().optional(),
  version: z.string().optional(),
  ip: z.string().optional()
});

const TrackFeatureSchema = z.object({
  feature: z.string().min(1),
  action: z.string().min(1),
  userId: z.string().optional(),
  organizationId: z.string().uuid().optional(),
  licenseId: z.string().optional(),
  sdk: z.string().optional(),
  version: z.string().optional(),
  metadata: z.record(z.any()).optional()
});

const TrackErrorSchema = z.object({
  errorType: z.string().min(1),
  errorMessage: z.string().min(1),
  stackTrace: z.string().optional(),
  userId: z.string().optional(),
  organizationId: z.string().uuid().optional(),
  licenseId: z.string().optional(),
  sdk: z.string().optional(),
  version: z.string().optional(),
  context: z.record(z.any()).optional()
});

/**
 * @route POST /api/v1/analytics/track
 * @desc Track a custom telemetry event
 * @access Public (rate limited)
 */
router.post('/track',
  rateLimiter({ windowMs: 60000, max: 1000 }), // 1000 events per minute
  async (req, res, next) => {
    try {
      const validation = TrackEventSchema.safeParse(req.body);
      if (!validation.success) {
        throw new ValidationError('Invalid event data', validation.error.issues);
      }

      const eventData = validation.data;

      // Add IP and user agent from request if not provided
      const context = {
        ...eventData.context,
        ip: eventData.context?.ip || req.ip,
        userAgent: eventData.context?.userAgent || req.get('User-Agent'),
        timestamp: new Date()
      };

      await telemetryService.trackEvent({
        ...eventData,
        context
      });

      res.status(201).json({ success: true });

    } catch (error) {
      next(error);
    }
  }
);

/**
 * @route POST /api/v1/analytics/track/download
 * @desc Track SDK download
 * @access Public (rate limited)
 */
router.post('/track/download',
  rateLimiter({ windowMs: 60000, max: 100 }), // 100 downloads per minute
  async (req, res, next) => {
    try {
      const validation = TrackDownloadSchema.safeParse(req.body);
      if (!validation.success) {
        throw new ValidationError('Invalid download data', validation.error.issues);
      }

      const downloadData = validation.data;

      await telemetryService.trackDownload({
        ...downloadData,
        ip: downloadData.ip || req.ip,
        userAgent: downloadData.userAgent || req.get('User-Agent')
      });

      res.status(201).json({ success: true });

    } catch (error) {
      next(error);
    }
  }
);

/**
 * @route POST /api/v1/analytics/track/api-call
 * @desc Track API call metrics
 * @access Private
 */
router.post('/track/api-call',
  authenticateApiKey(['admin', 'system']),
  rateLimiter({ windowMs: 60000, max: 10000 }), // 10k API calls per minute
  async (req, res, next) => {
    try {
      const validation = TrackApiCallSchema.safeParse(req.body);
      if (!validation.success) {
        throw new ValidationError('Invalid API call data', validation.error.issues);
      }

      const apiCallData = validation.data;

      await telemetryService.trackApiCall({
        ...apiCallData,
        ip: apiCallData.ip || req.ip
      });

      res.status(201).json({ success: true });

    } catch (error) {
      next(error);
    }
  }
);

/**
 * @route POST /api/v1/analytics/track/feature
 * @desc Track feature usage
 * @access Public (rate limited)
 */
router.post('/track/feature',
  rateLimiter({ windowMs: 60000, max: 500 }), // 500 feature events per minute
  async (req, res, next) => {
    try {
      const validation = TrackFeatureSchema.safeParse(req.body);
      if (!validation.success) {
        throw new ValidationError('Invalid feature data', validation.error.issues);
      }

      const featureData = validation.data;

      await telemetryService.trackFeatureUsage(featureData);

      res.status(201).json({ success: true });

    } catch (error) {
      next(error);
    }
  }
);

/**
 * @route POST /api/v1/analytics/track/error
 * @desc Track error occurrences
 * @access Public (rate limited)
 */
router.post('/track/error',
  rateLimiter({ windowMs: 60000, max: 200 }), // 200 errors per minute
  async (req, res, next) => {
    try {
      const validation = TrackErrorSchema.safeParse(req.body);
      if (!validation.success) {
        throw new ValidationError('Invalid error data', validation.error.issues);
      }

      const errorData = validation.data;

      await telemetryService.trackError(errorData);

      res.status(201).json({ success: true });

    } catch (error) {
      next(error);
    }
  }
);

/**
 * @route GET /api/v1/analytics/data
 * @desc Get analytics data
 * @access Private
 */
router.get('/data',
  authenticateApiKey(['admin', 'analytics']),
  async (req, res, next) => {
    try {
      const validation = AnalyticsQuerySchema.safeParse(req.query);
      if (!validation.success) {
        throw new ValidationError('Invalid analytics query', validation.error.issues);
      }

      const queryData = validation.data;

      const analytics = await telemetryService.getAnalytics({
        ...queryData,
        startDate: new Date(queryData.startDate),
        endDate: new Date(queryData.endDate)
      });

      res.json(analytics);

    } catch (error) {
      next(error);
    }
  }
);

/**
 * @route GET /api/v1/analytics/sdk-metrics
 * @desc Get SDK metrics
 * @access Private
 */
router.get('/sdk-metrics',
  authenticateApiKey(['admin', 'analytics']),
  async (req, res, next) => {
    try {
      const { timeframe = 'week' } = req.query;

      if (!['day', 'week', 'month'].includes(timeframe as string)) {
        throw new ValidationError('Invalid timeframe. Must be day, week, or month');
      }

      const metrics = await telemetryService.getSDKMetrics(timeframe as 'day' | 'week' | 'month');

      res.json(metrics);

    } catch (error) {
      next(error);
    }
  }
);

/**
 * @route GET /api/v1/analytics/real-time
 * @desc Get real-time metrics
 * @access Private
 */
router.get('/real-time',
  authenticateApiKey(['admin', 'analytics']),
  rateLimiter({ windowMs: 60000, max: 120 }), // 2 requests per second
  async (req, res, next) => {
    try {
      const metrics = await telemetryService.getRealTimeMetrics();

      res.json({
        timestamp: new Date().toISOString(),
        metrics
      });

    } catch (error) {
      next(error);
    }
  }
);

/**
 * @route GET /api/v1/analytics/organization/:organizationId
 * @desc Get analytics for specific organization
 * @access Private
 */
router.get('/organization/:organizationId',
  authenticateApiKey(['admin', 'analytics', 'organization']),
  async (req, res, next) => {
    try {
      const { organizationId } = req.params;
      const { startDate, endDate, granularity = 'day' } = req.query;

      // Check access permissions
      if (req.user?.role !== 'admin' &&
          req.user?.role !== 'analytics' &&
          req.user?.organizationId !== organizationId) {
        return res.status(403).json({
          error: 'Forbidden',
          message: 'Access denied to this organization data'
        });
      }

      if (!startDate || !endDate) {
        throw new ValidationError('startDate and endDate are required');
      }

      const analytics = await telemetryService.getAnalytics({
        organizationId,
        startDate: new Date(startDate as string),
        endDate: new Date(endDate as string),
        granularity: granularity as 'hour' | 'day' | 'week' | 'month'
      });

      res.json(analytics);

    } catch (error) {
      next(error);
    }
  }
);

/**
 * @route GET /api/v1/analytics/license/:licenseId
 * @desc Get analytics for specific license
 * @access Private
 */
router.get('/license/:licenseId',
  authenticateApiKey(['admin', 'analytics', 'organization']),
  async (req, res, next) => {
    try {
      const { licenseId } = req.params;
      const { startDate, endDate, granularity = 'day' } = req.query;

      if (!startDate || !endDate) {
        throw new ValidationError('startDate and endDate are required');
      }

      // TODO: Add license access validation

      const analytics = await telemetryService.getAnalytics({
        licenseId,
        startDate: new Date(startDate as string),
        endDate: new Date(endDate as string),
        granularity: granularity as 'hour' | 'day' | 'week' | 'month'
      });

      res.json(analytics);

    } catch (error) {
      next(error);
    }
  }
);

/**
 * @route GET /api/v1/analytics/health
 * @desc Health check for analytics service
 * @access Public
 */
router.get('/health', (req, res) => {
  res.json({
    status: 'healthy',
    service: 'analytics',
    timestamp: new Date().toISOString()
  });
});

export default router;