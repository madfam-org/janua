"""A hosted sign-in POST whose pending request is gone never answers JSON.

Production incident 2026-11-19 (docs/runbooks/incidents/2026-11-19-hosted-login-double-submit.md):
a person pressed «Entrar» twice. The first POST signed them in and consumed
`oauth:pre_login:<id>`; the second POST, 2–3 s later with the same id, cancelled
the first navigation in the browser and was answered with the error body as raw
JSON (`login_client_context` raised 400). Refresh re-POSTed and showed it again.

These tests pin, against the real router, SQLite and an in-memory Redis:

- a second POST for a consumed id checks the credentials again, against the
  client the form names, and lands in that client (303 to its registered
  origin, which starts a fresh request the new session completes);
- a wrong password, a lockout, an identity outside the client's pool and a
  forged client on a live request are still refused;
- a gone id that nothing registered can restart answers a 303 to a GET page
  (refresh-safe), never the error body, and checks no credentials;
- every hosted sign-in form loads the same-origin one-press script the CSP
  allows and names its busy label.
"""

import json
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import fakeredis.aioredis
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.auth.tenant_login_context import LoginRequestExpired, login_client_context
from app.core.redis_circuit_breaker import ResilientRedisClient
from app.database import get_db
from app.models import Base, OAuthClient, Organization, OrganizationMember, User, UserStatus
from app.models import Session as UserSession
from app.models.organization_authentication_policy import OrganizationAuthenticationPolicy
from app.services.auth_service import AuthService

PASSWORD = "Synthetic-Password-7!"
CLIENT = "synthetic-map"
CALLBACK = "https://map.test/api/auth/callback"
APP_ORIGIN = "https://map.test/"


@pytest_asyncio.fixture
async def env(monkeypatch):
    import app.auth.hosted_security as hosted
    import app.services.auth_service as service
    from app import dependencies
    from app.core import redis as core_redis
    from app.core.database import get_db as core_get_db
    from app.main import app
    from app.routers.v1 import auth, oauth_provider

    engine = create_async_engine("sqlite+aiosqlite:///:memory:", poolclass=StaticPool)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
        await connection.exec_driver_sql("DROP INDEX uq_users_email_global")
        await connection.exec_driver_sql(
            "CREATE UNIQUE INDEX uq_users_email_global ON users(email) WHERE tenant_id IS NULL"
        )
    factory = async_sessionmaker(engine, expire_on_commit=False)
    redis = ResilientRedisClient(fakeredis.aioredis.FakeRedis(decode_responses=True))

    async def get_session():
        async with factory() as db:
            yield db

    get_memory_redis = AsyncMock(return_value=redis)
    for module in (core_redis, auth, hosted, service, oauth_provider):
        monkeypatch.setattr(module, "get_redis", get_memory_redis)
    previous = dict(app.dependency_overrides)
    for key in (get_db, core_get_db):
        app.dependency_overrides[key] = get_session
    for key in (core_redis.get_redis, dependencies.get_redis, auth.get_redis):
        app.dependency_overrides[key] = lambda: redis
    for route in app.routes:
        dependant = getattr(route, "dependant", None)
        if dependant:
            for child in dependant.dependencies:
                if getattr(child.call, "__name__", "") in ("get_redis", "mock_get_redis"):
                    app.dependency_overrides[child.call] = lambda: redis
    org_id, user_id = uuid.uuid4(), uuid.uuid4()
    user = User(
        id=user_id,
        tenant_id=org_id,
        email="member@example.com",
        password_hash=AuthService.hash_password(PASSWORD),
        email_verified=True,
        status=UserStatus.ACTIVE,
        is_active=True,
    )
    async with factory() as db:
        db.add(user)
        db.add(Organization(id=org_id, name="Synthetic org", slug="synthetic", owner_id=user_id))
        db.add(
            OrganizationMember(
                user_id=user_id, organization_id=org_id, role="owner", status="active"
            )
        )
        for client_id, org, uri in (
            (CLIENT, org_id, CALLBACK),
            ("synthetic-unbound", None, "https://other.test/callback"),
        ):
            db.add(
                OAuthClient(
                    client_id=client_id,
                    name=client_id,
                    organization_id=org,
                    created_by=user_id,
                    client_secret_hash="not-a-real-secret",
                    client_secret_prefix="synthetic",
                    redirect_uris=[uri],
                    is_active=True,
                    is_confidential=False,
                )
            )
        await db.commit()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="https://test") as http:
        yield SimpleNamespace(http=http, factory=factory, redis=redis, user=user, org_id=org_id)
    app.dependency_overrides.clear()
    app.dependency_overrides.update(previous)
    await engine.dispose()


async def _pending(env, request_id="req-1", client_id=CLIENT, redirect_uri=CALLBACK):
    """What GET /oauth/authorize stores before sending the browser to the login page."""
    await env.redis.strict_set(
        f"oauth:pre_login:{request_id}",
        json.dumps(
            {
                "response_type": "code",
                "client_id": client_id,
                "redirect_uri": redirect_uri,
                "scope": "openid profile email",
                "state": "synthetic-state",
                "code_challenge": "c" * 43,
                "code_challenge_method": "S256",
                "ui_locales": "es",
            }
        ),
        ex=600,
    )
    return request_id


async def _post(env, *, password=PASSWORD, request_id="req-1", client_id=CLIENT, **extra):
    data = {"email": env.user.email, "password": password, "ui_locales": "es", **extra}
    if request_id is not None:
        data["auth_request_id"] = request_id
    if client_id is not None:
        data["client_id"] = client_id
    return await env.http.post("/api/v1/auth/login-form", data=data)


async def _sessions(env):
    async with env.factory() as db:
        return (await db.execute(select(UserSession))).scalars().all()


def _not_the_error_body(response):
    assert "application/json" not in response.headers.get("content-type", "")
    assert not response.text.lstrip().startswith("{") and "HTTP_ERROR" not in response.text


async def test_double_submit_second_post_lands_in_the_app(env):
    await _pending(env)
    first = await _post(env)
    assert first.status_code == 302
    assert first.headers["location"].startswith("/api/v1/oauth/authorize?")
    assert "state=synthetic-state" in first.headers["location"]
    assert await env.redis.strict_get("oauth:pre_login:req-1") is None

    # The second press: same id, the first submit already consumed it.
    second = await _post(env)
    _not_the_error_body(second)
    assert second.status_code == 303, second.text
    assert second.headers["location"] == APP_ORIGIN
    cookies = second.headers.get_list("set-cookie")
    assert any(c.startswith("janua_access_token=") for c in cookies)
    assert any(c.startswith("janua_refresh_token=") for c in cookies)
    sessions = await _sessions(env)
    assert len(sessions) == 2 and {s.user_id for s in sessions} == {env.user.id}


async def test_second_post_with_a_wrong_password_is_refused(env):
    await _pending(env)
    assert (await _post(env)).status_code == 302
    refused = await _post(env, password="Not-The-Password-1!")
    _not_the_error_body(refused)
    assert refused.status_code == 401
    assert "El correo o la contraseña no son correctos" in refused.text
    assert len(await _sessions(env)) == 1
    async with env.factory() as db:
        user = await db.get(User, env.user.id)
        assert user.failed_login_attempts == 1


async def test_second_post_for_a_locked_account_is_refused(env):
    from datetime import datetime, timedelta

    await _pending(env)
    assert (await _post(env)).status_code == 302
    async with env.factory() as db:
        user = await db.get(User, env.user.id)
        user.locked_until = datetime.utcnow() + timedelta(minutes=10)
        await db.commit()
    refused = await _post(env)
    _not_the_error_body(refused)
    assert refused.status_code == 401
    assert "bloqueada" in refused.text
    assert len(await _sessions(env)) == 1


async def test_gone_request_resolves_the_identity_in_the_named_clients_pool(env):
    """The form's client_id decides the pool exactly as a fresh sign-in at that
    client would: this person exists only in synthetic-map's organization pool,
    so naming an unbound client finds no one."""
    refused = await _post(env, request_id="never-stored", client_id="synthetic-unbound")
    _not_the_error_body(refused)
    assert refused.status_code == 401
    assert await _sessions(env) == []


async def test_forged_client_on_a_live_request_is_still_refused(env):
    await _pending(env)
    refused = await _post(env, client_id="synthetic-unbound")
    assert refused.status_code == 400
    assert await _sessions(env) == []
    # The live request is untouched; the real client still completes it.
    assert (await _post(env)).status_code == 302


async def test_gone_request_without_a_client_is_a_get_page_and_checks_nothing(env):
    for password in (PASSWORD, "Not-The-Password-1!"):
        response = await _post(env, request_id="never-stored", client_id=None, password=password)
        _not_the_error_body(response)
        assert response.status_code == 303
        assert response.headers["location"] == "/api/v1/auth/login-expired?ui_locales=es"
        assert not response.headers.get_list("set-cookie")
    assert await _sessions(env) == []
    async with env.factory() as db:
        assert (await db.get(User, env.user.id)).failed_login_attempts in (0, None)

    page = await env.http.get("/api/v1/auth/login-expired?ui_locales=es")
    _not_the_error_body(page)
    assert page.headers["content-type"].startswith("text/html")
    assert page.headers["cache-control"] == "no-store"
    assert "La solicitud para entrar venció" in page.text
    assert "Volver a iniciar sesión" not in page.text  # nothing registered to restart at


async def test_gone_request_for_an_unknown_client_is_a_get_page(env):
    response = await _post(env, request_id="never-stored", client_id="no-such-client")
    _not_the_error_body(response)
    assert response.status_code == 303
    assert response.headers["location"].startswith("/api/v1/auth/login-expired?")
    assert await _sessions(env) == []


async def test_expired_page_restarts_at_the_registered_origin_only(env):
    page = await env.http.get(f"/api/v1/auth/login-expired?client_id={CLIENT}&ui_locales=es")
    _not_the_error_body(page)
    assert f'<a href="{APP_ORIGIN}"' in page.text
    assert "Volver a iniciar sesión" in page.text
    english = await env.http.get(f"/api/v1/auth/login-expired?client_id={CLIENT}")
    assert '<html lang="en">' in english.text
    assert "Sign-in session expired" in english.text and "Start signing in again" in english.text


async def test_gone_request_needing_a_second_factor_issues_nothing(env):
    async with env.factory() as db:
        db.add(
            OrganizationAuthenticationPolicy(
                organization_id=env.org_id, mfa_mode="required", version=1, updated_by=env.user.id
            )
        )
        await db.commit()
    response = await _post(env, request_id="never-stored")
    _not_the_error_body(response)
    assert response.status_code == 303
    assert response.headers["location"] == (
        f"/api/v1/auth/login-expired?client_id={CLIENT}&ui_locales=es"
    )
    assert not response.headers.get_list("set-cookie")
    assert await _sessions(env) == []


async def test_login_request_expired_is_the_same_400_for_every_other_caller(env):
    async with env.factory() as db:
        with pytest.raises(LoginRequestExpired) as error:
            await login_client_context(db, env.redis, auth_request_id="never-stored")
    assert error.value.status_code == 400
    assert error.value.detail == "La solicitud de acceso venció. Vuelve al MAP para iniciar."


async def test_hosted_forms_load_the_same_origin_one_press_script(env):
    from app.routers.v1.auth import HOSTED_FORM_SCRIPT_PATH

    page = await env.http.get(
        "/api/v1/auth/login",
        params={"auth_request_id": await _pending(env), "client_id": CLIENT, "ui_locales": "es"},
    )
    assert page.status_code == 200
    assert f'<script src="{HOSTED_FORM_SCRIPT_PATH}" defer></script>' in page.text
    assert 'data-busy-label="Entrando…"' in page.text
    # No inline script: every <script> on the page has a same-origin src.
    assert page.text.count("<script") == page.text.count(f'<script src="{HOSTED_FORM_SCRIPT_PATH}"')
    csp = page.headers["content-security-policy"]
    script_src = next(d for d in csp.split("; ") if d.startswith("script-src "))
    assert "'self'" in script_src.split()

    script = await env.http.get(HOSTED_FORM_SCRIPT_PATH)
    assert script.status_code == 200
    assert script.headers["content-type"].startswith("application/javascript")
    for needle in ("data-busy-label", "data-submitting", "preventDefault", "pageshow", "role"):
        assert needle in script.text, needle

    english = await env.http.get("/api/v1/auth/login", params={"client_id": CLIENT})
    assert 'data-busy-label="Signing in…"' in english.text
    magic = await env.http.get(
        "/api/v1/auth/login", params={"client_id": CLIENT, "login_method": "magic_link"}
    )
    if 'id="magicLinkForm"' in magic.text:  # only where this deployment can mail links
        assert 'data-busy-label="Sending…"' in magic.text
    forgot = await env.http.get("/api/v1/auth/forgot-password", params={"ui_locales": "es"})
    assert 'data-busy-label="Enviando…"' in forgot.text
    assert f'<script src="{HOSTED_FORM_SCRIPT_PATH}" defer></script>' in forgot.text

    wrong = await _post(env, password="Not-The-Password-1!")
    assert wrong.status_code == 401
    assert 'data-busy-label="Entrando…"' in wrong.text
    assert f'<script src="{HOSTED_FORM_SCRIPT_PATH}" defer></script>' in wrong.text
