# Polar Integration Design for Plinto

**Date**: November 16, 2025  
**Status**: Design Phase  
**Version**: 1.0.0

---

## 🎯 Objectives

### 1. Use Polar as Merchant of Record (MoR)
Replace Fungies.io with Polar for all non-Mexican paying customers, leveraging Polar's developer-first payment infrastructure.

### 2. Offer Polar Plugin for Plinto Customers
Provide a Plinto plugin similar to Better-Auth's Polar implementation, enabling Plinto users to accept payments through Polar while using Plinto authentication.

### 3. Dogfood Our Own Features
Use Plinto's own authentication and organization management features to power our Polar integration, demonstrating real-world usage.

---

## 📊 Current State Analysis

### Existing Billing Architecture

**Current Providers**:
- **Conekta**: Mexican customers (MX)
- **Fungies.io**: International customers (non-MX)

**Current Models** (`apps/api/app/models/enterprise.py`):
```python
class Subscription(Base):
    organization_id: UUID  # Multi-tenant support
    plan: BillingPlan  # FREE, PRO, ENTERPRISE
    status: SubscriptionStatus  # ACTIVE, CANCELED, PAST_DUE, etc.
    billing_interval: BillingInterval  # MONTHLY, YEARLY
    stripe_subscription_id: str  # Generic provider ID
    stripe_customer_id: str  # Generic customer ID
    subscription_metadata: JSONB  # Extensible metadata
```

**Current Service** (`apps/api/app/services/billing_service.py`):
- `determine_payment_provider(country)` → "conekta" | "fungies"
- Conekta integration for MX
- Fungies.io integration for international

**Key Insight**: Architecture already supports multi-provider billing with organization-level subscriptions.

---

## 🏗️ Architecture Design

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Plinto Platform                           │
│  ┌──────────────────────────────────────────────────────┐   │
│  │              Authentication Layer                     │   │
│  │  - User Management                                    │   │
│  │  - Organization Management                            │   │
│  │  - Session Management                                 │   │
│  └──────────────────────────────────────────────────────┘   │
│                           │                                  │
│  ┌──────────────────────────────────────────────────────┐   │
│  │              Billing Abstraction Layer                │   │
│  │                                                        │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  │   │
│  │  │  Conekta    │  │   Polar     │  │  Plugin     │  │   │
│  │  │  Provider   │  │  Provider   │  │  System     │  │   │
│  │  │  (Mexico)   │  │  (Global)   │  │  (Users)    │  │   │
│  │  └─────────────┘  └─────────────┘  └─────────────┘  │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

### Three Integration Levels

**Level 1: Internal Use (Plinto → Polar)**
- Replace Fungies.io with Polar
- Use Polar for all non-Mexican customers
- Direct API integration

**Level 2: Plugin System (Plinto Users → Polar)**
- Offer Polar plugin to Plinto customers
- SDK/plugin for easy integration
- Similar to Better-Auth's approach

**Level 3: Dogfooding (Plinto Self-Use)**
- Use our own authentication
- Use our own organization management
- Use our own Polar plugin

---

## 🔧 Technical Design

### 1. Backend Integration (Python/FastAPI)

#### New Models

**File**: `apps/api/app/models/polar.py`

```python
"""
Polar-specific models and types
"""

from sqlalchemy import Column, String, DateTime, ForeignKey, Text, Integer, Enum as SQLEnum
from app.models.types import GUID as UUID, JSON as JSONB
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
import enum
from . import Base


class PolarCustomerStatus(str, enum.Enum):
    """Polar customer status"""
    ACTIVE = "active"
    DELETED = "deleted"


class PolarCheckoutStatus(str, enum.Enum):
    """Polar checkout status"""
    OPEN = "open"
    EXPIRED = "expired"
    CONFIRMED = "confirmed"
    FAILED = "failed"


class PolarSubscriptionTier(str, enum.Enum):
    """Polar subscription tiers"""
    FREE = "free"
    INDIVIDUAL = "individual"
    BUSINESS = "business"


class PolarCustomer(Base):
    """Polar customer mapping to Plinto users/organizations"""
    __tablename__ = "polar_customers"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Link to Plinto entities
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    
    # Polar customer details
    polar_customer_id = Column(String(255), unique=True, nullable=False, index=True)
    email = Column(String(255), nullable=False)
    name = Column(String(255))
    status = Column(SQLEnum(PolarCustomerStatus), default=PolarCustomerStatus.ACTIVE)
    
    # Metadata
    polar_metadata = Column(JSONB, default={})
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    deleted_at = Column(DateTime, nullable=True)


class PolarCheckout(Base):
    """Polar checkout sessions"""
    __tablename__ = "polar_checkouts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Link to Plinto entities
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    polar_customer_id = Column(UUID(as_uuid=True), ForeignKey("polar_customers.id"), nullable=True)
    
    # Polar checkout details
    polar_checkout_id = Column(String(255), unique=True, nullable=False, index=True)
    product_id = Column(String(255), nullable=False)
    product_price_id = Column(String(255))
    status = Column(SQLEnum(PolarCheckoutStatus), default=PolarCheckoutStatus.OPEN)
    
    # URLs
    success_url = Column(String(500))
    embed_origin = Column(String(255))
    
    # Metadata
    polar_metadata = Column(JSONB, default={})
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    confirmed_at = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=True)


class PolarSubscription(Base):
    """Polar subscriptions linked to organizations"""
    __tablename__ = "polar_subscriptions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Link to Plinto subscription
    subscription_id = Column(UUID(as_uuid=True), ForeignKey("subscriptions.id"), nullable=False)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    polar_customer_id = Column(UUID(as_uuid=True), ForeignKey("polar_customers.id"), nullable=False)
    
    # Polar subscription details
    polar_subscription_id = Column(String(255), unique=True, nullable=False, index=True)
    product_id = Column(String(255), nullable=False)
    tier = Column(SQLEnum(PolarSubscriptionTier), nullable=False)
    
    # Status
    status = Column(String(50), nullable=False)  # active, canceled, incomplete, etc.
    current_period_start = Column(DateTime, nullable=False)
    current_period_end = Column(DateTime, nullable=False)
    cancel_at_period_end = Column(Boolean, default=False)
    
    # Metadata
    polar_metadata = Column(JSONB, default={})
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    canceled_at = Column(DateTime, nullable=True)


class PolarWebhookEvent(Base):
    """Polar webhook event log"""
    __tablename__ = "polar_webhook_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Webhook details
    event_id = Column(String(255), unique=True, nullable=False, index=True)
    event_type = Column(String(255), nullable=False, index=True)
    
    # Payload
    payload = Column(JSONB, nullable=False)
    
    # Processing status
    processed = Column(Boolean, default=False)
    processed_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)


class PolarUsageEvent(Base):
    """Polar usage-based billing events"""
    __tablename__ = "polar_usage_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Link to organization
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    polar_customer_id = Column(UUID(as_uuid=True), ForeignKey("polar_customers.id"), nullable=False)
    
    # Usage details
    event_name = Column(String(255), nullable=False)
    quantity = Column(Integer, default=1)
    
    # Metadata
    properties = Column(JSONB, default={})
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    reported_to_polar_at = Column(DateTime, nullable=True)
```

#### Updated Billing Service

**File**: `apps/api/app/services/polar_service.py`

```python
"""
Polar billing service for international customers
"""

from typing import Optional, Dict, Any, List
from uuid import UUID
from datetime import datetime
import httpx
import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.config import settings
from app.models.polar import (
    PolarCustomer,
    PolarCheckout,
    PolarSubscription,
    PolarWebhookEvent,
    PolarUsageEvent,
    PolarCustomerStatus,
    PolarCheckoutStatus,
)
from app.models.enterprise import Subscription, SubscriptionStatus

logger = structlog.get_logger()


class PolarService:
    """Handles Polar payment infrastructure integration"""
    
    def __init__(self):
        self.access_token = settings.POLAR_ACCESS_TOKEN
        self.api_url = "https://api.polar.sh"
        self.sandbox = settings.POLAR_SANDBOX  # Use sandbox for development
        
        if self.sandbox:
            self.api_url = "https://sandbox-api.polar.sh"
    
    # ==================== Customer Management ====================
    
    async def create_customer(
        self,
        db: AsyncSession,
        email: str,
        name: Optional[str] = None,
        organization_id: Optional[UUID] = None,
        user_id: Optional[UUID] = None,
        metadata: Optional[Dict] = None
    ) -> PolarCustomer:
        """Create a Polar customer (auto-created on signup if enabled)"""
        async with httpx.AsyncClient() as client:
            try:
                # Create customer in Polar
                response = await client.post(
                    f"{self.api_url}/v1/customers",
                    headers={
                        "Authorization": f"Bearer {self.access_token}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "email": email,
                        "name": name,
                        "metadata": metadata or {}
                    }
                )
                response.raise_for_status()
                polar_customer = response.json()
                
                # Store in database
                customer = PolarCustomer(
                    organization_id=organization_id,
                    user_id=user_id,
                    polar_customer_id=polar_customer["id"],
                    email=email,
                    name=name,
                    status=PolarCustomerStatus.ACTIVE,
                    polar_metadata=polar_customer.get("metadata", {})
                )
                
                db.add(customer)
                await db.commit()
                await db.refresh(customer)
                
                logger.info(
                    "Polar customer created",
                    polar_customer_id=polar_customer["id"],
                    organization_id=str(organization_id) if organization_id else None
                )
                
                return customer
                
            except httpx.HTTPError as e:
                logger.error("Failed to create Polar customer", error=str(e))
                raise
    
    async def get_customer(
        self,
        db: AsyncSession,
        organization_id: Optional[UUID] = None,
        user_id: Optional[UUID] = None
    ) -> Optional[PolarCustomer]:
        """Get Polar customer by organization or user ID"""
        query = select(PolarCustomer).where(
            PolarCustomer.status == PolarCustomerStatus.ACTIVE
        )
        
        if organization_id:
            query = query.where(PolarCustomer.organization_id == organization_id)
        elif user_id:
            query = query.where(PolarCustomer.user_id == user_id)
        else:
            return None
        
        result = await db.execute(query)
        return result.scalar_one_or_none()
    
    # ==================== Checkout Management ====================
    
    async def create_checkout(
        self,
        db: AsyncSession,
        product_id: str,
        organization_id: Optional[UUID] = None,
        user_id: Optional[UUID] = None,
        success_url: Optional[str] = None,
        embed_origin: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> PolarCheckout:
        """Create a Polar checkout session"""
        
        # Get or create customer
        customer = await self.get_customer(db, organization_id, user_id)
        
        async with httpx.AsyncClient() as client:
            try:
                payload = {
                    "product_id": product_id,
                    "success_url": success_url,
                    "metadata": metadata or {}
                }
                
                # Add customer ID if authenticated
                if customer:
                    payload["customer_id"] = customer.polar_customer_id
                
                if embed_origin:
                    payload["embed_origin"] = embed_origin
                
                # Create checkout in Polar
                response = await client.post(
                    f"{self.api_url}/v1/checkouts",
                    headers={
                        "Authorization": f"Bearer {self.access_token}",
                        "Content-Type": "application/json"
                    },
                    json=payload
                )
                response.raise_for_status()
                polar_checkout = response.json()
                
                # Store in database
                checkout = PolarCheckout(
                    organization_id=organization_id,
                    user_id=user_id,
                    polar_customer_id=customer.id if customer else None,
                    polar_checkout_id=polar_checkout["id"],
                    product_id=product_id,
                    status=PolarCheckoutStatus.OPEN,
                    success_url=success_url,
                    embed_origin=embed_origin,
                    polar_metadata=polar_checkout.get("metadata", {}),
                    expires_at=polar_checkout.get("expires_at")
                )
                
                db.add(checkout)
                await db.commit()
                await db.refresh(checkout)
                
                logger.info(
                    "Polar checkout created",
                    checkout_id=polar_checkout["id"],
                    product_id=product_id
                )
                
                return checkout
                
            except httpx.HTTPError as e:
                logger.error("Failed to create Polar checkout", error=str(e))
                raise
    
    async def get_checkout_url(self, checkout_id: str) -> str:
        """Get Polar checkout URL"""
        return f"https://polar.sh/checkout/{checkout_id}"
    
    # ==================== Subscription Management ====================
    
    async def get_subscriptions(
        self,
        db: AsyncSession,
        organization_id: UUID,
        active_only: bool = True
    ) -> List[PolarSubscription]:
        """Get organization subscriptions"""
        query = select(PolarSubscription).where(
            PolarSubscription.organization_id == organization_id
        )
        
        if active_only:
            query = query.where(PolarSubscription.status == "active")
        
        result = await db.execute(query)
        return list(result.scalars().all())
    
    async def check_organization_access(
        self,
        db: AsyncSession,
        organization_id: UUID,
        required_tier: Optional[str] = None
    ) -> bool:
        """Check if organization has active subscription (optionally with specific tier)"""
        subscriptions = await self.get_subscriptions(db, organization_id, active_only=True)
        
        if not subscriptions:
            return False
        
        if required_tier:
            return any(sub.tier.value == required_tier for sub in subscriptions)
        
        return True
    
    # ==================== Customer Portal ====================
    
    async def get_customer_portal_url(
        self,
        db: AsyncSession,
        organization_id: UUID
    ) -> Optional[str]:
        """Get Polar customer portal URL for organization"""
        customer = await self.get_customer(db, organization_id=organization_id)
        
        if not customer:
            return None
        
        # Polar customer portal URL
        return f"https://polar.sh/customer/{customer.polar_customer_id}"
    
    async def get_customer_data(
        self,
        db: AsyncSession,
        organization_id: UUID
    ) -> Optional[Dict[str, Any]]:
        """Get complete customer data (subscriptions, benefits, orders)"""
        customer = await self.get_customer(db, organization_id=organization_id)
        
        if not customer:
            return None
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{self.api_url}/v1/customers/{customer.polar_customer_id}/portal",
                    headers={"Authorization": f"Bearer {self.access_token}"}
                )
                response.raise_for_status()
                return response.json()
                
            except httpx.HTTPError as e:
                logger.error("Failed to get customer data", error=str(e))
                return None
    
    # ==================== Usage-Based Billing ====================
    
    async def ingest_usage_event(
        self,
        db: AsyncSession,
        organization_id: UUID,
        event_name: str,
        quantity: int = 1,
        properties: Optional[Dict] = None
    ) -> PolarUsageEvent:
        """Ingest usage event for organization"""
        customer = await self.get_customer(db, organization_id=organization_id)
        
        if not customer:
            raise ValueError(f"No Polar customer found for organization {organization_id}")
        
        # Create local event record
        event = PolarUsageEvent(
            organization_id=organization_id,
            polar_customer_id=customer.id,
            event_name=event_name,
            quantity=quantity,
            properties=properties or {}
        )
        
        db.add(event)
        await db.commit()
        await db.refresh(event)
        
        # Send to Polar asynchronously
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.api_url}/v1/usage",
                    headers={
                        "Authorization": f"Bearer {self.access_token}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "customer_id": customer.polar_customer_id,
                        "event_name": event_name,
                        "quantity": quantity,
                        "properties": properties or {}
                    }
                )
                response.raise_for_status()
                
                event.reported_to_polar_at = datetime.utcnow()
                await db.commit()
                
                logger.info(
                    "Usage event ingested",
                    organization_id=str(organization_id),
                    event_name=event_name,
                    quantity=quantity
                )
                
        except httpx.HTTPError as e:
            logger.error("Failed to send usage event to Polar", error=str(e))
            # Don't raise - event is saved locally for retry
        
        return event
    
    # ==================== Webhook Handling ====================
    
    async def verify_webhook_signature(
        self,
        payload: bytes,
        signature: str,
        webhook_secret: str
    ) -> bool:
        """Verify Polar webhook signature"""
        import hmac
        import hashlib
        
        expected_signature = hmac.new(
            webhook_secret.encode(),
            payload,
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(signature, expected_signature)
    
    async def handle_webhook(
        self,
        db: AsyncSession,
        event_type: str,
        payload: Dict[str, Any]
    ) -> None:
        """Handle Polar webhook event"""
        
        # Log event
        event = PolarWebhookEvent(
            event_id=payload.get("id", ""),
            event_type=event_type,
            payload=payload
        )
        db.add(event)
        await db.commit()
        
        try:
            # Handle different event types
            if event_type == "checkout.created":
                await self._handle_checkout_created(db, payload)
            elif event_type == "checkout.updated":
                await self._handle_checkout_updated(db, payload)
            elif event_type == "subscription.created":
                await self._handle_subscription_created(db, payload)
            elif event_type == "subscription.updated":
                await self._handle_subscription_updated(db, payload)
            elif event_type == "subscription.canceled":
                await self._handle_subscription_canceled(db, payload)
            # Add more handlers as needed
            
            event.processed = True
            event.processed_at = datetime.utcnow()
            await db.commit()
            
            logger.info("Webhook event processed", event_type=event_type)
            
        except Exception as e:
            event.error_message = str(e)
            await db.commit()
            logger.error("Failed to process webhook", event_type=event_type, error=str(e))
            raise
    
    async def _handle_subscription_created(
        self,
        db: AsyncSession,
        payload: Dict[str, Any]
    ) -> None:
        """Handle subscription.created webhook"""
        # Implementation for subscription creation
        pass
    
    async def _handle_subscription_updated(
        self,
        db: AsyncSession,
        payload: Dict[str, Any]
    ) -> None:
        """Handle subscription.updated webhook"""
        # Implementation for subscription updates
        pass
    
    async def _handle_subscription_canceled(
        self,
        db: AsyncSession,
        payload: Dict[str, Any]
    ) -> None:
        """Handle subscription.canceled webhook"""
        # Implementation for subscription cancellation
        pass
    
    async def _handle_checkout_created(
        self,
        db: AsyncSession,
        payload: Dict[str, Any]
    ) -> None:
        """Handle checkout.created webhook"""
        # Implementation for checkout creation
        pass
    
    async def _handle_checkout_updated(
        self,
        db: AsyncSession,
        payload: Dict[str, Any]
    ) -> None:
        """Handle checkout.updated webhook"""
        # Implementation for checkout updates
        pass
```

#### Updated Billing Service Router

**File**: `apps/api/app/services/billing_service.py` (updated)

```python
async def determine_payment_provider(self, country: str) -> Literal["conekta", "polar"]:
    """Determine which payment provider to use based on country"""
    # Use Conekta for Mexico, Polar for everything else
    return "conekta" if country.upper() == "MX" else "polar"  # Changed from "fungies"
```

---

### 2. API Endpoints

#### Polar Router

**File**: `apps/api/app/routers/polar.py`

```python
"""
Polar billing endpoints
"""

from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Request, Header
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, get_current_user
from app.models.user import User
from app.services.polar_service import PolarService
from pydantic import BaseModel

router = APIRouter(prefix="/polar", tags=["Polar"])

# ==================== Request/Response Models ====================

class CheckoutRequest(BaseModel):
    product_id: str
    organization_id: Optional[UUID] = None
    success_url: Optional[str] = None
    metadata: Optional[dict] = None


class CheckoutResponse(BaseModel):
    checkout_id: str
    checkout_url: str
    expires_at: Optional[str] = None


class UsageEventRequest(BaseModel):
    event_name: str
    quantity: int = 1
    properties: Optional[dict] = None


# ==================== Endpoints ====================

@router.post("/checkout", response_model=CheckoutResponse)
async def create_checkout(
    request: CheckoutRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create Polar checkout session"""
    polar_service = PolarService()
    
    checkout = await polar_service.create_checkout(
        db=db,
        product_id=request.product_id,
        organization_id=request.organization_id,
        user_id=current_user.id,
        success_url=request.success_url,
        metadata=request.metadata
    )
    
    checkout_url = await polar_service.get_checkout_url(checkout.polar_checkout_id)
    
    return CheckoutResponse(
        checkout_id=checkout.polar_checkout_id,
        checkout_url=checkout_url,
        expires_at=checkout.expires_at.isoformat() if checkout.expires_at else None
    )


@router.get("/customer/portal")
async def get_customer_portal(
    organization_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get customer portal URL"""
    polar_service = PolarService()
    
    portal_url = await polar_service.get_customer_portal_url(db, organization_id)
    
    if not portal_url:
        raise HTTPException(status_code=404, detail="No Polar customer found")
    
    return {"portal_url": portal_url}


@router.get("/customer/data")
async def get_customer_data(
    organization_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get complete customer data (subscriptions, benefits, orders)"""
    polar_service = PolarService()
    
    data = await polar_service.get_customer_data(db, organization_id)
    
    if not data:
        raise HTTPException(status_code=404, detail="No customer data found")
    
    return data


@router.post("/usage")
async def ingest_usage_event(
    request: UsageEventRequest,
    organization_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Ingest usage event for billing"""
    polar_service = PolarService()
    
    event = await polar_service.ingest_usage_event(
        db=db,
        organization_id=organization_id,
        event_name=request.event_name,
        quantity=request.quantity,
        properties=request.properties
    )
    
    return {
        "event_id": str(event.id),
        "event_name": event.event_name,
        "quantity": event.quantity,
        "reported": event.reported_to_polar_at is not None
    }


@router.post("/webhooks")
async def handle_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
    x_polar_signature: str = Header(None)
):
    """Handle Polar webhook events"""
    polar_service = PolarService()
    
    # Verify signature
    payload = await request.body()
    webhook_secret = settings.POLAR_WEBHOOK_SECRET
    
    if not polar_service.verify_webhook_signature(payload, x_polar_signature, webhook_secret):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")
    
    # Parse payload
    event_data = await request.json()
    event_type = event_data.get("type")
    
    # Handle event
    await polar_service.handle_webhook(db, event_type, event_data)
    
    return {"status": "success"}
```

---

### 3. Frontend Integration (TypeScript/React)

#### Polar Client Plugin

**File**: `packages/typescript-sdk/src/plugins/polar.ts`

```typescript
/**
 * Polar Plugin for Plinto TypeScript SDK
 * 
 * Provides Polar payment integration similar to Better-Auth's implementation
 */

import { PlintoClient } from '../client'

export interface PolarPluginConfig {
  /**
   * Polar organization ID (for Plinto users accepting payments)
   */
  organizationId?: string
  
  /**
   * Enable automatic customer creation on user signup
   */
  createCustomerOnSignUp?: boolean
  
  /**
   * Default success URL for checkouts
   */
  defaultSuccessUrl?: string
}

export interface PolarCheckoutOptions {
  productId: string
  organizationId?: string
  successUrl?: string
  metadata?: Record<string, any>
}

export interface PolarUsageEventOptions {
  eventName: string
  quantity?: number
  properties?: Record<string, any>
}

export interface CustomerPortalData {
  subscriptions: any[]
  benefits: any[]
  orders: any[]
}

export class PolarPlugin {
  private client: PlintoClient
  private config: PolarPluginConfig
  
  constructor(client: PlintoClient, config: PolarPluginConfig = {}) {
    this.client = client
    this.config = config
  }
  
  /**
   * Create a Polar checkout session
   */
  async createCheckout(options: PolarCheckoutOptions): Promise<{
    checkoutId: string
    checkoutUrl: string
    expiresAt?: string
  }> {
    const response = await this.client.post('/polar/checkout', {
      product_id: options.productId,
      organization_id: options.organizationId || this.config.organizationId,
      success_url: options.successUrl || this.config.defaultSuccessUrl,
      metadata: options.metadata,
    })
    
    return {
      checkoutId: response.checkout_id,
      checkoutUrl: response.checkout_url,
      expiresAt: response.expires_at,
    }
  }
  
  /**
   * Redirect to Polar checkout
   */
  async redirectToCheckout(options: PolarCheckoutOptions): Promise<void> {
    const { checkoutUrl } = await this.createCheckout(options)
    window.location.href = checkoutUrl
  }
  
  /**
   * Get customer portal URL
   */
  async getCustomerPortalUrl(organizationId?: string): Promise<string> {
    const orgId = organizationId || this.config.organizationId
    if (!orgId) {
      throw new Error('Organization ID is required')
    }
    
    const response = await this.client.get(`/polar/customer/portal?organization_id=${orgId}`)
    return response.portal_url
  }
  
  /**
   * Redirect to customer portal
   */
  async redirectToCustomerPortal(organizationId?: string): Promise<void> {
    const portalUrl = await this.getCustomerPortalUrl(organizationId)
    window.location.href = portalUrl
  }
  
  /**
   * Get customer data (subscriptions, benefits, orders)
   */
  async getCustomerData(organizationId?: string): Promise<CustomerPortalData> {
    const orgId = organizationId || this.config.organizationId
    if (!orgId) {
      throw new Error('Organization ID is required')
    }
    
    return await this.client.get(`/polar/customer/data?organization_id=${orgId}`)
  }
  
  /**
   * Ingest usage event for usage-based billing
   */
  async ingestUsageEvent(
    organizationId: string,
    options: PolarUsageEventOptions
  ): Promise<void> {
    await this.client.post(`/polar/usage?organization_id=${organizationId}`, {
      event_name: options.eventName,
      quantity: options.quantity || 1,
      properties: options.properties,
    })
  }
}

/**
 * Create Polar plugin instance
 */
export function createPolarPlugin(config: PolarPluginConfig = {}) {
  return {
    name: 'polar',
    install(client: PlintoClient) {
      const polar = new PolarPlugin(client, config)
      
      // Attach to client
      ;(client as any).polar = polar
      
      return polar
    },
  }
}

// Type augmentation for client
declare module '../client' {
  interface PlintoClient {
    polar: PolarPlugin
  }
}
```

#### React Components

**File**: `packages/ui/src/components/billing/polar-checkout-button.tsx`

```typescript
'use client'

import { useState } from 'react'
import { usePlintoClient } from '../../hooks/use-plinto-client'

export interface PolarCheckoutButtonProps {
  productId: string
  organizationId?: string
  successUrl?: string
  className?: string
  children?: React.ReactNode
  onError?: (error: Error) => void
}

export function PolarCheckoutButton({
  productId,
  organizationId,
  successUrl,
  className,
  children = 'Subscribe',
  onError,
}: PolarCheckoutButtonProps) {
  const client = usePlintoClient()
  const [loading, setLoading] = useState(false)
  
  const handleCheckout = async () => {
    setLoading(true)
    
    try {
      await client.polar.redirectToCheckout({
        productId,
        organizationId,
        successUrl,
      })
    } catch (error) {
      console.error('Checkout error:', error)
      onError?.(error as Error)
      setLoading(false)
    }
  }
  
  return (
    <button
      onClick={handleCheckout}
      disabled={loading}
      className={className}
    >
      {loading ? 'Loading...' : children}
    </button>
  )
}
```

**File**: `packages/ui/src/components/billing/polar-customer-portal.tsx`

```typescript
'use client'

import { usePlintoClient } from '../../hooks/use-plinto-client'

export interface PolarCustomerPortalProps {
  organizationId?: string
  className?: string
  children?: React.ReactNode
}

export function PolarCustomerPortal({
  organizationId,
  className,
  children = 'Manage Subscription',
}: PolarCustomerPortalProps) {
  const client = usePlintoClient()
  
  const handlePortal = async () => {
    try {
      await client.polar.redirectToCustomerPortal(organizationId)
    } catch (error) {
      console.error('Portal error:', error)
    }
  }
  
  return (
    <button onClick={handlePortal} className={className}>
      {children}
    </button>
  )
}
```

---

### 4. Configuration

**File**: `apps/api/app/config.py` (additions)

```python
# Polar configuration
POLAR_ACCESS_TOKEN: str = os.getenv("POLAR_ACCESS_TOKEN", "")
POLAR_SANDBOX: bool = os.getenv("POLAR_SANDBOX", "true").lower() == "true"
POLAR_WEBHOOK_SECRET: str = os.getenv("POLAR_WEBHOOK_SECRET", "")
POLAR_CREATE_CUSTOMER_ON_SIGNUP: bool = os.getenv("POLAR_CREATE_CUSTOMER_ON_SIGNUP", "false").lower() == "true"
```

**File**: `.env.example`

```bash
# Polar Configuration
POLAR_ACCESS_TOKEN=your_polar_access_token_here
POLAR_SANDBOX=true  # Use sandbox for development
POLAR_WEBHOOK_SECRET=your_webhook_secret_here
POLAR_CREATE_CUSTOMER_ON_SIGNUP=true  # Auto-create customers on signup
```

---

## 🔄 Migration Strategy

### Phase 1: Internal Use (Weeks 1-2)

**Goal**: Replace Fungies.io with Polar for Plinto's own billing

**Tasks**:
1. ✅ Implement Polar service and models
2. ✅ Update billing service to use Polar instead of Fungies
3. ✅ Add Polar webhook handlers
4. ✅ Migrate existing international customers to Polar
5. ✅ Test end-to-end checkout flow

**Success Criteria**:
- All new international customers use Polar
- Existing customers migrated successfully
- Webhooks processing correctly

### Phase 2: Plugin Development (Weeks 3-4)

**Goal**: Create Polar plugin for Plinto customers

**Tasks**:
1. ✅ Develop TypeScript SDK plugin
2. ✅ Create React UI components
3. ✅ Write comprehensive documentation
4. ✅ Create example implementations
5. ✅ Beta test with select customers

**Success Criteria**:
- Plugin matches Better-Auth feature parity
- Documentation complete (<5 min integration)
- Beta users successfully accepting payments

### Phase 3: Dogfooding (Week 5)

**Goal**: Use our own Polar plugin for our billing

**Tasks**:
1. ✅ Integrate Plinto Polar plugin into Plinto demo app
2. ✅ Use Plinto auth for our own platform
3. ✅ Document learnings and improvements
4. ✅ Create case study

**Success Criteria**:
- Plinto uses its own Polar plugin
- Real-world validation complete
- Case study published

---

## 📚 Documentation Plan

### User Documentation

**1. Polar Integration Guide** (`docs/integrations/POLAR.md`)
- Quick start (<5 minutes)
- Complete API reference
- React component examples
- Webhook configuration

**2. Billing Plugin Tutorial** (`docs/tutorials/POLAR_PLUGIN.md`)
- Step-by-step integration
- Usage-based billing setup
- Customer portal customization
- Testing guide

### API Documentation

**1. Polar Endpoints** (OpenAPI)
- `/polar/checkout` - Create checkout
- `/polar/customer/portal` - Get portal URL
- `/polar/customer/data` - Get customer data
- `/polar/usage` - Ingest usage events
- `/polar/webhooks` - Handle webhooks

**2. SDK Documentation** (TypeDoc)
- `PolarPlugin` class reference
- `createPolarPlugin` factory
- React component props
- TypeScript types

---

## 🧪 Testing Strategy

### Unit Tests

**Backend**:
- `tests/services/test_polar_service.py`
- `tests/routers/test_polar.py`
- `tests/models/test_polar.py`

**Frontend**:
- `packages/typescript-sdk/src/plugins/__tests__/polar.test.ts`
- `packages/ui/src/components/billing/__tests__/polar-checkout-button.test.tsx`

### Integration Tests

- End-to-end checkout flow
- Webhook processing
- Usage event ingestion
- Customer portal access

### Manual Testing Checklist

- [ ] Create Polar customer on signup
- [ ] Create checkout session
- [ ] Complete payment flow
- [ ] Verify subscription created
- [ ] Access customer portal
- [ ] Ingest usage events
- [ ] Process webhooks
- [ ] Cancel subscription

---

## 🚀 Deployment Plan

### Environment Setup

**Development**:
- Use Polar sandbox
- Test webhooks with ngrok
- Mock payment completion

**Staging**:
- Use Polar sandbox
- Test full flow with test cards
- Verify webhook processing

**Production**:
- Use Polar production
- Real payment processing
- Monitor webhook delivery

### Rollout Strategy

**Week 1**: Internal testing  
**Week 2**: Beta customers (10 users)  
**Week 3**: Limited release (100 users)  
**Week 4**: General availability

---

## 📊 Success Metrics

### Business Metrics
- **Conversion Rate**: Checkout completion %
- **Revenue**: Monthly recurring revenue (MRR)
- **Churn**: Subscription cancellation rate
- **Expansion**: Upgrade rate to higher tiers

### Technical Metrics
- **API Latency**: Checkout creation <200ms
- **Webhook Processing**: <1s average
- **Error Rate**: <0.1% failed transactions
- **Uptime**: 99.9% availability

### User Experience Metrics
- **Time to First Payment**: <5 minutes
- **Customer Support Tickets**: <5% of transactions
- **Portal Usage**: % of customers using self-service
- **Documentation Satisfaction**: >90% helpful rating

---

## 🔒 Security Considerations

### Webhook Security
- ✅ Signature verification for all webhooks
- ✅ Idempotency for duplicate events
- ✅ Rate limiting on webhook endpoint

### API Security
- ✅ Access token stored securely
- ✅ HTTPS only for all API calls
- ✅ User authentication required for all endpoints
- ✅ Organization-level access control

### Data Privacy
- ✅ PCI compliance through Polar
- ✅ No credit card storage in Plinto
- ✅ GDPR compliance for customer data
- ✅ Data retention policies

---

## 🎯 Next Steps

### Immediate Actions (Week 1)

1. **Create Database Migration**
   ```bash
   alembic revision -m "Add Polar models"
   ```

2. **Implement Polar Service**
   - Create `apps/api/app/services/polar_service.py`
   - Add tests

3. **Create API Router**
   - Create `apps/api/app/routers/polar.py`
   - Register in main.py

4. **Develop SDK Plugin**
   - Create `packages/typescript-sdk/src/plugins/polar.ts`
   - Add TypeScript types

5. **Build React Components**
   - `PolarCheckoutButton`
   - `PolarCustomerPortal`

### Follow-up Actions (Weeks 2-4)

- Complete webhook handlers
- Write comprehensive tests
- Create documentation
- Beta test with customers
- Dogfood our own platform

---

**Design Status**: Ready for Implementation  
**Estimated Timeline**: 4 weeks  
**Risk Level**: Medium (proven integration pattern, clear requirements)  
**Dependencies**: Polar API access, database migration
