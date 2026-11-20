"""Request and response models of the OAuth provider routes.

Split out of `app/routers/v1/oauth_provider.py` (2026-11-19, the 800-line
pre-commit limit); code moved verbatim. Names tests patch live in one module
and other modules call them through it (e.g. `_oauth_provider_shared.get_redis`), so one
patch target reaches every caller.
"""

from typing import Optional

from pydantic import BaseModel, Field

# OpenAPI names models that share a class name by their defining module
# (`app__routers__v1__oauth_provider__TokenResponse`). These models were defined
# in `app.routers.v1.oauth_provider` until the 2026-11-19 split; they keep that
# module name so the published OpenAPI document is unchanged.
_OPENAPI_MODULE = "app.routers.v1.oauth_provider"


class AuthorizationRequest(BaseModel):
    """OAuth 2.0 Authorization Request parameters."""
    __module__ = _OPENAPI_MODULE

    response_type: str = Field(..., description="Must be 'code' for authorization code flow")
    client_id: str = Field(..., description="The OAuth client ID")
    redirect_uri: str = Field(..., description="Redirect URI for the callback")
    scope: str = Field("openid", description="Space-separated list of scopes")
    state: Optional[str] = Field(None, description="CSRF protection state parameter")
    nonce: Optional[str] = Field(None, description="Nonce for replay protection")
    code_challenge: Optional[str] = Field(None, description="PKCE code challenge")
    code_challenge_method: Optional[str] = Field(None, description="PKCE challenge method (S256)")


class TokenRequest(BaseModel):
    """OAuth 2.0 Token Request parameters."""
    __module__ = _OPENAPI_MODULE

    grant_type: str = Field(
        ..., description="Grant type (authorization_code, refresh_token, client_credentials)"
    )
    code: Optional[str] = Field(None, description="Authorization code")
    redirect_uri: Optional[str] = Field(None, description="Redirect URI used in authorization")
    client_id: Optional[str] = Field(None, description="Client ID")
    client_secret: Optional[str] = Field(None, description="Client secret")
    refresh_token: Optional[str] = Field(None, description="Refresh token for token refresh")
    code_verifier: Optional[str] = Field(None, description="PKCE code verifier")
    scope: Optional[str] = Field(None, description="Space-separated requested scopes")


class TokenResponse(BaseModel):
    """OAuth 2.0 Token Response."""
    __module__ = _OPENAPI_MODULE

    access_token: str
    token_type: str = "Bearer"
    expires_in: int
    refresh_token: Optional[str] = None
    id_token: Optional[str] = None
    scope: str


class UserInfoResponse(BaseModel):
    """OpenID Connect UserInfo Response."""
    __module__ = _OPENAPI_MODULE

    sub: str = Field(..., description="Subject identifier (user ID)")
    email: Optional[str] = None
    email_verified: Optional[bool] = None
    name: Optional[str] = None
    given_name: Optional[str] = None
    family_name: Optional[str] = None
    picture: Optional[str] = None
    updated_at: Optional[int] = None
    # How Spanish should address this person: "tu" or "usted". Profile-scope
    # claim; `null` until the person has been asked (see
    # app/services/spanish_formality.py). A relying party that gets `null` and
    # asks the person relays the answer to POST /api/v1/internal/users/spanish-formality.
    spanish_formality: Optional[str] = None
