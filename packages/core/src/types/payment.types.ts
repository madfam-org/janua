// Re-export payment types from payment gateway service for convenience
import type {
  PaymentProvider as PaymentProviderType
} from '../services/payment-gateway.service';

export {
  PaymentProvider,
  PaymentStatus,
  Currency,
  PaymentMethod,
  PaymentIntent,
  Customer,
  Address,
  TaxInfo,
  CheckoutSession,
  LineItem,
  RefundRequest,
  ComplianceCheck,
  PaymentProviderInterface
} from '../services/payment-gateway.service';

// Additional types needed by providers
export type SubscriptionStatus = 'active' | 'inactive' | 'canceled' | 'past_due' | 'trialing' | 'pending' | 'paused';
export type RefundStatus = 'pending' | 'succeeded' | 'failed' | 'canceled';

export interface Subscription {
  id: string;
  customer_id: string;
  status: SubscriptionStatus;
  plan_id: string;
  current_period_start: Date;
  current_period_end: Date;
  cancel_at_period_end: boolean;
  canceled_at?: Date;
  trial_start?: Date;
  trial_end?: Date;
  provider?: PaymentProviderType;
  metadata?: Record<string, any>;
}

export interface Webhook {
  id: string;
  url?: string;
  events: string[];
  secret: string;
  active: boolean;
  type?: string;
  data?: any;
  created_at: Date;
  updated_at: Date;
}