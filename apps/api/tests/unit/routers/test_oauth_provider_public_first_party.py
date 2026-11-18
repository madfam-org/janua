"""Silent sign-in and consent skip for marked PUBLIC first-party clients.

Owner decision (2026-11-18): a first-party browser app that is a public client
(PKCE, no secret) may use `prompt=none` and skip the consent screen when an
operator marked it with `madfam:silent_auth`, and only when the request binds
the code to the registered app:

- PKCE S256, stated explicitly, with a challenge of the S256 shape;
- `redirect_uri` exactly equal to a registered string;
- every requested scope registered for the client;
- reserved scopes (product roles, the marker itself) only when the person
  already granted them to this client on the consent screen;
- the row registered by a platform admin;
- the person's session, MFA and the other gates exactly as for every client.

Otherwise: `login_required`, `consent_required` or `interaction_required`,
redirected to the validated redirect_uri only. Unmarked public clients and
confidential clients behave as before.

Driven through the real app over ASGI with a real (SQLite) database and a
fakeredis-backed `ResilientRedisClient`, like `test_oauth_protected_resources.py`.
"""

from __future__ import annotations

import base64
import hashlib
import re
import secrets
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from urllib.parse import parse_qs, urlparse

import bcrypt
import fakeredis
import pytest
import pytest_asyncio

# Imported at collection time on purpose (see test_redis_strict_operations.py).
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.jwt_manager import jwt_manager
from app.core.redis_circuit_breaker import ResilientRedisClient
from app.models import Base, OAuthClient, User, UserStatus

pytestmark = pytest.mark.asyncio

CALLBACK = "https://app.example.test/auth/callback"
MARKED = "jnc_test_public_first_party_marked"
UNMARKED = "jnc_test_public_first_party_unmarked"
LEGACY_MARKED = "jnc_test_public_first_party_marked_by_tenant"
CONFIDENTIAL = "jnc_test_confidential_first_party"
CONFIDENTIAL_SECRET = "jns_test_confidential_first_party_placeholder"
ROLE_SCOPE = "tulana:viewer"  # a reserved product role scope (RESERVED_SCOPE_NAMESPACES)
MARKED_SCOPES = ["openid", "profile", "email", "offline_access", "madfam:silent_auth", ROLE_SCOPE]


def _hash(secret: str) -> str:
    return bcrypt.hashpw(secret.encode(), bcrypt.gensalt(rounds=4)).decode()


def _row(created_by, client_id, *, name, scopes, secret=None) -> OAuthClient:
    stored = secret or "jns_test_public_unused_placeholder"
    return OAuthClient(
        id=uuid.uuid4(),
        created_by=created_by,
        client_id=client_id,
        client_secret_hash=_hash(stored),
        client_secret_prefix=stored[:8],
        name=name,
        redirect_uris=[CALLBACK],
        allowed_scopes=scopes,
        grant_types=["authorization_code", "refresh_token"],
        is_active=True,
        is_confidential=secret is not None,
    )


@pytest_asyncio.fixture
async def env(monkeypatch):
    from app import dependencies
    from app.core import redis as core_redis
    from app.core.database import get_db as core_get_db
    from app.database import get_db
    from app.main import app
    from app.routers.v1 import auth as auth_router
    from app.routers.v1 import oauth_provider

    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    redis = ResilientRedisClient(
        fakeredis.aioredis.FakeRedis(server=fakeredis.FakeServer(), decode_responses=True)
    )

    async def override_get_db():
        async with factory() as session:
            yield session

    saved = dict(app.dependency_overrides)
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[core_get_db] = override_get_db
    for dep in {
        core_redis.get_redis,
        dependencies.get_redis,
        oauth_provider.get_redis,
        auth_router.get_redis,
    }:
        app.dependency_overrides[dep] = lambda: redis

    def person(email, **extra):
        return User(
            id=uuid.uuid4(),
            email=email,
            email_verified=True,
            status=UserStatus.ACTIVE,
            is_active=True,
            **extra,
        )

    admin = person("admin-public-fp@janua.test", is_admin=True)
    tenant_admin = person("tenant-public-fp@janua.test")
    member = person("persona-public-fp@janua.test")
    async with factory() as session:
        session.add_all([admin, tenant_admin, member])
        await session.flush()
        session.add_all(
            [
                _row(admin.id, MARKED, name="Portal marcado", scopes=MARKED_SCOPES),
                _row(
                    admin.id,
                    UNMARKED,
                    name="Portal sin marca",
                    scopes=["openid", "profile", "email", "offline_access"],
                ),
                # A marked row a non-admin wrote (before the registry reserved
                # the marker): the marker is not honoured on it.
                _row(tenant_admin.id, LEGACY_MARKED, name="Portal heredado", scopes=MARKED_SCOPES),
                _row(
                    admin.id,
                    CONFIDENTIAL,
                    name="madfam-confidential-regression",
                    scopes=["openid", "profile", "email", "offline_access"],
                    secret=CONFIDENTIAL_SECRET,
                ),
            ]
        )
        await session.commit()

    get = AsyncMock(return_value=redis)
    with (
        patch("app.core.redis.get_redis", get),
        patch("app.services.auth_service.get_redis", get),
        patch("app.routers.v1.oauth_provider.get_redis", get),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http:
            yield SimpleNamespace(http=http, member=member)

    app.dependency_overrides.clear()
    app.dependency_overrides.update(saved)
    await engine.dispose()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def pkce():
    verifier = secrets.token_urlsafe(48)
    challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    )
    return verifier, challenge


def params(challenge, *, client_id=MARKED, **extra) -> dict:
    values = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": CALLBACK,
        "scope": "openid profile email",
        "state": "rp-state",
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    }
    values.update(extra)
    return {key: value for key, value in values.items() if value is not None}


async def authorize(env, query_params, user=None):
    headers = {}
    if user is not None:
        token, _, _ = jwt_manager.create_access_token(user_id=str(user.id), email=user.email)
        headers["Authorization"] = f"Bearer {token}"
    return await env.http.get("/api/v1/oauth/authorize", params=query_params, headers=headers)


def callback_query(response, redirect_uri=CALLBACK) -> dict:
    assert response.status_code == 302, (response.status_code, response.text[:300])
    location = response.headers["location"]
    assert location.startswith(redirect_uri + ("&" if "?" in redirect_uri else "?")), location
    return {k: v[0] for k, v in parse_qs(urlparse(location).query).items()}


def assert_error(response, error, redirect_uri=CALLBACK) -> dict:
    query = callback_query(response, redirect_uri)
    assert query.get("error") == error, query
    assert "code" not in query
    assert query["state"] == "rp-state"
    return query


def assert_consent_page(response):
    assert response.status_code == 200, (response.status_code, response.headers.get("location"))
    assert 'name="csrf_token"' in response.text


async def approve(env, page, user):
    auth_request_id = re.search(r'name="auth_request_id" value="([^"]+)"', page.text).group(1)
    csrf_token = re.search(r'name="csrf_token" value="([^"]+)"', page.text).group(1)
    token, _, _ = jwt_manager.create_access_token(user_id=str(user.id), email=user.email)
    return await env.http.post(
        "/api/v1/oauth/consent",
        data={"auth_request_id": auth_request_id, "csrf_token": csrf_token, "action": "allow"},
        headers={"Authorization": f"Bearer {token}"},
    )


# ---------------------------------------------------------------------------
# The marked public client
# ---------------------------------------------------------------------------


class TestMarkedPublicClient:
    async def test_prompt_none_with_a_session_issues_a_code_that_redeems(self, env):
        verifier, challenge = pkce()
        query = callback_query(await authorize(env, params(challenge, prompt="none"), env.member))
        assert "error" not in query and query["code"] and query["state"] == "rp-state"

        exchanged = await env.http.post(
            "/api/v1/oauth/token",
            data={
                "grant_type": "authorization_code",
                "code": query["code"],
                "redirect_uri": CALLBACK,
                "client_id": MARKED,
                "code_verifier": verifier,
            },
        )
        assert exchanged.status_code == 200, exchanged.text
        assert exchanged.json()["access_token"]

    async def test_interactive_request_skips_the_consent_screen(self, env):
        _, challenge = pkce()
        query = callback_query(await authorize(env, params(challenge), env.member))
        assert query["code"]

    async def test_no_session_is_login_required(self, env):
        _, challenge = pkce()
        assert_error(await authorize(env, params(challenge, prompt="none")), "login_required")

    async def test_mfa_the_session_lacks_is_login_required(self, env, monkeypatch):
        from app.routers.v1 import oauth_provider

        monkeypatch.setattr(oauth_provider, "user_requires_mfa", AsyncMock(return_value=True))
        _, challenge = pkce()
        query = assert_error(
            await authorize(env, params(challenge, prompt="none"), env.member), "login_required"
        )
        assert query["error_description"] == "mfa_required"


class TestRequestConditions:
    @pytest.mark.parametrize(
        "redirect_uri",
        [CALLBACK + "?next=/x", CALLBACK + "/"],
        ids=["extra query", "trailing slash"],
    )
    async def test_redirect_uri_must_be_the_exact_registered_string(self, env, redirect_uri):
        # Both spellings pass the general (normalizing) redirect check, so the
        # error goes back to the URI the request named, never anywhere else.
        _, challenge = pkce()
        silent = await authorize(
            env, params(challenge, prompt="none", redirect_uri=redirect_uri), env.member
        )
        query = assert_error(silent, "interaction_required", redirect_uri=redirect_uri)
        assert query["error_description"] == "redirect_uri_not_exact"
        interactive = await authorize(env, params(challenge, redirect_uri=redirect_uri), env.member)
        assert_consent_page(interactive)

    async def test_unregistered_redirect_uri_is_never_redirected_to(self, env):
        _, challenge = pkce()
        response = await authorize(
            env,
            params(challenge, prompt="none", redirect_uri="https://evil.example.test/cb"),
            env.member,
        )
        assert response.status_code == 400
        assert "location" not in response.headers

    async def test_missing_code_challenge_is_refused_without_redirect(self, env):
        response = await authorize(
            env, params(None, prompt="none", code_challenge_method=None), env.member
        )
        assert response.status_code == 400
        assert "location" not in response.headers

    async def test_plain_pkce_is_refused_without_redirect(self, env):
        verifier, _ = pkce()
        response = await authorize(
            env,
            params(verifier, prompt="none", code_challenge_method="plain"),
            env.member,
        )
        assert response.status_code == 400
        assert "location" not in response.headers

    @pytest.mark.parametrize(
        "extra",
        [{"code_challenge_method": None}, {"code_challenge": "too-short"}],
        ids=["method omitted", "not an S256 challenge"],
    )
    async def test_pkce_must_be_explicit_s256(self, env, extra):
        _, challenge = pkce()
        silent = await authorize(env, params(challenge, prompt="none", **extra), env.member)
        query = assert_error(silent, "interaction_required")
        assert query["error_description"] == "pkce_s256_required"
        assert_consent_page(await authorize(env, params(challenge, **extra), env.member))

    async def test_scope_outside_the_registration(self, env):
        _, challenge = pkce()
        scope = "openid profile calendar:write"
        silent = await authorize(env, params(challenge, prompt="none", scope=scope), env.member)
        query = assert_error(silent, "consent_required")
        assert query["error_description"] == "scope_not_registered"
        assert_consent_page(await authorize(env, params(challenge, scope=scope), env.member))

    @pytest.mark.parametrize("scope", [f"openid {ROLE_SCOPE}", "openid madfam:silent_auth"])
    async def test_reserved_scope_needs_the_persons_own_consent_first(self, env, scope):
        _, challenge = pkce()
        silent = await authorize(env, params(challenge, prompt="none", scope=scope), env.member)
        assert_error(silent, "consent_required")

        # Asked once on the consent screen ...
        page = await authorize(env, params(challenge, scope=scope), env.member)
        assert_consent_page(page)
        assert callback_query(await approve(env, page, env.member))["code"]

        # ... then the same request is silent.
        _, challenge = pkce()
        query = callback_query(
            await authorize(env, params(challenge, prompt="none", scope=scope), env.member)
        )
        assert query["code"] and "error" not in query

    async def test_marker_on_a_row_not_registered_by_a_platform_admin(self, env):
        _, challenge = pkce()
        silent = await authorize(
            env, params(challenge, client_id=LEGACY_MARKED, prompt="none"), env.member
        )
        assert_error(silent, "interaction_required")
        assert_consent_page(
            await authorize(env, params(challenge, client_id=LEGACY_MARKED), env.member)
        )


class TestUnchanged:
    async def test_unmarked_public_client_cannot_use_prompt_none(self, env):
        _, challenge = pkce()
        silent = await authorize(
            env, params(challenge, client_id=UNMARKED, prompt="none"), env.member
        )
        query = assert_error(silent, "interaction_required")
        assert query["error_description"] == "silent_auth not allowed for this client"

    async def test_unmarked_public_client_sees_the_consent_screen(self, env):
        _, challenge = pkce()
        assert_consent_page(await authorize(env, params(challenge, client_id=UNMARKED), env.member))

    async def test_confidential_first_party_keeps_its_leniencies(self, env):
        # Confidential first-party clients are trusted by their secret: the
        # public-client request conditions do not apply to them.
        _, challenge = pkce()
        query = callback_query(
            await authorize(
                env,
                params(
                    challenge,
                    client_id=CONFIDENTIAL,
                    prompt="none",
                    code_challenge_method=None,
                    scope="openid profile calendar:write",
                ),
                env.member,
            )
        )
        assert query["code"] and "error" not in query
