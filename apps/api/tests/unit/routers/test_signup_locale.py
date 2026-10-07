"""Signup paths must record the requester's language.

`users.locale` has existed since 000_init but no creation path ever wrote it,
so it was NULL for every row. These tests pin the capture at each path where a
User is constructed from an HTTP request.
"""

import uuid
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from starlette.requests import Request

import app.routers.v1.auth as auth_mod
from app.routers.v1.auth import MagicLinkRequest, SignUpRequest, send_magic_link, sign_up

pytestmark = pytest.mark.asyncio


def _request(accept_language=None):
    headers = [(b"user-agent", b"pytest")]
    if accept_language is not None:
        headers.append((b"accept-language", accept_language.encode()))
    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/v1/auth/signup",
            "headers": headers,
            "client": ("198.51.100.7", 51234),
        }
    )


def _db():
    """Async session that reports "nothing exists yet" for every lookup.

    `refresh` stands in for the round-trip that would normally apply server
    defaults, so the route can shape its response. It deliberately does not
    touch `locale`: that value must come from the request, and letting the
    fake database supply one would hide the very thing under test.
    """
    db = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none = MagicMock(return_value=None)
    db.execute = AsyncMock(return_value=result)
    db.add = MagicMock()
    db.commit = AsyncMock()

    async def refresh(obj, *args, **kwargs):
        for column, default in (
            ("id", uuid.uuid4()),
            ("email_verified", False),
            ("is_admin", False),
            ("mfa_enabled", False),
            ("created_at", datetime.utcnow()),
            ("updated_at", datetime.utcnow()),
        ):
            if getattr(obj, column, None) is None:
                setattr(obj, column, default)

    db.refresh = AsyncMock(side_effect=refresh)
    return db


def _added_users(db):
    """Users handed to db.add(), which is where every creation path puts them.

    Intercepting db.add rather than the User symbol matters: these code paths
    also use User inside SQLAlchemy select()/query() expressions, and swapping
    the name there breaks the query rather than observing it.
    """
    from app.models import User

    return [
        call.args[0]
        for call in db.add.call_args_list
        if call.args and isinstance(call.args[0], User)
    ]


def _only_locale(db):
    users = _added_users(db)
    assert len(users) == 1, f"expected one User, got {len(users)}"
    return users[0].locale


async def _signup(accept_language=None, body_locale=None):
    db = _db()
    # Session creation reaches for Redis, which is out of scope here — the
    # assertion is about the User handed to db.add, which happens first.
    session_stub = AsyncMock(return_value=("access", "refresh", MagicMock()))
    with (
        patch.object(auth_mod.settings, "ENABLE_SIGNUPS", True),
        patch.object(auth_mod.AuthService, "create_session", session_stub),
    ):
        await sign_up(
            request=_request(accept_language),
            signup_data=SignUpRequest(
                email="new@example.com", password="Str0ng!Passw0rd", locale=body_locale
            ),
            background_tasks=MagicMock(),
            db=db,
        )
    return _only_locale(db)


async def _magic(accept_language=None):
    db = _db()
    with (
        patch.object(auth_mod.settings, "ENABLE_MAGIC_LINKS", True),
        patch.object(auth_mod.settings, "EMAIL_ENABLED", True),
    ):
        await send_magic_link(
            request=_request(accept_language),
            magic_link_data=MagicLinkRequest(email="new@example.com"),
            background_tasks=MagicMock(),
            db=db,
        )
    return _only_locale(db)


class TestSignup:
    async def test_header_captured(self):
        assert await _signup("es-MX,es;q=0.9,en;q=0.5") == "es"

    async def test_english_header(self):
        assert await _signup("en-GB,en;q=0.9") == "en"

    async def test_no_header(self):
        # Must succeed and leave NULL so the configured default applies.
        assert await _signup(None) is None

    async def test_unsupported_not_stored(self):
        assert await _signup("fr-CA,fr;q=0.9,de;q=0.8") is None

    async def test_body_wins(self):
        assert await _signup("en-US", body_locale="es-MX") == "es"

    async def test_bad_body_falls_back(self):
        # An unsupported body value must not 422 the signup, nor shadow a
        # usable header.
        assert await _signup("es-MX", body_locale="fr-CA") == "es"


class TestMagicLink:
    async def test_header_captured(self):
        assert await _magic("es-MX,es;q=0.9") == "es"

    async def test_no_header(self):
        assert await _magic(None) is None

    async def test_unsupported_not_stored(self):
        assert await _magic("de-DE,de;q=0.9") is None


class TestOauth:
    """OAuth account creation, where the provider may assert a locale."""

    async def _run(self, claims, locale=None):
        from app.models import OAuthProvider
        from app.services.oauth import OAuthService

        # `find_or_create_user` runs on the request's AsyncSession (2026-09-06):
        # every lookup answers "nothing exists yet", so the create branch runs.
        db = MagicMock()
        nothing = MagicMock()
        nothing.scalar_one_or_none.return_value = None
        nothing.scalars.return_value.first.return_value = None
        db.execute = AsyncMock(return_value=nothing)
        db.add = MagicMock()
        db.flush = AsyncMock()
        db.commit = AsyncMock()

        await OAuthService.find_or_create_user(
            db,
            OAuthProvider.GOOGLE,
            {
                "provider_user_id": "g-1",
                "email": "new@example.com",
                "email_verified": True,
                "raw_data": claims,
            },
            {"access_token": "t"},
            locale=locale,
        )
        return _only_locale(db)

    async def test_provider_claim_wins(self):
        # A user's language on their Google account beats today's browser.
        assert await self._run({"locale": "es-MX"}, locale="en") == "es"

    async def test_header_fallback(self):
        assert await self._run({}, locale="es") == "es"

    async def test_unsupported_claim(self):
        # An untranslatable claim must not shadow the usable header value.
        assert await self._run({"locale": "fr-CA"}, locale="es") == "es"

    async def test_nothing(self):
        assert await self._run({}, locale=None) is None


class TestInviteAccept:
    """A user created by redeeming an invitation."""

    def _run(self, locale):
        from app.services.invitation_service import InvitationService

        invitation = SimpleNamespace(
            id="inv-1",
            email="new@example.com",
            organization_id="org-1",
            role="member",
            status="pending",
            token="tok",
            expires_at=None,
            is_valid=True,
            is_expired=False,
            accepted_at=None,
        )

        db = MagicMock()
        found = MagicMock()
        found.scalars.return_value.first.return_value = invitation
        # invitation by token, then its organization (none here)
        none = MagicMock()
        none.scalars.return_value.first.return_value = None
        db.execute = AsyncMock(side_effect=[found, none])
        db.flush = AsyncMock()
        db.commit = AsyncMock()

        service = InvitationService(db)
        service.cache = MagicMock()
        service.cache.delete = AsyncMock()
        service.audit_logger = MagicMock()
        service.audit_logger.log = AsyncMock()
        return service, db, invitation

    async def test_locale_stored(self):
        service, db, _ = self._run("es")
        await service.accept_invitation(
            token="tok",
            user=None,
            new_user_data={"name": "New Person", "password_hash": "x"},
            locale="es",
        )
        assert _only_locale(db) == "es"

    async def test_no_locale(self):
        service, db, _ = self._run(None)
        await service.accept_invitation(
            token="tok",
            user=None,
            new_user_data={"name": "New Person", "password_hash": "x"},
            locale=None,
        )
        assert _only_locale(db) is None
