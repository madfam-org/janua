"""Tokens Janua mints for protected resources (RFC 8707 audience binding).

Access token — an RFC 9068 JWT, verifiable with the public JWKS:

- header ``typ: at+jwt``, ``alg: RS256``, ``kid`` (the JWKS key);
- ``iss`` = the discovery issuer, ``aud`` = the resource URI exactly,
  ``sub`` = the person's Janua user id (the same ``sub`` as their ID token and
  every other Janua token), ``client_id``, ``scope`` (resource scopes only),
  ``iat``, ``exp`` (the resource's access-token lifetime, at most 15 minutes)
  and a unique ``jti``.
- Deliberately NO Janua ``type`` claim and no email, roles or organization
  claims: every Janua verifier of its own session tokens requires
  ``type == "access"``, so a token minted for a resource can never be replayed
  as a Janua (or MAP) session, and the resource learns only who and what.

Refresh token — read only by Janua's token endpoint:

- ``type: resource_refresh`` (Janua's own ``/auth/refresh`` and the plain OIDC
  refresh grant require ``type == "refresh"``, so they refuse it), ``aud`` =
  the issuer, plus the bound ``resource``, ``client_id``, granted ``scope``,
  the rotation ``family`` and ``family_iat`` (when the person consented).
- Single use: the first redemption marks its ``jti`` used in Redis
  (``SET NX``); a second redemption of the same token is reuse, which revokes
  the whole family (RFC 6819 §5.2.2.3, OAuth 2.1 §4.3.1) — the attacker's and
  the client's tokens alike — and answers ``invalid_grant``.
- Lifetime: ``refresh_token_idle_seconds`` from its own issue, never past
  ``family_iat + refresh_token_max_lifetime_seconds``.
"""

from __future__ import annotations

import secrets
import time
from dataclasses import dataclass
from typing import Any, Optional, Sequence

from app.core.jwt_manager import jwt_manager
from app.core.oauth_metadata import oauth_issuer
from app.core.protected_resources import OFFLINE_ACCESS_SCOPE, ProtectedResource

ACCESS_TOKEN_JWT_TYPE = "at+jwt"
REFRESH_TOKEN_TYPE = "resource_refresh"
USED_REFRESH_KEY_PREFIX = "oauth:resource_rt_used:"


@dataclass(frozen=True)
class MintedAccessToken:
    token: str
    jti: str
    expires_in: int


def mint_access_token(
    *,
    resource: ProtectedResource,
    subject: str,
    client_id: str,
    scopes: Sequence[str],
    now: Optional[int] = None,
) -> MintedAccessToken:
    issued_at = int(now if now is not None else time.time())
    jti = secrets.token_urlsafe(24)
    ttl = resource.access_token_ttl_seconds
    claims = {
        "iss": oauth_issuer(),
        "sub": subject,
        "aud": resource.resource,
        "exp": issued_at + ttl,
        "iat": issued_at,
        "jti": jti,
        "client_id": client_id,
        "scope": " ".join(scope for scope in scopes if scope != OFFLINE_ACCESS_SCOPE),
    }
    return MintedAccessToken(
        token=jwt_manager.encode_token(claims, typ=ACCESS_TOKEN_JWT_TYPE),
        jti=jti,
        expires_in=ttl,
    )


def refresh_token_expiry(resource: ProtectedResource, *, issued_at: int, family_iat: int) -> int:
    return min(
        issued_at + resource.refresh_token_idle_seconds,
        family_iat + resource.refresh_token_max_lifetime_seconds,
    )


def mint_refresh_token(
    *,
    resource: ProtectedResource,
    subject: str,
    client_id: str,
    scope: str,
    family: Optional[str] = None,
    family_iat: Optional[int] = None,
    now: Optional[int] = None,
) -> str:
    issued_at = int(now if now is not None else time.time())
    family_started = int(family_iat if family_iat is not None else issued_at)
    issuer = oauth_issuer()
    claims = {
        "iss": issuer,
        "sub": subject,
        "aud": issuer,
        "exp": refresh_token_expiry(resource, issued_at=issued_at, family_iat=family_started),
        "iat": issued_at,
        "jti": secrets.token_urlsafe(32),
        "type": REFRESH_TOKEN_TYPE,
        "client_id": client_id,
        "resource": resource.resource,
        "scope": scope,
        "family": family or secrets.token_urlsafe(16),
        "family_iat": family_started,
    }
    return jwt_manager.encode_token(claims)


def verify_refresh_token(token: str) -> Optional[dict[str, Any]]:
    """The claims of a valid, unexpired resource refresh token, else None.

    Revocation and single use are checked by the caller (they need Redis).
    """
    if not isinstance(token, str) or not token:
        return None
    issuer = oauth_issuer()
    claims = jwt_manager.decode_verified(token, issuer=issuer, audience=issuer)
    if not claims or claims.get("type") != REFRESH_TOKEN_TYPE:
        return None
    for key in ("client_id", "resource", "scope", "family", "sub", "jti"):
        if not isinstance(claims.get(key), str) or not claims.get(key):
            return None
    if not isinstance(claims.get("family_iat"), int):
        return None
    return claims


def looks_like_resource_refresh_token(token: Optional[str]) -> bool:
    """Unverified peek: is this one of ours (routing only, never authorization)?"""
    if not isinstance(token, str) or token.count(".") != 2:
        return False
    try:
        claims = jwt_manager.get_unverified_claims(token)
    except Exception:
        return False
    return isinstance(claims, dict) and claims.get("type") == REFRESH_TOKEN_TYPE


def verify_access_token(token: str, resource: ProtectedResource) -> Optional[dict[str, Any]]:
    """Verify a resource access token the way a resource server must (for tests,
    revocation and documentation): RFC 9068 ``typ``, signature, ``iss``,
    ``aud`` = the resource, expiry."""
    try:
        header = jwt_manager.get_unverified_header(token)
    except Exception:
        return None
    if str(header.get("typ", "")).lower() not in (ACCESS_TOKEN_JWT_TYPE, "application/at+jwt"):
        return None
    claims = jwt_manager.decode_verified(
        token,
        issuer=oauth_issuer(),
        audience=resource.resource,
        required_claims=("exp", "iat", "iss", "aud", "sub", "jti", "client_id"),
    )
    if not claims or "type" in claims:
        return None
    return claims
