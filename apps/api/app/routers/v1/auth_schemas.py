"""Request and response models of the /auth routes.

Split out of `app/routers/v1/auth.py` (2026-11-19, the 800-line
pre-commit limit); code moved verbatim. Names tests patch live in one module
and other modules call them through it (e.g. `_auth_shared.get_redis`), so one
patch target reaches every caller.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator

from app.services.email_i18n import normalize_formality

# OpenAPI names models that share a class name by their defining module
# (`app__routers__v1__auth__TokenResponse`). These models were defined in
# `app.routers.v1.auth` until the 2026-11-19 split; they keep that module name
# so the published OpenAPI document (and SDKs generated from it) is unchanged.
_OPENAPI_MODULE = "app.routers.v1.auth"


# Request/Response Models
class SignUpRequest(BaseModel):
    __module__ = _OPENAPI_MODULE
    email: EmailStr
    password: str = Field(..., min_length=8)
    first_name: Optional[str] = Field(None, max_length=100)
    last_name: Optional[str] = Field(None, max_length=100)
    username: Optional[str] = Field(None, min_length=3, max_length=50)
    # Optional and unvalidated by pattern on purpose: an integrating app that
    # already knows its user's language should be able to say so, and an
    # unsupported tag must degrade to the default rather than 422 a signup.
    locale: Optional[str] = Field(None, max_length=35)
    # The OAuth client of the app whose end-user is signing up. When present and
    # bound to an organization, the new user is scoped to that tenant (tenant_id
    # + an OrganizationMember row) — this is what makes a client's DB-only BaaS
    # signup land a *tenant-scoped* user, so the data-api token (the `data-api`
    # scope) can carry a tenant_id. Absent/unknown/not-org-bound → an ordinary
    # untenanted signup, exactly as before. Deliberately a soft hint, never a
    # 422: a bad client_id must not block a signup (same stance as `locale`).
    client_id: Optional[str] = Field(None, max_length=255)

    @field_validator("username")
    @classmethod
    def validate_username(cls, v):
        if v and not v.replace("_", "").replace("-", "").isalnum():
            raise ValueError("Username can only contain letters, numbers, underscores, and hyphens")
        return v


class SignInRequest(BaseModel):
    __module__ = _OPENAPI_MODULE
    email: Optional[EmailStr] = None
    username: Optional[str] = None
    password: str

    @model_validator(mode="after")
    def validate_credentials(self):
        if not self.username and not self.email:
            raise ValueError("Either email or username must be provided")
        return self


class RefreshTokenRequest(BaseModel):
    __module__ = _OPENAPI_MODULE
    refresh_token: str


class ForgotPasswordRequest(BaseModel):
    __module__ = _OPENAPI_MODULE
    email: EmailStr
    # Optional product-surface page that will consume the token, e.g.
    # "https://app.dhan.am/reset-password". Only honored when its value is in
    # settings.PASSWORD_RESET_REDIRECT_ORIGINS — otherwise the default
    # FRONTEND_URL page is used. Lets each product's reset email land on that
    # product's own UI instead of Janua's.
    redirect_base: Optional[str] = None
    client_id: Optional[str] = None
    auth_request_id: Optional[str] = None
    return_url: Optional[str] = None


class ResetPasswordRequest(BaseModel):
    __module__ = _OPENAPI_MODULE
    token: str
    new_password: str = Field(..., min_length=8)


class VerifyEmailRequest(BaseModel):
    __module__ = _OPENAPI_MODULE
    token: str


class ChangePasswordRequest(BaseModel):
    __module__ = _OPENAPI_MODULE
    current_password: str
    new_password: str = Field(..., min_length=8)


class MagicLinkRequest(BaseModel):
    __module__ = _OPENAPI_MODULE
    email: EmailStr
    redirect_url: Optional[str] = None
    # THE HOSTED HOP (J6), as an explicit override. Left None — the normal case
    # — janua DERIVES it: the link lands on janua first exactly when the
    # destination host could not otherwise receive the `janua_sso` estate cookie
    # (see app/auth/hosted_hop.py). A product only sets this to force the
    # decision either way for a host the derived rule would answer differently,
    # e.g. a rehearsal host inside the cookie domain that still wants the hop.
    #
    # ORTHOGONAL TO `formality` below: the hop moves where the link LANDS, the
    # register decides how the message READS. Both are resolved from the same
    # `redirect_url` and neither reads the other.
    hosted_hop: Optional[bool] = None
    # The Spanish register the REQUESTING PRODUCT speaks in: "tu" or "usted".
    # Optional, and validated rather than trusted — `normalize_formality`
    # returns None for anything unsupported (including `vosotros`), which makes
    # a bad value fall through to the next precedence tier instead of 422ing a
    # sign-in request over a cosmetic field. A product that omits it gets the
    # default for its redirect host (app/services/email_branding.py), so the
    # only products that need to send it are ones whose voice differs from
    # their host's registered default.
    formality: Optional[str] = None

    @field_validator("formality")
    @classmethod
    def _validate_formality(cls, value: Optional[str]) -> Optional[str]:
        """Normalize, never reject. See the field comment above."""
        return normalize_formality(value)


class VerifyMagicLinkRequest(BaseModel):
    __module__ = _OPENAPI_MODULE
    token: str


class UserResponse(BaseModel):
    __module__ = _OPENAPI_MODULE
    id: str
    email: str
    email_verified: bool
    username: Optional[str]
    first_name: Optional[str]
    last_name: Optional[str]
    profile_image_url: Optional[str]
    is_admin: bool = False
    created_at: datetime
    updated_at: datetime
    last_sign_in_at: Optional[datetime]


class TokenResponse(BaseModel):
    __module__ = _OPENAPI_MODULE
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class SignInResponse(BaseModel):
    __module__ = _OPENAPI_MODULE
    user: UserResponse
    tokens: Optional[TokenResponse] = None
    mfa_required: bool = False
    mfa_token: Optional[str] = None
