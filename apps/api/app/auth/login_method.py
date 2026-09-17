"""Which method the hosted login page offers first.

The hosted login page (GET /api/v1/auth/login) is where an OAuth ``/authorize``
sends a browser that holds no Janua session. Historically it rendered one
thing: an email + password form. Janua has had a complete passwordless path
for as long (POST /api/v1/auth/magic-link, the emailed callback, first-contact
user creation), but the hosted page never offered it — so a public PKCE client
whose users hold no password (the Yantra4D Studio, 2026-09-17) could send them
nowhere useful.

Precedence, resolved by ``effective_login_method``:

1. the request — ``login_method=`` on ``/authorize`` (stored with the pre-login
   request and carried to the login page), or on the login page itself;
2. the deployment — ``HOSTED_LOGIN_DEFAULT_METHOD`` (``password`` unless an
   operator flips it, so no existing product's login changes by this module);
3. ``password``.

Magic link is only ever OFFERED when the deployment can send mail; otherwise
the page falls back to the password form rather than rendering a form whose
submit can only fail. Values are normalised, never rejected: an unknown value
falls through to the next tier instead of failing a sign-in over a hint.
"""

from __future__ import annotations

from typing import Optional

from app.config import settings

LOGIN_METHOD_MAGIC_LINK = "magic_link"
LOGIN_METHOD_PASSWORD = "password"
LOGIN_METHODS = frozenset({LOGIN_METHOD_MAGIC_LINK, LOGIN_METHOD_PASSWORD})


def normalize_login_method(value: Optional[str]) -> Optional[str]:
    """Canonical method name, or None for anything unknown."""
    if not isinstance(value, str):
        return None
    candidate = value.strip().lower().replace("-", "_")
    return candidate if candidate in LOGIN_METHODS else None


def magic_link_login_available() -> bool:
    """The same two switches POST /magic-link gates on."""
    return bool(settings.ENABLE_MAGIC_LINKS and settings.EMAIL_ENABLED)


def effective_login_method(requested: Optional[str]) -> str:
    """Resolve the method the hosted page renders first (see module docstring)."""
    method = (
        normalize_login_method(requested)
        or normalize_login_method(getattr(settings, "HOSTED_LOGIN_DEFAULT_METHOD", None))
        or LOGIN_METHOD_PASSWORD
    )
    if method == LOGIN_METHOD_MAGIC_LINK and not magic_link_login_available():
        return LOGIN_METHOD_PASSWORD
    return method
