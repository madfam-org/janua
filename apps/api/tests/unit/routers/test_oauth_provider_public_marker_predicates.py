"""The two pure predicates janua#833 added for marked public clients.

``test_oauth_provider_public_first_party.py`` drives ``/oauth/authorize`` end to
end with clients named without a first-party prefix. These pin the branches it
does not reach:

- a PUBLIC client named ``madfam-*`` / ``selva-office*`` is never first-party
  without the marker, and an inactive marked client is not marked;
- ``_public_first_party_refusal`` has no loopback-port leniency (the general
  redirect check accepts another port on ``localhost``; this rule does not).
"""

from __future__ import annotations

import base64
import hashlib
import secrets
from types import SimpleNamespace

import pytest

from app.core.reserved_oauth_boundaries import SILENT_AUTH_SCOPE
from app.routers.v1.oauth_provider import (
    _is_marked_public_client,
    _public_first_party_refusal,
)

LOOPBACK = "http://localhost:3000/auth/callback"
HTTPS = "https://app.example.test/auth/callback"


def _client(*, name="app-web", active=True, confidential=False, scopes=None, uris=None):
    return SimpleNamespace(
        client_id="jnc_fixture",
        name=name,
        is_active=active,
        is_confidential=confidential,
        allowed_scopes=scopes if scopes is not None else ["openid", "profile", SILENT_AUTH_SCOPE],
        redirect_uris=uris if uris is not None else [HTTPS],
    )


def _challenge() -> str:
    verifier = secrets.token_urlsafe(48)
    digest = hashlib.sha256(verifier.encode()).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode()


@pytest.mark.parametrize("name", ["madfam-web", "selva-office-web", "MADFAM-web"])
def test_a_first_party_name_never_marks_a_public_client(name):
    assert not _is_marked_public_client(_client(name=name, scopes=["openid", "profile"]))


def test_the_marker_marks_an_active_public_client_only():
    assert _is_marked_public_client(_client())
    assert not _is_marked_public_client(_client(active=False))
    assert not _is_marked_public_client(_client(confidential=True))


def test_exact_registered_uri_with_explicit_s256_passes():
    client = _client()
    assert (
        _public_first_party_refusal(
            client,
            redirect_uri=HTTPS,
            requested_scope="openid profile",
            code_challenge=_challenge(),
            code_challenge_method="S256",
        )
        is None
    )


@pytest.mark.parametrize(
    "requested",
    ["http://localhost:4000/auth/callback", "http://127.0.0.1:3000/auth/callback"],
    ids=["another port", "loopback alias"],
)
def test_no_loopback_leniency(requested):
    client = _client(uris=[LOOPBACK])
    assert _public_first_party_refusal(
        client,
        redirect_uri=requested,
        requested_scope="openid",
        code_challenge=_challenge(),
        code_challenge_method="S256",
    ) == ("interaction_required", "redirect_uri_not_exact")


def test_pkce_is_checked_before_the_redirect():
    """A request failing both reports PKCE: the order the docs state."""
    assert _public_first_party_refusal(
        _client(),
        redirect_uri=HTTPS + "/",
        requested_scope="openid",
        code_challenge=_challenge(),
        code_challenge_method="s256",
    ) == ("interaction_required", "pkce_s256_required")
