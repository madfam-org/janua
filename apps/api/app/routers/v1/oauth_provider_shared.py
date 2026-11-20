"""Shared OAuth provider plumbing: the routers, token audiences and verification, consent CSRF tokens, the browser session user, authorization codes, redirect validation, PKCE and ID tokens.

Split out of `app/routers/v1/oauth_provider.py` (2026-11-19, the 800-line
pre-commit limit); code moved verbatim. Names tests patch live in one module
and other modules call them through it (e.g. `_oauth_provider_shared.get_redis`), so one
patch target reaches every caller.
"""

import hashlib
import json
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from urllib.parse import urlencode

import structlog
from fastapi import APIRouter, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.authentication_assurance import (
    assurance_for_request,  # noqa: F401 (patch point)
    session_assurance,
    user_requires_mfa,  # noqa: F401 (patch point)
)
from app.auth.sessions_cookie import SESSIONS_COOKIE_NAME, TAB_SESSION_HEADER, read_sessions_cookie
from app.auth.sso_cookie import SSO_COOKIE_NAME, resolve_session_by_id, resolve_sso_cookie_session
from app.config import settings
from app.core.jwt_manager import jwt_manager
from app.core.oauth_metadata import oauth_issuer
from app.core.redis import ResilientRedisClient, get_redis
from app.core.redis_circuit_breaker import RedisUnavailableError
from app.core.url_security import is_safe_redirect_url, validate_oauth_redirect_uri
from app.models import OAuthClient, Organization, OrganizationMember, User
from app.models import Session as UserSession
from app.services import token_revocation
from app.services.oauth_client_authority import client_registered_by_platform_admin  # noqa: F401 (patch point)
from app.services.org_claims_service import get_user_org_claims, organization_roles_for_roles_claim
from app.services.spanish_formality import spanish_formality_claims

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
            # Collect the organization roles across active organizations.
            # A string shaped like an application role (`<app>:<role>`) is NOT
            # published: organization admins name these strings freely, and
            # under `roles` nothing would tell it from an audited grant. See
            # `organization_roles_for_roles_claim`.
            entitlements["roles"] = organization_roles_for_roles_claim(
                (m.role for m in memberships), user_id=user.id
            )

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


async def _verify_own_access_token(token: str) -> Optional[dict]:
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

    A token on the revocation list (signed out, session revoked) is refused
    like an expired one; `RedisUnavailableError` propagates (503) rather than
    accepting a token whose revocation status is unknown.
    """
    payload = jwt_manager.verify_token(token, token_type="access")
    if not payload:
        payload = jwt_manager.verify_token(token, token_type="access", verify_audience=False)
        if not payload:
            return None
        aud = payload.get("aud")
        if not isinstance(aud, str) or not aud:
            logger.warning("Session token carries no usable audience claim")
            return None

    if await token_revocation.is_revoked(await get_redis(), payload, "access"):
        logger.info("Session token refused: revoked")
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
            payload = await _verify_own_access_token(token)
            if payload and payload.get("sub"):
                result = await db.execute(select(User).where(User.id == payload.get("sub")))
                user = result.scalar_one_or_none()
                if user:
                    request.state.authentication_assurance = payload
                    return user
        except RedisUnavailableError:
            raise
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
                    request.state.authentication_assurance = session_assurance(_tab_session)
                    return tab_user
                logger.info("X-Janua-Session names a held sid whose row is not live; ignoring")
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
            payload = await _verify_own_access_token(access_token)
            if payload and payload.get("sub"):
                result = await db.execute(select(User).where(User.id == payload.get("sub")))
                hosted_user = result.scalar_one_or_none()
                if hosted_user is not None:
                    hosted_payload = payload
        except RedisUnavailableError:
            raise
        except Exception:
            pass  # Intentionally ignoring - cookie JWT verification failure means user is not authenticated

    if estate_user is None:
        request.state.authentication_assurance = hosted_payload or {}
        return hosted_user
    if hosted_user is None or str(hosted_user.id) == str(estate_user.id):
        request.state.authentication_assurance = session_assurance(estate_session)
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
        hosted_started is not None
        and estate_started is not None
        and hosted_started > estate_started
    )
    logger.info(
        "Session cookies name different users; preferring the newer session",
        estate_user=_redacted(estate_user.id),
        hosted_user=_redacted(hosted_user.id),
        estate_session_started=estate_started.isoformat() if estate_started else None,
        hosted_session_started=hosted_started.isoformat() if hosted_started else None,
        winner="janua_access_token" if hosted_wins else SSO_COOKIE_NAME,
    )
    request.state.authentication_assurance = (
        hosted_payload if hosted_wins else session_assurance(estate_session)
    )
    return hosted_user if hosted_wins else estate_user


AUTH_CODE_PREFIX = "oauth:code:"


AUTH_CODE_TTL = 600  # 10 minutes


async def _store_auth_code(code: str, data: dict, redis: ResilientRedisClient):
    """Store authorization code in Redis with TTL.

    Strict: raises RedisUnavailableError (→ 503 + Retry-After) when Redis cannot
    store it. A breaker fallback here would keep the code in one pod's memory,
    where the token endpoint on the other pod cannot find it.
    """
    key = f"{AUTH_CODE_PREFIX}{code}"
    logger.info("Storing auth code in Redis", client_id=data.get("client_id"))
    await redis.strict_set(key, json.dumps(data), ex=AUTH_CODE_TTL)
    logger.info("Auth code stored successfully")


async def _get_auth_code(code: str, redis: ResilientRedisClient) -> dict | None:
    """Retrieve authorization code from Redis itself (strict: never a pod-local copy).

    A fallback read could return a code this pod saw earlier and another pod
    already redeemed — replay of a single-use code.
    """
    key = f"{AUTH_CODE_PREFIX}{code}"
    logger.info("Retrieving auth code from Redis")
    data = await redis.strict_get(key)
    if data:
        logger.info("Auth code found in Redis")
        return json.loads(data)
    logger.warning("Auth code NOT found in Redis")
    return None


async def _delete_auth_code(code: str, redis: ResilientRedisClient) -> bool:
    """Consume an authorization code (single use).

    True only for the caller that actually removed it: of two concurrent
    redemptions of the same code, exactly one wins.
    """
    key = f"{AUTH_CODE_PREFIX}{code}"
    return await redis.strict_delete(key) == 1


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
    authentication_assurance: Optional[dict] = None,
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
        "email": user.email,
        "email_verified": user.email_verified if hasattr(user, "email_verified") else True,
        "name": user.name if hasattr(user, "name") else None,
    }

    claims.update(authentication_assurance or {})

    # The person's Spanish register ("tu" | "usted"), only once they have
    # answered; absent otherwise, so an unanswered person's ID token is unchanged.
    claims.update(spanish_formality_claims(user))

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
