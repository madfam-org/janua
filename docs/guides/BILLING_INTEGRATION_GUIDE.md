# Janua Billing Integration Guide

**Last Updated**: November 2025  
**Status**: Production Ready  
**Version**: 1.0

## Overview

Janua includes a comprehensive billing and payment system with support for multiple payment providers. This guide covers the existing implementation and how to integrate billing into your application.

## Architecture

### Payment Provider Abstraction

Janua uses a provider abstraction layer that allows seamless switching between payment processors:

```
┌─────────────────────────────────────────────────────┐
│           PaymentGatewayService                     │
│                                                     │
│  ┌─────────────────────────────────────────────┐   │
│  │    PaymentProviderInterface                  │   │
│  │    - createCustomer()                        │   │
│  │    - createPaymentIntent()                   │   │
│  │    - createSubscription()                    │   │
│  │    - handleWebhook()                         │   │
│  └─────────────────────────────────────────────┘   │
│                                                     │
│  ┌──────────────┐  ┌──────────────┐               │
│  │    Stripe    │  │   Conekta    │               │
│  │   Provider   │  │   Provider   │               │
│  └──────────────┘  └──────────────┘               │
└─────────────────────────────────────────────────────┘
```

### Implemented Providers

| Provider | Status | Best For | Currencies |
|----------|--------|----------|------------|
| **Stripe** | ✅ Production Ready | Global payments, US/EU/LATAM | 45+ currencies |
| **Conekta** | ✅ Production Ready | Mexico (OXXO, SPEI, Cards) | MXN |
| **Polar.sh** | ✅ Production Ready | Merchant of Record, SaaS, Global Tax | Global |

> **📖 For detailed Polar.sh integration, see [POLAR_INTEGRATION_GUIDE.md](./POLAR_INTEGRATION_GUIDE.md)**

## Core Services

### 1. PaymentGatewayService

Location: `packages/core/src/services/payment-gateway.service.ts`

The main entry point for all payment operations:

```typescript
import { PaymentGatewayService } from '@janua/core';

const paymentGateway = new PaymentGatewayService();

// Create a customer
const customerId = await paymentGateway.createCustomer({
  email: 'user@example.com',
  name: 'John Doe',
  provider: 'stripe' // or 'conekta'
});

// Create a payment intent
const paymentIntent = await paymentGateway.createPaymentIntent({
  amount: 2999, // in cents
  currency: 'USD',
  customer_id: customerId,
  description: 'Pro Plan Subscription'
});
```

### 2. BillingService

Location: `packages/core/src/services/billing.service.ts`

Higher-level billing operations including plans, subscriptions, and invoices:

```typescript
import { BillingService } from '@janua/core';

const billing = new BillingService();

// Get available plans
const plans = await billing.getPlans();

// Create a subscription
const subscription = await billing.createSubscription({
  organization_id: 'org_123',
  plan_id: 'pro',
  payment_method_id: 'pm_123'
});

// Get subscription status
const status = await billing.getSubscription(subscriptionId);
```

### 3. Provider-Specific Services

#### Stripe Provider
Location: `packages/core/src/services/providers/stripe.provider.ts`

```typescript
import { StripeProvider } from '@janua/core';

const stripe = new StripeProvider({
  secretKey: process.env.STRIPE_SECRET_KEY,
  publishableKey: process.env.STRIPE_PUBLISHABLE_KEY,
  webhookSecret: process.env.STRIPE_WEBHOOK_SECRET,
  apiVersion: '2023-10-16'
}, redisClient);

await stripe.initialize();
```

**Supported Features:**
- Credit/debit card payments
- ACH bank transfers
- SEPA direct debit
- Apple Pay / Google Pay
- Subscriptions with trials
- Invoicing
- Tax calculation
- Refunds and disputes

#### Conekta Provider
Location: `packages/core/src/services/providers/conekta.provider.ts`

```typescript
import { ConektaProvider } from '@janua/core';

const conekta = new ConektaProvider({
  privateKey: process.env.CONEKTA_PRIVATE_KEY,
  publicKey: process.env.CONEKTA_PUBLIC_KEY,
  webhookSecret: process.env.CONEKTA_WEBHOOK_SECRET,
  sandbox: process.env.NODE_ENV !== 'production'
});
```

**Supported Features:**
- Credit/debit cards (Mexican banks)
- OXXO cash payments
- SPEI bank transfers
- Mexican fiscal entities (RFC)
- Installments (MSI)

## Configuration

### Environment Variables

```env
# Stripe Configuration
STRIPE_SECRET_KEY=sk_live_xxxxx
STRIPE_PUBLISHABLE_KEY=pk_live_xxxxx
STRIPE_WEBHOOK_SECRET=whsec_xxxxx

# Conekta Configuration (Mexico)
CONEKTA_PRIVATE_KEY=key_xxxxx
CONEKTA_PUBLIC_KEY=key_xxxxx
CONEKTA_WEBHOOK_SECRET=whsec_xxxxx
CONEKTA_SANDBOX=false

# Billing Configuration
DEFAULT_CURRENCY=USD
DEFAULT_PAYMENT_PROVIDER=stripe
BILLING_WEBHOOK_URL=https://api.yourapp.com/webhooks/billing
```

### Billing Plans Configuration

Plans are defined in `packages/core/src/config/billing-plans.ts`:

```typescript
export const BILLING_PLANS = {
  free: {
    id: 'free',
    name: 'Free',
    price: { amount: 0, currency: 'USD', interval: 'monthly' },
    features: {
      users: 3,
      teams: 1,
      storage: 1_000_000_000, // 1GB
      api_calls: 10_000,
      sso: false,
      support_level: 'community'
    }
  },
  pro: {
    id: 'pro',
    name: 'Pro',
    price: { amount: 2900, currency: 'USD', interval: 'monthly' },
    stripe_price_id: 'price_xxxxx',
    features: {
      users: 25,
      teams: 5,
      storage: 50_000_000_000, // 50GB
      api_calls: 100_000,
      sso: true,
      support_level: 'email'
    }
  },
  enterprise: {
    id: 'enterprise',
    name: 'Enterprise',
    price: { amount: 0, currency: 'USD', interval: 'monthly' }, // Custom
    features: {
      users: -1, // Unlimited
      teams: -1,
      storage: -1,
      api_calls: -1,
      sso: true,
      support_level: 'dedicated'
    }
  }
};
```

## Integration Patterns

### 1. Checkout Flow

```typescript
// Create checkout session
const session = await paymentGateway.createCheckoutSession({
  customer_id: customerId,
  line_items: [{
    name: 'Pro Plan',
    amount: 2900,
    currency: 'USD',
    quantity: 1
  }],
  success_url: 'https://app.example.com/success?session={CHECKOUT_SESSION_ID}',
  cancel_url: 'https://app.example.com/pricing'
});

// Redirect user to checkout
window.location.href = session.url;
```

### 2. Subscription Management

```typescript
// Upgrade subscription
await billing.updateSubscription(subscriptionId, {
  plan_id: 'enterprise',
  proration_behavior: 'create_prorations'
});

// Cancel subscription
await billing.cancelSubscription(subscriptionId, {
  cancel_at_period_end: true // Don't cancel immediately
});

// Resume canceled subscription
await billing.resumeSubscription(subscriptionId);
```

### 3. Webhook Handling

```typescript
// Express.js webhook handler
app.post('/webhooks/billing/:provider', async (req, res) => {
  const { provider } = req.params;
  const signature = req.headers['stripe-signature'] || req.headers['x-conekta-signature'];
  
  try {
    await paymentGateway.handleWebhook(provider, req.body, signature);
    res.status(200).send('OK');
  } catch (error) {
    console.error('Webhook error:', error);
    res.status(400).send('Webhook Error');
  }
});
```

### 4. Usage-Based Billing

```typescript
// Record usage
await billing.recordUsage({
  organization_id: 'org_123',
  metric: 'api_calls',
  quantity: 1000,
  timestamp: new Date()
});

// Get usage summary
const usage = await billing.getUsageSummary('org_123', {
  start_date: new Date('2025-01-01'),
  end_date: new Date('2025-01-31')
});
```

## Provider Selection Logic

The system automatically selects the best provider based on customer location and use case:

```typescript
// In payment-gateway.service.ts
async selectProvider(customer: Customer): Promise<PaymentProvider> {
  // Mexico → Conekta (better rates, local payment methods like OXXO, SPEI)
  if (customer.address?.country === 'MX') {
    return 'conekta';
  }
  
  // Global → Polar (Merchant of Record handles VAT/GST/sales tax)
  // Recommended for SaaS with international customers
  if (process.env.POLAR_ACCESS_TOKEN) {
    return 'polar';
  }
  
  // Fallback → Stripe (global coverage)
  return 'stripe';
}
```

### Provider Routing Summary

| Customer Location | Recommended Provider | Reason |
|-------------------|---------------------|--------|
| Mexico | Conekta | Local payment methods (OXXO, SPEI), better rates |
| EU/Global | Polar | MoR handles VAT compliance automatically |
| US | Polar or Stripe | Polar handles sales tax; Stripe for custom flows |
| Fallback | Stripe | Universal coverage when others unavailable |

## Type Definitions

### Core Types

```typescript
type PaymentProvider = 'conekta' | 'stripe' | 'polar';
type PaymentStatus = 'pending' | 'processing' | 'succeeded' | 'failed' | 'canceled' | 'refunded';
type Currency = 'MXN' | 'USD' | 'EUR' | 'GBP' | /* ... 40+ currencies */;

interface PaymentIntent {
  id: string;
  provider: PaymentProvider;
  provider_intent_id?: string;
  amount: number;
  currency: Currency;
  status: PaymentStatus;
  customer_id: string;
  organization_id: string;
  payment_method?: PaymentMethod;
  error?: PaymentError;
  created_at: Date;
  updated_at: Date;
}

interface Subscription {
  id: string;
  organization_id: string;
  plan_id: string;
  status: 'trialing' | 'active' | 'past_due' | 'canceled' | 'unpaid';
  current_period_start: Date;
  current_period_end: Date;
  trial_end?: Date;
  cancel_at?: Date;
  stripe_subscription_id?: string;
}
```

## Webhook Events

### Stripe Events Handled
- `checkout.session.completed`
- `customer.subscription.created`
- `customer.subscription.updated`
- `customer.subscription.deleted`
- `invoice.paid`
- `invoice.payment_failed`
- `payment_intent.succeeded`
- `payment_intent.payment_failed`

### Conekta Events Handled
- `order.paid`
- `order.pending_payment`
- `order.expired`
- `charge.paid`
- `charge.refunded`
- `subscription.created`
- `subscription.cancelled`

## Security Considerations

### PCI Compliance
- All card data is handled by payment providers (PCI DSS Level 1)
- No raw card numbers stored in Janua database
- All payments use tokenization

### Webhook Security
- All webhooks verified with provider-specific signatures
- Idempotency keys prevent duplicate processing
- Events logged for audit trail

### Data Protection
- Customer PII encrypted at rest
- Payment method tokens, not raw data
- GDPR-compliant data export/deletion

## Testing

### Stripe Test Cards
```
Success: 4242 4242 4242 4242
Decline: 4000 0000 0000 0002
3D Secure: 4000 0027 6000 3184
```

### Conekta Test Cards (Sandbox)
```
Success: 4242 4242 4242 4242
Decline: 4000 0000 0000 0002
OXXO Reference: Generated automatically
```

## Troubleshooting

### Common Issues

**1. Webhook signature verification failed**
- Verify webhook secret is correctly configured
- Ensure raw request body is passed (not parsed JSON)
- Check webhook URL is publicly accessible

**2. Payment intent creation fails**
- Verify API keys are for correct environment (test vs live)
- Check customer exists in the provider
- Ensure currency is supported

**3. Subscription not activating**
- Check webhook events are being received
- Verify payment method is attached to customer
- Check for failed invoice payments

## Future Roadmap

### Multi-Provider Routing Enhancements (Planned)
See [PAYMENT_INFRASTRUCTURE_ROADMAP.md](../roadmap/PAYMENT_INFRASTRUCTURE_ROADMAP.md) for:
- Advanced automatic provider selection algorithms
- Failover between providers
- Cost optimization routing
- A/B testing payment flows

## API Reference

### PaymentProviderInterface

All providers implement this interface:

```typescript
interface PaymentProviderInterface {
  name: PaymentProvider;
  
  // Customer Management
  createCustomer(customer: Partial<Customer>): Promise<string>;
  updateCustomer(customerId: string, updates: Partial<Customer>): Promise<void>;
  deleteCustomer(customerId: string): Promise<void>;
  
  // Payment Methods
  attachPaymentMethod(customerId: string, paymentMethodId: string): Promise<void>;
  detachPaymentMethod(paymentMethodId: string): Promise<void>;
  listPaymentMethods(customerId: string): Promise<PaymentMethod[]>;
  
  // Payments
  createPaymentIntent(params: CreatePaymentIntentParams): Promise<PaymentIntent>;
  confirmPaymentIntent(intentId: string): Promise<PaymentIntent>;
  cancelPaymentIntent(intentId: string): Promise<void>;
  
  // Checkout
  createCheckoutSession(params: CreateCheckoutParams): Promise<CheckoutSession>;
  
  // Subscriptions
  createSubscription(params: CreateSubscriptionParams): Promise<Subscription>;
  updateSubscription(subscriptionId: string, updates: UpdateSubscriptionParams): Promise<Subscription>;
  cancelSubscription(subscriptionId: string): Promise<void>;
  
  // Refunds
  createRefund(request: RefundRequest): Promise<Refund>;
  
  // Webhooks
  handleWebhook(payload: any, signature: string): Promise<WebhookEvent>;
}
```

## Support

- **Documentation**: This guide and linked references
- **Issues**: GitHub Issues for bug reports
- **Enterprise Support**: Contact sales@janua.dev for dedicated support

---

*Janua Billing Integration Guide | November 2025*
