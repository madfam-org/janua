/**
 * Polar.sh Payment Provider for Janua
 *
 * Merchant of Record (MoR) payment provider that handles global payments,
 * tax compliance, and subscription management through Polar's developer-first platform.
 *
 * Key Features:
 * - Global payment processing with automatic tax handling (VAT, GST, sales tax)
 * - Subscription and usage-based billing
 * - Customer portal for self-service management
 * - Webhook-driven event processing
 * - Developer-first API design
 *
 * @see https://docs.polar.sh
 */

import { EventEmitter } from 'events';
import { Redis } from 'ioredis';
import crypto from 'crypto';
import {
  PaymentProvider,
  PaymentIntent,
  PaymentMethod,
  Customer,
  CheckoutSession,
  Currency,
  PaymentStatus,
  PaymentProviderInterface,
  LineItem,
  RefundRequest,
  ComplianceCheck
} from '../../types/payment.types';
import { Subscription, SubscriptionStatus } from '../../types/payment.types';
import { createLogger } from '../../utils/logger';

const logger = createLogger('PolarProvider');

// ============================================================================
// Polar Configuration
// ============================================================================

export interface PolarConfig {
  /** Polar API access token (server-side) */
  accessToken: string;
  /** Polar organization ID */
  organizationId?: string;
  /** Webhook secret for signature verification */
  webhookSecret: string;
  /** Use sandbox environment for testing */
  sandbox?: boolean;
  /** Auto-create customers on first interaction */
  autoCreateCustomers?: boolean;
}

// ============================================================================
// Polar API Types
// ============================================================================

/** Polar customer object */
interface PolarCustomer {
  id: string;
  email: string;
  name?: string;
  billing_address?: PolarAddress;
  tax_id?: string[];
  organization_id?: string;
  metadata: Record<string, string>;
  created_at: string;
  modified_at?: string;
}

/** Polar address object */
interface PolarAddress {
  line1?: string;
  line2?: string;
  city?: string;
  state?: string;
  postal_code?: string;
  country: string; // ISO 3166-1 alpha-2
}

/** Polar product object */
interface PolarProduct {
  id: string;
  name: string;
  description?: string;
  is_recurring: boolean;
  is_archived: boolean;
  organization_id: string;
  prices: PolarPrice[];
  benefits: PolarBenefit[];
  medias: any[];
  created_at: string;
  modified_at?: string;
}

/** Polar price object */
interface PolarPrice {
  id: string;
  type: 'one_time' | 'recurring';
  amount_type: 'fixed' | 'custom' | 'free';
  price_amount?: number;
  price_currency: string;
  recurring_interval?: 'month' | 'year';
  created_at: string;
}

/** Polar benefit object */
interface PolarBenefit {
  id: string;
  type: string;
  description: string;
  is_selectable: boolean;
  is_deletable: boolean;
  organization_id: string;
  created_at: string;
}

/** Polar checkout session object */
interface PolarCheckout {
  id: string;
  url: string;
  status: 'open' | 'expired' | 'confirmed' | 'succeeded';
  client_secret: string;
  product_id: string;
  product_price_id?: string;
  customer_id?: string;
  customer_email?: string;
  success_url: string;
  embed_origin?: string;
  amount?: number;
  tax_amount?: number;
  currency?: string;
  total_amount?: number;
  metadata: Record<string, string>;
  expires_at: string;
  created_at: string;
}

/** Polar subscription object */
interface PolarSubscription {
  id: string;
  status: 'incomplete' | 'incomplete_expired' | 'trialing' | 'active' | 'past_due' | 'canceled' | 'unpaid';
  current_period_start: string;
  current_period_end: string;
  cancel_at_period_end: boolean;
  canceled_at?: string;
  ended_at?: string;
  customer_id: string;
  product_id: string;
  price_id: string;
  user_id?: string;
  organization_id?: string;
  metadata: Record<string, string>;
  created_at: string;
  modified_at?: string;
}

/** Polar order object (one-time purchase) */
interface PolarOrder {
  id: string;
  amount: number;
  tax_amount: number;
  currency: string;
  customer_id: string;
  product_id: string;
  product_price_id: string;
  subscription_id?: string;
  billing_reason?: string;
  billing_address?: PolarAddress;
  metadata: Record<string, string>;
  created_at: string;
}

/** Polar webhook event */
interface PolarWebhookEvent {
  type: string;
  data: Record<string, any>;
}

// ============================================================================
// Polar Provider Implementation
// ============================================================================

export class PolarProvider extends EventEmitter implements PaymentProviderInterface {
  public readonly id = 'polar';
  public readonly name: PaymentProvider = 'polar' as PaymentProvider;

  /**
   * Polar acts as Merchant of Record, supporting most countries globally
   * Excludes sanctioned countries per OFAC regulations
   */
  public readonly supportedCountries = [
    // North America
    'US', 'CA', 'MX',
    // Europe
    'GB', 'IE', 'FR', 'DE', 'IT', 'ES', 'NL', 'BE', 'AT', 'CH', 'DK', 'FI',
    'NO', 'SE', 'PL', 'PT', 'GR', 'CZ', 'HU', 'RO', 'BG', 'HR', 'EE', 'LV',
    'LT', 'LU', 'MT', 'SK', 'SI', 'CY', 'IS',
    // Asia Pacific
    'AU', 'NZ', 'JP', 'SG', 'HK', 'MY', 'TH', 'PH', 'ID', 'IN', 'KR', 'TW',
    // Middle East & Africa
    'AE', 'SA', 'IL', 'ZA', 'NG', 'KE', 'GH', 'EG',
    // Latin America
    'BR', 'AR', 'CL', 'CO', 'PE', 'UY'
  ];

  /**
   * Polar supports major global currencies
   */
  public readonly supportedCurrencies: Currency[] = [
    'USD', 'EUR', 'GBP', 'CAD', 'AUD', 'JPY', 'CHF', 'SEK', 'NOK', 'DKK',
    'PLN', 'CZK', 'HUF', 'RON', 'BGN', 'SGD', 'HKD', 'NZD', 'INR', 'BRL',
    'MXN', 'ZAR', 'AED', 'SAR', 'ILS', 'KRW', 'TWD'
  ];

  /** Sanctioned countries where Polar cannot operate */
  private readonly sanctionedCountries = ['CU', 'IR', 'KP', 'SY', 'RU', 'BY'];

  private config: PolarConfig;
  private redis: Redis;
  private apiUrl: string;

  constructor(config: PolarConfig, redis: Redis) {
    super();
    this.config = config;
    this.redis = redis;
    this.apiUrl = config.sandbox
      ? 'https://sandbox-api.polar.sh'
      : 'https://api.polar.sh';
  }

  // ==========================================================================
  // Initialization
  // ==========================================================================

  /**
   * Initialize Polar provider and verify API credentials
   */
  async initialize(): Promise<void> {
    try {
      // Verify access token by fetching organization details
      const response = await this.apiRequest('GET', '/v1/organizations');

      if (!response.items || response.items.length === 0) {
        throw new Error('No organizations found for Polar access token');
      }

      const org = response.items[0];

      // Cache organization info
      await this.redis.setex(
        `polar:organization:${org.id}`,
        3600,
        JSON.stringify({
          id: org.id,
          name: org.name,
          slug: org.slug,
          avatar_url: org.avatar_url
        })
      );

      logger.info('Polar provider initialized', { organizationId: org.id });
      this.emit('initialized', { provider: 'polar', organizationId: org.id });
    } catch (error) {
      logger.error('Failed to initialize Polar provider', { error });
      this.emit('initialization_failed', { provider: 'polar', error });
      throw error;
    }
  }

  // ==========================================================================
  // Customer Management
  // ==========================================================================

  /**
   * Create a new Polar customer
   */
  async createCustomer(customer: Partial<Customer>): Promise<string> {
    const polarCustomer = await this.apiRequest<PolarCustomer>('POST', '/v1/customers', {
      email: customer.email,
      name: customer.name,
      billing_address: customer.address ? {
        line1: customer.address.line1,
        line2: customer.address.line2,
        city: customer.address.city,
        state: customer.address.state,
        postal_code: customer.address.postal_code,
        country: customer.address.country
      } : undefined,
      metadata: customer.metadata || {}
    });

    // Cache customer data
    await this.redis.setex(
      `polar:customer:${polarCustomer.id}`,
      86400,
      JSON.stringify(polarCustomer)
    );

    logger.info('Polar customer created', { customerId: polarCustomer.id });
    return polarCustomer.id;
  }

  /**
   * Update an existing Polar customer
   */
  async updateCustomer(customerId: string, updates: Partial<Customer>): Promise<void> {
    await this.apiRequest('PATCH', `/v1/customers/${customerId}`, {
      email: updates.email,
      name: updates.name,
      billing_address: updates.address ? {
        line1: updates.address.line1,
        line2: updates.address.line2,
        city: updates.address.city,
        state: updates.address.state,
        postal_code: updates.address.postal_code,
        country: updates.address.country
      } : undefined,
      metadata: updates.metadata
    });

    // Invalidate cache
    await this.redis.del(`polar:customer:${customerId}`);
    logger.info('Polar customer updated', { customerId });
  }

  /**
   * Delete a Polar customer
   */
  async deleteCustomer(customerId: string): Promise<void> {
    await this.apiRequest('DELETE', `/v1/customers/${customerId}`);
    await this.redis.del(`polar:customer:${customerId}`);
    logger.info('Polar customer deleted', { customerId });
  }

  /**
   * Get Polar customer by ID
   */
  async getCustomer(customerId: string): Promise<PolarCustomer | null> {
    // Check cache first
    const cached = await this.redis.get(`polar:customer:${customerId}`);
    if (cached) {
      return JSON.parse(cached);
    }

    try {
      const customer = await this.apiRequest<PolarCustomer>('GET', `/v1/customers/${customerId}`);
      await this.redis.setex(`polar:customer:${customerId}`, 86400, JSON.stringify(customer));
      return customer;
    } catch (error: any) {
      if (error.status === 404) return null;
      throw error;
    }
  }

  /**
   * Find customer by email
   */
  async findCustomerByEmail(email: string): Promise<PolarCustomer | null> {
    const response = await this.apiRequest<{ items: PolarCustomer[] }>(
      'GET',
      `/v1/customers?email=${encodeURIComponent(email)}`
    );
    return response.items.length > 0 ? response.items[0] : null;
  }

  // ==========================================================================
  // Payment Methods (Polar handles payment methods internally)
  // ==========================================================================

  /**
   * Polar manages payment methods through checkout flow
   * This is a no-op for Polar as they handle payment methods internally
   */
  async attachPaymentMethod(_customerId: string, _paymentMethodId: string): Promise<void> {
    // Polar manages payment methods internally through checkout
    logger.debug('Payment method attachment handled by Polar checkout flow');
  }

  async detachPaymentMethod(_paymentMethodId: string): Promise<void> {
    // Polar manages payment methods internally
    logger.debug('Payment method detachment handled by Polar customer portal');
  }

  async listPaymentMethods(_customerId: string): Promise<PaymentMethod[]> {
    // Polar doesn't expose payment methods directly
    // Customers manage them through the customer portal
    return [];
  }

  // ==========================================================================
  // Checkout Sessions
  // ==========================================================================

  /**
   * Create a Polar checkout session for product purchase
   */
  async createCheckoutSession(params: {
    customer_id?: string;
    customer_email?: string;
    product_id: string;
    price_id?: string;
    success_url: string;
    cancel_url?: string;
    embed_origin?: string;
    metadata?: Record<string, any>;
  }): Promise<CheckoutSession> {
    const polarCheckout = await this.apiRequest<PolarCheckout>('POST', '/v1/checkouts', {
      product_id: params.product_id,
      product_price_id: params.price_id,
      customer_id: params.customer_id,
      customer_email: params.customer_email,
      success_url: params.success_url,
      embed_origin: params.embed_origin,
      metadata: params.metadata || {}
    });

    const session: CheckoutSession = {
      id: polarCheckout.id,
      provider: 'polar' as PaymentProvider,
      provider_session_id: polarCheckout.id,
      amount: (polarCheckout.amount || 0) / 100,
      currency: (polarCheckout.currency || 'USD').toUpperCase() as Currency,
      customer_id: polarCheckout.customer_id || '',
      success_url: params.success_url,
      cancel_url: params.cancel_url || '',
      line_items: [],
      status: polarCheckout.status === 'succeeded' ? 'complete' :
              polarCheckout.status === 'expired' ? 'expired' : 'open',
      expires_at: new Date(polarCheckout.expires_at),
      url: polarCheckout.url,
      metadata: polarCheckout.metadata,
      created_at: new Date(polarCheckout.created_at)
    };

    // Cache session
    await this.redis.setex(
      `polar:checkout:${session.id}`,
      3600,
      JSON.stringify(session)
    );

    logger.info('Polar checkout session created', {
      checkoutId: session.id,
      productId: params.product_id
    });

    return session;
  }

  /**
   * Get checkout session by ID
   */
  async getCheckoutSession(checkoutId: string): Promise<CheckoutSession | null> {
    try {
      const polarCheckout = await this.apiRequest<PolarCheckout>(
        'GET',
        `/v1/checkouts/${checkoutId}`
      );

      return {
        id: polarCheckout.id,
        provider: 'polar' as PaymentProvider,
        provider_session_id: polarCheckout.id,
        amount: (polarCheckout.amount || 0) / 100,
        currency: (polarCheckout.currency || 'USD').toUpperCase() as Currency,
        customer_id: polarCheckout.customer_id || '',
        success_url: polarCheckout.success_url,
        cancel_url: '',
        line_items: [],
        status: polarCheckout.status === 'succeeded' ? 'complete' :
                polarCheckout.status === 'expired' ? 'expired' : 'open',
        expires_at: new Date(polarCheckout.expires_at),
        url: polarCheckout.url,
        metadata: polarCheckout.metadata,
        created_at: new Date(polarCheckout.created_at)
      };
    } catch (error: any) {
      if (error.status === 404) return null;
      throw error;
    }
  }

  // ==========================================================================
  // Payment Intents (Polar uses checkout flow primarily)
  // ==========================================================================

  /**
   * Create payment intent - Polar uses checkout sessions primarily
   * This creates a checkout session and returns it as a payment intent
   */
  async createPaymentIntent(params: {
    amount: number;
    currency: Currency;
    customer_id?: string;
    payment_method_id?: string;
    description?: string;
    metadata?: Record<string, any>;
  }): Promise<PaymentIntent> {
    // For Polar, we need a product to create a checkout
    // This is a simplified implementation - in production, you'd map to real products
    const intent: PaymentIntent = {
      id: `polar_intent_${Date.now()}`,
      provider: 'polar' as PaymentProvider,
      amount: params.amount,
      currency: params.currency,
      status: 'pending',
      customer_id: params.customer_id || '',
      organization_id: params.metadata?.organization_id || '',
      description: params.description,
      metadata: params.metadata,
      created_at: new Date(),
      updated_at: new Date()
    };

    logger.info('Polar payment intent created (use checkout for actual payments)', {
      intentId: intent.id
    });

    return intent;
  }

  async confirmPayment(intentId: string): Promise<PaymentIntent> {
    // Polar handles payment confirmation through checkout flow
    const cached = await this.redis.get(`polar:intent:${intentId}`);
    if (!cached) {
      throw new Error(`Payment intent ${intentId} not found`);
    }

    const intent = JSON.parse(cached) as PaymentIntent;
    intent.status = 'succeeded';
    intent.updated_at = new Date();

    return intent;
  }

  async cancelPayment(intentId: string): Promise<PaymentIntent> {
    const cached = await this.redis.get(`polar:intent:${intentId}`);
    if (!cached) {
      throw new Error(`Payment intent ${intentId} not found`);
    }

    const intent = JSON.parse(cached) as PaymentIntent;
    intent.status = 'canceled';
    intent.updated_at = new Date();

    return intent;
  }

  // ==========================================================================
  // Subscriptions
  // ==========================================================================

  /**
   * Create a subscription (typically done through checkout)
   */
  async createSubscription(params: {
    customer_id: string;
    product_id: string;
    price_id?: string;
    metadata?: Record<string, any>;
  }): Promise<Subscription> {
    // Subscriptions are typically created through checkout flow
    // This is for direct API subscription creation
    const polarSub = await this.apiRequest<PolarSubscription>('POST', '/v1/subscriptions', {
      customer_id: params.customer_id,
      product_id: params.product_id,
      price_id: params.price_id,
      metadata: params.metadata || {}
    });

    return this.mapPolarSubscription(polarSub);
  }

  /**
   * Get subscription by ID
   */
  async getSubscription(subscriptionId: string): Promise<Subscription | null> {
    try {
      const polarSub = await this.apiRequest<PolarSubscription>(
        'GET',
        `/v1/subscriptions/${subscriptionId}`
      );
      return this.mapPolarSubscription(polarSub);
    } catch (error: any) {
      if (error.status === 404) return null;
      throw error;
    }
  }

  /**
   * List subscriptions for a customer
   */
  async listSubscriptions(customerId: string): Promise<Subscription[]> {
    const response = await this.apiRequest<{ items: PolarSubscription[] }>(
      'GET',
      `/v1/subscriptions?customer_id=${customerId}`
    );
    return response.items.map(sub => this.mapPolarSubscription(sub));
  }

  /**
   * Cancel a subscription
   */
  async cancelSubscription(
    subscriptionId: string,
    cancelAtPeriodEnd: boolean = true
  ): Promise<Subscription> {
    const endpoint = cancelAtPeriodEnd
      ? `/v1/subscriptions/${subscriptionId}`
      : `/v1/subscriptions/${subscriptionId}/cancel`;

    const polarSub = await this.apiRequest<PolarSubscription>(
      cancelAtPeriodEnd ? 'PATCH' : 'POST',
      endpoint,
      cancelAtPeriodEnd ? { cancel_at_period_end: true } : {}
    );

    logger.info('Polar subscription canceled', {
      subscriptionId,
      cancelAtPeriodEnd
    });

    return this.mapPolarSubscription(polarSub);
  }

  /**
   * Resume a canceled subscription (before period end)
   */
  async resumeSubscription(subscriptionId: string): Promise<Subscription> {
    const polarSub = await this.apiRequest<PolarSubscription>(
      'PATCH',
      `/v1/subscriptions/${subscriptionId}`,
      { cancel_at_period_end: false }
    );

    logger.info('Polar subscription resumed', { subscriptionId });
    return this.mapPolarSubscription(polarSub);
  }

  // ==========================================================================
  // Customer Portal
  // ==========================================================================

  /**
   * Create a customer portal session URL
   */
  async createCustomerPortalSession(customerId: string): Promise<string> {
    const response = await this.apiRequest<{ url: string }>(
      'POST',
      `/v1/customers/${customerId}/portal`
    );
    return response.url;
  }

  /**
   * Get customer portal data (subscriptions, benefits, orders)
   */
  async getCustomerPortalData(customerId: string): Promise<{
    subscriptions: Subscription[];
    benefits: PolarBenefit[];
    orders: PolarOrder[];
  }> {
    const [subscriptions, benefits, orders] = await Promise.all([
      this.listSubscriptions(customerId),
      this.getCustomerBenefits(customerId),
      this.getCustomerOrders(customerId)
    ]);

    return { subscriptions, benefits, orders };
  }

  /**
   * Get customer benefits
   */
  private async getCustomerBenefits(customerId: string): Promise<PolarBenefit[]> {
    const response = await this.apiRequest<{ items: PolarBenefit[] }>(
      'GET',
      `/v1/customers/${customerId}/benefits`
    );
    return response.items;
  }

  /**
   * Get customer orders (one-time purchases)
   */
  private async getCustomerOrders(customerId: string): Promise<PolarOrder[]> {
    const response = await this.apiRequest<{ items: PolarOrder[] }>(
      'GET',
      `/v1/orders?customer_id=${customerId}`
    );
    return response.items;
  }

  // ==========================================================================
  // Usage-Based Billing
  // ==========================================================================

  /**
   * Ingest usage event for metered billing
   */
  async ingestUsageEvent(params: {
    customer_id: string;
    event_name: string;
    quantity?: number;
    properties?: Record<string, any>;
    timestamp?: Date;
  }): Promise<void> {
    await this.apiRequest('POST', '/v1/usage', {
      customer_id: params.customer_id,
      event_name: params.event_name,
      quantity: params.quantity || 1,
      properties: params.properties || {},
      timestamp: (params.timestamp || new Date()).toISOString()
    });

    logger.info('Polar usage event ingested', {
      customerId: params.customer_id,
      eventName: params.event_name,
      quantity: params.quantity || 1
    });
  }

  /**
   * Get usage summary for a customer
   */
  async getUsageSummary(
    customerId: string,
    startDate?: Date,
    endDate?: Date
  ): Promise<{ event_name: string; total_quantity: number }[]> {
    const params = new URLSearchParams({ customer_id: customerId });
    if (startDate) params.append('start_date', startDate.toISOString());
    if (endDate) params.append('end_date', endDate.toISOString());

    const response = await this.apiRequest<{
      items: { event_name: string; total_quantity: number }[]
    }>('GET', `/v1/usage/summary?${params.toString()}`);

    return response.items;
  }

  // ==========================================================================
  // Products & Prices
  // ==========================================================================

  /**
   * List products available for purchase
   */
  async listProducts(): Promise<PolarProduct[]> {
    const response = await this.apiRequest<{ items: PolarProduct[] }>(
      'GET',
      '/v1/products'
    );
    return response.items;
  }

  /**
   * Get product by ID
   */
  async getProduct(productId: string): Promise<PolarProduct | null> {
    try {
      return await this.apiRequest<PolarProduct>('GET', `/v1/products/${productId}`);
    } catch (error: any) {
      if (error.status === 404) return null;
      throw error;
    }
  }

  // ==========================================================================
  // Refunds
  // ==========================================================================

  /**
   * Create a refund for an order
   */
  async createRefund(request: RefundRequest): Promise<{ id: string; status: string }> {
    const response = await this.apiRequest<{ id: string; status: string }>(
      'POST',
      '/v1/refunds',
      {
        order_id: request.payment_intent_id,
        amount: request.amount ? Math.round(request.amount * 100) : undefined,
        reason: request.reason,
        metadata: request.metadata
      }
    );

    logger.info('Polar refund created', {
      refundId: response.id,
      orderId: request.payment_intent_id
    });

    return response;
  }

  // ==========================================================================
  // Webhooks
  // ==========================================================================

  /**
   * Validate webhook signature
   */
  validateWebhookSignature(payload: string, signature: string): boolean {
    if (!this.config.webhookSecret) {
      logger.warn('Webhook secret not configured');
      return false;
    }

    const expectedSignature = crypto
      .createHmac('sha256', this.config.webhookSecret)
      .update(payload)
      .digest('hex');

    return crypto.timingSafeEqual(
      Buffer.from(signature),
      Buffer.from(`sha256=${expectedSignature}`)
    );
  }

  /**
   * Process webhook event
   */
  async processWebhookEvent(event: PolarWebhookEvent): Promise<void> {
    logger.info('Processing Polar webhook', { type: event.type });

    switch (event.type) {
      // Checkout events
      case 'checkout.created':
        this.emit('checkout.created', event.data);
        break;
      case 'checkout.updated':
        this.emit('checkout.updated', event.data);
        break;

      // Subscription events
      case 'subscription.created':
        this.emit('subscription.created', event.data);
        break;
      case 'subscription.updated':
        this.emit('subscription.updated', event.data);
        break;
      case 'subscription.active':
        this.emit('subscription.active', event.data);
        break;
      case 'subscription.canceled':
        this.emit('subscription.canceled', event.data);
        break;
      case 'subscription.revoked':
        this.emit('subscription.revoked', event.data);
        break;

      // Order events (one-time purchases)
      case 'order.created':
        this.emit('order.created', event.data);
        break;

      // Benefit events
      case 'benefit.granted':
        this.emit('benefit.granted', event.data);
        break;
      case 'benefit.revoked':
        this.emit('benefit.revoked', event.data);
        break;

      // Customer events
      case 'customer.created':
        this.emit('customer.created', event.data);
        break;
      case 'customer.updated':
        this.emit('customer.updated', event.data);
        break;

      default:
        logger.debug('Unhandled Polar webhook event', { type: event.type });
    }
  }

  // ==========================================================================
  // Utilities
  // ==========================================================================

  /**
   * Check if provider is available for country/currency
   */
  isAvailable(country: string, currency: Currency): boolean {
    // Check if country is sanctioned
    if (this.sanctionedCountries.includes(country)) {
      return false;
    }

    // Check country support
    if (!this.supportedCountries.includes(country)) {
      return false;
    }

    // Check currency support
    if (!this.supportedCurrencies.includes(currency)) {
      return false;
    }

    return true;
  }

  /**
   * Get supported payment methods for a country
   */
  getSupportedPaymentMethods(country: string): string[] {
    // Polar handles payment methods automatically based on country
    // This returns the common methods available
    const methods = ['card'];

    // Add region-specific methods
    if (['US', 'CA'].includes(country)) {
      methods.push('apple_pay', 'google_pay');
    }
    if (['DE', 'AT', 'NL', 'BE'].includes(country)) {
      methods.push('sepa', 'giropay', 'sofort');
    }
    if (country === 'NL') {
      methods.push('ideal');
    }
    if (country === 'PL') {
      methods.push('przelewy24');
    }

    return methods;
  }

  /**
   * Get compliance requirements for a transaction
   */
  getComplianceRequirements(check: ComplianceCheck): string[] {
    const requirements: string[] = [];

    // Polar handles most compliance as MoR, but we note requirements
    if (['EU'].some(region => this.isEUCountry(check.country))) {
      requirements.push('vat_collection');
      requirements.push('gdpr_consent');
    }

    if (check.customer_type === 'business') {
      requirements.push('tax_id_verification');
    }

    if (check.amount > 10000) {
      requirements.push('enhanced_due_diligence');
    }

    return requirements;
  }

  // ==========================================================================
  // Private Helpers
  // ==========================================================================

  /**
   * Make API request to Polar
   */
  private async apiRequest<T>(
    method: 'GET' | 'POST' | 'PATCH' | 'DELETE',
    endpoint: string,
    body?: Record<string, any>
  ): Promise<T> {
    const url = `${this.apiUrl}${endpoint}`;

    const options: RequestInit = {
      method,
      headers: {
        'Authorization': `Bearer ${this.config.accessToken}`,
        'Content-Type': 'application/json',
        'Accept': 'application/json'
      }
    };

    if (body && method !== 'GET') {
      options.body = JSON.stringify(body);
    }

    const response = await fetch(url, options);

    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      const err = new Error(error.detail || `Polar API error: ${response.status}`);
      (err as any).status = response.status;
      (err as any).response = error;
      throw err;
    }

    // Handle 204 No Content
    if (response.status === 204) {
      return {} as T;
    }

    return response.json();
  }

  /**
   * Map Polar subscription to internal format
   */
  private mapPolarSubscription(polarSub: PolarSubscription): Subscription {
    return {
      id: polarSub.id,
      customer_id: polarSub.customer_id,
      status: this.mapSubscriptionStatus(polarSub.status),
      plan_id: polarSub.product_id,
      current_period_start: new Date(polarSub.current_period_start),
      current_period_end: new Date(polarSub.current_period_end),
      cancel_at_period_end: polarSub.cancel_at_period_end,
      canceled_at: polarSub.canceled_at ? new Date(polarSub.canceled_at) : undefined,
      provider: 'polar' as PaymentProvider,
      metadata: polarSub.metadata
    };
  }

  /**
   * Map Polar subscription status to internal status
   */
  private mapSubscriptionStatus(status: PolarSubscription['status']): SubscriptionStatus {
    const statusMap: Record<PolarSubscription['status'], SubscriptionStatus> = {
      'incomplete': 'pending',
      'incomplete_expired': 'inactive',
      'trialing': 'trialing',
      'active': 'active',
      'past_due': 'past_due',
      'canceled': 'canceled',
      'unpaid': 'past_due'
    };
    return statusMap[status] || 'inactive';
  }

  /**
   * Map payment status
   */
  private mapPaymentStatus(status: string): PaymentStatus {
    const statusMap: Record<string, PaymentStatus> = {
      'pending': 'pending',
      'processing': 'processing',
      'succeeded': 'succeeded',
      'failed': 'failed',
      'canceled': 'canceled',
      'refunded': 'refunded'
    };
    return statusMap[status] || 'pending';
  }

  /**
   * Check if country is in EU
   */
  private isEUCountry(country: string): boolean {
    const euCountries = [
      'AT', 'BE', 'BG', 'HR', 'CY', 'CZ', 'DK', 'EE', 'FI', 'FR',
      'DE', 'GR', 'HU', 'IE', 'IT', 'LV', 'LT', 'LU', 'MT', 'NL',
      'PL', 'PT', 'RO', 'SK', 'SI', 'ES', 'SE'
    ];
    return euCountries.includes(country);
  }
}

// ============================================================================
// Factory Function
// ============================================================================

/**
 * Create a new Polar provider instance
 */
export function createPolarProvider(config: PolarConfig, redis: Redis): PolarProvider {
  return new PolarProvider(config, redis);
}

export default PolarProvider;
