"""
Webhook management endpoints

Force Railway rebuild - clearing potential import cache issues
"""

from typing import List, Optional
from datetime import datetime
import uuid
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import select, func
from pydantic import BaseModel, Field, HttpUrl

from app.database import get_db
from ...models import User, WebhookEndpoint, WebhookEvent, WebhookDelivery
from app.dependencies import get_current_user
from app.services.webhooks import (
    webhook_service,
    WebhookEventType
)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


# Request/Response models
class WebhookEndpointCreate(BaseModel):
    """Request model for creating webhook endpoint"""
    url: HttpUrl = Field(..., description="Webhook endpoint URL")
    events: List[WebhookEventType] = Field(..., description="Events to subscribe to")
    description: Optional[str] = Field(None, description="Endpoint description")
    headers: Optional[dict] = Field(None, description="Custom headers to include")


class WebhookEndpointUpdate(BaseModel):
    """Request model for updating webhook endpoint"""
    url: Optional[HttpUrl] = Field(None, description="New webhook URL")
    events: Optional[List[WebhookEventType]] = Field(None, description="New events list")
    is_active: Optional[bool] = Field(None, description="Enable/disable endpoint")
    description: Optional[str] = Field(None, description="New description")
    headers: Optional[dict] = Field(None, description="New custom headers")


class WebhookEndpointResponse(BaseModel):
    """Response model for webhook endpoint"""
    id: uuid.UUID
    url: str
    secret: str
    events: List[str]
    is_active: bool
    description: Optional[str]
    headers: Optional[dict]
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class WebhookEventResponse(BaseModel):
    """Response model for webhook event"""
    id: uuid.UUID
    type: str
    data: dict
    created_at: datetime
    
    class Config:
        from_attributes = True


class WebhookDeliveryResponse(BaseModel):
    """Response model for webhook delivery"""
    id: uuid.UUID
    webhook_endpoint_id: uuid.UUID
    webhook_event_id: uuid.UUID
    status_code: Optional[int]
    response_body: Optional[str]
    error: Optional[str]
    attempt: int
    delivered_at: Optional[datetime]
    created_at: datetime
    
    class Config:
        from_attributes = True


class WebhookStatsResponse(BaseModel):
    """Response model for webhook statistics"""
    total_deliveries: int
    successful: int
    failed: int
    success_rate: float
    average_delivery_time: float
    period_days: int


class WebhookEndpointListResponse(BaseModel):
    """Response model for listing webhook endpoints"""
    endpoints: List[WebhookEndpointResponse]
    total: int


class WebhookEventListResponse(BaseModel):
    """Response model for listing webhook events"""
    events: List[WebhookEventResponse]
    total: int


# Helper functions
async def check_webhook_permission(
    db: Session,
    user: User,
    endpoint_id: uuid.UUID
) -> WebhookEndpoint:
    """Check if user has permission to manage webhook endpoint"""

    result = await db.execute(select(WebhookEndpoint).where(
        WebhookEndpoint.id == endpoint_id
    ))
    endpoint = result.scalar_one_or_none()
    
    if not endpoint:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Webhook endpoint not found"
        )
    
    # Check if user owns the endpoint or is admin
    if endpoint.user_id != user.id and not user.is_admin:
        # Check if user has organization permission
        if endpoint.organization_id:
            # TODO: Check organization membership and role
            pass
        else:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Permission denied"
            )
    
    return endpoint


# Endpoints
@router.post("/", response_model=WebhookEndpointResponse)
async def create_webhook_endpoint(
    endpoint_data: WebhookEndpointCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new webhook endpoint"""
    
    # Create webhook endpoint
    endpoint = await webhook_service.register_endpoint(
        db,
        url=str(endpoint_data.url),
        events=endpoint_data.events,
        organization_id=None,  # TODO: Add organization support
        description=endpoint_data.description,
        headers=endpoint_data.headers
    )
    
    # Add user association
    endpoint.user_id = current_user.id
    await db.commit()
    await db.refresh(endpoint)
    
    return endpoint


@router.get("/", response_model=WebhookEndpointListResponse)
async def list_webhook_endpoints(
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List webhook endpoints for current user"""

    stmt = select(WebhookEndpoint).where(
        WebhookEndpoint.user_id == current_user.id
    )

    if is_active is not None:
        stmt = stmt.where(WebhookEndpoint.is_active == is_active)

    result = await db.execute(stmt)
    endpoints = result.scalars().all()
    
    return WebhookEndpointListResponse(
        endpoints=endpoints,
        total=len(endpoints)
    )


@router.get("/{endpoint_id}", response_model=WebhookEndpointResponse)
async def get_webhook_endpoint(
    endpoint_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get webhook endpoint details"""
    
    endpoint = await check_webhook_permission(db, current_user, endpoint_id)
    return endpoint


@router.patch("/{endpoint_id}", response_model=WebhookEndpointResponse)
async def update_webhook_endpoint(
    endpoint_id: uuid.UUID,
    update_data: WebhookEndpointUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update webhook endpoint configuration"""
    
    endpoint = await check_webhook_permission(db, current_user, endpoint_id)
    
    # Update endpoint
    updated_endpoint = await webhook_service.update_endpoint(
        db,
        endpoint_id=str(endpoint_id),
        url=str(update_data.url) if update_data.url else None,
        events=update_data.events,
        is_active=update_data.is_active,
        description=update_data.description,
        headers=update_data.headers
    )
    
    return updated_endpoint


@router.delete("/{endpoint_id}")
async def delete_webhook_endpoint(
    endpoint_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete webhook endpoint"""
    
    endpoint = await check_webhook_permission(db, current_user, endpoint_id)
    
    # Delete endpoint
    deleted = await webhook_service.delete_endpoint(db, str(endpoint_id))
    
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete webhook endpoint"
        )
    
    return {"message": "Webhook endpoint deleted successfully"}


@router.post("/{endpoint_id}/test")
async def test_webhook_endpoint(
    endpoint_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Send test webhook to endpoint"""
    
    endpoint = await check_webhook_permission(db, current_user, endpoint_id)
    
    # Send test webhook
    success = await webhook_service.test_endpoint(db, str(endpoint_id))
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to send test webhook"
        )
    
    return {"message": "Test webhook sent successfully"}


@router.get("/{endpoint_id}/stats", response_model=WebhookStatsResponse)
async def get_webhook_endpoint_stats(
    endpoint_id: uuid.UUID,
    days: int = Query(7, description="Number of days to include in stats"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get webhook endpoint delivery statistics"""
    
    endpoint = await check_webhook_permission(db, current_user, endpoint_id)
    
    # Get statistics
    stats = await webhook_service.get_endpoint_stats(
        db,
        str(endpoint_id),
        days=days
    )
    
    return stats


@router.get("/{endpoint_id}/events", response_model=WebhookEventListResponse)
async def list_webhook_events(
    endpoint_id: uuid.UUID,
    limit: int = Query(100, le=1000, description="Max events to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List webhook events for an endpoint"""
    
    endpoint = await check_webhook_permission(db, current_user, endpoint_id)
    
    # Get events delivered to this endpoint
    events_stmt = select(WebhookEvent).join(
        WebhookDelivery,
        WebhookDelivery.webhook_event_id == WebhookEvent.id
    ).where(
        WebhookDelivery.webhook_endpoint_id == endpoint_id
    ).order_by(
        WebhookEvent.created_at.desc()
    )

    count_result = await db.execute(select(func.count()).select_from(events_stmt.subquery()))
    total = count_result.scalar()

    events_result = await db.execute(events_stmt.offset(offset).limit(limit))
    events = events_result.scalars().all()
    
    return WebhookEventListResponse(
        events=events,
        total=total
    )


@router.get("/{endpoint_id}/deliveries", response_model=List[WebhookDeliveryResponse])
async def list_webhook_deliveries(
    endpoint_id: uuid.UUID,
    limit: int = Query(100, le=1000, description="Max deliveries to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List webhook delivery attempts for an endpoint"""
    
    endpoint = await check_webhook_permission(db, current_user, endpoint_id)
    
    # Get deliveries for this endpoint
    result = await db.execute(select(WebhookDelivery).where(
        WebhookDelivery.webhook_endpoint_id == endpoint_id
    ).order_by(
        WebhookDelivery.created_at.desc()
    ).offset(offset).limit(limit))
    deliveries = result.scalars().all()
    
    return deliveries


@router.post("/{endpoint_id}/regenerate-secret", response_model=WebhookEndpointResponse)
async def regenerate_webhook_secret(
    endpoint_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Regenerate webhook endpoint secret"""
    
    endpoint = await check_webhook_permission(db, current_user, endpoint_id)
    
    # Generate new secret
    import hashlib
    import time
    
    new_secret = hashlib.sha256(
        f"{endpoint.url}{time.time()}{uuid.uuid4()}".encode()
    ).hexdigest()
    
    endpoint.secret = new_secret
    endpoint.updated_at = datetime.utcnow()
    
    await db.commit()
    await db.refresh(endpoint)
    
    return endpoint


@router.get("/events/types", response_model=List[str])
async def list_available_event_types(
    current_user: User = Depends(get_current_user)
):
    """List all available webhook event types"""
    
    return [event.value for event in WebhookEventType]


@router.post("/verify-signature")
async def verify_webhook_signature(
    secret: str,
    payload: str,
    signature: str,
    current_user: User = Depends(get_current_user)
):
    """Verify webhook signature for testing"""
    
    is_valid = await webhook_service.verify_webhook_signature(
        secret,
        payload,
        signature
    )
    
    return {"valid": is_valid}