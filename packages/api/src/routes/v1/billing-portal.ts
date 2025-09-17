/**
 * Customer billing portal API endpoints
 * Public endpoints for customer self-service billing management
 */

import { Router } from 'express';
import { z } from 'zod';
import { rateLimiter } from '../../middleware';
import { BillingPortalService } from '../../services/BillingPortalService';
import { ValidationError } from '../../utils/errors';
import { logger } from '../../utils/logger';

const router = Router();
const portalService = new BillingPortalService();

// Validation schemas
const CreatePortalSessionSchema = z.object({
  customerId: z.string(),
  organizationId: z.string().uuid(),
  returnUrl: z.string().url().optional(),
  expiresInMinutes: z.number().min(5).max(1440).optional() // 5 minutes to 24 hours
});

const UpdateSubscriptionSchema = z.object({
  plan: z.enum(['pro', 'enterprise']),
  billingCycle: z.enum(['monthly', 'yearly']).optional(),
  seats: z.number().positive().optional()
});

const AddPaymentMethodSchema = z.object({
  paymentMethodId: z.string()
});

const SetDefaultPaymentMethodSchema = z.object({
  paymentMethodId: z.string()
});

/**
 * @route POST /api/v1/billing-portal/sessions
 * @desc Create a billing portal session (Admin/Billing only)
 * @access Private
 */
router.post('/sessions',
  rateLimiter({ windowMs: 60000, max: 10 }), // 10 sessions per minute
  async (req, res, next) => {
    try {
      const validation = CreatePortalSessionSchema.safeParse(req.body);
      if (!validation.success) {
        throw new ValidationError('Invalid portal session data', validation.error.issues);
      }

      const sessionData = validation.data;
      const result = await portalService.createPortalSession(sessionData);

      logger.info('Billing portal session created', {
        sessionId: result.sessionId,
        customerId: sessionData.customerId,
        organizationId: sessionData.organizationId
      });

      res.status(201).json(result);

    } catch (error) {
      next(error);
    }
  }
);

/**
 * @route GET /api/v1/billing-portal/info
 * @desc Get customer billing information
 * @access Public (session validated)
 */
router.get('/info',
  rateLimiter({ windowMs: 60000, max: 60 }), // 60 requests per minute
  async (req, res, next) => {
    try {
      const { session: sessionId, token } = req.query;

      if (!sessionId || !token) {
        return res.status(400).json({
          error: 'Missing session or token'
        });
      }

      const billingInfo = await portalService.getCustomerBillingInfo(
        sessionId as string,
        token as string
      );

      res.json(billingInfo);

    } catch (error) {
      next(error);
    }
  }
);

/**
 * @route PUT /api/v1/billing-portal/subscription
 * @desc Update subscription plan
 * @access Public (session validated)
 */
router.put('/subscription',
  rateLimiter({ windowMs: 60000, max: 5 }), // 5 updates per minute
  async (req, res, next) => {
    try {
      const { session: sessionId, token } = req.query;

      if (!sessionId || !token) {
        return res.status(400).json({
          error: 'Missing session or token'
        });
      }

      const validation = UpdateSubscriptionSchema.safeParse(req.body);
      if (!validation.success) {
        throw new ValidationError('Invalid subscription update data', validation.error.issues);
      }

      const updateData = validation.data;
      const subscription = await portalService.updateSubscriptionPlan(
        sessionId as string,
        token as string,
        updateData
      );

      res.json({
        message: 'Subscription updated successfully',
        subscription
      });

    } catch (error) {
      next(error);
    }
  }
);

/**
 * @route DELETE /api/v1/billing-portal/subscription
 * @desc Cancel subscription
 * @access Public (session validated)
 */
router.delete('/subscription',
  rateLimiter({ windowMs: 60000, max: 3 }), // 3 cancellations per minute
  async (req, res, next) => {
    try {
      const { session: sessionId, token, immediate = 'false' } = req.query;

      if (!sessionId || !token) {
        return res.status(400).json({
          error: 'Missing session or token'
        });
      }

      const isImmediate = immediate === 'true';
      const subscription = await portalService.cancelSubscription(
        sessionId as string,
        token as string,
        isImmediate
      );

      res.json({
        message: isImmediate
          ? 'Subscription cancelled immediately'
          : 'Subscription will cancel at the end of the billing period',
        subscription
      });

    } catch (error) {
      next(error);
    }
  }
);

/**
 * @route POST /api/v1/billing-portal/payment-methods
 * @desc Add payment method
 * @access Public (session validated)
 */
router.post('/payment-methods',
  rateLimiter({ windowMs: 60000, max: 5 }), // 5 additions per minute
  async (req, res, next) => {
    try {
      const { session: sessionId, token } = req.query;

      if (!sessionId || !token) {
        return res.status(400).json({
          error: 'Missing session or token'
        });
      }

      const validation = AddPaymentMethodSchema.safeParse(req.body);
      if (!validation.success) {
        throw new ValidationError('Invalid payment method data', validation.error.issues);
      }

      const { paymentMethodId } = validation.data;
      const paymentMethod = await portalService.addPaymentMethod(
        sessionId as string,
        token as string,
        paymentMethodId
      );

      res.status(201).json({
        message: 'Payment method added successfully',
        paymentMethod
      });

    } catch (error) {
      next(error);
    }
  }
);

/**
 * @route DELETE /api/v1/billing-portal/payment-methods/:paymentMethodId
 * @desc Remove payment method
 * @access Public (session validated)
 */
router.delete('/payment-methods/:paymentMethodId',
  rateLimiter({ windowMs: 60000, max: 5 }), // 5 removals per minute
  async (req, res, next) => {
    try {
      const { session: sessionId, token } = req.query;
      const { paymentMethodId } = req.params;

      if (!sessionId || !token) {
        return res.status(400).json({
          error: 'Missing session or token'
        });
      }

      await portalService.removePaymentMethod(
        sessionId as string,
        token as string,
        paymentMethodId
      );

      res.json({
        message: 'Payment method removed successfully'
      });

    } catch (error) {
      next(error);
    }
  }
);

/**
 * @route PUT /api/v1/billing-portal/payment-methods/:paymentMethodId/default
 * @desc Set default payment method
 * @access Public (session validated)
 */
router.put('/payment-methods/:paymentMethodId/default',
  rateLimiter({ windowMs: 60000, max: 10 }), // 10 updates per minute
  async (req, res, next) => {
    try {
      const { session: sessionId, token } = req.query;
      const { paymentMethodId } = req.params;

      if (!sessionId || !token) {
        return res.status(400).json({
          error: 'Missing session or token'
        });
      }

      await portalService.setDefaultPaymentMethod(
        sessionId as string,
        token as string,
        paymentMethodId
      );

      res.json({
        message: 'Default payment method updated successfully'
      });

    } catch (error) {
      next(error);
    }
  }
);

/**
 * @route GET /api/v1/billing-portal/invoices/:invoiceId/download
 * @desc Download invoice
 * @access Public (session validated)
 */
router.get('/invoices/:invoiceId/download',
  rateLimiter({ windowMs: 60000, max: 10 }), // 10 downloads per minute
  async (req, res, next) => {
    try {
      const { session: sessionId, token } = req.query;
      const { invoiceId } = req.params;

      if (!sessionId || !token) {
        return res.status(400).json({
          error: 'Missing session or token'
        });
      }

      const download = await portalService.downloadInvoice(
        sessionId as string,
        token as string,
        invoiceId
      );

      res.json({
        downloadUrl: download.url,
        expiresAt: download.expiresAt
      });

    } catch (error) {
      next(error);
    }
  }
);

/**
 * @route GET /api/v1/billing-portal/health
 * @desc Health check for billing portal
 * @access Public
 */
router.get('/health', (req, res) => {
  res.json({
    status: 'healthy',
    service: 'billing-portal',
    timestamp: new Date().toISOString()
  });
});

export default router;