"""
OAuth2 Client Management Schemas

Pydantic models for OAuth2 client registration and management.
These schemas support Janua acting as an OAuth2 Provider (IdP).
"""

import re
from datetime import datetime
from typing import List, Optional
from urllib.parse import urlparse

from pydantic import BaseModel, Field, field_validator


class OAuthClientCreate(BaseModel):
    """Schema for creating a new OAuth2 client"""

    name: str = Field(..., min_length=1, max_length=255, description="Client application name")
    description: Optional[str] = Field(None, max_length=1000, description="Client description")
    redirect_uris: List[str] = Field(
        ..., min_length=1, description="Allowed redirect URIs for OAuth flow"
    )
    allowed_scopes: Optional[List[str]] = Field(
        default=["openid", "profile", "email"],
        description="Allowed OAuth scopes for this client",
    )
    grant_types: Optional[List[str]] = Field(
        default=["authorization_code", "refresh_token"],
        description="Allowed OAuth grant types",
    )
    logo_url: Optional[str] = Field(None, max_length=500, description="Client logo URL")
    website_url: Optional[str] = Field(None, max_length=500, description="Client website URL")
    is_confidential: Optional[bool] = Field(
        default=True,
        description="True for server-side apps (require secret), False for SPAs/mobile",
    )

    @field_validator("redirect_uris")
    @classmethod
    def validate_redirect_uris(cls, v: List[str]) -> List[str]:
        """Validate redirect URIs are valid URLs or localhost"""
        validated = []
        for uri in v:
            parsed = urlparse(uri)
            # Allow localhost for development
            if parsed.netloc.startswith("localhost") or parsed.netloc.startswith("127.0.0.1"):
                validated.append(uri)
                continue
            # Require HTTPS for production
            if parsed.scheme != "https":
                raise ValueError(f"Redirect URI must use HTTPS: {uri}")
            if not parsed.netloc:
                raise ValueError(f"Invalid redirect URI: {uri}")
            validated.append(uri)
        return validated

    @field_validator("allowed_scopes")
    @classmethod
    def validate_scopes(cls, v: Optional[List[str]]) -> List[str]:
        """Validate OAuth scopes"""
        valid_scopes = {"openid", "profile", "email", "offline_access", "api", "admin"}
        if v is None:
            return ["openid", "profile", "email"]
        for scope in v:
            if scope not in valid_scopes:
                raise ValueError(f"Invalid scope: {scope}. Valid: {', '.join(valid_scopes)}")
        return v

    @field_validator("grant_types")
    @classmethod
    def validate_grant_types(cls, v: Optional[List[str]]) -> List[str]:
        """Validate OAuth grant types"""
        valid_types = {
            "authorization_code",
            "refresh_token",
            "client_credentials",
            "implicit",
        }
        if v is None:
            return ["authorization_code", "refresh_token"]
        for grant_type in v:
            if grant_type not in valid_types:
                raise ValueError(f"Invalid grant type: {grant_type}")
        return v


class OAuthClientUpdate(BaseModel):
    """Schema for updating an OAuth2 client"""

    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=1000)
    redirect_uris: Optional[List[str]] = None
    allowed_scopes: Optional[List[str]] = None
    grant_types: Optional[List[str]] = None
    logo_url: Optional[str] = Field(None, max_length=500)
    website_url: Optional[str] = Field(None, max_length=500)
    is_active: Optional[bool] = None

    @field_validator("redirect_uris")
    @classmethod
    def validate_redirect_uris(cls, v: Optional[List[str]]) -> Optional[List[str]]:
        """Validate redirect URIs if provided"""
        if v is None:
            return None
        validated = []
        for uri in v:
            parsed = urlparse(uri)
            if parsed.netloc.startswith("localhost") or parsed.netloc.startswith("127.0.0.1"):
                validated.append(uri)
                continue
            if parsed.scheme != "https":
                raise ValueError(f"Redirect URI must use HTTPS: {uri}")
            if not parsed.netloc:
                raise ValueError(f"Invalid redirect URI: {uri}")
            validated.append(uri)
        return validated


class OAuthClientResponse(BaseModel):
    """Basic OAuth2 client response (list view)"""

    id: str
    client_id: str
    name: str
    description: Optional[str] = None
    is_active: bool
    is_confidential: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class OAuthClientDetailResponse(OAuthClientResponse):
    """Detailed OAuth2 client response"""

    client_secret: Optional[str] = Field(
        None, description="Only returned on creation, never stored in plain text"
    )
    redirect_uris: List[str]
    allowed_scopes: List[str]
    grant_types: List[str]
    logo_url: Optional[str] = None
    website_url: Optional[str] = None
    last_used_at: Optional[datetime] = None
    organization_id: Optional[str] = None


class OAuthClientListResponse(BaseModel):
    """Paginated list of OAuth2 clients"""

    clients: List[OAuthClientResponse]
    total: int
    page: int
    per_page: int


class OAuthClientSecretRotateResponse(BaseModel):
    """Response after rotating client secret"""

    client_id: str
    client_secret: str = Field(..., description="New client secret (save immediately)")
    rotated_at: datetime
    message: str = "Client secret rotated successfully. Save the new secret immediately."
