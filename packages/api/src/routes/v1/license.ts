/**
 * License validation and management API endpoints
 */

import { Router } from 'express';
import { z } from 'zod';
import { authenticateApiKey, rateLimiter } from '../../middleware';
import { LicenseService } from '../../services/LicenseService';
import { ValidationError, NotFoundError } from '../../utils/errors';
import { logger } from '../../utils/logger';

const router = Router();
const licenseService = new LicenseService();

// Validation schemas
const ValidateLicenseSchema = z.object({
  key: z.string().min(1, 'License key is required'),
  sdk: z.string().optional(),
  version: z.string().optional(),
  environment: z.enum(['development', 'staging', 'production']).optional(),
  domain: z.string().optional()
});

const GenerateLicenseSchema = z.object({
  organizationId: z.string().uuid(),
  plan: z.enum(['pro', 'enterprise']),
  features: z.array(z.string()),
  expiresAt: z.string().datetime().optional(),
  seats: z.number().positive().optional(),
  customLimits: z.record(z.any()).optional(),
  metadata: z.record(z.any()).optional()
});

const UpdateLicenseSchema = z.object({
  features: z.array(z.string()).optional(),
  expiresAt: z.string().datetime().optional(),
  seats: z.number().positive().optional(),
  customLimits: z.record(z.any()).optional(),
  status: z.enum(['active', 'suspended', 'expired']).optional(),
  metadata: z.record(z.any()).optional()
});

/**
 * @route POST /api/v1/license/validate
 * @desc Validate a license key
 * @access Public (rate limited)
 */
router.post('/validate',
  rateLimiter({ windowMs: 60000, max: 100 }), // 100 requests per minute
  async (req, res, next) => {
    try {
      const validation = ValidateLicenseSchema.safeParse(req.body);
      if (!validation.success) {
        throw new ValidationError('Invalid request data', validation.error.issues);
      }

      const { key, sdk, version, environment, domain } = validation.data;

      // Validate the license
      const licenseInfo = await licenseService.validateLicense(key, {
        sdk,
        version,
        environment,
        domain,
        ip: req.ip,
        userAgent: req.get('User-Agent')
      });

      if (!licenseInfo.valid) {
        return res.status(402).json({
          error: 'Payment Required',
          message: 'License is invalid, expired, or suspended',
          code: 'LICENSE_INVALID'
        });
      }

      // Track usage
      await licenseService.trackUsage(key, 'validation', {
        sdk,
        version,
        environment,
        domain,
        ip: req.ip
      });

      // Return license information
      res.json({
        valid: true,
        plan: licenseInfo.plan,
        features: licenseInfo.features,
        organizationId: licenseInfo.organizationId,
        expiresAt: licenseInfo.expiresAt,
        seats: licenseInfo.seats,
        customLimits: licenseInfo.customLimits,
        usage: {
          currentPeriod: licenseInfo.currentUsage,
          limits: licenseInfo.limits
        }
      });

    } catch (error) {
      next(error);
    }
  }
);

/**
 * @route POST /api/v1/license/generate
 * @desc Generate a new license key (Admin only)
 * @access Private
 */
router.post('/generate',
  authenticateApiKey(['admin', 'billing']),
  async (req, res, next) => {
    try {
      const validation = GenerateLicenseSchema.safeParse(req.body);
      if (!validation.success) {
        throw new ValidationError('Invalid request data', validation.error.issues);
      }

      const licenseData = validation.data;
      const license = await licenseService.generateLicense(licenseData);

      logger.info('License generated', {
        licenseId: license.id,
        organizationId: licenseData.organizationId,
        plan: licenseData.plan,
        adminId: req.user?.id
      });

      res.status(201).json({
        id: license.id,
        key: license.key,
        plan: license.plan,
        features: license.features,
        organizationId: license.organizationId,
        expiresAt: license.expiresAt,
        seats: license.seats,
        customLimits: license.customLimits,
        status: license.status,
        createdAt: license.createdAt
      });

    } catch (error) {
      next(error);
    }
  }
);

/**
 * @route GET /api/v1/license/:licenseId
 * @desc Get license details (Organization admin or system admin)
 * @access Private
 */
router.get('/:licenseId',
  authenticateApiKey(['admin', 'organization']),
  async (req, res, next) => {
    try {
      const { licenseId } = req.params;

      const license = await licenseService.getLicenseById(licenseId);
      if (!license) {
        throw new NotFoundError('License not found');
      }

      // Check access permissions
      if (req.user?.role !== 'admin' &&
          req.user?.organizationId !== license.organizationId) {
        return res.status(403).json({
          error: 'Forbidden',
          message: 'Access denied to this license'
        });
      }

      res.json({
        id: license.id,
        key: license.maskedKey, // Only show masked version
        plan: license.plan,
        features: license.features,
        organizationId: license.organizationId,
        expiresAt: license.expiresAt,
        seats: license.seats,
        customLimits: license.customLimits,
        status: license.status,
        usage: license.currentUsage,
        createdAt: license.createdAt,
        updatedAt: license.updatedAt
      });

    } catch (error) {
      next(error);
    }
  }
);

/**
 * @route PUT /api/v1/license/:licenseId
 * @desc Update license (Admin only)
 * @access Private
 */
router.put('/:licenseId',
  authenticateApiKey(['admin']),
  async (req, res, next) => {
    try {
      const { licenseId } = req.params;

      const validation = UpdateLicenseSchema.safeParse(req.body);
      if (!validation.success) {
        throw new ValidationError('Invalid request data', validation.error.issues);
      }

      const updateData = validation.data;
      const license = await licenseService.updateLicense(licenseId, updateData);

      logger.info('License updated', {
        licenseId,
        updateData,
        adminId: req.user?.id
      });

      res.json({
        id: license.id,
        plan: license.plan,
        features: license.features,
        organizationId: license.organizationId,
        expiresAt: license.expiresAt,
        seats: license.seats,
        customLimits: license.customLimits,
        status: license.status,
        updatedAt: license.updatedAt
      });

    } catch (error) {
      next(error);
    }
  }
);

/**
 * @route DELETE /api/v1/license/:licenseId
 * @desc Revoke/Delete license (Admin only)
 * @access Private
 */
router.delete('/:licenseId',
  authenticateApiKey(['admin']),
  async (req, res, next) => {
    try {
      const { licenseId } = req.params;

      await licenseService.revokeLicense(licenseId);

      logger.info('License revoked', {
        licenseId,
        adminId: req.user?.id
      });

      res.json({
        message: 'License revoked successfully'
      });

    } catch (error) {
      next(error);
    }
  }
);

/**
 * @route GET /api/v1/license/:licenseId/usage
 * @desc Get license usage statistics
 * @access Private
 */
router.get('/:licenseId/usage',
  authenticateApiKey(['admin', 'organization']),
  async (req, res, next) => {
    try {
      const { licenseId } = req.params;
      const { startDate, endDate, granularity = 'day' } = req.query;

      const license = await licenseService.getLicenseById(licenseId);
      if (!license) {
        throw new NotFoundError('License not found');
      }

      // Check access permissions
      if (req.user?.role !== 'admin' &&
          req.user?.organizationId !== license.organizationId) {
        return res.status(403).json({
          error: 'Forbidden',
          message: 'Access denied to this license'
        });
      }

      const usage = await licenseService.getUsageStatistics(licenseId, {
        startDate: startDate as string,
        endDate: endDate as string,
        granularity: granularity as 'hour' | 'day' | 'week' | 'month'
      });

      res.json(usage);

    } catch (error) {
      next(error);
    }
  }
);

/**
 * @route POST /api/v1/license/:licenseId/suspend
 * @desc Suspend a license (Admin only)
 * @access Private
 */
router.post('/:licenseId/suspend',
  authenticateApiKey(['admin']),
  async (req, res, next) => {
    try {
      const { licenseId } = req.params;
      const { reason } = req.body;

      await licenseService.suspendLicense(licenseId, reason);

      logger.warn('License suspended', {
        licenseId,
        reason,
        adminId: req.user?.id
      });

      res.json({
        message: 'License suspended successfully'
      });

    } catch (error) {
      next(error);
    }
  }
);

/**
 * @route POST /api/v1/license/:licenseId/reactivate
 * @desc Reactivate a suspended license (Admin only)
 * @access Private
 */
router.post('/:licenseId/reactivate',
  authenticateApiKey(['admin']),
  async (req, res, next) => {
    try {
      const { licenseId } = req.params;

      await licenseService.reactivateLicense(licenseId);

      logger.info('License reactivated', {
        licenseId,
        adminId: req.user?.id
      });

      res.json({
        message: 'License reactivated successfully'
      });

    } catch (error) {
      next(error);
    }
  }
);

export default router;