/**
 * Payments SDK Module
 *
 * TypeScript SDK for Janua billing and subscription management.
 *
 * Features:
 * - Multi-provider support (Conekta, Stripe, Polar)
 * - Subscription management
 * - Payment method management
 * - Invoice management
 * - Provider fallback tracking
 */

import type { HttpClient } from './http-client';
import { NotFoundError } from './errors';

// ============================================================================
// Types
// ============================================================================

export enum BillingInterval {
  MONTHLY = 'monthly',
  YEARLY = 'yearly',
}

export enum SubscriptionStatus {
  ACTIVE = 'active',
  TRIALING = 'trialing',
  PAST_DUE = 'past_due',
  CANCELED = 'canceled',
  UNPAID = 'unpaid',
  PAUSED = 'paused',
}

export enum PaymentStatus {
  PENDING = 'pending',
  PAID = 'paid',
  FAILED = 'failed',
  REFUNDED = 'refunded',
  VOID = 'void',
}

export interface SubscriptionPlan {
  id: string;
  name: string;
  description?: string;
  price_monthly?: number;
  price_yearly?: number;
  currency_usd: string;
  currency_mxn: string;
  features: string[];
  limits: Record<string, any>;
  is_active: boolean;
}

export interface Subscription {
  id: string;
  organization_id: string;
  plan_id: string;
  plan_name: string;
  provider: 'conekta' | 'stripe' | 'polar';
  status: SubscriptionStatus;
  billing_interval: BillingInterval;
  current_period_start: string;
  current_period_end: string;
  cancel_at_period_end: boolean;
  trial_end?: string;
  created_at: string;
}

export interface PaymentMethod {
  id: string;
  organization_id: string;
  provider: 'conekta' | 'stripe' | 'polar';
  type: 'card' | 'bank_account' | 'oxxo' | 'spei';
  last4?: string;
  brand?: string;
  exp_month?: number;
  exp_year?: number;
  billing_address?: Record<string, string>;
  is_default: boolean;
  created_at: string;
}

export interface Invoice {
  id: string;
  subscription_id: string;
  provider: 'conekta' | 'stripe' | 'polar';
  amount: number;
  currency: string;
  status: PaymentStatus;
  invoice_date: string;
  due_date?: string;
  paid_at?: string;
  hosted_invoice_url?: string;
  invoice_pdf?: string;
  created_at: string;
}

export interface ProviderFallbackInfo {
  attempted_provider: 'conekta' | 'polar';
  fallback_provider: 'stripe';
  reason: 'provider_not_configured' | 'provider_api_error' | 'provider_timeout' | 'provider_unavailable';
  timestamp: string;
}

// Request types
export interface CreateSubscriptionRequest {
  plan_id: string;
  billing_interval: BillingInterval;
  payment_method_id?: string;
  trial_days?: number;
}

export interface UpdateSubscriptionRequest {
  plan_id?: string;
  billing_interval?: BillingInterval;
}

export interface AddPaymentMethodRequest {
  token: string; // Provider-specific token from client SDK
  billing_address: Record<string, string>;
  set_as_default?: boolean;
}

// ============================================================================
// Payments Class
// ============================================================================

export class Payments {
  constructor(private http: HttpClient) {}

  // --------------------------------------------------------------------------
  // Subscription Plans
  // --------------------------------------------------------------------------

  /**
   * List all available subscription plans
   */
  async listPlans(): Promise<SubscriptionPlan[]> {
    const response = await this.http.get<SubscriptionPlan[]>('/api/v1/billing/plans');
    return response.data;
  }

  /**
   * Get specific subscription plan details
   */
  async getPlan(planId: string): Promise<SubscriptionPlan> {
    const response = await this.http.get<SubscriptionPlan>(`/api/v1/billing/plans/${planId}`);
    return response.data;
  }

  // --------------------------------------------------------------------------
  // Subscriptions
  // --------------------------------------------------------------------------

  /**
   * Create new subscription
   *
   * Provider selection is automatic based on:
   * - Transaction type
   * - Customer location (geolocation)
   * - Billing address
   *
   * Stripe is used as universal fallback if primary provider unavailable.
   */
  async createSubscription(request: CreateSubscriptionRequest): Promise<Subscription> {
    const response = await this.http.post<Subscription>(
      '/api/v1/billing/subscriptions',
      request
    );
    return response.data;
  }

  /**
   * List all subscriptions for current organization
   */
  async listSubscriptions(): Promise<Subscription[]> {
    const response = await this.http.get<Subscription[]>('/api/v1/billing/subscriptions');
    return response.data;
  }

  /**
   * Get specific subscription details
   */
  async getSubscription(subscriptionId: string): Promise<Subscription> {
    const response = await this.http.get<Subscription>(
      `/api/v1/billing/subscriptions/${subscriptionId}`
    );
    return response.data;
  }

  /**
   * Update subscription (change plan or billing interval)
   */
  async updateSubscription(
    subscriptionId: string,
    request: UpdateSubscriptionRequest
  ): Promise<Subscription> {
    const response = await this.http.patch<Subscription>(
      `/api/v1/billing/subscriptions/${subscriptionId}`,
      request
    );
    return response.data;
  }

  /**
   * Cancel subscription
   *
   * @param immediate - If true, cancel immediately. If false, cancel at period end.
   */
  async cancelSubscription(subscriptionId: string, immediate: boolean = false): Promise<Subscription> {
    const response = await this.http.post<Subscription>(
      `/api/v1/billing/subscriptions/${subscriptionId}/cancel`,
      { immediate }
    );
    return response.data;
  }

  /**
   * Resume canceled subscription (if not yet expired)
   */
  async resumeSubscription(subscriptionId: string): Promise<Subscription> {
    const response = await this.http.post<Subscription>(
      `/api/v1/billing/subscriptions/${subscriptionId}/resume`,
      {}
    );
    return response.data;
  }

  // --------------------------------------------------------------------------
  // Payment Methods
  // --------------------------------------------------------------------------

  /**
   * Add payment method
   *
   * Note: Token must be obtained from provider's client SDK:
   * - Conekta: Use Conekta.js tokenization
   * - Stripe: Use Stripe.js or Elements tokenization
   * - Polar: Use Polar checkout session
   *
   * Provider selection based on billing address country.
   */
  async addPaymentMethod(request: AddPaymentMethodRequest): Promise<PaymentMethod> {
    const response = await this.http.post<PaymentMethod>(
      '/api/v1/billing/payment-methods',
      request
    );
    return response.data;
  }

  /**
   * List all payment methods for current organization
   */
  async listPaymentMethods(): Promise<PaymentMethod[]> {
    const response = await this.http.get<PaymentMethod[]>('/api/v1/billing/payment-methods');
    return response.data;
  }

  /**
   * Delete payment method
   */
  async deletePaymentMethod(paymentMethodId: string): Promise<void> {
    await this.http.delete(`/api/v1/billing/payment-methods/${paymentMethodId}`);
  }

  /**
   * Set payment method as default
   */
  async setDefaultPaymentMethod(paymentMethodId: string): Promise<PaymentMethod> {
    const response = await this.http.post<PaymentMethod>(
      `/api/v1/billing/payment-methods/${paymentMethodId}/set-default`,
      {}
    );
    return response.data;
  }

  // --------------------------------------------------------------------------
  // Invoices
  // --------------------------------------------------------------------------

  /**
   * List invoices for current organization
   *
   * @param status - Filter by status (pending, paid, failed, etc.)
   * @param limit - Maximum number of invoices to return
   * @param offset - Number of invoices to skip
   */
  async listInvoices(
    status?: PaymentStatus,
    limit: number = 50,
    offset: number = 0
  ): Promise<Invoice[]> {
    const params = new URLSearchParams();
    if (status) params.append('status', status);
    params.append('limit', limit.toString());
    params.append('offset', offset.toString());

    const response = await this.http.get<Invoice[]>(
      `/api/v1/billing/invoices?${params.toString()}`
    );
    return response.data;
  }

  /**
   * Get specific invoice details
   */
  async getInvoice(invoiceId: string): Promise<Invoice> {
    const response = await this.http.get<Invoice>(`/api/v1/billing/invoices/${invoiceId}`);
    return response.data;
  }

  /**
   * Pay pending invoice
   *
   * @param paymentMethodId - Optional payment method to use. If not provided, uses default.
   */
  async payInvoice(invoiceId: string, paymentMethodId?: string): Promise<Invoice> {
    const response = await this.http.post<Invoice>(
      `/api/v1/billing/invoices/${invoiceId}/pay`,
      paymentMethodId ? { payment_method_id: paymentMethodId } : {}
    );
    return response.data;
  }

  /**
   * Download invoice PDF
   *
   * Returns the URL to the hosted invoice PDF.
   */
  async getInvoicePdfUrl(invoiceId: string): Promise<string> {
    const invoice = await this.getInvoice(invoiceId);
    if (!invoice.invoice_pdf) {
      throw new NotFoundError('Invoice PDF not available');
    }
    return invoice.invoice_pdf;
  }

  // --------------------------------------------------------------------------
  // Provider Information
  // --------------------------------------------------------------------------

  /**
   * Get provider information for customer
   *
   * Returns which payment provider will be used based on customer location.
   * Useful for determining which client SDK to load (Conekta.js, Stripe.js, etc.)
   */
  async getProviderInfo(): Promise<{
    provider: 'conekta' | 'stripe' | 'polar';
    currency: string;
    payment_methods: string[];
    fallback_info?: ProviderFallbackInfo;
  }> {
    const response = await this.http.get('/api/v1/billing/provider-info');
    return response.data;
  }
}
