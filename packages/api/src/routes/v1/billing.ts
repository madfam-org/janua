/**
 * Customer billing and subscription management API endpoints
 */

import { Router } from 'express';
import { z } from 'zod';
import { authenticateApiKey, rateLimiter } from '../../middleware';
import { PaymentGatewayService } from '../../services/PaymentGatewayService';
import { LicenseService } from '../../services/LicenseService';
import { ValidationError, NotFoundError, ConflictError } from '../../utils/errors';
import { logger } from '../../utils/logger';

const router = Router();
const paymentService = new PaymentGatewayService();
const licenseService = new LicenseService();

// Validation schemas
const CreateCustomerSchema = z.object({
  email: z.string().email(),
  name: z.string().min(1),
  organizationId: z.string().uuid(),
  country: z.string().length(2), // ISO country code
  billingAddress: z.object({
    line1: z.string(),
    line2: z.string().optional(),
    city: z.string(),
    state: z.string().optional(),
    postalCode: z.string(),
    country: z.string().length(2)
  })
});

const CreateSubscriptionSchema = z.object({
  customerId: z.string(),
  plan: z.enum(['pro', 'enterprise']),
  paymentMethodId: z.string().optional(),
  billingCycle: z.enum(['monthly', 'yearly']).default('monthly'),
  features: z.array(z.string()).optional(),
  seats: z.number().positive().optional(),
  customLimits: z.record(z.any()).optional()
});

const UpdateSubscriptionSchema = z.object({
  plan: z.enum(['pro', 'enterprise']).optional(),
  seats: z.number().positive().optional(),
  billingCycle: z.enum(['monthly', 'yearly']).optional(),
  features: z.array(z.string()).optional(),
  customLimits: z.record(z.any()).optional()
});

const CreatePaymentIntentSchema = z.object({
  customerId: z.string(),
  amount: z.number().positive(),
  currency: z.string().length(3).default('USD'),
  plan: z.enum(['pro', 'enterprise']),
  billingCycle: z.enum(['monthly', 'yearly']).default('monthly')
});

/**
 * @route POST /api/v1/billing/customers
 * @desc Create a new customer
 * @access Private
 */
router.post('/customers',
  authenticateApiKey(['admin', 'billing']),
  async (req, res, next) => {
    try {
      const validation = CreateCustomerSchema.safeParse(req.body);
      if (!validation.success) {
        throw new ValidationError('Invalid customer data', validation.error.issues);
      }

      const customerData = validation.data;
      const customer = await paymentService.createCustomer(customerData);

      logger.info('Customer created', {
        customerId: customer.id,
        email: customerData.email,
        organizationId: customerData.organizationId,
        adminId: req.user?.id
      });

      res.status(201).json({
        id: customer.id,
        email: customer.email,
        name: customer.name,
        organizationId: customer.organizationId,
        country: customer.country,
        paymentGateway: customer.paymentGateway,
        status: customer.status,
        createdAt: customer.createdAt
      });

    } catch (error) {
      next(error);
    }
  }
);

/**
 * @route GET /api/v1/billing/customers/:customerId
 * @desc Get customer details
 * @access Private
 */
router.get('/customers/:customerId',
  authenticateApiKey(['admin', 'billing', 'organization']),
  async (req, res, next) => {
    try {
      const { customerId } = req.params;

      const customer = await paymentService.getCustomer(customerId);
      if (!customer) {
        throw new NotFoundError('Customer not found');
      }

      // Check access permissions
      if (req.user?.role !== 'admin' &&
          req.user?.role !== 'billing' &&
          req.user?.organizationId !== customer.organizationId) {
        return res.status(403).json({
          error: 'Forbidden',
          message: 'Access denied to this customer'
        });
      }

      res.json(customer);

    } catch (error) {
      next(error);
    }
  }
);

/**
 * @route POST /api/v1/billing/payment-intents
 * @desc Create a payment intent for subscription
 * @access Private
 */
router.post('/payment-intents',
  authenticateApiKey(['admin', 'billing', 'organization']),
  rateLimiter({ windowMs: 60000, max: 10 }), // 10 payment intents per minute
  async (req, res, next) => {
    try {
      const validation = CreatePaymentIntentSchema.safeParse(req.body);
      if (!validation.success) {
        throw new ValidationError('Invalid payment intent data', validation.error.issues);
      }

      const intentData = validation.data;
      const customer = await paymentService.getCustomer(intentData.customerId);

      if (!customer) {
        throw new NotFoundError('Customer not found');
      }

      // Check permissions
      if (req.user?.role !== 'admin' &&
          req.user?.role !== 'billing' &&
          req.user?.organizationId !== customer.organizationId) {
        return res.status(403).json({
          error: 'Forbidden',
          message: 'Access denied'
        });
      }

      const paymentIntent = await paymentService.createPaymentIntent(intentData);

      logger.info('Payment intent created', {
        paymentIntentId: paymentIntent.id,
        customerId: intentData.customerId,
        amount: intentData.amount,
        currency: intentData.currency,
        gateway: paymentIntent.gateway,
        userId: req.user?.id
      });

      res.status(201).json(paymentIntent);

    } catch (error) {
      next(error);
    }
  }
);

/**
 * @route POST /api/v1/billing/subscriptions
 * @desc Create a new subscription
 * @access Private
 */
router.post('/subscriptions',
  authenticateApiKey(['admin', 'billing']),
  async (req, res, next) => {
    try {
      const validation = CreateSubscriptionSchema.safeParse(req.body);
      if (!validation.success) {
        throw new ValidationError('Invalid subscription data', validation.error.issues);
      }

      const subscriptionData = validation.data;
      const customer = await paymentService.getCustomer(subscriptionData.customerId);

      if (!customer) {
        throw new NotFoundError('Customer not found');
      }

      // Check for existing active subscription
      const existingSubscription = await paymentService.getActiveSubscription(subscriptionData.customerId);
      if (existingSubscription) {
        throw new ConflictError('Customer already has an active subscription');
      }

      const subscription = await paymentService.createSubscription(subscriptionData);

      // Generate license key after successful subscription
      const licenseData = {
        organizationId: customer.organizationId,
        plan: subscriptionData.plan,
        features: subscriptionData.features || [],
        seats: subscriptionData.seats,
        customLimits: subscriptionData.customLimits,
        metadata: {
          subscriptionId: subscription.id,
          customerId: customer.id,
          gateway: subscription.gateway
        }
      };

      const license = await licenseService.generateLicense(licenseData);

      logger.info('Subscription and license created', {
        subscriptionId: subscription.id,
        licenseId: license.id,
        customerId: customer.id,
        plan: subscriptionData.plan,
        adminId: req.user?.id
      });

      res.status(201).json({
        subscription,
        license: {
          id: license.id,
          key: license.key,
          plan: license.plan,
          features: license.features,
          expiresAt: license.expiresAt
        }
      });

    } catch (error) {
      next(error);
    }
  }
);

/**
 * @route GET /api/v1/billing/subscriptions/:subscriptionId
 * @desc Get subscription details
 * @access Private
 */
router.get('/subscriptions/:subscriptionId',
  authenticateApiKey(['admin', 'billing', 'organization']),
  async (req, res, next) => {
    try {
      const { subscriptionId } = req.params;

      const subscription = await paymentService.getSubscription(subscriptionId);
      if (!subscription) {
        throw new NotFoundError('Subscription not found');
      }

      const customer = await paymentService.getCustomer(subscription.customerId);

      // Check access permissions
      if (req.user?.role !== 'admin' &&
          req.user?.role !== 'billing' &&
          req.user?.organizationId !== customer?.organizationId) {
        return res.status(403).json({
          error: 'Forbidden',
          message: 'Access denied to this subscription'
        });
      }

      res.json(subscription);

    } catch (error) {
      next(error);
    }
  }
);

/**
 * @route PUT /api/v1/billing/subscriptions/:subscriptionId
 * @desc Update subscription
 * @access Private
 */
router.put('/subscriptions/:subscriptionId',
  authenticateApiKey(['admin', 'billing']),
  async (req, res, next) => {
    try {
      const { subscriptionId } = req.params;

      const validation = UpdateSubscriptionSchema.safeParse(req.body);
      if (!validation.success) {
        throw new ValidationError('Invalid subscription update data', validation.error.issues);
      }

      const updateData = validation.data;
      const subscription = await paymentService.updateSubscription(subscriptionId, updateData);

      logger.info('Subscription updated', {
        subscriptionId,
        updateData,
        adminId: req.user?.id
      });

      res.json(subscription);

    } catch (error) {
      next(error);
    }
  }
);

/**
 * @route DELETE /api/v1/billing/subscriptions/:subscriptionId
 * @desc Cancel subscription
 * @access Private
 */
router.delete('/subscriptions/:subscriptionId',
  authenticateApiKey(['admin', 'billing']),
  async (req, res, next) => {
    try {
      const { subscriptionId } = req.params;
      const { immediate = false } = req.query;

      const subscription = await paymentService.cancelSubscription(
        subscriptionId,
        immediate === 'true'
      );

      // If immediate cancellation, suspend the license
      if (immediate === 'true') {
        // Find license by subscription metadata
        // This would require extending LicenseService to find by metadata
        logger.info('Immediate subscription cancellation - license should be suspended', {
          subscriptionId,
          adminId: req.user?.id
        });
      }

      logger.info('Subscription cancelled', {
        subscriptionId,
        immediate,
        adminId: req.user?.id
      });

      res.json({
        message: immediate === 'true' ? 'Subscription cancelled immediately' : 'Subscription will cancel at period end',
        subscription
      });

    } catch (error) {
      next(error);
    }
  }
);

/**
 * @route GET /api/v1/billing/customers/:customerId/subscriptions
 * @desc Get customer's subscriptions
 * @access Private
 */
router.get('/customers/:customerId/subscriptions',
  authenticateApiKey(['admin', 'billing', 'organization']),
  async (req, res, next) => {
    try {
      const { customerId } = req.params;

      const customer = await paymentService.getCustomer(customerId);
      if (!customer) {
        throw new NotFoundError('Customer not found');
      }

      // Check access permissions
      if (req.user?.role !== 'admin' &&
          req.user?.role !== 'billing' &&
          req.user?.organizationId !== customer.organizationId) {
        return res.status(403).json({
          error: 'Forbidden',
          message: 'Access denied'
        });
      }

      const subscriptions = await paymentService.getCustomerSubscriptions(customerId);

      res.json({
        customerId,
        subscriptions
      });

    } catch (error) {
      next(error);
    }
  }
);

/**
 * @route GET /api/v1/billing/customers/:customerId/invoices
 * @desc Get customer's billing history
 * @access Private
 */
router.get('/customers/:customerId/invoices',
  authenticateApiKey(['admin', 'billing', 'organization']),
  async (req, res, next) => {
    try {
      const { customerId } = req.params;
      const { limit = 20, offset = 0 } = req.query;

      const customer = await paymentService.getCustomer(customerId);
      if (!customer) {
        throw new NotFoundError('Customer not found');
      }

      // Check access permissions
      if (req.user?.role !== 'admin' &&
          req.user?.role !== 'billing' &&
          req.user?.organizationId !== customer.organizationId) {
        return res.status(403).json({
          error: 'Forbidden',
          message: 'Access denied'
        });
      }

      const invoices = await paymentService.getCustomerInvoices(
        customerId,
        parseInt(limit as string),
        parseInt(offset as string)
      );

      res.json({
        customerId,
        invoices,
        pagination: {
          limit: parseInt(limit as string),
          offset: parseInt(offset as string),
          total: invoices.length
        }
      });

    } catch (error) {
      next(error);
    }
  }
);

/**
 * @route POST /api/v1/billing/webhooks/:gateway
 * @desc Handle payment gateway webhooks
 * @access Public (but verified)
 */
router.post('/webhooks/:gateway',
  async (req, res, next) => {
    try {
      const { gateway } = req.params;
      const signature = req.get('stripe-signature') ||
                       req.get('conekta-signature') ||
                       req.get('x-webhook-signature');

      if (!['stripe', 'conekta', 'fungies'].includes(gateway)) {
        return res.status(400).json({
          error: 'Invalid gateway'
        });
      }

      const result = await paymentService.handleWebhook(
        gateway as 'stripe' | 'conekta' | 'fungies',
        req.body,
        signature || ''
      );

      logger.info('Webhook processed', {
        gateway,
        eventType: result.eventType,
        processed: result.processed
      });

      res.json({ received: true, processed: result.processed });

    } catch (error) {
      logger.error('Webhook processing failed', { error, gateway: req.params.gateway });
      next(error);
    }
  }
);

export default router;