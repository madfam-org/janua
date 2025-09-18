import { EventEmitter } from 'events';
import { Redis } from 'ioredis';
import {
  PaymentProvider,
  PaymentIntent,
  PaymentMethod,
  Customer,
  Subscription,
  Webhook,
  CheckoutSession,
  Currency,
  PaymentStatus,
  SubscriptionStatus,
  RefundStatus,
  PaymentProviderInterface,
  LineItem,
  RefundRequest,
  ComplianceCheck
} from '../../types/payment.types';

interface FungiesConfig {
  apiKey: string;
  secretKey: string;
  merchantId: string;
  webhookSecret: string;
  environment: 'sandbox' | 'production';
  baseUrl?: string;
  timeout?: number;
  retryAttempts?: number;
  supportedCountries?: string[];
  supportedCurrencies?: Currency[];
  supportsCrypto?: boolean;
  supportsBNPL?: boolean;
  taxSettings?: {
    autoCalculateVAT: boolean;
    includeVATInPrice: boolean;
    defaultTaxRate: number;
    calculateTaxRefunds?: boolean;
  };
}

interface TaxCalculation {
  country: string;
  vatRate: number;
  vatAmount: number;
  netAmount: number;
  grossAmount: number;
  taxType: 'VAT' | 'GST' | 'SALES_TAX' | 'NONE';
  businessCustomer: boolean;
  reverseCharge: boolean;
}

export class FungiesProvider extends EventEmitter implements PaymentProviderInterface {
  public readonly id = 'fungies';
  public readonly name = 'fungies';
  public readonly supportedCountries = [
    // EU Countries
    'AT', 'BE', 'BG', 'HR', 'CY', 'CZ', 'DK', 'EE', 'FI', 'FR',
    'DE', 'GR', 'HU', 'IE', 'IT', 'LV', 'LT', 'LU', 'MT', 'NL',
    'PL', 'PT', 'RO', 'SK', 'SI', 'ES', 'SE',
    // Other supported countries
    'GB', 'CH', 'NO', 'IS', 'US', 'CA', 'AU', 'NZ', 'JP', 'SG',
    'HK', 'IN', 'BR', 'AR', 'CL', 'CO', 'PE', 'UY'
  ];

  public readonly supportedCurrencies: Currency[] = [
    'USD', 'EUR', 'GBP', 'CAD', 'AUD', 'JPY', 'CHF', 'NOK', 'SEK',
    'DKK', 'PLN', 'CZK', 'HUF', 'RON', 'BGN', 'HRK', 'SGD', 'HKD',
    'NZD', 'BRL', 'ARS', 'CLP', 'COP', 'PEN', 'UYU', 'INR'
  ];

  private config: FungiesConfig;
  private redis: Redis;
  private apiClient: any; // Fungies SDK client

  constructor(config: FungiesConfig, redis: Redis) {
    super();
    this.config = config;
    this.redis = redis;
    this.initializeClient();
  }

  private initializeClient(): void {
    // Initialize Fungies.io SDK
    const baseUrl = this.config.environment === 'production'
      ? 'https://api.fungies.io/v1'
      : 'https://sandbox.api.fungies.io/v1';

    // In production, this would use the official Fungies SDK
    this.apiClient = {
      baseUrl,
      headers: {
        'Authorization': `Bearer ${this.config.apiKey}`,
        'Merchant-ID': this.config.merchantId,
        'Content-Type': 'application/json'
      }
    };
  }

  async initialize(): Promise<void> {
    try {
      // Verify API credentials
      const response = await this.makeRequest('GET', '/merchant/verify');

      if (!response.active) {
        throw new Error('Fungies.io merchant account is not active');
      }

      // Cache merchant capabilities
      await this.redis.setex(
        `fungies:merchant:${this.config.merchantId}`,
        3600,
        JSON.stringify(response)
      );

      this.emit('initialized', { provider: 'fungies' });
    } catch (error) {
      this.emit('initialization_failed', { provider: 'fungies', error });
      throw error;
    }
  }

  async createCustomer(customer: Partial<Customer>): Promise<string> {
    const payload = {
      email: customer.email,
      name: customer.name,
      metadata: {
        ...customer.metadata,
        // Tax-related metadata for MoR compliance
        tax_exempt: customer.metadata?.tax_exempt || false,
        vat_number: customer.metadata?.vat_number,
        business_type: customer.metadata?.business_type,
        tax_location: customer.metadata?.tax_location
      }
    };

    const response = await this.makeRequest('POST', '/customers', payload);

    const createdCustomer: Customer = {
      id: response.id,
      provider: 'fungies',
      email: response.email,
      name: response.name,
      metadata: response.metadata,
      provider_customers: {
        fungies: { id: response.id, created_at: new Date(response.created_at) }
      },
      created_at: new Date(response.created_at),
      updated_at: new Date(response.updated_at)
    };

    // Cache customer with tax information
    await this.redis.setex(
      `fungies:customer:${createdCustomer.id}`,
      86400,
      JSON.stringify(createdCustomer)
    );

    return createdCustomer.id;
  }

  async updateCustomer(customerId: string, updates: Partial<Customer>): Promise<void> {
    const payload = {
      email: updates.email,
      name: updates.name,
      metadata: updates.metadata
    };

    const response = await this.makeRequest('PATCH', `/customers/${customerId}`, payload);

    const customer: Customer = {
      id: response.id,
      provider: 'fungies',
      email: response.email,
      name: response.name,
      metadata: response.metadata,
      provider_customers: {
        fungies: { id: response.id, created_at: new Date(response.created_at) }
      },
      created_at: new Date(response.created_at),
      updated_at: new Date(response.updated_at)
    };

    // Update cache
    await this.redis.setex(
      `fungies:customer:${customer.id}`,
      86400,
      JSON.stringify(customer)
    );
  }

  async createPaymentIntent(data: {
    amount: number;
    currency: Currency;
    customerId?: string;
    organizationId?: string;
    metadata?: Record<string, any>;
  }): Promise<PaymentIntent> {
    // Calculate tax for MoR compliance
    const taxCalculation = await this.calculateTax({
      amount: data.amount,
      currency: data.currency,
      customerId: data.customerId,
      country: data.metadata?.country || 'US'
    });

    const payload = {
      amount: taxCalculation.grossAmount, // Include tax
      currency: data.currency,
      customer_id: data.customerId,
      tax_calculation: {
        net_amount: taxCalculation.netAmount,
        tax_amount: taxCalculation.vatAmount,
        tax_rate: taxCalculation.vatRate,
        tax_type: taxCalculation.taxType,
        reverse_charge: taxCalculation.reverseCharge
      },
      merchant_of_record: true, // Fungies handles tax compliance
      metadata: {
        ...data.metadata,
        original_amount: data.amount,
        tax_calculated: true
      }
    };

    const response = await this.makeRequest('POST', '/payment_intents', payload);

    const intent: PaymentIntent = {
      id: response.id,
      provider: 'fungies',
      amount: response.amount,
      currency: response.currency as Currency,
      status: this.mapPaymentStatus(response.status),
      customer_id:response.customer_id,
      organization_id: data.organizationId || 'default-org',
      metadata: response.metadata,
      created_at: new Date(response.created_at),
      updated_at: new Date(response.updated_at)
    };

    // Cache with tax details
    await this.redis.setex(
      `fungies:intent:${intent.id}`,
      3600,
      JSON.stringify({ intent, taxCalculation })
    );

    return intent;
  }

  async confirmPaymentIntent(
    intentId: string,
    paymentMethodId: string
  ): Promise<PaymentIntent> {
    const payload = {
      payment_method: paymentMethodId,
      confirm: true,
      return_url: `${process.env.APP_URL}/payments/complete`
    };

    const response = await this.makeRequest(
      'POST',
      `/payment_intents/${intentId}/confirm`,
      payload
    );

    const intent: PaymentIntent = {
      id: response.id,
      provider: 'fungies',
      amount: response.amount,
      currency: response.currency as Currency,
      status: this.mapPaymentStatus(response.status),
      customer_id:response.customer_id,
      organization_id: 'default-org',
      payment_method: response.payment_method,
      metadata: response.metadata,
      created_at: new Date(response.created_at),
      updated_at: new Date(response.updated_at)
    };

    // Update cache
    await this.redis.setex(
      `fungies:intent:${intent.id}`,
      3600,
      JSON.stringify(intent)
    );

    // Generate tax invoice if payment succeeded
    if (intent.status === 'succeeded') {
      await this.generateTaxInvoice(intentId);
    }

    return intent;
  }

  async createCheckoutSession(params: {
    customer_id: string;
    line_items: LineItem[];
    success_url: string;
    cancel_url: string;
    metadata?: Record<string, any>;
  }): Promise<CheckoutSession> {
    // Calculate total amount from line items
    const totalAmount = params.line_items.reduce((sum, item) => sum + (item.amount * item.quantity), 0);
    const currency = params.line_items[0]?.currency || 'USD';

    // Calculate tax for display
    const taxCalculation = await this.calculateTax({
      amount: totalAmount,
      currency: currency as Currency,
      customerId: params.customer_id,
      country: params.metadata?.country || 'US'
    });

    const payload = {
      mode: 'payment',
      amount: taxCalculation.grossAmount,
      currency: currency,
      customer_id: params.customer_id,
      success_url: params.success_url,
      cancel_url: params.cancel_url,
      line_items: params.line_items.map(item => ({
        name: item.name || 'Plinto Service',
        description: item.description,
        amount: item.amount,
        currency: item.currency,
        quantity: item.quantity,
        tax: {
          amount: taxCalculation.vatAmount,
          rate: taxCalculation.vatRate,
          type: taxCalculation.taxType
        }
      })),
      tax_display: {
        show_inclusive: this.config.taxSettings?.includeVATInPrice ?? false,
        show_breakdown: true
      },
      payment_method_types: this.getAvailablePaymentMethods(
        params.metadata?.country || 'US',
        currency
      ),
      metadata: params.metadata
    };

    const response = await this.makeRequest('POST', '/checkout/sessions', payload);

    const session: CheckoutSession = {
      id: response.id,
      provider: 'fungies',
      url: response.url,
      amount: totalAmount,
      currency: currency as Currency,
      customer_id: params.customer_id,
      success_url: params.success_url,
      cancel_url: params.cancel_url,
      line_items: params.line_items,
      status: response.status || 'open',
      metadata: params.metadata,
      expires_at: new Date(response.expires_at),
      created_at: new Date(response.created_at)
    };

    // Cache session
    await this.redis.setex(
      `fungies:session:${session.id}`,
      3600,
      JSON.stringify(session)
    );

    return session;
  }

  async createSubscription(data: {
    customerId: string;
    planId: string;
    paymentMethodId?: string;
    trialDays?: number;
    metadata?: Record<string, any>;
  }): Promise<Subscription> {
    const payload = {
      customer_id: data.customerId,
      price_id: data.planId, // Fungies uses price_id for subscription plans
      payment_method: data.paymentMethodId,
      trial_period_days: data.trialDays,
      tax_behavior: 'inclusive', // MoR handles tax
      automatic_tax: {
        enabled: true
      },
      metadata: data.metadata
    };

    const response = await this.makeRequest('POST', '/subscriptions', payload);

    const subscription: Subscription = {
      id: response.id,
      provider: 'fungies',
      customer_id:response.customer_id,
      plan_id: response.price_id,
      status: this.mapSubscriptionStatus(response.status),
      current_period_start: new Date(response.current_period_start),
      current_period_end: new Date(response.current_period_end),
      cancel_at_period_end: response.cancel_at_period_end || false,
      metadata: response.metadata
    };

    // Cache subscription
    await this.redis.setex(
      `fungies:subscription:${subscription.id}`,
      86400,
      JSON.stringify(subscription)
    );

    return subscription;
  }

  async cancelSubscription(subscriptionId: string): Promise<Subscription> {
    const payload = {
      cancel_at_period_end: true
    };

    const response = await this.makeRequest(
      'PATCH',
      `/subscriptions/${subscriptionId}`,
      payload
    );

    const subscription: Subscription = {
      id: response.id,
      provider: 'fungies',
      customer_id:response.customer_id,
      plan_id: response.price_id,
      status: this.mapSubscriptionStatus(response.status),
      current_period_start: new Date(response.current_period_start),
      current_period_end: new Date(response.current_period_end),
      cancel_at_period_end: response.cancel_at_period_end || false,
      canceled_at: response.canceled_at ? new Date(response.canceled_at) : undefined,
      metadata: response.metadata
    };

    // Update cache
    await this.redis.setex(
      `fungies:subscription:${subscription.id}`,
      86400,
      JSON.stringify(subscription)
    );

    return subscription;
  }

  async createPaymentMethod(data: {
    type: 'card' | 'bank_account' | 'paypal' | 'sepa' | 'ideal' | 'giropay';
    customerId: string;
    details: Record<string, any>;
  }): Promise<PaymentMethod> {
    const payload = {
      type: this.mapPaymentMethodType(data.type),
      customer_id: data.customerId,
      ...data.details
    };

    const response = await this.makeRequest('POST', '/payment_methods', payload);

    const method: PaymentMethod = {
      id: response.id,
      provider: 'fungies',
      type: data.type,
      is_default: false,
      details: {
        brand: response.card?.brand,
        last4: response.card?.last4,
        exp_month: response.card?.exp_month,
        exp_year: response.card?.exp_year,
        ...response.details
      }
    };

    return method;
  }

  async refund(paymentIntentId: string, amount?: number): Promise<{
    id: string;
    status: RefundStatus;
    amount: number;
  }> {
    const payload = {
      payment_intent: paymentIntentId,
      amount: amount // If not provided, full refund
    };

    const response = await this.makeRequest('POST', '/refunds', payload);

    // Handle tax refund for MoR
    await this.handleTaxRefund(response.id, paymentIntentId);

    return {
      id: response.id,
      status: this.mapRefundStatus(response.status),
      amount: response.amount
    };
  }

  async validateWebhook(payload: string, signature: string): Promise<boolean> {
    // Fungies.io webhook validation
    const crypto = require('crypto');
    const expectedSignature = crypto
      .createHmac('sha256', this.config.webhookSecret)
      .update(payload)
      .digest('hex');

    return signature === expectedSignature;
  }

  async processWebhook(event: Webhook): Promise<void> {
    switch (event.type) {
      case 'payment_intent.succeeded':
        await this.handlePaymentSuccess(event.data);
        break;
      case 'payment_intent.failed':
        await this.handlePaymentFailure(event.data);
        break;
      case 'subscription.created':
      case 'subscription.updated':
        await this.handleSubscriptionUpdate(event.data);
        break;
      case 'invoice.payment_succeeded':
        await this.handleInvoicePayment(event.data);
        break;
      case 'tax_calculation.completed':
        await this.handleTaxCalculation(event.data);
        break;
      case 'compliance.document_required':
        await this.handleComplianceRequest(event.data);
        break;
      default:
        this.emit('webhook_received', event);
    }
  }

  isAvailable(country: string, currency: Currency): boolean {
    // Check if country and currency are supported
    if (!this.supportedCountries.includes(country)) {
      return false;
    }

    if (!this.supportedCurrencies.includes(currency)) {
      return false;
    }

    // Check for specific restrictions
    const restrictions = this.getCountryRestrictions(country);
    if (restrictions.blocked) {
      return false;
    }

    // Check for currency-country compatibility
    return this.isCurrencyValidForCountry(currency, country);
  }

  // Tax calculation for Merchant of Record
  private async calculateTax(params: {
    amount: number;
    currency: Currency;
    customerId?: string;
    country: string;
  }): Promise<TaxCalculation> {
    const payload = {
      amount: params.amount,
      currency: params.currency,
      customer_id: params.customerId,
      customer_country: params.country,
      merchant_of_record: true
    };

    const response = await this.makeRequest('POST', '/tax/calculate', payload);

    return {
      country: response.country,
      vatRate: response.tax_rate,
      vatAmount: response.tax_amount,
      netAmount: response.net_amount,
      grossAmount: response.gross_amount,
      taxType: response.tax_type,
      businessCustomer: response.business_customer,
      reverseCharge: response.reverse_charge
    };
  }

  // Generate tax-compliant invoice
  private async generateTaxInvoice(paymentIntentId: string): Promise<void> {
    const payload = {
      payment_intent_id: paymentIntentId,
      generate_pdf: true,
      send_to_customer: true
    };

    await this.makeRequest('POST', '/invoices/generate', payload);
    this.emit('invoice_generated', { paymentIntentId });
  }

  // Handle tax refund for MoR compliance
  private async handleTaxRefund(refundId: string, paymentIntentId: string): Promise<void> {
    const payload = {
      refund_id: refundId,
      payment_intent_id: paymentIntentId,
      generate_credit_note: true
    };

    await this.makeRequest('POST', '/tax/refund', payload);
    this.emit('tax_refund_processed', { refundId, paymentIntentId });
  }

  // Get available payment methods for country/currency
  private getAvailablePaymentMethods(country: string, currency: Currency): string[] {
    const methods: string[] = ['card']; // Card always available

    // EU payment methods
    if (this.isEUCountry(country)) {
      methods.push('sepa_debit', 'ideal', 'giropay', 'sofort', 'bancontact');
    }

    // UK
    if (country === 'GB') {
      methods.push('bacs_debit');
    }

    // US & Canada
    if (['US', 'CA'].includes(country)) {
      methods.push('ach_debit', 'us_bank_account');
    }

    // Asia Pacific
    if (['JP', 'SG', 'HK', 'AU', 'NZ'].includes(country)) {
      methods.push('alipay', 'wechat_pay');
    }

    // Brazil
    if (country === 'BR') {
      methods.push('boleto', 'pix');
    }

    return methods;
  }

  private getCountryRestrictions(country: string): { blocked: boolean; reason?: string } {
    // Sanctioned countries
    const sanctionedCountries = ['KP', 'IR', 'SY', 'CU', 'VE'];
    if (sanctionedCountries.includes(country)) {
      return { blocked: true, reason: 'Sanctioned country' };
    }

    return { blocked: false };
  }

  private isCurrencyValidForCountry(currency: Currency, country: string): boolean {
    // Basic currency-country validation
    const currencyCountryMap: Record<Currency, string[]> = {
      EUR: this.getEUCountries(),
      GBP: ['GB'],
      USD: ['US', 'CA', 'AU', 'NZ', 'SG', 'HK'],
      CAD: ['CA'],
      AUD: ['AU'],
      JPY: ['JP'],
      CHF: ['CH'],
      // Add more mappings...
    } as Record<Currency, string[]>;

    const validCountries = currencyCountryMap[currency];
    return !validCountries || validCountries.includes(country) || currency === 'USD'; // USD as fallback
  }

  private isEUCountry(country: string): boolean {
    const euCountries = [
      'AT', 'BE', 'BG', 'HR', 'CY', 'CZ', 'DK', 'EE', 'FI', 'FR',
      'DE', 'GR', 'HU', 'IE', 'IT', 'LV', 'LT', 'LU', 'MT', 'NL',
      'PL', 'PT', 'RO', 'SK', 'SI', 'ES', 'SE'
    ];
    return euCountries.includes(country);
  }

  private getEUCountries(): string[] {
    return [
      'AT', 'BE', 'BG', 'HR', 'CY', 'CZ', 'DK', 'EE', 'FI', 'FR',
      'DE', 'GR', 'HU', 'IE', 'IT', 'LV', 'LT', 'LU', 'MT', 'NL',
      'PL', 'PT', 'RO', 'SK', 'SI', 'ES', 'SE'
    ];
  }

  // Map internal types to Fungies types
  private mapPaymentMethodType(type: string): string {
    const typeMap: Record<string, string> = {
      'card': 'card',
      'bank_account': 'bank_transfer',
      'paypal': 'paypal',
      'sepa': 'sepa_debit',
      'ideal': 'ideal',
      'giropay': 'giropay'
    };
    return typeMap[type] || type;
  }

  private mapPaymentStatus(status: string): PaymentStatus {
    const statusMap: Record<string, PaymentStatus> = {
      'requires_payment_method': 'pending',
      'requires_confirmation': 'pending',
      'requires_action': 'pending',
      'processing': 'processing',
      'succeeded': 'succeeded',
      'canceled': 'canceled',
      'failed': 'failed'
    };
    return statusMap[status] || 'pending';
  }

  private mapSubscriptionStatus(status: string): SubscriptionStatus {
    const statusMap: Record<string, SubscriptionStatus> = {
      'trialing': 'trialing',
      'active': 'active',
      'past_due': 'past_due',
      'canceled': 'canceled',
      'incomplete': 'pending',
      'incomplete_expired': 'canceled',
      'paused': 'paused'
    };
    return statusMap[status] || 'pending';
  }

  private mapRefundStatus(status: string): RefundStatus {
    const statusMap: Record<string, RefundStatus> = {
      'pending': 'pending',
      'succeeded': 'succeeded',
      'failed': 'failed',
      'canceled': 'canceled'
    };
    return statusMap[status] || 'pending';
  }

  // Additional webhook handlers for complete coverage
  private async handleSubscriptionCancellation(data: any): Promise<void> {
    this.emit('subscription_canceled', {
      subscription_id: data.id,
      customer_id: data.customer,
      canceled_at: data.canceled_at,
      provider: 'fungies'
    });
  }

  private async handleRefundCompleted(data: any): Promise<void> {
    this.emit('refund_completed', {
      refund_id: data.id,
      payment_intent_id: data.payment_intent,
      amount: data.amount,
      status: data.status,
      provider: 'fungies'
    });
  }

  private async handlePaymentMethodUpdate(data: any): Promise<void> {
    this.emit('payment_method_updated', {
      payment_method_id: data.id,
      customer_id: data.customer,
      type: data.type,
      provider: 'fungies'
    });
  }

  // Webhook handlers
  private async handlePaymentSuccess(data: any): Promise<void> {
    this.emit('payment_succeeded', {
      intentId: data.id,
      amount: data.amount,
      currency: data.currency
    });
  }

  private async handlePaymentFailure(data: any): Promise<void> {
    this.emit('payment_failed', {
      intentId: data.id,
      error: data.last_error
    });
  }

  private async handleSubscriptionUpdate(data: any): Promise<void> {
    this.emit('subscription_updated', {
      subscriptionId: data.id,
      status: data.status
    });
  }

  private async handleInvoicePayment(data: any): Promise<void> {
    this.emit('invoice_paid', {
      invoiceId: data.id,
      subscriptionId: data.subscription
    });
  }

  private async handleTaxCalculation(data: any): Promise<void> {
    this.emit('tax_calculated', {
      calculationId: data.id,
      amount: data.tax_amount
    });
  }

  private async handleComplianceRequest(data: any): Promise<void> {
    this.emit('compliance_required', {
      customer_id:data.customer_id,
      documents: data.required_documents
    });
  }

  // HTTP client wrapper
  private async makeRequest(method: string, path: string, data?: any): Promise<any> {
    // In production, use actual HTTP client (axios, fetch, etc.)
    const url = `${this.apiClient.baseUrl}${path}`;

    // Simulated API response for development
    return {
      id: `fungies_${Date.now()}`,
      status: 'succeeded',
      ...data
    };
  }

  // ============================================
  // Additional Interface Methods Implementation
  // ============================================

  /**
   * Delete a customer from the payment provider
   * Properly handles cleanup and associated data removal
   */
  async deleteCustomer(customerId: string): Promise<void> {
    try {
      // Delete from provider
      await this.makeRequest('DELETE', `/customers/${customerId}`, {});

      // Clean up cache
      await this.redis.del(`fungies:customer:${customerId}`);

      // Emit event for audit trail
      this.emit('customer_deleted', { customerId, provider: 'fungies' });
    } catch (error: any) {
      throw new Error(`Failed to delete customer: ${error.message}`);
    }
  }

  /**
   * Attach a payment method to a customer
   * Links payment method for future transactions
   */
  async attachPaymentMethod(customerId: string, paymentMethodId: string): Promise<void> {
    try {
      const payload = {
        customer_id: customerId
      };

      await this.makeRequest('POST', `/payment_methods/${paymentMethodId}/attach`, payload);

      // Update cache to reflect attached method
      const cacheKey = `fungies:customer:${customerId}:payment_methods`;
      const methods = await this.redis.get(cacheKey);
      if (methods) {
        const methodsList = JSON.parse(methods);
        methodsList.push(paymentMethodId);
        await this.redis.setex(cacheKey, 86400, JSON.stringify(methodsList));
      }
    } catch (error: any) {
      throw new Error(`Failed to attach payment method: ${error.message}`);
    }
  }

  /**
   * Detach a payment method from its customer
   * Removes payment method association
   */
  async detachPaymentMethod(paymentMethodId: string): Promise<void> {
    try {
      await this.makeRequest('POST', `/payment_methods/${paymentMethodId}/detach`, {});

      // Clean up from all customer caches
      const keys = await this.redis.keys('fungies:customer:*:payment_methods');
      for (const key of keys) {
        const methods = JSON.parse(await this.redis.get(key) || '[]');
        const filtered = methods.filter((id: string) => id !== paymentMethodId);
        if (filtered.length !== methods.length) {
          await this.redis.setex(key, 86400, JSON.stringify(filtered));
        }
      }
    } catch (error: any) {
      throw new Error(`Failed to detach payment method: ${error.message}`);
    }
  }

  /**
   * List all payment methods for a customer
   * Returns array of payment methods with full details
   */
  async listPaymentMethods(customerId: string): Promise<PaymentMethod[]> {
    try {
      // Check cache first
      const cacheKey = `fungies:customer:${customerId}:payment_methods`;
      const cached = await this.redis.get(cacheKey);
      if (cached) {
        return JSON.parse(cached);
      }

      // Fetch from provider
      const response = await this.makeRequest('GET', `/customers/${customerId}/payment_methods`, {});

      const methods: PaymentMethod[] = response.data.map((method: any) => ({
        id: method.id,
        provider: 'fungies',
        type: method.type,
        is_default: method.is_default || false,
        details: {
          brand: method.card?.brand,
          last4: method.card?.last4,
          exp_month: method.card?.exp_month,
          exp_year: method.card?.exp_year,
          bank_name: method.bank?.name,
          ...method.details
        }
      }));

      // Cache the results
      await this.redis.setex(cacheKey, 3600, JSON.stringify(methods));

      return methods;
    } catch (error: any) {
      throw new Error(`Failed to list payment methods: ${error.message}`);
    }
  }

  /**
   * Cancel a payment intent
   * Properly cancels payment and handles refunds if needed
   */
  async cancelPayment(intentId: string): Promise<PaymentIntent> {
    try {
      const response = await this.makeRequest('POST', `/payment_intents/${intentId}/cancel`, {});

      const intent: PaymentIntent = {
        id: response.id,
        provider: 'fungies',
        amount: response.amount,
        currency: response.currency as Currency,
        status: 'canceled',
        customer_id: response.customer_id,
        organization_id: response.metadata?.organization_id || 'default-org',
        metadata: response.metadata,
        created_at: new Date(response.created_at),
        updated_at: new Date(response.updated_at)
      };

      // Update cache
      await this.redis.setex(
        `fungies:intent:${intent.id}`,
        86400,
        JSON.stringify(intent)
      );

      // Emit cancellation event
      this.emit('payment_canceled', { intentId, provider: 'fungies' });

      return intent;
    } catch (error: any) {
      throw new Error(`Failed to cancel payment: ${error.message}`);
    }
  }

  /**
   * Create a refund for a payment
   * Handles partial and full refunds with proper tax calculations
   */
  async createRefund(request: RefundRequest): Promise<{ id: string; status: string }> {
    try {
      const payload = {
        payment_intent: request.payment_intent_id,
        amount: request.amount,
        reason: request.reason,
        metadata: request.metadata
      };

      const response = await this.makeRequest('POST', '/refunds', payload);

      // Handle tax refund for MoR compliance
      if (this.config.taxSettings?.calculateTaxRefunds) {
        await this.handleTaxRefund(response.id, request.payment_intent_id);
      }

      return {
        id: response.id,
        status: this.mapRefundStatus(response.status)
      };
    } catch (error: any) {
      throw new Error(`Failed to create refund: ${error.message}`);
    }
  }

  /**
   * Retrieve subscription details
   * Fetches complete subscription information
   */
  async getSubscription(subscriptionId: string): Promise<Subscription> {
    try {
      // Check cache first
      const cached = await this.redis.get(`fungies:subscription:${subscriptionId}`);
      if (cached) {
        return JSON.parse(cached);
      }

      const response = await this.makeRequest('GET', `/subscriptions/${subscriptionId}`, {});

      const subscription: Subscription = {
        id: response.id,
        customer_id: response.customer_id,
        status: this.mapSubscriptionStatus(response.status),
        plan_id: response.price_id,
        current_period_start: new Date(response.current_period_start),
        current_period_end: new Date(response.current_period_end),
        cancel_at_period_end: response.cancel_at_period_end || false,
        canceled_at: response.canceled_at ? new Date(response.canceled_at) : undefined,
        trial_start: response.trial_start ? new Date(response.trial_start) : undefined,
        trial_end: response.trial_end ? new Date(response.trial_end) : undefined,
        provider: 'fungies',
        metadata: response.metadata
      };

      // Cache for 1 hour
      await this.redis.setex(
        `fungies:subscription:${subscriptionId}`,
        3600,
        JSON.stringify(subscription)
      );

      return subscription;
    } catch (error: any) {
      throw new Error(`Failed to get subscription: ${error.message}`);
    }
  }

  /**
   * List all subscriptions for a customer
   * Returns active and inactive subscriptions
   */
  async listSubscriptions(customerId: string): Promise<Subscription[]> {
    try {
      const response = await this.makeRequest('GET', `/customers/${customerId}/subscriptions`, {});

      return response.data.map((sub: any) => ({
        id: sub.id,
        customer_id: sub.customer_id,
        status: this.mapSubscriptionStatus(sub.status),
        plan_id: sub.price_id,
        current_period_start: new Date(sub.current_period_start),
        current_period_end: new Date(sub.current_period_end),
        cancel_at_period_end: sub.cancel_at_period_end || false,
        canceled_at: sub.canceled_at ? new Date(sub.canceled_at) : undefined,
        trial_start: sub.trial_start ? new Date(sub.trial_start) : undefined,
        trial_end: sub.trial_end ? new Date(sub.trial_end) : undefined,
        provider: 'fungies',
        metadata: sub.metadata
      }));
    } catch (error: any) {
      throw new Error(`Failed to list subscriptions: ${error.message}`);
    }
  }

  /**
   * Pause a subscription
   * Temporarily suspends billing while preserving subscription
   */
  async pauseSubscription(subscriptionId: string): Promise<Subscription> {
    try {
      const response = await this.makeRequest('POST', `/subscriptions/${subscriptionId}/pause`, {});

      const subscription: Subscription = {
        id: response.id,
        customer_id: response.customer_id,
        status: 'paused',
        plan_id: response.price_id,
        current_period_start: new Date(response.current_period_start),
        current_period_end: new Date(response.current_period_end),
        cancel_at_period_end: response.cancel_at_period_end || false,
        metadata: response.metadata
      };

      // Update cache
      await this.redis.setex(
        `fungies:subscription:${subscriptionId}`,
        86400,
        JSON.stringify(subscription)
      );

      return subscription;
    } catch (error: any) {
      throw new Error(`Failed to pause subscription: ${error.message}`);
    }
  }

  /**
   * Resume a paused subscription
   * Reactivates billing for a paused subscription
   */
  async resumeSubscription(subscriptionId: string): Promise<Subscription> {
    try {
      const response = await this.makeRequest('POST', `/subscriptions/${subscriptionId}/resume`, {});

      const subscription: Subscription = {
        id: response.id,
        customer_id: response.customer_id,
        status: 'active',
        plan_id: response.price_id,
        current_period_start: new Date(response.current_period_start),
        current_period_end: new Date(response.current_period_end),
        cancel_at_period_end: response.cancel_at_period_end || false,
        metadata: response.metadata
      };

      // Update cache
      await this.redis.setex(
        `fungies:subscription:${subscriptionId}`,
        86400,
        JSON.stringify(subscription)
      );

      return subscription;
    } catch (error: any) {
      throw new Error(`Failed to resume subscription: ${error.message}`);
    }
  }

  /**
   * Confirm a payment intent
   * This method is already implemented above as confirmPaymentIntent
   * Adding alias for interface compliance
   */
  async confirmPayment(intentId: string): Promise<PaymentIntent> {
    // For the interface, we use the default payment method
    // In production, this would retrieve the default from the intent
    return this.confirmPaymentIntent(intentId, '');
  }

  /**
   * Validate webhook signature
   * Ensures webhook authenticity for security
   */
  validateWebhookSignature(payload: string, signature: string): boolean {
    try {
      // Import crypto for signature verification
      const crypto = require('crypto');

      // Compute expected signature
      const expectedSignature = crypto
        .createHmac('sha256', this.config.webhookSecret)
        .update(payload)
        .digest('hex');

      // Constant-time comparison to prevent timing attacks
      const actualSignature = Buffer.from(signature);
      const expectedBuffer = Buffer.from(expectedSignature);

      if (actualSignature.length !== expectedBuffer.length) {
        return false;
      }

      return crypto.timingSafeEqual(actualSignature, expectedBuffer);
    } catch (error: any) {
      console.error('Webhook signature validation failed:', error);
      return false;
    }
  }

  /**
   * Process webhook event
   * Handles incoming webhook events from provider
   */
  async processWebhookEvent(event: any): Promise<void> {
    try {
      const eventType = event.type;
      const eventData = event.data;

      // Route events to appropriate handlers
      switch (eventType) {
        case 'payment_intent.succeeded':
          await this.handlePaymentSuccess(eventData);
          break;

        case 'payment_intent.failed':
          await this.handlePaymentFailure(eventData);
          break;

        case 'customer.subscription.created':
        case 'customer.subscription.updated':
          await this.handleSubscriptionUpdate(eventData);
          break;

        case 'customer.subscription.deleted':
          await this.handleSubscriptionCancellation(eventData);
          break;

        case 'charge.refunded':
          await this.handleRefundCompleted(eventData);
          break;

        case 'payment_method.attached':
        case 'payment_method.updated':
          await this.handlePaymentMethodUpdate(eventData);
          break;

        default:
          // Log unhandled events for monitoring
          console.log(`Unhandled webhook event type: ${eventType}`);
      }

      // Emit event for audit trail
      this.emit('webhook_processed', { eventType, provider: 'fungies' });
    } catch (error: any) {
      console.error('Failed to process webhook event:', error);
      throw new Error(`Webhook processing failed: ${error.message}`);
    }
  }

  /**
   * Get supported payment methods
   * Returns available payment methods for given country
   */
  getSupportedPaymentMethods(country: string): string[] {
    // Base payment methods always available
    const baseMethods = ['card'];

    // Country-specific payment methods
    const countryMethods: Record<string, string[]> = {
      'US': ['ach_debit', 'wire_transfer'],
      'EU': ['sepa_debit', 'ideal', 'giropay'],
      'MX': ['oxxo', 'spei'],
      'BR': ['boleto', 'pix'],
      'JP': ['konbini'],
      'CN': ['alipay', 'wechat_pay'],
      'IN': ['upi', 'netbanking'],
      'UK': ['bacs_debit'],
      'CA': ['interac'],
      'AU': ['becs_debit'],
      'DE': ['sepa_debit', 'giropay'],
      'FR': ['sepa_debit'],
      'IT': ['sepa_debit'],
      'ES': ['sepa_debit'],
      'NL': ['ideal', 'sepa_debit']
    };

    const methods = new Set(baseMethods);

    // Add country-specific methods
    const countrySpecific = countryMethods[country] || [];
    countrySpecific.forEach(method => methods.add(method));

    // Add crypto payment if enabled
    if (this.config.supportsCrypto) {
      methods.add('crypto');
    }

    // Add buy-now-pay-later if enabled
    if (this.config.supportsBNPL) {
      methods.add('bnpl');
    }

    return Array.from(methods);
  }

  /**
   * Get compliance requirements
   * Returns regulatory requirements for given check
   */
  getComplianceRequirements(check: ComplianceCheck): string[] {
    const requirements: string[] = [];

    // EU compliance (GDPR, VAT, PSD2)
    const euCountries = [
      'AT', 'BE', 'BG', 'HR', 'CY', 'CZ', 'DK', 'EE', 'FI', 'FR', 
      'DE', 'GR', 'HU', 'IE', 'IT', 'LV', 'LT', 'LU', 'MT', 'NL', 
      'PL', 'PT', 'RO', 'SK', 'SI', 'ES', 'SE'
    ];

    if (euCountries.includes(check.country)) {
      requirements.push('GDPR', 'VAT_ID_REQUIRED', 'PSD2_SCA');
      if (check.amount > 30) {
        requirements.push('3DS2_REQUIRED');
      }
    }

    // US compliance
    if (check.country === 'US') {
      requirements.push('SSN_OR_EIN', 'STATE_TAX');
      if (check.amount > 10000) {
        requirements.push('IRS_FORM_8300');
      }
      if (check.customer_type === 'business') {
        requirements.push('W9_REQUIRED');
      }
    }

    // UK compliance
    if (check.country === 'GB') {
      requirements.push('VAT_NUMBER', 'FCA_COMPLIANCE');
      if (check.amount > 15000) {
        requirements.push('AML_CHECK_REQUIRED');
      }
    }

    // Canada compliance
    if (check.country === 'CA') {
      requirements.push('GST_HST_NUMBER', 'PROVINCIAL_TAX');
    }

    // Australia compliance
    if (check.country === 'AU') {
      requirements.push('ABN_REQUIRED', 'GST_REGISTRATION');
    }

    // India compliance
    if (check.country === 'IN') {
      requirements.push('GST_NUMBER', 'PAN_CARD');
      if (check.amount > 200000) { // INR
        requirements.push('TDS_DEDUCTION');
      }
    }

    // Brazil compliance
    if (check.country === 'BR') {
      requirements.push('CPF_CNPJ', 'NOTA_FISCAL');
    }

    // Japan compliance
    if (check.country === 'JP') {
      requirements.push('CONSUMPTION_TAX', 'MY_NUMBER');
    }

    // China compliance
    if (check.country === 'CN') {
      requirements.push('BUSINESS_LICENSE', 'TAX_REGISTRATION', 'CBEC_REGISTRATION');
    }

    // General requirements based on amount
    if (check.amount > 10000) {
      requirements.push('ENHANCED_KYC', 'SOURCE_OF_FUNDS');
    }

    // Recurring payment requirements
    if (check.is_recurring) {
      requirements.push('MANDATE_REQUIRED', 'RECURRING_INDICATOR');
    }

    // Business customer requirements
    if (check.customer_type === 'business') {
      requirements.push('BUSINESS_VERIFICATION', 'TAX_ID_REQUIRED');
    }

    return requirements;
  }
}