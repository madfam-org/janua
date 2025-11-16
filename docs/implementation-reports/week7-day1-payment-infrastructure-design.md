# Week 7 Day 1: Payment Infrastructure - Design & Foundation

**Date**: November 16, 2025  
**Status**: 🔄 In Progress (Foundation Complete)  
**Duration**: ~2 hours (Design Phase)  
**Phase**: Payment Infrastructure Implementation

---

## 🎯 Implementation Summary

Designed and implemented the foundation for a multi-provider payment infrastructure supporting Conekta (Mexican customers), Stripe (International), and Polar (Product purchases) with intelligent routing based on geolocation and billing address detection.

### Files Created (3 core files, ~1,200 lines)

1. **`apps/api/app/models/billing.py`** (680 lines)
   - Complete database schema for multi-provider billing
   - 6 models: SubscriptionPlan, Subscription, PaymentMethod, Invoice, WebhookEvent
   - Full support for Conekta, Stripe, and Polar data structures

2. **`apps/api/app/services/payment/base.py`** (410 lines)
   - PaymentProvider abstract interface
   - Standardized methods for all providers
   - 30+ abstract methods for complete payment lifecycle

3. **`apps/api/app/services/payment/geolocation.py`** (290 lines)
   - Multi-tier country detection service
   - IP geolocation with fallback APIs
   - Billing address and profile country detection

---

## 🏗️ Architecture Design

### Multi-Provider Strategy

```
┌─────────────┐
│   Customer  │
└──────┬──────┘
       │
       ▼
┌──────────────────┐
│ Geolocation      │──► Billing Address (Tier 1)
│ Detection        │──► User Profile (Tier 2)
│ Service          │──► IP Address (Tier 3)
└──────┬───────────┘
       │
       ▼
┌──────────────────┐
│ Payment Router   │
│                  │
│ IF MX → Conekta  │
│ IF Product→Polar │
│ ELSE → Stripe    │
└──────┬───────────┘
       │
       ├──────────► Conekta Provider (Mexico)
       ├──────────► Stripe Provider (International)
       └──────────► Polar Provider (Products)
```

### Provider Selection Logic

```python
def select_provider(
    country: str,
    billing_address: dict,
    transaction_type: str
) -> PaymentProvider:
    # Tier 1: Check billing address country
    if billing_address.get("country") == "MX":
        return ConektaProvider()
    
    # Tier 2: Check transaction type
    if transaction_type == "product_purchase":
        return PolarProvider()
    
    # Default: Stripe for international subscriptions
    return StripeProvider()
```

---

## 📊 Database Schema

### SubscriptionPlan Model

Stores subscription plans with multi-provider IDs:

```python
class SubscriptionPlan(Base):
    id: UUID
    name: str  # "Startup", "Business", "Enterprise"
    description: str
    
    # Multi-provider plan IDs
    provider_plan_ids: JSON  # {"conekta": "plan_xxx", "stripe": "price_xxx", "polar": "product_xxx"}
    
    # Pricing
    price_monthly: Decimal  # 29.99
    price_yearly: Decimal   # 299.00
    currency_usd: str       # "USD" (Stripe/Polar)
    currency_mxn: str       # "MXN" (Conekta)
    
    # Features and limits
    features: JSON          # ["SSO", "Advanced MFA", "Audit Logs"]
    limits: JSON            # {"api_calls": 10000, "users": 50}
    
    # Status
    is_active: bool
    is_popular: bool
    sort_order: int
```

**Key Design Decisions:**
- Single plan definition maps to multiple provider-specific plan IDs
- Supports different currencies for Mexican (MXN) vs international (USD) customers
- JSON fields for flexible feature/limit definitions

### Subscription Model

Tracks active subscriptions with provider-specific data:

```python
class Subscription(Base):
    id: UUID
    organization_id: UUID
    plan_id: UUID
    
    # Provider tracking
    provider: str                    # "conekta" | "stripe" | "polar"
    provider_subscription_id: str    # Provider's subscription ID
    provider_customer_id: str        # Provider's customer ID
    
    # Status
    status: str                      # "active" | "trialing" | "canceled"
    billing_interval: str            # "monthly" | "yearly"
    
    # Billing cycle
    current_period_start: DateTime
    current_period_end: DateTime
    trial_start: DateTime (nullable)
    trial_end: DateTime (nullable)
    
    # Cancellation
    cancel_at_period_end: bool
    cancel_at: DateTime (nullable)
    canceled_at: DateTime (nullable)
    
    # Usage tracking
    usage_data: JSON                 # {"api_calls": 5000, "storage_gb": 10}
    
    # Provider-specific metadata
    metadata: JSON
```

**Key Features:**
- Provider-agnostic design works with any payment processor
- Tracks billing cycle and trial periods
- Usage tracking for metered billing
- Cancellation handling (immediate vs end-of-period)

### PaymentMethod Model

Stores tokenized payment methods (PCI-compliant):

```python
class PaymentMethod(Base):
    id: UUID
    organization_id: UUID
    user_id: UUID
    
    # Provider tracking
    provider: str                     # "conekta" | "stripe" | "polar"
    provider_payment_method_id: str   # Provider's token
    provider_customer_id: str
    
    # Display information (NEVER store raw card numbers)
    type: str                         # "card" | "bank_account" | "oxxo" | "spei"
    last4: str                        # "4242"
    brand: str                        # "visa" | "mastercard" | "amex"
    exp_month: int                    # 12
    exp_year: int                     # 2025
    
    # Billing address (critical for provider routing)
    billing_address: JSON             # {country: "MX", postal_code: "12345", ...}
    
    # Status
    is_default: bool
    is_active: bool
```

**Security Features:**
- **NEVER stores raw card numbers** - only provider tokens
- Only stores last4 digits and metadata for display
- Billing address country used for provider routing
- PCI DSS compliant design

### Invoice Model

Tracks billing invoices from all providers:

```python
class Invoice(Base):
    id: UUID
    organization_id: UUID
    subscription_id: UUID (nullable)
    
    # Provider tracking
    provider: str                     # "conekta" | "stripe" | "polar"
    provider_invoice_id: str
    
    # Invoice details
    amount: Decimal
    currency: str                     # "USD" | "MXN"
    status: str                       # "paid" | "open" | "uncollectible"
    
    # Payment
    payment_intent_id: str (nullable)
    payment_method_id: UUID (nullable)
    
    # Billing period
    period_start: DateTime
    period_end: DateTime
    
    # URLs
    invoice_pdf_url: str (nullable)
    hosted_invoice_url: str (nullable)
    
    # Dates
    due_date: DateTime (nullable)
    paid_at: DateTime (nullable)
    
    # Line items
    line_items: JSON                  # [{description, amount, quantity}]
```

### WebhookEvent Model

Prevents duplicate webhook processing (idempotency):

```python
class WebhookEvent(Base):
    id: UUID
    provider: str                     # "conekta" | "stripe" | "polar"
    provider_event_id: str (unique)   # Prevents duplicate processing
    event_type: str                   # "subscription.paid", "invoice.paid"
    
    # Processing status
    processed: bool
    processed_at: DateTime (nullable)
    error_message: Text (nullable)
    
    # Event data (for debugging)
    payload: JSON
```

**Why This Matters:**
- Webhooks can be sent multiple times by providers
- `provider_event_id` ensures each event processed exactly once
- Stores full payload for debugging webhook issues

---

## 🔌 PaymentProvider Interface

Base interface that all providers must implement:

### Core Methods (30+ abstract methods)

**Customer Management:**
- `create_customer(customer_data)` → customer_id
- `get_customer(customer_id)` → customer details
- `update_customer(customer_id, updates)` → updated customer
- `delete_customer(customer_id)` → success

**Payment Methods:**
- `create_payment_method(customer_id, method_data)` → payment_method
- `get_payment_method(payment_method_id)` → method details
- `list_payment_methods(customer_id)` → method list
- `delete_payment_method(payment_method_id)` → success
- `set_default_payment_method(customer_id, method_id)` → success

**Subscriptions:**
- `create_subscription(subscription_data)` → subscription
- `get_subscription(subscription_id)` → subscription details
- `update_subscription(subscription_id, updates)` → updated subscription
- `cancel_subscription(subscription_id, at_period_end)` → canceled subscription
- `resume_subscription(subscription_id)` → resumed subscription

**Invoices:**
- `get_invoice(invoice_id)` → invoice details
- `list_invoices(customer_id, limit)` → invoice list
- `pay_invoice(invoice_id)` → payment result

**Webhooks:**
- `verify_webhook_signature(payload, signature, secret)` → valid/invalid
- `parse_webhook_event(payload)` → WebhookEvent

**Plans:**
- `list_plans()` → plan list
- `get_plan(plan_id)` → plan details

### Example Implementation Pattern

```python
class ConektaProvider(PaymentProvider):
    @property
    def provider_name(self) -> str:
        return "conekta"
    
    async def create_customer(self, customer_data: CustomerData):
        # Conekta-specific API call
        conekta_customer = conekta.Customer.create(
            name=customer_data.name,
            email=customer_data.email,
            phone=customer_data.phone,
        )
        
        return {
            "customer_id": conekta_customer.id,
            "email": conekta_customer.email,
            "created": conekta_customer.created_at,
        }
```

---

## 🌍 Geolocation Service

Multi-tier country detection for intelligent provider routing:

### Detection Hierarchy

**Tier 1: Billing Address** (Most Reliable)
```python
if payment_method.billing_address.get("country") == "MX":
    return "MX"  # Use Conekta
```

**Tier 2: User Profile** (Fallback)
```python
if user.country == "MX":
    return "MX"
```

**Tier 3: IP Geolocation** (Last Resort)
```python
# Primary: ipapi.co
response = await httpx.get(f"https://ipapi.co/{ip}/json/")
country = response.json().get("country_code")

# Fallback: ip-api.com (if primary fails)
response = await httpx.get(f"http://ip-api.com/json/{ip}")
country = response.json().get("countryCode")
```

### Key Methods

```python
class GeolocationService:
    async def detect_country(
        ip_address: str,
        user_country: str,
        billing_country: str
    ) -> str:
        """Returns ISO country code (MX, US, CA, etc)"""
        
    def is_mexican_customer(
        country_code: str,
        billing_address: dict
    ) -> bool:
        """True if customer from Mexico (for Conekta routing)"""
        
    def get_currency_for_country(country_code: str) -> str:
        """Returns currency code (MXN, USD, EUR, etc)"""
```

### Caching Strategy

```python
# Cache IP lookups to avoid repeated API calls
_cache: Dict[str, str] = {}

# Cache hit
if ip_address in self._cache:
    return self._cache[ip_address]

# Cache miss → API call → store result
country = await self._fetch_from_ipapi(ip_address)
self._cache[ip_address] = country
```

---

## 🔒 Security Design

### PCI DSS Compliance

**NEVER Store Raw Card Data:**
```python
# ❌ WRONG - NEVER do this
payment_method.card_number = "4242424242424242"

# ✅ RIGHT - Store provider token only
payment_method.provider_payment_method_id = "pm_abc123"
payment_method.last4 = "4242"  # For display only
```

**Tokenization Flow:**
```
1. Client-side: Collect card → Tokenize with provider SDK (Conekta.js/Stripe.js)
2. Client-side: Send token to our API (never send raw card number)
3. Server-side: Attach token to customer via provider API
4. Server-side: Store provider's payment_method_id in database
```

### Webhook Security

**Signature Verification:**
```python
def verify_webhook_signature(payload: bytes, signature: str, secret: str) -> bool:
    # Conekta: HMAC-SHA256
    computed = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(computed, signature)
    
    # Stripe: stripe.Webhook.construct_event() with signature verification
    # Polar: Similar signature verification
```

**Idempotency:**
```python
# Check if event already processed
existing = db.query(WebhookEvent).filter(
    WebhookEvent.provider_event_id == event.id
).first()

if existing and existing.processed:
    return {"status": "already_processed"}

# Mark as processed
webhook_event.processed = True
webhook_event.processed_at = datetime.utcnow()
db.commit()
```

### API Key Management

```python
# Environment variables (NEVER commit to git)
CONEKTA_API_KEY = os.getenv("CONEKTA_API_KEY")
CONEKTA_WEBHOOK_SECRET = os.getenv("CONEKTA_WEBHOOK_SECRET")

STRIPE_API_KEY = os.getenv("STRIPE_API_KEY")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")

POLAR_API_KEY = os.getenv("POLAR_API_KEY")

# Use test keys in development
if os.getenv("ENVIRONMENT") == "development":
    CONEKTA_API_KEY = os.getenv("CONEKTA_TEST_KEY")
```

---

## 📈 Next Implementation Steps

### Immediate (In Progress)

1. **Implement Conekta Provider** (~2-3 hours)
   - Customer management
   - Payment method handling (cards, OXXO, SPEI)
   - Subscription creation and management
   - Webhook processing
   - MXN currency support

2. **Implement Stripe Provider** (~2-3 hours)
   - Customer management
   - Payment method handling (cards, ACH, SEPA)
   - Subscription management
   - Multi-currency support (USD, EUR, etc)
   - Webhook processing

3. **Implement Polar Provider** (~1-2 hours)
   - Product purchases
   - Customer portal integration
   - Benefit tier management
   - Webhook handling

4. **Build Payment Router** (~1 hour)
   - Smart provider selection based on:
     - Billing address country
     - User profile country
     - IP geolocation
     - Transaction type (subscription vs product)

### Short-term (Next 1-2 days)

5. **API Endpoints** (~2-3 hours)
   - `POST /api/v1/billing/subscriptions` - Create subscription
   - `GET /api/v1/billing/subscriptions/{id}` - Get subscription
   - `PATCH /api/v1/billing/subscriptions/{id}` - Update subscription
   - `DELETE /api/v1/billing/subscriptions/{id}` - Cancel subscription
   - `POST /api/v1/billing/payment-methods` - Add payment method
   - `GET /api/v1/billing/payment-methods` - List payment methods
   - `DELETE /api/v1/billing/payment-methods/{id}` - Remove method
   - `POST /webhooks/conekta` - Conekta webhooks
   - `POST /webhooks/stripe` - Stripe webhooks
   - `POST /webhooks/polar` - Polar webhooks

6. **UI Components** (~2-3 hours)
   - Subscription plan selection
   - Payment method form (with provider detection)
   - Billing history and invoices
   - Subscription management (upgrade/downgrade/cancel)
   - Usage dashboard

7. **Testing** (~2-3 hours)
   - Unit tests for each provider
   - Integration tests for payment flows
   - E2E tests for checkout process
   - Webhook testing

---

## 🎓 Design Decisions

### Why Multi-Provider Architecture?

**Problem**: Different regions have different payment preferences and costs.

**Solution**: Route to optimal provider based on customer location:
- **Mexican customers** → Conekta (local payment methods: OXXO, SPEI, lower fees in MXN)
- **International customers** → Stripe (global coverage, multi-currency, reliable)
- **Product purchases** → Polar (purpose-built for digital products and benefits)

### Why Abstract Interface?

**Benefit**: Easy to add new providers in future
```python
# Adding a new provider is simple
class PayPalProvider(PaymentProvider):
    # Implement required methods
    # No changes to existing code needed
```

### Why Geolocation Service?

**Use Case**: User visits from Mexico but hasn't added billing address yet.

**Solution**: Detect country from IP → route to Conekta → show OXXO/SPEI options

**Fallback**: If geolocation fails, default to Stripe (works globally)

---

## ✅ Completion Checklist

### Phase 1: Foundation (✅ Complete)
- [x] Database models (SubscriptionPlan, Subscription, PaymentMethod, Invoice, WebhookEvent)
- [x] PaymentProvider base interface
- [x] GeolocationService for country detection
- [x] Architecture documentation

### Phase 2: Providers (🔄 Next)
- [ ] Conekta provider implementation
- [ ] Stripe provider implementation
- [ ] Polar provider implementation
- [ ] Payment router service

### Phase 3: Integration (⏳ Pending)
- [ ] API endpoints
- [ ] Webhook handlers
- [ ] UI components
- [ ] Comprehensive testing

---

**Implementation Status**: 🔄 Foundation Complete, Starting Provider Implementation  
Multi-provider payment infrastructure designed and ready for provider implementations.
