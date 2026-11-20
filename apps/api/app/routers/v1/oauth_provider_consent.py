"""POST /oauth/consent and POST /oauth/authorize.

Split out of `app/routers/v1/oauth_provider.py` (2026-11-19, the 800-line
pre-commit limit); code moved verbatim. Names tests patch live in one module
and other modules call them through it (e.g. `_oauth_provider_shared.get_redis`), so one
patch target reaches every caller.
"""

import json
import secrets
import time
from datetime import datetime
from typing import List, Optional

from fastapi import Depends, Form, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.authentication_assurance import has_mfa_assurance
from app.core.database import get_db
from app.core.redis import ResilientRedisClient
from app.dependencies import get_current_user
from app.models import User
from app.routers.v1 import oauth_provider_shared as _oauth_provider_shared
from app.routers.v1.oauth_provider_clients import _redirect_with_oauth_error
from app.routers.v1.oauth_provider_resources import (
    _complete_protected_resource_consent,
    _resource_values,
)
from app.routers.v1.oauth_provider_scopes import _require_grantable_scope
from app.routers.v1.oauth_provider_shared import AUTH_CODE_TTL, _build_safe_callback_url, router
from app.services.client_id_metadata import is_url_client_id
from app.services.consent_service import ConsentService


@router.post("/consent")
async def handle_consent(
    request: Request,
    auth_request_id: str = Form(...),
    csrf_token: str = Form(...),
    action: str = Form(...),
    db: AsyncSession = Depends(get_db),
    redis: ResilientRedisClient = Depends(_oauth_provider_shared.get_redis),
):
    """
    Handle OAuth consent form submission.

    User can either 'allow' or 'deny' the authorization request.
    """
    # Get user from cookie or header (supports browser-based OAuth flow)
    current_user = await _oauth_provider_shared.get_user_from_cookie_or_header(request, db)
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    # Validate CSRF token
    if not await _oauth_provider_shared._validate_csrf_token(csrf_token, str(current_user.id), redis):
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
            request=request,
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
    client = await _oauth_provider_shared._get_oauth_client(auth_request["client_id"], db)
    if not client or not _oauth_provider_shared._validate_redirect_uri(redirect_uri, client.redirect_uris):
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
        _oauth_provider_shared.logger.error(
            "Failed to store OAuth consent",
            user_id=str(current_user.id),
            client_id=client_id,
            error=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process consent. Please try again.",
        )

    authentication_assurance = await _oauth_provider_shared.assurance_for_request(request, db, current_user)
    if await _oauth_provider_shared.user_requires_mfa(db, current_user, client.organization_id) and not has_mfa_assurance(
        authentication_assurance
    ):
        raise HTTPException(428, "Multi-factor authentication required")

    # Generate authorization code
    auth_code = secrets.token_urlsafe(32)
    code_data = {
        "client_id": client_id,
        "user_id": str(current_user.id),
        "authentication_assurance": authentication_assurance,
        "redirect_uri": redirect_uri,
        "scope": scope,
        "nonce": auth_request.get("nonce"),
        "code_challenge": auth_request.get("code_challenge"),
        "code_challenge_method": auth_request.get("code_challenge_method") or "S256",
        "expires_at": time.time() + AUTH_CODE_TTL,
    }
    await _oauth_provider_shared._store_auth_code(auth_code, code_data, redis)

    # Update client last_used_at
    try:
        if client:
            client.last_used_at = datetime.utcnow()
            await db.commit()
    except Exception as e:
        # Non-critical — don't fail the consent flow for a timestamp update
        _oauth_provider_shared.logger.warning("Failed to update client last_used_at", error=str(e))

    # SECURITY: Redirect with code using validated redirect_uri
    callback_params = {"code": auth_code}
    if state:
        callback_params["state"] = state

    callback_url = _build_safe_callback_url(redirect_uri, callback_params, client_validated=True)

    _oauth_provider_shared.logger.info(
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
    redis: ResilientRedisClient = Depends(_oauth_provider_shared.get_redis),
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
    if not csrf_token or not await _oauth_provider_shared._validate_csrf_token(csrf_token, str(current_user.id), redis):
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

    client = await _oauth_provider_shared._get_oauth_client(client_id, db)
    if not client or not client.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid_client")

    # SECURITY: Validate redirect_uri against registered URIs (CWE-601 prevention)
    if not _oauth_provider_shared._validate_redirect_uri(redirect_uri, client.redirect_uris):
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
    if _oauth_provider_shared.settings.REQUIRE_EMAIL_VERIFICATION and not getattr(current_user, "email_verified", False):
        # Check grace period for new accounts
        from datetime import timedelta

        if current_user.created_at:
            grace_period = timedelta(hours=_oauth_provider_shared.settings.EMAIL_VERIFICATION_GRACE_PERIOD_HOURS)
            grace_deadline = current_user.created_at + grace_period
            if datetime.utcnow() >= grace_deadline:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Email verification required. Please verify your email before authorizing third-party applications.",
                )

    authentication_assurance = await _oauth_provider_shared.assurance_for_request(request, db, current_user)

    # Generate authorization code and store in Redis
    auth_code = secrets.token_urlsafe(32)
    code_data = {
        "client_id": client_id,
        "user_id": str(current_user.id),
        "authentication_assurance": authentication_assurance,
        "redirect_uri": redirect_uri,
        "scope": scope,
        "nonce": nonce,
        "code_challenge": code_challenge,
        "code_challenge_method": code_challenge_method or "S256",
        "expires_at": time.time() + AUTH_CODE_TTL,
    }
    await _oauth_provider_shared._store_auth_code(auth_code, code_data, redis)

    # Update client last_used_at
    client.last_used_at = datetime.utcnow()
    await db.commit()

    # SECURITY: Redirect with code using validated redirect_uri
    callback_params = {"code": auth_code}
    if state:
        callback_params["state"] = state

    callback_url = _build_safe_callback_url(redirect_uri, callback_params, client_validated=True)
    return RedirectResponse(url=callback_url, status_code=302)
