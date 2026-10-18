"""Shared MFA-enforcement gate for the login paths.

2026-08-23 security fix. The completeness audit found MFA was enforced on exactly
ONE path (the JSON `/signin` endpoint) while the OAuth browser login, the OAuth
`/authorize` flow, and magic-link login all issued full sessions WITHOUT checking
`mfa_enabled` — so a user who "enabled 2FA" was unprotected on every path a real
product uses through Janua. This module centralizes the decision so every login
path enforces MFA identically, and gates it behind a DEFAULT-OFF flag so shipping
the enforcement cannot lock anyone out before the MFA-challenge UI is live.

Usage in a login path, immediately before it would create a session:

    if mfa_required_for(user):
        return mfa_challenge_response(user)   # JSON callers
        # or: redirect back to the login UI with ?mfa_required=1 (browser flow)

The challenge token this mints is consumed by POST /api/v1/mfa/challenge/verify,
which already exists and issues the real session once the second factor checks.
"""

from __future__ import annotations

import hashlib
import hmac
from datetime import datetime, timedelta

import jwt as pyjwt

from app.config import settings

MFA_CHALLENGE_TYPE = "mfa_challenge"
_CHALLENGE_TTL_MINUTES = 5

# The value config.py substitutes for an unset JWT_SECRET_KEY outside
# production. It is published in this repository, so it is never a signing key.
_DEV_DEFAULT_SECRET = "development-secret-key"
_DEV_ENVIRONMENTS = {"development", "test", "testing", "local"}


def mfa_challenge_signing_key() -> str:
    """The HS256 key for MFA challenge tokens (mint and verify).

    Uses JWT_SECRET_KEY when it is configured. When it is unset (RS256-only
    deployments do not need it for sessions), the key is derived from
    SECRET_KEY, which production requires. Only a development or test
    environment with neither configured falls back to the development default;
    anywhere else this raises rather than sign with a known value.
    """
    configured = settings.JWT_SECRET_KEY
    if configured and configured != _DEV_DEFAULT_SECRET:
        return configured
    app_secret = settings.SECRET_KEY
    if app_secret:
        return hmac.new(
            app_secret.encode("utf-8"), b"janua.mfa_challenge.v1", hashlib.sha256
        ).hexdigest()
    environment = str(getattr(settings, "ENVIRONMENT", "") or "").lower()
    if environment in _DEV_ENVIRONMENTS:
        return _DEV_DEFAULT_SECRET
    raise RuntimeError("No signing key is configured for MFA challenge tokens")


def mfa_required_for(user) -> bool:
    """True iff this login should be interrupted for a second factor.

    Requires BOTH the global enforcement flag (default OFF — see
    settings.MFA_ENFORCE_ON_LOGIN) and the user actually having MFA configured.
    When the flag is off, this always returns False and every login path behaves
    exactly as it did before this change. A per-org "require MFA" policy can be
    layered on top later (it would make this return True even for a user who has
    not yet enrolled — a separate, enrollment-forcing flow).
    """
    if not getattr(settings, "MFA_ENFORCE_ON_LOGIN", False):
        return False
    return bool(getattr(user, "mfa_enabled", False) and getattr(user, "mfa_secret", None))


def mint_mfa_challenge_token(user) -> str:
    """Mint a short-lived challenge token (NOT a session token).

    Identical shape to the one the JSON /signin path already issues, so
    /mfa/challenge/verify accepts it unchanged: {sub, type:"mfa_challenge", exp,
    iat, iss}, HS256 over JWT_SECRET_KEY.
    """
    payload = {
        "sub": str(user.id),
        "type": MFA_CHALLENGE_TYPE,
        "exp": datetime.utcnow() + timedelta(minutes=_CHALLENGE_TTL_MINUTES),
        "iat": datetime.utcnow(),
        "iss": settings.JWT_ISSUER,
    }
    return pyjwt.encode(
        payload,
        mfa_challenge_signing_key(),
        algorithm="HS256",
    )
