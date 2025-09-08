"""
Token models
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class TokenClaims(BaseModel):
    """
    JWT token claims
    """
    sub: str = Field(..., description="Subject (identity ID)")
    tid: str = Field(..., description="Tenant ID")
    oid: Optional[str] = Field(None, description="Organization ID")
    iat: datetime = Field(..., description="Issued at")
    exp: datetime = Field(..., description="Expiration")
    nbf: Optional[datetime] = Field(None, description="Not before")
    jti: str = Field(..., description="JWT ID")
    iss: str = Field(..., description="Issuer")
    aud: str = Field(..., description="Audience")
    type: str = Field(..., description="Token type (access/refresh)")
    
    # Custom claims
    roles: Optional[list[str]] = Field(default_factory=list)
    permissions: Optional[list[str]] = Field(default_factory=list)
    email: Optional[str] = None
    email_verified: Optional[bool] = None


class TokenPair(BaseModel):
    """
    Access and refresh token pair
    """
    access_token: str
    refresh_token: str
    expires_in: int = Field(..., description="Seconds until access token expires")
    token_type: str = "Bearer"


class TokenRequest(BaseModel):
    """
    Token request
    """
    grant_type: str = Field(..., pattern="^(password|refresh_token|authorization_code)$")
    username: Optional[str] = None
    password: Optional[str] = None
    refresh_token: Optional[str] = None
    code: Optional[str] = None
    redirect_uri: Optional[str] = None
    client_id: Optional[str] = None
    client_secret: Optional[str] = None


class TokenResponse(BaseModel):
    """
    OAuth2 token response
    """
    access_token: str
    token_type: str = "Bearer"
    expires_in: int
    refresh_token: Optional[str] = None
    id_token: Optional[str] = None
    scope: Optional[str] = None