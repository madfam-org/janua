"""Opt-in first-party continuation; ordinary OAuth remains the target authority."""

from __future__ import annotations

import json
import re
import time
from typing import Any
from urllib.parse import parse_qs, urlencode, urlsplit
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel, ConfigDict, Field, SecretStr
from sqlalchemy import Text, and_, cast, func, literal_column, or_, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.session_bridge_authority import (
    InvalidSessionProof,
    recheck_source_proof,
    verify_source_proof,
)
from app.auth.session_bridge_state import TRANSACTION_TTL, BridgeStateStore, InvalidBridgeState
from app.auth.sso_cookie import SSO_COOKIE_NAME, resolve_sso_cookie_session, set_sso_cookie
from app.config import settings
from app.core.database import get_db
from app.core.redis import get_redis
from app.core.redis_circuit_breaker import ResilientRedisClient
from app.core.reserved_oauth_boundaries import FIRST_PARTY_NAME_PREFIXES, SILENT_AUTH_SCOPE
from app.models import OAuthClient, User
from app.routers.v1.oauth_provider import (
    _authenticate_revoking_client,
    _client_grant_types,
    _get_oauth_client,
    _is_silent_auth_allowed,
    _redirect_with_oauth_error,
    _require_grantable_scope,
    _verify_own_access_token,
)
from app.services import token_revocation

router = APIRouter(prefix="/oauth/session-bridge", tags=["OAuth Provider"])
COOKIE = "__Host-janua-session-bridge"
FINAL_COOKIE = "__Host-janua-session-bridge-final"
FINAL_PATH = "/api/v1/oauth/session-bridge/finalize"
HEADERS = {"Cache-Control": "no-store", "Pragma": "no-cache", "Referrer-Policy": "no-referrer"}
REQUIRED = {
    "response_type",
    "client_id",
    "redirect_uri",
    "scope",
    "state",
    "nonce",
    "code_challenge",
    "code_challenge_method",
    "prompt",
}
OPTIONAL = {"audience", "ui_locales"}
OPAQUE = re.compile(r"[A-Za-z0-9_-]{43}\Z")


class PrepareInput(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)
    state: str = Field(min_length=43, max_length=43, pattern=r"^[A-Za-z0-9_-]{43}$")
    access_token: SecretStr | None = Field(default=None, max_length=16384)
    refresh_token: SecretStr | None = Field(default=None, max_length=16384)


def _enabled() -> None:
    if not settings.SESSION_BRIDGE_ENABLED:
        raise HTTPException(404, "Not found", headers=HEADERS)


def _origin(uri: str) -> str:
    parsed = urlsplit(uri)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.fragment
    ):
        raise InvalidBridgeState()
    hostname = parsed.hostname.encode("idna").decode("ascii").lower()
    if ":" in hostname:
        hostname = f"[{hostname}]"
    port = parsed.port
    return f"https://{hostname}" + (f":{port}" if port is not None and port != 443 else "")


def _trusted(client: Any) -> None:
    if (
        client is None
        or not _is_silent_auth_allowed(client)
        or "authorization_code" not in _client_grant_types(client)
    ):
        raise InvalidBridgeState()


def _authorization(params: dict[str, str], client: OAuthClient) -> dict[str, str]:
    _trusted(client)
    if not REQUIRED.issubset(params) or set(params) - REQUIRED - OPTIONAL:
        raise InvalidBridgeState()
    if any(not isinstance(v, str) or len(v) > 4096 for v in params.values()):
        raise InvalidBridgeState()
    if (
        params["client_id"] != client.client_id
        or params["response_type"] != "code"
        or params["prompt"] != "none"
    ):
        raise InvalidBridgeState()
    if (
        not isinstance(client.redirect_uris, list)
        or params["redirect_uri"] not in client.redirect_uris
    ):
        raise InvalidBridgeState()
    _origin(params["redirect_uri"])
    if (
        params["code_challenge_method"] != "S256"
        or OPAQUE.fullmatch(params["code_challenge"]) is None
    ):
        raise InvalidBridgeState()
    if not 16 <= len(params["state"]) <= 4096 or not 16 <= len(params["nonce"]) <= 256:
        raise InvalidBridgeState()
    if "audience" in params and params["audience"] != (client.audience or settings.JWT_AUDIENCE):
        raise InvalidBridgeState()
    try:
        scope = _require_grantable_scope(params["scope"], client, grant="authorization_code")
    except (ValueError, HTTPException):
        raise InvalidBridgeState() from None
    return {**params, "scope": scope}


async def _pair(transaction: dict[str, Any], db: AsyncSession):
    source = await _get_oauth_client(transaction.get("source_client_id"), db)
    target = await _get_oauth_client(transaction.get("target_client_id"), db)
    _trusted(source)
    _trusted(target)
    if not source.audience or source.audience != transaction.get("source_audience"):
        raise InvalidBridgeState()
    uri = transaction.get("source_uri")
    if (
        not isinstance(uri, str)
        or not isinstance(source.redirect_uris, list)
        or uri not in source.redirect_uris
    ):
        raise InvalidBridgeState()
    _origin(uri)
    authorization = _authorization(transaction.get("authorization", {}), target)
    if authorization != transaction["authorization"]:
        raise InvalidBridgeState()
    return source, target, authorization


def _clear(response):
    response.delete_cookie(COOKIE, path="/", secure=True, httponly=True, samesite="none")
    response.delete_cookie(FINAL_COOKIE, path="/", secure=True, httponly=True, samesite="lax")
    return response


def _same_source_origin(request: Request, transaction: dict[str, Any]) -> None:
    origins = request.headers.getlist("origin")
    if len(origins) != 1 or origins[0] != _origin(transaction["source_uri"]):
        raise InvalidBridgeState()


def _json_member_candidate(column, value: str):
    """Native arrays or exact quoted tokens in historical ORM JSON strings."""
    stored = cast(column, JSONB)
    scalar = stored.op("#>>", return_type=Text)(literal_column("'{}'::text[]"))
    return or_(
        and_(func.jsonb_typeof(stored) == "array", stored.contains([value])),
        and_(
            func.jsonb_typeof(stored) == "string",
            scalar.contains(json.dumps(value), autoescape=True),
        ),
    )


def _source_query(source_uri: str):
    """Bound candidates without applying Text.contains to a JSONB column.

    URI/scopes/grants retain historical ORM string storage compatibility. The
    existing reserved first-party name/scope policy filters untrusted clients
    BEFORE the cap, preventing self-registered lookalikes from crowding it.
    Current Python trust and exact URI membership are still checked afterward.
    """
    redirects = cast(OAuthClient.redirect_uris, JSONB)
    grants = cast(OAuthClient.grant_types, JSONB)
    grant_scalar = grants.op("#>>", return_type=Text)(literal_column("'{}'::text[]"))
    return (
        select(OAuthClient.client_id, redirects.label("registered_uris"))
        .where(
            OAuthClient.is_active.is_(True),
            OAuthClient.is_confidential.is_(True),
            OAuthClient.audience.is_not(None),
            OAuthClient.audience != "",
            or_(
                *(
                    func.translate(
                        OAuthClient.name, "ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz"
                    ).startswith(prefix, autoescape=True)
                    for prefix in FIRST_PARTY_NAME_PREFIXES
                ),
                _json_member_candidate(OAuthClient.allowed_scopes, SILENT_AUTH_SCOPE),
            ),
            or_(
                _json_member_candidate(OAuthClient.grant_types, "authorization_code"),
                grants.is_(None),
                func.jsonb_typeof(grants) == "null",
                grants == [],
                grant_scalar == "[]",
            ),
            _json_member_candidate(OAuthClient.redirect_uris, source_uri),
        )
        .limit(3)
    )


async def _source_client(source_uri: str, db: AsyncSession):
    # Three candidates suffice to refuse overflow; never scan the registry or
    # cast arbitrary stored strings to JSONB. A malformed candidate fails closed.
    rows = (await db.execute(_source_query(source_uri))).all()
    if len(rows) >= 3:
        raise InvalidBridgeState()
    matches = []
    for client_id, stored in rows:
        if isinstance(stored, str):
            try:
                stored = json.loads(stored)
            except (ValueError, TypeError):
                raise InvalidBridgeState() from None
        if not isinstance(stored, list) or any(not isinstance(uri, str) for uri in stored):
            raise InvalidBridgeState()
        if source_uri in stored:
            matches.append(client_id)
    if len(matches) != 1:
        raise InvalidBridgeState()
    source = await _get_oauth_client(matches[0], db)
    _trusted(source)
    if not isinstance(source.redirect_uris, list) or source_uri not in source.redirect_uris:
        raise InvalidBridgeState()
    return source


@router.get("/start")
async def start(
    request: Request,
    db: AsyncSession = Depends(get_db),
    redis: ResilientRedisClient = Depends(get_redis),
):
    _enabled()
    try:
        if request.headers.get("sec-fetch-dest") not in (None, "", "document"):
            raise InvalidBridgeState()
        params = dict(request.query_params)
        if any(len(request.query_params.getlist(k)) != 1 for k in params):
            raise InvalidBridgeState()
        source_uri = params.pop("bridge_uri", None)
        if not isinstance(source_uri, str) or urlsplit(source_uri).query:
            raise InvalidBridgeState()
        _origin(source_uri)
        source = await _source_client(source_uri, db)
        if not isinstance(source.audience, str) or not source.audience:
            raise InvalidBridgeState()
        target = await _get_oauth_client(params.get("client_id"), db)
        authorization = _authorization(params, target)
        begun = await BridgeStateStore(redis).start(
            source_client_id=source.client_id,
            source_uri=source_uri,
            source_audience=source.audience,
            target_client_id=target.client_id,
            authorization=authorization,
        )
        response = RedirectResponse(
            source_uri + "?" + urlencode({"state": begun.state}), status_code=303, headers=HEADERS
        )
        # Top-level cross-site POST requires None; Origin + random browser secret are both mandatory.
        response.set_cookie(
            COOKIE,
            begun.browser_secret,
            max_age=TRANSACTION_TTL,
            path="/",
            secure=True,
            httponly=True,
            samesite="none",
        )
        return response
    except (InvalidBridgeState, ValueError, TypeError):
        raise HTTPException(400, "Invalid session continuation") from None


@router.post("/prepare")
async def prepare(
    request: Request,
    body: PrepareInput,
    db: AsyncSession = Depends(get_db),
    redis: ResilientRedisClient = Depends(get_redis),
):
    _enabled()
    client = await _authenticate_revoking_client(request, None, None, db)
    try:
        store = BridgeStateStore(redis)
        _, transaction = await store.read(body.state)
        source, _, _ = await _pair(transaction, db)
        if client.client_id != source.client_id:
            raise InvalidBridgeState()
        proof = await verify_source_proof(
            db,
            redis,
            source_client_id=source.client_id,
            source_audience=source.audience,
            access_token=(
                body.access_token.get_secret_value() if body.access_token is not None else None
            ),
            refresh_token=(
                body.refresh_token.get_secret_value() if body.refresh_token is not None else None
            ),
        )
        issued = await store.issue(body.state, proof)
        return JSONResponse({"code": issued.code}, headers=HEADERS)
    except (InvalidBridgeState, InvalidSessionProof):
        raise HTTPException(403, "Session continuation refused") from None


def _failure(authorization: dict[str, str], error: str):
    response = _redirect_with_oauth_error(
        authorization["redirect_uri"],
        error=error,
        error_description="Sign-in confirmation is required",
        state=authorization["state"],
        client_validated=True,
    )
    response.status_code = 303
    response.headers.update(HEADERS)
    return _clear(response)


async def _existing_identities(
    request: Request, db: AsyncSession, redis: ResilientRedisClient
) -> set[str]:
    identities: set[str] = set()
    estate = request.cookies.get(SSO_COOKIE_NAME)
    if estate:
        user, parent = await resolve_sso_cookie_session(estate, db)
        if user is not None and not await token_revocation.is_revoked(
            redis, {"family": parent.refresh_token_family}, "refresh"
        ):
            identities.add(str(user.id))
    access = request.cookies.get("janua_access_token")
    if access:
        claims = await _verify_own_access_token(access)
        if claims:
            try:
                user_id = UUID(claims["sub"])
            except (KeyError, ValueError, TypeError, AttributeError):
                raise InvalidBridgeState() from None
            user = await db.get(User, user_id)
            if user is not None:
                # Match the downstream selector conservatively: it may still choose
                # a signed hosted subject whose row/status/session became inactive.
                # This subject blocks an identity switch; it never grants restoration.
                identities.add(str(user.id))
    return identities


async def _form(request: Request) -> dict[str, str]:
    if (
        request.headers.get("content-type", "").split(";", 1)[0].lower()
        != "application/x-www-form-urlencoded"
    ):
        raise InvalidBridgeState()
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > 4096:
            raise InvalidBridgeState()
    values = parse_qs(
        body.decode("ascii"), keep_blank_values=True, strict_parsing=True, max_num_fields=3
    )
    if set(values) - {"state", "code", "error"} or any(
        len(v) != 1 or not v[0] for v in values.values()
    ):
        raise InvalidBridgeState()
    return {k: v[0] for k, v in values.items()}


@router.post("/complete")
async def complete(
    request: Request,
    db: AsyncSession = Depends(get_db),
    redis: ResilientRedisClient = Depends(get_redis),
):
    _enabled()
    try:
        data = await _form(request)
        state = data.get("state", "")
        browser = request.cookies.get(COOKIE, "")
        store = BridgeStateStore(redis)
        if "error" in data:
            if "code" in data or data["error"] not in {"login_required", "interaction_required"}:
                raise InvalidBridgeState()
            _, transaction = await store.browser_transaction(state, browser)
            _same_source_origin(request, transaction)
            _, _, authorization = await _pair(transaction, db)
            await store.cancel(state, browser)
            return _failure(authorization, data["error"])
        bound = await store.bound(state, data.get("code", ""), browser)
        _same_source_origin(request, bound.transaction)
        _, _, authorization = await _pair(bound.transaction, db)
        try:
            await recheck_source_proof(db, redis, bound.proof)
        except InvalidSessionProof:
            await store.cancel(state, browser)
            return _failure(authorization, "interaction_required")
        # Cross-site POST does not carry explicit-Lax issuer auth cookies. It
        # approves refs only; current identity comparison belongs to the safe GET.
        approved = await store.approve(bound)
        response = RedirectResponse(FINAL_PATH, status_code=303, headers=HEADERS)
        response.delete_cookie(COOKIE, path="/", secure=True, httponly=True, samesite="none")
        response.set_cookie(
            FINAL_COOKIE,
            approved.code,
            max_age=max(0, approved.expires_at - int(time.time())),
            path="/",
            secure=True,
            httponly=True,
            samesite="lax",
        )
        return response
    except (InvalidBridgeState, ValueError, TypeError, UnicodeError):
        raise HTTPException(400, "Invalid session continuation") from None


@router.get("/finalize")
async def finalize(
    request: Request,
    db: AsyncSession = Depends(get_db),
    redis: ResilientRedisClient = Depends(get_redis),
):
    _enabled()
    try:
        # No public transaction, source code or caller-supplied grant is accepted.
        if request.query_params or request.headers.get("sec-fetch-dest") not in (
            None,
            "",
            "document",
        ):
            raise InvalidBridgeState()
        store = BridgeStateStore(redis)
        approved = await store.approved(request.cookies.get(FINAL_COOKIE, ""))
        try:
            _, _, authorization = await _pair(approved.transaction, db)
        except (InvalidBridgeState, ValueError, TypeError):
            await store.consume_approval(approved)
            return _clear(
                JSONResponse(
                    {"detail": "Invalid session continuation"}, status_code=400, headers=HEADERS
                )
            )
        try:
            user, parent = await recheck_source_proof(db, redis, approved.proof)
            held = await _existing_identities(request, db, redis)
            if held - {str(user.id)}:
                raise InvalidSessionProof()
        except InvalidSessionProof:
            await store.consume_approval(approved)
            return _failure(authorization, "interaction_required")
        await store.consume_approval(approved)
        response = RedirectResponse(
            "/api/v1/oauth/authorize?" + urlencode(authorization), status_code=303, headers=HEADERS
        )
        if not set_sso_cookie(response, str(user.id), parent):
            raise InvalidBridgeState()
        return _clear(response)
    except (InvalidBridgeState, ValueError, TypeError):
        raise HTTPException(400, "Invalid session continuation", headers=HEADERS) from None
