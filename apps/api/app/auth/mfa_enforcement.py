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

from datetime import datetime, timedelta

import jwt as pyjwt

from app.config import settings

MFA_CHALLENGE_TYPE = "mfa_challenge"
_CHALLENGE_TTL_MINUTES = 5


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


def mfa_enrolled(user) -> bool:
    """True when the user has MFA configured (enabled with a secret).

    Paths that already have a second-factor step (JSON /signin and the hosted
    password form) challenge enrolled users regardless of MFA_ENFORCE_ON_LOGIN.
    """
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
        settings.JWT_SECRET_KEY or "development-secret-key",
        algorithm="HS256",
    )
