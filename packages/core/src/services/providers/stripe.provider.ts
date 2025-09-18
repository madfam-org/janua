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
  RefundStatus,
  PaymentProviderInterface,
  LineItem,
  RefundRequest,
  ComplianceCheck
} from '../../types/payment.types';

interface StripeConfig {
  secretKey: string;
  publishableKey: string;
  webhookSecret: string;
  apiVersion: string;
}

export class StripeProvider extends EventEmitter implements PaymentProviderInterface {
  public readonly id = 'stripe';
  public readonly name = 'stripe';

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

  async createCustomer(customer: Partial<Customer>): Promise<string> {
    const stripeCustomer = await this.stripe.customers.create({
      email: customer.email,
      name: customer.name,
      metadata: customer.metadata || {}
    });

    const customerData: Customer = {
      id: stripeCustomer.id,
      email: stripeCustomer.email!,
      name: stripeCustomer.name || '',
      phone: undefined,
      address: undefined,
      tax_info: undefined,
      provider_customers: {
        stripe: {
          id: stripeCustomer.id,
          created_at: new Date(stripeCustomer.created * 1000)
        }
      },
      default_payment_method: undefined,
      provider: 'stripe',
      metadata: stripeCustomer.metadata as Record<string, any> || {},
      created_at: new Date(stripeCustomer.created * 1000),
      updated_at: new Date()
    };

    // Cache customer
    await this.redis.setex(
      `stripe:customer:${stripeCustomer.id}`,
      86400,
      JSON.stringify(customerData)
    );

    return stripeCustomer.id;
  }

  async updateCustomer(customerId: string, updates: Partial<Customer>): Promise<void> {
    await this.stripe.customers.update(customerId, {
      email: updates.email,
      name: updates.name,
      metadata: updates.metadata
    });

    // Update cache
    await this.redis.del(`stripe:customer:${customerId}`);
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
      provider: 'stripe',
      provider_intent_id: stripeIntent.id,
      amount: stripeIntent.amount / 100,
      currency: stripeIntent.currency.toUpperCase() as Currency,
      status: this.mapPaymentStatus(stripeIntent.status),
      customer_id: stripeIntent.customer as string,
      organization_id: data.metadata?.organization_id || '',
      description: data.metadata?.description,
      metadata: stripeIntent.metadata,
      created_at: new Date(stripeIntent.created * 1000),
      updated_at: new Date()
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
      provider: 'stripe',
      provider_intent_id: stripeIntent.id,
      amount: stripeIntent.amount / 100,
      currency: stripeIntent.currency.toUpperCase() as Currency,
      status: this.mapPaymentStatus(stripeIntent.status),
      customer_id: stripeIntent.customer as string,
      organization_id: stripeIntent.metadata?.organization_id || '',
      description: stripeIntent.metadata?.description,
      metadata: stripeIntent.metadata,
      created_at: new Date(stripeIntent.created * 1000),
      updated_at: new Date()
    };

    // Update cache
    await this.redis.setex(
      `stripe:intent:${intent.id}`,
      3600,
      JSON.stringify(intent)
    );

    return intent;
  }

  async createCheckoutSession(params: {
    customer_id: string;
    line_items: LineItem[];
    success_url: string;
    cancel_url: string;
    metadata?: Record<string, any>;
  }): Promise<CheckoutSession> {
    const stripeSession = await this.stripe.checkout.sessions.create({
      customer: params.customer_id,
      line_items: params.line_items.map(item => ({
        price_data: {
          currency: item.currency.toLowerCase(),
          product_data: {
            name: item.name,
            description: item.description,
            images: item.images
          },
          unit_amount: Math.round(item.amount * 100)
        },
        quantity: item.quantity
      })),
      mode: 'payment',
      success_url: params.success_url,
      cancel_url: params.cancel_url,
      metadata: params.metadata
    });

    const session: CheckoutSession = {
      id: stripeSession.id,
      provider: 'stripe',
      provider_session_id: stripeSession.id,
      amount: params.line_items.reduce((sum, item) => sum + (item.amount * item.quantity), 0),
      currency: params.line_items[0].currency,
      customer_id: stripeSession.customer as string,
      success_url: params.success_url,
      cancel_url: params.cancel_url,
      line_items: params.line_items,
      payment_intent_id: stripeSession.payment_intent as string,
      status: stripeSession.status === 'open' ? 'open' : stripeSession.status === 'complete' ? 'complete' : 'expired',
      expires_at: new Date(stripeSession.expires_at * 1000),
      url: stripeSession.url || undefined,
      metadata: stripeSession.metadata as Record<string, any> || {},
      created_at: new Date()
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
      customer_id: stripeSubscription.customer as string,
      status: this.mapSubscriptionStatus(stripeSubscription.status),
      plan_id: stripeSubscription.items.data[0].price.id,
      current_period_start: new Date((stripeSubscription as any).current_period_start * 1000),
      current_period_end: new Date((stripeSubscription as any).current_period_end * 1000),
      cancel_at_period_end: false,
      canceled_at: undefined,
      trial_start: stripeSubscription.trial_start ? new Date(stripeSubscription.trial_start * 1000) : undefined,
      trial_end: stripeSubscription.trial_end ? new Date(stripeSubscription.trial_end * 1000) : undefined,
      provider: 'stripe',
      metadata: stripeSubscription.metadata
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
      customer_id: stripeSubscription.customer as string,
      status: this.mapSubscriptionStatus(stripeSubscription.status),
      plan_id: stripeSubscription.items.data[0].price.id,
      current_period_start: new Date((stripeSubscription as any).current_period_start * 1000),
      current_period_end: new Date((stripeSubscription as any).current_period_end * 1000),
      cancel_at_period_end: true,
      canceled_at: stripeSubscription.canceled_at
        ? new Date(stripeSubscription.canceled_at * 1000)
        : undefined,
      trial_start: stripeSubscription.trial_start ? new Date(stripeSubscription.trial_start * 1000) : undefined,
      trial_end: stripeSubscription.trial_end ? new Date(stripeSubscription.trial_end * 1000) : undefined,
      provider: 'stripe',
      metadata: stripeSubscription.metadata
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
      provider: 'stripe',
      type: stripePaymentMethod.type as any,
      details: {
        brand: stripePaymentMethod.card?.brand,
        last4: stripePaymentMethod.card?.last4,
        exp_month: stripePaymentMethod.card?.exp_month,
        exp_year: stripePaymentMethod.card?.exp_year,
        bank_name: stripePaymentMethod.sepa_debit?.bank_code || undefined,
        reference: stripePaymentMethod.id
      },
      is_default: false,
      metadata: stripePaymentMethod.metadata ? (stripePaymentMethod.metadata as Record<string, any>) : undefined
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
      'canceled': 'canceled'
    };
    return statusMap[status] || 'failed';
  }

  private mapSubscriptionStatus(status: Stripe.Subscription.Status): SubscriptionStatus {
    const statusMap: Record<Stripe.Subscription.Status, SubscriptionStatus> = {
      'trialing': 'trialing',
      'active': 'active',
      'incomplete': 'canceled',
      'incomplete_expired': 'canceled',
      'past_due': 'past_due',
      'canceled': 'canceled',
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
      'canceled': 'canceled'
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
      subscriptionId: (invoice as any).subscription
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

    if ((intent as any).charges && (intent as any).charges.data.length > 0) {
      const charge = (intent as any).charges.data[0] as Stripe.Charge;
      return charge.outcome?.risk_score || 0;
    }

    return 0;
  }

  // Add missing interface methods before the class ends
  
  async deleteCustomer(customerId: string): Promise<void> {
    await this.stripe.customers.del(customerId);
    await this.redis.del(`stripe:customer:${customerId}`);
  }

  async attachPaymentMethod(customerId: string, paymentMethodId: string): Promise<void> {
    await this.stripe.paymentMethods.attach(paymentMethodId, {
      customer: customerId
    });
  }

  async detachPaymentMethod(paymentMethodId: string): Promise<void> {
    await this.stripe.paymentMethods.detach(paymentMethodId);
  }

  async listPaymentMethods(customerId: string): Promise<PaymentMethod[]> {
    const methods = await this.stripe.paymentMethods.list({
      customer: customerId,
      type: 'card'
    });

    return methods.data.map(pm => ({
      id: pm.id,
      provider: 'stripe',
      type: pm.type as any,
      details: {
        brand: pm.card?.brand,
        last4: pm.card?.last4,
        exp_month: pm.card?.exp_month,
        exp_year: pm.card?.exp_year
      },
      is_default: false,
      metadata: pm.metadata as Record<string, any>
    }));
  }

  async confirmPayment(intentId: string): Promise<PaymentIntent> {
    const stripeIntent = await this.stripe.paymentIntents.confirm(intentId);
    
    return {
      id: stripeIntent.id,
      provider: 'stripe',
      provider_intent_id: stripeIntent.id,
      amount: stripeIntent.amount / 100,
      currency: stripeIntent.currency.toUpperCase() as Currency,
      status: this.mapPaymentStatus(stripeIntent.status),
      customer_id: stripeIntent.customer as string,
      organization_id: stripeIntent.metadata?.organization_id || '',
      description: stripeIntent.metadata?.description,
      metadata: stripeIntent.metadata,
      created_at: new Date(stripeIntent.created * 1000),
      updated_at: new Date()
    };
  }

  async cancelPayment(intentId: string): Promise<PaymentIntent> {
    const stripeIntent = await this.stripe.paymentIntents.cancel(intentId);
    
    return {
      id: stripeIntent.id,
      provider: 'stripe',
      provider_intent_id: stripeIntent.id,
      amount: stripeIntent.amount / 100,
      currency: stripeIntent.currency.toUpperCase() as Currency,
      status: this.mapPaymentStatus(stripeIntent.status),
      customer_id: stripeIntent.customer as string,
      organization_id: stripeIntent.metadata?.organization_id || '',
      description: stripeIntent.metadata?.description,
      metadata: stripeIntent.metadata,
      created_at: new Date(stripeIntent.created * 1000),
      updated_at: new Date()
    };
  }

  async createRefund(request: RefundRequest): Promise<{ id: string; status: string }> {
    const refundParams: Stripe.RefundCreateParams = {
      payment_intent: request.payment_intent_id,
      reason: request.reason === 'duplicate' ? 'duplicate' :
              request.reason === 'fraudulent' ? 'fraudulent' : 
              'requested_by_customer',
      metadata: request.metadata
    };

    if (request.amount) {
      refundParams.amount = Math.round(request.amount * 100);
    }

    const stripeRefund = await this.stripe.refunds.create(refundParams);

    return {
      id: stripeRefund.id,
      status: this.mapRefundStatus(stripeRefund.status!)
    };
  }

  validateWebhookSignature(payload: string, signature: string): boolean {
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

  async processWebhookEvent(event: any): Promise<void> {
    switch (event.type) {
      case 'payment_intent.succeeded':
        await this.handlePaymentSuccess(event.data);
        break;
      case 'payment_intent.payment_failed':
        await this.handlePaymentFailure(event.data);
        break;
      case 'checkout.session.completed':
        // Handle checkout session completion
        this.emit('checkout:completed', event.data);
        break;
      case 'customer.subscription.created':
        await this.handleSubscriptionUpdate(event.data);
        break;
      case 'customer.subscription.deleted':
        await this.handleSubscriptionCancellation(event.data);
        break;
      default:
        console.log(`Unhandled webhook event: ${event.type}`);
    }
  }

  isAvailable(country: string, currency: Currency): boolean {
    // Stripe supports most countries and currencies
    const supportedCurrencies = [
      'USD', 'EUR', 'GBP', 'CAD', 'AUD', 'JPY', 'CNY', 'SGD', 'HKD', 
      'NZD', 'SEK', 'NOK', 'DKK', 'PLN', 'CZK', 'HUF', 'RON', 'BGN',
      'HRK', 'CHF', 'MXN', 'BRL', 'ARS', 'COP', 'CLP', 'PEN', 'UYU',
      'INR', 'RUB', 'TRY', 'ILS', 'SAR', 'AED', 'ZAR', 'THB', 'MYR',
      'PHP', 'IDR', 'KRW', 'TWD', 'VND'
    ];
    
    return supportedCurrencies.includes(currency);
  }

  getSupportedPaymentMethods(country: string): string[] {
    const methods: string[] = ['card']; // Card always supported
    
    // Country-specific payment methods
    if (country === 'US') {
      methods.push('ach_credit_transfer', 'us_bank_account');
    } else if (country === 'GB') {
      methods.push('bacs_debit');
    } else if (country === 'JP') {
      methods.push('konbini', 'jcb');
    } else if (country === 'CN') {
      methods.push('alipay', 'wechat_pay');
    } else if (['DE', 'NL', 'BE', 'AT', 'ES', 'IT', 'FR'].includes(country)) {
      methods.push('sepa_debit', 'ideal', 'bancontact', 'giropay');
    }
    
    return methods;
  }

  getComplianceRequirements(check: ComplianceCheck): string[] {
    const requirements: string[] = [];
    
    // EU compliance
    const euCountries = [
      'AT', 'BE', 'BG', 'HR', 'CY', 'CZ', 'DK', 'EE', 'FI', 'FR', 
      'DE', 'GR', 'HU', 'IE', 'IT', 'LV', 'LT', 'LU', 'MT', 'NL', 
      'PL', 'PT', 'RO', 'SK', 'SI', 'ES', 'SE'
    ];
    
    if (euCountries.includes(check.country)) {
      requirements.push('SCA', 'GDPR', 'VAT_ID');
    }
    
    if (check.customer_type === 'business') {
      requirements.push('BUSINESS_VERIFICATION', 'TAX_ID');
    }
    
    if (check.amount > 10000) {
      requirements.push('ENHANCED_KYC', 'SOURCE_OF_FUNDS');
    }
    
    if (check.is_recurring) {
      requirements.push('MANDATE_ACCEPTANCE', 'RECURRING_PERMISSIONS');
    }
    
    return requirements;
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