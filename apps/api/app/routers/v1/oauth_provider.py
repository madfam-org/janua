"""
OAuth2 Provider Endpoints for Janua

This module implements the OAuth 2.0 Authorization Server endpoints that allow
external applications (like Enclii) to authenticate users via Janua.

Implements:
- Authorization Endpoint (GET/POST /oauth/authorize)
- Token Endpoint (POST /oauth/token)
- UserInfo Endpoint (GET /oauth/userinfo)

Based on RFC 6749 (OAuth 2.0) and OpenID Connect Core 1.0
"""

import hashlib
import html
import json
import os
import re
import secrets
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, List, Optional
from urllib.parse import urlencode

import structlog
from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.authorize_resume import authorize_query
from app.auth.login_method import normalize_login_method
from app.auth.resource_consent_page import render_resource_consent_page
from app.auth.sessions_cookie import (
    SESSIONS_COOKIE_NAME,
    TAB_SESSION_HEADER,
    read_sessions_cookie,
)
from app.auth.sso_cookie import (
    SSO_COOKIE_NAME,
    clear_sso_cookie,
    resolve_session_by_id,
    resolve_sso_cookie_session,
    revoke_sso_cookie_session,
)
from app.config import settings
from app.core.database import get_db
from app.core.jwt_manager import jwt_manager
from app.core.oauth_metadata import oauth_issuer
from app.core.protected_resources import (
    OFFLINE_ACCESS_SCOPE,
    PROTECTED_RESOURCES,
    InvalidResourceIndicator,
    ProtectedResource,
    all_cimd_client_ids,
    all_cimd_hosts,
    canonical_resource,
    granted_scopes,
    is_loopback_redirect,
    redirect_display_host,
    redirect_uri_matches,
)
from app.core.redis import ResilientRedisClient, get_redis
from app.core.redis_circuit_breaker import RedisUnavailableError
from app.core.reserved_oauth_boundaries import SILENT_AUTH_SCOPE, is_first_party_name
from app.core.url_security import (
    is_safe_redirect_url,
    validate_oauth_redirect_uri,
    validate_post_logout_redirect_uri,
)
from app.dependencies import get_current_user
from app.models import OAuthClient, Organization, OrganizationMember, User, UserStatus
from app.models import Session as UserSession
from app.services import resource_tokens, token_revocation
from app.services.audit_logger import AuditEventType, AuditLogger
from app.services.client_id_metadata import (
    ClientMetadataError,
    client_id_host,
    is_url_client_id,
    resolve_client_metadata,
)
from app.services.consent_service import ConsentService
from app.services.entitlements_service import (
    entitlements_to_claim,
    get_user_entitlements,
)
from app.services.oauth_client_authority import client_registered_by_platform_admin
from app.services.org_claims_service import (
    ORG_ROLES_CLAIM,
    get_user_org_claims,
    merge_app_roles_into_claims,
)
from app.services.service_principal import service_principal_claims

logger = structlog.get_logger()
router = APIRouter(prefix="/oauth", tags=["OAuth Provider"])
# Root-level OIDC end-session route (mounted at /logout in main.py)
logout_router = APIRouter(tags=["OAuth Provider"])

# CSRF token TTL (10 minutes)
CSRF_TOKEN_TTL = 600

# Lifetime of client_credentials (service) access tokens. Machine tokens are
# deliberately short-lived: services re-request tokens instead of refreshing,
# so this must match the `expires_in` advertised in the token response rather
# than inheriting the (much longer) human-session access-token TTL.
SERVICE_TOKEN_TTL_SECONDS = 3600


def _audiences_from_claims(claims: dict) -> list[str]:
    """Extract audience values embedded in a JWT (string or array claim)."""
    audiences: list[str] = []
    token_aud = claims.get("aud")
    if isinstance(token_aud, str):
        audiences.append(token_aud)
    elif isinstance(token_aud, list):
        audiences.extend(str(value) for value in token_aud if value)
    return audiences


def _merge_audiences(*groups: list[str]) -> list[str]:
    """Return de-duplicated audience strings preserving order."""
    merged: list[str] = []
    for group in groups:
        for audience in group:
            if audience and audience not in merged:
                merged.append(audience)
    return merged


def _accepted_audiences_for_client(client: OAuthClient | None) -> list[str]:
    """Return accepted token audiences for an OAuth client, including legacy global aud."""
    if not client:
        return [settings.JWT_AUDIENCE]
    return _merge_audiences(
        [client.audience or settings.JWT_AUDIENCE, settings.JWT_AUDIENCE],
    )


async def _resolve_token_client(
    token: str,
    db: AsyncSession,
    expected_client: Optional[OAuthClient] = None,
    claims: Optional[dict] = None,
) -> Optional[OAuthClient]:
    """Resolve the OAuth client bound to a token before audience validation."""
    if expected_client:
        return expected_client

    if claims is None:
        try:
            claims = jwt_manager.get_unverified_claims(token)
        except Exception:
            return None

    client_id = claims.get("client_id")
    if not client_id:
        return None

    client = await _get_oauth_client(client_id, db)
    if not client or not client.is_active:
        return None
    return client


async def _verify_oauth_token(
    token: str,
    token_type: str,
    db: AsyncSession,
    expected_client: Optional[OAuthClient] = None,
) -> Optional[dict]:
    """Verify OAuth tokens against client + token audiences (e.g. karafiel-api)."""
    try:
        claims = jwt_manager.get_unverified_claims(token)
    except Exception:
        return None

    client = await _resolve_token_client(
        token,
        db,
        expected_client,
        claims=claims,
    )
    audiences = _merge_audiences(
        _accepted_audiences_for_client(client),
        _audiences_from_claims(claims),
    )

    payload = jwt_manager.verify_token(
        token,
        token_type=token_type,
        audience=audiences,
    )
    if not payload:
        return None

    if client:
        token_client_id = payload.get("client_id")
        if token_client_id and token_client_id != client.client_id:
            logger.warning(
                "OAuth token client mismatch",
                expected=client.client_id,
                got=token_client_id,
                token_type=token_type,
            )
            return None

    return payload


# Consent security state (CSRF tokens, stored authorization requests,
# authorization codes) must be the SAME on every API replica: the consent page
# is rendered by one pod and the form is posted to whichever pod the load
# balancer picks. It therefore goes through the client's STRICT operations,
# which raise `RedisUnavailableError` (answered as a retryable 503 by
# `redis_unavailable_handler`) instead of falling back to a value or to one
# pod's memory. Before 2026-10 these calls used the breaker's fallback: a token
# "stored" while a pod's circuit was open (or while its client had never
# connected) was stored nowhere, and the Allow button then failed on every pod
# with 403 "Invalid or expired CSRF token".


async def _generate_csrf_token(user_id: str, redis: ResilientRedisClient) -> str:
    """Generate a CSRF token for OAuth consent forms.

    Raises RedisUnavailableError when the token cannot be stored, so no consent
    form is ever rendered with a token that cannot validate.
    """
    csrf_token = secrets.token_urlsafe(32)
    await redis.strict_set(f"oauth:csrf:{csrf_token}", user_id, ex=CSRF_TOKEN_TTL)
    return csrf_token


async def _validate_csrf_token(csrf_token: str, user_id: str, redis: ResilientRedisClient) -> bool:
    """Validate a CSRF token and consume it (single use).

    False means the token is really unusable (absent, unknown, expired, issued
    to another user, or consumed by a concurrent submit). Redis being
    unavailable is NOT that: it raises RedisUnavailableError (→ 503).
    """
    if not csrf_token:
        logger.info("oauth.consent.csrf_rejected", reason="missing")
        return False

    key = f"oauth:csrf:{csrf_token}"
    stored_user_id = await redis.strict_get(key)

    if not stored_user_id:
        # Unknown, expired, or already consumed (e.g. the form was submitted
        # twice). Never "not stored": a failed store raised at render time.
        logger.info("oauth.consent.csrf_rejected", reason="unknown_or_expired")
        return False

    # Verify it belongs to the same user
    if stored_user_id != user_id:
        logger.warning(
            "CSRF token user mismatch",
            expected=user_id,
            got=stored_user_id,
        )
        return False

    # Consume (single use). Of two concurrent submits only one deletes the key.
    if await redis.strict_delete(key) != 1:
        logger.info("oauth.consent.csrf_rejected", reason="consumed_concurrently")
        return False
    return True


# ============================================================================
# User Entitlements Helper (Galaxy Membership Claims)
# ============================================================================


async def _get_user_entitlements(
    user: User,
    db: AsyncSession,
) -> dict:
    """
    Fetch user entitlements for JWT enrichment.

    Returns tier, roles, and subscription status for the Galaxy ecosystem.
    This enables "one membership, all services" across Enclii, Dhanam, etc.

    Returns:
        dict with keys: tier, roles, sub_status, is_admin
    """
    # Default entitlements (community tier, no special roles)
    entitlements = {
        "tier": "community",
        "roles": [],
        "sub_status": "inactive",
        "is_admin": user.is_admin if hasattr(user, "is_admin") else False,
    }

    try:
        # Get user's ACTIVE organization memberships only. A member whose
        # status is pending/inactive/removed must NOT keep org roles or tier in
        # their token — mirrors the status filter in `_get_user_org_claims`.
        result = await db.execute(
            select(OrganizationMember).where(
                OrganizationMember.user_id == user.id,
                OrganizationMember.status == "active",
            )
        )
        memberships = result.scalars().all()

        if memberships:
            # Collect all roles across active organizations
            roles = list({m.role for m in memberships if m.role})
            entitlements["roles"] = roles

            # Get primary organization (tenant, or first ACTIVE membership).
            primary_org_id = memberships[0].organization_id
            if hasattr(user, "tenant_id") and user.tenant_id:
                primary_org_id = user.tenant_id

            # Fetch organization for subscription tier
            org_result = await db.execute(
                select(Organization).where(Organization.id == primary_org_id)
            )
            org = org_result.scalar_one_or_none()

            if org:
                entitlements["tier"] = org.subscription_tier or "community"
                # Check if org has active subscription (simplified check)
                entitlements["sub_status"] = (
                    "active"
                    if org.subscription_tier and org.subscription_tier != "community"
                    else "active"
                )

        # Add admin role if user is system admin
        if entitlements["is_admin"] and "admin" not in entitlements["roles"]:
            entitlements["roles"].append("admin")

    except Exception as e:
        logger.warning(
            "Failed to fetch user entitlements, using defaults",
            user_id=str(user.id),
            error=str(e),
        )
        await db.rollback()

    return entitlements


# Organization claims now live in app/services/org_claims_service.py — the SSOT
# shared with AuthService.create_session / refresh_tokens, so a magic-link
# session token carries the SAME org_id/tenant_id/org_slug an OIDC token does.
# Re-exported under the historical private name so existing call sites and
# tests keep addressing it here.
_get_user_org_claims = get_user_org_claims


# ============================================================================
# Cookie-based Authentication Helper
# ============================================================================


def _verify_own_access_token(token: str) -> Optional[dict]:
    """Verify an access token Janua itself minted, tolerating any audience it mints.

    `jwt_manager.verify_token` validates against the single platform audience
    (`JWT_AUDIENCE`), which is right for a resource server deciding which
    tokens to accept. Here Janua is the ISSUER reading its own session, and it
    mints more than one audience: a magic-link session carries the audience of
    the product the link forwards to (`crea-map`, `nauta-portal`, ...) — see
    `_session_audience_for_redirect` in routers/v1/auth.py. Rejecting those
    would mean the session cookie written on a magic-link login (B1) is
    invisible to `/authorize`, so `prompt=none` would answer `login_required`
    for every product session with no error anywhere in the happy path.

    This mirrors the tolerance `AuthService.verify_token`
    (services/auth_service.py) already has, adapted to how `jwt_manager`
    reports failure: it SWALLOWS `InvalidTokenError` — of which
    `InvalidAudienceError` is a subclass — and returns None rather than
    raising, so the retry is driven by a None result, not by an except clause.
    The second pass turns off ONLY the audience check; signature, issuer,
    expiry and token type stay enforced both times, and a token with no usable
    `aud` claim is still refused, exactly as AuthService does.
    """
    payload = jwt_manager.verify_token(token, token_type="access")
    if payload:
        return payload

    payload = jwt_manager.verify_token(token, token_type="access", verify_audience=False)
    if not payload:
        return None
    aud = payload.get("aud")
    if not isinstance(aud, str) or not aud:
        logger.warning("Session token carries no usable audience claim")
        return None
    return payload


def _redacted(user_id: Any) -> str:
    """An id prefix, for logs that must name *which* two people disagreed.

    Eight characters of a UUID identify the row for an operator reading Janua's
    own logs next to its own database, and are not an identifier that can be
    presented anywhere. Full user ids never enter a log line here.
    """
    return f"{str(user_id)[:8]}…"


def _session_started_at(session: Any) -> Optional[datetime]:
    """When a `sessions` row began, for ordering two sessions by recency.

    `created_at` is the birth of the session and never moves; `last_activity`
    is a fallback for rows old enough (or mocked thin enough) to carry no
    `created_at`. Deliberately NOT the other way round: "most recent login" is
    the question, and a background token refresh on an old session must not be
    able to make it look newer than a login that just happened.
    """
    started = getattr(session, "created_at", None)
    if isinstance(started, datetime):
        return started
    activity = getattr(session, "last_activity", None)
    return activity if isinstance(activity, datetime) else None


async def _hosted_cookie_session(payload: dict[str, Any], db: AsyncSession) -> Optional[Any]:
    """The `sessions` row a verified `janua_access_token` belongs to, if findable.

    `AuthService.create_session` writes the access token's `jti` to
    `sessions.access_token_jti`, so the row is one indexed lookup away. It is
    genuinely optional: `refresh_tokens` rotates that column, so a cookie whose
    session has since refreshed matches no row. A `None` here is "undatable",
    never "invalid" — the caller treats it as such.
    """
    jti = payload.get("jti")
    if not jti:
        return None
    result = await db.execute(select(UserSession).where(UserSession.access_token_jti == jti))
    return result.scalar_one_or_none()


async def get_user_from_cookie_or_header(
    request: Request,
    db: AsyncSession,
) -> Optional[User]:
    """
    Get authenticated user from, in precedence order:
    1. Bearer token in Authorization header (API clients)
    2. X-Janua-Session header (per-tab override — two-tab focus, Layer 3
       follow-on): honored ONLY when its sid is in this browser's signed
       janua_sessions held-set AND names a live sessions row. Otherwise ignored
       and resolution falls through to the cookie — never an escalation.
    3. janua_sso cookie (the estate session — J5/R1)
    4. janua_access_token cookie (the hosted-login browser session)

    This enables the OAuth authorize endpoint to work with browser sessions
    after the user logs in via the login form, or after a magic link (B1).
    Both cookie paths accept any audience Janua minted — see
    `_verify_own_access_token`.

    (2) is the case B1 could not reach. The MAP and the nauta ERP portal exchange
    the magic link server-to-server, so their browsers never receive
    `janua_access_token`; `@madfam/janua-next` relays `janua_sso` to the browser
    instead. A person arriving at `/authorize` from another product has ONLY that
    cookie, and it must be enough — for `prompt=none` and for the interactive
    flow alike, which is what "single sign-on" means. Everything the interactive
    path enforces afterwards (email verification, MFA, consent for third
    parties) is enforced identically; this resolves *who* the person is, never
    *whether they may proceed*.

    ## Why the estate cookie outranks the hosted one (J9)

    Until J9 the order was Bearer → `janua_access_token` → `janua_sso`, and in
    production that silently sent the wrong person through the ERP's silent SSO.
    A browser that had ever completed a hosted login on `auth.madfam.io` keeps
    `janua_access_token` for that person; `/signout` does not clear it (only the
    OIDC `end_session` endpoint does), and **no other host in the estate can**:
    `crea-map.madfam.io` cannot delete a cookie scoped to the issuer host. So a
    fresh MAP magic-link login, whose only browser-visible trace is the relayed
    `janua_sso`, lost to a stale hosted cookie for whoever last used the hosted
    form on that machine, and `/authorize` issued a code for the wrong user with
    nothing wrong in the happy path. Ordering at this seam is the only fix that
    does not depend on a cookie one origin cannot reach.

    The estate cookie is also the safer thing to rank first: it is the only one
    of the three whose validity is re-read from the `sessions` row on every use,
    so revoking that row stops it immediately, while a `janua_access_token`
    remains valid until its own `exp` regardless of the session's fate.

    ### When both cookies are valid and name different people

    Take the **newer session**, and say so in the log. The estate row's
    `created_at` comes back with resolution; the hosted cookie's row is looked up
    by its `jti` (`_hosted_cookie_session`) and may legitimately not be found,
    because refresh rotation moves `access_token_jti`. An undatable hosted
    session cannot be shown to be newer, so the estate session keeps precedence —
    as it does on an exact tie. Same user in both cookies: no contest.

    This function is the ONLY reader of `janua_sso` — and, deliberately, the ONLY
    reader of the `X-Janua-Session` per-tab header, so that header can never
    become a general auth input or a second bearer channel. Its only callers are
    the authorize flow (`GET /authorize`) and its consent continuation
    (`POST /consent`). Neither the cookie nor the header is a bearer substitute:
    the cookie carries `type: "sso_session"`, the held-set that gates the header
    carries `type: "sso_session_set"`, and every bearer path — `get_current_user`,
    `_verify_own_access_token` above — verifies `token_type="access"`, so neither
    can be presented as `Authorization: Bearer …`.
    """
    # First, the Authorization header. Unchanged and still first: an API client
    # that attaches a bearer token is naming the identity it means to act as,
    # explicitly, per request — nothing ambient can be staler than that.
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]
        try:
            payload = _verify_own_access_token(token)
            if payload and payload.get("sub"):
                result = await db.execute(select(User).where(User.id == payload.get("sub")))
                user = result.scalar_one_or_none()
                if user:
                    return user
        except Exception:
            pass  # Intentionally ignoring - JWT verification failure handled by trying cookie auth next

    # Between the bearer and the estate cookie: the per-tab session override
    # (two-tab focus, the Layer 3 follow-on). A tab that wants to be a different
    # held account than the browser-wide `janua_sso` pointer sends `sid` in the
    # `X-Janua-Session` header. It is honored ONLY when that sid is BOTH vouched
    # for by this browser's signed `janua_sessions` held-set AND still a live,
    # active `sessions` row of an active user — the same two-part construction
    # `switch-session` uses, applied per-tab instead of browser-wide.
    #
    # Why this cannot escalate (and why it ranks here, just above the cookie it
    # overrides, never above an explicit bearer):
    #   - The header carries no secret — a `sid` is the same opaque id the two
    #     estate cookies already carry, and every use re-reads the row, so a
    #     revoked/expired sid authenticates nothing (exactly as at `/authorize`).
    #   - It is useless without the HttpOnly, signed `janua_sessions` cookie
    #     proving the browser holds that sid: an unheld sid is IGNORED (it falls
    #     through to `janua_sso` below — never an error, never an escalation), so
    #     the header adds no authority the browser did not already have.
    #   - It mints no token. Like `janua_sso`, it only decides *who* the person
    #     is; every gate after this point (email-verified, MFA, consent) is
    #     unchanged and decides *whether they may proceed*.
    # A custom request header is also not attachable by a cross-site form or
    # top-level navigation, so this is a CSRF gain over the ambient cookie.
    tab_sid = request.headers.get(TAB_SESSION_HEADER)
    if tab_sid:
        try:
            held = read_sessions_cookie(request.cookies.get(SESSIONS_COOKIE_NAME))
            if tab_sid in held:
                tab_user, _tab_session = await resolve_session_by_id(tab_sid, db)
                if tab_user is not None:
                    return tab_user
                logger.info(
                    "X-Janua-Session names a held sid whose row is not live; ignoring"
                )
            else:
                # A sid not in the signed held-set is refused deliberately: the
                # header can never front an account this browser was not granted.
                logger.info("X-Janua-Session sid is not in the held set; ignoring")
        except Exception:
            logger.warning("X-Janua-Session header resolution failed", exc_info=True)

    # Second, the estate cookie — see the docstring for why it outranks the
    # hosted one. Unlike the header above this is not a token the holder could
    # spend anywhere: resolution re-reads the `sessions` row it references, so a
    # revoked session stops authenticating it immediately.
    estate_user: Optional[User] = None
    estate_session: Optional[Any] = None
    sso_cookie = request.cookies.get(SSO_COOKIE_NAME)
    if sso_cookie:
        try:
            estate_user, estate_session = await resolve_sso_cookie_session(sso_cookie, db)
        except Exception:
            logger.warning("janua_sso cookie resolution failed", exc_info=True)

    # Third, the hosted-login cookie. Resolved even when the estate cookie
    # already answered, but only so a disagreement can be detected and decided
    # deliberately — never so it can win by arriving second.
    hosted_user: Optional[User] = None
    hosted_payload: Optional[dict[str, Any]] = None
    access_token = request.cookies.get("janua_access_token")
    if access_token:
        try:
            payload = _verify_own_access_token(access_token)
            if payload and payload.get("sub"):
                result = await db.execute(select(User).where(User.id == payload.get("sub")))
                hosted_user = result.scalar_one_or_none()
                if hosted_user is not None:
                    hosted_payload = payload
        except Exception:
            pass  # Intentionally ignoring - cookie JWT verification failure means user is not authenticated

    if estate_user is None:
        return hosted_user
    if hosted_user is None or str(hosted_user.id) == str(estate_user.id):
        return estate_user

    # Two valid cookies, two different people. Prefer the newer session.
    hosted_started: Optional[datetime] = None
    try:
        hosted_session = (
            await _hosted_cookie_session(hosted_payload, db) if hosted_payload else None
        )
        if hosted_session is not None:
            hosted_started = _session_started_at(hosted_session)
    except Exception:
        logger.warning("Could not date the janua_access_token session", exc_info=True)

    estate_started = _session_started_at(estate_session)
    hosted_wins = (
        hosted_started is not None and estate_started is not None and hosted_started > estate_started
    )
    logger.info(
        "Session cookies name different users; preferring the newer session",
        estate_user=_redacted(estate_user.id),
        hosted_user=_redacted(hosted_user.id),
        estate_session_started=estate_started.isoformat() if estate_started else None,
        hosted_session_started=hosted_started.isoformat() if hosted_started else None,
        winner="janua_access_token" if hosted_wins else SSO_COOKIE_NAME,
    )
    return hosted_user if hosted_wins else estate_user


# ============================================================================
# Pydantic Schemas
# ============================================================================


class AuthorizationRequest(BaseModel):
    """OAuth 2.0 Authorization Request parameters."""

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

    access_token: str
    token_type: str = "Bearer"
    expires_in: int
    refresh_token: Optional[str] = None
    id_token: Optional[str] = None
    scope: str


class UserInfoResponse(BaseModel):
    """OpenID Connect UserInfo Response."""

    sub: str = Field(..., description="Subject identifier (user ID)")
    email: Optional[str] = None
    email_verified: Optional[bool] = None
    name: Optional[str] = None
    given_name: Optional[str] = None
    family_name: Optional[str] = None
    picture: Optional[str] = None
    updated_at: Optional[int] = None


# ============================================================================
# Redis-based authorization code storage
# ============================================================================

AUTH_CODE_PREFIX = "oauth:code:"
AUTH_CODE_TTL = 600  # 10 minutes


def _auth_code_ref(code: str) -> str:
    """Log-safe reference to an authorization code (never the code itself).

    The code is a bearer credential until redeemed; logs carry a short hash so
    store and lookup lines can still be correlated.
    """
    return hashlib.sha256(code.encode()).hexdigest()[:12]


async def _store_auth_code(code: str, data: dict, redis: ResilientRedisClient):
    """Store authorization code in Redis with TTL.

    Strict: raises RedisUnavailableError (→ 503 + Retry-After) when Redis cannot
    store it. A breaker fallback here would keep the code in one pod's memory,
    where the token endpoint on the other pod cannot find it.
    """
    key = f"{AUTH_CODE_PREFIX}{code}"
    ref = _auth_code_ref(code)
    logger.info("Storing auth code in Redis", code_ref=ref, client_id=data.get("client_id"))
    await redis.strict_set(key, json.dumps(data), ex=AUTH_CODE_TTL)
    logger.info("Auth code stored successfully", code_ref=ref)


async def _get_auth_code(code: str, redis: ResilientRedisClient) -> dict | None:
    """Retrieve authorization code from Redis itself (strict: never a pod-local copy).

    A fallback read could return a code this pod saw earlier and another pod
    already redeemed — replay of a single-use code.
    """
    key = f"{AUTH_CODE_PREFIX}{code}"
    ref = _auth_code_ref(code)
    logger.info("Retrieving auth code from Redis", code_ref=ref)
    data = await redis.strict_get(key)
    if data:
        logger.info("Auth code found in Redis", code_ref=ref)
        return json.loads(data)
    logger.warning("Auth code NOT found in Redis", code_ref=ref)
    return None


async def _delete_auth_code(code: str, redis: ResilientRedisClient) -> bool:
    """Consume an authorization code (single use).

    True only for the caller that actually removed it: of two concurrent
    redemptions of the same code, exactly one wins.
    """
    key = f"{AUTH_CODE_PREFIX}{code}"
    return await redis.strict_delete(key) == 1


# ============================================================================
# Helper Functions
# ============================================================================


async def _get_oauth_client(client_id: str, db: AsyncSession) -> OAuthClient | None:
    """Retrieve OAuth client by client_id."""
    result = await db.execute(select(OAuthClient).where(OAuthClient.client_id == client_id))
    return result.scalar_one_or_none()


def _validate_redirect_uri(redirect_uri: str, allowed_uris: list[str]) -> bool:
    """
    Validate that redirect_uri is in the allowed list.

    SECURITY: This function prevents open redirect attacks (CWE-601) by
    ensuring the redirect URI exactly matches one of the pre-registered
    URIs for the OAuth client. This is a critical security control.
    """
    # Use centralized validation from url_security module
    return validate_oauth_redirect_uri(redirect_uri, allowed_uris)


def _verify_pkce(code_verifier: str, code_challenge: str, method: str = "S256") -> bool:
    """Verify PKCE code verifier against stored challenge.

    SECURITY: Only S256 method is supported. Plain method is not allowed
    as it provides no security benefit and violates OAuth 2.1 recommendations.
    """
    if method != "S256":
        # SECURITY: Only S256 is allowed - plain method is not secure
        logger.warning("Rejected PKCE with non-S256 method", method=method)
        return False

    # S256: BASE64URL(SHA256(code_verifier))
    import base64

    verifier_hash = hashlib.sha256(code_verifier.encode("ascii")).digest()
    computed_challenge = base64.urlsafe_b64encode(verifier_hash).rstrip(b"=").decode("ascii")
    return secrets.compare_digest(computed_challenge, code_challenge)


def _generate_id_token(
    user: User,
    client_id: str,
    nonce: Optional[str] = None,
    access_token: Optional[str] = None,
) -> str:
    """Generate an OpenID Connect ID Token."""
    now = datetime.now(timezone.utc)
    # Use JANUA_CUSTOM_DOMAIN as issuer if set (for white-label deployments like auth.madfam.io)
    # This must match the issuer in /.well-known/openid-configuration
    custom_domain_issuer = os.getenv("JANUA_CUSTOM_DOMAIN")
    if custom_domain_issuer:
        issuer = f"https://{custom_domain_issuer}".rstrip("/")
    elif settings.API_BASE_URL:
        issuer = settings.API_BASE_URL.rstrip("/")
    else:
        issuer = settings.BASE_URL or "https://api.janua.dev"

    claims = {
        "iss": issuer,
        "sub": str(user.id),
        "aud": client_id,
        "exp": int((now + timedelta(hours=1)).timestamp()),
        "iat": int(now.timestamp()),
        "auth_time": int(now.timestamp()),
        "email": user.email,
        "email_verified": user.email_verified if hasattr(user, "email_verified") else True,
        "name": user.name if hasattr(user, "name") else None,
    }

    if nonce:
        claims["nonce"] = nonce

    # Add at_hash (access token hash) if access_token provided
    if access_token:
        # at_hash is left 128 bits of SHA256 of access token, base64url encoded
        import base64

        token_hash = hashlib.sha256(access_token.encode("ascii")).digest()
        claims["at_hash"] = base64.urlsafe_b64encode(token_hash[:16]).rstrip(b"=").decode("ascii")

    return jwt_manager.encode_token(claims)


def _build_safe_callback_url(
    redirect_uri: str,
    params: dict,
    client_validated: bool = False,
) -> str:
    """
    Build an authorization-response callback URL with query parameters.

    SECURITY: The redirect_uri MUST have been validated against the OAuth client's
    registered redirect URIs BEFORE calling this function. This function assumes
    the redirect_uri is already trusted.

    Every authorization response, success or error, carries `iss` (RFC 9207,
    advertised as `authorization_response_iss_parameter_supported`): the
    issuer from the discovery document, so a client talking to more than one
    authorization server can tell which one answered (mix-up defence). A
    redirect URI that already has a query keeps it; the parameters are added
    with `&` (RFC 6749 §3.1.2).

    Args:
        redirect_uri: The validated redirect URI from the OAuth client
        params: Query parameters to append (code, state, error, etc.)
        client_validated: If True, the redirect_uri was already validated against
            the OAuth client's registered redirect_uris. Skips host allowlist
            check but still validates against dangerous schemes.

    Returns:
        The complete callback URL with query parameters
    """
    # Always block dangerous schemes regardless of validation status
    url_lower = (redirect_uri or "").lower().strip()
    if url_lower.startswith(("javascript:", "data:", "vbscript:", "file:")):
        logger.error(
            "Blocked dangerous scheme in redirect URI",
            redirect_uri_prefix=redirect_uri[:50] if redirect_uri else None,
        )
        raise ValueError("Invalid redirect URI scheme")

    if not client_validated:
        # Full host allowlist check for non-client-validated URIs
        if not is_safe_redirect_url(redirect_uri, allow_relative=False):
            logger.error(
                "Attempted to build callback URL with unsafe redirect_uri",
                redirect_uri_prefix=redirect_uri[:50] if redirect_uri else None,
            )
            raise ValueError("Invalid redirect URI")

    response_params = dict(params)
    response_params["iss"] = oauth_issuer()
    separator = "&" if "?" in redirect_uri else "?"
    return f"{redirect_uri}{separator}{urlencode(response_params)}"


#: What a client with no stored ``grant_types`` / ``allowed_scopes`` may use.
DEFAULT_CLIENT_GRANT_TYPES = ("authorization_code", "refresh_token")
DEFAULT_CLIENT_SCOPES = ("openid", "profile", "email")


def _client_grant_types(client: OAuthClient) -> set:
    """The grant types the token endpoint honours for ``client``.

    The stored value is taken as-is (``set(value)``), falling back to the
    defaults when it is empty. Only a JSON array of names names a grant.
    `scripts/audit_client_credentials_tier_claims.py` carries a copy; its
    tests fail if the two drift.
    """
    return set(client.grant_types or DEFAULT_CLIENT_GRANT_TYPES)


def _client_allowed_scopes(client: OAuthClient) -> set:
    """The scopes a token grant may request for ``client`` (same rules as above)."""
    return set(client.allowed_scopes or DEFAULT_CLIENT_SCOPES)


def _parse_requested_scopes(scope: Optional[str], client: OAuthClient) -> str:
    """Return validated space-separated scopes for token grants."""
    allowed = _client_allowed_scopes(client)
    requested = set((scope or "").split())
    if not requested:
        requested = set(allowed)

    if not requested.issubset(allowed):
        denied = sorted(requested - allowed)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"invalid_scope: {', '.join(denied)}",
        )

    return " ".join(sorted(requested))


#: Standard OIDC identity scopes an END-USER grant may always carry, whatever
#: the client's stored ``allowed_scopes``. They confer nothing beyond the
#: person's own identity — the ID token already carries ``email``/``name`` and a
#: refresh token is issued without ``offline_access`` — so honouring them keeps
#: every existing sign-in working even for a client whose stored list omits
#: one (``offline_access`` is not in ``DEFAULT_CLIENT_SCOPES``). Not used by the
#: client_credentials grant.
USER_GRANT_IDENTITY_SCOPES = frozenset({"openid", "profile", "email", "offline_access"})


def _narrow_to_allowed_scopes(scope: Optional[str], client: OAuthClient) -> tuple[str, list[str]]:
    """Narrow an END-USER grant's scope to what ``client`` may hold.

    The authorization-code and refresh grants carry a scope a person approved
    for a client. That scope may never contain anything outside the client's
    ``allowed_scopes`` (``_client_allowed_scopes``, the client_credentials
    allowlist) plus ``USER_GRANT_IDENTITY_SCOPES``. RFC 6749 §3.3 lets the authorization server
    "fully or partially ignore the scope requested"; the token response's
    ``scope`` field then tells the client what was actually granted.

    Returns ``(granted, dropped)``:

    * ``granted`` is the input UNCHANGED (byte for byte) when every requested
      scope is allowed — so a client that only asks for what it is registered
      for sees exactly the token it saw before. Otherwise it is the allowed
      subset, space-joined in request order with duplicates removed. An empty
      request stays empty (nothing to narrow, nothing to widen).
    * ``dropped`` lists the refused scopes (sorted, de-duplicated) for logging.

    Callers decide what an empty result means for their grant (see
    ``_require_grantable_scope``). The client_credentials grant keeps using
    ``_parse_requested_scopes``, which rejects instead of narrowing.
    """
    requested = (scope or "").split()
    allowed = _client_allowed_scopes(client) | USER_GRANT_IDENTITY_SCOPES
    dropped = sorted({s for s in requested if s not in allowed})
    if not dropped:
        return scope or "", []
    kept: list[str] = []
    for s in requested:
        if s in allowed and s not in kept:
            kept.append(s)
    return " ".join(kept), dropped


def _require_grantable_scope(scope: Optional[str], client: OAuthClient, *, grant: str) -> str:
    """``_narrow_to_allowed_scopes`` plus the one case narrowing cannot answer.

    A NON-EMPTY request of which nothing is allowed has no partial grant to
    fall back to, so it is refused with ``invalid_scope`` (``ValueError``; the
    caller maps it to a redirect or a 400 as its endpoint requires). Dropped
    scopes are logged, never silently discarded.
    """
    granted, dropped = _narrow_to_allowed_scopes(scope, client)
    if dropped:
        logger.warning(
            "oauth.scope_not_allowed_for_client",
            grant=grant,
            client_id=client.client_id,
            dropped_scopes=dropped,
            granted_scope=granted,
        )
    if (scope or "").split() and not granted:
        raise ValueError(f"invalid_scope: {', '.join(dropped)}")
    return granted


# The scope a relying party requests to receive a PostgREST-shaped token — the
# BaaS/data-API seam (enclii managed-Postgres addons). Opt-in per client: it only
# takes effect when the client has it in `allowed_scopes` AND requests it, so
# every existing token is byte-for-byte unchanged. See `_data_api_claims`.
DATA_API_SCOPE = "data-api"
# The single scalar Postgres role PostgREST maps to `SET LOCAL ROLE` for an
# authenticated end-user. Deliberately the conventional Supabase/PostgREST value
# so a tenant's existing PostgREST/RLS setup and `@supabase/*` clients work as-is.
DATA_API_ROLE = "authenticated"


def _data_api_claims(scope: str, client: OAuthClient, org_claims: dict) -> dict:
    """Extra claims that make a token consumable by an enclii data-API (PostgREST).

    Returns `{}` unless the granted scope includes ``data-api`` (which requires
    the client to have that scope allowed) — so this is a NO-OP for every token
    that does not opt in, and no existing MADFAM/ecosystem token changes shape.

    When opted in, two claims are added:
      * ``role`` — the SCALAR PostgREST needs for ``SET LOCAL ROLE`` (Janua's
        other tokens carry ``roles`` as an ARRAY of app-RBAC roles, which
        PostgREST cannot use). Set to ``authenticated``.
      * ``tenant_id`` — bound to the CLIENT's organization when it has one
        (`OAuthClient.organization_id`), so a data-API addon registered for a
        tenant always scopes to that tenant's rows under RLS, regardless of how
        many orgs the end-user belongs to. Falls back to the ambiguity-resolved
        ``tenant_id`` from `org_claims` when the client is not org-bound.
    """
    if DATA_API_SCOPE not in set(scope.split()):
        return {}
    claims: dict = {"role": DATA_API_ROLE}
    if client.organization_id is not None:
        claims["tenant_id"] = str(client.organization_id)
    elif org_claims.get("tenant_id"):
        claims["tenant_id"] = org_claims["tenant_id"]
    return claims


def _service_account_email(client: OAuthClient) -> str:
    """Derive a stable non-human email claim for machine clients."""
    slug = re.sub(r"[^a-z0-9-]+", "-", (client.name or "").lower()).strip("-")
    slug = slug or "service-account"
    return f"{slug}@service.auth.madfam.io"


# ---------------------------------------------------------------------------
# Application roles for org-bound service clients
# ---------------------------------------------------------------------------

#: Shape of a namespaced application role, `"<app>:<role>"` — the vocabulary
#: symbiosis-hcm reads (`hcm:hr`, `hcm:admin`, `hcm:employee`) and the same
#: shape `models/app_role.format_app_role` produces for a human's grant. Janua
#: validates SHAPE, never MEANING: it holds no table of valid apps and no
#: vocabulary of role names, exactly as it holds none for capability-link
#: scopes. A new HCM role must not require a janua deploy.
APP_ROLE_SCOPE_PATTERN = re.compile(r"^[a-z][a-z0-9-]*:[a-z][a-z0-9_-]*$")

#: Organization-MEMBERSHIP roles. These describe authority over the janua
#: ACCOUNT (inviting a colleague, rotating a secret, paying the invoice) and
#: must never authorize anything inside a product. They ride under the
#: namespaced `madfam_org_roles` claim and are refused here even if an operator
#: writes one into `allowed_scopes` — symbiosis-hcm's `HR_ROLES` set contains
#: the literal string `"admin"`, so an org role reaching a bare `roles` claim is
#: precisely the payroll leak the namespace exists to prevent.
ORG_MEMBERSHIP_ROLE_SCOPES = frozenset({"owner", "admin", "member"})


def _service_client_app_roles(client: OAuthClient, granted_scopes: set[str]) -> list[str]:
    """Namespaced application roles a machine token may carry, from its grant.

    THE GRANT FOR A SERVICE CLIENT IS ITS ``allowed_scopes``. A person's
    application roles come from `organization_member_app_roles` (migration 016),
    keyed by a membership row; a service client has no membership, so the
    operator-controlled column that already says what this client may ask for is
    the grant record. Nothing here is derived, defaulted, or inferred: a role
    reaches a service token because an operator put that exact string in
    `allowed_scopes` AND the client requested it.

    Four conditions, all required:

    1. **The client is org-bound** (`organization_id` is set). A service without
       a tenant must not carry tenant authority — its token has no `org_id` to
       scope the role to, so an `hcm:hr` on it would be authority over *every*
       tenant HCM happens to ask about. Fail-closed: no org, no app roles.
    2. **The scope was REQUESTED.** Least privilege survives: a client allowed
       `hcm:hr` that asks only for `openid` gets a token that cannot read
       payroll. (`_parse_requested_scopes` has already refused anything outside
       `allowed_scopes`, and defaults an empty request to the full allowed set.)
    3. **The scope is allowed** on the client. Belt-and-braces with (2): this
       function never reads a string the operator did not grant, even if a
       future caller reaches it with an unvalidated scope list.
    4. **The scope has the namespaced app-role SHAPE** and is not an
       organization-membership role nor a bare/`*:admin` legacy alias. The
       legacy aliases keep their existing underscore treatment in the caller
       (`hcm:admin` → `hcm_admin`) so no live consumer changes shape.

    Emitted VERBATIM, colon kept, because the resource server matches the exact
    string it publishes. Deduplicated and sorted so a token's role list is
    stable across mints — a claim that reorders between refreshes is a diff that
    means nothing and that someone will eventually try to debug.
    """
    if not client.organization_id:
        return []

    allowed = set(client.allowed_scopes or [])
    roles = set()
    for requested_scope in granted_scopes:
        if requested_scope not in allowed:
            continue
        if requested_scope in ORG_MEMBERSHIP_ROLE_SCOPES:
            continue
        if requested_scope.endswith(":admin"):
            # Legacy alias territory. The caller already emits the underscore
            # form (`hcm_admin`) for these and has done for every existing
            # consumer; minting the colon form here as well would quietly widen
            # what an established `*:admin` scope authorizes.
            continue
        if not APP_ROLE_SCOPE_PATTERN.match(requested_scope):
            continue
        roles.add(requested_scope)

    return sorted(roles)


async def _get_client_credentials_claims(
    client: OAuthClient,
    scope: str,
    db: AsyncSession,
) -> dict:
    """Build downstream-compatible claims for a machine OAuth client."""
    requested_scopes = set(scope.split())
    scoped_products = {
        requested_scope.split(":", 1)[0]
        for requested_scope in requested_scopes
        if ":" in requested_scope
    }
    roles = ["service_account"]
    if "admin" in requested_scopes:
        roles.append("admin")
    for requested_scope in requested_scopes:
        if requested_scope.endswith(":admin"):
            roles.append(requested_scope.replace(":", "_"))

    # Namespaced application roles from the client's grant (`allowed_scopes`).
    # ADDITIVE: every string above is still emitted, so no existing consumer
    # sees a claim change shape. See `_service_client_app_roles` for why the
    # grant is `allowed_scopes` and why a client with no `organization_id`
    # receives none of these.
    app_roles = _service_client_app_roles(client, requested_scopes)
    roles.extend(app_roles)

    claims = {
        "client_id": client.client_id,
        "scope": scope,
        "token_use": "client_credentials",
        "actor_type": "service_account",
        "roles": sorted(set(roles)),
        "is_admin": "admin" in requested_scopes,
        "tier": "community",
        "sub_status": "active",
        # NAMESPACED organization roles, consistent with session and OIDC
        # tokens. A machine principal holds no organization MEMBERSHIP, so the
        # only truthful thing to say about its account authority is what it is:
        # a service account. Application roles go ONLY in `roles`; putting one
        # here would tell a consumer that the janua account granted it, which
        # is exactly the conflation `madfam_org_roles` was namespaced to stop
        # (see `services/org_claims_service.py`, «Why madfam_org_roles and not
        # roles»).
        ORG_ROLES_CLAIM: ["service_account"],
    }

    # Product tier claims (`<product>_tier`) state an entitlement, and
    # downstream tier gates authorize on them. Two sources:
    #
    # - a client registered by a platform admin is MADFAM's own service
    #   account: each product it holds a namespaced scope for gets the
    #   `madfam` tier, so it can reach that product's gated operations
    #   without a human session;
    # - every client bound to an organization gets that organization's
    #   `product_tiers` (applied below, and they win over the above).
    #
    # Any other client gets no tier claim for a product its organization is
    # not entitled to. Consumers read an absent claim as their lowest
    # authenticated tier.
    if scoped_products and await client_registered_by_platform_admin(db, client):
        for product in scoped_products:
            claim_key = re.sub(r"[^a-z0-9_]", "_", str(product).lower())
            if claim_key:
                claims[f"{claim_key}_tier"] = "madfam"

    if client.organization_id:
        org_result = await db.execute(
            select(Organization).where(Organization.id == client.organization_id)
        )
        org = org_result.scalar_one_or_none()
        if org:
            org_id = str(org.id)
            claims.update(
                {
                    "org_id": org_id,
                    "tenant_id": org_id,
                    "org_slug": org.slug,
                    "tier": org.subscription_tier or "community",
                    "product_tiers": org.product_tiers or {},
                }
            )
            for product, product_tier in (org.product_tiers or {}).items():
                claim_key = re.sub(r"[^a-z0-9_]", "_", str(product).lower())
                if claim_key:
                    claims[f"{claim_key}_tier"] = product_tier

    return claims


# ============================================================================
# OAuth2 Authorization Endpoint
# ============================================================================


def _is_silent_auth_allowed(client: OAuthClient) -> bool:
    """`prompt=none` is restricted to first-party clients to prevent surprise
    issuance to third-party apps.

    A client is first-party when it is BOTH `is_active=True` AND `is_confidential=True`
    (i.e. has a registered server-side secret) AND its name does not begin
    with the operator-marker prefix used for tenant-self-service registrations.
    Operators wanting silent-auth for a specific tenant client can opt-in by
    setting `OAuthClient.allowed_scopes` to include `madfam:silent_auth`.

    The implementation is intentionally conservative: silent-auth bypasses
    the visible consent screen, so we err on the side of "no, show the
    interactive flow" when a client has not been explicitly trusted.
    """
    if not client.is_active:
        return False
    if not getattr(client, "is_confidential", False):
        return False
    allowed_scopes = list(client.allowed_scopes or [])
    if SILENT_AUTH_SCOPE in allowed_scopes:
        return True
    # Default-allow for known first-party MADFAM client_ids. The Selva office
    # client is the primary consumer of silent-auth in Phase 1.
    return is_first_party_name(client.name)


def _is_first_party_preconsented(client: OAuthClient) -> bool:
    """First-party clients do not need a visible consent screen (B6).

    Consent exists so a person can refuse a THIRD party access to their Janua
    account. `selva-office*`, `madfam-*`, and any client an operator has
    explicitly marked with `madfam:silent_auth` are surfaces of MADFAM itself:
    asking someone to authorize MADFAM to MADFAM communicates nothing and, on
    the silent path, is not even askable — `prompt=none` cannot render a
    screen, so a missing consent row turns into `consent_required` and the
    silent hop fails for a client that was never going to be refused.

    Deliberately the SAME predicate as `_is_silent_auth_allowed`, not a looser
    one: exactly the clients trusted to skip the consent UI silently are the
    clients treated as pre-consented, so widening one can never quietly widen
    the other. A third-party client is unaffected and still sees the screen.
    """
    return _is_silent_auth_allowed(client)


async def _resolve_held_accounts(
    held_sids: list[str], db: AsyncSession
) -> list[tuple[str, Any]]:
    """Resolve each held `sid` to `(sid, user)`: live sessions only, one per person.

    A `sid` whose row is revoked, expired, or whose user is not active is
    silently omitted — the chooser only ever offers accounts a switch could
    actually front.

    One entry per USER: every sign-in appends a new `sid`, so a person who signed
    in five times holds five live sessions and was listed five times. The entry
    kept is that user's newest live session (by `created_at`; on a tie or an
    undatable row, the later position in `janua_sessions`, which is
    most-recent-last). The list keeps the held order of the sessions kept.
    The held set itself is not pruned here; see `append_sid` for why.
    """
    best: dict[str, tuple[int, str, Any, Any]] = {}
    for position, sid in enumerate(held_sids):
        user, session = await resolve_session_by_id(sid, db)
        if user is None or session is None:
            continue
        key = str(getattr(user, "id", sid))
        current = best.get(key)
        if current is None:
            best[key] = (position, sid, user, session)
            continue
        new_started = _session_started_at(session)
        old_started = _session_started_at(current[3])
        if new_started is not None and old_started is not None and new_started < old_started:
            continue  # the one already kept is newer
        best[key] = (position, sid, user, session)
    kept = sorted(best.values(), key=lambda entry: entry[0])
    return [(sid, user) for _, sid, user, _ in kept]


def _account_chooser_html(
    accounts: list[tuple[str, Any]],
    *,
    authorize_next: str,
    add_account_url: str,
    client_name: str,
) -> str:
    """Render the `prompt=select_account` chooser over the held estate accounts.

    Each account is a form that POSTs its `sid` to `/api/v1/auth/switch-session/form`
    (the form-encoded twin of the JSON `/switch-session`, which answers a plain
    HTML form with 422) with `next` set to the rebuilt authorize URL, so choosing an account re-points
    `janua_sso` and lands back at `/authorize` for that account. "Use another
    account" is a normal interactive login. All user-controlled text is HTML
    escaped (XSS), and only the opaque `sid` and the pre-validated `next` travel
    in the forms — no token, no email in a query string.
    """
    escaped_client = html.escape(client_name or "the application")
    escaped_next = html.escape(authorize_next)
    escaped_add = html.escape(add_account_url)

    rows = ""
    for sid, user in accounts:
        label = getattr(user, "email", None) or getattr(user, "username", None) or "Account"
        display = html.escape(str(label))
        escaped_sid = html.escape(str(sid))
        rows += f"""
        <form method="post" action="/api/v1/auth/switch-session/form" class="account">
            <input type="hidden" name="sid" value="{escaped_sid}">
            <input type="hidden" name="next" value="{escaped_next}">
            <button type="submit" class="account-btn">
                <span class="account-avatar">{display[:1].upper()}</span>
                <span class="account-email">{display}</span>
            </button>
        </form>
        """

    return f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Choose an account - Janua</title>
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh; display: flex; align-items: center;
            justify-content: center; padding: 20px;
        }}
        .chooser {{
            background: white; border-radius: 16px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            padding: 40px; width: 100%; max-width: 420px;
        }}
        h1 {{ font-size: 22px; color: #333; margin-bottom: 6px; text-align: center; }}
        p.sub {{ color: #666; font-size: 14px; margin-bottom: 24px; text-align: center; }}
        .account {{ margin-bottom: 10px; }}
        .account-btn {{
            width: 100%; display: flex; align-items: center; gap: 12px;
            padding: 12px 14px; border: 1px solid #e2e2e2; border-radius: 10px;
            background: #fafafa; cursor: pointer; font-size: 15px; color: #222;
        }}
        .account-btn:hover {{ background: #f0f0ff; border-color: #764ba2; }}
        .account-avatar {{
            width: 34px; height: 34px; border-radius: 50%;
            background: #764ba2; color: white; display: flex;
            align-items: center; justify-content: center; font-weight: 600;
        }}
        .add {{
            display: block; margin-top: 18px; text-align: center;
            color: #764ba2; text-decoration: none; font-size: 14px;
        }}
        .add:hover {{ text-decoration: underline; }}
    </style>
</head>
<body>
    <div class="chooser">
        <h1>Choose an account</h1>
        <p class="sub">to continue to {escaped_client}</p>
        {rows}
        <a class="add" href="{escaped_add}">Use another account</a>
    </div>
</body>
</html>
"""


def _redirect_with_oauth_error(
    redirect_uri: str,
    error: str,
    error_description: str,
    state: Optional[str],
    *,
    client_validated: bool,
) -> RedirectResponse:
    """Build an OAuth-spec-compliant error redirect (`error`, `error_description`,
    optional `state`).

    This is the standard "tell the client we couldn't authenticate silently"
    path for `prompt=none` failures (`error=login_required`,
    `error=consent_required`, etc.). The redirect_uri MUST be already
    validated against the OAuth client's registered URIs before calling this.
    """
    params: dict[str, str] = {
        "error": error,
        "error_description": error_description,
    }
    if state:
        params["state"] = state
    return RedirectResponse(
        url=_build_safe_callback_url(redirect_uri, params, client_validated=client_validated),
        status_code=302,
    )


# ============================================================================
# Protected resources (RFC 8707) — how Claude and Claude Code get MAP tokens
# ============================================================================
#
# A request that names a `resource`, or whose client_id is an https URL (a
# Client ID Metadata Document), takes this path end to end: /authorize, the
# consent POST, /token and /revoke. A request with neither keeps the original
# behavior byte for byte. Registry and client policy:
# app/core/protected_resources.py; CIMD fetching: app/services/client_id_metadata.py;
# tokens: app/services/resource_tokens.py. Rules enforced here:
#
# - exactly one registered resource, else `invalid_target`;
# - the client is a CIMD document from a host on the resource's allowlist, or
#   a client registered in Janua whose redirect URIs are all inside the
#   resource's redirect policy;
# - redirect URIs match exactly, except that a loopback URI matches on any
#   port (RFC 8252 §7.3);
# - response_type=code with PKCE S256 only;
# - consent is asked every time, in Spanish, and never remembered;
# - errors after the redirect URI is trusted go back to it with `error`,
#   `state` and `iss`; errors before that render a page and never redirect.

#: Pre-login state for a resource-bound request outlives the 15-minute magic
#: link that may resume it (the default path keeps 10 minutes).
RESOURCE_PRE_LOGIN_TTL = 20 * 60
#: How long the stored consent request waits for the person's answer.
RESOURCE_AUTH_REQUEST_TTL = 600
#: RFC 7636 §4.2: an S256 challenge is BASE64URL(SHA256(verifier)), 43 chars.
_S256_CHALLENGE = re.compile(r"^[A-Za-z0-9_-]{43}$")
#: RFC 7636 §4.1: the verifier's alphabet and length.
_CODE_VERIFIER = re.compile(r"^[A-Za-z0-9._~-]{43,128}$")

_TOKEN_RESPONSE_HEADERS = {"Cache-Control": "no-store", "Pragma": "no-cache"}

_ERROR_PAGE_MESSAGES = {
    "invalid_client": "La aplicación que pidió el acceso no está autorizada o no se pudo verificar.",
    "invalid_request": "La solicitud de acceso no es válida.",
    "invalid_target": "El recurso solicitado no existe o no está disponible.",
    "unauthorized_client": "Esta aplicación no tiene permiso para pedir acceso a este recurso.",
    "server_error": "No se pudo completar la autorización.",
}


@dataclass(frozen=True)
class _ResourceClient:
    """The client of a resource-bound request, from its CIMD document or its row."""

    client_id: str
    kind: str  # "cimd" | "registered"
    client_name: Optional[str]
    redirect_uris: tuple[str, ...]
    grant_types: frozenset[str]
    cimd_host: Optional[str] = None
    db_client: Optional[OAuthClient] = None

    def app_host(self, redirect_uri: str) -> str:
        """Who is asking, as a host: the client_id host, else the redirect host."""
        return self.cimd_host or redirect_display_host(redirect_uri)


def _resource_values(value: Any) -> list[str]:
    """The `resource` values of a request (RFC 8707 allows repeating it).

    Anything that is not a string or a list of strings — notably FastAPI's own
    `Query(None)` / `Form(None)` default when a route function is called
    directly — means "no resource".
    """
    if isinstance(value, str):
        return [value]
    if isinstance(value, (list, tuple)):
        return [item for item in value if isinstance(item, str)]
    return []


def _select_resource(values: list[str]) -> tuple[Optional[ProtectedResource], Optional[str]]:
    """(the registered resource, None) or (None, why it is `invalid_target`)."""
    if not values:
        return None, "the resource parameter is required for this client"
    canonical: set[str] = set()
    for value in values:
        try:
            canonical.add(canonical_resource(value))
        except InvalidResourceIndicator:
            return None, "the resource must be an absolute URI without a fragment"
    if len(canonical) != 1:
        return None, "exactly one resource per request is supported"
    resource = PROTECTED_RESOURCES.get(next(iter(canonical)))
    if resource is None:
        return None, "unknown resource"
    return resource, None


def _registered_redirect_uris(client: OAuthClient) -> tuple[str, ...]:
    uris = client.redirect_uris or []
    if isinstance(uris, str):
        # Some rows store the array double-encoded (see auth.py's resolvers).
        try:
            uris = json.loads(uris)
        except json.JSONDecodeError:
            uris = []
    if not isinstance(uris, list):
        return ()
    return tuple(uri for uri in uris if isinstance(uri, str))


async def _resolve_resource_client(
    client_id: str, resource: Optional[ProtectedResource], db: AsyncSession
) -> tuple[Optional[_ResourceClient], Optional[str]]:
    """(the client behind `client_id`, None), or (None, why it was refused).

    The reason is for the log only; the person sees a fixed message.

    A URL client_id is fetched as a Client ID Metadata Document only when it is
    one of the resource's pinned client_id URLs (on its host allowlist). With no
    usable resource the union of every resource's pins decides, so the
    `invalid_target` error can still be delivered to a verified redirect URI.
    """
    if is_url_client_id(client_id):
        if resource is not None:
            hosts = resource.client_policy.cimd_hosts
            pinned = resource.client_policy.cimd_client_ids
        else:
            hosts, pinned = all_cimd_hosts(), all_cimd_client_ids()
        try:
            metadata = await resolve_client_metadata(
                client_id, allowed_hosts=hosts, pinned_client_ids=pinned
            )
        except ClientMetadataError as exc:
            return None, exc.description
        return (
            _ResourceClient(
                client_id=metadata.client_id,
                kind="cimd",
                client_name=metadata.client_name,
                redirect_uris=metadata.redirect_uris,
                grant_types=frozenset(metadata.grant_types),
                cimd_host=metadata.host,
            ),
            None,
        )
    client = await _get_oauth_client(client_id, db)
    if not client or not client.is_active:
        return None, "unknown or disabled client"
    return (
        _ResourceClient(
            client_id=client_id,
            kind="registered",
            client_name=client.name,
            redirect_uris=_registered_redirect_uris(client),
            grant_types=frozenset(_client_grant_types(client)),
            db_client=client,
        ),
        None,
    )


def _resource_policy_error(
    resource: ProtectedResource, client: _ResourceClient, redirect_uri: str
) -> Optional[str]:
    """Why `client` may not obtain tokens for `resource` via `redirect_uri`, or None."""
    policy = resource.client_policy
    if client.kind == "cimd":
        if (
            client.cimd_host not in policy.cimd_hosts
            or policy.pinned_client_id(client.client_id) is None
        ):
            return "this client is not allowed to request this resource"
    elif not client.redirect_uris or not all(
        policy.allows_redirect(uri) for uri in client.redirect_uris
    ):
        return "the client's registered redirect URIs are outside this resource's policy"
    if not policy.allows_redirect(redirect_uri):
        return "this redirect URI is not allowed for this resource"
    if "authorization_code" not in client.grant_types:
        return "this client may not use the authorization_code grant"
    return None


def _authorization_error_page(error: str, description: str) -> HTMLResponse:
    """A refusal shown to the person, never redirected (untrusted redirect URI)."""
    message = _ERROR_PAGE_MESSAGES.get(error, _ERROR_PAGE_MESSAGES["server_error"])
    content = f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>No se pudo autorizar - Janua</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
               background: #f4f1ec; color: #1f2933; display: flex; align-items: center;
               justify-content: center; min-height: 100vh; margin: 0; padding: 16px; }}
        main {{ background: #fff; border-radius: 14px; padding: 28px; max-width: 440px;
               box-shadow: 0 12px 40px rgba(31, 41, 51, 0.16); }}
        h1 {{ font-size: 20px; margin: 0 0 12px; }}
        p {{ line-height: 1.5; }}
        code {{ font-size: 12px; color: #52606d; word-break: break-word; }}
    </style>
</head>
<body>
    <main>
        <h1>No se pudo autorizar la conexión</h1>
        <p>{html.escape(message)} Vuelve a la aplicación e inténtalo de nuevo.</p>
        <p><code>{html.escape(error)}: {html.escape(description)}</code></p>
    </main>
</body>
</html>
"""
    return HTMLResponse(content=content, status_code=400, headers={"Cache-Control": "no-store"})


def _login_redirect_for_resource(
    *,
    pre_login_id: str,
    client_id: str,
    app_name: str,
    login_method: Optional[str],
    mfa_required: bool = False,
) -> RedirectResponse:
    params = {"auth_request_id": pre_login_id, "client_id": client_id, "client_name": app_name}
    if login_method:
        params["login_method"] = login_method
    if mfa_required:
        params["mfa_required"] = "1"
    return RedirectResponse(url=f"/api/v1/auth/login?{urlencode(params)}", status_code=302)


async def _authorize_protected_resource(
    *,
    current_user: Optional[User],
    response_type: str,
    client_id: str,
    redirect_uri: str,
    scope: Optional[str],
    state: Optional[str],
    code_challenge: Optional[str],
    code_challenge_method: Optional[str],
    prompt: Optional[str],
    login_method: Optional[str],
    resource_values: list[str],
    db: AsyncSession,
    redis: ResilientRedisClient,
):
    """GET /authorize for a protected resource (see the section comment above).

    `current_user` is who `authorize_get` resolved from the request
    (`get_user_from_cookie_or_header`, the one reader of the session cookies),
    or None.
    """
    resource, resource_error = _select_resource(resource_values)

    # 1. Who is asking, and may the answer go to `redirect_uri`? Until both are
    #    known nothing is redirected (RFC 6749 §4.1.2.1).
    client, refusal = await _resolve_resource_client(client_id, resource, db)
    if client is None:
        logger.warning(
            "oauth.resource_authorize.refused",
            error="invalid_client",
            reason=refusal,
            client_kind="cimd" if is_url_client_id(client_id) else "registered",
        )
        return _authorization_error_page("invalid_client", "the client could not be verified")
    if not redirect_uri_matches(redirect_uri, client.redirect_uris):
        logger.warning(
            "oauth.resource_authorize.refused",
            error="invalid_request",
            reason="redirect_uri_not_registered",
            client_id=client_id,
        )
        return _authorization_error_page(
            "invalid_request", "redirect_uri is not registered for this client"
        )

    def refuse(error: str, description: str) -> RedirectResponse:
        logger.info(
            "oauth.resource_authorize.refused",
            error=error,
            reason=description,
            client_id=client_id,
        )
        return _redirect_with_oauth_error(
            redirect_uri,
            error=error,
            error_description=description,
            state=state,
            client_validated=True,
        )

    # 2. The request itself; errors now go back to the verified redirect URI.
    if resource is None:
        return refuse("invalid_target", resource_error or "unknown resource")
    if response_type != "code":
        return refuse("unsupported_response_type", "only response_type=code is supported")
    policy_error = _resource_policy_error(resource, client, redirect_uri)
    if policy_error:
        return refuse("unauthorized_client", policy_error)
    if not code_challenge:
        return refuse("invalid_request", "PKCE is required: send code_challenge")
    if code_challenge_method != "S256":
        return refuse("invalid_request", "code_challenge_method must be S256")
    if not _S256_CHALLENGE.match(code_challenge):
        return refuse("invalid_request", "code_challenge is not a valid S256 challenge")

    # An absent or empty `scope` asks for the resource's scopes (RFC 6749 §3.3
    # lets the server apply a default); `offline_access` must be asked for.
    requested = scope.split() if scope is not None and scope.strip() else None
    scopes, offline_access = granted_scopes(resource, requested)
    if not scopes:
        return refuse("invalid_scope", "no requested scope is available for this resource")
    if "refresh_token" not in client.grant_types:
        offline_access = False

    prompt_values = {value for value in (prompt or "").strip().lower().split() if value}
    force_login = "login" in prompt_values or "select_account" in prompt_values
    silent = "none" in prompt_values and not force_login

    app_host = client.app_host(redirect_uri)

    async def send_to_login(*, mfa_required: bool = False) -> RedirectResponse:
        pre_login_id = secrets.token_urlsafe(16)
        pre_login_data = {
            "response_type": response_type,
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "scope": scope,
            "state": state,
            "code_challenge": code_challenge,
            "code_challenge_method": code_challenge_method,
            "resource": resource.resource,
            "login_method": normalize_login_method(login_method) or resource.preferred_login_method,
        }
        await redis.strict_set(
            f"oauth:pre_login:{pre_login_id}",
            json.dumps(pre_login_data),
            ex=RESOURCE_PRE_LOGIN_TTL,
        )
        return _login_redirect_for_resource(
            pre_login_id=pre_login_id,
            client_id=client_id,
            app_name=f"{resource.display_name} ({app_host})",
            login_method=pre_login_data["login_method"],
            mfa_required=mfa_required,
        )

    if not current_user or force_login:
        if silent:
            return refuse("login_required", "no active Janua session")
        return await send_to_login()

    # Consent is asked on every request for a resource, so a silent request
    # can never complete.
    if silent:
        return refuse("consent_required", "consent is required for this resource")

    # Same identity gates as the default path: verified email (after the
    # grace period) and, when enforced, a second factor.
    if settings.REQUIRE_EMAIL_VERIFICATION and not getattr(current_user, "email_verified", False):
        created_at = getattr(current_user, "created_at", None)
        if created_at:
            grace = timedelta(hours=settings.EMAIL_VERIFICATION_GRACE_PERIOD_HOURS)
            if datetime.utcnow() >= created_at + grace:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Email verification required. Please verify your email before authorizing third-party applications.",
                )

    from app.auth.mfa_enforcement import mfa_required_for

    if mfa_required_for(current_user):
        return await send_to_login(mfa_required=True)

    # 3. Consent, in Spanish, every time.
    csrf_token = await _generate_csrf_token(str(current_user.id), redis)
    granted = scopes + ([OFFLINE_ACCESS_SCOPE] if offline_access else [])
    auth_request_id = secrets.token_urlsafe(16)
    auth_request_data = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": " ".join(granted),
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
        "resource": resource.resource,
        "user_id": str(current_user.id),
    }
    await redis.strict_set(
        f"oauth:auth_request:{auth_request_id}",
        json.dumps(auth_request_data),
        ex=RESOURCE_AUTH_REQUEST_TTL,
    )
    loopback = is_loopback_redirect(redirect_uri)
    page = render_resource_consent_page(
        resource=resource,
        # A registered client on a loopback redirect has no host worth naming.
        app_host=(
            app_host
            if client.kind == "cimd" or not loopback
            else "Una aplicación en esta computadora"
        ),
        client_name=client.client_name,
        redirect_host=redirect_display_host(redirect_uri),
        loopback=loopback,
        scopes=scopes,
        offline_access=offline_access,
        user_email=getattr(current_user, "email", "") or "",
        auth_request_id=auth_request_id,
        csrf_token=csrf_token,
    )
    return HTMLResponse(content=page, headers={"Cache-Control": "no-store"})


async def _complete_protected_resource_consent(
    *,
    current_user: User,
    auth_request: dict,
    action: str,
    db: AsyncSession,
    redis: ResilientRedisClient,
):
    """POST /consent for a protected resource: re-verify, then code or access_denied."""
    resource = PROTECTED_RESOURCES.get(auth_request.get("resource") or "")
    redirect_uri = auth_request.get("redirect_uri") or ""
    state = auth_request.get("state")
    client_id = auth_request.get("client_id") or ""
    if resource is None:
        return _authorization_error_page("invalid_target", "the resource is no longer available")
    if auth_request.get("user_id") != str(current_user.id):
        return _authorization_error_page(
            "invalid_request", "the signed-in account changed; start the connection again"
        )
    # Defense in depth: the stored request was validated when the page was
    # rendered, but the registry or the client's document may have changed.
    client, refusal = await _resolve_resource_client(client_id, resource, db)
    if client is None:
        logger.warning(
            "oauth.resource_consent.refused", error="invalid_client", reason=refusal
        )
        return _authorization_error_page("invalid_client", "the client could not be verified")
    if not redirect_uri_matches(redirect_uri, client.redirect_uris) or _resource_policy_error(
        resource, client, redirect_uri
    ):
        return _authorization_error_page(
            "unauthorized_client", "the client or its redirect URI is no longer allowed"
        )

    if action != "allow":
        logger.info(
            "oauth.resource_consent.denied",
            client_id=client_id,
            resource=resource.resource,
            user=_redacted(current_user.id),
        )
        return _redirect_with_oauth_error(
            redirect_uri,
            error="access_denied",
            error_description="the user denied the request",
            state=state,
            client_validated=True,
        )

    auth_code = secrets.token_urlsafe(32)
    code_data = {
        "client_id": client_id,
        "user_id": str(current_user.id),
        "redirect_uri": redirect_uri,
        "scope": auth_request.get("scope") or "",
        "resource": resource.resource,
        "nonce": None,
        "code_challenge": auth_request.get("code_challenge"),
        "code_challenge_method": "S256",
        "expires_at": time.time() + AUTH_CODE_TTL,
    }
    await _store_auth_code(auth_code, code_data, redis)

    if client.db_client is not None:
        try:
            client.db_client.last_used_at = datetime.utcnow()
            await db.commit()
        except Exception as e:
            logger.warning("Failed to update client last_used_at", error=str(e))

    logger.info(
        "oauth.resource_consent.granted",
        client_id=client_id,
        resource=resource.resource,
        scopes=code_data["scope"],
        user=_redacted(current_user.id),
    )
    callback_params = {"code": auth_code}
    if state:
        callback_params["state"] = state
    return RedirectResponse(
        url=_build_safe_callback_url(redirect_uri, callback_params, client_validated=True),
        status_code=302,
    )


@router.get("/authorize/resume")
async def authorize_resume(
    auth_request_id: str = Query(..., min_length=8, max_length=64),
    redis: ResilientRedisClient = Depends(get_redis),
):
    """Resume a protected-resource authorization after sign-in by email link.

    The emailed link's destination is stored in a 500-character column, and a
    full authorize URL for a Client ID Metadata Document client with a
    `resource` comes close to that. The link therefore carries only this short
    URL; the authorize parameters stay in the pre-login record, which for
    these requests outlives the link (RESOURCE_PRE_LOGIN_TTL).
    """
    stored = await redis.strict_get(f"oauth:pre_login:{auth_request_id}")
    params: Optional[dict] = None
    if stored:
        try:
            params = json.loads(stored)
        except (json.JSONDecodeError, TypeError):
            params = None
    if not isinstance(params, dict) or not params.get("resource"):
        return _authorization_error_page(
            "invalid_request", "this sign-in request expired; start the connection again"
        )
    return RedirectResponse(
        url=f"/api/v1/oauth/authorize?{urlencode(authorize_query(params))}", status_code=302
    )


@router.get("/authorize")
async def authorize_get(
    request: Request,
    response_type: str = Query(...),
    client_id: str = Query(...),
    redirect_uri: str = Query(...),
    scope: str = Query("openid"),
    state: Optional[str] = Query(None),
    nonce: Optional[str] = Query(None),
    code_challenge: Optional[str] = Query(None),
    code_challenge_method: Optional[str] = Query(None),
    prompt: Optional[str] = Query(
        None,
        description=(
            "OIDC prompt parameter — a space-delimited set. Honored: 'none' "
            "(silent auth: issue a code immediately if a valid Janua session "
            "cookie is present, otherwise redirect with error=login_required); "
            "'login' (force the interactive login form even when the session "
            "cookie is valid — never auto-issue a code); 'select_account' "
            "(render a chooser over the sessions this browser holds; with no held "
            "session it degrades to 'login'). 'none' is mutually exclusive with the others; if "
            "combined, the interactive force wins. Absent: the default "
            "interactive path (reuse a valid session, otherwise show login). "
            "MFA and consent gates are preserved under every value."
        ),
    ),
    login_method: Optional[str] = Query(
        None,
        description=(
            "Which method the hosted login page offers first when the browser "
            "holds no session: 'magic_link' (email a sign-in link) or "
            "'password'. Unknown values are ignored; absent means the "
            "deployment default (HOSTED_LOGIN_DEFAULT_METHOD)."
        ),
    ),
    resource: Optional[List[str]] = Query(
        None,
        description=(
            "RFC 8707 resource indicator: the protected resource (e.g. an MCP "
            "server URL) the token is for. Must name a registered resource; "
            "the access token's `aud` is that URI. Absent: the default flow."
        ),
    ),
    db: AsyncSession = Depends(get_db),
    redis: ResilientRedisClient = Depends(get_redis),
):
    """
    OAuth 2.0 Authorization Endpoint (GET).

    If user is not authenticated, redirect to login page.
    If user is authenticated, show consent screen or auto-approve.

    A request with `resource`, or with an https `client_id` (a Client ID
    Metadata Document), goes through `_authorize_protected_resource` instead:
    registered resources and clients only, PKCE S256, consent every time.

    Authentication is checked, in this order (see
    `get_user_from_cookie_or_header`, which owns the rule):
    - Authorization header (Bearer token)
    - janua_sso cookie (the estate session — preferred over the one below since
      J9, because a stale hosted-login cookie no host in the estate can delete
      must not outrank the login that just happened)
    - janua_access_token cookie (set by the hosted login form)

    OIDC `prompt=none` (silent auth, ADR 2026-05-04-selva-unified-sso):
        - Valid session present → issue code immediately, skip consent UI.
        - No / expired session → redirect back with `error=login_required`.
        - Consent missing → redirect back with `error=consent_required`.
        - Email verification or MFA required → respect those checks; never
          bypass them just because `prompt=none` was requested.
    """
    # Get user from header or cookie (supports browser-based OAuth flow)
    current_user = await get_user_from_cookie_or_header(request, db)

    resource_values = _resource_values(resource)
    if resource_values or is_url_client_id(client_id):
        scope_param = scope
        if isinstance(request, Request) and "scope" not in request.query_params:
            scope_param = None  # omitted: every scope of the resource
        return await _authorize_protected_resource(
            current_user=current_user,
            response_type=response_type,
            client_id=client_id,
            redirect_uri=redirect_uri,
            scope=scope_param,
            state=state,
            code_challenge=code_challenge,
            code_challenge_method=code_challenge_method,
            prompt=prompt,
            login_method=login_method,
            resource_values=resource_values,
            db=db,
            redis=redis,
        )

    # OIDC `prompt` is a space-delimited SET of values, not a single token.
    prompt_values = {p for p in (prompt or "").strip().lower().split() if p}
    silent_auth = "none" in prompt_values
    # `prompt=login` forces re-authentication; `prompt=select_account` asks for an
    # account chooser. select_account renders a chooser over the sessions this
    # browser holds (`janua_sessions`); with no held session it degrades to
    # `login` — the spec-permitted fallback when the AS cannot offer a selection.
    # Either one forces the interactive path even when a valid session cookie is
    # present. `none` is mutually exclusive with these per OIDC; if a client sends
    # `none` with `login`/`select_account`, silent auth is refused below and the
    # force applies, which is the safe (interactive) resolution.
    force_login = ("login" in prompt_values) or ("select_account" in prompt_values)
    wants_chooser = "select_account" in prompt_values
    # If a client illegally combines `none` with `login`/`select_account`, the
    # interactive force wins — never auto-issue a code when re-auth was demanded.
    if force_login:
        silent_auth = False

    # Validate response_type
    if response_type != "code":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="unsupported_response_type: Only 'code' is supported",
        )

    # Validate client
    client = await _get_oauth_client(client_id, db)
    if not client:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="invalid_client: Unknown client_id",
        )

    if not client.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="invalid_client: Client is disabled",
        )

    # SECURITY: Validate redirect_uri against registered URIs (CWE-601 prevention)
    # This MUST happen before ANY redirect to prevent open redirect attacks
    if not _validate_redirect_uri(redirect_uri, client.redirect_uris):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="invalid_redirect_uri: URI not registered for this client",
        )

    # Validate PKCE - SECURITY: Only S256 is allowed (OAuth 2.1 requirement)
    if code_challenge_method and code_challenge_method != "S256":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="invalid_request: Only S256 code_challenge_method is supported",
        )

    # SECURITY: PKCE is required for public (non-confidential) clients
    if not getattr(client, "is_confidential", False) and not code_challenge:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="invalid_request: PKCE (code_challenge) is required for public clients",
        )

    # SECURITY: the requested scope is narrowed to the client's `allowed_scopes`
    # BEFORE it is stored anywhere (pre-login request, consent request, code),
    # matching the client_credentials grant's allowlist. Unlisted scopes are
    # dropped (RFC 6749 §3.3); a request of which nothing is allowed is refused
    # with `invalid_scope`. redirect_uri is validated above, so redirecting the
    # error is safe.
    try:
        scope = _require_grantable_scope(scope, client, grant="authorization_code")
    except ValueError as exc:
        return _redirect_with_oauth_error(
            redirect_uri,
            error="invalid_scope",
            error_description=str(exc),
            state=state,
            client_validated=True,
        )

    # SECURITY: silent-auth (prompt=none) is restricted to pre-registered
    # first-party clients. A third-party app cannot use prompt=none to skip
    # the consent UI even if the user has a Janua session.
    if silent_auth and not _is_silent_auth_allowed(client):
        logger.warning(
            "Rejected prompt=none from non-first-party client",
            client_id=client_id,
            client_name=client.name,
        )
        return _redirect_with_oauth_error(
            redirect_uri,
            error="interaction_required",
            error_description="silent_auth not allowed for this client",
            state=state,
            client_validated=True,
        )

    # If user not authenticated — or re-auth was demanded via prompt=login /
    # prompt=select_account — send the browser through the interactive login form.
    # A forced re-auth must NOT auto-issue a code off a still-valid session cookie;
    # the login form is where the second factor and a fresh credential are proven,
    # so this path preserves the MFA and consent gates (login re-runs them) rather
    # than skipping straight to a code.
    if not current_user or force_login:
        if force_login:
            logger.info(
                "prompt forcing interactive login despite a session",
                prompt_value=(
                    "select_account" if "select_account" in prompt_values else "login"
                ),
                client_id=client_id,
            )
        # OIDC prompt=none: must NOT prompt — return error and let the caller
        # decide whether to fall back to interactive flow. (Unreachable when
        # force_login is set, since that clears silent_auth above.)
        if silent_auth:
            logger.info(
                "prompt=none but no Janua session — emitting login_required",
                client_id=client_id,
            )
            return _redirect_with_oauth_error(
                redirect_uri,
                error="login_required",
                error_description="No active Janua session for silent auth",
                state=state,
                client_validated=True,
            )
        # SECURITY: Store full OAuth parameters in Redis instead of encoding them
        # into the redirect URL. This avoids double-encoding issues with urlencode()
        # that caused redirect loops when the 'next' URL contained query params.
        # Pattern matches the consent flow storage at lines 580-596.
        pre_login_id = secrets.token_urlsafe(16)
        # The client's preferred first method travels with the request: the
        # hosted page reads it from the login URL, and the hosted magic-link
        # form finds the rest of the authorize request under this key.
        requested_login_method = normalize_login_method(login_method)
        pre_login_data = {
            "response_type": response_type,
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "scope": scope,
            "state": state,
            "nonce": nonce,
            "code_challenge": code_challenge,
            "code_challenge_method": code_challenge_method,
            "login_method": requested_login_method,
        }
        # Strict: if Redis cannot hold the request, answer a retryable 503 now
        # rather than send the browser to a login page whose id leads nowhere.
        await redis.strict_set(
            f"oauth:pre_login:{pre_login_id}",
            json.dumps(pre_login_data),
            ex=600,  # 10 minutes TTL
        )

        # Pass only the opaque ID plus display-only params to the login page
        login_param_values = {
            "auth_request_id": pre_login_id,
            "client_id": client_id,
            "client_name": client.name,
        }
        if requested_login_method:
            login_param_values["login_method"] = requested_login_method
        login_params = urlencode(login_param_values)
        login_url = f"/api/v1/auth/login?{login_params}"

        # prompt=select_account: render a chooser over the accounts this browser
        # holds, rather than jumping straight to a login form. With no held
        # account that still lives, fall through to the login form — the
        # spec-permitted degrade. The chooser only lists accounts a switch could
        # actually front (each `sid` re-checked live), and each choice re-points
        # janua_sso then lands back here for that account; "Use another account"
        # is this same login form.
        if wants_chooser:
            held_sids = read_sessions_cookie(request.cookies.get(SESSIONS_COOKIE_NAME))
            accounts = await _resolve_held_accounts(held_sids, db)
            if accounts:
                authorize_params = {
                    "response_type": response_type,
                    "client_id": client_id,
                    "redirect_uri": redirect_uri,
                    "scope": scope,
                }
                for key, value in (
                    ("state", state),
                    ("nonce", nonce),
                    ("code_challenge", code_challenge),
                    ("code_challenge_method", code_challenge_method),
                ):
                    if value is not None:
                        authorize_params[key] = value
                authorize_next = f"/api/v1/oauth/authorize?{urlencode(authorize_params)}"
                return HTMLResponse(
                    content=_account_chooser_html(
                        accounts,
                        authorize_next=authorize_next,
                        add_account_url=login_url,
                        client_name=client.name or "",
                    )
                )

        return RedirectResponse(url=login_url, status_code=302)

    # SECURITY: Require email verification for OAuth authorization
    if settings.REQUIRE_EMAIL_VERIFICATION and not getattr(current_user, "email_verified", False):
        # Check grace period for new accounts
        from datetime import timedelta

        if current_user.created_at:
            grace_period = timedelta(hours=settings.EMAIL_VERIFICATION_GRACE_PERIOD_HOURS)
            grace_deadline = current_user.created_at + grace_period
            if datetime.utcnow() >= grace_deadline:
                # Silent auth must surface this as an OAuth error redirect, not
                # an HTML 403 — the caller can then decide whether to escalate
                # to interactive flow.
                if silent_auth:
                    return _redirect_with_oauth_error(
                        redirect_uri,
                        error="login_required",
                        error_description="email_verification_required",
                        state=state,
                        client_validated=True,
                    )
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Email verification required. Please verify your email before authorizing third-party applications.",
                )

    # SECURITY (2026-08-23): enforce MFA at /authorize. The docstring long claimed
    # "MFA required → respect it; never bypass" but no check existed. Even with the
    # login form now gating MFA, a PRE-EXISTING non-MFA session cookie could sail
    # through here, so /authorize refuses to issue a code for an MFA-enforced user
    # and sends them back through login to complete the second factor. Gated behind
    # MFA_ENFORCE_ON_LOGIN (default OFF): inert until the challenge UI ships; when
    # off, behavior is unchanged. Mirrors the email-verification handling above:
    # silent auth → login_required error redirect; interactive → back to login.
    from app.auth.mfa_enforcement import mfa_required_for

    if mfa_required_for(current_user):
        if silent_auth:
            return _redirect_with_oauth_error(
                redirect_uri,
                error="login_required",
                error_description="mfa_required",
                state=state,
                client_validated=True,
            )
        login_params = urlencode(
            {"client_id": client_id, "client_name": client.name, "mfa_required": "1"}
        )
        return RedirectResponse(url=f"/api/v1/auth/login?{login_params}", status_code=302)

    # Check if user has already consented to all requested scopes
    requested_scopes = ConsentService.parse_scopes(scope)
    has_consent = await ConsentService.has_consent(db, current_user.id, client_id, requested_scopes)

    # B6: first-party surfaces are pre-consented. Without this, the silent path
    # answers consent_required for a client nobody would have been asked about,
    # and the interactive path shows "MADFAM would like access to MADFAM".
    if not has_consent and _is_first_party_preconsented(client):
        logger.info(
            "First-party client pre-consented — skipping consent screen",
            client_id=client_id,
            client_name=client.name,
            user_id=str(current_user.id),
        )
        has_consent = True

    if not has_consent:
        # OIDC prompt=none: never show an interactive consent screen. If the
        # user hasn't pre-consented, signal consent_required to the caller.
        #
        # Since B6 this branch is unreachable on the silent path by
        # construction: `silent_auth` already required
        # `_is_silent_auth_allowed(client)`, and B6 pre-consents exactly those
        # clients. It stays as defense in depth — if the two predicates ever
        # diverge, the spec-correct answer is still emitted rather than a
        # consent screen a silent caller cannot render.
        if silent_auth:
            logger.info(
                "prompt=none but consent missing — emitting consent_required",
                client_id=client_id,
                user_id=str(current_user.id),
            )
            return _redirect_with_oauth_error(
                redirect_uri,
                error="consent_required",
                error_description="User has not consented to requested scopes",
                state=state,
                client_validated=True,
            )
        # Show consent screen
        csrf_token = await _generate_csrf_token(str(current_user.id), redis)
        scope_descriptions = ConsentService.get_scope_descriptions()

        # Build scope list for display
        scope_display = []
        for s in requested_scopes:
            if s in scope_descriptions:
                name, desc = scope_descriptions[s]
                scope_display.append({"scope": s, "name": name, "description": desc})
            else:
                scope_display.append({"scope": s, "name": s, "description": f"Access {s}"})

        # Pre-generate scope items HTML (avoids f-string bracket issues in Python <3.12)
        # SECURITY: All user-controlled content is HTML escaped to prevent XSS
        scope_items_html = ""
        for s in scope_display:
            escaped_name = html.escape(s["name"])
            escaped_desc = html.escape(s["description"])
            scope_items_html += f"""
            <div class="scope-item">
                <svg class="scope-icon" fill="currentColor" viewBox="0 0 20 20">
                    <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd"></path>
                </svg>
                <div class="scope-text">
                    <h4>{escaped_name}</h4>
                    <p>{escaped_desc}</p>
                </div>
            </div>
            """

        # Pre-generate redirect URI display (escaped for XSS protection)
        redirect_display = (
            redirect_uri.split("//")[1].split("/")[0] if "//" in redirect_uri else redirect_uri
        )
        escaped_redirect_display = html.escape(redirect_display)

        # SECURITY: Escape all user-controlled content for the consent HTML
        escaped_client_name = html.escape(client.name or "Unknown Application")
        escaped_user_email = html.escape(current_user.email or "")

        # Store authorization request for POST handler
        auth_request_id = secrets.token_urlsafe(16)
        auth_request_data = {
            "response_type": response_type,
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "scope": scope,
            "state": state,
            "nonce": nonce,
            "code_challenge": code_challenge,
            "code_challenge_method": code_challenge_method,
        }
        # Strict, like the CSRF token above: the consent form is only rendered
        # once both are in Redis, where every replica can read them.
        await redis.strict_set(
            f"oauth:auth_request:{auth_request_id}",
            json.dumps(auth_request_data),
            ex=600,  # 10 minutes
        )

        # The form submits once: a second click (or a double-click) would post
        # the same single-use CSRF token again, and that second response — a 403
        # — is the one the browser shows, although the first one succeeded. The
        # guard is a flag, not `disabled` on the buttons: a disabled submitter
        # drops its `action` value from the form data.
        consent_html = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Authorize {escaped_client_name} - Janua</title>
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }}
        .consent-container {{
            background: white;
            border-radius: 16px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            padding: 40px;
            width: 100%;
            max-width: 450px;
        }}
        .header {{ text-align: center; margin-bottom: 30px; }}
        .header h1 {{ font-size: 24px; color: #333; margin-bottom: 8px; }}
        .header p {{ color: #666; font-size: 14px; }}
        .client-info {{
            background: #f8f9fa;
            border-radius: 12px;
            padding: 20px;
            margin-bottom: 24px;
            text-align: center;
        }}
        .client-name {{ font-size: 18px; font-weight: 600; color: #333; }}
        .client-url {{ font-size: 12px; color: #888; margin-top: 4px; }}
        .scopes-section {{ margin-bottom: 24px; }}
        .scopes-title {{ font-size: 14px; font-weight: 600; color: #333; margin-bottom: 12px; }}
        .scope-item {{
            display: flex;
            align-items: flex-start;
            padding: 12px 0;
            border-bottom: 1px solid #eee;
        }}
        .scope-item:last-child {{ border-bottom: none; }}
        .scope-icon {{ width: 24px; height: 24px; margin-right: 12px; color: #667eea; }}
        .scope-text h4 {{ font-size: 14px; font-weight: 500; color: #333; }}
        .scope-text p {{ font-size: 12px; color: #666; margin-top: 2px; }}
        .user-info {{ font-size: 12px; color: #888; margin-bottom: 20px; text-align: center; }}
        .legal-links {{ text-align: center; margin-bottom: 20px; font-size: 11px; color: #888; }}
        .legal-links a {{ color: #667eea; text-decoration: none; }}
        .legal-links a:hover {{ text-decoration: underline; }}
        .buttons {{ display: flex; gap: 12px; }}
        button {{
            flex: 1;
            padding: 14px;
            border-radius: 8px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            border: none;
        }}
        .btn-allow {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
        }}
        .btn-deny {{
            background: #f1f3f4;
            color: #333;
        }}
        .footer {{ text-align: center; margin-top: 24px; color: #888; font-size: 11px; }}
    </style>
</head>
<body>
    <div class="consent-container">
        <div class="header">
            <h1>&#128274; Authorize Application</h1>
            <p>An application is requesting access to your account</p>
        </div>

        <div class="client-info">
            <div class="client-name">{escaped_client_name}</div>
            <div class="client-url">{escaped_redirect_display}</div>
        </div>

        <div class="scopes-section">
            <div class="scopes-title">This application will be able to:</div>
            {scope_items_html}
        </div>

        <div class="user-info">
            Signed in as <strong>{escaped_user_email}</strong>
        </div>

        <div class="legal-links">
            By allowing, you agree to the
            <a href="https://madfam.io/terms" target="_blank" rel="noopener noreferrer">Terms of Service</a>
            and
            <a href="https://madfam.io/privacy" target="_blank" rel="noopener noreferrer">Privacy Policy</a>.
        </div>

        <form method="POST" action="/api/v1/oauth/consent"
              onsubmit="if (this.dataset.submitted) {{ return false; }} this.dataset.submitted = '1'; return true;">
            <input type="hidden" name="auth_request_id" value="{auth_request_id}">
            <input type="hidden" name="csrf_token" value="{csrf_token}">
            <div class="buttons">
                <button type="submit" name="action" value="deny" class="btn-deny">Deny</button>
                <button type="submit" name="action" value="allow" class="btn-allow">Allow</button>
            </div>
        </form>

        <div class="footer">
            Powered by Janua Identity Platform
        </div>
    </div>
</body>
</html>
"""
        return HTMLResponse(content=consent_html)

    # User has consented - generate authorization code
    auth_code = secrets.token_urlsafe(32)
    code_data = {
        "client_id": client_id,
        "user_id": str(current_user.id),
        "redirect_uri": redirect_uri,
        "scope": scope,
        "nonce": nonce,
        "code_challenge": code_challenge,
        "code_challenge_method": code_challenge_method or "S256",
        "expires_at": time.time() + AUTH_CODE_TTL,
    }
    await _store_auth_code(auth_code, code_data, redis)

    # Update client last_used_at
    client.last_used_at = datetime.utcnow()
    await db.commit()

    # SECURITY: Redirect back to client with authorization code
    # The redirect_uri was validated at the start of this function against the client's registered URIs
    callback_params = {"code": auth_code}
    if state:
        callback_params["state"] = state

    callback_url = _build_safe_callback_url(redirect_uri, callback_params, client_validated=True)
    return RedirectResponse(url=callback_url, status_code=302)


@router.post("/consent")
async def handle_consent(
    request: Request,
    auth_request_id: str = Form(...),
    csrf_token: str = Form(...),
    action: str = Form(...),
    db: AsyncSession = Depends(get_db),
    redis: ResilientRedisClient = Depends(get_redis),
):
    """
    Handle OAuth consent form submission.

    User can either 'allow' or 'deny' the authorization request.
    """
    # Get user from cookie or header (supports browser-based OAuth flow)
    current_user = await get_user_from_cookie_or_header(request, db)
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    # Validate CSRF token
    if not await _validate_csrf_token(csrf_token, str(current_user.id), redis):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid or expired CSRF token",
        )

    # Retrieve stored authorization request (strict, like the CSRF token)
    auth_request_key = f"oauth:auth_request:{auth_request_id}"
    auth_request_json = await redis.strict_get(auth_request_key)

    if not auth_request_json:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Authorization request expired or invalid",
        )

    # Delete the request to prevent replay; only one submit may consume it.
    if await redis.strict_delete(auth_request_key) != 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Authorization request expired or invalid",
        )

    auth_request = json.loads(auth_request_json)
    if auth_request.get("resource"):
        # A protected-resource request: its client may be a CIMD document
        # (no row), its code is bound to the resource, and nothing is stored
        # as remembered consent.
        return await _complete_protected_resource_consent(
            current_user=current_user,
            auth_request=auth_request,
            action=action,
            db=db,
            redis=redis,
        )
    redirect_uri = auth_request["redirect_uri"]
    state = auth_request.get("state")

    # SECURITY: Re-validate redirect_uri from stored request
    # Even though it was validated when stored, defense-in-depth requires re-validation
    client = await _get_oauth_client(auth_request["client_id"], db)
    if not client or not _validate_redirect_uri(redirect_uri, client.redirect_uris):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="invalid_redirect_uri: URI validation failed",
        )

    if action == "deny":
        # User denied the request
        error_params = {"error": "access_denied", "error_description": "User denied the request"}
        if state:
            error_params["state"] = state
        error_url = _build_safe_callback_url(redirect_uri, error_params, client_validated=True)
        return RedirectResponse(url=error_url, status_code=302)

    # User approved - store consent
    client_id = auth_request["client_id"]
    scope = auth_request["scope"]
    requested_scopes = ConsentService.parse_scopes(scope)

    try:
        await ConsentService.grant_consent(
            db=db,
            user_id=current_user.id,
            client_id=client_id,
            scopes=requested_scopes,
        )
    except Exception as e:
        logger.error(
            "Failed to store OAuth consent",
            user_id=str(current_user.id),
            client_id=client_id,
            error=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process consent. Please try again.",
        )

    # Generate authorization code
    auth_code = secrets.token_urlsafe(32)
    code_data = {
        "client_id": client_id,
        "user_id": str(current_user.id),
        "redirect_uri": redirect_uri,
        "scope": scope,
        "nonce": auth_request.get("nonce"),
        "code_challenge": auth_request.get("code_challenge"),
        "code_challenge_method": auth_request.get("code_challenge_method") or "S256",
        "expires_at": time.time() + AUTH_CODE_TTL,
    }
    await _store_auth_code(auth_code, code_data, redis)

    # Update client last_used_at
    try:
        if client:
            client.last_used_at = datetime.utcnow()
            await db.commit()
    except Exception as e:
        # Non-critical — don't fail the consent flow for a timestamp update
        logger.warning("Failed to update client last_used_at", error=str(e))

    # SECURITY: Redirect with code using validated redirect_uri
    callback_params = {"code": auth_code}
    if state:
        callback_params["state"] = state

    callback_url = _build_safe_callback_url(redirect_uri, callback_params, client_validated=True)

    logger.info(
        "OAuth consent granted",
        user_id=str(current_user.id),
        client_id=client_id,
        scopes=list(requested_scopes),
    )

    return RedirectResponse(url=callback_url, status_code=302)


@router.post("/authorize")
async def authorize_post(
    request: Request,
    response_type: str = Form(...),
    client_id: str = Form(...),
    redirect_uri: str = Form(...),
    scope: str = Form("openid"),
    state: Optional[str] = Form(None),
    nonce: Optional[str] = Form(None),
    code_challenge: Optional[str] = Form(None),
    code_challenge_method: Optional[str] = Form(None),
    csrf_token: Optional[str] = Form(None),
    resource: Optional[List[str]] = Form(None),
    db: AsyncSession = Depends(get_db),
    redis: ResilientRedisClient = Depends(get_redis),
    current_user: User = Depends(get_current_user),
):
    """
    OAuth 2.0 Authorization Endpoint (POST).

    Used for form-based authorization (consent submission).
    Requires CSRF token for protection against cross-site request forgery.

    Protected resources (`resource`, or an https `client_id`) are authorized
    through GET /authorize and its consent screen only; this form refuses them
    rather than issue a code that is not bound to the resource.
    """
    if _resource_values(resource) or is_url_client_id(client_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="invalid_request: protected resources are authorized through GET /authorize",
        )
    # SECURITY: Validate CSRF token
    if not csrf_token or not await _validate_csrf_token(csrf_token, str(current_user.id), redis):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid or missing CSRF token",
        )

    # Same validation as GET
    if response_type != "code":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="unsupported_response_type",
        )

    client = await _get_oauth_client(client_id, db)
    if not client or not client.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid_client")

    # SECURITY: Validate redirect_uri against registered URIs (CWE-601 prevention)
    if not _validate_redirect_uri(redirect_uri, client.redirect_uris):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid_redirect_uri")

    # Validate PKCE - SECURITY: Only S256 is allowed (OAuth 2.1 requirement)
    if code_challenge_method and code_challenge_method != "S256":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="invalid_request: Only S256 code_challenge_method is supported",
        )

    # SECURITY: PKCE is required for public (non-confidential) clients
    if not getattr(client, "is_confidential", False) and not code_challenge:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="invalid_request: PKCE (code_challenge) is required for public clients",
        )

    # SECURITY: same scope narrowing as GET /authorize — see there.
    try:
        scope = _require_grantable_scope(scope, client, grant="authorization_code")
    except ValueError as exc:
        return _redirect_with_oauth_error(
            redirect_uri,
            error="invalid_scope",
            error_description=str(exc),
            state=state,
            client_validated=True,
        )

    # SECURITY: Require email verification for OAuth authorization
    if settings.REQUIRE_EMAIL_VERIFICATION and not getattr(current_user, "email_verified", False):
        # Check grace period for new accounts
        from datetime import timedelta

        if current_user.created_at:
            grace_period = timedelta(hours=settings.EMAIL_VERIFICATION_GRACE_PERIOD_HOURS)
            grace_deadline = current_user.created_at + grace_period
            if datetime.utcnow() >= grace_deadline:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Email verification required. Please verify your email before authorizing third-party applications.",
                )

    # Generate authorization code and store in Redis
    auth_code = secrets.token_urlsafe(32)
    code_data = {
        "client_id": client_id,
        "user_id": str(current_user.id),
        "redirect_uri": redirect_uri,
        "scope": scope,
        "nonce": nonce,
        "code_challenge": code_challenge,
        "code_challenge_method": code_challenge_method or "S256",
        "expires_at": time.time() + AUTH_CODE_TTL,
    }
    await _store_auth_code(auth_code, code_data, redis)

    # Update client last_used_at
    client.last_used_at = datetime.utcnow()
    await db.commit()

    # SECURITY: Redirect with code using validated redirect_uri
    callback_params = {"code": auth_code}
    if state:
        callback_params["state"] = state

    callback_url = _build_safe_callback_url(redirect_uri, callback_params, client_validated=True)
    return RedirectResponse(url=callback_url, status_code=302)


# ============================================================================
# OAuth2 Token Endpoint
# ============================================================================


@router.post("/token", response_model=TokenResponse)
async def token(
    request: Request,
    grant_type: str = Form(...),
    code: Optional[str] = Form(None),
    redirect_uri: Optional[str] = Form(None),
    client_id: Optional[str] = Form(None),
    client_secret: Optional[str] = Form(None),
    refresh_token: Optional[str] = Form(None),
    code_verifier: Optional[str] = Form(None),
    scope: Optional[str] = Form(None),
    resource: Optional[List[str]] = Form(None),
    db: AsyncSession = Depends(get_db),
    redis: ResilientRedisClient = Depends(get_redis),
):
    """
    OAuth 2.0 Token Endpoint.

    Exchanges authorization code for tokens or refreshes tokens.

    Supports:
    - authorization_code: Exchange auth code for access/refresh/id tokens
    - refresh_token: Get new access token using refresh token
    - client_credentials: Get short-lived machine tokens for service accounts

    Protected resources (RFC 8707): a request with `resource`, from an https
    `client_id` (CIMD), or presenting a resource refresh token is handled by
    `_token_for_protected_resource` — RFC 6749 error bodies, RFC 9068 access
    tokens with `aud` = the resource, single-use rotating refresh tokens.
    """
    # Handle client authentication (Basic auth or form params)
    auth_header = request.headers.get("Authorization", "")
    used_basic_auth = auth_header.startswith("Basic ")
    if used_basic_auth:
        import base64

        try:
            decoded = base64.b64decode(auth_header[6:]).decode("utf-8")
            client_id, client_secret = decoded.split(":", 1)
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="invalid_client: Invalid Basic auth",
            )

    resource_values = _resource_values(resource)
    if (
        resource_values
        or is_url_client_id(client_id)
        or (
            grant_type == "refresh_token"
            and resource_tokens.looks_like_resource_refresh_token(refresh_token)
        )
    ):
        return await _token_for_protected_resource(
            grant_type=grant_type,
            code=code,
            redirect_uri=redirect_uri,
            client_id=client_id,
            client_secret=client_secret,
            refresh_token=refresh_token,
            code_verifier=code_verifier,
            scope=scope,
            resource_values=resource_values,
            used_basic_auth=used_basic_auth,
            db=db,
            redis=redis,
        )

    if not client_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="invalid_request: client_id required",
        )

    # Validate client
    client = await _get_oauth_client(client_id, db)
    if not client:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid_client: Unknown client",
        )

    if not client.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid_client: Client disabled",
        )

    # Verify client secret for confidential clients
    if client.is_confidential:
        if not client_secret:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="invalid_client: client_secret required",
            )
        if not client.verify_secret(client_secret):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="invalid_client: Invalid client_secret",
            )

    allowed_grants = _client_grant_types(client)
    if grant_type not in allowed_grants:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"unauthorized_client: Grant type not allowed: {grant_type}",
        )

    # Handle grant types
    if grant_type == "authorization_code":
        return await _handle_authorization_code_grant(
            code=code,
            redirect_uri=redirect_uri,
            client=client,
            code_verifier=code_verifier,
            db=db,
            redis=redis,
        )
    elif grant_type == "refresh_token":
        return await _handle_refresh_token_grant(
            refresh_token=refresh_token,
            client=client,
            db=db,
            redis=redis,
        )
    elif grant_type == "client_credentials":
        return await _handle_client_credentials_grant(
            client=client,
            requested_scope=scope,
            db=db,
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"unsupported_grant_type: {grant_type}",
        )


# ----------------------------------------------------------------------------
# Token endpoint for protected resources
# ----------------------------------------------------------------------------


@dataclass(frozen=True)
class _TokenClient:
    """An authenticated (or, for a public client, identified) token-endpoint client."""

    client_id: str
    kind: str  # "cimd" | "registered"
    grant_types: frozenset[str]
    cimd_host: Optional[str] = None
    db_client: Optional[OAuthClient] = None


def _oauth_token_error(
    error: str, description: str, status_code: int = 400, *, basic_auth: bool = False
) -> JSONResponse:
    """An RFC 6749 §5.2 error: `{"error", "error_description"}`, never cached.

    Clients act on the `error` code itself — Claude, for one, starts a new
    authorization only when a refresh answers `invalid_grant` — so this path
    never uses Janua's general error envelope.
    """
    headers = dict(_TOKEN_RESPONSE_HEADERS)
    if status_code == 401 and basic_auth:
        headers["WWW-Authenticate"] = 'Basic realm="janua"'
    return JSONResponse(
        status_code=status_code,
        content={"error": error, "error_description": description},
        headers=headers,
    )


def _pinned_cimd_client_id(client_id: Optional[str]) -> Optional[str]:
    """The pinned CIMD client_id (a registry string) equal to `client_id`, or None."""
    for pinned in sorted(all_cimd_client_ids()):
        if pinned == client_id:
            return pinned
    return None


def _cimd_client_allowed(resource: ProtectedResource, client: "_TokenClient") -> bool:
    policy = resource.client_policy
    return (
        client.cimd_host in policy.cimd_hosts
        and policy.pinned_client_id(client.client_id) is not None
    )


def _token_client_from_row(client: OAuthClient) -> _TokenClient:
    return _TokenClient(
        client_id=client.client_id,
        kind="registered",
        grant_types=frozenset(_client_grant_types(client)),
        db_client=client,
    )


async def _authenticate_resource_token_client(
    client_id: Optional[str],
    client_secret: Optional[str],
    used_basic_auth: bool,
    db: AsyncSession,
) -> tuple[Optional[_TokenClient], Optional[JSONResponse]]:
    """(client, None) or (None, the RFC 6749 error response)."""
    if not client_id:
        return None, _oauth_token_error("invalid_request", "client_id is required")
    if is_url_client_id(client_id):
        pinned = _pinned_cimd_client_id(client_id)
        if pinned is None:
            return None, _oauth_token_error(
                "invalid_client", "this client is not allowed at this server", 401
            )
        if client_secret or used_basic_auth:
            # Its document says token_endpoint_auth_method "none": PKCE only.
            return None, _oauth_token_error(
                "invalid_client",
                "this client authenticates with PKCE only",
                401,
                basic_auth=used_basic_auth,
            )
        return (
            _TokenClient(
                client_id=pinned,
                kind="cimd",
                grant_types=frozenset({"authorization_code", "refresh_token"}),
                cimd_host=client_id_host(pinned),
            ),
            None,
        )

    client = await _get_oauth_client(client_id, db)
    if not client or not client.is_active:
        return None, _oauth_token_error(
            "invalid_client", "unknown or disabled client", 401, basic_auth=used_basic_auth
        )
    if client.is_confidential and (not client_secret or not client.verify_secret(client_secret)):
        return None, _oauth_token_error(
            "invalid_client", "client authentication failed", 401, basic_auth=used_basic_auth
        )
    return _token_client_from_row(client), None


async def _active_user(user_id: Any, db: AsyncSession) -> Optional[User]:
    """The ACTIVE user with this id, else None.

    Only a malformed id is "no user"; a database failure propagates (a 5xx the
    client retries), never `invalid_grant`, which would make Claude discard a
    good refresh token.
    """
    try:
        user_uuid = uuid.UUID(str(user_id))
    except (TypeError, ValueError):
        return None
    result = await db.execute(select(User).where(User.id == user_uuid))
    user = result.scalar_one_or_none()
    if user is None or getattr(user, "status", None) != UserStatus.ACTIVE:
        return None
    if getattr(user, "is_active", True) is False:
        return None
    return user


def _resource_token_response(
    *,
    resource: ProtectedResource,
    subject: str,
    client: _TokenClient,
    access_scopes: list[str],
    refresh_token: Optional[str],
    grant_type: str,
) -> JSONResponse:
    access = resource_tokens.mint_access_token(
        resource=resource,
        subject=subject,
        client_id=client.client_id,
        scopes=access_scopes,
    )
    response_scope = access_scopes + ([OFFLINE_ACCESS_SCOPE] if refresh_token else [])
    body: dict[str, Any] = {
        "access_token": access.token,
        "token_type": "Bearer",
        "expires_in": access.expires_in,
        "scope": " ".join(response_scope),
    }
    if refresh_token:
        body["refresh_token"] = refresh_token
    logger.info(
        "oauth.resource_token.issued",
        grant_type=grant_type,
        client_id=client.client_id,
        resource=resource.resource,
        scopes=" ".join(access_scopes),
        refresh_token_issued=bool(refresh_token),
        user=_redacted(subject),
    )
    return JSONResponse(content=body, headers=dict(_TOKEN_RESPONSE_HEADERS))


def _requested_resource_mismatch(
    resource_values: list[str], bound: ProtectedResource
) -> Optional[JSONResponse]:
    """`invalid_target` unless the request names nothing, or exactly `bound`."""
    if not resource_values:
        return None
    requested, error = _select_resource(resource_values)
    if requested is None:
        return _oauth_token_error("invalid_target", error or "unknown resource")
    if requested.resource != bound.resource:
        return _oauth_token_error(
            "invalid_target", "the resource does not match the one this grant was issued for"
        )
    return None


async def _exchange_resource_code(
    *,
    code: str,
    code_data: dict,
    redirect_uri: Optional[str],
    code_verifier: Optional[str],
    client: _TokenClient,
    resource_values: list[str],
    db: AsyncSession,
    redis: ResilientRedisClient,
) -> JSONResponse:
    """authorization_code for a code bound to a protected resource."""
    if code_data.get("client_id") != client.client_id:
        logger.warning("token.rejected", reason="client_mismatch", client_id=client.client_id)
        return _oauth_token_error("invalid_grant", "the code was not issued to this client")
    resource = PROTECTED_RESOURCES.get(code_data.get("resource") or "")
    if resource is None:
        return _oauth_token_error("invalid_grant", "the code's resource is no longer available")
    mismatch = _requested_resource_mismatch(resource_values, resource)
    if mismatch is not None:
        return mismatch
    if client.kind == "cimd" and not _cimd_client_allowed(resource, client):
        return _oauth_token_error(
            "unauthorized_client", "this client may not obtain tokens for this resource"
        )
    if "authorization_code" not in client.grant_types:
        return _oauth_token_error("unauthorized_client", "grant type not allowed for this client")
    if redirect_uri is not None and redirect_uri != code_data.get("redirect_uri"):
        logger.warning("token.rejected", reason="redirect_uri_mismatch", client_id=client.client_id)
        return _oauth_token_error("invalid_grant", "redirect_uri does not match the authorization")
    challenge = code_data.get("code_challenge")
    if not challenge or code_data.get("code_challenge_method") != "S256":
        return _oauth_token_error("invalid_grant", "the code was not issued with PKCE S256")
    if not code_verifier:
        return _oauth_token_error("invalid_request", "code_verifier is required")
    if not _CODE_VERIFIER.match(code_verifier) or not _verify_pkce(
        code_verifier, challenge, "S256"
    ):
        logger.warning("token.rejected", reason="pkce_mismatch", client_id=client.client_id)
        return _oauth_token_error("invalid_grant", "PKCE verification failed")

    # Single use: of two concurrent redemptions exactly one deletes the code.
    if not await _delete_auth_code(code, redis):
        logger.warning("token.rejected", reason="code_already_redeemed", client_id=client.client_id)
        return _oauth_token_error("invalid_grant", "the code is invalid or was already used")

    user = await _active_user(code_data.get("user_id"), db)
    if user is None:
        return _oauth_token_error("invalid_grant", "the account is not active")

    granted = (code_data.get("scope") or "").split()
    access_scopes = [scope for scope in granted if scope in resource.scope_names]
    if not access_scopes:
        return _oauth_token_error("invalid_scope", "no scope of this resource was granted")

    refresh_token = None
    if OFFLINE_ACCESS_SCOPE in granted and "refresh_token" in client.grant_types:
        refresh_token = resource_tokens.mint_refresh_token(
            resource=resource,
            subject=str(user.id),
            client_id=client.client_id,
            scope=" ".join(access_scopes + [OFFLINE_ACCESS_SCOPE]),
        )

    if client.db_client is not None:
        client.db_client.last_used_at = datetime.utcnow()
        try:
            await db.commit()
        except Exception as e:
            logger.warning("Failed to update client last_used_at", error=str(e))

    return _resource_token_response(
        resource=resource,
        subject=str(user.id),
        client=client,
        access_scopes=access_scopes,
        refresh_token=refresh_token,
        grant_type="authorization_code",
    )


async def _refresh_resource_token(
    *,
    refresh_token: Optional[str],
    scope: Optional[str],
    client: _TokenClient,
    resource_values: list[str],
    db: AsyncSession,
    redis: ResilientRedisClient,
) -> JSONResponse:
    """refresh_token for a resource refresh token: rotate, detect reuse, never upscope."""
    if not refresh_token:
        return _oauth_token_error("invalid_request", "refresh_token is required")
    claims = resource_tokens.verify_refresh_token(refresh_token)
    if claims is None:
        return _oauth_token_error("invalid_grant", "the refresh token is invalid or expired")
    if claims["client_id"] != client.client_id:
        logger.warning(
            "token.rejected", reason="refresh_client_mismatch", client_id=client.client_id
        )
        return _oauth_token_error(
            "invalid_grant", "the refresh token was not issued to this client"
        )
    resource = PROTECTED_RESOURCES.get(claims["resource"])
    if resource is None:
        return _oauth_token_error("invalid_grant", "the token's resource is no longer available")
    mismatch = _requested_resource_mismatch(resource_values, resource)
    if mismatch is not None:
        return mismatch
    if client.kind == "cimd" and not _cimd_client_allowed(resource, client):
        return _oauth_token_error("invalid_grant", "this client may no longer use this resource")
    if "refresh_token" not in client.grant_types:
        return _oauth_token_error("unauthorized_client", "grant type not allowed for this client")

    # Revoked through POST /oauth/revoke, or a family closed by reuse? Strict
    # read: 503 when Redis cannot answer, never "not revoked".
    if await token_revocation.is_revoked(redis, claims, "refresh"):
        return _oauth_token_error("invalid_grant", "the refresh token was revoked")

    original = claims["scope"].split()
    current_scopes = [name for name in original if name in resource.scope_names]
    if scope is not None and scope.strip():
        requested = scope.split()
        if not set(requested) <= set(original):
            return _oauth_token_error("invalid_scope", "a refresh cannot add scopes")
        access_scopes = [name for name in current_scopes if name in requested]
    else:
        access_scopes = current_scopes
    if not access_scopes:
        return _oauth_token_error("invalid_scope", "no scope of this resource remains")

    user = await _active_user(claims["sub"], db)
    if user is None:
        return _oauth_token_error("invalid_grant", "the account is not active")

    # Single use. The first redemption wins the SET NX; any later one is reuse
    # of a rotated token, so the whole family is revoked.
    first_use = await redis.strict_set_nx(
        f"{resource_tokens.USED_REFRESH_KEY_PREFIX}{claims['jti']}",
        "1",
        ex=token_revocation.seconds_until(claims.get("exp"), resource.refresh_token_idle_seconds),
    )
    if not first_use:
        await token_revocation.revoke_family(
            redis,
            claims["family"],
            ttl=resource.refresh_token_idle_seconds,
            reason="resource_refresh_token_reuse",
            strict=True,
        )
        logger.warning(
            "oauth.resource_refresh.reuse_detected",
            client_id=client.client_id,
            resource=resource.resource,
            user=_redacted(claims["sub"]),
        )
        return _oauth_token_error("invalid_grant", "the refresh token was already used")

    # The new refresh token keeps the original scope (RFC 6749 §6) and family.
    new_refresh_token = resource_tokens.mint_refresh_token(
        resource=resource,
        subject=str(user.id),
        client_id=client.client_id,
        scope=claims["scope"],
        family=claims["family"],
        family_iat=claims["family_iat"],
    )
    return _resource_token_response(
        resource=resource,
        subject=str(user.id),
        client=client,
        access_scopes=access_scopes,
        refresh_token=new_refresh_token,
        grant_type="refresh_token",
    )


async def _token_for_protected_resource(
    *,
    grant_type: str,
    code: Optional[str],
    redirect_uri: Optional[str],
    client_id: Optional[str],
    client_secret: Optional[str],
    refresh_token: Optional[str],
    code_verifier: Optional[str],
    scope: Optional[str],
    resource_values: list[str],
    used_basic_auth: bool,
    db: AsyncSession,
    redis: ResilientRedisClient,
) -> JSONResponse:
    client, error = await _authenticate_resource_token_client(
        client_id, client_secret, used_basic_auth, db
    )
    if client is None:
        return error or _oauth_token_error("invalid_client", "client authentication failed", 401)

    if grant_type == "authorization_code":
        if not code:
            return _oauth_token_error("invalid_request", "code is required")
        code_data = await _get_auth_code(code, redis)
        if not code_data:
            return _oauth_token_error("invalid_grant", "the code is invalid or expired")
        if not code_data.get("resource"):
            # RFC 8707: a grant made without a resource cannot become one.
            return _oauth_token_error(
                "invalid_target", "this code was not issued for a protected resource"
            )
        return await _exchange_resource_code(
            code=code,
            code_data=code_data,
            redirect_uri=redirect_uri,
            code_verifier=code_verifier,
            client=client,
            resource_values=resource_values,
            db=db,
            redis=redis,
        )
    if grant_type == "refresh_token":
        if refresh_token and not resource_tokens.looks_like_resource_refresh_token(refresh_token):
            # Garbage, or a refresh token of the default flow (which names no
            # resource and can never become a resource token): either way the
            # grant is unusable here, and `invalid_grant` is what tells a
            # client like Claude to authorize again.
            return _oauth_token_error(
                "invalid_grant", "the refresh token is invalid for this resource"
            )
        return await _refresh_resource_token(
            refresh_token=refresh_token,
            scope=scope,
            client=client,
            resource_values=resource_values,
            db=db,
            redis=redis,
        )
    if grant_type == "client_credentials":
        return _oauth_token_error(
            "invalid_target", "client_credentials tokens are not issued for protected resources"
        )
    return _oauth_token_error("unsupported_grant_type", f"unsupported grant type: {grant_type}")


async def _audit_service_token_app_roles(
    client: OAuthClient,
    claims: dict,
    db: AsyncSession,
) -> None:
    """Record that a machine token was minted carrying application roles.

    Only fires when the token ACTUALLY carries app roles, so an ordinary
    service token writes no row and its mint cost is unchanged. A machine
    reading payroll is the case worth a durable record: `allowed_scopes` says
    what a client MAY ask for, and this says what it DID ask for, and when.

    Never records the client secret — only the public `client_id`, the org the
    token is scoped to, and the role strings themselves.

    Best-effort and staged on the caller's transaction, matching
    `internal_app_roles._audit`: a failure in the trail must not refuse a token
    the client is entitled to. The `allowed_scopes` grant is the durable record
    of the authority itself, so this row is evidence of USE, not of the grant.
    """
    app_roles = _service_client_app_roles(client, set((claims.get("scope") or "").split()))
    if not app_roles:
        return

    try:
        audit_logger = AuditLogger(db)
        await audit_logger.log(
            event_type=AuditEventType.SERVICE_TOKEN_APP_ROLES,
            tenant_id=str(client.organization_id),
            identity_id=None,
            organization_id=str(client.organization_id),
            resource_type="oauth_client",
            resource_id=str(client.id),
            details={
                "via": "oauth.token.client_credentials",
                "client_id": client.client_id,
                "org_id": str(client.organization_id),
                "app_roles": app_roles,
            },
            severity="info",
        )
    except Exception:
        # Deliberately swallowed. See the docstring: the token is the caller's
        # entitlement, not this row's.
        pass


async def _handle_client_credentials_grant(
    client: OAuthClient,
    requested_scope: Optional[str],
    db: AsyncSession,
) -> TokenResponse:
    """Handle client_credentials grant type for machine/service identities."""
    if not getattr(client, "is_confidential", False):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid_client: client_credentials requires a confidential client",
        )

    scope = _parse_requested_scopes(requested_scope, client)
    client_audience = client.audience or settings.JWT_AUDIENCE
    additional_claims = await _get_client_credentials_claims(client, scope, db)
    additional_claims["aud"] = client_audience
    # Override the default (human-session) access-token TTL so the token's
    # actual `exp` matches the `expires_in` we advertise below.
    additional_claims["exp"] = datetime.utcnow() + timedelta(seconds=SERVICE_TOKEN_TTL_SECONDS)

    access_token, _, _ = jwt_manager.create_access_token(
        user_id=f"service-account:{client.client_id}",
        email=_service_account_email(client),
        additional_claims=additional_claims,
    )

    client.last_used_at = datetime.utcnow()

    await _audit_service_token_app_roles(client, additional_claims, db)

    await db.commit()

    return TokenResponse(
        access_token=access_token,
        token_type="Bearer",
        expires_in=SERVICE_TOKEN_TTL_SECONDS,
        refresh_token=None,
        id_token=None,
        scope=scope,
    )


async def _handle_authorization_code_grant(
    code: Optional[str],
    redirect_uri: Optional[str],
    client: OAuthClient,
    code_verifier: Optional[str],
    db: AsyncSession,
    redis: ResilientRedisClient,
) -> TokenResponse:
    """Handle authorization_code grant type."""
    if not code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="invalid_request: code required",
        )

    # Validate authorization code from Redis
    code_data = await _get_auth_code(code, redis)
    if not code_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="invalid_grant: Code not found or expired",
        )

    if code_data.get("resource"):
        # A code bound to a protected resource only ever yields a token for
        # that resource, even when the token request omits `resource`
        # (RFC 8707 §2.2 allows that).
        return await _exchange_resource_code(
            code=code,
            code_data=code_data,
            redirect_uri=redirect_uri,
            code_verifier=code_verifier,
            client=_token_client_from_row(client),
            resource_values=[],
            db=db,
            redis=redis,
        )

    # Validate client matches
    if code_data["client_id"] != client.client_id:
        logger.warning(
            "token.rejected",
            reason="client_mismatch",
            client_id=client.client_id,
            code_client_id=code_data["client_id"],
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="invalid_grant: Code was not issued to this client",
        )

    # Validate redirect_uri matches
    if redirect_uri and code_data["redirect_uri"] != redirect_uri:
        logger.warning(
            "token.rejected",
            reason="redirect_uri_mismatch",
            client_id=client.client_id,
            presented=redirect_uri,
            issued_for=code_data["redirect_uri"],
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="invalid_grant: redirect_uri mismatch",
        )

    # SECURITY: PKCE is required for public clients (OAuth 2.1 requirement)
    # Verify PKCE if code_challenge was provided during authorization
    if code_data.get("code_challenge"):
        if not code_verifier:
            logger.warning(
                "token.rejected",
                reason="code_verifier_missing",
                client_id=client.client_id,
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="invalid_request: code_verifier required",
            )
        if not _verify_pkce(
            code_verifier,
            code_data["code_challenge"],
            code_data.get("code_challenge_method", "S256"),
        ):
            # The client's verifier belongs to a different authorize request
            # than the one that issued this code. Logging the challenge (a
            # public, single-use hash — never the verifier) is what makes that
            # diagnosable; without it a 400 here is indistinguishable from
            # every other 400 and costs hours to chase.
            logger.warning(
                "token.rejected",
                reason="pkce_mismatch",
                client_id=client.client_id,
                issued_challenge=code_data["code_challenge"],
                method=code_data.get("code_challenge_method", "S256"),
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="invalid_grant: PKCE verification failed",
            )
    elif not getattr(client, "is_confidential", False):
        # Public client without PKCE - this should have been caught at authorization
        # but provide defense-in-depth
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="invalid_request: PKCE is required for public clients",
        )

    # Delete the code (single use). Losing this race means another request
    # redeemed the same code first: refuse, as for any reused code.
    if not await _delete_auth_code(code, redis):
        logger.warning(
            "token.rejected",
            reason="code_already_redeemed",
            client_id=client.client_id,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="invalid_grant: Code not found or expired",
        )

    # Get user
    user_id = code_data["user_id"]
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="invalid_grant: User not found",
        )

    # Fetch user entitlements for Galaxy ecosystem (tier, roles, sub_status)
    entitlements = await _get_user_entitlements(user, db)

    # Per-product MADFAM ecosystem grants (Selva-unified SSO Phase 1).
    # Sourced from the user_entitlements table + org inheritance + admin
    # bootstrap. See app/services/entitlements_service.py.
    madfam_entitled_products = entitlements_to_claim(await get_user_entitlements(user, db))

    # Organization claims for org-scoped resource servers (symbiosis-hcm etc.);
    # unambiguous org_id or none — see _get_user_org_claims.
    org_claims = await _get_user_org_claims(user, db)

    # APPLICATION roles (`hcm:hr` and friends) are UNIONED onto the legacy
    # organization-role list rather than replacing it: `roles` has been an OIDC
    # claim for years and existing clients still read it, so nothing is removed
    # — they gain the namespaced application roles alongside what they had.
    # This merge must happen BEFORE the spread below, because `**org_claims`
    # lands AFTER `"roles": entitlements["roles"]` in the dict literal: an
    # unmerged `roles` key would silently clobber the legacy claim by ordering
    # alone. The shared helper also pops the resolver's private transport key,
    # so it can never reach a token.
    org_claims = merge_app_roles_into_claims(
        org_claims, existing_roles=entitlements["roles"]
    )

    # Resolve per-client audience (falls back to global JWT_AUDIENCE)
    client_audience = client.audience or settings.JWT_AUDIENCE

    # Generate tokens with enriched claims.
    # SECURITY (defence in depth): re-narrow the code's scope to the client's
    # CURRENT `allowed_scopes`. /authorize already narrowed it, but the grant may
    # have shrunk in the (up to AUTH_CODE_TTL) window since, and a code minted
    # before this check existed carries whatever was requested.
    try:
        scope = _require_grantable_scope(code_data.get("scope"), client, grant="authorization_code")
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    access_token, _, _ = jwt_manager.create_access_token(
        user_id=str(user.id),
        email=user.email,
        additional_claims={
            "client_id": client.client_id,
            "aud": client_audience,
            "scope": scope,
            # Galaxy membership claims
            "tier": entitlements["tier"],
            # Legacy organization roles. When the user holds application-role
            # grants, `**org_claims` below overrides this key with the UNION of
            # both lists (see the merge above) — a superset, never a removal.
            "roles": entitlements["roles"],
            "sub_status": entitlements["sub_status"],
            "is_admin": entitlements["is_admin"],
            # MADFAM ecosystem per-product entitlements
            "madfam_entitled_products": madfam_entitled_products,
            # Organization membership claims (orgs always when member of any;
            # org_id/tenant_id/org_slug only when unambiguous). Includes the
            # NAMESPACED `madfam_org_roles` — see org_claims_service for why
            # org roles must not reach a consumer as a bare `roles` list.
            **org_claims,
            # `is_service_account: true` only for technical logins; absent for
            # people, so a person's token shape is unchanged.
            **service_principal_claims(user),
            # PostgREST/data-API shaping — ONLY when the client opted into the
            # `data-api` scope; a no-op otherwise (see _data_api_claims).
            **_data_api_claims(scope, client, org_claims),
        },
    )

    # The refresh token carries the GRANTED (already narrowed) scope, so a
    # refresh re-issues what the person approved instead of falling back to
    # `openid`. The refresh grant re-narrows it to the client's allowed_scopes.
    refresh_token, _, _, _ = jwt_manager.create_refresh_token(
        user_id=str(user.id),
        additional_claims={
            "client_id": client.client_id,
            "aud": client_audience,
            "scope": scope,
        },
    )

    # Generate ID token if openid scope requested
    id_token = None
    if "openid" in scope:
        id_token = _generate_id_token(
            user=user,
            client_id=client.client_id,
            nonce=code_data.get("nonce"),
            access_token=access_token,
        )

    # Update client last_used_at
    client.last_used_at = datetime.utcnow()
    await db.commit()

    return TokenResponse(
        access_token=access_token,
        token_type="Bearer",
        expires_in=3600,  # 1 hour
        refresh_token=refresh_token,
        id_token=id_token,
        scope=scope,
    )


async def _handle_refresh_token_grant(
    refresh_token: Optional[str],
    client: OAuthClient,
    db: AsyncSession,
    redis: Optional[ResilientRedisClient] = None,
) -> TokenResponse:
    """Handle refresh_token grant type.

    A refresh token revoked through `POST /oauth/revoke` (its JTI or its
    rotation family) is refused with `invalid_grant`. The revocation read is
    strict: when Redis cannot answer, this raises `RedisUnavailableError`
    (503 + Retry-After) rather than minting tokens from a possibly revoked grant.
    """
    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="invalid_request: refresh_token required",
        )

    # Verify refresh token
    try:
        payload = await _verify_oauth_token(
            refresh_token,
            token_type="refresh",
            db=db,
            expected_client=client,
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="invalid_grant: Invalid refresh token",
        )
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="invalid_grant: Invalid refresh token",
        )

    # Validate client matches
    if payload.get("client_id") != client.client_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="invalid_grant: Token was not issued to this client",
        )

    # Revoked through POST /oauth/revoke (this token or its family)?
    if await token_revocation.is_revoked(redis or await get_redis(), payload, "refresh"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="invalid_grant: Invalid refresh token",
        )

    # Get user
    user_id = payload.get("sub")
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="invalid_grant: User not found",
        )

    # Fetch user entitlements for Galaxy ecosystem (tier, roles, sub_status)
    entitlements = await _get_user_entitlements(user, db)

    # Per-product MADFAM ecosystem grants (Selva-unified SSO Phase 1).
    madfam_entitled_products = entitlements_to_claim(await get_user_entitlements(user, db))

    # Organization claims for org-scoped resource servers (symbiosis-hcm etc.);
    # unambiguous org_id or none — see _get_user_org_claims.
    org_claims = await _get_user_org_claims(user, db)

    # APPLICATION roles (`hcm:hr` and friends) are UNIONED onto the legacy
    # organization-role list rather than replacing it: `roles` has been an OIDC
    # claim for years and existing clients still read it, so nothing is removed
    # — they gain the namespaced application roles alongside what they had.
    # This merge must happen BEFORE the spread below, because `**org_claims`
    # lands AFTER `"roles": entitlements["roles"]` in the dict literal: an
    # unmerged `roles` key would silently clobber the legacy claim by ordering
    # alone. The shared helper also pops the resolver's private transport key,
    # so it can never reach a token.
    org_claims = merge_app_roles_into_claims(
        org_claims, existing_roles=entitlements["roles"]
    )

    # Resolve per-client audience (falls back to global JWT_AUDIENCE)
    client_audience = client.audience or settings.JWT_AUDIENCE

    # Generate new access token with enriched claims.
    # A refresh can never WIDEN the grant: the scope comes only from the signed
    # refresh token (the `scope` form parameter is not read for this grant), and
    # it is re-narrowed to the client's CURRENT `allowed_scopes`, so a scope
    # removed from the client stops being re-issued at the next refresh.
    # Refresh tokens minted at code exchange carry the granted scope. One that
    # carries none was minted before that existed: it falls back to `openid`,
    # which the rotated token then carries, until the person signs in again.
    try:
        scope = _require_grantable_scope(
            payload.get("scope", "openid"), client, grant="refresh_token"
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    access_token, _, _ = jwt_manager.create_access_token(
        user_id=str(user.id),
        email=user.email,
        additional_claims={
            "client_id": client.client_id,
            "aud": client_audience,
            "scope": scope,
            # Galaxy membership claims
            "tier": entitlements["tier"],
            # Legacy organization roles. When the user holds application-role
            # grants, `**org_claims` below overrides this key with the UNION of
            # both lists (see the merge above) — a superset, never a removal.
            "roles": entitlements["roles"],
            "sub_status": entitlements["sub_status"],
            "is_admin": entitlements["is_admin"],
            # MADFAM ecosystem per-product entitlements
            "madfam_entitled_products": madfam_entitled_products,
            # Organization membership claims (orgs always when member of any;
            # org_id/tenant_id/org_slug only when unambiguous). Includes the
            # NAMESPACED `madfam_org_roles` — see org_claims_service for why
            # org roles must not reach a consumer as a bare `roles` list.
            **org_claims,
            # `is_service_account: true` only for technical logins; absent for
            # people, so a person's token shape is unchanged.
            **service_principal_claims(user),
            # PostgREST/data-API shaping — ONLY when the client opted into the
            # `data-api` scope; a no-op otherwise (see _data_api_claims). Carried
            # across refresh because the granted scope rides the refresh token
            # (set at code exchange, carried forward by rotation below) and is
            # re-narrowed above, so it survives only for an opted-in client.
            **_data_api_claims(scope, client, org_claims),
        },
    )

    # Issue new refresh token with client binding (rotation)
    new_refresh_token, _, _, _ = jwt_manager.create_refresh_token(
        user_id=str(user.id),
        family=payload.get("family"),
        additional_claims={
            "client_id": client.client_id,
            "aud": client_audience,
            "scope": scope,
        },
    )

    # Update client last_used_at
    client.last_used_at = datetime.utcnow()
    await db.commit()

    return TokenResponse(
        access_token=access_token,
        token_type="Bearer",
        expires_in=3600,
        refresh_token=new_refresh_token,
        scope=scope,
    )


# ============================================================================
# OpenID Connect UserInfo Endpoint
# ============================================================================


@router.get("/userinfo", response_model=UserInfoResponse)
async def userinfo(
    request: Request,
    db: AsyncSession = Depends(get_db),
    redis: ResilientRedisClient = Depends(get_redis),
):
    """
    OpenID Connect UserInfo Endpoint.

    Returns claims about the authenticated user.
    Requires Bearer token in Authorization header.
    """
    # Get access token from Authorization header
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid_token: Bearer token required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = auth_header[7:]

    # Verify token
    try:
        payload = await _verify_oauth_token(token, token_type="access", db=db)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid_token: Token expired or invalid",
            headers={"WWW-Authenticate": "Bearer"},
        )
    # A token revoked through POST /oauth/revoke is refused like an expired
    # one. Strict read: 503 when Redis cannot answer.
    if not payload or await token_revocation.is_revoked(redis, payload, "access"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid_token: Token expired or invalid",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Get user
    user_id = payload.get("sub")
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid_token: User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Build response based on scope
    scope = payload.get("scope", "")
    response = UserInfoResponse(sub=str(user.id))

    if "email" in scope or "openid" in scope:
        response.email = user.email
        response.email_verified = getattr(user, "email_verified", True)

    if "profile" in scope or "openid" in scope:
        response.name = getattr(user, "name", None)
        response.given_name = user.first_name or None
        response.family_name = user.last_name or None
        if not response.name and (response.given_name or response.family_name):
            response.name = " ".join(
                part for part in (response.given_name, response.family_name) if part
            )

        response.picture = user.avatar_url or user.profile_image_url or None
        if hasattr(user, "updated_at") and user.updated_at:
            response.updated_at = int(user.updated_at.timestamp())

    return response


# ============================================================================
# Token Introspection Endpoint (RFC 7662)
# ============================================================================


@router.post("/introspect")
async def introspect(
    request: Request,
    token: str = Form(...),
    token_type_hint: Optional[str] = Form(None),
    client_id: Optional[str] = Form(None),
    client_secret: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db),
    redis: ResilientRedisClient = Depends(get_redis),
):
    """
    OAuth 2.0 Token Introspection Endpoint (RFC 7662).

    Allows resource servers to query token validity. A token revoked through
    `POST /oauth/revoke` is reported `{"active": false}`. The revocation read
    is strict: when Redis cannot answer, this answers 503 + Retry-After rather
    than calling a possibly revoked token active.
    """
    # Authenticate client (required for introspection)
    if not client_id:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Basic "):
            import base64

            try:
                decoded = base64.b64decode(auth_header[6:]).decode("utf-8")
                client_id, client_secret = decoded.split(":", 1)
            except Exception:
                pass  # Intentionally ignoring - Basic auth decode failure handled by checking client_id below

    if not client_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Client authentication required",
        )

    client = await _get_oauth_client(client_id, db)
    if not client or not client.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid_client",
        )

    if client.is_confidential and not client.verify_secret(client_secret or ""):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid_client",
        )

    # Try to verify the token
    try:
        # Try as access token first
        token_type = token_type_hint or "access"
        payload = await _verify_oauth_token(
            token,
            token_type=token_type,
            db=db,
            expected_client=client,
        )
        if not payload:
            return {"active": False}
        if await token_revocation.is_revoked(redis, payload, token_type):
            return {"active": False}

        return {
            "active": True,
            "sub": payload.get("sub"),
            "client_id": payload.get("client_id"),
            "scope": payload.get("scope"),
            "exp": payload.get("exp"),
            "iat": payload.get("iat"),
            "token_type": token_type,
        }
    except RedisUnavailableError:
        raise  # 503 + Retry-After: revocation status unknown
    except Exception:
        # Token is invalid or expired
        return {"active": False}


# ============================================================================
# Token Revocation Endpoint (RFC 7009)
# ============================================================================


async def _authenticate_revoking_client(
    request: Request,
    client_id: Optional[str],
    client_secret: Optional[str],
    db: AsyncSession,
) -> OAuthClient:
    """Client authentication for `POST /oauth/revoke` (RFC 7009 §2.1).

    The same rules as the token endpoint: credentials by HTTP Basic or form
    fields; the client must exist and be active; a confidential client must
    present its secret. A public client identifies itself by `client_id`.
    """
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Basic "):
        import base64

        try:
            decoded = base64.b64decode(auth_header[6:]).decode("utf-8")
            client_id, client_secret = decoded.split(":", 1)
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="invalid_client: Invalid Basic auth",
            )

    if not client_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid_client: client authentication required",
        )

    client = await _get_oauth_client(client_id, db)
    if not client or not client.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid_client",
        )

    if client.is_confidential and not client.verify_secret(client_secret or ""):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid_client",
        )
    return client


async def _revoke_protected_resource_token(
    *,
    request: Request,
    token: str,
    client_id: Optional[str],
    client_secret: Optional[str],
    db: AsyncSession,
    redis: ResilientRedisClient,
):
    """RFC 7009 for protected-resource tokens (see `revoke`)."""
    if is_url_client_id(client_id):
        pinned = _pinned_cimd_client_id(client_id)
        if pinned is None or client_secret:
            return _oauth_token_error("invalid_client", "client authentication failed", 401)
        caller = pinned
    else:
        caller = (
            await _authenticate_revoking_client(request, client_id, client_secret, db)
        ).client_id

    claims = resource_tokens.verify_refresh_token(token)
    if claims is not None and claims.get("client_id") == caller:
        resource = PROTECTED_RESOURCES.get(claims["resource"])
        await token_revocation.revoke_family(
            redis,
            claims["family"],
            ttl=(
                resource.refresh_token_idle_seconds
                if resource
                else token_revocation.refresh_token_ttl()
            ),
            reason="oauth_revoke",
            strict=True,
        )
        logger.info("OAuth token revoked", client_id=caller, token_type="resource_refresh")
    # 200 whether or not anything was revoked (RFC 7009 §2.2).
    return {"message": "Token revoked"}


async def _verified_token_of_client(
    token: str, token_type: str, client: OAuthClient, db: AsyncSession
) -> Optional[dict[str, Any]]:
    """The token's claims when Janua minted it for `client` and it is unexpired."""
    try:
        payload = await _verify_oauth_token(
            token, token_type=token_type, db=db, expected_client=client
        )
    except Exception:
        return None
    if not payload or payload.get("client_id") != client.client_id:
        # Unknown, invalid, expired, or issued to another client (or a Janua
        # session token, which belongs to no client): nothing to revoke here.
        return None
    return payload


@router.post("/revoke")
async def revoke(
    request: Request,
    token: str = Form(...),
    token_type_hint: Optional[str] = Form(None),
    client_id: Optional[str] = Form(None),
    client_secret: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db),
    redis: ResilientRedisClient = Depends(get_redis),
):
    """
    OAuth 2.0 Token Revocation Endpoint (RFC 7009).

    - The client authenticates as at the token endpoint (401 `invalid_client`
      otherwise).
    - `token_type_hint` (`access_token` / `refresh_token`) sets which kind is
      tried first; it is optional and a wrong hint still works (§2.1).
    - A refresh token revokes its whole rotation family: the refresh grant
      refuses it and every token minted from it later (§2.1).
    - An access token is blacklisted by `jti` until it expires: `/userinfo`
      and `/introspect` refuse it. Relying parties that verify tokens
      offline against the JWKS cannot see a revocation; that is what the
      short access-token lifetime and introspection are for.
    - An unknown, invalid or expired token, or one issued to another client,
      changes nothing and still answers 200 (§2.2): the answer never tells a
      client whether a token exists.
    - Fails closed: when Redis cannot store the revocation the answer is 503 +
      Retry-After, never a 200 for a revocation that did not happen.
    - Protected resources: an https `client_id` (CIMD, public: no secret) or
      a resource refresh token is handled by
      `_revoke_protected_resource_token`; a resource refresh token revokes its
      family. Resource access tokens are verified offline by the resource and
      expire within minutes, so revoking one changes nothing (200).
    """
    if is_url_client_id(client_id) or resource_tokens.looks_like_resource_refresh_token(token):
        return await _revoke_protected_resource_token(
            request=request,
            token=token,
            client_id=client_id,
            client_secret=client_secret,
            db=db,
            redis=redis,
        )

    client = await _authenticate_revoking_client(request, client_id, client_secret, db)

    order = ["refresh", "access"] if token_type_hint == "refresh_token" else ["access", "refresh"]
    for token_type in order:
        payload = await _verified_token_of_client(token, token_type, client, db)
        if payload is None:
            continue
        if token_type == "refresh":
            await token_revocation.revoke_family(
                redis, payload.get("family"), reason="oauth_revoke", strict=True
            )
            await token_revocation.revoke_jti(
                redis,
                payload.get("jti"),
                token_revocation.seconds_until(
                    payload.get("exp"), token_revocation.refresh_token_ttl()
                ),
                reason="oauth_revoke",
                strict=True,
            )
        else:
            await token_revocation.revoke_jti(
                redis,
                payload.get("jti"),
                token_revocation.seconds_until(
                    payload.get("exp"), token_revocation.access_token_ttl()
                ),
                reason="oauth_revoke",
                strict=True,
            )
        logger.info(
            "OAuth token revoked",
            client_id=client.client_id,
            token_type=token_type,
        )
        break

    # 200 whether or not anything was revoked (RFC 7009 §2.2).
    return {"message": "Token revoked"}


# ============================================================================
# OIDC RP-Initiated Logout (OpenID Connect Session Management 1.0)
# ============================================================================


def _clear_janua_session_cookies(response: RedirectResponse) -> None:
    """Clear Janua browser session cookies on logout.

    `janua_sso` is deleted through its own helper because it is set with an
    explicit `Path=/` — a deletion that differs on Domain *or* Path addresses a
    different cookie and leaves the live one in the browser.
    """
    delete_kwargs: dict = {}
    if settings.COOKIE_DOMAIN:
        delete_kwargs["domain"] = settings.COOKIE_DOMAIN
    for cookie_name in (
        "janua_access_token",
        "janua_refresh_token",
        "access_token",
        "refresh_token",
    ):
        response.delete_cookie(cookie_name, **delete_kwargs)
    clear_sso_cookie(response)


async def _perform_oidc_end_session(
    client_id: str,
    post_logout_redirect_uri: str,
    state: Optional[str],
    db: AsyncSession,
    request: Optional[Request],
) -> RedirectResponse:
    """Shared body for the GET and POST forms of RP-Initiated Logout.

    Clears Janua session cookies, revokes the `janua_sso` row, and 302-redirects
    to an allowlisted `post_logout_redirect_uri`. Both the GET route (used by a
    top-level browser navigation) and the POST route (used by a form submission)
    call this so the two verbs cannot drift apart in their security checks.
    """
    client = await _get_oauth_client(client_id, db)
    if not client or not client.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="invalid_client",
        )

    allowed_uris = client.redirect_uris or []
    if isinstance(allowed_uris, str):
        try:
            allowed_uris = json.loads(allowed_uris)
        except json.JSONDecodeError:
            allowed_uris = []

    # SECURITY (CWE-601): the same open-redirect discipline the authorize
    # endpoint documents — an unlisted post_logout_redirect_uri is refused, never
    # redirected to.
    if not validate_post_logout_redirect_uri(post_logout_redirect_uri, allowed_uris):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="invalid_request: post_logout_redirect_uri not registered for client",
        )

    redirect_url = post_logout_redirect_uri
    if state:
        separator = "&" if "?" in redirect_url else "?"
        redirect_url = f"{redirect_url}{separator}{urlencode({'state': state})}"

    # Revoke before clearing: the cookie is the only handle we have on the row.
    # `request` is optional so the existing direct callers and tests, which invoke
    # the wrappers as plain coroutines with keyword args, keep working.
    try:
        if request is not None and await revoke_sso_cookie_session(
            request.cookies.get(SSO_COOKIE_NAME), db
        ):
            await db.commit()
    except Exception:
        logger.warning("Failed to revoke janua_sso session on end_session", exc_info=True)

    response = RedirectResponse(url=redirect_url, status_code=302)
    _clear_janua_session_cookies(response)
    return response


@logout_router.get("/logout")
async def oidc_end_session(
    client_id: str = Query(..., description="OAuth client ID"),
    post_logout_redirect_uri: str = Query(
        ..., description="URI to redirect after logout (must match client registration)"
    ),
    state: Optional[str] = Query(None, description="Opaque state forwarded to redirect URI"),
    db: AsyncSession = Depends(get_db),
    request: Request = None,
):
    """
    OIDC RP-Initiated Logout endpoint (end_session_endpoint), GET form.

    Clears Janua session cookies and redirects to the registered post-logout URI.
    The GET form is what a top-level browser navigation uses — the only shape that
    reliably lands the `janua_sso` (Domain=.madfam.io) deletion on the browser,
    since an XHR from any single estate host cannot delete an estate-wide cookie.

    SSO (J5/R1): deleting `janua_sso` is the cosmetic half. The half that matters
    is revoking the `sessions` row it references — a copy of the cookie taken
    before logout must stop working, not merely disappear from this browser. The
    cookie's signature is verified before anything is revoked, so a forged value
    cannot end someone else's session.

    `request` is declared last and optional so FastAPI still injects it on the
    real route while the existing keyword-only callers keep working unchanged.
    """
    return await _perform_oidc_end_session(
        client_id, post_logout_redirect_uri, state, db, request
    )


@logout_router.post("/logout")
async def oidc_end_session_post(
    client_id: str = Form(..., description="OAuth client ID"),
    post_logout_redirect_uri: str = Form(
        ..., description="URI to redirect after logout (must match client registration)"
    ),
    state: Optional[str] = Form(None, description="Opaque state forwarded to redirect URI"),
    db: AsyncSession = Depends(get_db),
    request: Request = None,
):
    """
    OIDC RP-Initiated Logout endpoint (end_session_endpoint), POST form.

    OIDC RP-Initiated Logout 1.0 §2 permits either GET or POST at the
    end_session_endpoint; the POST form reads its parameters from an
    `application/x-www-form-urlencoded` body. Same allowlist validation, same
    cookie clearing, and same `sessions`-row revocation as the GET form — they
    share `_perform_oidc_end_session` so the two verbs cannot diverge on any
    security check.
    """
    return await _perform_oidc_end_session(
        client_id, post_logout_redirect_uri, state, db, request
    )
