"""Validate source proof against an existing revocable issuer session.

Client authentication/registration and browser binding belong to the route/store.
This module never creates a session, rotates a token, or changes authentication evidence.
"""

from __future__ import annotations

import hashlib
import json
import time
from datetime import timezone
from typing import Any
from uuid import UUID

import jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.authentication_assurance import (
    has_mfa_assurance,
    session_assurance,
    user_requires_mfa,
)
from app.auth.sso_cookie import resolve_session_by_id
from app.core.jwt_manager import jwt_manager
from app.core.redis_circuit_breaker import ResilientRedisClient
from app.models import Session, User
from app.services import token_revocation


class InvalidSessionProof(ValueError):
    """A generic refusal; credentials and identity must never enter error text."""


def _required_string(value: Any) -> str:
    if not isinstance(value, str) or not value:
        raise InvalidSessionProof()
    return value


def _assurance_hash(session: Any) -> str:
    evidence = session_assurance(session)
    bound = {key: evidence.get(key) for key in ("sid", "amr", "auth_time", "mfa_time")}
    return hashlib.sha256(
        json.dumps(bound, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _session_expiry(session: Any) -> int:
    expiry = session.expires_at
    if expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=timezone.utc)
    return int(expiry.timestamp())


def _decode(token: str, token_type: str, audience: str) -> dict[str, Any]:
    try:
        # No HS fallback or audience derived from the token's own untrusted claims.
        if jwt.get_unverified_header(token).get("alg") != "RS256":
            raise InvalidSessionProof()
    except (jwt.InvalidTokenError, TypeError, ValueError):
        raise InvalidSessionProof() from None
    try:
        claims = jwt_manager.verify_token(token, token_type=token_type, audience=audience)
    except (jwt.InvalidTokenError, TypeError, ValueError, OverflowError):
        raise InvalidSessionProof() from None
    if not isinstance(claims, dict):
        raise InvalidSessionProof()
    for key in ("sub", "jti"):
        _required_string(claims.get(key))
    try:
        UUID(claims["sub"])
    except (ValueError, TypeError, AttributeError):
        raise InvalidSessionProof() from None
    if type(claims.get("exp")) is not int or claims["exp"] <= time.time():
        raise InvalidSessionProof()
    return claims


async def verify_source_proof(
    db: AsyncSession,
    redis: ResilientRedisClient,
    *,
    source_client_id: str,
    source_audience: str,
    access_token: str | None = None,
    refresh_token: str | None = None,
) -> dict[str, Any]:
    """Caller has authenticated the active confidential first-party source client.

    Direct credentials must be current in the parent row. An OIDC grant needs
    a signed revocable sid plus its refresh credential; an access JWT alone is
    insufficient. OAuth grants have no stored-current rotation ledger here.
    """
    _required_string(source_client_id)
    _required_string(source_audience)
    supplied = [
        (kind, token)
        for kind, token in (("access", access_token), ("refresh", refresh_token))
        if token is not None
    ]
    if not supplied:
        raise InvalidSessionProof()
    verified = [
        (kind, _decode(_required_string(token), kind, source_audience)) for kind, token in supplied
    ]
    for kind, claims in verified:
        if await token_revocation.is_revoked(redis, claims, kind):
            raise InvalidSessionProof()
    oidc = any(claims.get("client_id") is not None for _, claims in verified)
    if oidc:
        if refresh_token is None or any(
            claims.get("client_id") != source_client_id for _, claims in verified
        ):
            raise InvalidSessionProof()
        primary_kind, primary = next(
            (kind, claims) for kind, claims in verified if kind == "refresh"
        )
        sid = _required_string(primary.get("sid"))
        _required_string(primary.get("family"))
    else:
        primary_kind, primary = verified[-1]
        column = (
            Session.refresh_token_jti if primary_kind == "refresh" else Session.access_token_jti
        )
        result = await db.execute(select(Session).where(column == primary["jti"]))
        parent = result.scalar_one_or_none()
        if parent is None:
            raise InvalidSessionProof()
        sid = str(parent.id)
    user, parent = await resolve_session_by_id(sid, db)
    if user is None or parent is None:
        raise InvalidSessionProof()
    evidence = session_assurance(parent)
    parent_family = _required_string(parent.refresh_token_family)
    if await token_revocation.is_revoked(redis, {"family": parent_family}, "refresh"):
        raise InvalidSessionProof()
    for kind, claims in verified:
        if claims["sub"] != str(user.id):
            raise InvalidSessionProof()
        if claims.get("sid") is not None and claims["sid"] != str(parent.id):
            raise InvalidSessionProof()
        if oidc:
            # No missing sid or invented/stronger assurance on an OAuth grant.
            if claims.get("sid") != str(parent.id) or "amr" not in claims:
                raise InvalidSessionProof()
            if any(
                claims.get(key) != evidence.get(key) for key in ("amr", "auth_time", "mfa_time")
            ):
                raise InvalidSessionProof()
        else:
            current = parent.refresh_token_jti if kind == "refresh" else parent.access_token_jti
            if claims["jti"] != current:
                raise InvalidSessionProof()
            if claims.get("family") is not None and claims["family"] != parent_family:
                raise InvalidSessionProof()
            if any(
                key in claims and claims[key] != evidence.get(key)
                for key in ("amr", "auth_time", "mfa_time")
            ):
                raise InvalidSessionProof()
    if await user_requires_mfa(db, user) and not has_mfa_assurance(evidence):
        raise InvalidSessionProof()
    return {
        "user_id": str(user.id),
        "session_id": str(parent.id),
        "parent_family": parent_family,
        "proof_jti": primary["jti"],
        "proof_family": primary.get("family") or parent_family,
        "proof_type": primary_kind,
        "proof_kind": "oidc" if oidc else "direct",
        "source_client_id": source_client_id,
        "assurance_hash": _assurance_hash(parent),
        "expires_at": min(_session_expiry(parent), *(claims["exp"] for _, claims in verified)),
    }


async def recheck_source_proof(
    db: AsyncSession, redis: ResilientRedisClient, proof: dict[str, Any]
) -> tuple[User, Session]:
    """Recheck only stored validated references, immediately before atomic consume."""
    if type(proof.get("expires_at")) is not int or proof["expires_at"] <= time.time():
        raise InvalidSessionProof()
    user, parent = await resolve_session_by_id(proof.get("session_id"), db)
    if user is None or parent is None or str(user.id) != proof.get("user_id"):
        raise InvalidSessionProof()
    if parent.refresh_token_family != proof.get("parent_family") or _assurance_hash(
        parent
    ) != proof.get("assurance_hash"):
        raise InvalidSessionProof()
    kind = proof.get("proof_type")
    if kind not in ("access", "refresh") or proof.get("proof_kind") not in ("direct", "oidc"):
        raise InvalidSessionProof()
    if proof["proof_kind"] == "direct":
        current = parent.refresh_token_jti if kind == "refresh" else parent.access_token_jti
        if current != proof.get("proof_jti"):
            raise InvalidSessionProof()
    elif kind != "refresh":
        raise InvalidSessionProof()
    if await token_revocation.is_revoked(
        redis, {"jti": proof.get("proof_jti"), "family": proof.get("proof_family")}, kind
    ):
        raise InvalidSessionProof()
    if await token_revocation.is_revoked(redis, {"family": parent.refresh_token_family}, "refresh"):
        raise InvalidSessionProof()
    if await user_requires_mfa(db, user) and not has_mfa_assurance(session_assurance(parent)):
        raise InvalidSessionProof()
    return user, parent
