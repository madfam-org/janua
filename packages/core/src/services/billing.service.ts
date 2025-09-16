import { EventEmitter } from 'events';
import { RedisService, getRedis } from './redis.service';
import { getMultiTenancyService, MultiTenancyService } from './multi-tenancy.service';

interface BillingPlan {
  id: string;
  name: string;
  display_name: string;
  description: string;
  price: {
    amount: number;
    currency: string;
    interval: 'monthly' | 'yearly' | 'one-time';
    interval_count?: number;
  };
  features: {
    users: number;
    teams: number;
    storage: number; // bytes
    api_calls: number;
    custom_roles: number;
    audit_retention_days: number;
    support_level: 'community' | 'email' | 'priority' | 'dedicated';
    sla: boolean;
    custom_domain: boolean;
    sso: boolean;
    advanced_security: boolean;
    [key: string]: any;
  };
  stripe_price_id?: string;
  stripe_product_id?: string;
  is_active: boolean;
  is_default: boolean;
  metadata?: Record<string, any>;
}

interface Subscription {
  id: string;
  organization_id: string;
  plan_id: string;
  status: 'trialing' | 'active' | 'past_due' | 'canceled' | 'unpaid' | 'incomplete';
  current_period_start: Date;
  current_period_end: Date;
  trial_start?: Date;
  trial_end?: Date;
  cancel_at?: Date;
  canceled_at?: Date;
  stripe_subscription_id?: string;
  stripe_customer_id?: string;
  payment_method?: PaymentMethod;
  quantity: number;
  discount?: {
    coupon_id: string;
    percent_off?: number;
    amount_off?: number;
    valid_until?: Date;
  };
  metadata?: Record<string, any>;
  created_at: Date;
  updated_at: Date;
}

interface PaymentMethod {
  id: string;
  type: 'card' | 'bank_account' | 'paypal' | 'invoice';
  is_default: boolean;
  details: {
    brand?: string;
    last4?: string;
    exp_month?: number;
    exp_year?: number;
    bank_name?: string;
    account_last4?: string;
    email?: string;
  };
  stripe_payment_method_id?: string;
  created_at: Date;
}

interface Invoice {
  id: string;
  subscription_id: string;
  organization_id: string;
  invoice_number: string;
  status: 'draft' | 'open' | 'paid' | 'void' | 'uncollectible';
  amount_due: number;
  amount_paid: number;
  currency: string;
  period_start: Date;
  period_end: Date;
  due_date?: Date;
  paid_at?: Date;
  stripe_invoice_id?: string;
  line_items: InvoiceLineItem[];
  pdf_url?: string;
  hosted_invoice_url?: string;
  created_at: Date;
}

interface InvoiceLineItem {
  id: string;
  description: string;
  quantity: number;
  unit_amount: number;
  amount: number;
  currency: string;
  period: {
    start: Date;
    end: Date;
  };
}

interface UsageRecord {
  id: string;
  organization_id: string;
  metric: string;
  quantity: number;
  unit: string;
  timestamp: Date;
  metadata?: Record<string, any>;
}

interface BillingAlert {
  id: string;
  organization_id: string;
  type: 'usage_limit' | 'payment_failed' | 'subscription_ending' | 'trial_ending';
  severity: 'info' | 'warning' | 'critical';
  message: string;
  details: Record<string, any>;
  acknowledged: boolean;
  acknowledged_by?: string;
  acknowledged_at?: Date;
  created_at: Date;
}

interface CheckoutSession {
  id: string;
  organization_id: string;
  plan_id: string;
  status: 'pending' | 'completed' | 'expired' | 'canceled';
  success_url: string;
  cancel_url: string;
  stripe_session_id?: string;
  metadata?: Record<string, any>;
  created_at: Date;
  expires_at: Date;
}

export class BillingService extends EventEmitter {
  private redis: RedisService;
  private multiTenancy: MultiTenancyService;
  private plans: Map<string, BillingPlan> = new Map();
  private subscriptions: Map<string, Subscription> = new Map();
  private stripeClient: any; // Would be Stripe client in production
  
  constructor() {
    super();
    this.redis = getRedis();
    this.multiTenancy = getMultiTenancyService();
    this.initializePlans();
    this.initializeStripe();
  }
  
  // Plan Management
  async createPlan(data: Omit<BillingPlan, 'id'>): Promise<BillingPlan> {
    const plan: BillingPlan = {
      id: this.generatePlanId(),
      ...data
    };
    
    // Create in Stripe if configured
    if (this.stripeClient && !plan.stripe_product_id) {
      const stripeProduct = await this.createStripeProduct(plan);
      const stripePrice = await this.createStripePrice(plan, stripeProduct.id);
      plan.stripe_product_id = stripeProduct.id;
      plan.stripe_price_id = stripePrice.id;
    }
    
    await this.storePlan(plan);
    
    this.emit('plan_created', {
      plan_id: plan.id,
      name: plan.name,
      timestamp: new Date()
    });
    
    return plan;
  }
  
  async updatePlan(
    planId: string,
    updates: Partial<Omit<BillingPlan, 'id'>>
  ): Promise<BillingPlan> {
    const plan = await this.getPlan(planId);
    if (!plan) {
      throw new Error(`Plan '${planId}' not found`);
    }
    
    const updatedPlan: BillingPlan = {
      ...plan,
      ...updates
    };
    
    // Update in Stripe if price changed
    if (this.stripeClient && updates.price && plan.stripe_product_id) {
      const newStripePrice = await this.createStripePrice(updatedPlan, plan.stripe_product_id);
      updatedPlan.stripe_price_id = newStripePrice.id;
    }
    
    await this.storePlan(updatedPlan);
    
    this.emit('plan_updated', {
      plan_id: planId,
      changes: updates,
      timestamp: new Date()
    });
    
    return updatedPlan;
  }
  
  async getPlan(planId: string): Promise<BillingPlan | null> {
    if (this.plans.has(planId)) {
      return this.plans.get(planId)!;
    }
    
    const plan = await this.redis.hget<BillingPlan>('billing_plans', planId);
    if (plan) {
      this.plans.set(planId, plan);
      return plan;
    }
    
    return null;
  }
  
  async getPlans(activeOnly: boolean = true): Promise<BillingPlan[]> {
    const allPlans = await this.redis.hgetall<BillingPlan>('billing_plans');
    let plans = Object.values(allPlans);
    
    if (activeOnly) {
      plans = plans.filter(p => p.is_active);
    }
    
    return plans.sort((a, b) => a.price.amount - b.price.amount);
  }
  
  // Subscription Management
  async createSubscription(
    organizationId: string,
    planId: string,
    paymentMethodId?: string,
    trialDays?: number
  ): Promise<Subscription> {
    // Check for existing active subscription
    const existing = await this.getOrganizationSubscription(organizationId);
    if (existing && ['active', 'trialing'].includes(existing.status)) {
      throw new Error('Organization already has an active subscription');
    }
    
    const plan = await this.getPlan(planId);
    if (!plan) {
      throw new Error(`Plan '${planId}' not found`);
    }
    
    const now = new Date();
    const subscription: Subscription = {
      id: this.generateSubscriptionId(),
      organization_id: organizationId,
      plan_id: planId,
      status: trialDays ? 'trialing' : 'active',
      current_period_start: now,
      current_period_end: this.calculatePeriodEnd(now, plan.price.interval),
      quantity: 1,
      created_at: now,
      updated_at: now
    };
    
    if (trialDays) {
      subscription.trial_start = now;
      subscription.trial_end = new Date(now.getTime() + trialDays * 24 * 60 * 60 * 1000);
      subscription.status = 'trialing';
    }
    
    // Create in Stripe if configured
    if (this.stripeClient && plan.stripe_price_id) {
      const stripeSubscription = await this.createStripeSubscription(
        organizationId,
        plan.stripe_price_id,
        paymentMethodId,
        trialDays
      );
      subscription.stripe_subscription_id = stripeSubscription.id;
      subscription.stripe_customer_id = stripeSubscription.customer;
    }
    
    await this.storeSubscription(subscription);
    
    // Update organization features
    await this.applyPlanFeatures(organizationId, plan);
    
    this.emit('subscription_created', {
      subscription_id: subscription.id,
      organization_id: organizationId,
      plan_id: planId,
      status: subscription.status,
      timestamp: new Date()
    });
    
    // Schedule trial end reminder if applicable
    if (trialDays) {
      this.scheduleTrialEndReminder(subscription);
    }
    
    return subscription;
  }
  
  async updateSubscription(
    subscriptionId: string,
    updates: {
      plan_id?: string;
      quantity?: number;
      payment_method_id?: string;
    }
  ): Promise<Subscription> {
    const subscription = await this.getSubscription(subscriptionId);
    if (!subscription) {
      throw new Error(`Subscription '${subscriptionId}' not found`);
    }
    
    // Handle plan change
    if (updates.plan_id && updates.plan_id !== subscription.plan_id) {
      const newPlan = await this.getPlan(updates.plan_id);
      if (!newPlan) {
        throw new Error(`Plan '${updates.plan_id}' not found`);
      }
      
      // Update in Stripe
      if (this.stripeClient && subscription.stripe_subscription_id) {
        await this.updateStripeSubscription(
          subscription.stripe_subscription_id,
          { price: newPlan.stripe_price_id }
        );
      }
      
      subscription.plan_id = updates.plan_id;
      
      // Apply new plan features
      await this.applyPlanFeatures(subscription.organization_id, newPlan);
    }
    
    if (updates.quantity !== undefined) {
      subscription.quantity = updates.quantity;
    }
    
    subscription.updated_at = new Date();
    await this.storeSubscription(subscription);
    
    this.emit('subscription_updated', {
      subscription_id: subscriptionId,
      changes: updates,
      timestamp: new Date()
    });
    
    return subscription;
  }
  
  async cancelSubscription(
    subscriptionId: string,
    immediately: boolean = false,
    reason?: string
  ): Promise<Subscription> {
    const subscription = await this.getSubscription(subscriptionId);
    if (!subscription) {
      throw new Error(`Subscription '${subscriptionId}' not found`);
    }
    
    if (immediately) {
      subscription.status = 'canceled';
      subscription.canceled_at = new Date();
    } else {
      subscription.cancel_at = subscription.current_period_end;
    }
    
    // Cancel in Stripe
    if (this.stripeClient && subscription.stripe_subscription_id) {
      await this.cancelStripeSubscription(
        subscription.stripe_subscription_id,
        immediately
      );
    }
    
    subscription.updated_at = new Date();
    await this.storeSubscription(subscription);
    
    this.emit('subscription_canceled', {
      subscription_id: subscriptionId,
      organization_id: subscription.organization_id,
      immediately,
      reason,
      timestamp: new Date()
    });
    
    // Create cancellation alert
    await this.createBillingAlert(
      subscription.organization_id,
      'subscription_ending',
      'warning',
      `Your subscription will end on ${subscription.current_period_end.toDateString()}`,
      { reason }
    );
    
    return subscription;
  }
  
  async reactivateSubscription(subscriptionId: string): Promise<Subscription> {
    const subscription = await this.getSubscription(subscriptionId);
    if (!subscription) {
      throw new Error(`Subscription '${subscriptionId}' not found`);
    }
    
    if (subscription.status !== 'canceled' && !subscription.cancel_at) {
      throw new Error('Subscription is not canceled');
    }
    
    subscription.status = 'active';
    subscription.cancel_at = undefined;
    subscription.canceled_at = undefined;
    
    // Reactivate in Stripe
    if (this.stripeClient && subscription.stripe_subscription_id) {
      await this.reactivateStripeSubscription(subscription.stripe_subscription_id);
    }
    
    subscription.updated_at = new Date();
    await this.storeSubscription(subscription);
    
    this.emit('subscription_reactivated', {
      subscription_id: subscriptionId,
      organization_id: subscription.organization_id,
      timestamp: new Date()
    });
    
    return subscription;
  }
  
  async getSubscription(subscriptionId: string): Promise<Subscription | null> {
    if (this.subscriptions.has(subscriptionId)) {
      return this.subscriptions.get(subscriptionId)!;
    }
    
    const subscription = await this.redis.hget<Subscription>('subscriptions', subscriptionId);
    if (subscription) {
      this.subscriptions.set(subscriptionId, subscription);
      return subscription;
    }
    
    return null;
  }
  
  async getOrganizationSubscription(organizationId: string): Promise<Subscription | null> {
    const allSubscriptions = await this.redis.hgetall<Subscription>('subscriptions');
    return Object.values(allSubscriptions).find(
      s => s.organization_id === organizationId
    ) || null;
  }
  
  // Payment Method Management
  async addPaymentMethod(
    organizationId: string,
    paymentMethod: Omit<PaymentMethod, 'id' | 'created_at'>
  ): Promise<PaymentMethod> {
    const method: PaymentMethod = {
      id: this.generatePaymentMethodId(),
      ...paymentMethod,
      created_at: new Date()
    };
    
    // Add to Stripe
    if (this.stripeClient && paymentMethod.stripe_payment_method_id) {
      const customer = await this.getOrCreateStripeCustomer(organizationId);
      await this.attachStripePaymentMethod(
        paymentMethod.stripe_payment_method_id,
        customer.id
      );
    }
    
    await this.redis.hset(`payment_methods:${organizationId}`, method.id, method);
    
    // Set as default if first method
    const methods = await this.getPaymentMethods(organizationId);
    if (methods.length === 1) {
      await this.setDefaultPaymentMethod(organizationId, method.id);
    }
    
    this.emit('payment_method_added', {
      organization_id: organizationId,
      payment_method_id: method.id,
      type: method.type,
      timestamp: new Date()
    });
    
    return method;
  }
  
  async removePaymentMethod(
    organizationId: string,
    paymentMethodId: string
  ): Promise<void> {
    const method = await this.redis.hget<PaymentMethod>(
      `payment_methods:${organizationId}`,
      paymentMethodId
    );
    
    if (!method) {
      throw new Error('Payment method not found');
    }
    
    // Remove from Stripe
    if (this.stripeClient && method.stripe_payment_method_id) {
      await this.detachStripePaymentMethod(method.stripe_payment_method_id);
    }
    
    await this.redis.hdel(`payment_methods:${organizationId}`, paymentMethodId);
    
    this.emit('payment_method_removed', {
      organization_id: organizationId,
      payment_method_id: paymentMethodId,
      timestamp: new Date()
    });
  }
  
  async getPaymentMethods(organizationId: string): Promise<PaymentMethod[]> {
    const methods = await this.redis.hgetall<PaymentMethod>(
      `payment_methods:${organizationId}`
    );
    return Object.values(methods);
  }
  
  async setDefaultPaymentMethod(
    organizationId: string,
    paymentMethodId: string
  ): Promise<void> {
    const methods = await this.getPaymentMethods(organizationId);
    
    for (const method of methods) {
      method.is_default = method.id === paymentMethodId;
      await this.redis.hset(
        `payment_methods:${organizationId}`,
        method.id,
        method
      );
    }
    
    // Update Stripe default
    if (this.stripeClient) {
      const method = methods.find(m => m.id === paymentMethodId);
      if (method?.stripe_payment_method_id) {
        const customer = await this.getOrCreateStripeCustomer(organizationId);
        await this.updateStripeCustomer(customer.id, {
          invoice_settings: {
            default_payment_method: method.stripe_payment_method_id
          }
        });
      }
    }
  }
  
  // Invoice Management
  async getInvoices(
    organizationId: string,
    options?: {
      status?: Invoice['status'];
      limit?: number;
      offset?: number;
    }
  ): Promise<Invoice[]> {
    const allInvoices = await this.redis.hgetall<Invoice>(`invoices:${organizationId}`);
    let invoices = Object.values(allInvoices);
    
    if (options?.status) {
      invoices = invoices.filter(i => i.status === options.status);
    }
    
    // Sort by date descending
    invoices.sort((a, b) => b.created_at.getTime() - a.created_at.getTime());
    
    if (options?.offset !== undefined && options?.limit !== undefined) {
      invoices = invoices.slice(options.offset, options.offset + options.limit);
    }
    
    return invoices;
  }
  
  async getInvoice(organizationId: string, invoiceId: string): Promise<Invoice | null> {
    return await this.redis.hget<Invoice>(`invoices:${organizationId}`, invoiceId);
  }
  
  async downloadInvoice(
    organizationId: string,
    invoiceId: string
  ): Promise<{ url: string } | null> {
    const invoice = await this.getInvoice(organizationId, invoiceId);
    if (!invoice) return null;
    
    if (invoice.pdf_url) {
      return { url: invoice.pdf_url };
    }
    
    // Generate PDF if needed
    if (this.stripeClient && invoice.stripe_invoice_id) {
      const stripeInvoice = await this.getStripeInvoice(invoice.stripe_invoice_id);
      return { url: stripeInvoice.pdf };
    }
    
    return null;
  }
  
  // Usage Tracking
  async recordUsage(
    organizationId: string,
    metric: string,
    quantity: number,
    unit: string = 'unit',
    metadata?: Record<string, any>
  ): Promise<UsageRecord> {
    const record: UsageRecord = {
      id: this.generateUsageRecordId(),
      organization_id: organizationId,
      metric,
      quantity,
      unit,
      timestamp: new Date(),
      metadata
    };
    
    // Store record
    await this.redis.lpush(`usage:${organizationId}:${metric}`, record);
    
    // Update aggregates
    const today = new Date().toISOString().split('T')[0];
    await this.redis.hincrby(
      `usage:aggregate:${organizationId}:${metric}:${today}`,
      'total',
      quantity
    );
    
    // Check usage limits
    await this.checkUsageLimits(organizationId, metric);
    
    // Track in multi-tenancy service
    await this.multiTenancy.trackUsage(organizationId, metric, quantity);
    
    return record;
  }
  
  async getUsageSummary(
    organizationId: string,
    startDate: Date,
    endDate: Date
  ): Promise<Record<string, { total: number; unit: string }>> {
    const summary: Record<string, { total: number; unit: string }> = {};
    
    // Get all metrics
    const metrics = await this.redis.keys(`usage:${organizationId}:*`);
    
    for (const metricKey of metrics) {
      const metric = metricKey.split(':').pop()!;
      if (metric === organizationId) continue;
      
      let total = 0;
      const current = new Date(startDate);
      
      while (current <= endDate) {
        const dateKey = current.toISOString().split('T')[0];
        const dayTotal = await this.redis.hget<number>(
          `usage:aggregate:${organizationId}:${metric}:${dateKey}`,
          'total'
        ) || 0;
        total += dayTotal;
        current.setDate(current.getDate() + 1);
      }
      
      summary[metric] = { total, unit: 'unit' };
    }
    
    return summary;
  }
  
  private async checkUsageLimits(
    organizationId: string,
    metric: string
  ): Promise<void> {
    const subscription = await this.getOrganizationSubscription(organizationId);
    if (!subscription) return;
    
    const plan = await this.getPlan(subscription.plan_id);
    if (!plan) return;
    
    const limit = plan.features[metric];
    if (typeof limit !== 'number') return;
    
    // Get current usage
    const now = new Date();
    const startOfMonth = new Date(now.getFullYear(), now.getMonth(), 1);
    const usage = await this.getUsageSummary(organizationId, startOfMonth, now);
    const currentUsage = usage[metric]?.total || 0;
    
    const percentUsed = (currentUsage / limit) * 100;
    
    // Create alerts at different thresholds
    if (percentUsed >= 100) {
      await this.createBillingAlert(
        organizationId,
        'usage_limit',
        'critical',
        `You have exceeded your ${metric} limit (${currentUsage}/${limit})`,
        { metric, limit, current: currentUsage }
      );
    } else if (percentUsed >= 90) {
      await this.createBillingAlert(
        organizationId,
        'usage_limit',
        'warning',
        `You are approaching your ${metric} limit (${currentUsage}/${limit})`,
        { metric, limit, current: currentUsage }
      );
    }
  }
  
  // Billing Alerts
  async createBillingAlert(
    organizationId: string,
    type: BillingAlert['type'],
    severity: BillingAlert['severity'],
    message: string,
    details: Record<string, any>
  ): Promise<BillingAlert> {
    const alert: BillingAlert = {
      id: this.generateAlertId(),
      organization_id: organizationId,
      type,
      severity,
      message,
      details,
      acknowledged: false,
      created_at: new Date()
    };
    
    await this.redis.hset(`billing_alerts:${organizationId}`, alert.id, alert);
    
    this.emit('billing_alert_created', {
      alert_id: alert.id,
      organization_id: organizationId,
      type,
      severity,
      timestamp: new Date()
    });
    
    // Send notification based on severity
    if (severity === 'critical') {
      await this.sendAlertNotification(organizationId, alert);
    }
    
    return alert;
  }
  
  async acknowledgeAlert(
    organizationId: string,
    alertId: string,
    acknowledgedBy: string
  ): Promise<void> {
    const alert = await this.redis.hget<BillingAlert>(
      `billing_alerts:${organizationId}`,
      alertId
    );
    
    if (!alert) {
      throw new Error('Alert not found');
    }
    
    alert.acknowledged = true;
    alert.acknowledged_by = acknowledgedBy;
    alert.acknowledged_at = new Date();
    
    await this.redis.hset(`billing_alerts:${organizationId}`, alertId, alert);
  }
  
  async getAlerts(
    organizationId: string,
    unacknowledgedOnly: boolean = true
  ): Promise<BillingAlert[]> {
    const alerts = await this.redis.hgetall<BillingAlert>(
      `billing_alerts:${organizationId}`
    );
    
    let result = Object.values(alerts);
    
    if (unacknowledgedOnly) {
      result = result.filter(a => !a.acknowledged);
    }
    
    return result.sort((a, b) => b.created_at.getTime() - a.created_at.getTime());
  }
  
  // Checkout & Payment Processing
  async createCheckoutSession(
    organizationId: string,
    planId: string,
    successUrl: string,
    cancelUrl: string
  ): Promise<CheckoutSession> {
    const plan = await this.getPlan(planId);
    if (!plan) {
      throw new Error(`Plan '${planId}' not found`);
    }
    
    const session: CheckoutSession = {
      id: this.generateSessionId(),
      organization_id: organizationId,
      plan_id: planId,
      status: 'pending',
      success_url: successUrl,
      cancel_url: cancelUrl,
      created_at: new Date(),
      expires_at: new Date(Date.now() + 24 * 60 * 60 * 1000) // 24 hours
    };
    
    // Create Stripe checkout session
    if (this.stripeClient && plan.stripe_price_id) {
      const stripeSession = await this.createStripeCheckoutSession(
        organizationId,
        plan.stripe_price_id,
        successUrl,
        cancelUrl
      );
      session.stripe_session_id = stripeSession.id;
    }
    
    await this.redis.hset('checkout_sessions', session.id, session);
    
    return session;
  }
  
  async processWebhook(
    event: {
      type: string;
      data: Record<string, any>;
    }
  ): Promise<void> {
    switch (event.type) {
      case 'checkout.session.completed':
        await this.handleCheckoutComplete(event.data.object);
        break;
      
      case 'invoice.payment_succeeded':
        await this.handlePaymentSuccess(event.data.object);
        break;
      
      case 'invoice.payment_failed':
        await this.handlePaymentFailure(event.data.object);
        break;
      
      case 'customer.subscription.updated':
        await this.handleSubscriptionUpdate(event.data.object);
        break;
      
      case 'customer.subscription.deleted':
        await this.handleSubscriptionDeleted(event.data.object);
        break;
    }
  }
  
  // Helper Methods
  private async initializePlans(): Promise<void> {
    const defaultPlans: BillingPlan[] = [
      {
        id: 'free',
        name: 'free',
        display_name: 'Free',
        description: 'Perfect for trying out Plinto',
        price: {
          amount: 0,
          currency: 'USD',
          interval: 'monthly'
        },
        features: {
          users: 5,
          teams: 1,
          storage: 1073741824, // 1GB
          api_calls: 1000,
          custom_roles: 0,
          audit_retention_days: 7,
          support_level: 'community',
          sla: false,
          custom_domain: false,
          sso: false,
          advanced_security: false
        },
        is_active: true,
        is_default: true
      },
      {
        id: 'startup',
        name: 'startup',
        display_name: 'Startup',
        description: 'For growing teams',
        price: {
          amount: 49,
          currency: 'USD',
          interval: 'monthly'
        },
        features: {
          users: 20,
          teams: 5,
          storage: 10737418240, // 10GB
          api_calls: 10000,
          custom_roles: 5,
          audit_retention_days: 30,
          support_level: 'email',
          sla: false,
          custom_domain: true,
          sso: false,
          advanced_security: true
        },
        is_active: true,
        is_default: false
      },
      {
        id: 'professional',
        name: 'professional',
        display_name: 'Professional',
        description: 'For established organizations',
        price: {
          amount: 149,
          currency: 'USD',
          interval: 'monthly'
        },
        features: {
          users: 100,
          teams: 20,
          storage: 107374182400, // 100GB
          api_calls: 100000,
          custom_roles: 20,
          audit_retention_days: 90,
          support_level: 'priority',
          sla: true,
          custom_domain: true,
          sso: true,
          advanced_security: true
        },
        is_active: true,
        is_default: false
      },
      {
        id: 'enterprise',
        name: 'enterprise',
        display_name: 'Enterprise',
        description: 'Custom solutions for large organizations',
        price: {
          amount: 499,
          currency: 'USD',
          interval: 'monthly'
        },
        features: {
          users: -1, // unlimited
          teams: -1,
          storage: -1,
          api_calls: -1,
          custom_roles: -1,
          audit_retention_days: 365,
          support_level: 'dedicated',
          sla: true,
          custom_domain: true,
          sso: true,
          advanced_security: true
        },
        is_active: true,
        is_default: false
      }
    ];
    
    for (const plan of defaultPlans) {
      await this.storePlan(plan);
    }
  }
  
  private async initializeStripe(): Promise<void> {
    if (process.env.STRIPE_SECRET_KEY) {
      // In production, would initialize Stripe client
      // this.stripeClient = new Stripe(process.env.STRIPE_SECRET_KEY);
      console.log('Stripe client would be initialized here');
    }
  }
  
  private async storePlan(plan: BillingPlan): Promise<void> {
    await this.redis.hset('billing_plans', plan.id, plan);
    this.plans.set(plan.id, plan);
  }
  
  private async storeSubscription(subscription: Subscription): Promise<void> {
    await this.redis.hset('subscriptions', subscription.id, subscription);
    this.subscriptions.set(subscription.id, subscription);
  }
  
  private async applyPlanFeatures(
    organizationId: string,
    plan: BillingPlan
  ): Promise<void> {
    const tenant = await this.multiTenancy.getTenant(organizationId);
    if (!tenant) return;
    
    await this.multiTenancy.updateTenant(organizationId, {
      features: plan.features,
      limits: {
        users: plan.features.users,
        storage: plan.features.storage,
        api_calls: plan.features.api_calls,
        custom_roles: plan.features.custom_roles,
        teams: plan.features.teams
      },
      metadata: {
        ...tenant.metadata,
        billing_plan: plan.name
      }
    });
  }
  
  private calculatePeriodEnd(start: Date, interval: string): Date {
    const end = new Date(start);
    
    switch (interval) {
      case 'monthly':
        end.setMonth(end.getMonth() + 1);
        break;
      case 'yearly':
        end.setFullYear(end.getFullYear() + 1);
        break;
    }
    
    return end;
  }
  
  private scheduleTrialEndReminder(subscription: Subscription): void {
    if (!subscription.trial_end) return;
    
    // Schedule reminder 3 days before trial ends
    const reminderDate = new Date(subscription.trial_end);
    reminderDate.setDate(reminderDate.getDate() - 3);
    
    if (reminderDate > new Date()) {
      setTimeout(async () => {
        await this.createBillingAlert(
          subscription.organization_id,
          'trial_ending',
          'warning',
          'Your trial ends in 3 days. Add a payment method to continue.',
          { trial_end: subscription.trial_end }
        );
      }, reminderDate.getTime() - Date.now());
    }
  }
  
  private async sendAlertNotification(
    organizationId: string,
    alert: BillingAlert
  ): Promise<void> {
    // Would integrate with notification service
    console.log(`Sending alert notification to organization ${organizationId}:`, alert.message);
  }
  
  // Stripe Integration Methods (stubs)
  private async createStripeProduct(plan: BillingPlan): Promise<any> {
    return { id: `prod_${Math.random().toString(36).substring(2)}` };
  }
  
  private async createStripePrice(plan: BillingPlan, productId: string): Promise<any> {
    return { id: `price_${Math.random().toString(36).substring(2)}` };
  }
  
  private async createStripeSubscription(
    organizationId: string,
    priceId: string,
    paymentMethodId?: string,
    trialDays?: number
  ): Promise<any> {
    return {
      id: `sub_${Math.random().toString(36).substring(2)}`,
      customer: `cus_${Math.random().toString(36).substring(2)}`
    };
  }
  
  private async updateStripeSubscription(
    subscriptionId: string,
    updates: Record<string, any>
  ): Promise<any> {
    return { id: subscriptionId, ...updates };
  }
  
  private async cancelStripeSubscription(
    subscriptionId: string,
    immediately: boolean
  ): Promise<any> {
    return { id: subscriptionId, status: 'canceled' };
  }
  
  private async reactivateStripeSubscription(subscriptionId: string): Promise<any> {
    return { id: subscriptionId, status: 'active' };
  }
  
  private async getOrCreateStripeCustomer(organizationId: string): Promise<any> {
    return { id: `cus_${Math.random().toString(36).substring(2)}` };
  }
  
  private async updateStripeCustomer(customerId: string, updates: Record<string, any>): Promise<any> {
    return { id: customerId, ...updates };
  }
  
  private async attachStripePaymentMethod(paymentMethodId: string, customerId: string): Promise<any> {
    return { id: paymentMethodId, customer: customerId };
  }
  
  private async detachStripePaymentMethod(paymentMethodId: string): Promise<any> {
    return { id: paymentMethodId, customer: null };
  }
  
  private async getStripeInvoice(invoiceId: string): Promise<any> {
    return {
      id: invoiceId,
      pdf: `https://stripe.com/invoices/${invoiceId}/pdf`
    };
  }
  
  private async createStripeCheckoutSession(
    organizationId: string,
    priceId: string,
    successUrl: string,
    cancelUrl: string
  ): Promise<any> {
    return { id: `cs_${Math.random().toString(36).substring(2)}` };
  }
  
  private async handleCheckoutComplete(session: any): Promise<void> {
    // Handle checkout completion
    console.log('Checkout completed:', session);
  }
  
  private async handlePaymentSuccess(invoice: any): Promise<void> {
    // Handle successful payment
    console.log('Payment succeeded:', invoice);
  }
  
  private async handlePaymentFailure(invoice: any): Promise<void> {
    // Handle failed payment
    console.log('Payment failed:', invoice);
  }
  
  private async handleSubscriptionUpdate(subscription: any): Promise<void> {
    // Handle subscription update
    console.log('Subscription updated:', subscription);
  }
  
  private async handleSubscriptionDeleted(subscription: any): Promise<void> {
    // Handle subscription deletion
    console.log('Subscription deleted:', subscription);
  }
  
  // ID Generation
  private generatePlanId(): string {
    return `plan_${Date.now()}_${Math.random().toString(36).substring(2, 9)}`;
  }
  
  private generateSubscriptionId(): string {
    return `sub_${Date.now()}_${Math.random().toString(36).substring(2, 9)}`;
  }
  
  private generatePaymentMethodId(): string {
    return `pm_${Date.now()}_${Math.random().toString(36).substring(2, 9)}`;
  }
  
  private generateUsageRecordId(): string {
    return `usage_${Date.now()}_${Math.random().toString(36).substring(2, 9)}`;
  }
  
  private generateAlertId(): string {
    return `alert_${Date.now()}_${Math.random().toString(36).substring(2, 9)}`;
  }
  
  private generateSessionId(): string {
    return `cs_${Date.now()}_${Math.random().toString(36).substring(2, 9)}`;
  }
}

// Export singleton instance
let billingService: BillingService | null = null;

export function getBillingService(): BillingService {
  if (!billingService) {
    billingService = new BillingService();
  }
  return billingService;
}