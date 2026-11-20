"""JSON sign-up, sign-in and session check: POST /auth/signup, POST /auth/signin, GET /auth/session.

Split out of `app/routers/v1/auth.py` (2026-11-19, the 800-line
pre-commit limit); code moved verbatim. Names tests patch live in one module
and other modules call them through it (e.g. `_auth_shared.get_redis`), so one
patch target reaches every caller.
"""

import secrets
from datetime import datetime, timedelta
from typing import Optional

from fastapi import BackgroundTasks, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.core.locale import locale_from_request
from app.database import AsyncSessionLocal, get_db
from app.routers.v1 import auth_shared as _auth_shared
from app.routers.v1.auth_schemas import (
    SignInRequest,
    SignInResponse,
    SignUpRequest,
    TokenResponse,
    UserResponse,
)
from app.routers.v1.auth_shared import limiter, router, signups_enabled
from app.services.account_lockout_service import AccountLockoutService
from app.services.email_service import send_verification_email_task
from app.services.webhooks import WebhookEventType

from ...models import EmailVerification, User, UserStatus


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
    valid, message = _auth_shared.AuthService.validate_password_strength(signup_data.password)
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
        password_hash=_auth_shared.AuthService.hash_password(signup_data.password),
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
    access_token, refresh_token, session = await _auth_shared.AuthService.create_session(
        db, user, ip_address=request.client.host, user_agent=request.headers.get("user-agent")
    )

    # Log activity
    await _auth_shared.log_activity(db, str(user.id), "signup", {"method": "email"}, request)
    await _auth_shared.log_audit_event(db, str(user.id), "signup", {"method": "email"}, request)

    # Dispatch user.created webhook for CRM integration.
    # ISOLATED session, deliberately: the webhook path inserts an event-log
    # row, and a failure there (prod 2026-08-02: legacy_webhook_events table
    # missing) used to poison THIS request's session — the except below
    # swallowed the first error, but the doomed pending INSERT detonated at
    # the next db.commit(), turning every valid signup into a 503. With a
    # dedicated session, webhook logging cannot touch the signup transaction.
    try:
        async with AsyncSessionLocal() as webhook_db:
            await _auth_shared.trigger_user_webhook(
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
            org_id=getattr(user, "tenant_id", None),
            formality=getattr(user, "spanish_formality", None),
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
        user = await _auth_shared.get_user_by_email(db, credentials.email, tenant_id=None)
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
    if not user.password_hash or not _auth_shared.AuthService.verify_password(
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

    # SECURITY: Check if MFA is required before issuing session tokens.
    # The failure counter is reset only once no second factor is pending
    # (/mfa/challenge/verify resets it after the code checks).
    if getattr(user, "mfa_enabled", False) and getattr(user, "mfa_secret", None):
        from app.auth.mfa_enforcement import mint_mfa_challenge_token

        mfa_token = mint_mfa_challenge_token(user, methods=["pwd"])

        await _auth_shared.log_activity(
            db, str(user.id), "signin", {"method": "password", "mfa_required": True}, request
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
            mfa_token=mfa_token,
        )

    from app.auth.authentication_assurance import user_requires_mfa

    if await user_requires_mfa(db, user):
        raise HTTPException(428, "MFA enrollment required; continue through hosted sign-in")

    # No second factor pending: the sign-in is complete.
    await AccountLockoutService.reset_failed_attempts(db, user)

    # Create session (no MFA required)
    access_token, refresh_token, session = await _auth_shared.AuthService.create_session(
        db,
        user,
        ip_address=request.client.host,
        user_agent=request.headers.get("user-agent"),
        authentication_methods=["pwd"],
        authenticated_at=datetime.utcnow(),
    )

    # Log activity (best-effort, don't fail login)
    try:
        await _auth_shared.log_activity(db, str(user.id), "signin", {"method": "password"}, request)
    except Exception:
        pass
    try:
        await _auth_shared.log_audit_event(db, str(user.id), "signin", {"method": "password"}, request)
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

    # Validate access token, revocation list included. `verify_token` is a
    # coroutine; until 2026-10 it was called here without `await`, so the
    # revocation check never ran and `payload.get` failed on the coroutine.
    # When Redis cannot answer the revocation check this raises
    # RedisUnavailableError (503 + Retry-After), never "session valid".
    payload = await _auth_shared.AuthService.verify_token(access_token, token_type="access")
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
