"""Magic-link sessions carry the audience of the product they forward to.

Until 2026-08-15 every magic-link session minted the platform default
audience (`janua.dev`). The first real portal login exchanged its one-time
token successfully and was then rejected by the product's own verifier —
which had no reason to accept an audience naming the platform rather than
itself. The OIDC path has always minted per-client audiences; these tests pin
the magic-link flow doing the same, resolved from the redirect host.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import jwt as pyjwt
import pytest

from app.routers.v1.auth import _session_audience_for_redirect
from app.services.auth_service import AuthService


def _db_returning(clients):
    result = SimpleNamespace(scalars=lambda: iter(clients))
    return SimpleNamespace(execute=AsyncMock(return_value=result))


def _client(audience, uris):
    return SimpleNamespace(audience=audience, redirect_uris=uris, is_active=True)


@pytest.mark.asyncio
async def test_resolves_audience_by_redirect_host_not_full_uri():
    """The magic-link redirect (/portal/verify) is not an OAuth callback path;
    the HOST is what names the product."""
    db = _db_returning(
        [
            _client("nauta-api", ["https://nauta.madfam.io/api/auth/callback/janua"]),
            _client("nauta-portal", ["https://crea.madfam.io/api/auth/callback/janua"]),
        ]
    )
    audience = await _session_audience_for_redirect(
        db, "https://crea.madfam.io/portal/verify"
    )
    assert audience == "nauta-portal"


@pytest.mark.asyncio
async def test_double_encoded_redirect_uris_still_resolve():
    """Some prod rows store redirect_uris as a JSON string CONTAINING the
    array (both nauta clients did, 2026-08-15). Iterating that string yields
    characters; the resolver must decode it or silently match nothing."""
    db = _db_returning(
        [_client("nauta-portal", '["https://crea.madfam.io/api/auth/callback/janua"]')]
    )
    audience = await _session_audience_for_redirect(
        db, "https://crea.madfam.io/portal/verify"
    )
    assert audience == "nauta-portal"


@pytest.mark.asyncio
async def test_unknown_host_keeps_the_platform_default():
    db = _db_returning([_client("nauta-portal", ["https://crea.madfam.io/cb"])])
    assert await _session_audience_for_redirect(db, "https://other.example.com/x") is None


@pytest.mark.asyncio
async def test_no_redirect_means_no_override():
    db = _db_returning([])
    assert await _session_audience_for_redirect(db, None) is None
    db.execute.assert_not_awaited()


def test_access_token_carries_the_override_audience():
    token, _jti, _exp = AuthService.create_access_token(
        user_id="u-1", tenant_id="t-1", email="a@b.test", audience="nauta-portal"
    )
    claims = pyjwt.decode(token, options={"verify_signature": False}, algorithms=["HS256", "RS256"])
    assert claims["aud"] == "nauta-portal"


def test_access_token_without_override_keeps_the_platform_default():
    from app.config import settings

    token, _jti, _exp = AuthService.create_access_token(
        user_id="u-1", tenant_id="t-1", email="a@b.test"
    )
    claims = pyjwt.decode(token, options={"verify_signature": False}, algorithms=["HS256", "RS256"])
    assert claims["aud"] == settings.JWT_AUDIENCE


def test_both_magic_link_paths_resolve_the_audience():
    """Source-level pin: verify and callback must BOTH pass the resolved
    audience into create_session — a session from either door is the same
    session."""
    import inspect

    from app.routers.v1 import auth

    for handler in (auth.magic_link_callback, auth.verify_magic_link):
        source = inspect.getsource(handler)
        assert "_session_audience_for_redirect" in source, handler.__name__
