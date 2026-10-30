"""Shared MFA challenge signing and enrollment detection.

Voluntary enrollment is enforced on every login method. Organization policy
and live session assurance are resolved by authentication_assurance.py.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

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
    """Legacy synchronous enrollment predicate; organization policy is asynchronous."""
    # Voluntary enrollment is always enforced, including magic-link and SSO entry.
    return mfa_enrolled(user)


def mfa_enrolled(user) -> bool:
    """True when the user has MFA configured (enabled with a secret).

    All primary-factor paths challenge enrolled users regardless of the legacy
    MFA_ENFORCE_ON_LOGIN flag.
    """
    return bool(getattr(user, "mfa_enabled", False) and getattr(user, "mfa_secret", None))


def mint_mfa_challenge_token(user, *, methods=None, audience=None, authenticated_at=None) -> str:
    """Mint a short-lived challenge token (NOT a session token).

    Identical shape to the one the JSON /signin path already issues, so
    /mfa/challenge/verify accepts it unchanged: {sub, type:"mfa_challenge", exp,
    iat, iss}, HS256 over JWT_SECRET_KEY.
    """
    payload = {
        "sub": str(user.id),
        "type": MFA_CHALLENGE_TYPE,
        "jti": secrets.token_urlsafe(24),
        "amr": list(methods or ["pwd"]),
        "auth_time": (
            authenticated_at
            if authenticated_at is not None
            else int(datetime.now(timezone.utc).timestamp())
        ),
        "audience": audience,
        "exp": datetime.utcnow() + timedelta(minutes=_CHALLENGE_TTL_MINUTES),
        "iat": datetime.utcnow(),
        "iss": settings.JWT_ISSUER,
    }
    return pyjwt.encode(
        payload,
        mfa_challenge_signing_key(),
        algorithm="HS256",
    )
