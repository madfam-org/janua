/**
 * Polar Plugin for Janua TypeScript SDK
 *
 * Provides Polar.sh Merchant of Record integration for global payments,
 * automatic tax compliance, and subscription management.
 *
 * Features:
 * - Checkout session creation with automatic tax handling
 * - Customer portal access for self-service subscription management
 * - Usage-based billing event ingestion
 * - Subscription lifecycle management
 * - Benefit/entitlement checking
 *
 * @example
 * ```typescript
 * import { JanuaClient } from '@janua/typescript-sdk';
 * import { createPolarPlugin } from '@janua/typescript-sdk/plugins/polar';
 *
 * const client = new JanuaClient({
 *   apiUrl: 'https://api.janua.dev',
 *   publishableKey: 'pk_...'
 * });
 *
 * // Install Polar plugin
 * const polar = createPolarPlugin({
 *   products: {
 *     pro: 'prod_xxxxx',
 *     enterprise: 'prod_yyyyy'
 *   },
 *   defaultSuccessUrl: '/dashboard?upgraded=true'
 * });
 * polar.install(client);
 *
 * // Create checkout
 * await client.polar.checkout({ plan: 'pro', organizationId: 'org_123' });
 * ```
 */

import type { JanuaClient } from '../client';

// ============================================================================
// Types
// ============================================================================

/**
 * Polar plugin configuration options
 */
export interface PolarPluginConfig {
  /**
   * Map of plan names to Polar product IDs
   * @example { pro: 'prod_xxxxx', enterprise: 'prod_yyyyy' }
   */
  products?: Record<string, string>;

  /**
   * Default URL to redirect after successful checkout
   */
  defaultSuccessUrl?: string;

  /**
   * Default URL to redirect if user cancels checkout
   */
  defaultCancelUrl?: string;

  /**
   * Enable embedded checkout (iframe) instead of redirect
   */
  enableEmbeddedCheckout?: boolean;

  /**
   * Callback when checkout starts
   */
  onCheckoutStart?: () => void;

  /**
   * Callback when checkout completes successfully
   */
  onCheckoutSuccess?: (subscription: PolarSubscription) => void;

  /**
   * Callback when checkout fails or is canceled
   */
  onCheckoutError?: (error: Error) => void;

  /**
   * Callback when subscription status changes
   */
  onSubscriptionChange?: (subscription: PolarSubscription) => void;
}

/**
 * Polar checkout creation options
 */
export interface PolarCheckoutOptions {
  /**
   * Plan name (maps to product ID via config) OR direct product ID
   */
  plan?: string;

  /**
   * Direct Polar product ID (alternative to plan)
   */
  productId?: string;

  /**
   * Polar price ID for specific pricing tier
   */
  priceId?: string;

  /**
   * Organization ID to associate subscription with
   */
  organizationId?: string;

  /**
   * Customer email (for guest checkout)
   */
  email?: string;

  /**
   * URL to redirect after successful checkout
   */
  successUrl?: string;

  /**
   * URL to redirect if user cancels
   */
  cancelUrl?: string;

  /**
   * Origin for embedded checkout iframe
   */
  embedOrigin?: string;

  /**
   * Additional metadata to attach to checkout
   */
  metadata?: Record<string, string>;
}

/**
 * Polar checkout session response
 */
export interface PolarCheckoutSession {
  /** Checkout session ID */
  id: string;
  /** Full checkout URL */
  url: string;
  /** Client secret for embedded checkout */
  clientSecret?: string;
  /** Session status */
  status: 'open' | 'expired' | 'confirmed' | 'succeeded';
  /** Expiration timestamp */
  expiresAt: string;
}

/**
 * Polar subscription object
 */
export interface PolarSubscription {
  /** Subscription ID */
  id: string;
  /** Subscription status */
  status: 'incomplete' | 'trialing' | 'active' | 'past_due' | 'canceled' | 'unpaid';
  /** Current billing period start */
  currentPeriodStart: string;
  /** Current billing period end */
  currentPeriodEnd: string;
  /** Whether subscription will cancel at period end */
  cancelAtPeriodEnd: boolean;
  /** Cancellation timestamp if canceled */
  canceledAt?: string;
  /** Associated customer ID */
  customerId: string;
  /** Polar product ID */
  productId: string;
  /** Polar price ID */
  priceId: string;
  /** Plan name (resolved from product ID) */
  plan?: string;
  /** Additional metadata */
  metadata: Record<string, string>;
  /** Creation timestamp */
  createdAt: string;
}

/**
 * Polar customer object
 */
export interface PolarCustomer {
  /** Customer ID */
  id: string;
  /** Customer email */
  email: string;
  /** Customer name */
  name?: string;
  /** Billing address country */
  country?: string;
  /** Creation timestamp */
  createdAt: string;
}

/**
 * Polar customer portal data
 */
export interface PolarCustomerPortalData {
  /** Active subscriptions */
  subscriptions: PolarSubscription[];
  /** Granted benefits/entitlements */
  benefits: PolarBenefit[];
  /** Order history */
  orders: PolarOrder[];
}

/**
 * Polar benefit (entitlement)
 */
export interface PolarBenefit {
  /** Benefit ID */
  id: string;
  /** Benefit type */
  type: string;
  /** Benefit description */
  description: string;
  /** Whether benefit is currently active */
  isActive: boolean;
  /** Grant timestamp */
  grantedAt: string;
}

/**
 * Polar order (one-time purchase)
 */
export interface PolarOrder {
  /** Order ID */
  id: string;
  /** Order amount in cents */
  amount: number;
  /** Tax amount in cents */
  taxAmount: number;
  /** Currency code */
  currency: string;
  /** Product ID */
  productId: string;
  /** Order timestamp */
  createdAt: string;
}

/**
 * Usage event for metered billing
 */
export interface PolarUsageEvent {
  /** Event name (must match Polar usage meter) */
  eventName: string;
  /** Quantity to record (default: 1) */
  quantity?: number;
  /** Additional properties */
  properties?: Record<string, any>;
  /** Timestamp (default: now) */
  timestamp?: Date;
}

// ============================================================================
// Polar Plugin Class
// ============================================================================

/**
 * Polar plugin for Janua SDK
 *
 * Provides Merchant of Record payment integration with automatic
 * tax compliance, subscription management, and customer self-service.
 */
export class PolarPlugin {
  private client!: JanuaClient;
  private config: PolarPluginConfig;
  private productIdToName: Map<string, string> = new Map();

  constructor(config: PolarPluginConfig = {}) {
    this.config = config;

    // Build reverse lookup for product ID to name
    if (config.products) {
      for (const [name, id] of Object.entries(config.products)) {
        this.productIdToName.set(id, name);
      }
    }
  }

  /**
   * Install plugin on Janua client
   */
  install(client: JanuaClient): void {
    this.client = client;
    // Attach plugin to client instance
    (client as any).polar = this;
  }

  // ==========================================================================
  // Checkout
  // ==========================================================================

  /**
   * Create a Polar checkout session
   *
   * @example
   * ```typescript
   * // Using plan name
   * const session = await client.polar.createCheckout({
   *   plan: 'pro',
   *   organizationId: 'org_123',
   *   successUrl: '/dashboard?upgraded=true'
   * });
   *
   * // Using direct product ID
   * const session = await client.polar.createCheckout({
   *   productId: 'prod_xxxxx',
   *   organizationId: 'org_123'
   * });
   * ```
   */
  async createCheckout(options: PolarCheckoutOptions): Promise<PolarCheckoutSession> {
    // Resolve product ID from plan name if needed
    let productId = options.productId;
    if (!productId && options.plan && this.config.products) {
      productId = this.config.products[options.plan];
      if (!productId) {
        throw new Error(`Unknown plan: ${options.plan}. Available plans: ${Object.keys(this.config.products).join(', ')}`);
      }
    }

    if (!productId) {
      throw new Error('Either plan or productId is required');
    }

    this.config.onCheckoutStart?.();

    try {
      const response = await this.client.post<{
        checkout_id: string;
        checkout_url: string;
        client_secret?: string;
        status: string;
        expires_at: string;
      }>('/api/v1/polar/checkout', {
        product_id: productId,
        price_id: options.priceId,
        organization_id: options.organizationId,
        customer_email: options.email,
        success_url: options.successUrl || this.config.defaultSuccessUrl || `${window.location.origin}/billing/success`,
        cancel_url: options.cancelUrl || this.config.defaultCancelUrl,
        embed_origin: options.embedOrigin,
        metadata: options.metadata
      });

      return {
        id: response.data.checkout_id,
        url: response.data.checkout_url,
        clientSecret: response.data.client_secret,
        status: response.data.status as PolarCheckoutSession['status'],
        expiresAt: response.data.expires_at
      };
    } catch (error) {
      this.config.onCheckoutError?.(error as Error);
      throw error;
    }
  }

  /**
   * Create checkout and redirect to Polar
   *
   * @example
   * ```typescript
   * await client.polar.checkout({ plan: 'pro', organizationId: 'org_123' });
   * // User is redirected to Polar checkout
   * ```
   */
  async checkout(options: PolarCheckoutOptions): Promise<void> {
    const session = await this.createCheckout(options);

    if (typeof window !== 'undefined') {
      window.location.href = session.url;
    } else {
      throw new Error('checkout() requires a browser environment. Use createCheckout() in server contexts.');
    }
  }

  /**
   * Get checkout session status
   */
  async getCheckoutSession(checkoutId: string): Promise<PolarCheckoutSession> {
    const response = await this.client.get<{
      id: string;
      url: string;
      client_secret?: string;
      status: string;
      expires_at: string;
    }>(`/api/v1/polar/checkout/${checkoutId}`);

    return {
      id: response.data.id,
      url: response.data.url,
      clientSecret: response.data.client_secret,
      status: response.data.status as PolarCheckoutSession['status'],
      expiresAt: response.data.expires_at
    };
  }

  // ==========================================================================
  // Subscriptions
  // ==========================================================================

  /**
   * Get subscription for organization
   *
   * @example
   * ```typescript
   * const subscription = await client.polar.getSubscription('org_123');
   * if (subscription?.status === 'active') {
   *   console.log('Pro features enabled!');
   * }
   * ```
   */
  async getSubscription(organizationId: string): Promise<PolarSubscription | null> {
    try {
      const response = await this.client.get<{
        id: string;
        status: string;
        current_period_start: string;
        current_period_end: string;
        cancel_at_period_end: boolean;
        canceled_at?: string;
        customer_id: string;
        product_id: string;
        price_id: string;
        metadata: Record<string, string>;
        created_at: string;
      }>(`/api/v1/polar/subscriptions/${organizationId}`);

      return this.mapSubscription(response.data);
    } catch (error: any) {
      if (error.status === 404) return null;
      throw error;
    }
  }

  /**
   * List all subscriptions for organization
   */
  async listSubscriptions(organizationId: string): Promise<PolarSubscription[]> {
    const response = await this.client.get<{
      items: Array<{
        id: string;
        status: string;
        current_period_start: string;
        current_period_end: string;
        cancel_at_period_end: boolean;
        canceled_at?: string;
        customer_id: string;
        product_id: string;
        price_id: string;
        metadata: Record<string, string>;
        created_at: string;
      }>;
    }>(`/api/v1/polar/subscriptions?organization_id=${organizationId}`);

    return response.data.items.map(sub => this.mapSubscription(sub));
  }

  /**
   * Cancel subscription
   *
   * @param cancelAtPeriodEnd - If true, subscription remains active until period end
   *
   * @example
   * ```typescript
   * // Cancel at period end (recommended)
   * await client.polar.cancelSubscription('sub_123', true);
   *
   * // Cancel immediately
   * await client.polar.cancelSubscription('sub_123', false);
   * ```
   */
  async cancelSubscription(subscriptionId: string, cancelAtPeriodEnd: boolean = true): Promise<PolarSubscription> {
    const response = await this.client.post<any>(
      `/api/v1/polar/subscriptions/${subscriptionId}/cancel`,
      { cancel_at_period_end: cancelAtPeriodEnd }
    );

    const subscription = this.mapSubscription(response.data);
    this.config.onSubscriptionChange?.(subscription);
    return subscription;
  }

  /**
   * Resume a canceled subscription (before period end)
   */
  async resumeSubscription(subscriptionId: string): Promise<PolarSubscription> {
    const response = await this.client.post<any>(
      `/api/v1/polar/subscriptions/${subscriptionId}/resume`,
      {}
    );

    const subscription = this.mapSubscription(response.data);
    this.config.onSubscriptionChange?.(subscription);
    return subscription;
  }

  /**
   * Check if organization has active subscription
   *
   * @example
   * ```typescript
   * if (await client.polar.hasActiveSubscription('org_123')) {
   *   // Show pro features
   * }
   * ```
   */
  async hasActiveSubscription(organizationId: string): Promise<boolean> {
    const subscription = await this.getSubscription(organizationId);
    return subscription?.status === 'active' || subscription?.status === 'trialing';
  }

  /**
   * Check if organization has specific plan
   *
   * @example
   * ```typescript
   * if (await client.polar.hasPlan('org_123', 'enterprise')) {
   *   // Show enterprise features
   * }
   * ```
   */
  async hasPlan(organizationId: string, plan: string): Promise<boolean> {
    const subscription = await this.getSubscription(organizationId);
    if (!subscription) return false;

    const isActive = subscription.status === 'active' || subscription.status === 'trialing';
    const matchesPlan = subscription.plan === plan;

    return isActive && matchesPlan;
  }

  // ==========================================================================
  // Customer Portal
  // ==========================================================================

  /**
   * Get customer portal URL
   *
   * @example
   * ```typescript
   * const portalUrl = await client.polar.getCustomerPortalUrl('org_123');
   * window.open(portalUrl, '_blank');
   * ```
   */
  async getCustomerPortalUrl(organizationId: string): Promise<string> {
    const response = await this.client.get<{ portal_url: string }>(
      `/api/v1/polar/customer/portal?organization_id=${organizationId}`
    );
    return response.data.portal_url;
  }

  /**
   * Redirect to customer portal
   *
   * @example
   * ```typescript
   * await client.polar.redirectToPortal('org_123');
   * ```
   */
  async redirectToPortal(organizationId: string): Promise<void> {
    const portalUrl = await this.getCustomerPortalUrl(organizationId);

    if (typeof window !== 'undefined') {
      window.location.href = portalUrl;
    } else {
      throw new Error('redirectToPortal() requires a browser environment');
    }
  }

  /**
   * Get customer portal data (subscriptions, benefits, orders)
   *
   * @example
   * ```typescript
   * const data = await client.polar.getCustomerPortalData('org_123');
   * console.log('Active benefits:', data.benefits.filter(b => b.isActive));
   * ```
   */
  async getCustomerPortalData(organizationId: string): Promise<PolarCustomerPortalData> {
    const response = await this.client.get<{
      subscriptions: any[];
      benefits: any[];
      orders: any[];
    }>(`/api/v1/polar/customer/data?organization_id=${organizationId}`);

    return {
      subscriptions: response.data.subscriptions.map(sub => this.mapSubscription(sub)),
      benefits: response.data.benefits.map(benefit => ({
        id: benefit.id,
        type: benefit.type,
        description: benefit.description,
        isActive: benefit.is_active,
        grantedAt: benefit.granted_at
      })),
      orders: response.data.orders.map(order => ({
        id: order.id,
        amount: order.amount,
        taxAmount: order.tax_amount,
        currency: order.currency,
        productId: order.product_id,
        createdAt: order.created_at
      }))
    };
  }

  // ==========================================================================
  // Usage-Based Billing
  // ==========================================================================

  /**
   * Ingest usage event for metered billing
   *
   * @example
   * ```typescript
   * // Record API call
   * await client.polar.ingestUsage('org_123', {
   *   eventName: 'api_call',
   *   quantity: 1
   * });
   *
   * // Record storage usage
   * await client.polar.ingestUsage('org_123', {
   *   eventName: 'storage_gb',
   *   quantity: 5,
   *   properties: { bucket: 'uploads' }
   * });
   * ```
   */
  async ingestUsage(organizationId: string, event: PolarUsageEvent): Promise<void> {
    await this.client.post('/api/v1/polar/usage', {
      organization_id: organizationId,
      event_name: event.eventName,
      quantity: event.quantity || 1,
      properties: event.properties || {},
      timestamp: (event.timestamp || new Date()).toISOString()
    });
  }

  /**
   * Batch ingest multiple usage events
   *
   * @example
   * ```typescript
   * await client.polar.ingestUsageBatch('org_123', [
   *   { eventName: 'api_call', quantity: 100 },
   *   { eventName: 'compute_minutes', quantity: 30 }
   * ]);
   * ```
   */
  async ingestUsageBatch(organizationId: string, events: PolarUsageEvent[]): Promise<void> {
    await this.client.post('/api/v1/polar/usage/batch', {
      organization_id: organizationId,
      events: events.map(event => ({
        event_name: event.eventName,
        quantity: event.quantity || 1,
        properties: event.properties || {},
        timestamp: (event.timestamp || new Date()).toISOString()
      }))
    });
  }

  /**
   * Get usage summary for organization
   *
   * @example
   * ```typescript
   * const usage = await client.polar.getUsageSummary('org_123');
   * console.log('API calls this month:', usage.find(u => u.eventName === 'api_call')?.totalQuantity);
   * ```
   */
  async getUsageSummary(
    organizationId: string,
    startDate?: Date,
    endDate?: Date
  ): Promise<Array<{ eventName: string; totalQuantity: number }>> {
    const params = new URLSearchParams({ organization_id: organizationId });
    if (startDate) params.append('start_date', startDate.toISOString());
    if (endDate) params.append('end_date', endDate.toISOString());

    const response = await this.client.get<{
      items: Array<{ event_name: string; total_quantity: number }>;
    }>(`/api/v1/polar/usage/summary?${params.toString()}`);

    return response.data.items.map(item => ({
      eventName: item.event_name,
      totalQuantity: item.total_quantity
    }));
  }

  // ==========================================================================
  // Products
  // ==========================================================================

  /**
   * List available products
   */
  async listProducts(): Promise<Array<{
    id: string;
    name: string;
    description?: string;
    isRecurring: boolean;
    prices: Array<{
      id: string;
      amount?: number;
      currency: string;
      interval?: 'month' | 'year';
    }>;
  }>> {
    const response = await this.client.get<{
      items: Array<{
        id: string;
        name: string;
        description?: string;
        is_recurring: boolean;
        prices: Array<{
          id: string;
          price_amount?: number;
          price_currency: string;
          recurring_interval?: string;
        }>;
      }>;
    }>('/api/v1/polar/products');

    return response.data.items.map(product => ({
      id: product.id,
      name: product.name,
      description: product.description,
      isRecurring: product.is_recurring,
      prices: product.prices.map(price => ({
        id: price.id,
        amount: price.price_amount,
        currency: price.price_currency,
        interval: price.recurring_interval as 'month' | 'year' | undefined
      }))
    }));
  }

  // ==========================================================================
  // Private Helpers
  // ==========================================================================

  private mapSubscription(data: any): PolarSubscription {
    return {
      id: data.id,
      status: data.status,
      currentPeriodStart: data.current_period_start,
      currentPeriodEnd: data.current_period_end,
      cancelAtPeriodEnd: data.cancel_at_period_end,
      canceledAt: data.canceled_at,
      customerId: data.customer_id,
      productId: data.product_id,
      priceId: data.price_id,
      plan: this.productIdToName.get(data.product_id),
      metadata: data.metadata || {},
      createdAt: data.created_at
    };
  }
}

// ============================================================================
// Factory Function
// ============================================================================

/**
 * Create Polar plugin instance
 *
 * @example
 * ```typescript
 * const polar = createPolarPlugin({
 *   products: {
 *     pro: 'prod_xxxxx',
 *     enterprise: 'prod_yyyyy'
 *   },
 *   defaultSuccessUrl: '/dashboard?upgraded=true',
 *   onCheckoutSuccess: (subscription) => {
 *     console.log('Subscription created:', subscription);
 *   }
 * });
 *
 * polar.install(client);
 * ```
 */
export function createPolarPlugin(config: PolarPluginConfig = {}): PolarPlugin {
  return new PolarPlugin(config);
}

// ============================================================================
// Type Augmentation
// ============================================================================

// Augment JanuaClient type to include polar plugin
declare module '../client' {
  interface JanuaClient {
    polar: PolarPlugin;
  }
}

export default PolarPlugin;
