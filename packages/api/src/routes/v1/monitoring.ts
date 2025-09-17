/**
 * Monitoring and alerting API endpoints
 */

import { Router } from 'express';
import { z } from 'zod';
import { authenticateApiKey, rateLimiter } from '../../middleware';
import { MonitoringService } from '../../services/MonitoringService';
import { ValidationError } from '../../utils/errors';
import { logger } from '../../utils/logger';

const router = Router();
const monitoringService = new MonitoringService();

// Validation schemas
const CreateAlertSchema = z.object({
  type: z.enum(['system', 'business', 'security', 'performance']),
  severity: z.enum(['info', 'warning', 'error', 'critical']),
  title: z.string().min(1),
  message: z.string().min(1),
  source: z.string().min(1),
  metadata: z.record(z.any()).optional()
});

const MetricsQuerySchema = z.object({
  startTime: z.string().datetime(),
  endTime: z.string().datetime(),
  granularity: z.enum(['minute', 'hour', 'day']).optional()
});

/**
 * @route GET /api/v1/monitoring/health
 * @desc Get comprehensive health check
 * @access Admin only
 */
router.get('/health',
  authenticateApiKey(['admin']),
  async (req, res, next) => {
    try {
      const healthCheck = await monitoringService.performHealthCheck();

      res.json(healthCheck);

    } catch (error) {
      next(error);
    }
  }
);

/**
 * @route GET /api/v1/monitoring/metrics
 * @desc Get current system metrics
 * @access Admin only
 */
router.get('/metrics',
  authenticateApiKey(['admin']),
  async (req, res, next) => {
    try {
      const metrics = await monitoringService.collectMetrics();

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
 * @route GET /api/v1/monitoring/metrics/history
 * @desc Get metrics history for time range
 * @access Admin only
 */
router.get('/metrics/history',
  authenticateApiKey(['admin']),
  async (req, res, next) => {
    try {
      const validation = MetricsQuerySchema.safeParse(req.query);
      if (!validation.success) {
        throw new ValidationError('Invalid metrics query', validation.error.issues);
      }

      const { startTime, endTime, granularity = 'hour' } = validation.data;

      const history = await monitoringService.getMetricsHistory(
        new Date(startTime),
        new Date(endTime),
        granularity
      );

      res.json({
        query: {
          startTime,
          endTime,
          granularity
        },
        dataPoints: history.length,
        history
      });

    } catch (error) {
      next(error);
    }
  }
);

/**
 * @route GET /api/v1/monitoring/alerts
 * @desc Get active alerts
 * @access Admin only
 */
router.get('/alerts',
  authenticateApiKey(['admin']),
  async (req, res, next) => {
    try {
      const { severity, type } = req.query;

      const alerts = await monitoringService.getActiveAlerts(
        severity as string,
        type as string
      );

      res.json({
        total: alerts.length,
        alerts
      });

    } catch (error) {
      next(error);
    }
  }
);

/**
 * @route POST /api/v1/monitoring/alerts
 * @desc Create custom alert
 * @access Admin only
 */
router.post('/alerts',
  authenticateApiKey(['admin']),
  async (req, res, next) => {
    try {
      const validation = CreateAlertSchema.safeParse(req.body);
      if (!validation.success) {
        throw new ValidationError('Invalid alert data', validation.error.issues);
      }

      const alertData = validation.data;
      const alert = await monitoringService.createAlert(alertData);

      logger.info('Manual alert created', {
        alertId: alert.id,
        severity: alert.severity,
        title: alert.title,
        adminId: req.user?.id
      });

      res.status(201).json(alert);

    } catch (error) {
      next(error);
    }
  }
);

/**
 * @route PUT /api/v1/monitoring/alerts/:alertId/resolve
 * @desc Resolve alert
 * @access Admin only
 */
router.put('/alerts/:alertId/resolve',
  authenticateApiKey(['admin']),
  async (req, res, next) => {
    try {
      const { alertId } = req.params;
      const resolvedBy = req.user?.id || 'unknown';

      await monitoringService.resolveAlert(alertId, resolvedBy);

      logger.info('Alert resolved via monitoring API', {
        alertId,
        resolvedBy,
        adminId: req.user?.id
      });

      res.json({
        success: true,
        message: 'Alert resolved successfully'
      });

    } catch (error) {
      next(error);
    }
  }
);

/**
 * @route GET /api/v1/monitoring/system-load
 * @desc Check if system is under high load
 * @access Admin only
 */
router.get('/system-load',
  authenticateApiKey(['admin']),
  async (req, res, next) => {
    try {
      const loadStatus = await monitoringService.isSystemUnderHighLoad();

      res.json({
        timestamp: new Date().toISOString(),
        ...loadStatus
      });

    } catch (error) {
      next(error);
    }
  }
);

/**
 * @route GET /api/v1/monitoring/uptime
 * @desc Get uptime report
 * @access Admin only
 */
router.get('/uptime',
  authenticateApiKey(['admin']),
  async (req, res, next) => {
    try {
      const { days = 30 } = req.query;
      const daysNum = parseInt(days as string);

      if (daysNum < 1 || daysNum > 365) {
        throw new ValidationError('Days must be between 1 and 365');
      }

      const uptimeReport = await monitoringService.generateUptimeReport(daysNum);

      res.json({
        period: `${daysNum} days`,
        generatedAt: new Date().toISOString(),
        ...uptimeReport
      });

    } catch (error) {
      next(error);
    }
  }
);

/**
 * @route GET /api/v1/monitoring/status
 * @desc Get overall system status (public endpoint for status page)
 * @access Public
 */
router.get('/status',
  rateLimiter({ windowMs: 60000, max: 100 }), // 100 requests per minute
  async (req, res, next) => {
    try {
      const healthCheck = await monitoringService.performHealthCheck();

      // Return simplified status for public consumption
      const publicStatus = {
        status: healthCheck.status,
        lastUpdated: new Date().toISOString(),
        services: healthCheck.checks.map(check => ({
          name: check.name,
          status: check.status,
          responseTime: check.responseTime
        }))
      };

      res.json(publicStatus);

    } catch (error) {
      // Return degraded status on error
      res.json({
        status: 'warning',
        lastUpdated: new Date().toISOString(),
        message: 'Unable to perform full health check',
        services: []
      });
    }
  }
);

/**
 * @route POST /api/v1/monitoring/test-alert
 * @desc Test alert system (Admin only)
 * @access Admin only
 */
router.post('/test-alert',
  authenticateApiKey(['admin']),
  rateLimiter({ windowMs: 300000, max: 5 }), // 5 test alerts per 5 minutes
  async (req, res, next) => {
    try {
      const { severity = 'info' } = req.body;

      if (!['info', 'warning', 'error', 'critical'].includes(severity)) {
        throw new ValidationError('Invalid severity level');
      }

      const testAlert = await monitoringService.createAlert({
        type: 'system',
        severity,
        title: 'Test Alert',
        message: `Test alert created by admin ${req.user?.id || 'unknown'}`,
        source: 'monitoring_test',
        metadata: {
          test: true,
          adminId: req.user?.id,
          timestamp: new Date().toISOString()
        }
      });

      logger.info('Test alert created', {
        alertId: testAlert.id,
        severity,
        adminId: req.user?.id
      });

      res.status(201).json({
        success: true,
        message: 'Test alert created successfully',
        alert: testAlert
      });

    } catch (error) {
      next(error);
    }
  }
);

/**
 * @route GET /api/v1/monitoring/dashboards/overview
 * @desc Get monitoring dashboard overview
 * @access Admin only
 */
router.get('/dashboards/overview',
  authenticateApiKey(['admin']),
  async (req, res, next) => {
    try {
      const [healthCheck, metrics, activeAlerts, loadStatus] = await Promise.all([
        monitoringService.performHealthCheck(),
        monitoringService.collectMetrics(),
        monitoringService.getActiveAlerts(),
        monitoringService.isSystemUnderHighLoad()
      ]);

      const overview = {
        timestamp: new Date().toISOString(),
        health: {
          status: healthCheck.status,
          summary: healthCheck.summary
        },
        metrics: {
          system: metrics.system,
          application: metrics.application,
          database: metrics.database
        },
        alerts: {
          total: activeAlerts.length,
          critical: activeAlerts.filter(a => a.severity === 'critical').length,
          warning: activeAlerts.filter(a => a.severity === 'warning').length,
          recent: activeAlerts.slice(0, 5) // Last 5 alerts
        },
        load: loadStatus,
        summary: {
          systemHealthy: healthCheck.status === 'healthy',
          alertsActive: activeAlerts.length > 0,
          highLoad: loadStatus.isHighLoad,
          lastHealthCheck: healthCheck.checks[0]?.lastCheck
        }
      };

      res.json(overview);

    } catch (error) {
      next(error);
    }
  }
);

export default router;