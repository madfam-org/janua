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
  RefundStatus
} from '../../types/payment.types';

interface FungiesConfig {
  apiKey: string;
  merchantId: string;
  webhookSecret: string;
  environment: 'sandbox' | 'production';
  vatRegistrationId?: string;
  taxSettings: {
    autoCalculateVAT: boolean;
    includeVATInPrice: boolean;
    defaultTaxRate: number;
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

export class FungiesProvider extends EventEmitter implements PaymentProvider {
  public readonly id = 'fungies';
  public readonly name = 'Fungies.io';
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

  async createCustomer(data: {
    email: string;
    name?: string;
    metadata?: Record<string, any>;
  }): Promise<Customer> {
    const payload = {
      email: data.email,
      name: data.name,
      metadata: {
        ...data.metadata,
        // Tax-related metadata for MoR compliance
        tax_exempt: data.metadata?.tax_exempt || false,
        vat_number: data.metadata?.vat_number,
        business_type: data.metadata?.business_type,
        tax_location: data.metadata?.tax_location
      }
    };

    const response = await this.makeRequest('POST', '/customers', payload);

    const customer: Customer = {
      id: response.id,
      providerId: 'fungies',
      email: response.email,
      name: response.name,
      metadata: response.metadata,
      createdAt: new Date(response.created_at),
      updatedAt: new Date(response.updated_at)
    };

    // Cache customer with tax information
    await this.redis.setex(
      `fungies:customer:${customer.id}`,
      86400,
      JSON.stringify(customer)
    );

    return customer;
  }

  async updateCustomer(customerId: string, data: Partial<Customer>): Promise<Customer> {
    const payload = {
      email: data.email,
      name: data.name,
      metadata: data.metadata
    };

    const response = await this.makeRequest('PATCH', `/customers/${customerId}`, payload);

    const customer: Customer = {
      id: response.id,
      providerId: 'fungies',
      email: response.email,
      name: response.name,
      metadata: response.metadata,
      createdAt: new Date(response.created_at),
      updatedAt: new Date(response.updated_at)
    };

    // Update cache
    await this.redis.setex(
      `fungies:customer:${customer.id}`,
      86400,
      JSON.stringify(customer)
    );

    return customer;
  }

  async createPaymentIntent(data: {
    amount: number;
    currency: Currency;
    customerId?: string;
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
      providerId: 'fungies',
      amount: response.amount,
      currency: response.currency as Currency,
      status: this.mapPaymentStatus(response.status),
      customerId: response.customer_id,
      metadata: response.metadata,
      createdAt: new Date(response.created_at),
      updatedAt: new Date(response.updated_at)
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
      providerId: 'fungies',
      amount: response.amount,
      currency: response.currency as Currency,
      status: this.mapPaymentStatus(response.status),
      customerId: response.customer_id,
      paymentMethodId: response.payment_method,
      metadata: response.metadata,
      createdAt: new Date(response.created_at),
      updatedAt: new Date(response.updated_at),
      confirmedAt: response.confirmed_at ? new Date(response.confirmed_at) : undefined
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

  async createCheckoutSession(data: {
    amount: number;
    currency: Currency;
    customerId?: string;
    successUrl: string;
    cancelUrl: string;
    metadata?: Record<string, any>;
  }): Promise<CheckoutSession> {
    // Calculate tax for display
    const taxCalculation = await this.calculateTax({
      amount: data.amount,
      currency: data.currency,
      customerId: data.customerId,
      country: data.metadata?.country || 'US'
    });

    const payload = {
      mode: 'payment',
      amount: taxCalculation.grossAmount,
      currency: data.currency,
      customer_id: data.customerId,
      success_url: data.successUrl,
      cancel_url: data.cancelUrl,
      line_items: [{
        name: data.metadata?.product_name || 'Plinto Service',
        description: data.metadata?.product_description,
        amount: taxCalculation.netAmount,
        currency: data.currency,
        quantity: 1,
        tax: {
          amount: taxCalculation.vatAmount,
          rate: taxCalculation.vatRate,
          type: taxCalculation.taxType
        }
      }],
      tax_display: {
        show_inclusive: this.config.taxSettings.includeVATInPrice,
        show_breakdown: true
      },
      payment_method_types: this.getAvailablePaymentMethods(
        data.metadata?.country || 'US',
        data.currency
      ),
      metadata: data.metadata
    };

    const response = await this.makeRequest('POST', '/checkout/sessions', payload);

    const session: CheckoutSession = {
      id: response.id,
      providerId: 'fungies',
      url: response.url,
      amount: response.amount,
      currency: response.currency as Currency,
      customerId: response.customer_id,
      successUrl: response.success_url,
      cancelUrl: response.cancel_url,
      metadata: response.metadata,
      expiresAt: new Date(response.expires_at),
      createdAt: new Date(response.created_at)
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
      providerId: 'fungies',
      customerId: response.customer_id,
      planId: response.price_id,
      status: this.mapSubscriptionStatus(response.status),
      currentPeriodStart: new Date(response.current_period_start),
      currentPeriodEnd: new Date(response.current_period_end),
      metadata: response.metadata,
      createdAt: new Date(response.created_at),
      updatedAt: new Date(response.updated_at)
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
      providerId: 'fungies',
      customerId: response.customer_id,
      planId: response.price_id,
      status: this.mapSubscriptionStatus(response.status),
      currentPeriodStart: new Date(response.current_period_start),
      currentPeriodEnd: new Date(response.current_period_end),
      canceledAt: response.canceled_at ? new Date(response.canceled_at) : undefined,
      metadata: response.metadata,
      createdAt: new Date(response.created_at),
      updatedAt: new Date(response.updated_at)
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
      providerId: 'fungies',
      type: data.type,
      customerId: response.customer_id,
      details: {
        brand: response.card?.brand,
        last4: response.card?.last4,
        expiryMonth: response.card?.exp_month,
        expiryYear: response.card?.exp_year,
        ...response.details
      },
      createdAt: new Date(response.created_at)
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
      'canceled': 'cancelled',
      'failed': 'failed'
    };
    return statusMap[status] || 'pending';
  }

  private mapSubscriptionStatus(status: string): SubscriptionStatus {
    const statusMap: Record<string, SubscriptionStatus> = {
      'trialing': 'trialing',
      'active': 'active',
      'past_due': 'past_due',
      'canceled': 'cancelled',
      'incomplete': 'pending',
      'incomplete_expired': 'cancelled',
      'paused': 'paused'
    };
    return statusMap[status] || 'pending';
  }

  private mapRefundStatus(status: string): RefundStatus {
    const statusMap: Record<string, RefundStatus> = {
      'pending': 'pending',
      'succeeded': 'succeeded',
      'failed': 'failed',
      'canceled': 'cancelled'
    };
    return statusMap[status] || 'pending';
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
      customerId: data.customer_id,
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
}