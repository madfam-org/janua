"""
Authentication router for v1 API
"""

import json
import secrets
from datetime import datetime, timedelta
from typing import Dict, Optional
from urllib.parse import urlencode, urlparse

from fastapi import APIRouter, BackgroundTasks, Depends, Form, HTTPException, Request, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

import structlog

from app.config import settings
from app.core.locale import locale_from_request
from app.core.redis import ResilientRedisClient, get_redis
from app.core.url_security import validate_redirect_url
from app.database import AsyncSessionLocal, get_db
from app.dependencies import get_current_user
from app.services.account_lockout_service import AccountLockoutService
from app.services.auth_service import AuthService
from app.services.user_lookup import (
    AmbiguousEmailAcrossPools,
    get_user_by_email,
    resolve_user_by_email_across_pools,
)
from app.services.audit_logger import AuditEventType, AuditLogger
from app.services.email import EmailService
from app.services.email_i18n import normalize_formality
from app.services.email_service import (
    send_magic_link_email_task,
    send_password_reset_email_task,
    send_verification_email_task,
)
from app.models.system_settings import SettingKeys
from app.services.system_settings_service import SystemSettingsService
from app.services.webhooks import WebhookEventType, trigger_user_webhook
from app.auth.sso_cookie import (
    clear_sso_cookie,
    revoke_sso_cookie_session,
    set_sso_cookie,
)

from ...models import ActivityLog, EmailVerification, MagicLink, PasswordReset, User, UserStatus
from ...models import Session as UserSession

logger = structlog.get_logger()

# Initialize rate limiter
limiter = Limiter(key_func=get_remote_address)


router = APIRouter(prefix="/auth", tags=["Authentication"])
security = HTTPBearer()

# Include OAuth sub-router
from app.routers.v1 import oauth

router.include_router(oauth.router)


# Request/Response Models
class SignUpRequest(BaseModel):
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
    email: Optional[EmailStr] = None
    username: Optional[str] = None
    password: str

    @model_validator(mode="after")
    def validate_credentials(self):
        if not self.username and not self.email:
            raise ValueError("Either email or username must be provided")
        return self


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr
    # Optional product-surface page that will consume the token, e.g.
    # "https://app.dhan.am/reset-password". Only honored when its value is in
    # settings.PASSWORD_RESET_REDIRECT_ORIGINS — otherwise the default
    # FRONTEND_URL page is used. Lets each product's reset email land on that
    # product's own UI instead of Janua's.
    redirect_base: Optional[str] = None


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(..., min_length=8)


class VerifyEmailRequest(BaseModel):
    token: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=8)


class MagicLinkRequest(BaseModel):
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
    token: str


class UserResponse(BaseModel):
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
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class SignInResponse(BaseModel):
    user: UserResponse
    tokens: Optional[TokenResponse] = None
    mfa_required: bool = False
    mfa_token: Optional[str] = None


# Helper functions (get_current_user moved to app.dependencies)


async def log_activity(
    db: Session, user_id: str, action: str, details: Dict = None, request: Request = None
):
    """Log user activity"""
    activity = ActivityLog(
        user_id=user_id,
        action=action,
        activity_metadata=details or {},  # Model uses activity_metadata, not details
        ip_address=request.client.host if request else None,
        user_agent=request.headers.get("user-agent") if request else None,
    )
    db.add(activity)
    await db.commit()


# SOC 2 CF-08: Audit event type mapping for auth actions
_AUDIT_EVENT_MAP = {
    "signup": AuditEventType.AUTH_SIGNUP,
    "signin": AuditEventType.AUTH_SIGNIN,
    "signout": AuditEventType.AUTH_SIGNOUT,
    "password_change": AuditEventType.AUTH_PASSWORD_CHANGE,
    "password_reset": AuditEventType.AUTH_PASSWORD_RESET,
    "email_verified": AuditEventType.USER_UPDATE,
}


async def signups_enabled(db: Session) -> bool:
    """Resolve whether self-service signup is currently allowed.

    Precedence (most specific wins):
      1. `auth.allow_signups` system setting (DB-backed runtime switch) — lets an
         operator flip signups on/off via the admin settings API WITHOUT a
         redeploy. This is the live switch the `SettingKeys.AUTH_ALLOW_SIGNUPS`
         key was always meant to be but previously was read nowhere.
      2. `settings.ENABLE_SIGNUPS` (env/config) — the deploy-time default and the
         fallback used whenever the DB toggle is unset.

    The DB value is coerced from its stored form (SystemSettingsService persists
    scalars as strings), so "false"/"0"/"no"/"off"/"" all read as False. A failure
    reading the settings table must never silently harden the gate shut, so any
    error defers to the config default rather than inventing a decision.
    """
    try:
        service = SystemSettingsService(db)
        raw = await service.get_setting(SettingKeys.AUTH_ALLOW_SIGNUPS, default=None)
    except Exception:
        return settings.ENABLE_SIGNUPS

    if raw is None:
        return settings.ENABLE_SIGNUPS
    if isinstance(raw, bool):
        return raw
    if isinstance(raw, (int, float)):
        return bool(raw)
    return str(raw).strip().lower() not in {"false", "0", "no", "off", ""}


async def log_audit_event(
    db: Session, user_id: str, action: str, details: Dict = None, request: Request = None
):
    """Log to SOC 2 audit trail (CF-08) alongside activity log."""
    event_type = _AUDIT_EVENT_MAP.get(action)
    if not event_type:
        return
    try:
        audit_logger = AuditLogger(db)
        await audit_logger.log(
            event_type=event_type,
            tenant_id="default",
            identity_id=user_id,
            details=details or {},
            ip_address=request.client.host if request and request.client else None,
            user_agent=request.headers.get("user-agent") if request else None,
            severity="info",
        )
    except Exception:
        # Audit logging failure should not break auth flow
        pass


# Authentication endpoints


async def _resolve_signup_tenant(db: Session, client_id: Optional[str]):
    """Resolve the organization a self-signup should be scoped to, or None.

    Keyed off the app's OAuth ``client_id`` exactly as the data-api token seam
    is (`oauth_provider._data_api_claims`): the client is registered FOR a
    tenant, so its ``organization_id`` is the tenant a user signing up through
    that app belongs to.

    Returns the org UUID only when the client exists, is active, AND is
    org-bound. Every other case — no client_id, unknown/inactive client, or a
    client with no organization — returns None so the signup proceeds as an
    ordinary untenanted account. This is a soft hint by design: a wrong or stale
    client_id must never turn a valid signup into an error.
    """
    if not client_id:
        return None
    from ...models import OAuthClient as _OAuthClient

    result = await db.execute(select(_OAuthClient).where(_OAuthClient.client_id == client_id))
    oauth_client = result.scalar_one_or_none()
    if not oauth_client or not oauth_client.is_active:
        return None
    return oauth_client.organization_id


@router.post("/signup", response_model=SignInResponse)
@limiter.limit("3/minute")  # Strict rate limiting for signup
async def sign_up(
    request: Request,
    signup_data: SignUpRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Create a new user account"""
    # Gate honours the DB-backed `auth.allow_signups` runtime switch first,
    # falling back to the ENABLE_SIGNUPS config default. See signups_enabled().
    if not await signups_enabled(db):
        raise HTTPException(status_code=403, detail="Sign ups are currently disabled")

    # Resolve the tenant BEFORE the email check, because email uniqueness is now
    # per-tenant (migration 013): the same address may exist once per tenant plus
    # once in the untenanted pool. Resolving first lets the existence check — and
    # the created row — be scoped to exactly the pool the DB partial indexes
    # enforce, so the app and the DB agree. Soft hint: no/unknown/not-org-bound
    # client_id → None → the untenanted pool, exactly as before tenanting existed.
    signup_org_id = await _resolve_signup_tenant(db, signup_data.client_id)

    # Check if email already exists WITHIN the target pool. Scoping to
    # `tenant_id == signup_org_id` (or `IS NULL` for the untenanted pool) mirrors
    # the two partial unique indexes; a bare global check here would wrongly
    # reject a client's user whose email merely collides with another tenant's.
    email_stmt = select(User).where(User.email == signup_data.email)
    if signup_org_id is not None:
        email_stmt = email_stmt.where(User.tenant_id == signup_org_id)
    else:
        email_stmt = email_stmt.where(User.tenant_id.is_(None))
    result = await db.execute(email_stmt)
    existing_user = result.scalar_one_or_none()
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")

    # Check if username already exists
    if signup_data.username:
        result = await db.execute(select(User).where(User.username == signup_data.username))
        existing_username = result.scalar_one_or_none()
        if existing_username:
            raise HTTPException(status_code=400, detail="Username already taken")

    # Validate password
    valid, message = AuthService.validate_password_strength(signup_data.password)
    if not valid:
        raise HTTPException(status_code=400, detail=message)

    # Create user. locale is captured here because signup is the only moment
    # we are guaranteed to hear from the client directly; leaving it NULL (the
    # behaviour before this) meant every user fell through to the deployment
    # default forever, since nothing else ever writes the column except an
    # explicit PATCH /users/me that almost nobody makes.
    #
    # tenant_id is set at construction (from the tenant resolved above) so the
    # row lands in the right pool atomically and the DB partial unique index
    # (migration 013) enforces per-tenant email uniqueness on this very insert.
    user = User(
        email=signup_data.email,
        password_hash=AuthService.hash_password(signup_data.password),
        first_name=signup_data.first_name,
        last_name=signup_data.last_name,
        username=signup_data.username,
        status=UserStatus.ACTIVE,
        locale=locale_from_request(request, signup_data.locale),
        tenant_id=signup_org_id,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    # When the signup was tenant-bound, also record membership. This is what
    # makes `_get_user_org_claims` emit the org unambiguously, so the user's
    # data-api token (the `data-api` scope) carries that tenant_id and PostgREST
    # scopes their queries under RLS. No client_id / not org-bound → skipped
    # (ordinary untenanted signup, unchanged behaviour). Isolated in its own
    # commit so a membership hiccup cannot poison the user row that already
    # committed above.
    if signup_org_id is not None:
        from ...models import OrganizationMember

        db.add(
            OrganizationMember(
                organization_id=signup_org_id,
                user_id=user.id,
                role="member",
                status="active",
            )
        )
        await db.commit()
        await db.refresh(user)

    # Create session
    access_token, refresh_token, session = await AuthService.create_session(
        db, user, ip_address=request.client.host, user_agent=request.headers.get("user-agent")
    )

    # Log activity
    await log_activity(db, str(user.id), "signup", {"method": "email"}, request)
    await log_audit_event(db, str(user.id), "signup", {"method": "email"}, request)

    # Dispatch user.created webhook for CRM integration.
    # ISOLATED session, deliberately: the webhook path inserts an event-log
    # row, and a failure there (prod 2026-08-02: legacy_webhook_events table
    # missing) used to poison THIS request's session — the except below
    # swallowed the first error, but the doomed pending INSERT detonated at
    # the next db.commit(), turning every valid signup into a 503. With a
    # dedicated session, webhook logging cannot touch the signup transaction.
    try:
        async with AsyncSessionLocal() as webhook_db:
            await trigger_user_webhook(
                webhook_db,
                WebhookEventType.USER_CREATED,
                {
                    "id": str(user.id),
                    "email": user.email,
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                    "username": user.username,
                    "created_at": user.created_at.isoformat() if user.created_at else None,
                },
                user_id=str(user.id),
            )
            await webhook_db.commit()
    except Exception:
        pass  # Webhook failure must not block signup

    # Send verification email in background
    if settings.EMAIL_ENABLED:
        verification_token = secrets.token_urlsafe(32)
        verification = EmailVerification(
            user_id=user.id,
            token=verification_token,
            email=user.email,
            expires_at=datetime.utcnow() + timedelta(hours=48),
        )
        db.add(verification)
        await db.commit()

        background_tasks.add_task(
            send_verification_email_task,
            user.email,
            verification_token,
            locale=getattr(user, "locale", None),
        )

    return SignInResponse(
        user=UserResponse(
            id=str(user.id),
            email=user.email,
            email_verified=user.email_verified,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name,
            profile_image_url=user.profile_image_url,
            is_admin=getattr(user, "is_admin", False),
            created_at=user.created_at,
            updated_at=user.updated_at,
            last_sign_in_at=user.last_sign_in_at,
        ),
        tokens=TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        ),
    )


@router.post("/signin", response_model=SignInResponse)
@limiter.limit("5/minute")  # Rate limiting for signin attempts
async def sign_in(credentials: SignInRequest, request: Request, db: Session = Depends(get_db)):
    """Authenticate user and get tokens"""
    # Find user - we need to find the user first to check lockout status
    # Note: We look for any user (not just ACTIVE) to check lockout, then verify status
    # Scoped to the untenanted (staff / platform) pool: this bare-credential
    # /signin serves platform identities. End-user (tenanted) login gets its own
    # tenant-aware entry via the OIDC flow; keeping this pool-scoped means a
    # tenant's end-user can never be returned here (post-013 email is per-tenant,
    # so a global lookup could otherwise match the wrong pool's user).
    #
    # AUDITED 2026-09-03 alongside the magic-link outage and deliberately left
    # pool-scoped: unlike magic link this path has no create branch (a miss is
    # an ordinary 401), and it authenticates with a password hash, which the
    # internal provisioning API never sets. Widening it to other pools would
    # therefore admit no one who cannot sign in today, while giving a bare
    # credential pair a cross-tenant reach it should not have.
    if credentials.email:
        user = await get_user_by_email(db, credentials.email, tenant_id=None)
    else:
        result = await db.execute(select(User).where(User.username == credentials.username))
        user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # Check if account is locked
    is_locked, seconds_remaining = AccountLockoutService.is_account_locked(user)
    if is_locked:
        minutes_remaining = (seconds_remaining or 0) // 60 + 1
        raise HTTPException(
            status_code=423,  # HTTP 423 Locked
            detail=f"Account temporarily locked due to too many failed login attempts. "
            f"Please try again in {minutes_remaining} minute(s).",
        )

    # Check user status after lockout check
    if user.status != UserStatus.ACTIVE:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # Verify password
    if not user.password_hash or not AuthService.verify_password(
        credentials.password, user.password_hash
    ):
        # Record failed attempt
        ip_address = request.client.host if request.client else None
        is_now_locked, lock_seconds = await AccountLockoutService.record_failed_attempt(
            db, user, ip_address=ip_address
        )
        if is_now_locked:
            minutes_remaining = (lock_seconds or 0) // 60 + 1
            raise HTTPException(
                status_code=423,
                detail=f"Account locked due to too many failed login attempts. "
                f"Please try again in {minutes_remaining} minute(s).",
            )
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # Reset failed attempts on successful login
    await AccountLockoutService.reset_failed_attempts(db, user)

    # SECURITY: Check if MFA is required before issuing session tokens
    if getattr(user, 'mfa_enabled', False) and getattr(user, 'mfa_secret', None):
        # Issue a short-lived MFA challenge token (not a session token)
        import jwt as pyjwt

        mfa_challenge_payload = {
            "sub": str(user.id),
            "type": "mfa_challenge",
            "exp": datetime.utcnow() + timedelta(minutes=5),
            "iat": datetime.utcnow(),
            "iss": settings.JWT_ISSUER,
        }
        mfa_token = pyjwt.encode(
            mfa_challenge_payload,
            settings.JWT_SECRET_KEY or "development-secret-key",
            algorithm="HS256",
        )

        await log_activity(db, str(user.id), "signin", {"method": "password", "mfa_required": True}, request)

        return SignInResponse(
            user=UserResponse(
                id=str(user.id),
                email=user.email,
                email_verified=user.email_verified,
                username=user.username,
                first_name=user.first_name,
                last_name=user.last_name,
                profile_image_url=user.profile_image_url,
                is_admin=getattr(user, "is_admin", False),
                created_at=user.created_at,
                updated_at=user.updated_at,
                last_sign_in_at=user.last_sign_in_at,
            ),
            tokens=None,
            mfa_required=True,
            mfa_token=mfa_token,
        )

    # Create session (no MFA required)
    access_token, refresh_token, session = await AuthService.create_session(
        db, user, ip_address=request.client.host, user_agent=request.headers.get("user-agent")
    )

    # Log activity (best-effort, don't fail login)
    try:
        await log_activity(db, str(user.id), "signin", {"method": "password"}, request)
    except Exception:
        pass
    try:
        await log_audit_event(db, str(user.id), "signin", {"method": "password"}, request)
    except Exception:
        pass

    return SignInResponse(
        user=UserResponse(
            id=str(user.id),
            email=user.email,
            email_verified=user.email_verified,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name,
            profile_image_url=user.profile_image_url,
            is_admin=getattr(user, "is_admin", False),
            created_at=user.created_at,
            updated_at=user.updated_at,
            last_sign_in_at=user.last_sign_in_at,
        ),
        tokens=TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        ),
    )


@router.get("/session")
async def check_session(
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Check if the user has an active session via cookies.

    This endpoint is used for silent authentication / SSO across subdomains.
    It reads the access_token from HTTP-only cookies (set with COOKIE_DOMAIN)
    and returns user info if valid.

    Returns:
        - 200 with user info if session is valid
        - 401 if no session or invalid token
    """
    # Cookie first (browser SSO), then the Authorization header: products ask
    # this endpoint about a token they hold server-side — nauta's invitation
    # redemption did, and every such call 401'd here for want of a cookie the
    # server never had (found live 2026-08-15). The bearer token answers for
    # itself exactly as the cookie does; nothing else changes.
    access_token = request.cookies.get("access_token")
    if not access_token:
        authorization = request.headers.get("authorization", "")
        if authorization.lower().startswith("bearer "):
            access_token = authorization[7:].strip()

    if not access_token:
        raise HTTPException(status_code=401, detail="No session cookie or bearer token found")

    # Validate access token
    payload = AuthService.verify_token(access_token, token_type="access")
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired session")

    # Fetch user from database
    from uuid import UUID as PyUUID

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token payload")

    result = await db.execute(
        select(User).where(User.id == PyUUID(user_id), User.status == UserStatus.ACTIVE)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=401, detail="User not found or inactive")

    return {
        "authenticated": True,
        "user": {
            "id": str(user.id),
            "email": user.email,
            "username": user.username,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "email_verified": user.email_verified,
            "roles": getattr(user, "roles", []),
            "permissions": getattr(user, "permissions", []),
            "is_admin": getattr(user, "is_admin", False),
        },
        "session": {
            "expires_at": payload.get("exp"),
        },
    }


def _oauth_context_hidden_fields_html(
    *,
    auth_request_id: Optional[str],
    client_id: Optional[str],
    client_name: Optional[str],
    next_url: Optional[str] = None,
) -> str:
    """Hidden form fields that preserve OAuth context across retries."""
    import html

    parts: list[str] = []
    if auth_request_id:
        parts.append(
            f'<input type="hidden" name="auth_request_id" value="{html.escape(auth_request_id)}">'
        )
    elif next_url:
        parts.append(f'<input type="hidden" name="next" value="{html.escape(next_url)}">')
    if client_id:
        parts.append(
            f'<input type="hidden" name="client_id" value="{html.escape(client_id)}">'
        )
    if client_name:
        parts.append(
            f'<input type="hidden" name="client_name" value="{html.escape(client_name)}">'
        )
    return "".join(parts)


async def _recover_authorize_url_from_client(client_id: str, db) -> Optional[str]:
    """Send the user back to the CLIENT so it can start a fresh flow.

    This used to rebuild a synthetic /oauth/authorize URL from the client's
    registration. That URL carried no `state`, no `nonce` and no PKCE
    challenge, because the server cannot know them — only the client that
    started the flow does. Every modern OIDC client validates `state` and a
    PKCE verifier against its own cookies, so the callback produced by such a
    fabricated request could never be accepted: Auth.js rejects it with
    `response parameter "state" missing` (observed in prod 2026-08-13).

    A recovery that cannot succeed is worse than an honest restart. Returning
    the client's own origin lets it mint a new state + verifier pair the way
    it always does.
    """
    from ...models import OAuthClient as _OAuthClient

    stmt = select(_OAuthClient).where(_OAuthClient.client_id == client_id)
    result = await db.execute(stmt)
    oauth_client = result.scalar_one_or_none()
    if not oauth_client or not oauth_client.is_active or not oauth_client.redirect_uris:
        return None

    redirect_uris = oauth_client.redirect_uris
    if isinstance(redirect_uris, str):
        try:
            redirect_uris = json.loads(redirect_uris)
        except json.JSONDecodeError:
            redirect_uris = []
    if not redirect_uris:
        return None

    # The origin of the registered callback is the product itself. Landing
    # there re-enters the product's own sign-in entry point, which starts a
    # complete authorize request (state + PKCE) that its callback can verify.
    parsed = urlparse(redirect_uris[0])
    if not parsed.scheme or not parsed.netloc:
        return None
    return f"{parsed.scheme}://{parsed.netloc}/"


def _render_mfa_challenge_page(
    *,
    mfa_token: str,
    app_name: str,
    auth_request_id: Optional[str],
    client_id: Optional[str],
    client_name: Optional[str],
    next_url: Optional[str],
    error_message: Optional[str] = None,
    status_code: int = 200,
):
    """Render the hosted second-factor screen for the OAuth browser-login flow.

    This replaces the previous dead-end interstitial (a static "you need a second
    factor" message with no way to enter a code — auth's P1 #3). It POSTs the code
    plus the short-lived `mfa_token` to `/api/v1/auth/login-form/mfa`, which
    verifies the factor, sets the session cookies, and resumes the OAuth redirect.

    The OAuth context (`auth_request_id`/`client_id`/`client_name`/`next`) is
    carried as hidden fields so the verify step can rebuild the same authorize
    URL — the `oauth:pre_login:<auth_request_id>` Redis key is NOT consumed on the
    MFA branch (login_form only deletes it after a session is actually created),
    so it is still available when the second factor completes.
    """
    import html

    from fastapi.responses import HTMLResponse

    safe_app_name = html.escape(app_name or "Application")
    hidden_fields = _oauth_context_hidden_fields_html(
        auth_request_id=auth_request_id,
        client_id=client_id,
        client_name=client_name,
        next_url=next_url,
    )
    error_html = (
        f'<div class="error">{html.escape(error_message)}</div>' if error_message else ""
    )

    html_content = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Two-factor authentication - Janua</title>
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }}
        .login-container {{
            background: white;
            border-radius: 16px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            padding: 40px;
            width: 100%;
            max-width: 400px;
        }}
        .logo {{ text-align: center; margin-bottom: 24px; }}
        .logo h1 {{ font-size: 28px; color: #333; margin-bottom: 8px; }}
        .logo p {{ color: #666; font-size: 14px; }}
        .app-info {{
            background: #f8f9fa;
            border-radius: 8px;
            padding: 12px 16px;
            margin-bottom: 24px;
            text-align: center;
        }}
        .app-info span {{ color: #666; font-size: 13px; }}
        .app-info strong {{ color: #333; }}
        .form-group {{ margin-bottom: 20px; }}
        label {{ display: block; margin-bottom: 6px; color: #333; font-weight: 500; font-size: 14px; }}
        input[type="text"] {{
            width: 100%;
            padding: 12px 16px;
            border: 2px solid #e1e5eb;
            border-radius: 8px;
            font-size: 20px;
            letter-spacing: 4px;
            text-align: center;
        }}
        input:focus {{
            outline: none;
            border-color: #667eea;
            box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
        }}
        button {{
            width: 100%;
            padding: 14px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            border-radius: 8px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
        }}
        .hint {{ color: #666; font-size: 13px; text-align: center; margin-top: 12px; }}
        .error {{
            background: #fee;
            color: #c00;
            padding: 12px 16px;
            border-radius: 8px;
            margin-bottom: 20px;
            font-size: 14px;
        }}
        .footer {{ text-align: center; margin-top: 24px; color: #666; font-size: 12px; }}
    </style>
</head>
<body>
    <div class="login-container">
        <div class="logo">
            <h1>&#128274; Janua</h1>
            <p>Two-factor authentication</p>
        </div>

        <div class="app-info">
            <span>Signing in to <strong>{safe_app_name}</strong></span>
        </div>

        {error_html}

        <form method="POST" action="/api/v1/auth/login-form/mfa">
            <input type="hidden" name="mfa_token" value="{html.escape(mfa_token)}">
            {hidden_fields}
            <div class="form-group">
                <label for="code">Verification code</label>
                <input type="text" id="code" name="code" inputmode="text"
                       autocomplete="one-time-code" placeholder="123456"
                       required autofocus>
            </div>
            <button type="submit">Verify</button>
            <div class="hint">Enter the 6-digit code from your authenticator app, or a backup code.</div>
        </form>

        <div class="footer">Powered by Janua &bull; Secure Authentication</div>
    </div>
</body>
</html>
"""
    return HTMLResponse(content=html_content, status_code=status_code)


def _set_session_cookies(
    response,
    access_token: str,
    refresh_token: str,
    *,
    user=None,
    session=None,
) -> None:
    """Set the hosted-flow session cookies on a response.

    Extracted so the password path (login_form) and the second-factor path
    (login_form_mfa) set identical cookies — same names, flags, TTLs, and
    optional cross-subdomain domain — instead of drifting between two copies.
    The access cookie is intentionally non-HttpOnly (the browser SDK reads it for
    API calls); the refresh cookie is HttpOnly.

    SSO (J5/R1): when `user` and `session` are supplied, this also sets
    `janua_sso` — the HttpOnly estate cookie `@madfam/janua-next` relays to the
    browser after a server-to-server magic-link exchange, and the only session
    reference `/authorize` can see when a person arrives from another product.
    See `app/auth/sso_cookie.py` for why it is a separate cookie. `user`/`session`
    are keyword-only and optional so no existing caller changes behaviour by
    accident: a caller that cannot name the session row emits no `janua_sso`
    rather than one that could never be revoked.
    """
    access_cookie_kwargs: dict = {
        "httponly": False,
        "samesite": "lax",
        "secure": True,
        "max_age": 3600,  # 1 hour
    }
    refresh_cookie_kwargs: dict = {
        "httponly": True,
        "samesite": "lax",
        "secure": True,
        "max_age": 604800,  # 7 days
    }
    if settings.COOKIE_DOMAIN:
        access_cookie_kwargs["domain"] = settings.COOKIE_DOMAIN
        refresh_cookie_kwargs["domain"] = settings.COOKIE_DOMAIN

    response.set_cookie(key="janua_access_token", value=access_token, **access_cookie_kwargs)
    response.set_cookie(key="janua_refresh_token", value=refresh_token, **refresh_cookie_kwargs)

    if user is not None and session is not None:
        set_sso_cookie(response, str(getattr(user, "id", "")), session)


async def _resolve_oauth_redirect_target(
    *,
    auth_request_id: Optional[str],
    client_id: Optional[str],
    next_url: str,
    redis: ResilientRedisClient,
    db,
) -> str:
    """Resolve where to send the browser after a hosted login completes.

    Mirrors login_form's redirect logic for the second-factor path: prefer the
    OAuth authorize URL rebuilt from the Redis-stored params (keyed by
    auth_request_id), fall back to the client's registered origin, and otherwise
    use the validated `next` URL. Does NOT delete the Redis key (the caller does,
    after a session is created), matching login_form's single-use semantics.
    """
    if auth_request_id:
        stored_data = await redis.get(f"oauth:pre_login:{auth_request_id}")
        if stored_data:
            try:
                auth_params = json.loads(stored_data)
                query_params = {}
                for key in [
                    "response_type", "client_id", "redirect_uri", "scope",
                    "state", "nonce", "code_challenge", "code_challenge_method",
                ]:
                    if auth_params.get(key) is not None:
                        query_params[key] = auth_params[key]
                return f"/api/v1/oauth/authorize?{urlencode(query_params)}"
            except (json.JSONDecodeError, KeyError):
                pass
        # Redis lost the params — try the client's registered origin.
        if client_id:
            recovered = await _recover_authorize_url_from_client(client_id, db)
            if recovered:
                return recovered
        return "/"
    # Non-OAuth login: validate the caller-supplied next URL (CWE-601).
    return validate_redirect_url(next_url, default_url="/")


# GET /login - Render login form for OAuth flows
@router.get("/login")
async def login_page(
    request: Request,
    next: Optional[str] = None,
    auth_request_id: Optional[str] = None,
    client_id: Optional[str] = None,
    client_name: Optional[str] = None,
    db=Depends(get_db),
    redis: ResilientRedisClient = Depends(get_redis),
):
    """
    Render login page for OAuth authorization flows.

    This endpoint serves an HTML login form that:
    1. Accepts email/password credentials
    2. POSTs to /api/v1/auth/login-form
    3. On success, redirects to the OAuth authorize endpoint

    Query params:
    - auth_request_id: Opaque ID for Redis-stored OAuth params (preferred for OAuth flows)
    - next: URL to redirect to after successful login (fallback for non-OAuth logins)
    - client_id: OAuth client requesting authorization
    - client_name: Human-readable name of the OAuth client
    """
    import html

    from fastapi.responses import HTMLResponse, RedirectResponse

    # Stale bookmarked login URLs carry an expired auth_request_id. Restart the
    # OAuth flow instead of rendering a form that cannot complete.
    if auth_request_id and client_id:
        stored_data = await redis.get(f"oauth:pre_login:{auth_request_id}")
        if not stored_data:
            recovered = await _recover_authorize_url_from_client(client_id, db)
            if recovered:
                logger.info(
                    "login_page.stale_auth_request_restarted",
                    auth_request_id=auth_request_id,
                    client_id=client_id,
                )
                return RedirectResponse(url=recovered, status_code=302)

    # SECURITY: Validate the 'next' URL to prevent open redirect attacks (CWE-601)
    safe_next = validate_redirect_url(next or "/", default_url="/")
    app_name = html.escape(client_name or "Application")

    hidden_fields = _oauth_context_hidden_fields_html(
        auth_request_id=auth_request_id,
        client_id=client_id,
        client_name=client_name,
        next_url=safe_next if not auth_request_id else None,
    )

    html_content = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Sign in - Janua</title>
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }}
        .login-container {{
            background: white;
            border-radius: 16px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            padding: 40px;
            width: 100%;
            max-width: 400px;
        }}
        .logo {{
            text-align: center;
            margin-bottom: 30px;
        }}
        .logo h1 {{
            font-size: 28px;
            color: #333;
            margin-bottom: 8px;
        }}
        .logo p {{
            color: #666;
            font-size: 14px;
        }}
        .app-info {{
            background: #f8f9fa;
            border-radius: 8px;
            padding: 12px 16px;
            margin-bottom: 24px;
            text-align: center;
        }}
        .app-info span {{
            color: #666;
            font-size: 13px;
        }}
        .app-info strong {{
            color: #333;
        }}
        .form-group {{
            margin-bottom: 20px;
        }}
        label {{
            display: block;
            margin-bottom: 6px;
            color: #333;
            font-weight: 500;
            font-size: 14px;
        }}
        input[type="email"], input[type="password"] {{
            width: 100%;
            padding: 12px 16px;
            border: 2px solid #e1e5eb;
            border-radius: 8px;
            font-size: 16px;
            transition: border-color 0.2s, box-shadow 0.2s;
        }}
        input:focus {{
            outline: none;
            border-color: #667eea;
            box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
        }}
        button {{
            width: 100%;
            padding: 14px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            border-radius: 8px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            transition: transform 0.2s, box-shadow 0.2s;
        }}
        button:hover {{
            transform: translateY(-1px);
            box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
        }}
        button:disabled {{
            opacity: 0.7;
            cursor: not-allowed;
            transform: none;
        }}
        .error {{
            background: #fee;
            color: #c00;
            padding: 12px 16px;
            border-radius: 8px;
            margin-bottom: 20px;
            font-size: 14px;
            display: none;
        }}
        .aux-link {{
            text-align: right;
            margin-top: 6px;
        }}
        .aux-link a {{
            color: #667eea;
            font-size: 13px;
            text-decoration: none;
        }}
        .aux-link a:hover {{
            text-decoration: underline;
        }}
        .footer {{
            text-align: center;
            margin-top: 24px;
            color: #666;
            font-size: 12px;
        }}
    </style>
</head>
<body>
    <div class="login-container">
        <div class="logo">
            <h1>&#128274; Janua</h1>
            <p>Identity Platform</p>
        </div>

        <div class="app-info">
            <span>Signing in to <strong>{app_name}</strong></span>
        </div>

        <div class="error" id="error"></div>

        <form id="loginForm" method="POST" action="/api/v1/auth/login-form">
            {hidden_fields}
            <div class="form-group">
                <label for="email">Email</label>
                <input type="email" id="email" name="email" required autocomplete="email" autofocus>
            </div>
            <div class="form-group">
                <label for="password">Password</label>
                <input type="password" id="password" name="password" required autocomplete="current-password">
                <div class="aux-link"><a href="/api/v1/auth/forgot-password">Forgot your password?</a></div>
            </div>
            <button type="submit" id="submitBtn">Sign In</button>
        </form>

        <div class="footer">
            Powered by Janua &bull; Secure Authentication
        </div>
    </div>
</body>
</html>
"""
    return HTMLResponse(content=html_content)


# Form-based login for OAuth flows (handles browser form POST, sets cookies, redirects)
@router.post("/login-form")
@limiter.limit("5/minute")
async def login_form(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    next: str = Form("/"),
    auth_request_id: Optional[str] = Form(None),
    client_id: Optional[str] = Form(None),
    client_name: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    redis: ResilientRedisClient = Depends(get_redis),
):
    """
    Handle form-based login for OAuth authorization flows.

    This endpoint:
    1. Authenticates the user with email/password
    2. Sets access_token cookie for subsequent requests
    3. Redirects to the OAuth authorize endpoint (reconstructed from Redis) or 'next' URL

    This works without JavaScript, avoiding CSP issues with inline scripts.

    SECURITY: When auth_request_id is present, the OAuth parameters are retrieved from
    Redis and the authorize URL is reconstructed fresh, avoiding double-encoding issues
    with urlencode() that caused redirect loops. Falls back to the 'next' param for
    non-OAuth logins.
    """
    import html

    from fastapi.responses import HTMLResponse, RedirectResponse

    # Determine the redirect target: prefer Redis-backed auth request over 'next' URL.
    # This avoids the double-encoding bug where urlencode(redirect_uri) produced
    # mangled query strings that caused infinite redirect loops.
    #
    # Branch outcomes (each emits a structured log so silent UX failures are
    # diagnosable post-hoc — track via log line key `login_form.redirect_branch`):
    #   - redis_hit             → OAuth flow resumes (happy path)
    #   - redis_miss_oauth_recovered → OAuth flow resumes via OAuthClient fallback
    #   - redis_miss_no_recovery → renders an "expired session" error page (NOT
    #                              a silent redirect to JSON `/`, the historical bug)
    #   - redis_miss_parse_error → same as redis_miss_no_recovery
    #   - non_oauth             → normal `next` URL flow
    safe_next = "/"
    oauth_recovery_attempted = False
    redirect_branch = "non_oauth"
    if auth_request_id:
        # Retrieve stored OAuth parameters from Redis
        stored_data = await redis.get(f"oauth:pre_login:{auth_request_id}")
        if stored_data:
            try:
                auth_params = json.loads(stored_data)
                # Reconstruct the authorize URL fresh from stored parameters.
                # Only include non-None parameters to avoid polluting the URL.
                query_params = {}
                for key in [
                    "response_type", "client_id", "redirect_uri", "scope",
                    "state", "nonce", "code_challenge", "code_challenge_method",
                ]:
                    if auth_params.get(key) is not None:
                        query_params[key] = auth_params[key]

                safe_next = f"/api/v1/oauth/authorize?{urlencode(query_params)}"
                redirect_branch = "redis_hit"
                logger.info(
                    "login_form.redirect_branch",
                    branch=redirect_branch,
                    auth_request_id=auth_request_id,
                    client_id=auth_params.get("client_id"),
                )
            except (json.JSONDecodeError, KeyError) as e:
                redirect_branch = "redis_miss_parse_error"
                logger.warning(
                    "login_form.redirect_branch",
                    branch=redirect_branch,
                    auth_request_id=auth_request_id,
                    error=str(e),
                )
                oauth_recovery_attempted = True
        else:
            redirect_branch = "redis_miss"
            logger.warning(
                "login_form.redirect_branch",
                branch=redirect_branch,
                auth_request_id=auth_request_id,
                client_id_present=bool(client_id),
            )
            oauth_recovery_attempted = True

        # OAuth flow recovery: when Redis lost the params (TTL expired or API
        # restart), try to reconstruct a minimal authorize URL from the
        # OAuth client's first registered redirect_uri. This avoids the silent
        # redirect to `/` (raw JSON) that previously made "Sign In does
        # nothing". The user still needs to re-consent / re-grant if scopes
        # changed, but they land somewhere meaningful.
        if oauth_recovery_attempted and client_id:
            recovered = await _recover_authorize_url_from_client(client_id, db)
            if recovered:
                safe_next = recovered
                redirect_branch = "redis_miss_oauth_recovered"
                logger.info(
                    "login_form.redirect_branch",
                    branch=redirect_branch,
                    client_id=client_id,
                )
            else:
                logger.warning(
                    "login_form.redirect_branch",
                    branch="redis_miss_no_recovery",
                    client_id=client_id,
                )
                redirect_branch = "redis_miss_no_recovery"
    else:
        # Fallback: validate the 'next' URL for non-OAuth logins (CWE-601)
        safe_next = validate_redirect_url(next, default_url="/")

    # Preserve full OAuth context on error-page retries (including client_id so
    # Redis expiry recovery still works after a wrong-password attempt).
    error_hidden_field = _oauth_context_hidden_fields_html(
        auth_request_id=auth_request_id,
        client_id=client_id,
        client_name=client_name,
        next_url=safe_next if not auth_request_id else None,
    )

    # Helper to return error page
    def make_error_page(error_message: str) -> HTMLResponse:
        error_html = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Sign in - Janua</title>
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }}
        .login-container {{
            background: white;
            border-radius: 16px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            padding: 40px;
            width: 100%;
            max-width: 400px;
        }}
        .logo {{ text-align: center; margin-bottom: 30px; }}
        .logo h1 {{ font-size: 28px; color: #333; margin-bottom: 8px; }}
        .logo p {{ color: #666; font-size: 14px; }}
        .form-group {{ margin-bottom: 20px; }}
        label {{ display: block; margin-bottom: 6px; color: #333; font-weight: 500; font-size: 14px; }}
        input[type="email"], input[type="password"] {{
            width: 100%;
            padding: 12px 16px;
            border: 2px solid #e1e5eb;
            border-radius: 8px;
            font-size: 16px;
        }}
        input:focus {{ outline: none; border-color: #667eea; }}
        button {{
            width: 100%;
            padding: 14px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            border-radius: 8px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
        }}
        .error {{
            background: #fee;
            color: #c00;
            padding: 12px 16px;
            border-radius: 8px;
            margin-bottom: 20px;
            font-size: 14px;
        }}
        .footer {{ text-align: center; margin-top: 24px; color: #666; font-size: 12px; }}
    </style>
</head>
<body>
    <div class="login-container">
        <div class="logo">
            <h1>&#128274; Janua</h1>
            <p>Identity Platform</p>
        </div>
        <div class="error">{html.escape(error_message)}</div>
        <form method="POST" action="/api/v1/auth/login-form">
            {error_hidden_field}
            <div class="form-group">
                <label for="email">Email</label>
                <input type="email" id="email" name="email" value="{html.escape(email)}" required autofocus>
            </div>
            <div class="form-group">
                <label for="password">Password</label>
                <input type="password" id="password" name="password" required>
                <div style="text-align:right;margin-top:6px"><a href="/api/v1/auth/forgot-password" style="color:#667eea;font-size:13px;text-decoration:none">Forgot your password?</a></div>
            </div>
            <button type="submit">Sign In</button>
        </form>
        <div class="footer">Powered by Janua &bull; Secure Authentication</div>
    </div>
</body>
</html>
"""
        return HTMLResponse(content=error_html, status_code=401)

    # Find user by email (without status filter to check lockout first).
    # Untenanted / staff pool (see /signin note) — this hosted flow is platform.
    # Audited 2026-09-03 with the magic-link outage: same reasoning as /signin,
    # password-authenticated and no create branch, so it stays pool-scoped.
    user = await get_user_by_email(db, email, tenant_id=None)

    if not user:
        return make_error_page("Invalid email or password. Please try again.")

    # Check if account is locked
    is_locked, seconds_remaining = AccountLockoutService.is_account_locked(user)
    if is_locked:
        minutes_remaining = (seconds_remaining or 0) // 60 + 1
        return make_error_page(
            f"Account temporarily locked due to too many failed login attempts. "
            f"Please try again in {minutes_remaining} minute(s)."
        )

    # Check user status after lockout check
    if user.status != UserStatus.ACTIVE:
        return make_error_page("Invalid email or password. Please try again.")

    # Verify password
    if not user.password_hash or not AuthService.verify_password(password, user.password_hash):
        # Record failed attempt
        ip_address = request.client.host if request.client else None
        is_now_locked, lock_seconds = await AccountLockoutService.record_failed_attempt(
            db, user, ip_address=ip_address
        )
        if is_now_locked:
            minutes_remaining = (lock_seconds or 0) // 60 + 1
            return make_error_page(
                f"Account locked due to too many failed login attempts. "
                f"Please try again in {minutes_remaining} minute(s)."
            )
        return make_error_page("Invalid email or password. Please try again.")

    # Reset failed attempts on successful login
    await AccountLockoutService.reset_failed_attempts(db, user)

    # SECURITY (2026-08-23): enforce MFA on the OAuth browser-login path. This was
    # the primary bypass — a user with MFA enabled was issued a full session here
    # with no second factor. Gated behind MFA_ENFORCE_ON_LOGIN (default OFF), so
    # this is inert until the challenge UI ships and the flag is flipped; when off,
    # mfa_required_for() returns False and behavior is unchanged.
    from app.auth.mfa_enforcement import mfa_required_for

    if mfa_required_for(user):
        await log_activity(
            db, str(user.id), "signin", {"method": "oauth_form", "mfa_required": True}, request
        )
        # Render the real second-factor screen (P1 #3). We mint a short-lived
        # challenge token here and hand the user a code-entry form that POSTs to
        # /login-form/mfa; that endpoint verifies the factor, sets the session
        # cookies, and completes the OAuth redirect. The OAuth context is carried
        # in hidden fields so the redirect can be rebuilt after verification.
        from app.auth.mfa_enforcement import mint_mfa_challenge_token

        return _render_mfa_challenge_page(
            mfa_token=mint_mfa_challenge_token(user),
            app_name=client_name or "Application",
            auth_request_id=auth_request_id,
            client_id=client_id,
            client_name=client_name,
            # For non-OAuth logins the redirect target is `next`; for OAuth it is
            # rebuilt from auth_request_id, so only pass next when there is no
            # auth_request_id (matches _oauth_context_hidden_fields_html's rule).
            next_url=safe_next if not auth_request_id else None,
        )

    # Create session and tokens
    access_token, refresh_token, session = await AuthService.create_session(
        db, user, ip_address=request.client.host, user_agent=request.headers.get("user-agent")
    )

    # SECURITY: Delete the Redis key after successful login (single-use)
    # This prevents replay attacks where a leaked auth_request_id could be reused
    if auth_request_id:
        try:
            await redis.delete(f"oauth:pre_login:{auth_request_id}")
        except Exception:
            pass  # Best-effort cleanup; the key has a TTL anyway

    # If the OAuth context was unrecoverable (Redis expired AND we couldn't
    # reconstruct from the OAuthClient registration), render an explicit
    # "session expired" page instead of silently redirecting to JSON `/`.
    # This was the long-standing UX bug where Sign In appeared to do nothing.
    if redirect_branch in ("redis_miss_no_recovery", "redis_miss_parse_error") and (
        not auth_request_id or safe_next == "/"
    ):
        expired_html = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Sign-in session expired - Janua</title>
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex; align-items: center; justify-content: center;
            padding: 20px;
        }}
        .container {{
            background: white; border-radius: 16px; padding: 40px;
            width: 100%; max-width: 440px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
        }}
        h1 {{ color: #333; font-size: 22px; margin-bottom: 16px; }}
        p {{ color: #555; line-height: 1.55; margin-bottom: 12px; }}
        .footer {{ text-align: center; margin-top: 24px; color: #666; font-size: 12px; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>&#128274; Sign-in session expired</h1>
        <p>Your sign-in session for <strong>{html.escape(client_name or "this application")}</strong> expired before you completed login. Your credentials were accepted, but the OAuth flow can't continue from here.</p>
        <p>Return to the application and start sign-in again.</p>
        <div class="footer">Powered by Janua &bull; Secure Authentication</div>
    </div>
</body>
</html>
"""
        # Cookies are still set so the next OAuth /authorize will short-circuit
        # via get_user_from_cookie_or_header — the user won't have to re-type
        # their password.
        response = HTMLResponse(content=expired_html, status_code=200)
    else:
        # SECURITY: Create redirect response with validated URL (CWE-601 mitigation)
        # For OAuth flows, safe_next is the freshly-reconstructed authorize URL.
        # For non-OAuth flows, safe_next was validated against the redirect allowlist.
        response = RedirectResponse(url=safe_next, status_code=302)

    # Set session cookies (shared with the second-factor path — see helper).
    _set_session_cookies(response, access_token, refresh_token, user=user, session=session)

    return response


@router.post("/login-form/mfa")
@limiter.limit("5/minute")
async def login_form_mfa(
    request: Request,
    mfa_token: str = Form(...),
    code: str = Form(...),
    next: str = Form("/"),
    auth_request_id: Optional[str] = Form(None),
    client_id: Optional[str] = Form(None),
    client_name: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    redis: ResilientRedisClient = Depends(get_redis),
):
    """Complete the second factor for the hosted OAuth browser-login flow (P1 #3).

    The GET /login → POST /login-form path renders the MFA challenge screen (via
    _render_mfa_challenge_page) when MFA is required; that screen POSTs here with
    the short-lived `mfa_token` and the user's code, plus the OAuth context. This
    endpoint verifies the factor, establishes the session cookies, and resumes
    the OAuth redirect — the browser equivalent of POST /mfa/challenge/verify
    (which returns JSON tokens and cannot set cookies or redirect).

    On an invalid code it re-renders the challenge screen (401) with a freshly
    minted challenge token so the user can retry without restarting sign-in.
    """
    from uuid import UUID

    import jwt as pyjwt

    # Decode + validate the challenge token (same contract as
    # /mfa/challenge/verify: HS256 over JWT_SECRET_KEY, type == "mfa_challenge").
    def _reject(msg: str, *, remint_for=None):
        token_for_retry = mfa_token
        if remint_for is not None:
            from app.auth.mfa_enforcement import mint_mfa_challenge_token

            token_for_retry = mint_mfa_challenge_token(remint_for)
        return _render_mfa_challenge_page(
            mfa_token=token_for_retry,
            app_name=client_name or "Application",
            auth_request_id=auth_request_id,
            client_id=client_id,
            client_name=client_name,
            next_url=next if not auth_request_id else None,
            error_message=msg,
            status_code=401,
        )

    try:
        payload = pyjwt.decode(
            mfa_token,
            settings.JWT_SECRET_KEY or "development-secret-key",
            algorithms=["HS256"],
            options={"require": ["sub", "type", "exp"]},
        )
    except pyjwt.ExpiredSignatureError:
        # Can't re-mint (no user yet) — the challenge is stale, restart sign-in.
        return _reject("Your verification session expired. Please sign in again.")
    except pyjwt.InvalidTokenError:
        return _reject("Invalid verification session. Please sign in again.")

    if payload.get("type") != "mfa_challenge":
        return _reject("Invalid verification session. Please sign in again.")

    result = await db.execute(
        select(User).where(User.id == UUID(payload.get("sub")), User.status == UserStatus.ACTIVE)
    )
    user = result.scalar_one_or_none()
    if not user or not user.mfa_enabled or not user.mfa_secret:
        return _reject("Invalid verification session. Please sign in again.")

    # Verify TOTP, then fall back to a single-use backup code (shared helper).
    import pyotp

    from app.routers.v1.mfa import consume_backup_code

    code_valid = pyotp.TOTP(user.mfa_secret).verify(code, valid_window=1)
    if not code_valid and consume_backup_code(user, code):
        db.add(
            ActivityLog(
                user_id=user.id,
                action="mfa_backup_code_used",
                activity_metadata={"context": "oauth_form"},
            )
        )
        code_valid = True

    if not code_valid:
        # Wrong code — re-render with a fresh challenge token so retry works even
        # if the original is close to expiry.
        return _reject("Invalid verification code. Please try again.", remint_for=user)

    # Second factor cleared — create the session and resume the OAuth redirect.
    access_token, refresh_token, session = await AuthService.create_session(
        db, user, ip_address=request.client.host, user_agent=request.headers.get("user-agent")
    )
    await log_activity(
        db, str(user.id), "signin", {"method": "oauth_form", "mfa": "totp"}, request
    )

    safe_next = await _resolve_oauth_redirect_target(
        auth_request_id=auth_request_id,
        client_id=client_id,
        next_url=next,
        redis=redis,
        db=db,
    )

    # Single-use: drop the pre-login Redis key now that the session exists
    # (matches login_form). Best-effort — the key also has a TTL.
    if auth_request_id:
        try:
            await redis.delete(f"oauth:pre_login:{auth_request_id}")
        except Exception:
            pass

    from fastapi.responses import RedirectResponse

    response = RedirectResponse(url=safe_next, status_code=302)
    _set_session_cookies(response, access_token, refresh_token, user=user, session=session)
    return response


# Alias for /signup (the TypeScript SDK and @janua/ui components post to /register)
@router.post("/register", response_model=SignInResponse)
@limiter.limit("3/minute")  # Same strict rate limiting as /signup
async def register(
    request: Request,
    signup_data: SignUpRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Create a new user account (alias for /signup)"""
    return await sign_up(request, signup_data, background_tasks, db)


# Alias for /signin (tests expect /login)
@router.post("/login", response_model=SignInResponse)
@limiter.limit("5/minute")
async def login(credentials: SignInRequest, request: Request, db: Session = Depends(get_db)):
    """Authenticate user and get tokens (alias for /signin)"""
    return await sign_in(credentials, request, db)


# Alias for /signout (tests expect /logout)
@router.post("/logout")
async def logout(
    req: Request,
    response: Response,
    current_user: User = Depends(get_current_user),
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
):
    """Sign out current session (alias for /signout).

    SSO (J5/R1): this is the endpoint `@madfam/janua-next` calls from its logout
    route, and it relays the `janua_sso` deletion this sets back to the browser —
    the mirror of the relay that delivered the cookie. See `sign_out`.
    """
    return await sign_out(current_user, credentials, db, req=req, response=response)


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(request: RefreshTokenRequest, db: Session = Depends(get_db)):
    """Refresh access token using refresh token"""
    result = await AuthService.refresh_tokens(db, request.refresh_token)

    if not result:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")

    access_token, refresh_token = result

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post("/signout")
async def sign_out(
    current_user: User = Depends(get_current_user),
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
    req: Request = None,
    response: Response = None,
):
    """Sign out current session.

    SSO (J5/R1): besides the existing blacklist + session revocation, this
    revokes whatever `janua_sso` references and deletes the cookie with the same
    Domain and Path it was set with. Both halves are needed: deleting the cookie
    only clears this browser, while revoking the `sessions` row is what stops a
    copy of the cookie taken earlier. The signature is verified before anything
    is revoked, so a forged cookie cannot end someone else's session.

    `req`/`response` default to None so the existing direct callers and tests,
    which invoke this as a plain coroutine, keep working unchanged.
    """
    token = credentials.credentials
    payload = await AuthService.verify_token(token, token_type="access")

    if payload:
        # Blacklist the access token JTI
        try:
            from app.core.jwt_manager import jwt_manager
            await jwt_manager.blacklist_token(payload["jti"], "access")
        except Exception:
            pass  # Best-effort blacklisting

        # Find and revoke session in DB
        try:
            result = await db.execute(
                select(UserSession).where(UserSession.access_token_jti == payload["jti"])
            )
            session = result.scalar_one_or_none()

            if session:
                session.revoked = True
                # Also blacklist the refresh token
                if session.refresh_token_jti:
                    try:
                        from app.core.jwt_manager import jwt_manager
                        await jwt_manager.blacklist_token(session.refresh_token_jti, "refresh")
                    except Exception:
                        pass
                await db.commit()
        except Exception:
            pass  # Best-effort session revocation

    # SSO (J5/R1): revoke the estate session and clear its cookie. Best-effort,
    # exactly like the blacklisting above — logout must never fail on this.
    try:
        if req is not None and await revoke_sso_cookie_session(
            req.cookies.get("janua_sso"), db
        ):
            await db.commit()
    except Exception:
        pass
    if response is not None:
        clear_sso_cookie(response)

    # Log activity (best-effort, don't fail logout)
    try:
        await log_activity(db, str(current_user.id), "signout", {})
    except Exception:
        pass
    try:
        await log_audit_event(db, str(current_user.id), "signout", {})
    except Exception:
        pass

    return {"message": "Successfully signed out"}


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    """Get current user information"""
    return UserResponse(
        id=str(current_user.id),
        email=current_user.email,
        email_verified=current_user.email_verified,
        username=current_user.username,
        first_name=current_user.first_name,
        last_name=current_user.last_name,
        profile_image_url=current_user.profile_image_url,
        is_admin=getattr(current_user, "is_admin", False),
        created_at=current_user.created_at,
        updated_at=current_user.updated_at,
        last_sign_in_at=current_user.last_sign_in_at,
    )


async def _dispatch_password_reset(
    email: str,
    redirect_base_raw: Optional[str],
    background_tasks: BackgroundTasks,
    db,
) -> None:
    """Create a reset token and queue the email — shared by the JSON endpoint
    and the hosted forgot-password form. Does nothing when no ACTIVE user
    matches: enumeration safety is both callers' contract, so absence must be
    indistinguishable from success at every transport."""
    # Untenanted / staff pool (see /signin note); enumeration-safe either way.
    # Same silent-miss as the magic-link handler had: a user the internal
    # provisioning API created WITH a tenant_id is invisible here, so recovery
    # quietly did nothing for them. Fall back to the across-pools bridge. Since
    # migration 013 landed in production (2026-09-06, see
    # apps/api/alembic/PROD_ALEMBIC_STATE.json) that bridge is a RESOLUTION and
    # no longer an exact lookup: an address may sit in the platform pool and in
    # several tenant pools at once. No redirect_url is available here to name a
    # preferred pool, so genuine ambiguity simply declines to send — which is
    # also the enumeration-safe answer this function already gives for "no
    # match". It is silent to the caller BY DESIGN, which is exactly why it has
    # to be loud in the logs; see the handler below.
    user = await get_user_by_email(db, email, tenant_id=None, active_only=True)
    if not user:
        try:
            user = await resolve_user_by_email_across_pools(db, email, active_only=True)
        except AmbiguousEmailAcrossPools:
            return
    if not (user and settings.EMAIL_ENABLED):
        return

    reset_token = secrets.token_urlsafe(32)
    reset = PasswordReset(
        user_id=user.id, token=reset_token, expires_at=datetime.utcnow() + timedelta(hours=1)
    )
    db.add(reset)
    await db.commit()

    # Only a pre-registered product page may receive the token.
    redirect_base = None
    if redirect_base_raw:
        allowed = {
            origin.strip()
            for origin in (settings.PASSWORD_RESET_REDIRECT_ORIGINS or "").split(",")
            if origin.strip()
        }
        if redirect_base_raw in allowed:
            redirect_base = redirect_base_raw

    # Send email in background via the REAL mailer, with THE token that
    # /password/reset validates. The previous dispatch pointed at a
    # placebo EmailService (app.services.email logs and returns True —
    # nothing was ever sent) and even misnamed its method
    # (send_password_reset_email vs the placebo's send_password_reset),
    # while the SMTP-capable service generated a DIFFERENT token for the
    # URL than the one stored in password_resets. Recovery could never
    # complete by construction.
    background_tasks.add_task(
        send_password_reset_email_task,
        user.email,
        reset_token,
        redirect_base,
        locale=getattr(user, "locale", None),
    )


async def _consume_password_reset(token: str, new_password: str, db) -> tuple[bool, str]:
    """Validate a reset token and set the new password — shared by the JSON
    endpoint and the hosted reset form. Token check precedes policy check so a
    dead link surfaces before a weak password does."""
    result = await db.execute(
        select(PasswordReset).where(
            PasswordReset.token == token,
            PasswordReset.used == False,
            PasswordReset.expires_at > datetime.utcnow(),
        )
    )
    reset = result.scalar_one_or_none()

    if not reset:
        return False, "Invalid or expired reset token"

    valid, message = AuthService.validate_password_strength(new_password)
    if not valid:
        return False, message

    user = await db.get(User, reset.user_id)
    user.password_hash = AuthService.hash_password(new_password)
    # Completing a reset proves control of the mailbox the token was mailed
    # to — the same evidence the magic-link flow auto-verifies on. Without
    # this, an unverified account recovers its password only to be blocked
    # minutes later at the authorize endpoint's REQUIRE_EMAIL_VERIFICATION
    # gate (observed live 2026-08-13).
    user.email_verified = True

    reset.used = True
    reset.used_at = datetime.utcnow()

    await db.commit()

    await log_activity(db, str(user.id), "password_reset", {})
    await log_audit_event(db, str(user.id), "password_reset", {})

    return True, "Password successfully reset"


@router.post("/password/forgot")
@limiter.limit("3/hour")  # Strict rate limiting for password reset requests
async def forgot_password(
    request: Request,
    forgot_data: ForgotPasswordRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Request password reset email"""
    await _dispatch_password_reset(
        forgot_data.email, forgot_data.redirect_base, background_tasks, db
    )
    # Don't reveal if user exists
    return {"message": "If the email exists, a password reset link has been sent"}


@router.post("/password/reset")
async def reset_password(request: ResetPasswordRequest, db: Session = Depends(get_db)):
    """Reset password with token"""
    ok, message = await _consume_password_reset(request.token, request.new_password, db)
    if not ok:
        raise HTTPException(status_code=400, detail=message)
    return {"message": message}


def _recovery_page_html(body: str) -> str:
    """Visual shell for the hosted recovery pages — same look as the hosted
    login page (whose CSS is inlined per-page by existing convention)."""
    return f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Password recovery - Janua</title>
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }}
        .login-container {{
            background: white;
            border-radius: 16px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            padding: 40px;
            width: 100%;
            max-width: 400px;
        }}
        .logo {{ text-align: center; margin-bottom: 30px; }}
        .logo h1 {{ font-size: 28px; color: #333; margin-bottom: 8px; }}
        .logo p {{ color: #666; font-size: 14px; }}
        .lead {{ color: #666; font-size: 14px; margin-bottom: 20px; }}
        .lead a {{ color: #667eea; }}
        .hint {{ color: #666; font-size: 12px; margin: -8px 0 16px; }}
        .form-group {{ margin-bottom: 20px; }}
        label {{
            display: block;
            margin-bottom: 6px;
            color: #333;
            font-weight: 500;
            font-size: 14px;
        }}
        input[type="email"], input[type="password"] {{
            width: 100%;
            padding: 12px 16px;
            border: 2px solid #e1e5eb;
            border-radius: 8px;
            font-size: 16px;
            transition: border-color 0.2s, box-shadow 0.2s;
        }}
        input:focus {{
            outline: none;
            border-color: #667eea;
            box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
        }}
        button {{
            width: 100%;
            padding: 14px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            border-radius: 8px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            transition: transform 0.2s, box-shadow 0.2s;
        }}
        button:hover {{
            transform: translateY(-1px);
            box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
        }}
        .alert-error {{
            background: #fee;
            color: #c00;
            padding: 12px 16px;
            border-radius: 8px;
            margin-bottom: 20px;
            font-size: 14px;
        }}
        .alert-ok {{
            background: #e8f5ee;
            color: #14683c;
            padding: 12px 16px;
            border-radius: 8px;
            margin-bottom: 20px;
            font-size: 14px;
        }}
        .footer {{
            text-align: center;
            margin-top: 24px;
            color: #666;
            font-size: 12px;
        }}
    </style>
</head>
<body>
    <div class="login-container">
{body}
    </div>
</body>
</html>
"""


def _reset_form_body(token: str, error: Optional[str] = None) -> str:
    import html as html_mod

    error_html = f'<div class="alert-error">{html_mod.escape(error)}</div>' if error else ""
    return f"""
        <div class="logo"><h1>&#128274; Janua</h1><p>Choose a new password</p></div>
        {error_html}
        <form method="POST" action="/api/v1/auth/reset-password-form">
            <input type="hidden" name="token" value="{html_mod.escape(token)}">
            <div class="form-group">
                <label for="new_password">New password</label>
                <input type="password" id="new_password" name="new_password" required autocomplete="new-password" autofocus>
            </div>
            <div class="form-group">
                <label for="confirm_password">Confirm new password</label>
                <input type="password" id="confirm_password" name="confirm_password" required autocomplete="new-password">
            </div>
            <p class="hint">At least 12 characters, with an uppercase letter, a lowercase letter, a number, and a special character.</p>
            <button type="submit">Set new password</button>
        </form>
        <div class="footer">Powered by Janua &bull; Secure Authentication</div>
    """


@router.get("/forgot-password")
async def forgot_password_page():
    """Hosted forgot-password page, linked from the hosted login page.

    Before this page existed the hosted login form offered no recovery
    affordance at all — a user who forgot their password had nowhere to go
    (observed live 2026-08-13)."""
    from fastapi.responses import HTMLResponse

    body = """
        <div class="logo"><h1>&#128274; Janua</h1><p>Password recovery</p></div>
        <p class="lead">Enter your account email and we&#39;ll send you a reset link. The link works once and expires in 1 hour.</p>
        <form method="POST" action="/api/v1/auth/forgot-password-form">
            <div class="form-group">
                <label for="email">Email</label>
                <input type="email" id="email" name="email" required autocomplete="email" autofocus>
            </div>
            <button type="submit">Send reset link</button>
        </form>
        <div class="footer">Powered by Janua &bull; Secure Authentication</div>
    """
    return HTMLResponse(content=_recovery_page_html(body))


@router.post("/forgot-password-form")
@limiter.limit("3/hour")  # Same budget as the JSON endpoint — one recovery surface
async def forgot_password_form(
    request: Request,
    background_tasks: BackgroundTasks,
    email: str = Form(...),
    db: Session = Depends(get_db),
):
    """Browser half of /password/forgot: same dispatch, rendered as a page.
    No redirect_base — the emailed link lands on the API-hosted reset page."""
    import html as html_mod

    from fastapi.responses import HTMLResponse

    await _dispatch_password_reset(email, None, background_tasks, db)
    body = f"""
        <div class="logo"><h1>&#128274; Janua</h1><p>Password recovery</p></div>
        <div class="alert-ok">If an account exists for <strong>{html_mod.escape(email)}</strong>, a reset link is on its way. It works once and expires in 1 hour.</div>
        <p class="lead">Didn&#39;t get it? Check spam, or <a href="/api/v1/auth/forgot-password">try again</a> in a few minutes.</p>
        <div class="footer">Powered by Janua &bull; Secure Authentication</div>
    """
    return HTMLResponse(content=_recovery_page_html(body))


@router.get("/reset-password")
async def reset_password_page(token: Optional[str] = None):
    """Hosted reset page — the reset email's default landing since 2026-08-13.

    The previous default pointed at the product frontend, whose
    /auth/reset-password route sits behind the login wall: a user who cannot
    log in (the entire premise of a reset) was bounced to /login and the
    token was lost. This page is served by the API itself, on the same host
    that mints the token, so it can never be auth-walled away."""
    from fastapi.responses import HTMLResponse

    if not token:
        body = """
        <div class="logo"><h1>&#128274; Janua</h1><p>Choose a new password</p></div>
        <div class="alert-error">This page needs the link from your reset email. Open the most recent password-reset email and use its button or URL.</div>
        <p class="lead">Need a new link? <a href="/api/v1/auth/forgot-password">Request one here</a>.</p>
        <div class="footer">Powered by Janua &bull; Secure Authentication</div>
        """
        return HTMLResponse(content=_recovery_page_html(body), status_code=400)
    return HTMLResponse(content=_recovery_page_html(_reset_form_body(token)))


@router.post("/reset-password-form")
@limiter.limit("10/hour")
async def reset_password_form(
    request: Request,
    token: str = Form(...),
    new_password: str = Form(...),
    confirm_password: str = Form(...),
    db: Session = Depends(get_db),
):
    """Browser half of /password/reset: identical token validation and policy
    via _consume_password_reset, rendered as pages instead of JSON."""
    from fastapi.responses import HTMLResponse

    if new_password != confirm_password:
        return HTMLResponse(
            content=_recovery_page_html(
                _reset_form_body(token, "The two passwords don't match.")
            ),
            status_code=400,
        )

    ok, message = await _consume_password_reset(token, new_password, db)
    if ok:
        body = """
        <div class="logo"><h1>&#128274; Janua</h1><p>Password updated</p></div>
        <div class="alert-ok">Your password has been updated. Close this tab and sign in again from the application you came from.</div>
        <div class="footer">Powered by Janua &bull; Secure Authentication</div>
        """
        return HTMLResponse(content=_recovery_page_html(body))

    if message == "Invalid or expired reset token":
        body = """
        <div class="logo"><h1>&#128274; Janua</h1><p>Choose a new password</p></div>
        <div class="alert-error">This reset link is invalid or has expired (links work once and last 1 hour).</div>
        <p class="lead">Request a fresh one <a href="/api/v1/auth/forgot-password">here</a>.</p>
        <div class="footer">Powered by Janua &bull; Secure Authentication</div>
        """
        return HTMLResponse(content=_recovery_page_html(body), status_code=400)

    # Policy rejection — the token is still live, re-render the form with the
    # policy message so the user can try a stronger password on the same link.
    return HTMLResponse(
        content=_recovery_page_html(_reset_form_body(token, message)), status_code=400
    )


@router.post("/password/change")
async def change_password(
    request: ChangePasswordRequest,
    req: Request,
    current_user: User = Depends(get_current_user),
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
):
    """Change password for authenticated user"""
    # Verify current password
    if not AuthService.verify_password(request.current_password, current_user.password_hash):
        raise HTTPException(status_code=400, detail="Current password is incorrect")

    # Validate new password
    valid, message = AuthService.validate_password_strength(request.new_password)
    if not valid:
        raise HTTPException(status_code=400, detail=message)

    # Update password
    current_user.password_hash = AuthService.hash_password(request.new_password)
    await db.commit()

    # SECURITY: Revoke all sessions except current one to prevent stolen session reuse
    # Extract current session ID from the JWT claims
    current_session_id = None
    try:
        token = credentials.credentials
        payload = await AuthService.verify_token(token, token_type="access")
        if payload:
            # Find current session by access token JTI
            result = await db.execute(
                select(UserSession).where(UserSession.access_token_jti == payload.get("jti"))
            )
            current_session = result.scalar_one_or_none()
            if current_session:
                current_session_id = current_session.id
    except Exception:
        pass  # If we can't determine current session, revoke all

    await AuthService.invalidate_user_sessions(
        db, current_user.id, exclude_session_id=current_session_id
    )

    # Log activity
    await log_activity(db, str(current_user.id), "password_change", {}, req)
    await log_audit_event(db, str(current_user.id), "password_change", {}, req)

    return {"message": "Password successfully changed"}


# Alias for /email/verify (tests expect /verify-email)
@router.post("/verify-email")
async def verify_email_alias(request: VerifyEmailRequest, db: Session = Depends(get_db)):
    """Verify email with token (alias for /email/verify)"""
    return await verify_email(request, db)


@router.post("/email/verify")
async def verify_email(request: VerifyEmailRequest, db: Session = Depends(get_db)):
    """Verify email with token"""
    # Find valid verification token
    result = await db.execute(
        select(EmailVerification).where(
            EmailVerification.token == request.token,
            EmailVerification.verified == False,
            EmailVerification.expires_at > datetime.utcnow(),
        )
    )
    verification = result.scalar_one_or_none()

    if not verification:
        raise HTTPException(status_code=400, detail="Invalid or expired verification token")

    # Mark email as verified
    user = await db.get(User, verification.user_id)
    user.email_verified = True
    user.email_verified_at = datetime.utcnow()

    # Mark verification as used
    verification.verified = True
    verification.verified_at = datetime.utcnow()

    await db.commit()

    # Log activity
    await log_activity(db, str(user.id), "email_verified", {})
    await log_audit_event(db, str(user.id), "email_verified", {})

    return {"message": "Email successfully verified"}


@router.post("/email/resend-verification")
@limiter.limit("5/hour")  # Rate limiting for email verification requests
async def resend_verification_email(
    request: Request,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Resend verification email"""
    if current_user.email_verified:
        raise HTTPException(status_code=400, detail="Email already verified")

    if not settings.EMAIL_ENABLED:
        raise HTTPException(status_code=400, detail="Email service not configured")

    # Create new verification token
    verification_token = secrets.token_urlsafe(32)
    verification = EmailVerification(
        user_id=current_user.id,
        token=verification_token,
        email=current_user.email,
        expires_at=datetime.utcnow() + timedelta(hours=48),
    )
    db.add(verification)
    await db.commit()

    # Send email in background
    background_tasks.add_task(
        send_verification_email_task,
        current_user.email,
        verification_token,
        locale=getattr(current_user, "locale", None),
    )

    return {"message": "Verification email sent"}


@router.post("/magic-link")
# Config knob (default "5/hour", per client IP): a team-onboarding ceremony from
# one shared office IP dies at the 6th request under the hardcoded limit — see
# Settings.MAGIC_LINK_RATE_LIMIT. Callable so per-request evaluation follows the
# deployed env without code changes.
@limiter.limit(lambda: settings.MAGIC_LINK_RATE_LIMIT)
async def send_magic_link(
    request: Request,
    magic_link_data: MagicLinkRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Send magic link for passwordless signin"""
    if not settings.ENABLE_MAGIC_LINKS:
        raise HTTPException(status_code=403, detail="Magic links are disabled")

    if not settings.EMAIL_ENABLED:
        raise HTTPException(status_code=400, detail="Email service not configured")

    # Find or create user. The untenanted / staff pool is still the primary
    # meaning of this bare-email platform entry (see /signin note), but a MISS
    # there may not mean "no such user":
    #
    #   The internal provisioning API writes users WITH a tenant_id — CTM
    #   staff, provisioned by crea-map. Those rows are invisible to the
    #   untenanted lookup, so this handler fell through to the create branch
    #   and, under the then-global unique index ix_users_email, the INSERT hit
    #   it → IntegrityError → 503. The requesting product showed «revisa tu
    #   correo» and no link was ever sent (2026-09-03, 21 users).
    #
    # So on a miss, resolve across pools before considering a create. Migration
    # 013 is APPLIED in production now (2026-09-06; the ledger is
    # apps/api/alembic/PROD_ALEMBIC_STATE.json, converged at
    # 016_org_member_app_roles), so ix_users_email is gone and that resolution
    # is no longer exact: one address may legitimately hold a row in the
    # platform pool and in N tenant pools. The redirect host's OAuth client
    # supplies the preferred pool; when it cannot decide, the resolver raises
    # and this handler answers 400 rather than signing anyone into an arbitrary
    # tenant. That 400 is REACHABLE in production — it was not, before 013.
    user = await get_user_by_email(
        db, magic_link_data.email, tenant_id=None, active_only=True
    )

    if not user:
        try:
            user = await resolve_user_by_email_across_pools(
                db,
                magic_link_data.email,
                preferred_tenant_id=await _preferred_pool_for_redirect(
                    db, magic_link_data.redirect_url
                ),
                active_only=True,
            )
        except AmbiguousEmailAcrossPools as exc:
            # Refuse rather than sign someone into an arbitrary tenant.
            raise HTTPException(
                status_code=400,
                detail=(
                    "This email exists in more than one tenant pool; "
                    "request the link from the product that owns the account"
                ),
            ) from exc

    if not user:
        # Create user without password for magic link only.
        # This branch is a signup in everything but name — it is the first and
        # only chance to record the requester's language, and the very next
        # thing this endpoint does is mail them.
        user = User(
            email=magic_link_data.email,
            email_verified=True,  # Auto-verify for magic link users
            status=UserStatus.ACTIVE,
            locale=locale_from_request(request),
        )
        db.add(user)
        try:
            await db.commit()
            await db.refresh(user)
        except IntegrityError:
            # Lost a race, or the row exists in a state the lookups above do
            # not see (a non-ACTIVE row still occupies its pool's unique
            # index — uq_users_email_global for platform rows,
            # uq_users_tenant_email for tenant-pooled ones).
            # Re-select instead of 503ing: the address is taken, so the user
            # exists — find them rather than telling the product the service is
            # down.
            await db.rollback()
            user = await get_user_by_email(
                db, magic_link_data.email, tenant_id=None, active_only=True
            )
            if not user:
                try:
                    user = await resolve_user_by_email_across_pools(
                        db, magic_link_data.email, active_only=True
                    )
                except AmbiguousEmailAcrossPools as exc:
                    raise HTTPException(
                        status_code=400,
                        detail=(
                            "This email exists in more than one tenant pool; "
                            "request the link from the product that owns the account"
                        ),
                    ) from exc
            if not user:
                # The colliding row is not ACTIVE — a disabled or pending
                # account. Say so; do not retry the insert forever.
                raise HTTPException(
                    status_code=400,
                    detail="An account with this email exists but is not active",
                )

    # SECURITY: Validate the redirect URL to prevent open redirect attacks.
    # A supplied-but-disallowed destination is a 400 HERE, not a silent None:
    # the emailed link is built ON the destination host, so nulling it would
    # mail a link that signs the user in and then dead-ends — a failure the
    # requesting product cannot see and the recipient cannot fix. (Found live
    # 2026-08-15: the rehearsal host was missing from CORS_ORIGINS and the
    # first client-ceremony walkthrough ended on the recovery page.)
    safe_redirect_url = None
    if magic_link_data.redirect_url:
        safe_redirect_url = validate_redirect_url(magic_link_data.redirect_url, default_url=None)
        if safe_redirect_url is None:
            raise HTTPException(
                status_code=400,
                detail=(
                    "redirect_url host is not on the allowed list; "
                    "add it to CORS_ORIGINS before requesting links for it"
                ),
            )

    # Create magic link token
    magic_token = secrets.token_urlsafe(32)
    magic_link = MagicLink(
        user_id=user.id,
        # The model declares email NOT NULL and this constructor never set it,
        # so the moment migration backlog 003-011 landed in production
        # (2026-08-15) every plain magic-link send 503'd with a
        # NotNullViolation — found live, mid-rehearsal, on the first send of
        # the CTM ceremony walkthrough. The stored, verified address is the
        # right value: the request's raw input may differ in case or alias
        # form, and the row is an audit record of who was actually mailed.
        # (Prod's NOT NULL was dropped as the same-day unblock; restore it in
        # a later migration once this code is promoted and NULLs backfilled.)
        email=user.email,
        token=magic_token,
        redirect_url=safe_redirect_url,  # Use validated URL
        expires_at=datetime.utcnow() + timedelta(minutes=15),
    )
    db.add(magic_link)
    await db.commit()

    # Send email in background.
    #
    # Both `locale` and `formality` are read off the User row HERE, while the
    # request still holds a DB session — a BackgroundTask has none, so anything
    # stored about the recipient has to be resolved before the task is queued.
    # `magic_link_data.formality` is the requesting product's own register and
    # outranks the stored value; when both are absent the mailer falls back to
    # the redirect host's registered default rather than to a global `usted`
    # (app/services/email_branding.py::default_formality_for).
    background_tasks.add_task(
        send_magic_link_email_task,
        user.email,
        magic_token,
        safe_redirect_url,
        locale=getattr(user, "locale", None),
        formality=magic_link_data.formality,
        user_formality=getattr(user, "spanish_formality", None),
        hosted_hop=magic_link_data.hosted_hop,
    )

    return {"message": "Magic link sent to email"}


async def _session_audience_for_redirect(db: Session, redirect_url: Optional[str]) -> Optional[str]:
    """The per-client audience for a magic-link session, from the redirect host.

    A magic link that forwards to a product should mint a session that
    product's verifier accepts — the audience registered on the OAuth client
    whose redirect_uris share the destination's host. Matching is by HOST, not
    full URI: the magic-link redirect (`/portal/verify`) is not an OAuth
    callback path, but the host names the same product. The redirect_url was
    already allowlist-validated when the link was requested; this only decides
    which registered audience the session carries.

    None (no redirect, no host match, or client without an audience) keeps the
    platform default — exactly what every session minted before this existed.
    """
    client = await _oauth_client_for_redirect(db, redirect_url, require_audience=True)
    return client.audience if client else None


async def _oauth_client_for_redirect(
    db: Session, redirect_url: Optional[str], *, require_audience: bool = False
):
    """The active OAuth client whose redirect_uris share the destination's host.

    Factored out of :func:`_session_audience_for_redirect` so the same host →
    client mapping can answer two questions: which audience a session carries,
    and which ORGANIZATION owns the requesting product (the preferred user pool
    when an email could exist in more than one). ``require_audience`` keeps the
    audience resolver's original filter — a client without an audience never
    changed the session's audience — while the pool resolver wants any active
    client for the host.
    """
    if not redirect_url:
        return None
    host = urlparse(redirect_url).hostname
    if not host:
        return None

    from ...models import OAuthClient as _OAuthClient

    stmt = select(_OAuthClient).where(
        _OAuthClient.is_active == True,  # noqa: E712 — SQLAlchemy comparator
    )
    if require_audience:
        stmt = stmt.where(_OAuthClient.audience.isnot(None))
    result = await db.execute(stmt)
    for client in result.scalars():
        uris = client.redirect_uris or []
        # Some prod rows store the array double-encoded — a JSON string
        # CONTAINING the array — and iterating a string yields characters,
        # which would make this resolver silently match nothing. Same
        # tolerance the OAuth recovery path above applies.
        if isinstance(uris, str):
            try:
                uris = json.loads(uris)
            except json.JSONDecodeError:
                uris = []
        for uri in uris:
            if isinstance(uri, str) and urlparse(uri).hostname == host:
                return client
    return None


async def _preferred_pool_for_redirect(db: Session, redirect_url: Optional[str]):
    """The organization id to prefer when an email matches more than one pool."""
    client = await _oauth_client_for_redirect(db, redirect_url)
    return getattr(client, "organization_id", None) if client else None


def _magic_link_expired_page():
    """The one dead-link page both halves of the callback show.

    Shared so the GET (which only reads) and the POST (which spends) cannot
    drift into telling the same person two different stories. Deliberately does
    not distinguish expired from already-used: to the reader both mean "ask for
    a new link", and saying which leaks nothing useful.
    """
    from fastapi.responses import HTMLResponse

    return HTMLResponse(
        content=_recovery_page_html(
            "<h1>🔗 Link expired</h1>"
            '<p class="lede">Magic links work once and expire after 15 minutes.</p>'
            "<p>Request a new one from the page you were signing in to.</p>"
        ),
        status_code=400,
    )


def _magic_link_interstitial_html(token: str, redirect_url: Optional[str]) -> str:
    """The scanner-proof interstitial: one button that POSTs the token back.

    Branded from the DESTINATION host via `resolve_branding`, the same signal
    the email itself was branded from (`email_branding.py`), so the page a CTM
    person lands on carries the Crea header their mail carried rather than a
    MADFAM page they were not expecting. An unknown or absent destination
    resolves to the MADFAM default.

    The copy follows the destination's language: the CTM hosts are Spanish, and
    a person mid-sign-in should not be handed an English button. Anything else
    keeps English, which is what every other hosted page here renders.
    """
    import html as html_mod

    from app.services.email_branding import resolve_branding

    branding = resolve_branding(redirect_url=redirect_url)
    spanish = _magic_link_interstitial_is_spanish(redirect_url)

    heading = "Entrar" if spanish else "Sign in"
    explanation = (
        "Confirma que eres tú quien abrió este enlace."
        if spanish
        else "Confirm it was you who opened this link."
    )
    action = "Entrar" if spanish else "Continue"
    header_name = html_mod.escape(str(branding.get("header_name", "MADFAM")))
    header_bg = html_mod.escape(str(branding.get("header_bg", "")))
    header_fg = html_mod.escape(str(branding.get("header_fg", "#ffffff")))
    lang = "es-MX" if spanish else "en"

    return f"""<!DOCTYPE html>
<html lang="{lang}">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="robots" content="noindex">
    <title>{html_mod.escape(heading)}</title>
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #f4f5f7;
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }}
        .card {{
            background: #ffffff;
            border-radius: 16px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.15);
            width: 100%;
            max-width: 420px;
            overflow: hidden;
        }}
        .brand {{
            background: {header_bg};
            color: {header_fg};
            padding: 20px;
            text-align: center;
            font-weight: 700;
            font-size: 18px;
        }}
        .body {{ padding: 32px; text-align: center; }}
        h1 {{ font-size: 22px; color: #1b1c2e; margin-bottom: 10px; }}
        p {{ color: #5c5f72; font-size: 15px; line-height: 1.5; margin-bottom: 24px; }}
        button {{
            width: 100%;
            padding: 14px;
            background: {header_bg};
            color: {header_fg};
            border: none;
            border-radius: 8px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            min-height: 48px;
        }}
    </style>
</head>
<body>
    <div class="card">
        <div class="brand">{header_name}</div>
        <div class="body">
            <h1>{html_mod.escape(heading)}</h1>
            <p>{html_mod.escape(explanation)}</p>
            <form method="POST" action="/api/v1/auth/magic-link/callback">
                <input type="hidden" name="token" value="{html_mod.escape(token)}">
                <button type="submit">{html_mod.escape(action)}</button>
            </form>
        </div>
    </div>
</body>
</html>
"""


def _magic_link_interstitial_is_spanish(redirect_url: Optional[str]) -> bool:
    """Does this destination serve a Spanish-speaking tenant?

    Reuses `CTM_HOSTS` — the same registry that decides the email's branding —
    rather than introducing a second host list that could disagree with it. The
    hosts that take the hosted hop today are all CTM's.
    """
    if not redirect_url:
        return False
    from app.services.email_branding import CTM_HOSTS

    host = (urlparse(redirect_url).hostname or "").lower()
    if not host:
        return False
    return any(host == h or host.endswith(f".{h}") for h in CTM_HOSTS)


@router.get("/magic-link/callback")
async def magic_link_callback_interstitial(
    token: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """Render the scanner-proof interstitial. SPENDS NOTHING.

    ⚠️ THE TOKEN IS ONE-TIME, SO A GET MUST CONSUME NOTHING.

    Mail clients and their safe-link / preview scanners GET every URL in an
    email. Until 2026-09-06 this route VERIFIED on the GET: it burned
    `used_at`, minted a session and redirected. A scanner's fetch therefore
    spent the link and the human's own click replayed a spent token —
    "could not sign in". That is not hypothetical: it is the failure this
    estate already hit once (nauta portal, first real ceremony 2026-08-16),
    and it is the reason `@madfam/janua-next` splits its own magic-link route
    exactly this way. This route was written for the no-`redirect_url`
    fallback and never received the same treatment; the J6 hosted hop makes it
    the PRIMARY path for the client's brand hosts, so it had to be fixed
    before that traffic arrives.

    The split is the entire security property:
      • GET (here) renders a one-button page and spends NOTHING.
      • POST (below) is the ONLY place the token is exchanged.

    Do NOT "simplify" this back into a GET that verifies.

    Validation that only READS is still done here, so an already-dead link says
    so immediately instead of showing a button that cannot work.
    """
    from fastapi.responses import HTMLResponse

    if not token:
        return _magic_link_expired_page()

    result = await db.execute(
        select(MagicLink).where(
            MagicLink.token == token,
            MagicLink.used_at.is_(None),
            MagicLink.expires_at > datetime.utcnow(),
        )
    )
    magic_link = result.scalar_one_or_none()
    if not magic_link:
        return _magic_link_expired_page()

    return HTMLResponse(
        content=_magic_link_interstitial_html(token, magic_link.redirect_url),
        status_code=200,
        headers={
            "cache-control": "no-store",
            # The one-time token is in this URL's query string. `no-referrer`
            # keeps it out of any Referer header this page's own assets send.
            "referrer-policy": "no-referrer",
            "x-robots-tag": "noindex, nofollow",
        },
    )


@router.post("/magic-link/callback")
async def magic_link_callback(
    token: Optional[str] = Form(default=None),
    req: Request = None,
    db: Session = Depends(get_db),
):
    """Spend the clicked magic link and forward to the product with a session.

    The ONLY place the one-time token is exchanged — reached by the
    interstitial's button, never by a scanner (see the GET above).

    A link in an email is a GET, and only Janua can trade the one-time magic
    token for a session — so without this route the whole passwordless flow
    had no door to knock on: `/magic-link/verify` is a POST returning JSON,
    which no mail client can reach. Products (nauta's /portal/verify) expect
    to be handed the access token on the query string; that contract is why
    the token travels this way rather than in a body.

    THE HOSTED HOP (J6). This route is also what makes estate SSO reachable
    from a host OUTSIDE the cookie domain. The browser IS on auth.madfam.io
    for this hop, so this is the one moment the issuer can set its own
    first-party `janua_sso` cookie for a person signing in from
    `map.creatumundo.mx` — a host that can never receive it by relay, because a
    browser rejects a `.madfam.io` cookie from a `creatumundo.mx` page. The
    forward below keeps `?token=` exactly as products expect.
    """
    from fastapi.responses import HTMLResponse, RedirectResponse

    def _expired_page() -> HTMLResponse:
        return _magic_link_expired_page()

    if not token:
        return _expired_page()

    result = await db.execute(
        select(MagicLink).where(
            MagicLink.token == token,
            MagicLink.used_at.is_(None),
            MagicLink.expires_at > datetime.utcnow(),
        )
    )
    magic_link = result.scalar_one_or_none()
    if not magic_link:
        return _expired_page()

    result = await db.execute(
        select(User).where(User.id == magic_link.user_id, User.status == UserStatus.ACTIVE)
    )
    user = result.scalar_one_or_none()
    if not user:
        return _expired_page()

    # SECURITY (2026-08-23): a magic link proves mailbox control but is not the
    # user's second factor. If MFA is enforced and enabled, do NOT mint a session
    # here — and do NOT burn the link, so the user can complete verification.
    # Gated behind MFA_ENFORCE_ON_LOGIN (default OFF): inert until the challenge UI
    # ships. When off, behavior is unchanged.
    from app.auth.mfa_enforcement import mfa_required_for

    if mfa_required_for(user):
        await log_activity(
            db, str(user.id), "signin", {"method": "magic_link", "mfa_required": True}, req
        )
        return HTMLResponse(
            content=_recovery_page_html(
                "<h1>Additional verification required</h1>"
                '<p class="lede">This account has two-factor authentication enabled. '
                "Signing in by link is not sufficient on its own.</p>"
                "<p>Return to the sign-in page and complete the second-factor step.</p>"
            ),
            status_code=401,
        )

    # Burn the token before minting anything: a link that has produced a
    # session must never produce a second one.
    magic_link.used_at = datetime.utcnow()

    access_token, refresh_token, session = await AuthService.create_session(
        db, user, ip_address=req.client.host if req and req.client else None,
        user_agent=req.headers.get("user-agent") if req else None,
        audience=await _session_audience_for_redirect(db, magic_link.redirect_url),
    )

    # Signing in by emailed link proves control of the mailbox.
    if not user.email_verified:
        user.email_verified = True
    await db.commit()

    await log_activity(db, str(user.id), "signin", {"method": "magic_link"}, req)

    # Re-validate at redemption: the allowlist may have changed since the link
    # was issued, and this is the moment a credential is handed over.
    destination = validate_redirect_url(magic_link.redirect_url, default_url=None)
    if not destination:
        return HTMLResponse(
            content=_recovery_page_html(
                '<h1>✅ Signed in</h1>'
                '<p class="lede">Your link was valid, but its destination is no longer '
                'an allowed address, so we did not forward you.</p>'
                '<p>Return to the site you were signing in to and try again.</p>'
            ),
            status_code=400,
        )

    separator = "&" if "?" in destination else "?"
    redirect = RedirectResponse(
        url=f"{destination}{separator}token={access_token}", status_code=302
    )
    # SSO (B1): also leave an issuer-side browser session behind. The redirect
    # keeps `?token=` exactly as products expect — nothing about the contract
    # changes — but the browser IS on auth.madfam.io for this hop, so this is
    # the one moment the issuer can set its own cookie on a magic-link login.
    # Without it `/authorize?prompt=none` has no session to recognise and every
    # silent hop between products falls back to a fresh magic link.
    _set_session_cookies(redirect, access_token, refresh_token, user=user, session=session)
    return redirect


@router.post("/magic-link/verify", response_model=SignInResponse)
async def verify_magic_link(
    request: VerifyMagicLinkRequest,
    req: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    """Sign in with magic link token.

    SSO (B1): besides returning the tokens in the body — the contract
    `@madfam/janua-next` and nauta's integration package depend on, unchanged —
    this also sets the issuer session cookies on the response. That costs
    nothing when the caller is a server (Node keeps the Set-Cookie and drops
    it), and it is what makes `/authorize?prompt=none` work when a browser
    posts here directly.
    """
    # Find valid magic link
    result = await db.execute(
        select(MagicLink).where(
            MagicLink.token == request.token,
            MagicLink.used_at.is_(None),
            MagicLink.expires_at > datetime.utcnow(),
        )
    )
    magic_link = result.scalar_one_or_none()

    if not magic_link:
        raise HTTPException(status_code=400, detail="Invalid or expired magic link")

    # Get user
    result = await db.execute(
        select(User).where(User.id == magic_link.user_id, User.status == UserStatus.ACTIVE)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=400, detail="User not found")

    # SECURITY (2026-08-23): enforce MFA on the JSON magic-link path too. A JSON
    # caller receives the same mfa_required + mfa_token contract the /signin path
    # uses, and completes at /mfa/challenge/verify. The link is NOT burned on an
    # MFA interrupt, so the user isn't stranded. Gated behind MFA_ENFORCE_ON_LOGIN
    # (default OFF): inert until the challenge UI ships; when off, unchanged.
    from app.auth.mfa_enforcement import mfa_required_for, mint_mfa_challenge_token

    if mfa_required_for(user):
        await log_activity(
            db, str(user.id), "signin", {"method": "magic_link", "mfa_required": True}, req
        )
        return SignInResponse(
            user=UserResponse(
                id=str(user.id),
                email=user.email,
                email_verified=user.email_verified,
                username=user.username,
                first_name=user.first_name,
                last_name=user.last_name,
                profile_image_url=user.profile_image_url,
                is_admin=getattr(user, "is_admin", False),
                created_at=user.created_at,
                updated_at=user.updated_at,
                last_sign_in_at=user.last_sign_in_at,
            ),
            tokens=None,
            mfa_required=True,
            mfa_token=mint_mfa_challenge_token(user),
        )

    # Mark magic link as used
    magic_link.used_at = datetime.utcnow()

    # Create session, with the audience of the product the link forwards to.
    access_token, refresh_token, session = await AuthService.create_session(
        db, user, ip_address=req.client.host, user_agent=req.headers.get("user-agent"),
        audience=await _session_audience_for_redirect(db, magic_link.redirect_url),
    )

    # Log activity
    await log_activity(db, str(user.id), "signin", {"method": "magic_link"}, req)

    # SSO (B1): same tokens the body carries, also as issuer session cookies.
    # The response body below is byte-for-byte what it was before.
    _set_session_cookies(response, access_token, refresh_token, user=user, session=session)

    return SignInResponse(
        user=UserResponse(
            id=str(user.id),
            email=user.email,
            email_verified=user.email_verified,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name,
            profile_image_url=user.profile_image_url,
            is_admin=getattr(user, "is_admin", False),
            created_at=user.created_at,
            updated_at=user.updated_at,
            last_sign_in_at=user.last_sign_in_at,
        ),
        tokens=TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        ),
    )
