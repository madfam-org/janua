"""Rebuilding a pending ``/oauth/authorize`` request after the hosted login.

``GET /oauth/authorize`` stores the request under ``oauth:pre_login:<id>``
before sending an unauthenticated browser to the login page; every path that
signs the person in (password form, second factor, emailed link, and the
protected-resource resume URL) rebuilds the authorize URL from that record.
They share this list so a parameter added to the authorize request — such as
the RFC 8707 ``resource`` — survives every one of them.
"""

from __future__ import annotations

from typing import Any, Mapping

AUTHORIZE_RESUME_PARAMS = (
    "response_type",
    "client_id",
    "redirect_uri",
    "scope",
    "state",
    "nonce",
    "code_challenge",
    "code_challenge_method",
    "resource",
)


def authorize_query(stored: Mapping[str, Any]) -> dict[str, Any]:
    """The authorize query parameters to resume, from a pre-login record."""
    return {key: stored[key] for key in AUTHORIZE_RESUME_PARAMS if stored.get(key) is not None}


def is_resource_bound(stored: Mapping[str, Any]) -> bool:
    """Whether the pending request names a protected resource (RFC 8707)."""
    return bool(stored.get("resource"))
