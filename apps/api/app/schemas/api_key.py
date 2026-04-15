"""
API Key Pydantic schemas for request/response validation

API Keys allow programmatic access to Janua APIs with scoped permissions.
"""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


class ApiKeyCreate(BaseModel):
    """Schema for creating a new API key"""

    name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Human-readable name for the API key",
        examples=["Production Backend Key", "CI/CD Integration"],
    )
    scopes: List[str] = Field(
        default=[],
        description="List of permission scopes for this key",
        examples=[["read:users", "write:users", "read:organizations"]],
    )
    rate_limit_per_min: int = Field(
        default=60,
        ge=1,
        le=10000,
        description="Rate limit in requests per minute for this key",
    )
    expires_at: Optional[datetime] = Field(
        default=None,
        description="Optional expiration date for the key (null for no expiration)",
    )

    @field_validator("scopes")
    @classmethod
    def validate_scopes(cls, v: List[str]) -> List[str]:
        """Validate scope format: resource:action"""
        valid_patterns = []
        for scope in v:
            if ":" not in scope:
                raise ValueError(f"Invalid scope format '{scope}'. Expected 'resource:action' format.")
            parts = scope.split(":")
            if len(parts) != 2 or not parts[0] or not parts[1]:
                raise ValueError(f"Invalid scope format '{scope}'. Expected 'resource:action' format.")
            valid_patterns.append(scope.lower())
        return valid_patterns


class ApiKeyUpdate(BaseModel):
    """Schema for updating an existing API key"""

    name: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=255,
        description="Human-readable name for the API key",
    )
    scopes: Optional[List[str]] = Field(
        default=None,
        description="List of permission scopes for this key",
    )
    expires_at: Optional[datetime] = Field(
        default=None,
        description="Expiration date for the key",
    )
    is_active: Optional[bool] = Field(
        default=None,
        description="Whether the key is active",
    )

    @field_validator("scopes")
    @classmethod
    def validate_scopes(cls, v: Optional[List[str]]) -> Optional[List[str]]:
        """Validate scope format: resource:action"""
        if v is None:
            return v
        valid_patterns = []
        for scope in v:
            if ":" not in scope:
                raise ValueError(f"Invalid scope format '{scope}'. Expected 'resource:action' format.")
            parts = scope.split(":")
            if len(parts) != 2 or not parts[0] or not parts[1]:
                raise ValueError(f"Invalid scope format '{scope}'. Expected 'resource:action' format.")
            valid_patterns.append(scope.lower())
        return valid_patterns


class ApiKeyResponse(BaseModel):
    """Schema for API key responses (without the actual key)"""

    id: str = Field(..., description="Unique identifier for the API key")
    user_id: str = Field(..., description="ID of the user who owns this key")
    organization_id: str = Field(..., description="ID of the organization this key belongs to")
    name: str = Field(..., description="Human-readable name for the API key")
    prefix: str = Field(
        ..., description="Display prefix of the key (e.g., 'jnk_abc123...')"
    )
    key_prefix: Optional[str] = Field(
        default=None, description="Visible key prefix (e.g., 'sk_live_ab3f')"
    )
    scopes: List[str] = Field(default=[], description="Permission scopes for this key")
    rate_limit_per_min: int = Field(default=60, description="Rate limit per minute for this key")
    is_active: bool = Field(..., description="Whether the key is active")
    last_used: Optional[datetime] = Field(
        default=None, description="When the key was last used"
    )
    expires_at: Optional[datetime] = Field(
        default=None, description="When the key expires (null for no expiration)"
    )
    revoked_at: Optional[datetime] = Field(
        default=None, description="When the key was revoked (null if active)"
    )
    created_at: datetime = Field(..., description="When the key was created")
    updated_at: datetime = Field(..., description="When the key was last updated")

    class Config:
        from_attributes = True


class ApiKeyCreateResponse(ApiKeyResponse):
    """
    Schema for API key creation response - includes the plain key.

    IMPORTANT: The plain key is only returned ONCE during creation.
    It should be stored securely by the client as it cannot be retrieved again.
    """

    key: str = Field(
        ...,
        description="The plain API key. IMPORTANT: This is shown only once. Store it securely.",
    )


class ApiKeyListResponse(BaseModel):
    """Paginated list of API keys"""

    items: List[ApiKeyResponse] = Field(default=[], description="List of API keys")
    total: int = Field(..., description="Total number of API keys")
    page: int = Field(..., description="Current page number")
    per_page: int = Field(..., description="Number of items per page")


class ApiKeyRotateResponse(ApiKeyCreateResponse):
    """
    Schema for API key rotation response - includes the new plain key.

    The old key is immediately invalidated and a new key is generated.
    """

    previous_prefix: str = Field(
        ..., description="Prefix of the previous (now invalidated) key"
    )


class ApiKeyVerifyRequest(BaseModel):
    """Schema for verifying an API key (internal service-to-service endpoint)"""

    key: str = Field(
        ...,
        min_length=10,
        description="The full API key to verify",
    )


class ApiKeyVerifyResponse(BaseModel):
    """Schema for API key verification response"""

    valid: bool = Field(..., description="Whether the key is valid and active")
    org_id: Optional[str] = Field(
        default=None, description="Organization ID the key belongs to (null if invalid)"
    )
    scopes: List[str] = Field(
        default=[], description="Permission scopes granted by this key"
    )
    key_id: Optional[str] = Field(
        default=None, description="The API key record ID (null if invalid)"
    )
