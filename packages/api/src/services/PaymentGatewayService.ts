/**
 * Payment Gateway Service
 * Handles payment processing with Conekta (Mexico), Fungies.io (International), and Stripe (Fallback)
 */

import Stripe from 'stripe';
import axios from 'axios';
import { logger } from '../utils/logger';
import { PaymentError, ValidationError } from '../utils/errors';

interface PaymentGateway {
  name: string;
  priority: number;
  region: string[];
  isAvailable(): Promise<boolean>;
}

interface PaymentIntent {
  id: string;
  amount: number;
  currency: string;
  status: 'pending' | 'succeeded' | 'failed' | 'canceled';
  clientSecret?: string;
  redirectUrl?: string;
  metadata?: Record<string, any>;
}

interface Customer {
  id: string;
  email: string;
  name: string;
  country: string;
  paymentMethodId?: string;
}

interface Subscription {
  id: string;
  customerId: string;
  planId: string;
  status: 'active' | 'canceled' | 'past_due' | 'trialing';
  currentPeriodStart: Date;
  currentPeriodEnd: Date;
  cancelAtPeriodEnd: boolean;
  metadata?: Record<string, any>;
}

export class PaymentGatewayService {
  private stripe: Stripe;
  private conektaApiKey: string;
  private fungiesApiKey: string;
  private fungiesApiUrl: string;

  constructor() {
    this.stripe = new Stripe(process.env.STRIPE_SECRET_KEY!, {
      apiVersion: '2023-10-16'
    });
    this.conektaApiKey = process.env.CONEKTA_SECRET_KEY!;
    this.fungiesApiKey = process.env.FUNGIES_API_KEY!;
    this.fungiesApiUrl = process.env.FUNGIES_API_URL || 'https://api.fungies.io';
  }

  /**
   * Determine the best payment gateway for a customer
   */
  private selectPaymentGateway(country: string, amount: number): 'conekta' | 'fungies' | 'stripe' {
    // Mexican customers use Conekta
    if (country === 'MX') {
      return 'conekta';
    }

    // International customers use Fungies.io
    // Unless amount is very large (enterprise deals), then use Stripe
    if (amount >= 10000 * 100) { // $10,000+ USD
      return 'stripe';
    }

    return 'fungies';
  }

  /**
   * Create a customer in the appropriate gateway
   */
  async createCustomer(data: {
    email: string;
    name: string;
    country: string;
    phone?: string;
    metadata?: Record<string, any>;
  }): Promise<Customer> {
    const gateway = this.selectPaymentGateway(data.country, 0);

    try {
      switch (gateway) {
        case 'conekta':
          return await this.createConektaCustomer(data);
        case 'fungies':
          return await this.createFungiesCustomer(data);
        case 'stripe':
          return await this.createStripeCustomer(data);
        default:
          throw new PaymentError('Unsupported payment gateway');
      }
    } catch (error) {
      logger.error('Error creating customer', { error, data, gateway });

      // Fallback to Stripe if primary gateway fails
      if (gateway !== 'stripe') {
        logger.info('Falling back to Stripe for customer creation', { data });
        return await this.createStripeCustomer(data);
      }

      throw error;
    }
  }

  /**
   * Create a payment intent
   */
  async createPaymentIntent(data: {
    amount: number;
    currency: string;
    customerId: string;
    country: string;
    description?: string;
    metadata?: Record<string, any>;
  }): Promise<PaymentIntent> {
    const gateway = this.selectPaymentGateway(data.country, data.amount);

    try {
      switch (gateway) {
        case 'conekta':
          return await this.createConektaPaymentIntent(data);
        case 'fungies':
          return await this.createFungiesPaymentIntent(data);
        case 'stripe':
          return await this.createStripePaymentIntent(data);
        default:
          throw new PaymentError('Unsupported payment gateway');
      }
    } catch (error) {
      logger.error('Error creating payment intent', { error, data, gateway });

      // Fallback to Stripe if primary gateway fails
      if (gateway !== 'stripe') {
        logger.info('Falling back to Stripe for payment intent', { data });
        return await this.createStripePaymentIntent(data);
      }

      throw error;
    }
  }

  /**
   * Create a subscription
   */
  async createSubscription(data: {
    customerId: string;
    planId: string;
    country: string;
    trialDays?: number;
    metadata?: Record<string, any>;
  }): Promise<Subscription> {
    const gateway = this.selectPaymentGateway(data.country, 0);

    try {
      switch (gateway) {
        case 'conekta':
          return await this.createConektaSubscription(data);
        case 'fungies':
          return await this.createFungiesSubscription(data);
        case 'stripe':
          return await this.createStripeSubscription(data);
        default:
          throw new PaymentError('Unsupported payment gateway');
      }
    } catch (error) {
      logger.error('Error creating subscription', { error, data, gateway });

      // Fallback to Stripe if primary gateway fails
      if (gateway !== 'stripe') {
        logger.info('Falling back to Stripe for subscription', { data });
        return await this.createStripeSubscription(data);
      }

      throw error;
    }
  }

  // Conekta Implementation
  private async createConektaCustomer(data: {
    email: string;
    name: string;
    country: string;
    phone?: string;
    metadata?: Record<string, any>;
  }): Promise<Customer> {
    const response = await axios.post(
      'https://api.conekta.io/customers',
      {
        name: data.name,
        email: data.email,
        phone: data.phone,
        metadata: data.metadata
      },
      {
        headers: {
          'Authorization': `Bearer ${this.conektaApiKey}`,
          'Content-Type': 'application/json',
          'Accept': 'application/vnd.conekta-v2.1.0+json'
        }
      }
    );

    return {
      id: response.data.id,
      email: response.data.email,
      name: response.data.name,
      country: data.country
    };
  }

  private async createConektaPaymentIntent(data: {
    amount: number;
    currency: string;
    customerId: string;
    description?: string;
    metadata?: Record<string, any>;
  }): Promise<PaymentIntent> {
    const response = await axios.post(
      'https://api.conekta.io/orders',
      {
        amount: data.amount,
        currency: data.currency.toUpperCase(),
        customer_info: {
          customer_id: data.customerId
        },
        line_items: [{
          name: data.description || 'Plinto Subscription',
          unit_price: data.amount,
          quantity: 1
        }],
        metadata: data.metadata
      },
      {
        headers: {
          'Authorization': `Bearer ${this.conektaApiKey}`,
          'Content-Type': 'application/json',
          'Accept': 'application/vnd.conekta-v2.1.0+json'
        }
      }
    );

    return {
      id: response.data.id,
      amount: data.amount,
      currency: data.currency,
      status: this.mapConektaStatus(response.data.payment_status),
      clientSecret: response.data.id, // Conekta uses order ID as reference
      metadata: data.metadata
    };
  }

  private async createConektaSubscription(data: {
    customerId: string;
    planId: string;
    trialDays?: number;
    metadata?: Record<string, any>;
  }): Promise<Subscription> {
    const response = await axios.post(
      `https://api.conekta.io/customers/${data.customerId}/subscription`,
      {
        plan: data.planId,
        trial_end: data.trialDays ?
          Math.floor((Date.now() + data.trialDays * 24 * 60 * 60 * 1000) / 1000) :
          undefined,
        metadata: data.metadata
      },
      {
        headers: {
          'Authorization': `Bearer ${this.conektaApiKey}`,
          'Content-Type': 'application/json',
          'Accept': 'application/vnd.conekta-v2.1.0+json'
        }
      }
    );

    return {
      id: response.data.id,
      customerId: data.customerId,
      planId: data.planId,
      status: this.mapConektaSubscriptionStatus(response.data.status),
      currentPeriodStart: new Date(response.data.billing_cycle_start * 1000),
      currentPeriodEnd: new Date(response.data.billing_cycle_end * 1000),
      cancelAtPeriodEnd: false,
      metadata: data.metadata
    };
  }

  // Fungies.io Implementation
  private async createFungiesCustomer(data: {
    email: string;
    name: string;
    country: string;
    phone?: string;
    metadata?: Record<string, any>;
  }): Promise<Customer> {
    const response = await axios.post(
      `${this.fungiesApiUrl}/v1/customers`,
      {
        email: data.email,
        name: data.name,
        country: data.country,
        phone: data.phone,
        metadata: data.metadata
      },
      {
        headers: {
          'Authorization': `Bearer ${this.fungiesApiKey}`,
          'Content-Type': 'application/json'
        }
      }
    );

    return {
      id: response.data.id,
      email: response.data.email,
      name: response.data.name,
      country: data.country
    };
  }

  private async createFungiesPaymentIntent(data: {
    amount: number;
    currency: string;
    customerId: string;
    description?: string;
    metadata?: Record<string, any>;
  }): Promise<PaymentIntent> {
    const response = await axios.post(
      `${this.fungiesApiUrl}/v1/payment-intents`,
      {
        amount: data.amount,
        currency: data.currency,
        customer_id: data.customerId,
        description: data.description,
        metadata: data.metadata
      },
      {
        headers: {
          'Authorization': `Bearer ${this.fungiesApiKey}`,
          'Content-Type': 'application/json'
        }
      }
    );

    return {
      id: response.data.id,
      amount: data.amount,
      currency: data.currency,
      status: this.mapFungiesStatus(response.data.status),
      clientSecret: response.data.client_secret,
      metadata: data.metadata
    };
  }

  private async createFungiesSubscription(data: {
    customerId: string;
    planId: string;
    trialDays?: number;
    metadata?: Record<string, any>;
  }): Promise<Subscription> {
    const trialEnd = data.trialDays ?
      new Date(Date.now() + data.trialDays * 24 * 60 * 60 * 1000).toISOString() :
      undefined;

    const response = await axios.post(
      `${this.fungiesApiUrl}/v1/subscriptions`,
      {
        customer_id: data.customerId,
        plan_id: data.planId,
        trial_end: trialEnd,
        metadata: data.metadata
      },
      {
        headers: {
          'Authorization': `Bearer ${this.fungiesApiKey}`,
          'Content-Type': 'application/json'
        }
      }
    );

    return {
      id: response.data.id,
      customerId: data.customerId,
      planId: data.planId,
      status: this.mapFungiesSubscriptionStatus(response.data.status),
      currentPeriodStart: new Date(response.data.current_period_start),
      currentPeriodEnd: new Date(response.data.current_period_end),
      cancelAtPeriodEnd: response.data.cancel_at_period_end,
      metadata: data.metadata
    };
  }

  // Stripe Implementation (Fallback)
  private async createStripeCustomer(data: {
    email: string;
    name: string;
    country: string;
    phone?: string;
    metadata?: Record<string, any>;
  }): Promise<Customer> {
    const customer = await this.stripe.customers.create({
      email: data.email,
      name: data.name,
      phone: data.phone,
      metadata: data.metadata || {}
    });

    return {
      id: customer.id,
      email: customer.email!,
      name: customer.name!,
      country: data.country
    };
  }

  private async createStripePaymentIntent(data: {
    amount: number;
    currency: string;
    customerId: string;
    description?: string;
    metadata?: Record<string, any>;
  }): Promise<PaymentIntent> {
    const paymentIntent = await this.stripe.paymentIntents.create({
      amount: data.amount,
      currency: data.currency,
      customer: data.customerId,
      description: data.description,
      metadata: data.metadata || {},
      automatic_payment_methods: {
        enabled: true
      }
    });

    return {
      id: paymentIntent.id,
      amount: data.amount,
      currency: data.currency,
      status: this.mapStripeStatus(paymentIntent.status),
      clientSecret: paymentIntent.client_secret!,
      metadata: data.metadata
    };
  }

  private async createStripeSubscription(data: {
    customerId: string;
    planId: string;
    trialDays?: number;
    metadata?: Record<string, any>;
  }): Promise<Subscription> {
    const subscriptionData: any = {
      customer: data.customerId,
      items: [{ price: data.planId }],
      metadata: data.metadata || {},
      expand: ['latest_invoice.payment_intent']
    };

    if (data.trialDays) {
      subscriptionData.trial_period_days = data.trialDays;
    }

    const subscription = await this.stripe.subscriptions.create(subscriptionData);

    return {
      id: subscription.id,
      customerId: data.customerId,
      planId: data.planId,
      status: this.mapStripeSubscriptionStatus(subscription.status),
      currentPeriodStart: new Date(subscription.current_period_start * 1000),
      currentPeriodEnd: new Date(subscription.current_period_end * 1000),
      cancelAtPeriodEnd: subscription.cancel_at_period_end,
      metadata: data.metadata
    };
  }

  // Status mapping helpers
  private mapConektaStatus(status: string): 'pending' | 'succeeded' | 'failed' | 'canceled' {
    const statusMap: Record<string, 'pending' | 'succeeded' | 'failed' | 'canceled'> = {
      'pending_payment': 'pending',
      'paid': 'succeeded',
      'partially_paid': 'pending',
      'canceled': 'canceled',
      'declined': 'failed'
    };
    return statusMap[status] || 'pending';
  }

  private mapConektaSubscriptionStatus(status: string): 'active' | 'canceled' | 'past_due' | 'trialing' {
    const statusMap: Record<string, 'active' | 'canceled' | 'past_due' | 'trialing'> = {
      'active': 'active',
      'past_due': 'past_due',
      'canceled': 'canceled',
      'trialing': 'trialing',
      'in_trial': 'trialing'
    };
    return statusMap[status] || 'active';
  }

  private mapFungiesStatus(status: string): 'pending' | 'succeeded' | 'failed' | 'canceled' {
    const statusMap: Record<string, 'pending' | 'succeeded' | 'failed' | 'canceled'> = {
      'requires_payment_method': 'pending',
      'requires_confirmation': 'pending',
      'requires_action': 'pending',
      'processing': 'pending',
      'succeeded': 'succeeded',
      'canceled': 'canceled',
      'failed': 'failed'
    };
    return statusMap[status] || 'pending';
  }

  private mapFungiesSubscriptionStatus(status: string): 'active' | 'canceled' | 'past_due' | 'trialing' {
    const statusMap: Record<string, 'active' | 'canceled' | 'past_due' | 'trialing'> = {
      'active': 'active',
      'past_due': 'past_due',
      'canceled': 'canceled',
      'unpaid': 'past_due',
      'trialing': 'trialing'
    };
    return statusMap[status] || 'active';
  }

  private mapStripeStatus(status: string): 'pending' | 'succeeded' | 'failed' | 'canceled' {
    const statusMap: Record<string, 'pending' | 'succeeded' | 'failed' | 'canceled'> = {
      'requires_payment_method': 'pending',
      'requires_confirmation': 'pending',
      'requires_action': 'pending',
      'processing': 'pending',
      'requires_capture': 'pending',
      'succeeded': 'succeeded',
      'canceled': 'canceled',
      'payment_failed': 'failed'
    };
    return statusMap[status] || 'pending';
  }

  private mapStripeSubscriptionStatus(status: string): 'active' | 'canceled' | 'past_due' | 'trialing' {
    const statusMap: Record<string, 'active' | 'canceled' | 'past_due' | 'trialing'> = {
      'active': 'active',
      'past_due': 'past_due',
      'canceled': 'canceled',
      'unpaid': 'past_due',
      'trialing': 'trialing',
      'incomplete': 'pending' as any,
      'incomplete_expired': 'canceled'
    };
    return statusMap[status] || 'active';
  }

  /**
   * Cancel a subscription
   */
  async cancelSubscription(subscriptionId: string, gateway: 'conekta' | 'fungies' | 'stripe'): Promise<void> {
    try {
      switch (gateway) {
        case 'conekta':
          await axios.delete(`https://api.conekta.io/subscriptions/${subscriptionId}`, {
            headers: {
              'Authorization': `Bearer ${this.conektaApiKey}`,
              'Accept': 'application/vnd.conekta-v2.1.0+json'
            }
          });
          break;

        case 'fungies':
          await axios.post(`${this.fungiesApiUrl}/v1/subscriptions/${subscriptionId}/cancel`, {}, {
            headers: {
              'Authorization': `Bearer ${this.fungiesApiKey}`,
              'Content-Type': 'application/json'
            }
          });
          break;

        case 'stripe':
          await this.stripe.subscriptions.update(subscriptionId, {
            cancel_at_period_end: true
          });
          break;
      }
    } catch (error) {
      logger.error('Error canceling subscription', { error, subscriptionId, gateway });
      throw new PaymentError('Failed to cancel subscription');
    }
  }

  /**
   * Get subscription details
   */
  async getSubscription(subscriptionId: string, gateway: 'conekta' | 'fungies' | 'stripe'): Promise<Subscription> {
    try {
      switch (gateway) {
        case 'conekta':
          const conektaResponse = await axios.get(`https://api.conekta.io/subscriptions/${subscriptionId}`, {
            headers: {
              'Authorization': `Bearer ${this.conektaApiKey}`,
              'Accept': 'application/vnd.conekta-v2.1.0+json'
            }
          });

          return {
            id: conektaResponse.data.id,
            customerId: conektaResponse.data.customer_id,
            planId: conektaResponse.data.plan,
            status: this.mapConektaSubscriptionStatus(conektaResponse.data.status),
            currentPeriodStart: new Date(conektaResponse.data.billing_cycle_start * 1000),
            currentPeriodEnd: new Date(conektaResponse.data.billing_cycle_end * 1000),
            cancelAtPeriodEnd: false
          };

        case 'fungies':
          const fungiesResponse = await axios.get(`${this.fungiesApiUrl}/v1/subscriptions/${subscriptionId}`, {
            headers: {
              'Authorization': `Bearer ${this.fungiesApiKey}`
            }
          });

          return {
            id: fungiesResponse.data.id,
            customerId: fungiesResponse.data.customer_id,
            planId: fungiesResponse.data.plan_id,
            status: this.mapFungiesSubscriptionStatus(fungiesResponse.data.status),
            currentPeriodStart: new Date(fungiesResponse.data.current_period_start),
            currentPeriodEnd: new Date(fungiesResponse.data.current_period_end),
            cancelAtPeriodEnd: fungiesResponse.data.cancel_at_period_end
          };

        case 'stripe':
          const stripeSubscription = await this.stripe.subscriptions.retrieve(subscriptionId);

          return {
            id: stripeSubscription.id,
            customerId: stripeSubscription.customer as string,
            planId: stripeSubscription.items.data[0].price.id,
            status: this.mapStripeSubscriptionStatus(stripeSubscription.status),
            currentPeriodStart: new Date(stripeSubscription.current_period_start * 1000),
            currentPeriodEnd: new Date(stripeSubscription.current_period_end * 1000),
            cancelAtPeriodEnd: stripeSubscription.cancel_at_period_end
          };

        default:
          throw new PaymentError('Unsupported payment gateway');
      }
    } catch (error) {
      logger.error('Error getting subscription', { error, subscriptionId, gateway });
      throw new PaymentError('Failed to get subscription');
    }
  }
}