"""POST /oauth/token.

Split out of `app/routers/v1/oauth_provider.py` (2026-11-19, the 800-line
pre-commit limit); code moved verbatim. Names tests patch live in one module
and other modules call them through it (e.g. `_oauth_provider_shared.get_redis`), so one
patch target reaches every caller.
"""

from typing import List, Optional

from fastapi import Depends, Form, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.redis import ResilientRedisClient
from app.routers.v1 import oauth_provider_shared as _oauth_provider_shared
from app.routers.v1.oauth_provider_grants import (
    _handle_authorization_code_grant,
    _handle_client_credentials_grant,
    _handle_refresh_token_grant,
)
from app.routers.v1.oauth_provider_resource_tokens import _token_for_protected_resource
from app.routers.v1.oauth_provider_resources import _resource_values
from app.routers.v1.oauth_provider_schemas import TokenResponse
from app.routers.v1.oauth_provider_scopes import _client_grant_types
from app.routers.v1.oauth_provider_shared import router
from app.services import resource_tokens
from app.services.client_id_metadata import is_url_client_id


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
    redis: ResilientRedisClient = Depends(_oauth_provider_shared.get_redis),
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
    client = await _oauth_provider_shared._get_oauth_client(client_id, db)
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
