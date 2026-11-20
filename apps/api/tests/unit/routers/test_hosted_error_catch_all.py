"""No raw JSON on a browser-navigated hosted route (roadmap 0.2, rule R1).

After the 2026-11-19 incident (docs/runbooks/incidents/2026-11-19-hosted-login-double-submit.md)
every refusal on a hosted route that a browser NAVIGATED to answers a 303 to the
GET page `/api/v1/auth/error`, in the person's language, with a restart button to
the registered client's origin when the request named one. The same requests from
an API client (`Accept: application/json`, or a `fetch` with `Sec-Fetch-Mode:
cors`) keep the JSON envelope exactly as before. Each refusal on a hosted route
logs one `auth.hosted_refusal` line with a reason code (rule R4).

These run the real app against SQLite and an in-memory Redis, walking the
roadmap rows that answered JSON: E-12/E-14 (second factor), E-19 (recovery on a
gone request), E-22 (consent), E-23 (authorize with an unknown
client), E-26 (logout with an unknown client), plus a validation error.
"""

import json
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import fakeredis.aioredis
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool
from structlog.testing import capture_logs

from app.auth.hosted_errors import HOSTED_ERROR_PATH, is_hosted_route
from app.core.redis_circuit_breaker import ResilientRedisClient
from app.database import get_db
from app.models import Base, OAuthClient, Organization, OrganizationMember, User, UserStatus

CLIENT = "synthetic-app"
CALLBACK = "https://app.test/api/auth/callback"
APP_ORIGIN = "https://app.test/"
FIXED_TIME = 1_700_000_000.0

HTML = {"accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"}
NAVIGATE = {**HTML, "sec-fetch-mode": "navigate"}
JSON = {"accept": "application/json"}
FETCH = {"accept": "text/html,*/*", "sec-fetch-mode": "cors"}


@pytest_asyncio.fixture
async def env(monkeypatch):
    import app.auth.hosted_security as hosted
    import app.services.auth_service as service
    from app import dependencies
    from app.core import redis as core_redis
    from app.core.database import get_db as core_get_db
    from app.main import app
    from app.routers.v1 import auth, auth_shared, oauth_provider

    engine = create_async_engine("sqlite+aiosqlite:///:memory:", poolclass=StaticPool)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    redis = ResilientRedisClient(fakeredis.aioredis.FakeRedis(decode_responses=True))

    async def get_session():
        async with factory() as db:
            yield db

    get_memory_redis = AsyncMock(return_value=redis)
    # auth_shared: the /auth route modules call get_redis through it (2026-11-19 split).
    for module in (core_redis, auth, auth_shared, hosted, service, oauth_provider):
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
    async with factory() as db:
        db.add(
            User(
                id=user_id,
                tenant_id=org_id,
                email="member@example.com",
                password_hash=service.AuthService.hash_password("Synthetic-Password-7!"),
                email_verified=True,
                status=UserStatus.ACTIVE,
                is_active=True,
            )
        )
        db.add(Organization(id=org_id, name="Synthetic org", slug="synthetic", owner_id=user_id))
        db.add(
            OrganizationMember(
                user_id=user_id, organization_id=org_id, role="owner", status="active"
            )
        )
        db.add(
            OAuthClient(
                client_id=CLIENT,
                name=CLIENT,
                organization_id=org_id,
                created_by=user_id,
                client_secret_hash="not-a-real-secret",
                client_secret_prefix="synthetic",
                redirect_uris=[CALLBACK],
                is_active=True,
                is_confidential=False,
            )
        )
        await db.commit()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="https://test") as http:
        yield SimpleNamespace(http=http, redis=redis, app=app)
    app.dependency_overrides.clear()
    app.dependency_overrides.update(previous)
    await engine.dispose()


def _assert_page_redirect(response, *, reason, status, client_id=None, locale=None):
    assert response.status_code == 303, response.text
    assert "application/json" not in response.headers.get("content-type", "")
    location = response.headers["location"]
    assert location.startswith(HOSTED_ERROR_PATH + "?")
    assert f"reason={reason}" in location
    assert f"status={status}" in location
    assert ("client_id=" + client_id in location) if client_id else "client_id=" not in location
    assert (f"ui_locales={locale}" in location) if locale else "ui_locales=" not in location
    assert response.headers["cache-control"] == "no-store"
    return location


def _assert_html_page(response, status):
    assert response.status_code == status
    assert response.headers["content-type"].startswith("text/html")
    assert not response.text.lstrip().startswith("{")
    assert "HTTP_ERROR" not in response.text
    assert response.headers["cache-control"] == "no-store"


def _refusals(logs):
    return [entry for entry in logs if entry.get("event") == "auth.hosted_refusal"]


# --- E-12 / E-14: second factor ------------------------------------------------


async def test_factor_double_submit_navigation_gets_the_page_not_json(env):
    with capture_logs() as logs:
        response = await env.http.post(
            "/api/v1/auth/factor/complete",
            data={"flow_id": "gone", "code": "123456"},
            headers={**NAVIGATE, "accept-language": "es-MX,es;q=0.9,en;q=0.5"},
        )
    location = _assert_page_redirect(response, reason="bad_request", status=400, locale="es")
    page = await env.http.get(location, headers=NAVIGATE)
    _assert_html_page(page, 400)
    assert '<html lang="es-MX">' in page.text
    assert "Este inicio de sesión no puede continuar" in page.text
    # Never the exception's own message, only fixed copy.
    assert "La verificación venció" not in page.text
    [line] = _refusals(logs)
    assert line["reason"] == "bad_request"
    assert line["route"] == "/api/v1/auth/factor/complete"
    assert line["status_code"] == 400 and line["answer"] == "html"
    assert "member@example.com" not in json.dumps(line, default=str)


async def test_factor_from_another_browser_navigation_gets_the_page(env):
    await env.redis.strict_set(
        "auth:factor:flow-1",
        json.dumps({"binding": "0" * 64, "user_id": str(uuid.uuid4())}),
        ex=600,
    )
    response = await env.http.post(
        "/api/v1/auth/factor/complete",
        data={"flow_id": "flow-1", "code": "123456"},
        headers=HTML,
    )
    _assert_page_redirect(response, reason="forbidden", status=403)


async def test_factor_json_client_keeps_the_envelope_byte_for_byte(env):
    with patch("app.core.error_handling.time.time", return_value=FIXED_TIME):
        response = await env.http.post(
            "/api/v1/auth/factor/complete",
            data={"flow_id": "gone", "code": "123456"},
            headers={**JSON, "x-request-id": "ignored"},
        )
    assert response.status_code == 400
    body = response.json()
    request_id = body["error"]["request_id"]
    assert body == {
        "error": {
            "code": "HTTP_ERROR",
            "message": "La verificación venció. Vuelve a iniciar sesión.",
            "request_id": request_id,
            "timestamp": FIXED_TIME,
        }
    }


async def test_a_fetch_that_accepts_html_is_not_a_navigation(env):
    response = await env.http.post(
        "/api/v1/auth/factor/complete",
        data={"flow_id": "gone", "code": "123456"},
        headers=FETCH,
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "HTTP_ERROR"


# --- E-19: password recovery on a gone request --------------------------------


async def test_recovery_on_a_gone_request_gets_the_page_with_a_restart(env):
    response = await env.http.post(
        "/api/v1/auth/forgot-password-form",
        data={
            "email": "member@example.com",
            "client_id": CLIENT,
            "auth_request_id": "gone",
            "ui_locales": "es",
        },
        headers=NAVIGATE,
    )
    location = _assert_page_redirect(
        response, reason="login_request_expired", status=400, client_id=CLIENT, locale="es"
    )
    page = await env.http.get(location, headers=NAVIGATE)
    _assert_html_page(page, 400)
    assert f'href="{APP_ORIGIN}"' in page.text
    assert "Volver a empezar" in page.text
    assert "login_request_expired" in page.text  # the reference a person can quote


async def test_recovery_on_a_gone_request_json_unchanged(env):
    response = await env.http.post(
        "/api/v1/auth/forgot-password-form",
        data={"email": "member@example.com", "client_id": CLIENT, "auth_request_id": "gone"},
        headers=JSON,
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "HTTP_ERROR"
    assert response.json()["error"]["message"].startswith("La solicitud de acceso venció")


# --- E-22: consent -------------------------------------------------------------


async def test_consent_without_a_session_navigation_gets_the_page(env):
    response = await env.http.post(
        "/api/v1/oauth/consent",
        data={"auth_request_id": "r", "csrf_token": "t", "action": "allow"},
        headers=NAVIGATE,
    )
    _assert_page_redirect(response, reason="not_authenticated", status=401)


async def test_consent_without_a_session_json_unchanged(env):
    response = await env.http.post(
        "/api/v1/oauth/consent",
        data={"auth_request_id": "r", "csrf_token": "t", "action": "allow"},
        headers=JSON,
    )
    assert response.status_code == 401
    assert response.json()["error"]["message"] == "Not authenticated"


# --- E-23: authorize with an unknown client ------------------------------------


async def test_authorize_with_an_unknown_client_navigation_gets_the_page(env):
    response = await env.http.get(
        "/api/v1/oauth/authorize",
        params={
            "response_type": "code",
            "client_id": "no-such-client",
            "redirect_uri": "https://elsewhere.test/cb",
            "scope": "openid",
            "state": "s",
        },
        headers=NAVIGATE,
    )
    location = _assert_page_redirect(
        response, reason="bad_request", status=400, client_id="no-such-client"
    )
    page = await env.http.get(location, headers=NAVIGATE)
    _assert_html_page(page, 400)
    # An unknown client has no registered origin: words only, no button.
    assert "<a href" not in page.text
    assert "elsewhere.test" not in page.text


# --- E-26: logout with an unknown client ---------------------------------------


async def test_logout_with_an_unknown_client_navigation_gets_the_page(env):
    response = await env.http.get(
        "/logout",
        params={"client_id": "no-such-client", "post_logout_redirect_uri": "https://x.test/"},
        headers=NAVIGATE,
    )
    assert response.status_code == 303
    assert response.headers["location"].startswith(HOSTED_ERROR_PATH + "?")


async def test_logout_with_an_unknown_client_json_unchanged(env):
    response = await env.http.get(
        "/logout",
        params={"client_id": "no-such-client", "post_logout_redirect_uri": "https://x.test/"},
        headers=JSON,
    )
    assert 400 <= response.status_code < 500
    assert response.json()["error"]["code"] == "HTTP_ERROR"


# --- Validation errors ---------------------------------------------------------


async def test_validation_error_on_a_hosted_form_navigation_gets_the_page(env):
    response = await env.http.post(
        "/api/v1/auth/login-form", data={"ui_locales": "es"}, headers=NAVIGATE
    )
    _assert_page_redirect(response, reason="invalid_request", status=422, locale="es")


async def test_validation_error_on_a_hosted_form_json_unchanged(env):
    response = await env.http.post("/api/v1/auth/login-form", data={}, headers=JSON)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


# --- Scope and the page itself -------------------------------------------------


async def test_a_non_hosted_route_is_untouched_and_not_logged(env):
    with capture_logs() as logs:
        response = await env.http.get("/api/v1/auth/me", headers=NAVIGATE)
    assert response.status_code in (401, 403)
    assert response.headers["content-type"].startswith("application/json")
    assert _refusals(logs) == []


async def test_error_page_never_echoes_request_values(env):
    page = await env.http.get(
        HOSTED_ERROR_PATH,
        params={
            "reason": "<script>alert(1)</script>",
            "status": "200",
            "client_id": "javascript:alert(1)",
            "ref": "<b>",
        },
        headers=NAVIGATE,
    )
    _assert_html_page(page, 400)
    assert "<script>" not in page.text and "<b>" not in page.text
    assert "javascript:" not in page.text
    assert "bad_request" in page.text
    assert page.headers["content-security-policy"].startswith("default-src 'none'")


async def test_error_page_defaults_to_english_and_offers_the_registered_origin(env):
    page = await env.http.get(
        HOSTED_ERROR_PATH,
        params={"reason": "login_request_expired", "status": "400", "client_id": CLIENT},
        headers=NAVIGATE,
    )
    _assert_html_page(page, 400)
    assert '<html lang="en">' in page.text
    assert "This sign-in can&#x27;t continue" in page.text or "This sign-in can't continue" in (
        page.text
    )
    assert f'href="{APP_ORIGIN}"' in page.text


async def test_a_post_to_the_error_page_renders_and_never_loops(env):
    response = await env.http.post(HOSTED_ERROR_PATH, headers=NAVIGATE)
    _assert_html_page(response, 405)


@pytest.mark.parametrize(
    "path,hosted",
    [
        ("/api/v1/auth/login", True),
        ("/api/v1/auth/login-form", True),
        ("/api/v1/auth/login-form/mfa", True),
        ("/api/v1/auth/factor/complete", True),
        ("/api/v1/auth/forgot-password-form", True),
        ("/api/v1/auth/reset-password-form", True),
        ("/api/v1/auth/magic-link/callback", True),
        ("/api/v1/oauth/authorize", True),
        ("/api/v1/oauth/authorize/resume", True),
        ("/api/v1/oauth/consent", True),
        ("/logout", True),
        ("/api/v1/auth/logout", False),
        ("/api/v1/auth/refresh", False),
        ("/api/v1/auth/me", False),
        ("/api/v1/oauth/token", False),
        ("/api/v1/auth/magic-link", False),
        ("/api/v1/auth/login-formx", False),
    ],
)
def test_hosted_route_set(path, hosted):
    assert is_hosted_route(path) is hosted
