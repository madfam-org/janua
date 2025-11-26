# Polar.sh Integration Guide

Polar.sh is Janua's **Merchant of Record (MoR)** payment provider, handling global tax compliance (VAT, GST, sales tax) automatically. This guide covers complete integration from quick start to advanced usage.

## Table of Contents

- [Quick Start](#quick-start)
- [Configuration](#configuration)
- [Provider Architecture](#provider-architecture)
- [TypeScript SDK Plugin](#typescript-sdk-plugin)
- [React Components](#react-components)
- [Checkout Integration](#checkout-integration)
- [Subscription Management](#subscription-management)
- [Customer Portal](#customer-portal)
- [Usage-Based Billing](#usage-based-billing)
- [Webhook Integration](#webhook-integration)
- [Provider Routing](#provider-routing)
- [Testing](#testing)
- [Troubleshooting](#troubleshooting)

---

## Quick Start

Get Polar.sh integrated in under 5 minutes:

### 1. Set Environment Variables

```bash
# Required
POLAR_ACCESS_TOKEN=polar_at_xxx
POLAR_ORGANIZATION_ID=org_xxx

# Optional
POLAR_WEBHOOK_SECRET=whsec_xxx
POLAR_SANDBOX=true  # Set to false for production
POLAR_AUTO_CREATE_CUSTOMERS=true
```

### 2. Backend: Provider Auto-Initializes

The Polar provider initializes automatically in `payment-gateway.service.ts` when `POLAR_ACCESS_TOKEN` is set:

```typescript
// No manual initialization needed - automatic when env vars are present
const gateway = PaymentGatewayService.getInstance(redis, logger);
```

### 3. Frontend: Add Checkout Button

```tsx
import { PolarCheckoutButton } from '@janua/ui/components/payments';

function PricingPage() {
  return (
    <PolarCheckoutButton
      organizationId="org_xxx"
      productId="prod_xxx"
      variant="primary"
      size="lg"
    >
      Subscribe Now
    </PolarCheckoutButton>
  );
}
```

That's it! Polar handles checkout, payment processing, and tax compliance automatically.

---

## Configuration

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `POLAR_ACCESS_TOKEN` | ✅ | API access token from Polar dashboard |
| `POLAR_ORGANIZATION_ID` | ✅ | Your Polar organization ID |
| `POLAR_WEBHOOK_SECRET` | ⚠️ | Required for webhook validation |
| `POLAR_SANDBOX` | ❌ | Enable sandbox mode (default: false) |
| `POLAR_AUTO_CREATE_CUSTOMERS` | ❌ | Auto-create customers on checkout (default: false) |

### Provider Configuration Object

```typescript
interface PolarConfig {
  accessToken: string;           // Polar API access token
  organizationId?: string;       // Default organization ID
  webhookSecret: string;         // Webhook signature validation
  sandbox?: boolean;             // Use sandbox environment
  autoCreateCustomers?: boolean; // Auto-create on checkout
  defaultSuccessUrl?: string;    // Redirect after successful checkout
  defaultCancelUrl?: string;     // Redirect on checkout cancel
}
```

### Obtaining Credentials

1. **Access Token**: Polar Dashboard → Settings → API Keys → Create Token
2. **Organization ID**: Polar Dashboard → Organization → Settings (in URL: `polar.sh/org_xxx`)
3. **Webhook Secret**: Polar Dashboard → Settings → Webhooks → Create Endpoint

---

## Provider Architecture

### Class Overview

```typescript
class PolarProvider extends EventEmitter implements PaymentProviderInterface {
  readonly name: PaymentProvider = 'polar';
  
  // Customer Management
  createCustomer(customer: Partial<Customer>): Promise<string>
  updateCustomer(customerId: string, updates: Partial<Customer>): Promise<void>
  deleteCustomer(customerId: string): Promise<void>
  
  // Checkout
  createCheckoutSession(params: CheckoutParams): Promise<CheckoutSession>
  
  // Subscriptions
  createSubscription(params: SubscriptionParams): Promise<Subscription>
  cancelSubscription(subscriptionId: string, immediate?: boolean): Promise<Subscription>
  
  // Portal
  createCustomerPortalSession(customerId: string): Promise<string>
  
  // Usage Billing
  ingestUsageEvent(params: UsageEventParams): Promise<void>
  
  // Webhooks
  validateWebhookSignature(payload: string, signature: string): boolean
  processWebhookEvent(event: PolarWebhookEvent): Promise<void>
}
```

### Events Emitted

```typescript
// Listen to provider events
polar.on('checkout.completed', (data) => {
  console.log('Checkout completed:', data.checkoutId);
});

polar.on('subscription.created', (data) => {
  console.log('New subscription:', data.subscriptionId);
});

polar.on('subscription.updated', (data) => {
  console.log('Subscription updated:', data.subscriptionId);
});

polar.on('subscription.canceled', (data) => {
  console.log('Subscription canceled:', data.subscriptionId);
});
```

---

## TypeScript SDK Plugin

### Installation & Setup

```typescript
import { JanuaClient } from '@janua/typescript-sdk';
import { createPolarPlugin } from '@janua/typescript-sdk/plugins';

const client = new JanuaClient({
  apiKey: 'your-api-key',
  baseUrl: 'https://api.yourdomain.com'
});

// Create and use the Polar plugin
const polar = createPolarPlugin({
  defaultSuccessUrl: 'https://app.yourdomain.com/success',
  defaultCancelUrl: 'https://app.yourdomain.com/pricing'
});

// Attach client for API calls
polar.setClient(client);
```

### Plugin Methods

#### Checkout

```typescript
// Create checkout session (returns session data)
const session = await polar.createCheckout({
  organizationId: 'org_xxx',
  productId: 'prod_xxx',
  customerEmail: 'user@example.com',
  successUrl: 'https://app.example.com/success',
  metadata: { userId: 'user_123' }
});

console.log(session.url);  // Redirect URL
console.log(session.id);   // Session ID

// Direct redirect to checkout
await polar.checkout({
  organizationId: 'org_xxx',
  productId: 'prod_xxx'
});
// Browser redirects automatically
```

#### Subscriptions

```typescript
// Get current subscription
const subscription = await polar.getSubscription('org_xxx');

if (subscription) {
  console.log(subscription.status);     // 'active' | 'canceled' | 'past_due'
  console.log(subscription.plan);       // Plan name
  console.log(subscription.currentPeriodEnd);  // Period end date
}

// Check subscription status
const hasActive = await polar.hasActiveSubscription('org_xxx');
const hasPro = await polar.hasPlan('org_xxx', 'pro');

// Cancel subscription
const canceled = await polar.cancelSubscription(
  'sub_xxx',
  true  // cancelAtPeriodEnd - keeps active until period ends
);
```

#### Customer Portal

```typescript
// Get portal URL
const portalUrl = await polar.getCustomerPortalUrl('org_xxx');

// Or redirect directly
await polar.redirectToPortal('org_xxx');
```

#### Usage-Based Billing

```typescript
// Ingest usage event
await polar.ingestUsage('org_xxx', {
  name: 'api_calls',
  value: 150,
  timestamp: new Date().toISOString(),
  customerId: 'cust_xxx',
  metadata: {
    endpoint: '/api/v1/data',
    method: 'GET'
  }
});
```

---

## React Components

### PolarCheckoutButton

Full-featured checkout button with loading states and error handling.

```tsx
import { PolarCheckoutButton } from '@janua/ui/components/payments';

// Basic usage
<PolarCheckoutButton
  organizationId="org_xxx"
  productId="prod_xxx"
>
  Subscribe
</PolarCheckoutButton>

// Full configuration
<PolarCheckoutButton
  organizationId="org_xxx"
  productId="prod_xxx"
  plan="pro"
  successUrl="/dashboard?upgraded=true"
  variant="primary"
  size="lg"
  fullWidth
  showIcon
  client={januaClient}
  onCheckoutStart={() => trackEvent('checkout_started')}
  onCheckoutComplete={(session) => trackEvent('checkout_complete', session)}
  onError={(error) => showToast(error.message)}
  disabled={!isAuthenticated}
  className="my-custom-class"
>
  Upgrade to Pro - $29/mo
</PolarCheckoutButton>
```

#### Props

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `organizationId` | `string` | required | Polar organization ID |
| `productId` | `string` | - | Specific product ID |
| `plan` | `string` | - | Plan name (alternative to productId) |
| `successUrl` | `string` | current URL | Redirect after success |
| `variant` | `'default' \| 'primary' \| 'secondary' \| 'outline' \| 'ghost'` | `'default'` | Button style |
| `size` | `'sm' \| 'md' \| 'lg' \| 'xl'` | `'md'` | Button size |
| `fullWidth` | `boolean` | `false` | Full width button |
| `showIcon` | `boolean` | `true` | Show credit card icon |
| `client` | `JanuaClient` | - | SDK client instance |
| `onCheckoutStart` | `() => void` | - | Called when checkout starts |
| `onCheckoutComplete` | `(session) => void` | - | Called on success |
| `onError` | `(error) => void` | - | Called on error |

### PolarCustomerPortalButton

```tsx
import { PolarCustomerPortalButton } from '@janua/ui/components/payments';

<PolarCustomerPortalButton
  organizationId="org_xxx"
  variant="outline"
  client={client}
>
  Manage Subscription
</PolarCustomerPortalButton>
```

### PolarCustomerPortalCard

Full card component for subscription management section.

```tsx
import { PolarCustomerPortalCard } from '@janua/ui/components/payments';

<PolarCustomerPortalCard
  organizationId="org_xxx"
  title="Subscription Settings"
  description="Manage your billing, update payment methods, and view invoices."
  client={client}
/>
```

### PolarSubscriptionStatus

Display current subscription status with actions.

```tsx
import { PolarSubscriptionStatus } from '@janua/ui/components/payments';

// Full featured
<PolarSubscriptionStatus
  organizationId="org_xxx"
  client={client}
  showActions
  showCancelButton
  onSubscriptionChange={(sub) => refreshUserData()}
  onCancel={() => showConfirmation()}
  onUpgrade={() => navigate('/pricing')}
/>

// Compact version for headers/sidebars
<PolarSubscriptionStatus
  organizationId="org_xxx"
  client={client}
  compact
/>
```

#### Props

| Prop | Type | Description |
|------|------|-------------|
| `organizationId` | `string` | Polar organization ID |
| `client` | `JanuaClient` | SDK client instance |
| `showActions` | `boolean` | Show action buttons |
| `showCancelButton` | `boolean` | Show cancel button |
| `compact` | `boolean` | Compact display mode |
| `onSubscriptionChange` | `(sub) => void` | Subscription state change callback |
| `onCancel` | `() => void` | Cancel button callback |
| `onUpgrade` | `() => void` | Upgrade button callback |

---

## Checkout Integration

### Server-Side Checkout

```typescript
import { PaymentGatewayService } from '@janua/core/services';

const gateway = PaymentGatewayService.getInstance(redis, logger);

// Create checkout session
const session = await gateway.createCheckoutSession({
  provider: 'polar',
  customerId: 'cust_xxx',
  priceId: 'price_xxx',
  successUrl: 'https://app.example.com/success',
  cancelUrl: 'https://app.example.com/cancel',
  metadata: {
    userId: 'user_123',
    planType: 'pro'
  }
});

// Return URL to frontend
res.json({ checkoutUrl: session.url });
```

### Client-Side Redirect

```typescript
// Using SDK plugin
const polar = createPolarPlugin();
polar.setClient(client);

await polar.checkout({
  organizationId: 'org_xxx',
  productId: 'prod_xxx'
});
// Automatically redirects to Polar checkout
```

### Handling Success

```typescript
// In your success page/callback
import { useSearchParams } from 'react-router-dom';

function SuccessPage() {
  const [params] = useSearchParams();
  const checkoutId = params.get('checkout_id');
  
  useEffect(() => {
    if (checkoutId) {
      // Verify checkout and provision access
      verifyCheckout(checkoutId);
    }
  }, [checkoutId]);
  
  return <div>Thank you for subscribing!</div>;
}
```

---

## Subscription Management

### Creating Subscriptions

```typescript
const gateway = PaymentGatewayService.getInstance(redis, logger);

const subscription = await gateway.createSubscription({
  provider: 'polar',
  customerId: 'cust_xxx',
  priceId: 'price_xxx',
  metadata: {
    organizationId: 'org_xxx'
  }
});

console.log(subscription.id);
console.log(subscription.status);  // 'active'
```

### Retrieving Subscription Status

```typescript
// Via SDK plugin
const polar = createPolarPlugin();
const subscription = await polar.getSubscription('org_xxx');

// Check helpers
const isActive = await polar.hasActiveSubscription('org_xxx');
const isPro = await polar.hasPlan('org_xxx', 'pro');
```

### Canceling Subscriptions

```typescript
// Cancel at period end (recommended)
const subscription = await polar.cancelSubscription('sub_xxx', true);
// subscription.status === 'active'
// subscription.cancelAtPeriodEnd === true

// Cancel immediately
const subscription = await polar.cancelSubscription('sub_xxx', false);
// subscription.status === 'canceled'
```

### Subscription Lifecycle

```
checkout.completed → subscription.created → subscription.active
                                                    ↓
                                          subscription.updated (renewals)
                                                    ↓
                           subscription.canceled ← user cancels
                                                    ↓
                                          subscription.ended (access removed)
```

---

## Customer Portal

Polar's customer portal lets users self-manage subscriptions, payment methods, and view invoices.

### Generate Portal URL

```typescript
// Server-side
const gateway = PaymentGatewayService.getInstance(redis, logger);
const portalUrl = await gateway.createCustomerPortalSession('polar', 'cust_xxx');

// Client-side via plugin
const polar = createPolarPlugin();
const portalUrl = await polar.getCustomerPortalUrl('org_xxx');
```

### Portal Features

- ✅ View current subscription and plan
- ✅ Update payment method
- ✅ View and download invoices
- ✅ Cancel or pause subscription
- ✅ Update billing information
- ✅ View upcoming charges

### Customizing Portal

Configure portal appearance in Polar Dashboard → Settings → Customer Portal:

- Brand colors and logo
- Available actions (show/hide cancel button)
- Custom terms of service link
- Support contact information

---

## Usage-Based Billing

Polar supports metered/usage-based billing for API calls, storage, compute, etc.

### Ingesting Usage Events

```typescript
// Server-side: ingest usage after each API call
const polar = gateway.getProvider('polar') as PolarProvider;

await polar.ingestUsageEvent({
  customerId: 'cust_xxx',
  eventName: 'api_calls',
  value: 1,
  timestamp: new Date().toISOString(),
  idempotencyKey: `${requestId}-${timestamp}`,
  metadata: {
    endpoint: '/api/v1/data',
    method: 'POST',
    responseTime: 245
  }
});
```

### Batch Ingestion

```typescript
// Batch multiple events for efficiency
const events = apiCalls.map(call => ({
  customerId: call.customerId,
  eventName: 'api_calls',
  value: 1,
  timestamp: call.timestamp,
  idempotencyKey: call.requestId
}));

for (const event of events) {
  await polar.ingestUsageEvent(event);
}
```

### Usage Event Schema

| Field | Required | Description |
|-------|----------|-------------|
| `customerId` | ✅ | Polar customer ID |
| `eventName` | ✅ | Metric name (must match Polar product config) |
| `value` | ✅ | Numeric value (count, bytes, seconds, etc.) |
| `timestamp` | ✅ | ISO 8601 timestamp |
| `idempotencyKey` | ⚠️ | Recommended for deduplication |
| `metadata` | ❌ | Additional context (for analytics) |

### Common Usage Patterns

```typescript
// API calls
await polar.ingestUsageEvent({
  eventName: 'api_requests',
  value: 1,
  customerId: 'cust_xxx',
  timestamp: new Date().toISOString()
});

// Storage (bytes)
await polar.ingestUsageEvent({
  eventName: 'storage_bytes',
  value: fileSize,
  customerId: 'cust_xxx',
  timestamp: new Date().toISOString()
});

// Compute (seconds)
await polar.ingestUsageEvent({
  eventName: 'compute_seconds',
  value: executionTime / 1000,
  customerId: 'cust_xxx',
  timestamp: new Date().toISOString()
});

// Active users (daily)
await polar.ingestUsageEvent({
  eventName: 'active_users',
  value: dailyActiveUsers,
  customerId: 'cust_xxx',
  timestamp: new Date().toISOString()
});
```

---

## Webhook Integration

### Setting Up Webhooks

1. **Polar Dashboard** → Settings → Webhooks → Add Endpoint
2. **URL**: `https://api.yourdomain.com/webhooks/polar`
3. **Events**: Select events to receive
4. **Copy secret** to `POLAR_WEBHOOK_SECRET`

### Webhook Endpoint

```typescript
import express from 'express';

const app = express();

// Important: Use raw body for signature validation
app.post('/webhooks/polar', 
  express.raw({ type: 'application/json' }),
  async (req, res) => {
    const signature = req.headers['x-polar-signature'] as string;
    const payload = req.body.toString();
    
    const gateway = PaymentGatewayService.getInstance(redis, logger);
    const polar = gateway.getProvider('polar') as PolarProvider;
    
    // Validate signature
    if (!polar.validateWebhookSignature(payload, signature)) {
      return res.status(400).json({ error: 'Invalid signature' });
    }
    
    const event = JSON.parse(payload);
    
    try {
      await polar.processWebhookEvent(event);
      res.json({ received: true });
    } catch (error) {
      console.error('Webhook processing error:', error);
      res.status(500).json({ error: 'Processing failed' });
    }
  }
);
```

### Webhook Events

| Event | Description | Typical Action |
|-------|-------------|----------------|
| `checkout.completed` | Customer completed checkout | Create subscription record, send welcome email |
| `subscription.created` | New subscription created | Provision access, update user record |
| `subscription.updated` | Subscription changed | Update access level, plan metadata |
| `subscription.canceled` | Subscription canceled | Schedule access removal |
| `subscription.revoked` | Immediate cancellation | Remove access immediately |
| `payment.succeeded` | Payment processed | Update billing records |
| `payment.failed` | Payment failed | Notify user, retry logic |

### Event Handling Examples

```typescript
polar.on('checkout.completed', async (data) => {
  const { checkoutId, customerId, productId } = data;
  
  // Create subscription record in your database
  await db.subscriptions.create({
    customerId,
    productId,
    status: 'active',
    polarCheckoutId: checkoutId
  });
  
  // Send welcome email
  await email.send({
    to: data.customerEmail,
    template: 'welcome-subscriber'
  });
});

polar.on('subscription.canceled', async (data) => {
  const { subscriptionId, cancelAtPeriodEnd, currentPeriodEnd } = data;
  
  if (cancelAtPeriodEnd) {
    // Schedule access removal
    await scheduler.schedule({
      action: 'remove-access',
      subscriptionId,
      executeAt: currentPeriodEnd
    });
  } else {
    // Remove access immediately
    await removeAccess(subscriptionId);
  }
});

polar.on('payment.failed', async (data) => {
  const { customerId, attemptCount } = data;
  
  // Notify customer
  await email.send({
    to: data.customerEmail,
    template: 'payment-failed',
    data: { attemptCount }
  });
  
  // After multiple failures, downgrade
  if (attemptCount >= 3) {
    await downgradeToFree(customerId);
  }
});
```

---

## Provider Routing

Janua automatically routes payments to the optimal provider based on customer location and currency.

### Default Routing Rules

```typescript
// In payment-gateway.service.ts
const routingRules = {
  // Mexico: Use Conekta for local payment methods
  'MX': { provider: 'conekta', reason: 'Local payment methods (OXXO, SPEI)' },
  
  // Global: Use Polar for MoR (tax compliance)
  'default': { provider: 'polar', reason: 'Merchant of Record - global tax compliance' },
  
  // Fallback: Stripe
  'fallback': { provider: 'stripe', reason: 'Universal fallback' }
};
```

### Custom Routing

```typescript
// Override default routing
const session = await gateway.createCheckoutSession({
  provider: 'polar',  // Explicit provider selection
  customerId: 'cust_xxx',
  priceId: 'price_xxx',
  // ...
});

// Let gateway choose based on customer
const session = await gateway.createCheckoutSession({
  // No provider specified - uses routing rules
  customerId: 'cust_xxx',
  customerCountry: 'DE',  // Germany → Polar (EU VAT handling)
  priceId: 'price_xxx'
});
```

### Why Polar for Global Payments?

| Feature | Polar (MoR) | Stripe (Direct) |
|---------|-------------|-----------------|
| **Tax Calculation** | ✅ Automatic | ❌ You handle |
| **Tax Remittance** | ✅ Polar files | ❌ You file |
| **VAT/GST Compliance** | ✅ Built-in | ❌ You implement |
| **Invoicing** | ✅ Compliant | ⚠️ You ensure |
| **Nexus Tracking** | ✅ Automatic | ❌ You track |

---

## Testing

### Sandbox Mode

Enable sandbox for testing without real payments:

```bash
POLAR_SANDBOX=true
```

### Test Cards

In sandbox mode, use Polar's test cards:

| Card Number | Result |
|-------------|--------|
| `4242 4242 4242 4242` | Success |
| `4000 0000 0000 0002` | Decline |
| `4000 0000 0000 9995` | Insufficient funds |

### Integration Tests

```typescript
import { PolarProvider } from '@janua/core/services/providers/polar.provider';

describe('PolarProvider', () => {
  let polar: PolarProvider;
  
  beforeEach(() => {
    polar = new PolarProvider({
      accessToken: process.env.POLAR_TEST_TOKEN!,
      organizationId: process.env.POLAR_TEST_ORG!,
      webhookSecret: 'test_secret',
      sandbox: true
    }, redisClient);
  });
  
  test('creates checkout session', async () => {
    const session = await polar.createCheckoutSession({
      customerId: 'test_customer',
      priceId: 'price_test',
      successUrl: 'https://example.com/success',
      cancelUrl: 'https://example.com/cancel'
    });
    
    expect(session.url).toContain('polar.sh');
    expect(session.id).toBeDefined();
  });
  
  test('validates webhook signature', () => {
    const payload = JSON.stringify({ type: 'test' });
    const signature = generateTestSignature(payload);
    
    expect(polar.validateWebhookSignature(payload, signature)).toBe(true);
  });
});
```

### Testing React Components

```tsx
import { render, screen, fireEvent } from '@testing-library/react';
import { PolarCheckoutButton } from '@janua/ui/components/payments';

describe('PolarCheckoutButton', () => {
  test('renders and handles click', async () => {
    const onCheckoutStart = jest.fn();
    
    render(
      <PolarCheckoutButton
        organizationId="org_test"
        productId="prod_test"
        onCheckoutStart={onCheckoutStart}
      >
        Subscribe
      </PolarCheckoutButton>
    );
    
    fireEvent.click(screen.getByText('Subscribe'));
    
    expect(onCheckoutStart).toHaveBeenCalled();
  });
});
```

---

## Troubleshooting

### Common Issues

#### "Invalid access token"

```
Error: Polar API error: Invalid access token
```

**Solution**: Verify `POLAR_ACCESS_TOKEN` is correctly set and not expired. Generate a new token in Polar Dashboard → Settings → API Keys.

#### "Organization not found"

```
Error: Polar API error: Organization not found
```

**Solution**: Check `POLAR_ORGANIZATION_ID` matches your organization. Find it in Polar Dashboard URL: `polar.sh/org_xxx`.

#### "Webhook signature validation failed"

```
Error: Invalid webhook signature
```

**Solutions**:
1. Verify `POLAR_WEBHOOK_SECRET` matches the one in Polar Dashboard
2. Ensure you're using the raw request body (not parsed JSON)
3. Check signature header name: `x-polar-signature`

#### "Product/Price not found"

```
Error: Product not found: prod_xxx
```

**Solution**: Verify product exists in Polar Dashboard and is published. Use the exact product ID shown in the dashboard.

### Debug Mode

Enable verbose logging for debugging:

```typescript
const polar = new PolarProvider({
  // ... config
}, redisClient);

// The provider logs to console in development
// Check for prefixed logs: [Polar]
```

### Health Check

```typescript
// Verify provider is initialized and working
const gateway = PaymentGatewayService.getInstance(redis, logger);
const polar = gateway.getProvider('polar');

if (!polar) {
  console.error('Polar provider not initialized');
  console.error('Check POLAR_ACCESS_TOKEN and POLAR_ORGANIZATION_ID');
}

// Test API connection
try {
  await polar.healthCheck();
  console.log('Polar connection healthy');
} catch (error) {
  console.error('Polar connection failed:', error);
}
```

### Support Resources

- **Polar Documentation**: [docs.polar.sh](https://docs.polar.sh)
- **Polar Dashboard**: [polar.sh/dashboard](https://polar.sh/dashboard)
- **API Reference**: [docs.polar.sh/api](https://docs.polar.sh/api)
- **Janua Issues**: [github.com/your-org/janua/issues](https://github.com/your-org/janua/issues)

---

## Migration from Stripe

If migrating existing Stripe subscriptions to Polar:

### 1. Export Customer Data

```typescript
// Export from Stripe
const stripeCustomers = await stripe.customers.list({ limit: 100 });

// Create in Polar
for (const customer of stripeCustomers.data) {
  await polar.createCustomer({
    email: customer.email,
    name: customer.name,
    metadata: {
      stripeCustomerId: customer.id
    }
  });
}
```

### 2. Update Subscription References

```typescript
// Map Stripe subscription to Polar
await db.subscriptions.update({
  where: { stripeSubscriptionId: 'sub_stripe_xxx' },
  data: { 
    polarSubscriptionId: 'sub_polar_xxx',
    provider: 'polar'
  }
});
```

### 3. Update Webhook Endpoints

Add Polar webhook endpoint alongside Stripe (don't remove Stripe until migration complete):

```typescript
// Handle both during migration
app.post('/webhooks/stripe', handleStripeWebhook);
app.post('/webhooks/polar', handlePolarWebhook);
```

---

*Last updated: 2025-01-26 | Janua Payment Infrastructure v2.0*
