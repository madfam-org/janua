# Multi-Provider Payment Infrastructure Implementation Roadmap

**Version**: 1.0  
**Last Updated**: November 16, 2025  
**Status**: 📋 Planning → 🚀 Ready for Implementation  
**Timeline**: 6 weeks (3 phases)

---

## 🎯 Vision & Objectives

### Strategic Goals
1. **Polar as Merchant of Record**: Global payment infrastructure with tax/compliance handling
2. **Conekta for Mexico**: Optimized local payment processing for Mexican customers
3. **Stripe as Fallback**: Universal backup for edge cases and unsupported regions
4. **Plinto Polar Plugin**: Easy-to-implement plugin (like Better-Auth) for customers
5. **Dogfooding**: Use Plinto's own auth + payment features internally

### Success Criteria
- ✅ 100% payment coverage (Polar global + Conekta MX + Stripe fallback)
- ✅ <5 minute integration time for plugin users
- ✅ >95% payment success rate across all providers
- ✅ Real-world validation through dogfooding
- ✅ Competitive differentiation vs Clerk/Auth0

---

## 🏗️ Architecture Overview

### Payment Provider Routing Strategy

```
┌─────────────────────────────────────────────────────┐
│           Plinto Billing Service                     │
│                                                      │
│  ┌──────────────────────────────────────────────┐  │
│  │  Payment Provider Router                      │  │
│  │                                               │  │
│  │  if (country === 'MX' && card.country === 'MX') │
│  │    → Conekta (Local Mexican Processing)      │  │
│  │  else if (supported_by_polar)                 │  │
│  │    → Polar (Merchant of Record)              │  │
│  │  else                                         │  │
│  │    → Stripe (Universal Fallback)             │  │
│  └──────────────────────────────────────────────┘  │
│                                                      │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐         │
│  │ Conekta  │  │  Polar   │  │  Stripe  │         │
│  │ Service  │  │ Service  │  │ Service  │         │
│  └──────────┘  └──────────┘  └──────────┘         │
└─────────────────────────────────────────────────────┘
```

### Provider Responsibilities

**Conekta (Mexico)**:
- Primary for Mexican customers (geo + card country = MX)
- Local payment methods (OXXO, SPEI, Tarjeta de Débito)
- Optimized for Mexican regulations
- Lower processing fees for MX transactions

**Polar (Global Merchant of Record)**:
- Primary for all non-Mexican customers
- Handles VAT, sales tax, compliance globally
- Developer-first payment platform
- Subscription and usage-based billing
- Customer portal and analytics

**Stripe (Universal Fallback)**:
- Backup for Polar unsupported regions
- Payment methods not available via Polar/Conekta
- Legacy subscriptions migration path
- Edge case handling

---

## 📅 Implementation Timeline

### Phase 1: Multi-Provider Infrastructure (Weeks 1-2)

**Objective**: Build unified billing service supporting Polar, Conekta, and Stripe

#### Week 1: Core Infrastructure

**Backend Models** (`apps/api/app/models/billing.py`):
```python
# Enhanced billing models for multi-provider support

class PaymentProvider(str, Enum):
    POLAR = "polar"
    CONEKTA = "conekta"
    STRIPE = "stripe"

class BillingCustomer(Base):
    """Unified customer across all payment providers"""
    __tablename__ = "billing_customers"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    
    # Multi-provider IDs
    polar_customer_id = Column(String(255), unique=True, nullable=True, index=True)
    conekta_customer_id = Column(String(255), unique=True, nullable=True, index=True)
    stripe_customer_id = Column(String(255), unique=True, nullable=True, index=True)
    
    # Customer info
    email = Column(String(255), nullable=False)
    country = Column(String(2), nullable=True)  # ISO 3166-1 alpha-2
    preferred_provider = Column(SQLEnum(PaymentProvider), nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class BillingSubscription(Base):
    """Unified subscription across providers"""
    __tablename__ = "billing_subscriptions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    billing_customer_id = Column(UUID(as_uuid=True), ForeignKey("billing_customers.id"), nullable=False)
    
    # Provider-specific subscription IDs
    provider = Column(SQLEnum(PaymentProvider), nullable=False)
    provider_subscription_id = Column(String(255), nullable=False, index=True)
    
    # Subscription details
    plan = Column(SQLEnum(BillingPlan), nullable=False)
    status = Column(SQLEnum(SubscriptionStatus), nullable=False)
    current_period_start = Column(DateTime, nullable=False)
    current_period_end = Column(DateTime, nullable=False)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Indexes for efficient querying
    __table_args__ = (
        Index('ix_billing_subscriptions_provider_id', 'provider', 'provider_subscription_id'),
    )

class PaymentProviderEvent(Base):
    """Unified webhook event tracking"""
    __tablename__ = "payment_provider_events"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    provider = Column(SQLEnum(PaymentProvider), nullable=False)
    event_id = Column(String(255), unique=True, nullable=False, index=True)
    event_type = Column(String(100), nullable=False)
    payload = Column(JSON, nullable=False)
    processed = Column(Boolean, default=False)
    processed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
```

**Provider Router Service** (`apps/api/app/services/payment_router.py`):
```python
class PaymentProviderRouter:
    """Routes payments to appropriate provider based on customer location and card"""
    
    async def determine_provider(
        self,
        db: AsyncSession,
        organization_id: UUID,
        country: Optional[str] = None,
        card_country: Optional[str] = None,
        user_preference: Optional[PaymentProvider] = None
    ) -> PaymentProvider:
        """
        Routing logic:
        1. If Mexico + Mexican card → Conekta
        2. Else if Polar supported → Polar (MoR)
        3. Else → Stripe (fallback)
        """
        
        # Priority 1: Explicit user preference (override)
        if user_preference:
            return user_preference
        
        # Priority 2: Mexico optimization
        if country == "MX" and card_country == "MX":
            return PaymentProvider.CONEKTA
        
        # Priority 3: Polar as global MoR
        if self._is_polar_supported(country):
            return PaymentProvider.POLAR
        
        # Priority 4: Stripe fallback
        return PaymentProvider.STRIPE
    
    def _is_polar_supported(self, country: Optional[str]) -> bool:
        """Check if Polar supports this country"""
        # Polar supports most countries, excluding sanctioned regions
        POLAR_UNSUPPORTED = ["CU", "IR", "KP", "SY", "RU"]  # Cuba, Iran, North Korea, Syria, Russia
        return country not in POLAR_UNSUPPORTED if country else True
    
    async def get_or_create_customer(
        self,
        db: AsyncSession,
        organization_id: UUID,
        provider: PaymentProvider,
        email: str,
        country: Optional[str] = None
    ) -> BillingCustomer:
        """Get existing or create new customer for provider"""
        # Implementation details...
        pass
```

**Unified Billing Service** (`apps/api/app/services/billing_service.py`):
```python
class UnifiedBillingService:
    """Coordinates all payment providers through single interface"""
    
    def __init__(self):
        self.polar_service = PolarService()
        self.conekta_service = ConektaService()
        self.stripe_service = StripeService()
        self.router = PaymentProviderRouter()
    
    async def create_checkout(
        self,
        db: AsyncSession,
        organization_id: UUID,
        product_id: str,
        success_url: str,
        cancel_url: str,
        country: Optional[str] = None,
        card_country: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create checkout session with appropriate provider"""
        
        # Determine provider
        provider = await self.router.determine_provider(
            db, organization_id, country, card_country
        )
        
        # Get or create customer
        customer = await self.router.get_or_create_customer(
            db, organization_id, provider, email, country
        )
        
        # Route to provider
        if provider == PaymentProvider.POLAR:
            return await self.polar_service.create_checkout(...)
        elif provider == PaymentProvider.CONEKTA:
            return await self.conekta_service.create_checkout(...)
        else:  # Stripe
            return await self.stripe_service.create_checkout(...)
    
    async def handle_webhook(
        self,
        db: AsyncSession,
        provider: PaymentProvider,
        payload: Dict[str, Any],
        signature: str
    ) -> None:
        """Route webhook to appropriate provider handler"""
        
        if provider == PaymentProvider.POLAR:
            await self.polar_service.handle_webhook(db, payload, signature)
        elif provider == PaymentProvider.CONEKTA:
            await self.conekta_service.handle_webhook(db, payload, signature)
        else:  # Stripe
            await self.stripe_service.handle_webhook(db, payload, signature)
```

**Deliverables**:
- ✅ Database models and migration for multi-provider support
- ✅ PaymentProviderRouter with intelligent routing logic
- ✅ UnifiedBillingService coordinating all providers
- ✅ Provider-specific services (Polar, Conekta, Stripe)

#### Week 2: API Endpoints & Webhook Processing

**API Router** (`apps/api/app/routers/billing.py`):
```python
@router.post("/checkout")
async def create_checkout(
    request: CheckoutRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create checkout session with automatic provider routing"""
    
    billing_service = UnifiedBillingService()
    
    checkout = await billing_service.create_checkout(
        db=db,
        organization_id=request.organization_id,
        product_id=request.product_id,
        success_url=request.success_url,
        cancel_url=request.cancel_url,
        country=request.country,
        card_country=request.card_country
    )
    
    return {
        "checkout_id": checkout["id"],
        "checkout_url": checkout["url"],
        "provider": checkout["provider"]
    }

@router.post("/webhooks/{provider}")
async def handle_webhook(
    provider: PaymentProvider,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Handle webhooks from all payment providers"""
    
    payload = await request.json()
    signature = request.headers.get("X-Signature") or request.headers.get("Stripe-Signature")
    
    billing_service = UnifiedBillingService()
    await billing_service.handle_webhook(db, provider, payload, signature)
    
    return {"status": "success"}

@router.get("/customer/portal")
async def get_customer_portal(
    organization_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get customer portal URL for subscription management"""
    
    billing_service = UnifiedBillingService()
    portal = await billing_service.get_customer_portal(db, organization_id)
    
    return {
        "portal_url": portal["url"],
        "provider": portal["provider"]
    }
```

**Deliverables**:
- ✅ Unified billing API endpoints
- ✅ Multi-provider webhook processing
- ✅ Customer portal integration
- ✅ End-to-end testing with all three providers

---

### Phase 2: Plinto Polar Plugin (Weeks 3-4)

**Objective**: Create easy-to-integrate plugin for Plinto customers (similar to Better-Auth)

#### Week 3: TypeScript SDK Plugin

**Plugin Architecture** (`packages/typescript-sdk/src/plugins/polar.ts`):
```typescript
// Plinto Polar Plugin - Easy integration for customers

export interface PolarPluginConfig {
  /**
   * Plinto API URL (defaults to production)
   */
  apiUrl?: string
  
  /**
   * Product IDs for subscription tiers
   */
  products?: {
    free?: string
    pro?: string
    enterprise?: string
  }
  
  /**
   * Callbacks for payment events
   */
  onSuccess?: (subscription: Subscription) => void
  onError?: (error: Error) => void
  onCancel?: () => void
}

export class PolarPlugin {
  private client: PlintoClient
  private config: PolarPluginConfig
  
  constructor(client: PlintoClient, config: PolarPluginConfig = {}) {
    this.client = client
    this.config = {
      apiUrl: config.apiUrl || 'https://api.plinto.dev',
      ...config
    }
  }
  
  /**
   * Create checkout session and redirect to Polar
   * 
   * @example
   * ```typescript
   * await plintoClient.polar.subscribe({
   *   plan: 'pro',
   *   organizationId: 'org_123',
   *   successUrl: '/dashboard',
   * })
   * ```
   */
  async subscribe(options: {
    plan: 'free' | 'pro' | 'enterprise'
    organizationId: string
    successUrl: string
    cancelUrl?: string
  }): Promise<void> {
    const productId = this.config.products?.[options.plan]
    if (!productId) {
      throw new Error(`Product ID not configured for plan: ${options.plan}`)
    }
    
    try {
      const response = await this.client.post('/billing/checkout', {
        product_id: productId,
        organization_id: options.organizationId,
        success_url: `${window.location.origin}${options.successUrl}`,
        cancel_url: options.cancelUrl || window.location.href,
      })
      
      // Redirect to checkout
      window.location.href = response.checkout_url
    } catch (error) {
      this.config.onError?.(error as Error)
      throw error
    }
  }
  
  /**
   * Get customer portal URL for subscription management
   */
  async getPortal(organizationId: string): Promise<string> {
    const response = await this.client.get('/billing/customer/portal', {
      params: { organization_id: organizationId }
    })
    return response.portal_url
  }
  
  /**
   * Redirect to customer portal
   */
  async redirectToPortal(organizationId: string): Promise<void> {
    const portalUrl = await this.getPortal(organizationId)
    window.location.href = portalUrl
  }
  
  /**
   * Get current subscription status
   */
  async getSubscription(organizationId: string): Promise<Subscription | null> {
    try {
      return await this.client.get(`/billing/subscriptions/${organizationId}`)
    } catch (error) {
      if ((error as any).status === 404) return null
      throw error
    }
  }
  
  /**
   * Cancel subscription
   */
  async cancelSubscription(organizationId: string): Promise<void> {
    await this.client.delete(`/billing/subscriptions/${organizationId}`)
  }
}

// Type definitions
export interface Subscription {
  id: string
  organizationId: string
  plan: 'free' | 'pro' | 'enterprise'
  status: 'active' | 'canceled' | 'past_due'
  currentPeriodEnd: string
  provider: 'polar' | 'conekta' | 'stripe'
}

// Plugin registration
declare module '@plinto/typescript-sdk' {
  interface PlintoClient {
    polar: PolarPlugin
  }
}
```

**SDK Integration** (`packages/typescript-sdk/src/client.ts`):
```typescript
import { PolarPlugin, PolarPluginConfig } from './plugins/polar'

export class PlintoClient {
  public polar: PolarPlugin
  
  constructor(config: PlintoClientConfig & { polar?: PolarPluginConfig } = {}) {
    // ... existing client initialization
    
    // Initialize Polar plugin
    this.polar = new PolarPlugin(this, config.polar)
  }
}
```

**Deliverables**:
- ✅ PolarPlugin TypeScript SDK class
- ✅ Type-safe API with full TypeScript support
- ✅ Simple subscribe(), getPortal(), cancelSubscription() methods
- ✅ Plugin registration in PlintoClient

#### Week 4: React UI Components

**Polar Checkout Button** (`packages/ui/src/components/billing/polar-checkout-button.tsx`):
```typescript
import { useState } from 'react'
import { usePlintoClient } from '../../hooks/use-plinto-client'

export interface PolarCheckoutButtonProps {
  /**
   * Subscription plan to purchase
   */
  plan: 'free' | 'pro' | 'enterprise'
  
  /**
   * Organization ID for the subscription
   */
  organizationId: string
  
  /**
   * URL to redirect after successful payment
   */
  successUrl: string
  
  /**
   * URL to redirect if user cancels
   */
  cancelUrl?: string
  
  /**
   * Custom button content
   */
  children?: React.ReactNode
  
  /**
   * Custom CSS classes
   */
  className?: string
  
  /**
   * Button variant
   */
  variant?: 'primary' | 'secondary' | 'outline'
  
  /**
   * Button size
   */
  size?: 'sm' | 'md' | 'lg'
  
  /**
   * Callback when checkout starts
   */
  onCheckoutStart?: () => void
  
  /**
   * Callback on error
   */
  onError?: (error: Error) => void
}

export function PolarCheckoutButton({
  plan,
  organizationId,
  successUrl,
  cancelUrl,
  children = 'Subscribe',
  className = '',
  variant = 'primary',
  size = 'md',
  onCheckoutStart,
  onError,
}: PolarCheckoutButtonProps) {
  const client = usePlintoClient()
  const [loading, setLoading] = useState(false)
  
  const handleSubscribe = async () => {
    try {
      setLoading(true)
      onCheckoutStart?.()
      
      await client.polar.subscribe({
        plan,
        organizationId,
        successUrl,
        cancelUrl,
      })
    } catch (error) {
      setLoading(false)
      onError?.(error as Error)
      console.error('Checkout error:', error)
    }
  }
  
  const baseStyles = 'inline-flex items-center justify-center font-medium transition-colors focus:outline-none focus:ring-2 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed'
  
  const variantStyles = {
    primary: 'bg-blue-600 text-white hover:bg-blue-700 focus:ring-blue-500',
    secondary: 'bg-gray-600 text-white hover:bg-gray-700 focus:ring-gray-500',
    outline: 'border-2 border-blue-600 text-blue-600 hover:bg-blue-50 focus:ring-blue-500',
  }
  
  const sizeStyles = {
    sm: 'px-3 py-1.5 text-sm rounded',
    md: 'px-4 py-2 text-base rounded-md',
    lg: 'px-6 py-3 text-lg rounded-lg',
  }
  
  return (
    <button
      onClick={handleSubscribe}
      disabled={loading}
      className={`${baseStyles} ${variantStyles[variant]} ${sizeStyles[size]} ${className}`}
    >
      {loading ? (
        <>
          <svg className="animate-spin -ml-1 mr-2 h-4 w-4" fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
          </svg>
          Loading...
        </>
      ) : (
        children
      )}
    </button>
  )
}
```

**Customer Portal Button** (`packages/ui/src/components/billing/polar-customer-portal.tsx`):
```typescript
import { useState } from 'react'
import { usePlintoClient } from '../../hooks/use-plinto-client'

export interface PolarCustomerPortalProps {
  /**
   * Organization ID
   */
  organizationId: string
  
  /**
   * Custom button content
   */
  children?: React.ReactNode
  
  /**
   * Custom CSS classes
   */
  className?: string
  
  /**
   * Callback on error
   */
  onError?: (error: Error) => void
}

export function PolarCustomerPortal({
  organizationId,
  children = 'Manage Subscription',
  className = '',
  onError,
}: PolarCustomerPortalProps) {
  const client = usePlintoClient()
  const [loading, setLoading] = useState(false)
  
  const handlePortal = async () => {
    try {
      setLoading(true)
      await client.polar.redirectToPortal(organizationId)
    } catch (error) {
      setLoading(false)
      onError?.(error as Error)
      console.error('Portal error:', error)
    }
  }
  
  return (
    <button
      onClick={handlePortal}
      disabled={loading}
      className={`inline-flex items-center px-4 py-2 border border-gray-300 text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50 ${className}`}
    >
      {loading ? 'Loading...' : children}
    </button>
  )
}
```

**Subscription Status Component** (`packages/ui/src/components/billing/subscription-status.tsx`):
```typescript
import { useEffect, useState } from 'react'
import { usePlintoClient } from '../../hooks/use-plinto-client'
import type { Subscription } from '@plinto/typescript-sdk'

export interface SubscriptionStatusProps {
  organizationId: string
  className?: string
  showCancelButton?: boolean
  onCancel?: () => void
}

export function SubscriptionStatus({
  organizationId,
  className = '',
  showCancelButton = false,
  onCancel,
}: SubscriptionStatusProps) {
  const client = usePlintoClient()
  const [subscription, setSubscription] = useState<Subscription | null>(null)
  const [loading, setLoading] = useState(true)
  
  useEffect(() => {
    loadSubscription()
  }, [organizationId])
  
  const loadSubscription = async () => {
    try {
      const sub = await client.polar.getSubscription(organizationId)
      setSubscription(sub)
    } catch (error) {
      console.error('Failed to load subscription:', error)
    } finally {
      setLoading(false)
    }
  }
  
  const handleCancel = async () => {
    if (!confirm('Are you sure you want to cancel your subscription?')) return
    
    try {
      await client.polar.cancelSubscription(organizationId)
      onCancel?.()
      await loadSubscription()
    } catch (error) {
      console.error('Failed to cancel subscription:', error)
    }
  }
  
  if (loading) {
    return <div className={className}>Loading subscription...</div>
  }
  
  if (!subscription) {
    return <div className={className}>No active subscription</div>
  }
  
  const statusColors = {
    active: 'bg-green-100 text-green-800',
    canceled: 'bg-red-100 text-red-800',
    past_due: 'bg-yellow-100 text-yellow-800',
  }
  
  return (
    <div className={`space-y-4 ${className}`}>
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-medium">
            {subscription.plan.charAt(0).toUpperCase() + subscription.plan.slice(1)} Plan
          </h3>
          <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${statusColors[subscription.status]}`}>
            {subscription.status}
          </span>
        </div>
        
        {showCancelButton && subscription.status === 'active' && (
          <button
            onClick={handleCancel}
            className="text-sm text-red-600 hover:text-red-800"
          >
            Cancel Subscription
          </button>
        )}
      </div>
      
      <div className="text-sm text-gray-600">
        <p>Renews on {new Date(subscription.currentPeriodEnd).toLocaleDateString()}</p>
        <p className="text-xs text-gray-500 mt-1">Powered by {subscription.provider}</p>
      </div>
    </div>
  )
}
```

**Deliverables**:
- ✅ PolarCheckoutButton React component
- ✅ PolarCustomerPortal React component
- ✅ SubscriptionStatus React component
- ✅ Tailwind CSS styling with customization support
- ✅ TypeScript type safety throughout

---

### Phase 3: Dogfooding & Documentation (Weeks 5-6)

**Objective**: Use Plinto's own features internally and create comprehensive documentation

#### Week 5: Dogfooding Implementation

**Plinto Platform Billing** (apps/demo integration):
```typescript
// apps/demo/app/pricing/page.tsx
import { PolarCheckoutButton } from '@plinto/ui'
import { useAuth } from '@plinto/ui'

export default function PricingPage() {
  const { user, organization } = useAuth()
  
  return (
    <div className="pricing-grid">
      {/* Free Plan */}
      <PricingTier
        name="Free"
        price="$0"
        features={['Basic auth', '1,000 MAU', 'Community support']}
      >
        <button>Current Plan</button>
      </PricingTier>
      
      {/* Pro Plan */}
      <PricingTier
        name="Pro"
        price="$29/mo"
        features={['Advanced auth', '10,000 MAU', 'Email support', 'MFA & SSO']}
      >
        <PolarCheckoutButton
          plan="pro"
          organizationId={organization?.id}
          successUrl="/dashboard?upgraded=true"
          variant="primary"
          size="lg"
        >
          Upgrade to Pro
        </PolarCheckoutButton>
      </PricingTier>
      
      {/* Enterprise Plan */}
      <PricingTier
        name="Enterprise"
        price="Custom"
        features={['Unlimited MAU', 'SLA support', 'Custom features', 'Dedicated success manager']}
      >
        <a href="/contact">Contact Sales</a>
      </PricingTier>
    </div>
  )
}
```

**Settings Page Integration**:
```typescript
// apps/demo/app/settings/billing/page.tsx
import { SubscriptionStatus, PolarCustomerPortal } from '@plinto/ui'
import { useAuth } from '@plinto/ui'

export default function BillingSettingsPage() {
  const { organization } = useAuth()
  
  return (
    <div className="settings-page">
      <h1>Billing & Subscription</h1>
      
      <SubscriptionStatus
        organizationId={organization?.id}
        showCancelButton
        onCancel={() => {
          // Handle post-cancellation
          alert('Subscription canceled. You can continue using Pro features until the end of your billing period.')
        }}
      />
      
      <div className="mt-6">
        <PolarCustomerPortal
          organizationId={organization?.id}
          className="btn-secondary"
        >
          Manage Payment Methods
        </PolarCustomerPortal>
      </div>
    </div>
  )
}
```

**Deliverables**:
- ✅ Plinto demo app using own auth features
- ✅ Polar plugin integrated for billing
- ✅ Real-world validation and testing
- ✅ Performance and UX metrics collection
- ✅ Internal feedback and iteration

#### Week 6: Documentation & Launch

**Plugin Documentation** (`docs/plugins/POLAR_PLUGIN.md`):
````markdown
# Plinto Polar Plugin

Easy payment integration for your Plinto-powered app. Accept subscriptions in <5 minutes.

## Quick Start

### 1. Install (1 min)

```bash
npm install @plinto/ui @plinto/typescript-sdk
```

### 2. Configure Plinto Client (1 min)

```typescript
// lib/plinto-client.ts
import { PlintoClient } from '@plinto/typescript-sdk'

export const plintoClient = new PlintoClient({
  apiUrl: process.env.NEXT_PUBLIC_PLINTO_API_URL,
  publishableKey: process.env.NEXT_PUBLIC_PLINTO_PUBLISHABLE_KEY,
  
  // Configure Polar plugin
  polar: {
    products: {
      pro: 'prod_polar_pro_plan',
      enterprise: 'prod_polar_enterprise_plan',
    },
    onSuccess: (subscription) => {
      console.log('Payment successful!', subscription)
    },
    onError: (error) => {
      console.error('Payment failed:', error)
    },
  },
})
```

### 3. Add Checkout Button (2 min)

```typescript
// app/pricing/page.tsx
import { PolarCheckoutButton } from '@plinto/ui'

export default function PricingPage() {
  return (
    <PolarCheckoutButton
      plan="pro"
      organizationId="org_123"
      successUrl="/dashboard?upgraded=true"
    >
      Subscribe to Pro - $29/mo
    </PolarCheckoutButton>
  )
}
```

### 4. Add Customer Portal (1 min)

```typescript
// app/settings/billing/page.tsx
import { PolarCustomerPortal, SubscriptionStatus } from '@plinto/ui'

export default function BillingPage() {
  return (
    <>
      <SubscriptionStatus organizationId="org_123" />
      <PolarCustomerPortal organizationId="org_123" />
    </>
  )
}
```

## Complete Example

See our [demo app](https://demo.plinto.dev) for a full working example.

## API Reference

### PolarCheckoutButton

Redirect users to Polar checkout for subscription purchase.

**Props**:
- `plan` - Subscription plan: 'free' | 'pro' | 'enterprise'
- `organizationId` - Organization ID for subscription
- `successUrl` - Redirect URL after successful payment
- `cancelUrl` - (Optional) Redirect URL if user cancels
- `className` - (Optional) Custom CSS classes
- `variant` - (Optional) Button style: 'primary' | 'secondary' | 'outline'
- `size` - (Optional) Button size: 'sm' | 'md' | 'lg'

### PolarCustomerPortal

Link to Polar customer portal for subscription management.

**Props**:
- `organizationId` - Organization ID
- `className` - (Optional) Custom CSS classes

### SubscriptionStatus

Display current subscription status and details.

**Props**:
- `organizationId` - Organization ID
- `showCancelButton` - (Optional) Show cancel subscription button
- `onCancel` - (Optional) Callback when subscription is canceled

## SDK Methods

### Subscribe

```typescript
await plintoClient.polar.subscribe({
  plan: 'pro',
  organizationId: 'org_123',
  successUrl: '/dashboard',
})
```

### Get Portal URL

```typescript
const portalUrl = await plintoClient.polar.getPortal('org_123')
```

### Get Subscription

```typescript
const subscription = await plintoClient.polar.getSubscription('org_123')
```

### Cancel Subscription

```typescript
await plintoClient.polar.cancelSubscription('org_123')
```

## Styling

Components use Tailwind CSS classes and can be customized with `className` prop.

## TypeScript Support

Full TypeScript support with type definitions included.

## Troubleshooting

### Checkout redirects to wrong URL
- Verify `successUrl` includes full path
- Check `NEXT_PUBLIC_PLINTO_API_URL` environment variable

### "Product ID not configured" error
- Configure product IDs in Polar plugin config
- Verify product IDs match Polar dashboard

### Subscription not loading
- Check organization ID is correct
- Verify API credentials in environment variables
````

**Deliverables**:
- ✅ Complete plugin documentation (<5 min quickstart)
- ✅ API reference for all components and methods
- ✅ Troubleshooting guide
- ✅ Example implementations (Next.js, React, Vue)
- ✅ Migration guide from other payment providers
- ✅ Case study blog post on dogfooding

---

## 🔒 Security & Compliance

### Security Measures

**Webhook Verification**:
```python
# All webhooks verified with provider-specific signatures
def verify_polar_webhook(payload: bytes, signature: str) -> bool:
    secret = settings.POLAR_WEBHOOK_SECRET
    expected_sig = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(signature, f"sha256={expected_sig}")

def verify_conekta_webhook(payload: bytes, signature: str) -> bool:
    # Conekta verification logic
    pass

def verify_stripe_webhook(payload: bytes, signature: str) -> bool:
    # Stripe verification logic
    pass
```

**PCI Compliance**:
- All card data handled by payment providers (PCI DSS Level 1)
- No card data stored in Plinto database
- Tokenization via provider APIs

**Data Privacy**:
- GDPR-compliant customer data export
- Right to deletion implementation
- Data retention policies per provider

### Configuration

```env
# Polar Configuration
POLAR_ACCESS_TOKEN=polar_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
POLAR_WEBHOOK_SECRET=whsec_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
POLAR_SANDBOX=false

# Conekta Configuration
CONEKTA_API_KEY=key_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
CONEKTA_WEBHOOK_SECRET=whsec_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# Stripe Configuration
STRIPE_SECRET_KEY=sk_live_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
STRIPE_WEBHOOK_SECRET=whsec_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

---

## 🧪 Testing Strategy

### Unit Tests

**Provider Router**:
```python
# tests/unit/services/test_payment_router.py
async def test_mexican_customer_routes_to_conekta():
    router = PaymentProviderRouter()
    provider = await router.determine_provider(
        db, org_id, country="MX", card_country="MX"
    )
    assert provider == PaymentProvider.CONEKTA

async def test_non_mexican_routes_to_polar():
    router = PaymentProviderRouter()
    provider = await router.determine_provider(
        db, org_id, country="US", card_country="US"
    )
    assert provider == PaymentProvider.POLAR

async def test_sanctioned_country_routes_to_stripe():
    router = PaymentProviderRouter()
    provider = await router.determine_provider(
        db, org_id, country="RU"
    )
    assert provider == PaymentProvider.STRIPE
```

**Unified Billing Service**:
```python
# tests/unit/services/test_unified_billing.py
async def test_create_checkout_with_polar():
    service = UnifiedBillingService()
    checkout = await service.create_checkout(
        db, org_id, product_id="prod_polar_pro",
        success_url="/success", cancel_url="/cancel",
        country="US"
    )
    assert checkout["provider"] == "polar"
    assert "checkout_url" in checkout
```

### Integration Tests

**End-to-End Checkout Flow**:
```typescript
// tests/e2e/checkout-flow.spec.ts
test('complete checkout flow with Polar', async ({ page }) => {
  await page.goto('/pricing')
  await page.click('text=Subscribe to Pro')
  
  // Redirected to Polar checkout
  await expect(page).toHaveURL(/polar\.sh\/checkout/)
  
  // Complete payment (sandbox mode)
  await fillPaymentDetails(page, {
    cardNumber: '4242424242424242',
    expiry: '12/25',
    cvc: '123'
  })
  await page.click('text=Pay')
  
  // Redirected back to success URL
  await expect(page).toHaveURL('/dashboard?upgraded=true')
  
  // Verify subscription activated
  const subscription = await getSubscription(orgId)
  expect(subscription.status).toBe('active')
  expect(subscription.plan).toBe('pro')
})

test('Mexican customer uses Conekta', async ({ page }) => {
  // Set geolocation to Mexico
  await page.context().setGeolocation({ latitude: 19.4326, longitude: -99.1332 })
  
  await page.goto('/pricing')
  await page.click('text=Suscribirse a Pro')
  
  // Redirected to Conekta checkout
  await expect(page).toHaveURL(/conekta\.com/)
})
```

### Manual Testing Checklist

**Phase 1 - Multi-Provider**:
- [ ] Polar checkout (US customer)
- [ ] Conekta checkout (MX customer)
- [ ] Stripe fallback (sanctioned country)
- [ ] Webhook processing for all providers
- [ ] Subscription activation/cancellation
- [ ] Customer portal access

**Phase 2 - Plugin**:
- [ ] Install plugin in new Next.js app
- [ ] Configure with Polar credentials
- [ ] Add checkout button
- [ ] Complete payment flow
- [ ] Access customer portal
- [ ] View subscription status

**Phase 3 - Dogfooding**:
- [ ] Plinto demo app pricing page
- [ ] Subscribe to Pro plan via plugin
- [ ] Manage subscription via portal
- [ ] Cancel and verify access retention
- [ ] Performance and UX validation

---

## 📊 Success Metrics

### Business KPIs

**Payment Coverage**:
- Target: 100% global coverage
- Polar: ~180 countries
- Conekta: Mexico (56M credit cards)
- Stripe: Universal fallback

**Payment Success Rate**:
- Target: >95% across all providers
- Track by provider and region
- Monitor decline reasons

**Revenue Growth**:
- International revenue via Polar
- Mexican revenue via Conekta
- Compare vs previous Fungies.io baseline

**Customer Satisfaction**:
- Plugin integration survey: >90% satisfaction
- Checkout experience NPS: >50
- Support ticket reduction: 60%+

### Technical KPIs

**Performance**:
- Checkout creation: <200ms
- Webhook processing: <500ms
- Portal URL generation: <150ms
- API uptime: >99.9%

**Plugin Adoption**:
- Beta users: 5-10 early adopters
- Integration time: <5 minutes average
- Documentation satisfaction: >90%
- GitHub stars: Track community interest

**Dogfooding Validation**:
- Real transactions processed
- No critical bugs in production
- Performance benchmarks met
- UX feedback incorporated

---

## 🚀 Deployment Strategy

### Phase 1 Deployment (Weeks 1-2)

**Week 1: Development Environment**
```bash
# Set up all providers in sandbox mode
export POLAR_SANDBOX=true
export CONEKTA_SANDBOX=true
export STRIPE_TEST_MODE=true

# Run migrations
alembic upgrade head

# Start development server
uvicorn main:app --reload
```

**Week 2: Staging Deployment**
- Deploy to staging with all sandbox credentials
- Run full integration test suite
- Manual testing of all payment flows
- Load test webhook processing (1000 events/min)

### Phase 2 Deployment (Weeks 3-4)

**Week 3: Plugin Beta**
- Publish beta version to npm with `-beta` tag
- Invite 5-10 beta users to test
- Collect feedback and iterate
- Monitor integration issues

**Week 4: Plugin Production**
- Publish stable version to npm
- Announce plugin availability
- Update documentation
- Marketing campaign

### Phase 3 Deployment (Weeks 5-6)

**Week 5: Internal Dogfooding**
- Deploy Plinto demo app with plugin
- Internal team testing
- Real transaction processing
- Performance monitoring

**Week 6: Public Launch**
- Announce dogfooding case study
- Publish blog post
- Submit to Product Hunt
- Marketing push

---

## 📚 Documentation Deliverables

### For Developers (Internal)
- [ ] Multi-provider architecture guide
- [ ] Payment router logic documentation
- [ ] Webhook testing guide
- [ ] Deployment runbook
- [ ] Troubleshooting guide

### For Plugin Users (External)
- [ ] Polar plugin quick start (<5 min)
- [ ] Complete API reference
- [ ] TypeScript type definitions
- [ ] Example implementations (Next.js, React, Vue, Angular)
- [ ] Migration guide (from Stripe, other providers)
- [ ] Video tutorial (setup and integration)

### For Marketing
- [ ] Dogfooding case study blog post
- [ ] Comparison: Plinto vs Clerk vs Auth0 (pricing + features)
- [ ] Plugin announcement post
- [ ] Social media content
- [ ] Product Hunt launch materials

---

## 🎯 Competitive Advantages

### vs Clerk
- **Lower Cost**: $0.005/MAU vs $0.02/MAU (4x cheaper)
- **Polar Plugin**: Easy monetization for customers (Clerk doesn't offer this)
- **Self-Hosting**: Open-core model with deployment flexibility
- **Multi-Provider**: Optimized routing (Conekta MX + Polar global + Stripe fallback)

### vs Auth0
- **Simpler Pricing**: Transparent MAU-based vs complex tiers
- **Faster Integration**: <5 min plugin setup vs 30+ min Auth0 billing integration
- **Better DX**: Modern API, better docs, React components included
- **Dogfooding**: Real-world validation we actually use our own product

### vs Better-Auth
- **Production-Ready**: Battle-tested infrastructure vs early-stage
- **Multi-Provider**: Intelligent routing vs single provider
- **Complete Platform**: Auth + Billing + Organizations in one
- **Enterprise Support**: SLA and dedicated support available

---

## 🔄 Migration Strategy

### From Existing Billing (Fungies.io)

**Week 1: Parallel Operation**
- Deploy multi-provider infrastructure
- Route 10% of new customers to Polar
- Monitor success rates and errors
- Keep Fungies.io as fallback

**Week 2: Gradual Rollout**
- Increase to 50% on Polar
- Migrate existing subscriptions (with notification)
- A/B test user experience
- Address any issues

**Week 3: Full Migration**
- Route 100% to multi-provider system
- Complete subscription migrations
- Deprecate Fungies.io integration
- Archive legacy payment data

**Week 4: Cleanup**
- Remove Fungies.io code
- Update billing reports
- Celebrate success 🎉

---

## ✅ Roadmap Checklist

### Phase 1: Multi-Provider Infrastructure ✅
- [ ] Database models and migrations
- [ ] PaymentProviderRouter service
- [ ] UnifiedBillingService implementation
- [ ] Provider-specific services (Polar, Conekta, Stripe)
- [ ] API endpoints for checkout, webhooks, portal
- [ ] Webhook signature verification
- [ ] Integration tests for all providers
- [ ] Staging deployment and validation

### Phase 2: Plinto Polar Plugin ✅
- [ ] PolarPlugin TypeScript SDK class
- [ ] SDK integration in PlintoClient
- [ ] PolarCheckoutButton React component
- [ ] PolarCustomerPortal React component
- [ ] SubscriptionStatus React component
- [ ] TypeScript type definitions
- [ ] Plugin documentation (<5 min quickstart)
- [ ] Beta testing with 5-10 users
- [ ] NPM package publication

### Phase 3: Dogfooding & Launch ✅
- [ ] Integrate plugin in Plinto demo app
- [ ] Pricing page with checkout buttons
- [ ] Settings page with subscription management
- [ ] Real transaction processing
- [ ] Performance and UX validation
- [ ] Case study blog post
- [ ] Video tutorial
- [ ] Public launch and marketing

---

## 🎉 Expected Outcomes

### Technical Excellence
- ✅ 100% payment coverage (Polar + Conekta + Stripe)
- ✅ >95% payment success rate
- ✅ <5 minute plugin integration
- ✅ Production-grade infrastructure

### Business Impact
- ✅ 4x pricing advantage vs Clerk
- ✅ Unique plugin differentiator
- ✅ Real-world dogfooding validation
- ✅ Revenue growth through better payment infrastructure

### Developer Experience
- ✅ Dead-simple plugin integration
- ✅ Type-safe TypeScript SDK
- ✅ React components out of the box
- ✅ Comprehensive documentation

### Market Position
- ✅ Only auth provider offering Polar plugin
- ✅ Multi-provider optimization (not just Stripe)
- ✅ Proven through dogfooding
- ✅ Community validation and adoption

---

**Roadmap Version**: 1.0  
**Timeline**: 6 weeks (3 two-week phases)  
**Status**: 📋 Ready for implementation approval  
**Next Step**: Team review and resource allocation

---

*Plinto Payment Infrastructure Roadmap | November 16, 2025*
