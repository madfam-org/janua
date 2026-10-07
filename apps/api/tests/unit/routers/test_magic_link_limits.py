"""Sign-in link limits: per ADDRESS, plus a per-caller ceiling (2026-10-07).

THE DEFECT. POST /magic-link was limited by slowapi at 5/hour keyed on
`request.client.host`. In production that is the tunnel pod's address for every
public request, and a product's server asks on behalf of all its people. So
the MAP got 5 links per hour for its whole staff. The 6th person got a 429,
the MAP read it as success («Revisa tu correo»), and no email came.

(slowapi is replaced by a no-op MockLimiter in tests/conftest.py, so on main
these routes are not limited at all under test. The tests below therefore fail
on main where they expect a 429, and pass vacuously where they expect none.)

What is pinned here:
  * 6 different addresses from one IP within the hour all get their link;
  * the 6th request for the SAME address gets a 429, whoever asks;
  * the 429 comes before any lookup and reads the same for every address, so it
    never says whether an account exists;
  * the per-caller ceiling is per IP for anonymous callers, resolved only
    through TRUSTED_PROXIES (a spoofed X-Forwarded-For buys nothing), and per
    key for a trusted service, which may name its own visitor's IP.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import fakeredis
import fakeredis.aioredis
import pytest
from fastapi import HTTPException
from starlette.requests import Request

import app.routers.v1.auth as auth_mod
from app.auth import magic_link_limits as limits_mod
from app.models import User, UserStatus
from app.routers.v1.auth import MagicLinkRequest, send_magic_link

pytestmark = pytest.mark.asyncio

TUNNEL_POD = ("10.42.3.17", 51234)  # what client.host is for every public request
SERVICE_KEY = "internal-key-for-tests-only"


def _request(*, client=TUNNEL_POD, headers=None) -> Request:
    raw = [(b"user-agent", b"pytest")]
    for name, value in (headers or {}).items():
        raw.append((name.lower().encode(), value.encode()))
    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/v1/auth/magic-link",
            "headers": raw,
            "client": client,
        }
    )


def _db():
    """A session in which every address already has an ACTIVE account."""
    result = MagicMock()

    def _user():
        return User(
            id=uuid.uuid4(),
            email="placeholder@example.com",
            status=UserStatus.ACTIVE,
            email_verified=True,
        )

    result.scalar_one_or_none = MagicMock(side_effect=lambda: _user())
    result.scalars.return_value.all = MagicMock(return_value=[])
    result.scalars.return_value.__iter__ = lambda self: iter(())
    db = AsyncMock()
    db.execute = AsyncMock(return_value=result)
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.rollback = AsyncMock()

    async def refresh(obj, *args, **kwargs):
        for column, default in (("id", uuid.uuid4()), ("created_at", datetime.utcnow())):
            if getattr(obj, column, None) is None:
                setattr(obj, column, default)

    db.refresh = AsyncMock(side_effect=refresh)
    return db


@pytest.fixture
def store():
    """A real Redis protocol (fakeredis) behind the limiter, empty per test.

    Its own FakeServer: fakeredis instances otherwise share one server per
    process, and counters would leak between tests.
    """
    fake = fakeredis.aioredis.FakeRedis(server=fakeredis.FakeServer(), decode_responses=True)
    with patch.object(limits_mod, "_redis_client", AsyncMock(return_value=fake)):
        yield fake


@pytest.fixture
def mail_on():
    with (
        patch.object(auth_mod.settings, "ENABLE_MAGIC_LINKS", True),
        patch.object(auth_mod.settings, "EMAIL_ENABLED", True),
        patch.object(auth_mod.settings, "INTERNAL_API_KEY", SERVICE_KEY),
        patch.object(auth_mod.settings, "TRUSTED_PROXIES", "127.0.0.1,::1"),
    ):
        yield


async def _ask(email: str, request: Request | None = None, db=None):
    return await send_magic_link(
        request=request or _request(),
        magic_link_data=MagicLinkRequest(email=email),
        background_tasks=MagicMock(),
        db=db or _db(),
    )


# --------------------------------------------------------------------------
# 1. The incident: one server, many people
# --------------------------------------------------------------------------


class TestPerAddress:
    async def test_six_people_from_one_ip_all_get_their_link(self, store, mail_on):
        for n in range(6):
            assert await _ask(f"persona{n}@example.com") == {"message": "Magic link sent to email"}

    async def test_the_sixth_request_for_the_same_address_is_429(self, store, mail_on):
        for _ in range(5):
            await _ask("misma@example.com")
        with pytest.raises(HTTPException) as caught:
            await _ask("misma@example.com")
        assert caught.value.status_code == 429
        assert int(caught.value.headers["Retry-After"]) > 0

    async def test_the_address_is_normalised(self, store, mail_on):
        for variant in ("Misma@Example.com", " misma@example.com", "MISMA@EXAMPLE.COM"):
            await _ask(variant.strip())
        await _ask("misma@example.com")
        await _ask("misma@example.com")
        with pytest.raises(HTTPException) as caught:
            await _ask("misma@Example.COM")
        assert caught.value.status_code == 429

    async def test_the_address_limit_holds_for_a_trusted_service_too(self, store, mail_on):
        service = {"X-Internal-API-Key": SERVICE_KEY}
        for _ in range(5):
            await _ask("misma@example.com", _request(headers=service))
        with pytest.raises(HTTPException) as caught:
            await _ask("misma@example.com", _request(headers=service))
        assert caught.value.status_code == 429


class TestNoEnumeration:
    async def test_429_comes_before_any_lookup_and_reads_the_same(self, store, mail_on):
        details = []
        for email in ("existe@example.com", "no-existe@example.com"):
            for _ in range(5):
                await _ask(email)
            db = _db()
            with pytest.raises(HTTPException) as caught:
                await _ask(email, db=db)
            assert db.execute.await_count == 0, "a limited request must not touch the database"
            assert db.add.call_count == 0
            details.append((caught.value.status_code, caught.value.detail))
        assert details[0] == details[1]

    async def test_the_counter_key_never_contains_the_address(self, store, mail_on):
        await _ask("privada@example.com")
        keys = [k async for k in store.scan_iter("magic_link:rl:*")]
        assert keys and not any("privada" in k or "example" in k for k in keys)


# --------------------------------------------------------------------------
# 2. The per-caller ceiling
# --------------------------------------------------------------------------


class TestPerCallerCeiling:
    async def test_anonymous_callers_share_a_per_ip_ceiling(self, store, mail_on):
        with patch.object(auth_mod.settings, "MAGIC_LINK_RATE_LIMIT", "3/hour"):
            for n in range(3):
                await _ask(f"anon{n}@example.com")
            with pytest.raises(HTTPException) as caught:
                await _ask("anon3@example.com")
        assert caught.value.status_code == 429

    async def test_a_trusted_service_has_its_own_higher_ceiling(self, store, mail_on):
        """The MAP's server asks for its whole staff: the per-IP ceiling (here 3)
        must not apply to it. Its own ceiling does."""
        service = {"X-Internal-API-Key": SERVICE_KEY}
        with (
            patch.object(auth_mod.settings, "MAGIC_LINK_RATE_LIMIT", "3/hour"),
            patch.object(auth_mod.settings, "MAGIC_LINK_SERVICE_RATE_LIMIT", "8/hour"),
        ):
            for n in range(8):
                await _ask(f"equipo{n}@example.com", _request(headers=service))
            with pytest.raises(HTTPException) as caught:
                await _ask("equipo8@example.com", _request(headers=service))
        assert caught.value.status_code == 429

    async def test_a_service_may_name_its_visitor_and_that_visitor_is_limited(self, store, mail_on):
        """A public sign-in page behind a service keeps a per-visitor limit."""
        visitor = {"X-Internal-API-Key": SERVICE_KEY, "X-Janua-End-User-IP": "198.51.100.23"}
        other = {"X-Internal-API-Key": SERVICE_KEY, "X-Janua-End-User-IP": "198.51.100.99"}
        with patch.object(auth_mod.settings, "MAGIC_LINK_RATE_LIMIT", "3/hour"):
            for n in range(3):
                await _ask(f"v{n}@example.com", _request(headers=visitor))
            with pytest.raises(HTTPException):
                await _ask("v3@example.com", _request(headers=visitor))
            # Another visitor of the same service is unaffected.
            assert await _ask("w0@example.com", _request(headers=other))

    async def test_a_wrong_key_is_just_an_anonymous_caller(self, store, mail_on):
        wrong = {"X-Internal-API-Key": "not-the-key", "X-Janua-End-User-IP": "198.51.100.1"}
        with patch.object(auth_mod.settings, "MAGIC_LINK_RATE_LIMIT", "2/hour"):
            await _ask("x0@example.com", _request(headers=wrong))
            await _ask("x1@example.com", _request(headers=wrong))
            with pytest.raises(HTTPException) as caught:
                # The named visitor IP is NOT believed without a valid key: the
                # anonymous per-IP bucket (the tunnel's) is what fills up.
                await _ask("x2@example.com", _request(headers=wrong))
        assert caught.value.status_code == 429

    def test_the_default_ceilings(self):
        from app.config import Settings

        s = Settings()
        assert s.MAGIC_LINK_EMAIL_RATE_LIMIT == "5/hour"
        assert s.MAGIC_LINK_RATE_LIMIT == "60/hour"
        assert s.MAGIC_LINK_SERVICE_RATE_LIMIT == "300/hour"


# --------------------------------------------------------------------------
# 3. Which IP: forwarded headers only through TRUSTED_PROXIES
# --------------------------------------------------------------------------


class TestTrustedClientIp:
    def test_untrusted_peer_cannot_spoof_its_address(self):
        req = _request(
            client=("203.0.113.5", 1),
            headers={"X-Forwarded-For": "1.2.3.4", "CF-Connecting-IP": "5.6.7.8"},
        )
        with patch.object(limits_mod.settings, "TRUSTED_PROXIES", "10.0.0.0/8"):
            assert limits_mod.trusted_client_ip(req) == "203.0.113.5"

    def test_trusted_proxy_cidr_reads_cf_connecting_ip(self):
        req = _request(headers={"CF-Connecting-IP": "198.51.100.23"})
        with patch.object(limits_mod.settings, "TRUSTED_PROXIES", "127.0.0.1,10.0.0.0/8"):
            assert limits_mod.trusted_client_ip(req) == "198.51.100.23"

    def test_xff_is_read_from_the_right_never_the_spoofable_left(self):
        req = _request(headers={"X-Forwarded-For": "1.2.3.4, 198.51.100.23, 10.42.0.9"})
        with patch.object(limits_mod.settings, "TRUSTED_PROXIES", "10.0.0.0/8"):
            assert limits_mod.trusted_client_ip(req) == "198.51.100.23"

    def test_without_trusted_proxies_it_is_the_tunnel_pod(self):
        req = _request(headers={"CF-Connecting-IP": "198.51.100.23"})
        with patch.object(limits_mod.settings, "TRUSTED_PROXIES", "127.0.0.1,::1"):
            assert limits_mod.trusted_client_ip(req) == TUNNEL_POD[0]

    def test_ipv6_is_bucketed_per_64(self):
        a = limits_mod._ip_bucket_key("2001:db8:1:2::1")
        b = limits_mod._ip_bucket_key("2001:db8:1:2:ffff::9")
        c = limits_mod._ip_bucket_key("2001:db8:1:3::1")
        assert a == b != c


# --------------------------------------------------------------------------
# 4. When Redis does not answer, the limits degrade to this process
# --------------------------------------------------------------------------


async def test_without_redis_the_address_limit_still_holds(mail_on):
    limits_mod.reset_memory_counters()
    with patch.object(limits_mod, "_redis_client", AsyncMock(side_effect=OSError("down"))):
        for _ in range(5):
            await _ask("sinredis@example.com")
        with pytest.raises(HTTPException) as caught:
            await _ask("sinredis@example.com")
    assert caught.value.status_code == 429


def test_the_hosted_form_passes_429_through():
    import inspect

    source = inspect.getsource(auth_mod.login_form_magic_link)
    assert "(400, 403, 429)" in source


def test_no_slowapi_decorator_left_on_the_magic_link_routes():
    """slowapi keyed these routes on `request.client.host` (the tunnel pod); the
    limits now live in `_issue_magic_link`, which both routes go through."""
    import inspect

    for handler in (auth_mod.send_magic_link, auth_mod.login_form_magic_link):
        assert "@limiter.limit" not in inspect.getsource(handler)
    assert "enforce_magic_link_limits(request" in inspect.getsource(auth_mod._issue_magic_link)
