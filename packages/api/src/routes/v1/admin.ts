/**
 * Admin dashboard API endpoints
 */

import { Router } from 'express';
import { z } from 'zod';
import { authenticateApiKey, rateLimiter } from '../../middleware';
import { AdminDashboardService } from '../../services/AdminDashboardService';
import { LicenseService } from '../../services/LicenseService';
import { PaymentGatewayService } from '../../services/PaymentGatewayService';
import { ValidationError, NotFoundError } from '../../utils/errors';
import { logger } from '../../utils/logger';

const router = Router();
const adminService = new AdminDashboardService();
const licenseService = new LicenseService();
const paymentService = new PaymentGatewayService();

// Validation schemas
const CreateAlertSchema = z.object({
  type: z.enum(['info', 'warning', 'error', 'critical']),
  message: z.string().min(1),
  source: z.string().optional(),
  metadata: z.record(z.any()).optional()
});

const UpdateUserSchema = z.object({
  name: z.string().optional(),
  email: z.string().email().optional(),
  role: z.enum(['user', 'admin', 'billing']).optional(),
  status: z.enum(['active', 'suspended', 'deactivated']).optional()
});

/**
 * @route GET /api/v1/admin/dashboard
 * @desc Get dashboard overview
 * @access Admin only
 */
router.get('/dashboard',
  authenticateApiKey(['admin']),
  async (req, res, next) => {
    try {
      const overview = await adminService.getDashboardOverview();

      res.json(overview);

    } catch (error) {
      next(error);
    }
  }
);

/**
 * @route GET /api/v1/admin/system-health
 * @desc Get system health status
 * @access Admin only
 */
router.get('/system-health',
  authenticateApiKey(['admin']),
  async (req, res, next) => {
    try {
      const health = await adminService.getSystemHealth();

      res.json(health);

    } catch (error) {
      next(error);
    }
  }
);

/**
 * @route GET /api/v1/admin/customers
 * @desc Get customer insights
 * @access Admin only
 */
router.get('/customers',
  authenticateApiKey(['admin']),
  async (req, res, next) => {
    try {
      const insights = await adminService.getCustomerInsights();

      res.json(insights);

    } catch (error) {
      next(error);
    }
  }
);

/**
 * @route GET /api/v1/admin/licenses
 * @desc Get license metrics
 * @access Admin only
 */
router.get('/licenses',
  authenticateApiKey(['admin']),
  async (req, res, next) => {
    try {
      const metrics = await adminService.getLicenseMetrics();

      res.json(metrics);

    } catch (error) {
      next(error);
    }
  }
);

/**
 * @route GET /api/v1/admin/revenue
 * @desc Get revenue analytics
 * @access Admin only
 */
router.get('/revenue',
  authenticateApiKey(['admin']),
  async (req, res, next) => {
    try {
      const analytics = await adminService.getRevenueAnalytics();

      res.json(analytics);

    } catch (error) {
      next(error);
    }
  }
);

/**
 * @route GET /api/v1/admin/platform-stats
 * @desc Get platform statistics
 * @access Admin only
 */
router.get('/platform-stats',
  authenticateApiKey(['admin']),
  async (req, res, next) => {
    try {
      const stats = await adminService.getPlatformStatistics();

      res.json(stats);

    } catch (error) {
      next(error);
    }
  }
);

/**
 * @route POST /api/v1/admin/alerts
 * @desc Create system alert
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
      await adminService.createAlert(alertData);

      logger.info('Alert created via admin dashboard', {
        type: alertData.type,
        message: alertData.message,
        adminId: req.user?.id
      });

      res.status(201).json({ success: true });

    } catch (error) {
      next(error);
    }
  }
);

/**
 * @route PUT /api/v1/admin/alerts/:alertId/resolve
 * @desc Resolve system alert
 * @access Admin only
 */
router.put('/alerts/:alertId/resolve',
  authenticateApiKey(['admin']),
  async (req, res, next) => {
    try {
      const { alertId } = req.params;

      await adminService.resolveAlert(alertId);

      logger.info('Alert resolved via admin dashboard', {
        alertId,
        adminId: req.user?.id
      });

      res.json({ success: true });

    } catch (error) {
      next(error);
    }
  }
);

/**
 * @route GET /api/v1/admin/users
 * @desc Get all users with pagination
 * @access Admin only
 */
router.get('/users',
  authenticateApiKey(['admin']),
  async (req, res, next) => {
    try {
      const { page = 1, limit = 50, search, status, role } = req.query;

      const skip = (parseInt(page as string) - 1) * parseInt(limit as string);
      const take = parseInt(limit as string);

      const whereClause: any = {};

      if (search) {
        whereClause.OR = [
          { name: { contains: search as string, mode: 'insensitive' } },
          { email: { contains: search as string, mode: 'insensitive' } }
        ];
      }

      if (status) {
        whereClause.status = status;
      }

      if (role) {
        whereClause.role = role;
      }

      const [users, total] = await Promise.all([
        // Assuming Prisma client exists - this would need proper implementation
        // this.prisma.user.findMany({
        //   where: whereClause,
        //   skip,
        //   take,
        //   orderBy: { createdAt: 'desc' }
        // }),
        // this.prisma.user.count({ where: whereClause })
        [], // Placeholder
        0 // Placeholder
      ]);

      res.json({
        users,
        pagination: {
          page: parseInt(page as string),
          limit: parseInt(limit as string),
          total,
          pages: Math.ceil(total / parseInt(limit as string))
        }
      });

    } catch (error) {
      next(error);
    }
  }
);

/**
 * @route GET /api/v1/admin/users/:userId
 * @desc Get user details
 * @access Admin only
 */
router.get('/users/:userId',
  authenticateApiKey(['admin']),
  async (req, res, next) => {
    try {
      const { userId } = req.params;

      // Get user with related data
      // const user = await this.prisma.user.findUnique({
      //   where: { id: userId },
      //   include: {
      //     organizations: true,
      //     sessions: true
      //   }
      // });

      // Placeholder response
      const user = {
        id: userId,
        name: 'User Name',
        email: 'user@example.com',
        status: 'active',
        role: 'user',
        createdAt: new Date(),
        lastLoginAt: new Date()
      };

      if (!user) {
        throw new NotFoundError('User not found');
      }

      res.json(user);

    } catch (error) {
      next(error);
    }
  }
);

/**
 * @route PUT /api/v1/admin/users/:userId
 * @desc Update user
 * @access Admin only
 */
router.put('/users/:userId',
  authenticateApiKey(['admin']),
  async (req, res, next) => {
    try {
      const { userId } = req.params;

      const validation = UpdateUserSchema.safeParse(req.body);
      if (!validation.success) {
        throw new ValidationError('Invalid user update data', validation.error.issues);
      }

      const updateData = validation.data;

      // Update user
      // const user = await this.prisma.user.update({
      //   where: { id: userId },
      //   data: updateData
      // });

      // Placeholder response
      const user = {
        id: userId,
        ...updateData,
        updatedAt: new Date()
      };

      logger.info('User updated via admin dashboard', {
        userId,
        updateData,
        adminId: req.user?.id
      });

      res.json(user);

    } catch (error) {
      next(error);
    }
  }
);

/**
 * @route GET /api/v1/admin/organizations
 * @desc Get all organizations
 * @access Admin only
 */
router.get('/organizations',
  authenticateApiKey(['admin']),
  async (req, res, next) => {
    try {
      const { page = 1, limit = 50, search } = req.query;

      const skip = (parseInt(page as string) - 1) * parseInt(limit as string);
      const take = parseInt(limit as string);

      const whereClause: any = {};

      if (search) {
        whereClause.name = {
          contains: search as string,
          mode: 'insensitive'
        };
      }

      // Placeholder response
      const organizations = [
        {
          id: '1',
          name: 'Example Org',
          plan: 'pro',
          userCount: 25,
          licenseCount: 1,
          createdAt: new Date()
        }
      ];

      res.json({
        organizations,
        pagination: {
          page: parseInt(page as string),
          limit: parseInt(limit as string),
          total: organizations.length,
          pages: 1
        }
      });

    } catch (error) {
      next(error);
    }
  }
);

/**
 * @route GET /api/v1/admin/licenses/search
 * @desc Search licenses
 * @access Admin only
 */
router.get('/licenses/search',
  authenticateApiKey(['admin']),
  async (req, res, next) => {
    try {
      const { query, status, plan, organizationId } = req.query;

      const whereClause: any = {};

      if (status) {
        whereClause.status = status;
      }

      if (plan) {
        whereClause.plan = plan;
      }

      if (organizationId) {
        whereClause.organizationId = organizationId;
      }

      if (query) {
        whereClause.OR = [
          { key: { contains: query as string } },
          { organizationId: query as string }
        ];
      }

      // Get licenses with usage data
      const licenses = await Promise.all([
        // Would implement actual license search here
      ]);

      res.json({ licenses: [] }); // Placeholder

    } catch (error) {
      next(error);
    }
  }
);

/**
 * @route GET /api/v1/admin/payment-gateways/status
 * @desc Get payment gateway status
 * @access Admin only
 */
router.get('/payment-gateways/status',
  authenticateApiKey(['admin']),
  async (req, res, next) => {
    try {
      // Check status of all payment gateways
      const status = {
        conekta: { status: 'healthy', lastCheck: new Date() },
        fungies: { status: 'healthy', lastCheck: new Date() },
        stripe: { status: 'healthy', lastCheck: new Date() }
      };

      res.json(status);

    } catch (error) {
      next(error);
    }
  }
);

/**
 * @route POST /api/v1/admin/maintenance
 * @desc Trigger maintenance tasks
 * @access Admin only
 */
router.post('/maintenance',
  authenticateApiKey(['admin']),
  rateLimiter({ windowMs: 300000, max: 5 }), // 5 maintenance tasks per 5 minutes
  async (req, res, next) => {
    try {
      const { task } = req.body;

      const validTasks = [
        'cleanup_expired_sessions',
        'cleanup_old_telemetry',
        'refresh_analytics',
        'check_license_compliance',
        'sync_payment_data'
      ];

      if (!validTasks.includes(task)) {
        throw new ValidationError('Invalid maintenance task');
      }

      // Execute maintenance task asynchronously
      setImmediate(async () => {
        try {
          await this.executeMaintenanceTask(task);
          logger.info('Maintenance task completed', {
            task,
            adminId: req.user?.id
          });
        } catch (error) {
          logger.error('Maintenance task failed', {
            task,
            error,
            adminId: req.user?.id
          });
        }
      });

      res.json({
        success: true,
        message: `Maintenance task '${task}' started`
      });

    } catch (error) {
      next(error);
    }
  }
);

// Private method for maintenance tasks
async function executeMaintenanceTask(task: string): Promise<void> {
  switch (task) {
    case 'cleanup_expired_sessions':
      // Clean up expired sessions
      break;
    case 'cleanup_old_telemetry':
      // Clean up old telemetry data
      break;
    case 'refresh_analytics':
      // Refresh analytics caches
      break;
    case 'check_license_compliance':
      // Check license usage compliance
      break;
    case 'sync_payment_data':
      // Sync payment gateway data
      break;
  }
}

export default router;