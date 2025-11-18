"""
Token Response Schemas

Pydantic models for JWT token responses.
These are API response models, separate from database models.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class TokenPairResponse(BaseModel):
    """Response model for token pair creation"""

    access_token: str = Field(..., description="JWT access token")
    refresh_token: str = Field(..., description="JWT refresh token")
    expires_in: int = Field(..., description="Access token expiration in seconds")
    token_type: str = Field(default="Bearer", description="Token type")

    class Config:
        json_schema_extra = {
            "example": {
                "access_token": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...",
                "refresh_token": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...",
                "expires_in": 3600,
                "token_type": "Bearer",
            }
        }


class TokenClaimsResponse(BaseModel):
    """Response model for decoded JWT token claims"""

    sub: str = Field(..., description="Subject (user/identity ID)")
    tid: Optional[str] = Field(None, description="Tenant ID")
    oid: Optional[str] = Field(None, description="Organization ID")
    exp: datetime = Field(..., description="Expiration time")
    iat: datetime = Field(..., description="Issued at time")
    nbf: Optional[datetime] = Field(None, description="Not before time")
    jti: str = Field(..., description="JWT ID (unique token identifier)")
    iss: str = Field(..., description="Issuer")
    aud: str = Field(..., description="Audience")
    type: str = Field(..., description="Token type (access or refresh)")

    class Config:
        json_schema_extra = {
            "example": {
                "sub": "user-123",
                "tid": "tenant-456",
                "oid": "org-789",
                "exp": "2025-11-17T12:00:00",
                "iat": "2025-11-17T11:00:00",
                "jti": "unique-token-id-123",
                "iss": "https://api.plinto.dev",
                "aud": "https://plinto.dev",
                "type": "access",
            }
        }
