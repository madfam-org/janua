import { EventEmitter } from 'events';
import { Redis } from 'ioredis';
import Stripe from 'stripe';
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

interface StripeConfig {
  secretKey: string;
  publishableKey: string;
  webhookSecret: string;
  apiVersion: string;
}

export class StripeProvider extends EventEmitter implements PaymentProvider {
  public readonly id = 'stripe';
  public readonly name = 'Stripe';

  // Stripe supports most countries globally
  public readonly supportedCountries = [
    'US', 'CA', 'MX', 'BR', 'AR', 'CL', 'CO', 'PE', 'UY',
    'GB', 'IE', 'FR', 'DE', 'IT', 'ES', 'NL', 'BE', 'AT',
    'CH', 'DK', 'FI', 'NO', 'SE', 'PL', 'PT', 'GR', 'CZ',
    'HU', 'RO', 'BG', 'HR', 'EE', 'LV', 'LT', 'LU', 'MT',
    'SK', 'SI', 'CY', 'IS',
    'AU', 'NZ', 'JP', 'SG', 'HK', 'MY', 'TH', 'PH', 'ID',
    'IN', 'AE', 'SA', 'IL', 'EG', 'ZA', 'NG', 'KE', 'GH'
  ];

  public readonly supportedCurrencies: Currency[] = [
    'USD', 'EUR', 'GBP', 'CAD', 'AUD', 'JPY', 'CNY', 'CHF',
    'SEK', 'NOK', 'DKK', 'PLN', 'CZK', 'HUF', 'RON', 'BGN',
    'HRK', 'RUB', 'TRY', 'INR', 'IDR', 'MYR', 'PHP', 'SGD',
    'THB', 'VND', 'KRW', 'ILS', 'HKD', 'TWD', 'SAR', 'AED',
    'MXN', 'BRL', 'ARS', 'CLP', 'COP', 'PEN', 'UYU', 'ZAR',
    'NGN', 'KES', 'GHS', 'EGP', 'MAD', 'NZD'
  ];

  private stripe: Stripe;
  private config: StripeConfig;
  private redis: Redis;

  constructor(config: StripeConfig, redis: Redis) {
    super();
    this.config = config;
    this.redis = redis;

    // Initialize Stripe SDK
    this.stripe = new Stripe(config.secretKey, {
      apiVersion: config.apiVersion as Stripe.LatestApiVersion,
      typescript: true
    });
  }

  async initialize(): Promise<void> {
    try {
      // Verify API key by fetching account details
      const account = await this.stripe.accounts.retrieve();

      if (!account.charges_enabled || !account.payouts_enabled) {
        throw new Error('Stripe account is not fully activated');
      }

      // Cache account capabilities
      await this.redis.setex(
        `stripe:account:${account.id}`,
        3600,
        JSON.stringify({
          id: account.id,
          country: account.country,
          capabilities: account.capabilities,
          settings: account.settings
        })
      );

      this.emit('initialized', { provider: 'stripe' });
    } catch (error) {
      this.emit('initialization_failed', { provider: 'stripe', error });
      throw error;
    }
  }

  async createCustomer(data: {
    email: string;
    name?: string;
    metadata?: Record<string, any>;
  }): Promise<Customer> {
    const stripeCustomer = await this.stripe.customers.create({
      email: data.email,
      name: data.name,
      metadata: data.metadata || {}
    });

    const customer: Customer = {
      id: stripeCustomer.id,
      providerId: 'stripe',
      email: stripeCustomer.email!,
      name: stripeCustomer.name || undefined,
      metadata: stripeCustomer.metadata,
      createdAt: new Date(stripeCustomer.created * 1000),
      updatedAt: new Date()
    };

    // Cache customer
    await this.redis.setex(
      `stripe:customer:${customer.id}`,
      86400,
      JSON.stringify(customer)
    );

    return customer;
  }

  async updateCustomer(customerId: string, data: Partial<Customer>): Promise<Customer> {
    const stripeCustomer = await this.stripe.customers.update(customerId, {
      email: data.email,
      name: data.name,
      metadata: data.metadata
    });

    const customer: Customer = {
      id: stripeCustomer.id,
      providerId: 'stripe',
      email: stripeCustomer.email!,
      name: stripeCustomer.name || undefined,
      metadata: stripeCustomer.metadata,
      createdAt: new Date(stripeCustomer.created * 1000),
      updatedAt: new Date()
    };

    // Update cache
    await this.redis.setex(
      `stripe:customer:${customer.id}`,
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
    const stripeIntent = await this.stripe.paymentIntents.create({
      amount: Math.round(data.amount * 100), // Convert to cents
      currency: data.currency.toLowerCase(),
      customer: data.customerId,
      metadata: data.metadata || {},
      // Automatic payment methods for better conversion
      automatic_payment_methods: {
        enabled: true,
        allow_redirects: 'always'
      }
    });

    const intent: PaymentIntent = {
      id: stripeIntent.id,
      providerId: 'stripe',
      amount: stripeIntent.amount / 100,
      currency: stripeIntent.currency.toUpperCase() as Currency,
      status: this.mapPaymentStatus(stripeIntent.status),
      customerId: stripeIntent.customer as string | undefined,
      metadata: stripeIntent.metadata,
      clientSecret: stripeIntent.client_secret!,
      createdAt: new Date(stripeIntent.created * 1000),
      updatedAt: new Date()
    };

    // Cache intent
    await this.redis.setex(
      `stripe:intent:${intent.id}`,
      3600,
      JSON.stringify(intent)
    );

    return intent;
  }

  async confirmPaymentIntent(
    intentId: string,
    paymentMethodId: string
  ): Promise<PaymentIntent> {
    const stripeIntent = await this.stripe.paymentIntents.confirm(intentId, {
      payment_method: paymentMethodId,
      return_url: `${process.env.APP_URL}/payments/complete`
    });

    const intent: PaymentIntent = {
      id: stripeIntent.id,
      providerId: 'stripe',
      amount: stripeIntent.amount / 100,
      currency: stripeIntent.currency.toUpperCase() as Currency,
      status: this.mapPaymentStatus(stripeIntent.status),
      customerId: stripeIntent.customer as string | undefined,
      paymentMethodId: stripeIntent.payment_method as string | undefined,
      metadata: stripeIntent.metadata,
      clientSecret: stripeIntent.client_secret!,
      createdAt: new Date(stripeIntent.created * 1000),
      updatedAt: new Date(),
      confirmedAt: stripeIntent.status === 'succeeded' ? new Date() : undefined
    };

    // Update cache
    await this.redis.setex(
      `stripe:intent:${intent.id}`,
      3600,
      JSON.stringify(intent)
    );

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
    const sessionParams: Stripe.Checkout.SessionCreateParams = {
      mode: 'payment',
      customer: data.customerId,
      success_url: data.successUrl,
      cancel_url: data.cancelUrl,
      line_items: [{
        price_data: {
          currency: data.currency.toLowerCase(),
          unit_amount: Math.round(data.amount * 100),
          product_data: {
            name: data.metadata?.product_name || 'Plinto Service',
            description: data.metadata?.product_description,
            metadata: data.metadata
          }
        },
        quantity: 1
      }],
      payment_method_types: ['card'],
      // Enable more payment methods based on currency/country
      payment_method_options: this.getPaymentMethodOptions(data.currency),
      metadata: data.metadata || {},
      expires_at: Math.floor(Date.now() / 1000) + 3600 // 1 hour
    };

    // Add local payment methods based on currency
    if (data.currency === 'EUR') {
      sessionParams.payment_method_types!.push('sepa_debit', 'ideal', 'bancontact');
    } else if (data.currency === 'GBP') {
      sessionParams.payment_method_types!.push('bacs_debit');
    } else if (data.currency === 'JPY') {
      sessionParams.payment_method_types!.push('konbini');
    }

    const stripeSession = await this.stripe.checkout.sessions.create(sessionParams);

    const session: CheckoutSession = {
      id: stripeSession.id,
      providerId: 'stripe',
      url: stripeSession.url!,
      amount: data.amount,
      currency: data.currency,
      customerId: data.customerId,
      successUrl: data.successUrl,
      cancelUrl: data.cancelUrl,
      metadata: stripeSession.metadata,
      expiresAt: new Date(stripeSession.expires_at * 1000),
      createdAt: new Date()
    };

    // Cache session
    await this.redis.setex(
      `stripe:session:${session.id}`,
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
    const subscriptionParams: Stripe.SubscriptionCreateParams = {
      customer: data.customerId,
      items: [{ price: data.planId }],
      default_payment_method: data.paymentMethodId,
      trial_period_days: data.trialDays,
      metadata: data.metadata || {},
      payment_behavior: 'default_incomplete',
      payment_settings: {
        save_default_payment_method: 'on_subscription'
      },
      expand: ['latest_invoice.payment_intent']
    };

    const stripeSubscription = await this.stripe.subscriptions.create(subscriptionParams);

    const subscription: Subscription = {
      id: stripeSubscription.id,
      providerId: 'stripe',
      customerId: stripeSubscription.customer as string,
      planId: data.planId,
      status: this.mapSubscriptionStatus(stripeSubscription.status),
      currentPeriodStart: new Date(stripeSubscription.current_period_start * 1000),
      currentPeriodEnd: new Date(stripeSubscription.current_period_end * 1000),
      metadata: stripeSubscription.metadata,
      createdAt: new Date(stripeSubscription.created * 1000),
      updatedAt: new Date()
    };

    // Cache subscription
    await this.redis.setex(
      `stripe:subscription:${subscription.id}`,
      86400,
      JSON.stringify(subscription)
    );

    return subscription;
  }

  async cancelSubscription(subscriptionId: string): Promise<Subscription> {
    const stripeSubscription = await this.stripe.subscriptions.update(subscriptionId, {
      cancel_at_period_end: true
    });

    const subscription: Subscription = {
      id: stripeSubscription.id,
      providerId: 'stripe',
      customerId: stripeSubscription.customer as string,
      planId: stripeSubscription.items.data[0].price.id,
      status: this.mapSubscriptionStatus(stripeSubscription.status),
      currentPeriodStart: new Date(stripeSubscription.current_period_start * 1000),
      currentPeriodEnd: new Date(stripeSubscription.current_period_end * 1000),
      canceledAt: stripeSubscription.canceled_at
        ? new Date(stripeSubscription.canceled_at * 1000)
        : undefined,
      metadata: stripeSubscription.metadata,
      createdAt: new Date(stripeSubscription.created * 1000),
      updatedAt: new Date()
    };

    // Update cache
    await this.redis.setex(
      `stripe:subscription:${subscription.id}`,
      86400,
      JSON.stringify(subscription)
    );

    return subscription;
  }

  async createPaymentMethod(data: {
    type: 'card' | 'bank_account' | 'sepa_debit' | 'bacs_debit';
    customerId: string;
    details: Record<string, any>;
  }): Promise<PaymentMethod> {
    // For Stripe, payment methods are typically created client-side
    // This method would attach an existing payment method to a customer
    const stripePaymentMethod = await this.stripe.paymentMethods.attach(
      data.details.paymentMethodId,
      { customer: data.customerId }
    );

    const method: PaymentMethod = {
      id: stripePaymentMethod.id,
      providerId: 'stripe',
      type: stripePaymentMethod.type as any,
      customerId: data.customerId,
      details: {
        brand: stripePaymentMethod.card?.brand,
        last4: stripePaymentMethod.card?.last4,
        expiryMonth: stripePaymentMethod.card?.exp_month,
        expiryYear: stripePaymentMethod.card?.exp_year,
        ...stripePaymentMethod.metadata
      },
      createdAt: new Date(stripePaymentMethod.created * 1000)
    };

    return method;
  }

  async refund(paymentIntentId: string, amount?: number): Promise<{
    id: string;
    status: RefundStatus;
    amount: number;
  }> {
    const refundParams: Stripe.RefundCreateParams = {
      payment_intent: paymentIntentId
    };

    if (amount) {
      refundParams.amount = Math.round(amount * 100);
    }

    const stripeRefund = await this.stripe.refunds.create(refundParams);

    return {
      id: stripeRefund.id,
      status: this.mapRefundStatus(stripeRefund.status!),
      amount: stripeRefund.amount / 100
    };
  }

  async validateWebhook(payload: string, signature: string): Promise<boolean> {
    try {
      this.stripe.webhooks.constructEvent(
        payload,
        signature,
        this.config.webhookSecret
      );
      return true;
    } catch (error) {
      return false;
    }
  }

  async processWebhook(event: Webhook): Promise<void> {
    switch (event.type) {
      case 'payment_intent.succeeded':
        await this.handlePaymentSuccess(event.data);
        break;
      case 'payment_intent.payment_failed':
        await this.handlePaymentFailure(event.data);
        break;
      case 'customer.subscription.created':
      case 'customer.subscription.updated':
        await this.handleSubscriptionUpdate(event.data);
        break;
      case 'customer.subscription.deleted':
        await this.handleSubscriptionCancellation(event.data);
        break;
      case 'invoice.payment_succeeded':
        await this.handleInvoicePayment(event.data);
        break;
      case 'charge.dispute.created':
        await this.handleDispute(event.data);
        break;
      case 'radar.early_fraud_warning.created':
        await this.handleFraudWarning(event.data);
        break;
      default:
        this.emit('webhook_received', event);
    }
  }

  isAvailable(country: string, currency: Currency): boolean {
    // Stripe is available in most countries
    if (!this.supportedCountries.includes(country)) {
      return false;
    }

    // Check currency support
    if (!this.supportedCurrencies.includes(currency)) {
      return false;
    }

    // Check for specific restrictions
    const restrictions = this.getCountryRestrictions(country);
    if (restrictions.blocked) {
      return false;
    }

    return true;
  }

  // Helper methods
  private getPaymentMethodOptions(currency: Currency): any {
    const options: any = {};

    if (currency === 'EUR') {
      options.sepa_debit = {
        mandate_options: {
          notification_method: 'email'
        }
      };
    }

    if (currency === 'GBP') {
      options.bacs_debit = {
        setup_future_usage: 'off_session'
      };
    }

    options.card = {
      setup_future_usage: 'on_session',
      request_three_d_secure: 'automatic'
    };

    return options;
  }

  private getCountryRestrictions(country: string): { blocked: boolean; reason?: string } {
    // Stripe restricted countries
    const restrictedCountries = ['KP', 'IR', 'SY', 'CU'];
    if (restrictedCountries.includes(country)) {
      return { blocked: true, reason: 'Country not supported by Stripe' };
    }

    return { blocked: false };
  }

  private mapPaymentStatus(status: Stripe.PaymentIntent.Status): PaymentStatus {
    const statusMap: Record<Stripe.PaymentIntent.Status, PaymentStatus> = {
      'requires_payment_method': 'pending',
      'requires_confirmation': 'pending',
      'requires_action': 'pending',
      'processing': 'processing',
      'requires_capture': 'processing',
      'succeeded': 'succeeded',
      'canceled': 'cancelled'
    };
    return statusMap[status] || 'failed';
  }

  private mapSubscriptionStatus(status: Stripe.Subscription.Status): SubscriptionStatus {
    const statusMap: Record<Stripe.Subscription.Status, SubscriptionStatus> = {
      'trialing': 'trialing',
      'active': 'active',
      'incomplete': 'pending',
      'incomplete_expired': 'cancelled',
      'past_due': 'past_due',
      'canceled': 'cancelled',
      'unpaid': 'past_due',
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
    const intent = data.object as Stripe.PaymentIntent;
    this.emit('payment_succeeded', {
      intentId: intent.id,
      amount: intent.amount / 100,
      currency: intent.currency
    });
  }

  private async handlePaymentFailure(data: any): Promise<void> {
    const intent = data.object as Stripe.PaymentIntent;
    this.emit('payment_failed', {
      intentId: intent.id,
      error: intent.last_payment_error
    });
  }

  private async handleSubscriptionUpdate(data: any): Promise<void> {
    const subscription = data.object as Stripe.Subscription;
    this.emit('subscription_updated', {
      subscriptionId: subscription.id,
      status: subscription.status
    });
  }

  private async handleSubscriptionCancellation(data: any): Promise<void> {
    const subscription = data.object as Stripe.Subscription;
    this.emit('subscription_cancelled', {
      subscriptionId: subscription.id,
      canceledAt: subscription.canceled_at
    });
  }

  private async handleInvoicePayment(data: any): Promise<void> {
    const invoice = data.object as Stripe.Invoice;
    this.emit('invoice_paid', {
      invoiceId: invoice.id,
      subscriptionId: invoice.subscription
    });
  }

  private async handleDispute(data: any): Promise<void> {
    const dispute = data.object as Stripe.Dispute;
    this.emit('dispute_created', {
      disputeId: dispute.id,
      amount: dispute.amount / 100,
      reason: dispute.reason
    });
  }

  private async handleFraudWarning(data: any): Promise<void> {
    const warning = data.object;
    this.emit('fraud_warning', {
      warningId: warning.id,
      chargeId: warning.charge
    });
  }

  // 3D Secure and Strong Customer Authentication
  async handleSecureAuthentication(paymentIntentId: string): Promise<{
    requiresAction: boolean;
    clientSecret?: string;
    nextAction?: string;
  }> {
    const intent = await this.stripe.paymentIntents.retrieve(paymentIntentId);

    if (intent.status === 'requires_action' && intent.next_action) {
      return {
        requiresAction: true,
        clientSecret: intent.client_secret!,
        nextAction: intent.next_action.type
      };
    }

    return {
      requiresAction: false
    };
  }

  // Stripe Radar fraud detection
  async getFraudScore(paymentIntentId: string): Promise<number> {
    const intent = await this.stripe.paymentIntents.retrieve(paymentIntentId, {
      expand: ['charges.data.outcome']
    });

    if (intent.charges && intent.charges.data.length > 0) {
      const charge = intent.charges.data[0] as Stripe.Charge;
      return charge.outcome?.risk_score || 0;
    }

    return 0;
  }

  // Payment method recommendations based on country/currency
  getRecommendedPaymentMethods(country: string, currency: Currency): string[] {
    const methods: string[] = ['card']; // Card always recommended

    // Regional recommendations
    if (currency === 'EUR') {
      methods.push('sepa_debit', 'ideal');
    } else if (currency === 'GBP') {
      methods.push('bacs_debit');
    } else if (country === 'US') {
      methods.push('ach_credit_transfer', 'us_bank_account');
    } else if (country === 'JP') {
      methods.push('konbini', 'jcb');
    } else if (country === 'CN') {
      methods.push('alipay', 'wechat_pay');
    }

    return methods;
  }
}