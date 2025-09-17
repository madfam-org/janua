/**
 * Customer billing portal service
 * Provides customer-facing billing management functionality
 */

import { PrismaClient } from '@prisma/client';
import jwt from 'jsonwebtoken';
import { PaymentGatewayService } from './PaymentGatewayService';
import { LicenseService } from './LicenseService';
import { RedisService } from './RedisService';
import { logger } from '../utils/logger';
import { NotFoundError, ValidationError, UnauthorizedError } from '../utils/errors';

interface BillingPortalSession {
  id: string;
  customerId: string;
  organizationId: string;
  expiresAt: Date;
  returnUrl?: string;
}

interface CustomerBillingInfo {
  customer: {
    id: string;
    email: string;
    name: string;
    organizationId: string;
    country: string;
    paymentGateway: string;
    status: string;
  };
  subscription?: {
    id: string;
    plan: string;
    status: string;
    currentPeriodStart: Date;
    currentPeriodEnd: Date;
    cancelAtPeriodEnd: boolean;
    billingCycle: string;
    amount: number;
    currency: string;
  };
  license?: {
    id: string;
    maskedKey: string;
    plan: string;
    features: string[];
    status: string;
    expiresAt?: Date;
    currentUsage: Record<string, number>;
    limits: Record<string, number>;
  };
  invoices: Array<{
    id: string;
    amount: number;
    currency: string;
    status: string;
    date: Date;
    downloadUrl?: string;
  }>;
  paymentMethods: Array<{
    id: string;
    type: string;
    last4?: string;
    brand?: string;
    expiryMonth?: number;
    expiryYear?: number;
    isDefault: boolean;
  }>;
}

export class BillingPortalService {
  private prisma: PrismaClient;
  private paymentService: PaymentGatewayService;
  private licenseService: LicenseService;
  private redis: RedisService;
  private jwtSecret: string;

  constructor() {
    this.prisma = new PrismaClient();
    this.paymentService = new PaymentGatewayService();
    this.licenseService = new LicenseService();
    this.redis = new RedisService();
    this.jwtSecret = process.env.JWT_SECRET || 'plinto-billing-portal-secret';
  }

  /**
   * Create a secure billing portal session
   */
  async createPortalSession(data: {
    customerId: string;
    organizationId: string;
    returnUrl?: string;
    expiresInMinutes?: number;
  }): Promise<{ sessionId: string; portalUrl: string }> {
    const sessionId = this.generateSessionId();
    const expiresAt = new Date();
    expiresAt.setMinutes(expiresAt.getMinutes() + (data.expiresInMinutes || 60));

    const session: BillingPortalSession = {
      id: sessionId,
      customerId: data.customerId,
      organizationId: data.organizationId,
      expiresAt,
      returnUrl: data.returnUrl
    };

    // Store session in Redis with expiration
    const sessionKey = `billing_portal:${sessionId}`;
    await this.redis.setex(
      sessionKey,
      (data.expiresInMinutes || 60) * 60,
      JSON.stringify(session)
    );

    // Generate JWT token for additional security
    const token = jwt.sign(
      {
        sessionId,
        customerId: data.customerId,
        organizationId: data.organizationId
      },
      this.jwtSecret,
      { expiresIn: `${data.expiresInMinutes || 60}m` }
    );

    const portalUrl = `${process.env.FRONTEND_URL}/billing?session=${sessionId}&token=${token}`;

    logger.info('Billing portal session created', {
      sessionId,
      customerId: data.customerId,
      organizationId: data.organizationId,
      expiresAt
    });

    return { sessionId, portalUrl };
  }

  /**
   * Validate and retrieve portal session
   */
  async validateSession(sessionId: string, token: string): Promise<BillingPortalSession> {
    try {
      // Verify JWT token
      const decoded = jwt.verify(token, this.jwtSecret) as any;

      if (decoded.sessionId !== sessionId) {
        throw new UnauthorizedError('Invalid session token');
      }

      // Get session from Redis
      const sessionKey = `billing_portal:${sessionId}`;
      const sessionData = await this.redis.get(sessionKey);

      if (!sessionData) {
        throw new UnauthorizedError('Session expired or not found');
      }

      const session: BillingPortalSession = JSON.parse(sessionData);

      if (new Date() > session.expiresAt) {
        await this.redis.del(sessionKey);
        throw new UnauthorizedError('Session expired');
      }

      return session;

    } catch (error) {
      if (error instanceof jwt.JsonWebTokenError) {
        throw new UnauthorizedError('Invalid session token');
      }
      throw error;
    }
  }

  /**
   * Get comprehensive billing information for customer
   */
  async getCustomerBillingInfo(sessionId: string, token: string): Promise<CustomerBillingInfo> {
    const session = await this.validateSession(sessionId, token);

    // Get customer information
    const customer = await this.paymentService.getCustomer(session.customerId);
    if (!customer) {
      throw new NotFoundError('Customer not found');
    }

    // Verify organization access
    if (customer.organizationId !== session.organizationId) {
      throw new UnauthorizedError('Access denied');
    }

    // Get active subscription
    const subscription = await this.paymentService.getActiveSubscription(session.customerId);

    // Get license information if subscription exists
    let license;
    if (subscription) {
      // Find license by organization ID (assuming one license per org)
      const licenses = await this.prisma.license.findMany({
        where: {
          organizationId: session.organizationId,
          status: 'active'
        },
        orderBy: { createdAt: 'desc' },
        take: 1
      });

      if (licenses.length > 0) {
        const licenseData = await this.licenseService.getLicenseById(licenses[0].id);
        if (licenseData) {
          license = {
            id: licenseData.id,
            maskedKey: licenseData.maskedKey,
            plan: licenseData.plan,
            features: licenseData.features,
            status: licenseData.status,
            expiresAt: licenseData.expiresAt,
            currentUsage: licenseData.currentUsage,
            limits: this.getLimitsForPlan(licenseData.plan as 'pro' | 'enterprise', licenseData.customLimits)
          };
        }
      }
    }

    // Get billing history
    const invoices = await this.paymentService.getCustomerInvoices(session.customerId, 10, 0);

    // Get payment methods
    const paymentMethods = await this.paymentService.getCustomerPaymentMethods(session.customerId);

    return {
      customer: {
        id: customer.id,
        email: customer.email,
        name: customer.name,
        organizationId: customer.organizationId,
        country: customer.country,
        paymentGateway: customer.paymentGateway,
        status: customer.status
      },
      subscription,
      license,
      invoices,
      paymentMethods
    };
  }

  /**
   * Update subscription plan
   */
  async updateSubscriptionPlan(
    sessionId: string,
    token: string,
    data: {
      plan: 'pro' | 'enterprise';
      billingCycle?: 'monthly' | 'yearly';
      seats?: number;
    }
  ) {
    const session = await this.validateSession(sessionId, token);

    const subscription = await this.paymentService.getActiveSubscription(session.customerId);
    if (!subscription) {
      throw new NotFoundError('No active subscription found');
    }

    const updatedSubscription = await this.paymentService.updateSubscription(subscription.id, {
      plan: data.plan,
      billingCycle: data.billingCycle,
      seats: data.seats
    });

    // Update license if it exists
    const licenses = await this.prisma.license.findMany({
      where: {
        organizationId: session.organizationId,
        status: 'active'
      }
    });

    if (licenses.length > 0) {
      await this.licenseService.updateLicense(licenses[0].id, {
        features: this.getFeaturesForPlan(data.plan),
        seats: data.seats
      });
    }

    logger.info('Subscription plan updated via portal', {
      sessionId,
      customerId: session.customerId,
      subscriptionId: subscription.id,
      newPlan: data.plan,
      billingCycle: data.billingCycle
    });

    return updatedSubscription;
  }

  /**
   * Cancel subscription
   */
  async cancelSubscription(
    sessionId: string,
    token: string,
    immediate: boolean = false
  ) {
    const session = await this.validateSession(sessionId, token);

    const subscription = await this.paymentService.getActiveSubscription(session.customerId);
    if (!subscription) {
      throw new NotFoundError('No active subscription found');
    }

    const cancelledSubscription = await this.paymentService.cancelSubscription(
      subscription.id,
      immediate
    );

    if (immediate) {
      // Immediately suspend license
      const licenses = await this.prisma.license.findMany({
        where: {
          organizationId: session.organizationId,
          status: 'active'
        }
      });

      for (const license of licenses) {
        await this.licenseService.suspendLicense(license.id, 'Subscription cancelled');
      }
    }

    logger.info('Subscription cancelled via portal', {
      sessionId,
      customerId: session.customerId,
      subscriptionId: subscription.id,
      immediate
    });

    return cancelledSubscription;
  }

  /**
   * Add payment method
   */
  async addPaymentMethod(
    sessionId: string,
    token: string,
    paymentMethodId: string
  ) {
    const session = await this.validateSession(sessionId, token);

    const paymentMethod = await this.paymentService.attachPaymentMethod(
      session.customerId,
      paymentMethodId
    );

    logger.info('Payment method added via portal', {
      sessionId,
      customerId: session.customerId,
      paymentMethodId
    });

    return paymentMethod;
  }

  /**
   * Remove payment method
   */
  async removePaymentMethod(
    sessionId: string,
    token: string,
    paymentMethodId: string
  ) {
    const session = await this.validateSession(sessionId, token);

    await this.paymentService.detachPaymentMethod(paymentMethodId);

    logger.info('Payment method removed via portal', {
      sessionId,
      customerId: session.customerId,
      paymentMethodId
    });
  }

  /**
   * Set default payment method
   */
  async setDefaultPaymentMethod(
    sessionId: string,
    token: string,
    paymentMethodId: string
  ) {
    const session = await this.validateSession(sessionId, token);

    await this.paymentService.setDefaultPaymentMethod(session.customerId, paymentMethodId);

    logger.info('Default payment method updated via portal', {
      sessionId,
      customerId: session.customerId,
      paymentMethodId
    });
  }

  /**
   * Download invoice
   */
  async downloadInvoice(
    sessionId: string,
    token: string,
    invoiceId: string
  ): Promise<{ url: string; expiresAt: Date }> {
    const session = await this.validateSession(sessionId, token);

    const invoice = await this.paymentService.getInvoice(invoiceId);
    if (!invoice || invoice.customerId !== session.customerId) {
      throw new NotFoundError('Invoice not found or access denied');
    }

    // Generate temporary download URL (expires in 1 hour)
    const downloadUrl = await this.paymentService.getInvoiceDownloadUrl(invoiceId);
    const expiresAt = new Date();
    expiresAt.setHours(expiresAt.getHours() + 1);

    logger.info('Invoice download requested via portal', {
      sessionId,
      customerId: session.customerId,
      invoiceId
    });

    return { url: downloadUrl, expiresAt };
  }

  // Private helper methods

  private generateSessionId(): string {
    return `billing_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  }

  private getFeaturesForPlan(plan: 'pro' | 'enterprise'): string[] {
    const features = {
      pro: [
        'basic_auth',
        'user_management',
        'mfa',
        'password_reset',
        'email_verification',
        'organizations',
        'webhooks',
        'api_keys',
        'custom_domains',
        'analytics',
        'priority_support'
      ],
      enterprise: [
        'basic_auth',
        'user_management',
        'mfa',
        'password_reset',
        'email_verification',
        'organizations',
        'webhooks',
        'api_keys',
        'custom_domains',
        'analytics',
        'priority_support',
        'sso_saml',
        'sso_oidc',
        'audit_logs',
        'custom_roles',
        'white_labeling',
        'compliance_reports',
        'dedicated_support'
      ]
    };

    return features[plan];
  }

  private getLimitsForPlan(plan: 'pro' | 'enterprise', customLimits?: Record<string, any>): Record<string, number> {
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
}