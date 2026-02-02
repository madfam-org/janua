"""
Schemas for internal service-to-service API endpoints.
Used by hub services (Dhanam, etc.) to sync state with Janua.
"""

from typing import Literal, Optional

from pydantic import BaseModel


class TierSyncRequest(BaseModel):
    """Request to sync an organization's subscription tier from Dhanam."""

    tier: Literal["free_tier", "pro_tier", "scale_tier", "enterprise_tier"]
    source: str = "dhanam"
    idempotency_key: str


class TierSyncResponse(BaseModel):
    """Response after syncing an organization's subscription tier."""

    status: str
    previous_tier: Optional[str] = None
    new_tier: str
