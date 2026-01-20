/**
 * Organization Billing and Quotas Service
 * Manages subscription tiers, usage tracking, billing cycles, and quota enforcement
 */

import { EventEmitter } from 'events';
import crypto from 'crypto';

export interface SubscriptionPlan {
  id: string;
  name: string;
  display_name: string;
  description: string;
  price_monthly: number;
  price_yearly: number;
  currency: string;
  features: PlanFeature[];
  quotas: PlanQuotas;
  is_active: boolean;
  is_public: boolean;
  trial_days?: number;
  metadata?: Record<string, any>;
}

export interface PlanFeature {
  name: string;
  description: string;
  enabled: boolean;
  value?: string | number | boolean;
}

export interface PlanQuotas {
  max_users: number;
  max_api_calls_per_month: number;
  max_storage_gb: number;
  max_organizations: number;
  max_projects: number;
  max_webhooks: number;
  max_audit_retention_days: number;
  max_sso_connections: number;
  max_custom_roles: number;
  max_api_keys: number;
  rate_limit_per_second: number;
  rate_limit_per_minute: number;
  concurrent_sessions: number;
  data_export_enabled: boolean;
  api_access_enabled: boolean;
  custom_domain_enabled: boolean;
  advanced_analytics_enabled: boolean;
  priority_support: boolean;
}

export interface OrganizationSubscription {
  id: string;
  organization_id: string;
  plan_id: string;
  plan: SubscriptionPlan;
  status: 'active' | 'trialing' | 'past_due' | 'canceled' | 'paused';
  billing_cycle: 'monthly' | 'yearly';
  current_period_start: Date;
  current_period_end: Date;
  trial_start?: Date;
  trial_end?: Date;
  canceled_at?: Date;
  pause_collection?: {
    behavior: 'keep_as_draft' | 'void' | 'mark_uncollectible';
    resumes_at?: Date;
  };
  payment_method?: PaymentMethod;
  billing_email: string;
  tax_info?: TaxInfo;
  discount?: Discount;
  metadata?: Record<string, any>;
}

export interface PaymentMethod {
  id: string;
  type: 'card' | 'bank_account' | 'paypal' | 'invoice';
  last_four?: string;
  brand?: string;
  exp_month?: number;
  exp_year?: number;
  is_default: boolean;
}

export interface TaxInfo {
  tax_id: string;
  tax_id_type: 'eu_vat' | 'us_ein' | 'br_cnpj' | 'other';
  country: string;
  state?: string;
  tax_exempt: boolean;
}

export interface Discount {
  id: string;
  type: 'percentage' | 'fixed';
  value: number;
  duration: 'forever' | 'once' | 'repeating';
  duration_months?: number;
  applied_at: Date;
  expires_at?: Date;
}

export interface UsageRecord {
  id: string;
  organization_id: string;
  metric: UsageMetric;
  value: number;
  timestamp: Date;
  period_start: Date;
  period_end: Date;
  metadata?: Record<string, any>;
}

export type UsageMetric = 
  | 'api_calls'
  | 'storage_bytes'
  | 'active_users'
  | 'webhooks_sent'
  | 'audit_events'
  | 'sessions_created'
  | 'data_transfer_bytes'
  | 'compute_minutes';

export interface UsageSummary {
  organization_id: string;
  period_start: Date;
  period_end: Date;
  metrics: Record<UsageMetric, {
    current: number;
    limit: number;
    percentage: number;
    projected: number;
  }>;
  overage_charges: number;
  warnings: UsageWarning[];
}

export interface UsageWarning {
  metric: UsageMetric;
  level: 'info' | 'warning' | 'critical';
  message: string;
  threshold_percentage: number;
  current_percentage: number;
}

export interface Invoice {
  id: string;
  organization_id: string;
  invoice_number: string;
  status: 'draft' | 'open' | 'paid' | 'void' | 'uncollectible';
  amount_due: number;
  amount_paid: number;
  currency: string;
  period_start: Date;
  period_end: Date;
  due_date: Date;
  paid_at?: Date;
  line_items: InvoiceLineItem[];
  tax_amount: number;
  discount_amount: number;
  pdf_url?: string;
  payment_intent_id?: string;
  metadata?: Record<string, any>;
}

export interface InvoiceLineItem {
  id: string;
  description: string;
  amount: number;
  quantity: number;
  unit_price: number;
  type: 'subscription' | 'usage' | 'overage' | 'addon' | 'credit';
  metadata?: Record<string, any>;
}

export interface QuotaEnforcement {
  metric: UsageMetric;
  current_usage: number;
  quota_limit: number;
  enforcement_action: 'allow' | 'warn' | 'throttle' | 'block';
  grace_period_ends?: Date;
  overage_allowed: boolean;
  overage_rate?: number;
}

export class BillingQuotasService extends EventEmitter {
  private plans: Map<string, SubscriptionPlan> = new Map();
  private subscriptions: Map<string, OrganizationSubscription> = new Map();
  private usage: Map<string, UsageRecord[]> = new Map();
  private invoices: Map<string, Invoice[]> = new Map();
  private quotaCache: Map<string, QuotaEnforcement> = new Map();

  constructor(
    private readonly config: {
      stripe_secret_key?: string;
      enable_overage?: boolean;
      overage_rates?: Record<UsageMetric, number>;
      warning_thresholds?: {
        info: number;    // e.g., 50%
        warning: number;  // e.g., 75%
        critical: number; // e.g., 90%
      };
      grace_period_days?: number;
      auto_upgrade_enabled?: boolean;
    } = {}
  ) {
    super();
    this.initializeDefaultPlans();
    this.startUsageAggregation();
  }

  /**
   * Create or update a subscription plan
   */
  async createPlan(plan: SubscriptionPlan): Promise<SubscriptionPlan> {
    // Validate plan
    if (plan.price_monthly < 0 || plan.price_yearly < 0) {
      throw new Error('Plan prices cannot be negative');
    }

    // Store plan
    this.plans.set(plan.id, plan);

    this.emit('plan:created', { plan_id: plan.id, name: plan.name });

    return plan;
  }

  /**
   * Subscribe organization to a plan
   */
  async subscribeOrganization(params: {
    organization_id: string;
    plan_id: string;
    billing_cycle: 'monthly' | 'yearly';
    billing_email: string;
    payment_method?: PaymentMethod;
    tax_info?: TaxInfo;
    start_trial?: boolean;
  }): Promise<OrganizationSubscription> {
    const plan = this.plans.get(params.plan_id);
    if (!plan) {
      throw new Error('Plan not found');
    }

    // Check if organization already has a subscription
    const existing = this.getOrganizationSubscription(params.organization_id);
    if (existing && existing.status === 'active') {
      throw new Error('Organization already has an active subscription');
    }

    const now = new Date();
    const subscription: OrganizationSubscription = {
      id: crypto.randomUUID(),
      organization_id: params.organization_id,
      plan_id: params.plan_id,
      plan,
      status: params.start_trial && plan.trial_days ? 'trialing' : 'active',
      billing_cycle: params.billing_cycle,
      current_period_start: now,
      current_period_end: this.calculatePeriodEnd(now, params.billing_cycle),
      billing_email: params.billing_email,
      payment_method: params.payment_method,
      tax_info: params.tax_info
    };

    if (params.start_trial && plan.trial_days) {
      subscription.trial_start = now;
      subscription.trial_end = new Date(now.getTime() + plan.trial_days * 86400000);
      subscription.status = 'trialing';
    }

    this.subscriptions.set(params.organization_id, subscription);

    this.emit('subscription:created', {
      organization_id: params.organization_id,
      plan_id: params.plan_id,
      status: subscription.status
    });

    return subscription;
  }

  /**
   * Upgrade or downgrade subscription
   */
  async changeSubscriptionPlan(
    organization_id: string,
    new_plan_id: string,
    immediate: boolean = false
  ): Promise<OrganizationSubscription> {
    const subscription = this.getOrganizationSubscription(organization_id);
    if (!subscription) {
      throw new Error('No active subscription found');
    }

    const newPlan = this.plans.get(new_plan_id);
    if (!newPlan) {
      throw new Error('Plan not found');
    }

    const oldPlanId = subscription.plan_id;
    
    if (immediate) {
      // Immediate change with proration
      subscription.plan_id = new_plan_id;
      subscription.plan = newPlan;
      
      // Calculate proration
      const proration = this.calculateProration(subscription, oldPlanId, new_plan_id);
      
      this.emit('subscription:plan-changed', {
        organization_id,
        old_plan_id: oldPlanId,
        new_plan_id,
        proration
      });
    } else {
      // Schedule change for next billing cycle
      subscription.metadata = subscription.metadata || {};
      subscription.metadata.scheduled_plan_change = {
        plan_id: new_plan_id,
        effective_date: subscription.current_period_end
      };

      this.emit('subscription:plan-change-scheduled', {
        organization_id,
        new_plan_id,
        effective_date: subscription.current_period_end
      });
    }

    return subscription;
  }

  /**
   * Cancel subscription
   */
  async cancelSubscription(
    organization_id: string,
    immediate: boolean = false
  ): Promise<void> {
    const subscription = this.getOrganizationSubscription(organization_id);
    if (!subscription) {
      throw new Error('No active subscription found');
    }

    if (immediate) {
      subscription.status = 'canceled';
      subscription.canceled_at = new Date();
    } else {
      // Cancel at period end
      subscription.canceled_at = subscription.current_period_end;
      subscription.metadata = subscription.metadata || {};
      subscription.metadata.cancel_at_period_end = true;
    }

    this.emit('subscription:canceled', {
      organization_id,
      canceled_at: subscription.canceled_at,
      immediate
    });
  }

  /**
   * Track usage
   */
  async trackUsage(
    organization_id: string,
    metric: UsageMetric,
    value: number,
    metadata?: Record<string, any>
  ): Promise<UsageRecord> {
    const now = new Date();
    const subscription = this.getOrganizationSubscription(organization_id);
    
    if (!subscription) {
      throw new Error('No active subscription found');
    }

    const record: UsageRecord = {
      id: crypto.randomUUID(),
      organization_id,
      metric,
      value,
      timestamp: now,
      period_start: subscription.current_period_start,
      period_end: subscription.current_period_end,
      metadata
    };

    // Store usage record
    if (!this.usage.has(organization_id)) {
      this.usage.set(organization_id, []);
    }
    this.usage.get(organization_id)!.push(record);

    // Check quota enforcement
    await this.checkQuotaEnforcement(organization_id, metric);

    this.emit('usage:tracked', {
      organization_id,
      metric,
      value
    });

    return record;
  }

  /**
   * Check quota enforcement
   */
  async checkQuotaEnforcement(
    organization_id: string,
    metric: UsageMetric
  ): Promise<QuotaEnforcement> {
    const subscription = this.getOrganizationSubscription(organization_id);
    if (!subscription) {
      throw new Error('No active subscription found');
    }

    const usage = await this.getCurrentUsage(organization_id, metric);
    const quota = this.getQuotaLimit(subscription.plan, metric);

    const percentage = (usage / quota) * 100;
    const cacheKey = `${organization_id}:${metric}`;

    const enforcement: QuotaEnforcement = {
      metric,
      current_usage: usage,
      quota_limit: quota,
      enforcement_action: 'allow',
      overage_allowed: this.config.enable_overage || false,
      overage_rate: this.config.overage_rates?.[metric]
    };

    // Determine enforcement action
    if (percentage >= 100) {
      if (this.config.enable_overage) {
        enforcement.enforcement_action = 'allow'; // But track overage
        this.emit('quota:overage', {
          organization_id,
          metric,
          usage,
          quota,
          overage: usage - quota
        });
      } else {
        enforcement.enforcement_action = 'block';
        this.emit('quota:exceeded', {
          organization_id,
          metric,
          usage,
          quota
        });
      }
    } else if (percentage >= (this.config.warning_thresholds?.critical || 90)) {
      enforcement.enforcement_action = 'warn';
      this.emit('quota:critical', {
        organization_id,
        metric,
        usage,
        quota,
        percentage
      });
    } else if (percentage >= (this.config.warning_thresholds?.warning || 75)) {
      enforcement.enforcement_action = 'warn';
      this.emit('quota:warning', {
        organization_id,
        metric,
        usage,
        quota,
        percentage
      });
    }

    // Cache enforcement decision
    this.quotaCache.set(cacheKey, enforcement);

    return enforcement;
  }

  /**
   * Get current usage for a metric
   */
  async getCurrentUsage(
    organization_id: string,
    metric: UsageMetric
  ): Promise<number> {
    const subscription = this.getOrganizationSubscription(organization_id);
    if (!subscription) return 0;

    const records = this.usage.get(organization_id) || [];
    
    // Filter records for current billing period
    const currentPeriodRecords = records.filter(
      r => r.metric === metric &&
           r.timestamp >= subscription.current_period_start &&
           r.timestamp <= subscription.current_period_end
    );

    // Sum usage
    return currentPeriodRecords.reduce((sum, r) => sum + r.value, 0);
  }

  /**
   * Get usage summary
   */
  async getUsageSummary(organization_id: string): Promise<UsageSummary> {
    const subscription = this.getOrganizationSubscription(organization_id);
    if (!subscription) {
      throw new Error('No active subscription found');
    }

    const metrics: UsageSummary['metrics'] = {} as any;
    const warnings: UsageWarning[] = [];

    const allMetrics: UsageMetric[] = [
      'api_calls', 'storage_bytes', 'active_users', 'webhooks_sent',
      'audit_events', 'sessions_created', 'data_transfer_bytes', 'compute_minutes'
    ];

    for (const metric of allMetrics) {
      const current = await this.getCurrentUsage(organization_id, metric);
      const limit = this.getQuotaLimit(subscription.plan, metric);
      const percentage = (current / limit) * 100;
      
      // Project usage for rest of period
      const daysInPeriod = this.getDaysInPeriod(subscription);
      const daysElapsed = this.getDaysElapsed(subscription);
      const projected = daysElapsed > 0 ? (current / daysElapsed) * daysInPeriod : current;

      metrics[metric] = {
        current,
        limit,
        percentage,
        projected
      };

      // Generate warnings
      if (percentage >= (this.config.warning_thresholds?.critical || 90)) {
        warnings.push({
          metric,
          level: 'critical',
          message: `${metric} usage is at ${percentage.toFixed(1)}% of limit`,
          threshold_percentage: this.config.warning_thresholds?.critical || 90,
          current_percentage: percentage
        });
      } else if (percentage >= (this.config.warning_thresholds?.warning || 75)) {
        warnings.push({
          metric,
          level: 'warning',
          message: `${metric} usage is at ${percentage.toFixed(1)}% of limit`,
          threshold_percentage: this.config.warning_thresholds?.warning || 75,
          current_percentage: percentage
        });
      } else if (projected > limit) {
        warnings.push({
          metric,
          level: 'info',
          message: `${metric} projected to exceed limit by end of period`,
          threshold_percentage: 100,
          current_percentage: (projected / limit) * 100
        });
      }
    }

    // Calculate overage charges
    const overageCharges = await this.calculateOverageCharges(organization_id);

    return {
      organization_id,
      period_start: subscription.current_period_start,
      period_end: subscription.current_period_end,
      metrics,
      overage_charges: overageCharges,
      warnings
    };
  }

  /**
   * Generate invoice
   */
  async generateInvoice(organization_id: string): Promise<Invoice> {
    const subscription = this.getOrganizationSubscription(organization_id);
    if (!subscription) {
      throw new Error('No active subscription found');
    }

    const lineItems: InvoiceLineItem[] = [];

    // Base subscription charge
    const baseAmount = subscription.billing_cycle === 'monthly'
      ? subscription.plan.price_monthly
      : subscription.plan.price_yearly;

    lineItems.push({
      id: crypto.randomUUID(),
      description: `${subscription.plan.display_name} - ${subscription.billing_cycle} subscription`,
      amount: baseAmount,
      quantity: 1,
      unit_price: baseAmount,
      type: 'subscription'
    });

    // Add overage charges
    const overageCharges = await this.calculateOverageCharges(organization_id);
    if (overageCharges > 0) {
      lineItems.push({
        id: crypto.randomUUID(),
        description: 'Usage overage charges',
        amount: overageCharges,
        quantity: 1,
        unit_price: overageCharges,
        type: 'overage'
      });
    }

    // Apply discount
    let discountAmount = 0;
    if (subscription.discount) {
      if (subscription.discount.type === 'percentage') {
        discountAmount = baseAmount * (subscription.discount.value / 100);
      } else {
        discountAmount = subscription.discount.value;
      }

      lineItems.push({
        id: crypto.randomUUID(),
        description: 'Discount',
        amount: -discountAmount,
        quantity: 1,
        unit_price: -discountAmount,
        type: 'credit'
      });
    }

    // Calculate tax
    const subtotal = lineItems.reduce((sum, item) => sum + item.amount, 0);
    const taxAmount = this.calculateTax(subtotal, subscription.tax_info);

    const invoice: Invoice = {
      id: crypto.randomUUID(),
      organization_id,
      invoice_number: this.generateInvoiceNumber(),
      status: 'draft',
      amount_due: subtotal + taxAmount,
      amount_paid: 0,
      currency: subscription.plan.currency,
      period_start: subscription.current_period_start,
      period_end: subscription.current_period_end,
      due_date: new Date(subscription.current_period_end.getTime() + 7 * 86400000), // 7 days after period end
      line_items: lineItems,
      tax_amount: taxAmount,
      discount_amount: discountAmount
    };

    // Store invoice
    if (!this.invoices.has(organization_id)) {
      this.invoices.set(organization_id, []);
    }
    this.invoices.get(organization_id)!.push(invoice);

    this.emit('invoice:generated', {
      organization_id,
      invoice_id: invoice.id,
      amount_due: invoice.amount_due
    });

    return invoice;
  }

  /**
   * Process payment for invoice
   */
  async processPayment(
    invoice_id: string,
    payment_method_id: string
  ): Promise<Invoice> {
    // Find invoice
    let targetInvoice: Invoice | null = null;
    
    for (const invoiceList of this.invoices.values()) {
      const invoice = invoiceList.find(i => i.id === invoice_id);
      if (invoice) {
        targetInvoice = invoice;
        break;
      }
    }

    if (!targetInvoice) {
      throw new Error('Invoice not found');
    }

    if (targetInvoice.status === 'paid') {
      throw new Error('Invoice already paid');
    }

    // In production, integrate with payment processor (Stripe, etc.)
    // For now, mark as paid
    targetInvoice.status = 'paid';
    targetInvoice.paid_at = new Date();
    targetInvoice.amount_paid = targetInvoice.amount_due;

    this.emit('invoice:paid', {
      invoice_id: targetInvoice.id,
      organization_id: targetInvoice.organization_id,
      amount_paid: targetInvoice.amount_paid
    });

    return targetInvoice;
  }

  /**
   * Get organization subscription
   */
  getOrganizationSubscription(organization_id: string): OrganizationSubscription | null {
    return this.subscriptions.get(organization_id) || null;
  }

  /**
   * Get organization invoices
   */
  getOrganizationInvoices(
    organization_id: string,
    filters?: {
      status?: Invoice['status'];
      since?: Date;
    }
  ): Invoice[] {
    let invoices = this.invoices.get(organization_id) || [];

    if (filters) {
      if (filters.status) {
        invoices = invoices.filter(i => i.status === filters.status);
      }
      if (filters.since) {
        invoices = invoices.filter(i => i.period_start >= filters.since!);
      }
    }

    return invoices.sort((a, b) => b.period_start.getTime() - a.period_start.getTime());
  }

  /**
   * Get available plans
   */
  getAvailablePlans(): SubscriptionPlan[] {
    return Array.from(this.plans.values()).filter(p => p.is_active && p.is_public);
  }

  /**
   * Private: Initialize default plans
   */
  private initializeDefaultPlans(): void {
    const defaultPlans: SubscriptionPlan[] = [
      {
        id: 'free',
        name: 'free',
        display_name: 'Free',
        description: 'Perfect for trying out Janua',
        price_monthly: 0,
        price_yearly: 0,
        currency: 'USD',
        features: [
          { name: 'Basic Authentication', description: 'Email/password auth', enabled: true },
          { name: 'API Access', description: 'Limited API access', enabled: true }
        ],
        quotas: {
          max_users: 10,
          max_api_calls_per_month: 10000,
          max_storage_gb: 1,
          max_organizations: 1,
          max_projects: 3,
          max_webhooks: 5,
          max_audit_retention_days: 7,
          max_sso_connections: 0,
          max_custom_roles: 0,
          max_api_keys: 2,
          rate_limit_per_second: 10,
          rate_limit_per_minute: 100,
          concurrent_sessions: 5,
          data_export_enabled: false,
          api_access_enabled: true,
          custom_domain_enabled: false,
          advanced_analytics_enabled: false,
          priority_support: false
        },
        is_active: true,
        is_public: true,
        trial_days: 0
      },
      {
        id: 'pro',
        name: 'pro',
        display_name: 'Pro',
        description: 'For growing teams',
        price_monthly: 49,
        price_yearly: 490,
        currency: 'USD',
        features: [
          { name: 'All Free Features', description: 'Everything in Free', enabled: true },
          { name: 'SSO', description: 'Single Sign-On', enabled: true },
          { name: 'Advanced MFA', description: 'All MFA methods', enabled: true },
          { name: 'Custom Roles', description: 'Create custom roles', enabled: true }
        ],
        quotas: {
          max_users: 100,
          max_api_calls_per_month: 100000,
          max_storage_gb: 10,
          max_organizations: 5,
          max_projects: 20,
          max_webhooks: 50,
          max_audit_retention_days: 30,
          max_sso_connections: 2,
          max_custom_roles: 10,
          max_api_keys: 20,
          rate_limit_per_second: 50,
          rate_limit_per_minute: 1000,
          concurrent_sessions: 50,
          data_export_enabled: true,
          api_access_enabled: true,
          custom_domain_enabled: false,
          advanced_analytics_enabled: true,
          priority_support: false
        },
        is_active: true,
        is_public: true,
        trial_days: 14
      },
      {
        id: 'enterprise',
        name: 'enterprise',
        display_name: 'Enterprise',
        description: 'For large organizations',
        price_monthly: 499,
        price_yearly: 4990,
        currency: 'USD',
        features: [
          { name: 'All Pro Features', description: 'Everything in Pro', enabled: true },
          { name: 'Custom Domain', description: 'Use your own domain', enabled: true },
          { name: 'Unlimited SSO', description: 'Unlimited SSO connections', enabled: true },
          { name: 'Priority Support', description: '24/7 priority support', enabled: true },
          { name: 'SLA', description: '99.99% uptime SLA', enabled: true }
        ],
        quotas: {
          max_users: 999999,
          max_api_calls_per_month: 999999999,
          max_storage_gb: 1000,
          max_organizations: 999999,
          max_projects: 999999,
          max_webhooks: 999999,
          max_audit_retention_days: 365,
          max_sso_connections: 999999,
          max_custom_roles: 999999,
          max_api_keys: 999999,
          rate_limit_per_second: 500,
          rate_limit_per_minute: 10000,
          concurrent_sessions: 999999,
          data_export_enabled: true,
          api_access_enabled: true,
          custom_domain_enabled: true,
          advanced_analytics_enabled: true,
          priority_support: true
        },
        is_active: true,
        is_public: true,
        trial_days: 30
      }
    ];

    for (const plan of defaultPlans) {
      this.plans.set(plan.id, plan);
    }
  }

  /**
   * Private: Get quota limit for metric
   */
  private getQuotaLimit(plan: SubscriptionPlan, metric: UsageMetric): number {
    const quotaMap: Record<UsageMetric, number> = {
      api_calls: plan.quotas.max_api_calls_per_month,
      storage_bytes: plan.quotas.max_storage_gb * 1073741824, // GB to bytes
      active_users: plan.quotas.max_users,
      webhooks_sent: plan.quotas.max_webhooks * 1000, // Assuming 1000 per webhook
      audit_events: plan.quotas.max_audit_retention_days * 10000, // Estimate
      sessions_created: plan.quotas.concurrent_sessions * 100,
      data_transfer_bytes: plan.quotas.max_storage_gb * 10737418240, // 10x storage
      compute_minutes: plan.quotas.max_api_calls_per_month / 100 // Estimate
    };

    return quotaMap[metric] || 0;
  }

  /**
   * Private: Calculate period end
   */
  private calculatePeriodEnd(start: Date, cycle: 'monthly' | 'yearly'): Date {
    const end = new Date(start);
    if (cycle === 'monthly') {
      end.setMonth(end.getMonth() + 1);
    } else {
      end.setFullYear(end.getFullYear() + 1);
    }
    return end;
  }

  /**
   * Private: Calculate proration
   */
  private calculateProration(
    subscription: OrganizationSubscription,
    old_plan_id: string,
    new_plan_id: string
  ): number {
    const oldPlan = this.plans.get(old_plan_id);
    const newPlan = this.plans.get(new_plan_id);
    
    if (!oldPlan || !newPlan) return 0;

    const daysRemaining = this.getDaysRemaining(subscription);
    const daysInPeriod = this.getDaysInPeriod(subscription);
    
    const oldDailyRate = subscription.billing_cycle === 'monthly'
      ? oldPlan.price_monthly / daysInPeriod
      : oldPlan.price_yearly / 365;

    const newDailyRate = subscription.billing_cycle === 'monthly'
      ? newPlan.price_monthly / daysInPeriod
      : newPlan.price_yearly / 365;

    return (newDailyRate - oldDailyRate) * daysRemaining;
  }

  /**
   * Private: Calculate overage charges
   */
  private async calculateOverageCharges(organization_id: string): Promise<number> {
    if (!this.config.enable_overage) return 0;

    const subscription = this.getOrganizationSubscription(organization_id);
    if (!subscription) return 0;

    let totalOverage = 0;

    const metrics: UsageMetric[] = [
      'api_calls', 'storage_bytes', 'webhooks_sent', 'data_transfer_bytes'
    ];

    for (const metric of metrics) {
      const usage = await this.getCurrentUsage(organization_id, metric);
      const limit = this.getQuotaLimit(subscription.plan, metric);
      
      if (usage > limit) {
        const overage = usage - limit;
        const rate = this.config.overage_rates?.[metric] || 0;
        totalOverage += overage * rate;
      }
    }

    return totalOverage;
  }

  /**
   * Private: Calculate tax
   */
  private calculateTax(amount: number, taxInfo?: TaxInfo): number {
    if (!taxInfo || taxInfo.tax_exempt) return 0;

    // Simplified tax calculation
    // In production, integrate with tax calculation service
    const taxRates: Record<string, number> = {
      'US': 0.08,
      'EU': 0.20,
      'GB': 0.20,
      'CA': 0.13
    };

    const rate = taxRates[taxInfo.country] || 0;
    return amount * rate;
  }

  /**
   * Private: Generate invoice number
   */
  private generateInvoiceNumber(): string {
    const date = new Date();
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const random = Math.floor(Math.random() * 10000).toString().padStart(4, '0');
    
    return `INV-${year}${month}-${random}`;
  }

  /**
   * Private: Get days in period
   */
  private getDaysInPeriod(subscription: OrganizationSubscription): number {
    const diff = subscription.current_period_end.getTime() - subscription.current_period_start.getTime();
    return Math.floor(diff / 86400000);
  }

  /**
   * Private: Get days elapsed
   */
  private getDaysElapsed(subscription: OrganizationSubscription): number {
    const diff = Date.now() - subscription.current_period_start.getTime();
    return Math.floor(diff / 86400000);
  }

  /**
   * Private: Get days remaining
   */
  private getDaysRemaining(subscription: OrganizationSubscription): number {
    const diff = subscription.current_period_end.getTime() - Date.now();
    return Math.max(0, Math.floor(diff / 86400000));
  }

  /**
   * Private: Start usage aggregation
   */
  private startUsageAggregation(): void {
    // Aggregate usage every hour
    setInterval(() => {
      this.aggregateUsage();
    }, 3600000);
  }

  /**
   * Private: Aggregate usage
   */
  private aggregateUsage(): void {
    // Clean up old usage records
    const thirtyDaysAgo = new Date(Date.now() - 30 * 86400000);

    for (const [orgId, records] of this.usage) {
      const filtered = records.filter(r => r.timestamp > thirtyDaysAgo);
      this.usage.set(orgId, filtered);
    }
  }
}

// Export factory function
export function createBillingQuotasService(config?: any): BillingQuotasService {
  return new BillingQuotasService(config);
}