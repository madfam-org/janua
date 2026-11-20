"""Token grant handlers: client credentials, authorization code and refresh token.

Split out of `app/routers/v1/oauth_provider.py` (2026-11-19, the 800-line
pre-commit limit); code moved verbatim. Names tests patch live in one module
and other modules call them through it (e.g. `_oauth_provider_shared.get_redis`), so one
patch target reaches every caller.
"""

from datetime import datetime, timedelta
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.authentication_assurance import has_mfa_assurance
from app.core.jwt_manager import jwt_manager
from app.core.redis import ResilientRedisClient
from app.models import OAuthClient, User
from app.routers.v1 import oauth_provider_shared as _oauth_provider_shared
from app.routers.v1.oauth_provider_resource_tokens import (
    _exchange_resource_code,
    _token_client_from_row,
)
from app.routers.v1.oauth_provider_schemas import TokenResponse
from app.routers.v1.oauth_provider_scopes import (
    _data_api_claims,
    _get_client_credentials_claims,
    _parse_requested_scopes,
    _require_grantable_scope,
    _service_account_email,
    _service_client_app_roles,
)
from app.routers.v1.oauth_provider_shared import SERVICE_TOKEN_TTL_SECONDS, _redacted
from app.services import token_revocation
from app.services.audit_logger import AuditEventType, AuditLogger
from app.services.entitlements_service import (
    entitlements_to_claim,
    get_product_tier_claims,
    get_user_entitlements,
)
from app.services.invite_only_clients import has_invited_access
from app.services.org_claims_service import merge_app_roles_into_claims
from app.services.service_principal import service_principal_claims
from app.services.spanish_formality import spanish_formality_claims


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
    client_audience = client.audience or _oauth_provider_shared.settings.JWT_AUDIENCE
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


async def _require_invited_access(user: User, client: OAuthClient, db: AsyncSession) -> None:
    """400 invalid_grant unless ``user`` may use ``client`` (always true for open clients)."""
    if await has_invited_access(user, client.client_id, db):
        return
    _oauth_provider_shared.logger.info(
        "token.rejected",
        reason="invite_only",
        client_id=client.client_id,
        user=_redacted(getattr(user, "id", "")),
    )
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="invalid_grant: This account has not been invited to this application",
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
    code_data = await _oauth_provider_shared._get_auth_code(code, redis)
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
        _oauth_provider_shared.logger.warning(
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
        _oauth_provider_shared.logger.warning(
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
            _oauth_provider_shared.logger.warning(
                "token.rejected",
                reason="code_verifier_missing",
                client_id=client.client_id,
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="invalid_request: code_verifier required",
            )
        if not _oauth_provider_shared._verify_pkce(
            code_verifier,
            code_data["code_challenge"],
            code_data.get("code_challenge_method", "S256"),
        ):
            # The client's verifier belongs to a different authorize request
            # than the one that issued this code. Logging the challenge (a
            # public, single-use hash — never the verifier) is what makes that
            # diagnosable; without it a 400 here is indistinguishable from
            # every other 400 and costs hours to chase.
            _oauth_provider_shared.logger.warning(
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
    if not await _oauth_provider_shared._delete_auth_code(code, redis):
        _oauth_provider_shared.logger.warning(
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

    # Invite-only clients: the enforcement half of the /authorize gate. Every
    # code path (password, emailed link, consent, account chooser) and every
    # refresh ends here, so a person without the client's product entitlement —
    # or whose invitation was revoked since — gets no token.
    await _require_invited_access(user, client, db)

    from app.auth.authentication_assurance import validate_live_assurance
    from app.auth.tenant_login_context import require_client_membership

    await require_client_membership(db, user, client)
    authentication_assurance = await validate_live_assurance(
        db, user, code_data.get("authentication_assurance", {})
    )
    if await _oauth_provider_shared.user_requires_mfa(
        db, user, getattr(client, "organization_id", None)
    ) and not has_mfa_assurance(authentication_assurance):
        raise HTTPException(400, "invalid_grant: multi-factor authentication required")

    # Fetch user entitlements for Galaxy ecosystem (tier, roles, sub_status)
    entitlements = await _oauth_provider_shared._get_user_entitlements(user, db)

    # Per-product MADFAM ecosystem grants (Selva-unified SSO Phase 1).
    # Sourced from the user_entitlements table + org inheritance + admin
    # bootstrap. See app/services/entitlements_service.py.
    madfam_entitled_products = entitlements_to_claim(await get_user_entitlements(user, db))

    # Organization claims for org-scoped resource servers (symbiosis-hcm etc.);
    # unambiguous org_id or none — see _get_user_org_claims.
    org_claims = await _oauth_provider_shared._get_user_org_claims(user, db)

    # APPLICATION roles (`hcm:hr` and friends) are UNIONED onto the legacy
    # organization-role list rather than replacing it: `roles` has been an OIDC
    # claim for years and existing clients still read it, so nothing is removed
    # — they gain the namespaced application roles alongside what they had.
    # This merge must happen BEFORE the spread below, because `**org_claims`
    # lands AFTER `"roles": entitlements["roles"]` in the dict literal: an
    # unmerged `roles` key would silently clobber the legacy claim by ordering
    # alone. The shared helper also pops the resolver's private transport key,
    # so it can never reach a token.
    org_claims = merge_app_roles_into_claims(org_claims, existing_roles=entitlements["roles"])

    # `{product}_tier` claims (G1-1): the token's own org's product tiers merged
    # with the user's active per-user grants. Products authorize on these, not
    # on `madfam_entitled_products`. Spread FIRST below so no product slug can
    # override another claim.
    tier_claims = await get_product_tier_claims(user, db, org_id=org_claims.get("org_id"))

    # Resolve per-client audience (falls back to global JWT_AUDIENCE)
    client_audience = client.audience or _oauth_provider_shared.settings.JWT_AUDIENCE

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
            **tier_claims,
            **authentication_assurance,
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
            # `spanish_formality` ("tu" | "usted") only once the person has
            # answered; re-read from the row at every mint, refresh included.
            **spanish_formality_claims(user),
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
            **authentication_assurance,
            "client_id": client.client_id,
            "aud": client_audience,
            "scope": scope,
        },
    )

    # Generate ID token if openid scope requested
    id_token = None
    if "openid" in scope:
        id_token = _oauth_provider_shared._generate_id_token(
            user=user,
            client_id=client.client_id,
            nonce=code_data.get("nonce"),
            access_token=access_token,
            authentication_assurance=authentication_assurance,
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
        payload = await _oauth_provider_shared._verify_oauth_token(
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
    if await token_revocation.is_revoked(redis or await _oauth_provider_shared.get_redis(), payload, "refresh"):
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

    # Invite-only clients: the enforcement half of the /authorize gate. Every
    # code path (password, emailed link, consent, account chooser) and every
    # refresh ends here, so a person without the client's product entitlement —
    # or whose invitation was revoked since — gets no token.
    await _require_invited_access(user, client, db)

    from app.auth.authentication_assurance import validate_live_assurance
    from app.auth.tenant_login_context import require_client_membership

    await require_client_membership(db, user, client)
    authentication_assurance = await validate_live_assurance(db, user, payload)
    if await _oauth_provider_shared.user_requires_mfa(
        db, user, getattr(client, "organization_id", None)
    ) and not has_mfa_assurance(authentication_assurance):
        raise HTTPException(400, "invalid_grant: multi-factor authentication required")

    # Fetch user entitlements for Galaxy ecosystem (tier, roles, sub_status)
    entitlements = await _oauth_provider_shared._get_user_entitlements(user, db)

    # Per-product MADFAM ecosystem grants (Selva-unified SSO Phase 1).
    madfam_entitled_products = entitlements_to_claim(await get_user_entitlements(user, db))

    # Organization claims for org-scoped resource servers (symbiosis-hcm etc.);
    # unambiguous org_id or none — see _get_user_org_claims.
    org_claims = await _oauth_provider_shared._get_user_org_claims(user, db)

    # APPLICATION roles (`hcm:hr` and friends) are UNIONED onto the legacy
    # organization-role list rather than replacing it: `roles` has been an OIDC
    # claim for years and existing clients still read it, so nothing is removed
    # — they gain the namespaced application roles alongside what they had.
    # This merge must happen BEFORE the spread below, because `**org_claims`
    # lands AFTER `"roles": entitlements["roles"]` in the dict literal: an
    # unmerged `roles` key would silently clobber the legacy claim by ordering
    # alone. The shared helper also pops the resolver's private transport key,
    # so it can never reach a token.
    org_claims = merge_app_roles_into_claims(org_claims, existing_roles=entitlements["roles"])

    # `{product}_tier` claims (G1-1): the token's own org's product tiers merged
    # with the user's active per-user grants. Products authorize on these, not
    # on `madfam_entitled_products`. Spread FIRST below so no product slug can
    # override another claim.
    tier_claims = await get_product_tier_claims(user, db, org_id=org_claims.get("org_id"))

    # Resolve per-client audience (falls back to global JWT_AUDIENCE)
    client_audience = client.audience or _oauth_provider_shared.settings.JWT_AUDIENCE

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
            **tier_claims,
            **authentication_assurance,
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
            # `spanish_formality` ("tu" | "usted") only once the person has
            # answered; re-read from the row at every mint, refresh included.
            **spanish_formality_claims(user),
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
            **authentication_assurance,
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
