"""The MCP authorization path end to end: Claude and Claude Code get MAP tokens.

Owner decision (2026-10): the center's Director connects the MAP of Crea Tu
Mundo (an MCP server at https://map.creatumundo.mx/api/mcp) to Claude as a
custom connector, and Claude Code must work too. Claude identifies itself with
a Client ID Metadata Document and sends the RFC 8707 `resource` on every
authorization and token request.

Driven through the real app over ASGI with a real (SQLite) database, a
fakeredis-backed `ResilientRedisClient`, an RS256 key (tokens are checked
against the public JWKS) and a fake network serving Claude's two CIMD
documents. Covers:

- no `resource`: the default flow is unchanged (plus `iss` on redirects);
- `invalid_target` for unknown, malformed, repeated or mismatched resources,
  at /authorize, at the code exchange and at refresh;
- the access token: RFC 9068 shape, `aud` = the resource exactly, `sub` = the
  same subject the ID token carries, scopes = requested ∩ the resource's;
- CIMD allowlist, redirect matching (loopback on any port), PKCE S256 only,
  response_type=code only, the Spanish consent screen on every request;
- refresh: rotation, reuse detection (the family dies, `invalid_grant`),
  downscoping without upscoping, revocation, RFC 6749 error bodies;
- a resource token is never a Janua session, and vice versa;
- the hosted-login resume keeps `resource`.
"""

from __future__ import annotations

import base64
import hashlib
import json
import re
import secrets
import time
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from urllib.parse import parse_qs, urlparse

import bcrypt
import fakeredis
import httpx
import jwt
import pytest
import pytest_asyncio
from cryptography.hazmat.primitives.asymmetric import rsa

# Imported at collection time on purpose (see test_redis_strict_operations.py).
from httpx import ASGITransport, AsyncClient
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.jwt_manager import jwt_manager
from app.core.protected_resources import MAP_CREA_TU_MUNDO
from app.core.redis_circuit_breaker import ResilientRedisClient
from app.models import Base, OAuthClient, User, UserStatus
from app.services import client_id_metadata as cimd
from app.services import resource_tokens

ISSUER = "https://auth.madfam.io"
MAP = "https://map.creatumundo.mx/api/mcp"
CLAUDE = "https://claude.ai/oauth/mcp-oauth-client-metadata"
CLAUDE_CODE = "https://claude.ai/oauth/claude-code-client-metadata"
CLAUDE_CALLBACK = "https://claude.ai/api/mcp/auth_callback"
CODE_LOOPBACK = "http://localhost:53682/callback"
ALL_SCOPES = "map.ops:read map.cobro:read offline_access"
PUBLIC_IP = "104.18.32.47"

CLAUDE_DOC = {
    "client_id": CLAUDE,
    "client_name": "Claude",
    "client_uri": "https://claude.ai",
    "redirect_uris": [CLAUDE_CALLBACK],
    "grant_types": [
        "authorization_code",
        "refresh_token",
        "urn:ietf:params:oauth:grant-type:jwt-bearer",
    ],
    "response_types": ["code"],
    "token_endpoint_auth_method": "none",
}
CLAUDE_CODE_DOC = {
    "client_id": CLAUDE_CODE,
    "client_name": "Claude Code",
    "client_uri": "https://claude.ai",
    "redirect_uris": ["http://localhost/callback", "http://127.0.0.1/callback"],
    "grant_types": ["authorization_code", "refresh_token"],
    "response_types": ["code"],
    "token_endpoint_auth_method": "none",
}

# Clients registered in Janua's database (the "use your own OAuth client" path).
REG_CLAUDE = "jnc_test_mcp_registered_claude"
REG_LOOPBACK = "jnc_test_mcp_registered_loopback"
REG_LOOPBACK_SECRET = "jns_test_mcp_loopback_secret_placeholder"
REG_MIXED = "jnc_test_mcp_registered_mixed"
REG_OUTSIDE = "jnc_test_mcp_registered_outside"
LEGACY = "jnc_test_mcp_legacy_first_party"
LEGACY_SECRET = "jns_test_mcp_legacy_secret_placeholder"
LEGACY_CALLBACK = "https://app.example.test/callback"


def _hash(secret: str) -> str:
    return bcrypt.hashpw(secret.encode(), bcrypt.gensalt(rounds=4)).decode()


def _row(created_by, client_id, *, name, redirect_uris, secret=None, scopes=None) -> OAuthClient:
    stored = secret or "jns_test_public_unused_placeholder"
    return OAuthClient(
        id=uuid.uuid4(),
        created_by=created_by,
        client_id=client_id,
        client_secret_hash=_hash(stored),
        client_secret_prefix=stored[:8],
        name=name,
        redirect_uris=redirect_uris,
        allowed_scopes=scopes or ["openid", "profile", "email", "offline_access"],
        grant_types=["authorization_code", "refresh_token"],
        is_active=True,
        is_confidential=secret is not None,
    )


class FakeClaudeNet:
    """claude.ai as the CIMD fetcher sees it: DNS plus the two documents."""

    def __init__(self):
        self.requests: list[httpx.Request] = []
        self.documents = {
            "/oauth/mcp-oauth-client-metadata": CLAUDE_DOC,
            "/oauth/claude-code-client-metadata": CLAUDE_CODE_DOC,
        }

    async def resolve(self, host):
        if host == "claude.ai":
            return [PUBLIC_IP]
        raise OSError("no such host")

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        document = self.documents.get(request.url.path)
        if document is None:
            return httpx.Response(404)
        return httpx.Response(
            200,
            headers={"content-type": "application/json", "cache-control": "public, max-age=300"},
            content=json.dumps(document).encode(),
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

    # Production shape: RS256 (tokens verify against the JWKS) and the
    # white-label issuer auth.madfam.io.
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    monkeypatch.setattr(jwt_manager, "algorithm", "RS256")
    monkeypatch.setattr(jwt_manager, "private_key", key)
    monkeypatch.setattr(jwt_manager, "public_key", key.public_key())
    monkeypatch.setattr(jwt_manager, "kid", "mcp-test-kid")
    monkeypatch.setenv("JANUA_CUSTOM_DOMAIN", "auth.madfam.io")

    net = FakeClaudeNet()
    monkeypatch.setattr(cimd, "resolver", net.resolve)
    monkeypatch.setattr(cimd, "transport_factory", lambda: httpx.MockTransport(net.handler))
    cimd.clear_cache()

    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    server = fakeredis.FakeServer()
    redis = ResilientRedisClient(fakeredis.aioredis.FakeRedis(server=server, decode_responses=True))

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

    admin = person("admin-mcp@janua.test", is_admin=True)
    director = person("direccion-mcp@janua.test")
    other = person("otra-persona-mcp@janua.test")
    async with factory() as session:
        session.add_all([admin, director, other])
        await session.flush()
        session.add_all(
            [
                _row(
                    admin.id,
                    REG_CLAUDE,
                    name="Claude (registro manual)",
                    redirect_uris=[CLAUDE_CALLBACK],
                ),
                _row(
                    admin.id,
                    REG_LOOPBACK,
                    name="Herramienta local",
                    redirect_uris=["http://localhost/callback"],
                    secret=REG_LOOPBACK_SECRET,
                ),
                _row(
                    admin.id,
                    REG_MIXED,
                    name="Mixta",
                    redirect_uris=[CLAUDE_CALLBACK, "https://evil.example/cb"],
                ),
                _row(admin.id, REG_OUTSIDE, name="Fuera", redirect_uris=[LEGACY_CALLBACK]),
                _row(
                    admin.id,
                    LEGACY,
                    name="madfam-legacy-regression",
                    redirect_uris=[LEGACY_CALLBACK],
                    secret=LEGACY_SECRET,
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
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as http:
            yield SimpleNamespace(
                http=http,
                factory=factory,
                redis=redis,
                server=server,
                net=net,
                admin=admin,
                director=director,
                other=other,
            )

    app.dependency_overrides.clear()
    app.dependency_overrides.update(saved)
    cimd.clear_cache()
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


def session_bearer(user) -> dict:
    token, _, _ = jwt_manager.create_access_token(user_id=str(user.id), email=user.email)
    return {"Authorization": f"Bearer {token}"}


def query(location: str) -> dict:
    return {key: values[0] for key, values in parse_qs(urlparse(location).query).items()}


def form_fields(page: str) -> tuple[str, str]:
    auth_request_id = re.search(r'name="auth_request_id" value="([^"]+)"', page).group(1)
    csrf_token = re.search(r'name="csrf_token" value="([^"]+)"', page).group(1)
    return auth_request_id, csrf_token


def jwks_claims(token: str, audience: str) -> tuple[dict, dict]:
    """(header, claims) of a token verified with the public JWKS, as a resource would."""
    header = jwt.get_unverified_header(token)
    (jwk,) = [k for k in jwt_manager.get_jwks()["keys"] if k["kid"] == header["kid"]]
    claims = jwt.decode(
        token,
        jwt.PyJWK(jwk).key,
        algorithms=["RS256"],
        audience=audience,
        issuer=ISSUER,
        options={"require": ["exp", "iat", "iss", "aud", "sub", "jti"]},
    )
    return header, claims


def authorize_params(
    challenge,
    *,
    client_id=CLAUDE,
    redirect_uri=CLAUDE_CALLBACK,
    resource=MAP,
    scope=ALL_SCOPES,
    state="claude-state-123",
    **extra,
) -> list[tuple[str, str]]:
    params = [
        ("response_type", "code"),
        ("client_id", client_id),
        ("redirect_uri", redirect_uri),
        ("code_challenge", challenge),
        ("code_challenge_method", "S256"),
    ]
    if state is not None:
        params.append(("state", state))
    if scope is not None:
        params.append(("scope", scope))
    for value in [resource] if isinstance(resource, str) else resource or []:
        params.append(("resource", value))
    for key, value in extra.items():
        if value is None:
            params = [(k, v) for k, v in params if k != key]
        else:
            params = [(k, v) for k, v in params if k != key] + [(key, value)]
    return params


async def authorize(env, params, user=None):
    headers = session_bearer(user) if user is not None else {}
    return await env.http.get("/api/v1/oauth/authorize", params=params, headers=headers)


async def consent(env, page_response, user, action="allow"):
    auth_request_id, csrf_token = form_fields(page_response.text)
    return await env.http.post(
        "/api/v1/oauth/consent",
        data={"auth_request_id": auth_request_id, "csrf_token": csrf_token, "action": action},
        headers=session_bearer(user),
    )


async def get_code(env, *, user=None, **kwargs):
    """Run /authorize + consent; return (code, verifier, callback query)."""
    user = user or env.director
    verifier, challenge = pkce()
    page = await authorize(env, authorize_params(challenge, **kwargs), user)
    assert page.status_code == 200, (
        page.status_code,
        page.headers.get("location"),
        page.text[:300],
    )
    redirect = await consent(env, page, user)
    assert redirect.status_code == 302, redirect.text
    params = query(redirect.headers["location"])
    assert "code" in params, params
    return params["code"], verifier, params


async def token(env, data, headers=None):
    return await env.http.post("/api/v1/oauth/token", data=data, headers=headers or {})


async def exchange(
    env, code, verifier, *, client_id=CLAUDE, redirect_uri=CLAUDE_CALLBACK, resource=MAP, **extra
):
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri,
        "client_id": client_id,
        "code_verifier": verifier,
    }
    if resource is not None:
        data["resource"] = resource
    data.update(extra)
    return await token(env, data)


async def refresh(env, refresh_token, *, client_id=CLAUDE, resource=MAP, **extra):
    data = {"grant_type": "refresh_token", "refresh_token": refresh_token, "client_id": client_id}
    if resource is not None:
        data["resource"] = resource
    data.update(extra)
    return await token(env, data)


async def connect(env, **kwargs):
    """The whole Claude connection: authorize, consent, exchange. Returns the token body."""
    client_id = kwargs.get("client_id", CLAUDE)
    redirect_uri = kwargs.get("redirect_uri", CLAUDE_CALLBACK)
    code, verifier, _ = await get_code(env, **kwargs)
    response = await exchange(env, code, verifier, client_id=client_id, redirect_uri=redirect_uri)
    assert response.status_code == 200, response.text
    return response.json()


def assert_oauth_error(response, error, status_code=400):
    assert response.status_code == status_code, response.text
    assert response.json()["error"] == error, response.text
    assert set(response.json()) == {"error", "error_description"}
    assert response.headers["cache-control"] == "no-store"


def assert_redirect_error(
    response, error, *, redirect_uri=CLAUDE_CALLBACK, state="claude-state-123"
):
    assert response.status_code == 302, response.text
    location = response.headers["location"]
    assert location.startswith(redirect_uri + "?"), location
    params = query(location)
    assert params["error"] == error, params
    assert params["iss"] == ISSUER
    if state:
        assert params["state"] == state
    return params


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------


class TestDiscovery:
    async def test_both_documents_are_the_same(self, env):
        oidc = await env.http.get("/.well-known/openid-configuration")
        rfc8414 = await env.http.get("/.well-known/oauth-authorization-server")
        assert oidc.status_code == rfc8414.status_code == 200
        assert oidc.json() == rfc8414.json()
        doc = rfc8414.json()
        assert doc["issuer"] == ISSUER
        assert doc["authorization_endpoint"] == f"{ISSUER}/api/v1/oauth/authorize"
        assert doc["token_endpoint"] == f"{ISSUER}/api/v1/oauth/token"
        assert doc["code_challenge_methods_supported"] == ["S256"]
        assert doc["client_id_metadata_document_supported"] is True
        assert doc["authorization_response_iss_parameter_supported"] is True
        assert "none" in doc["token_endpoint_auth_methods_supported"]
        assert {"map.ops:read", "map.cobro:read", "offline_access"} <= set(doc["scopes_supported"])

    async def test_jwks_publishes_the_signing_key(self, env):
        jwks = (await env.http.get("/.well-known/jwks.json")).json()
        assert [k["kid"] for k in jwks["keys"]] == ["mcp-test-kid"]


# ---------------------------------------------------------------------------
# Requests without `resource` keep the default flow
# ---------------------------------------------------------------------------


class TestWithoutResource:
    async def _legacy_code(self, env, user=None):
        verifier, challenge = pkce()
        response = await authorize(
            env,
            authorize_params(
                challenge,
                client_id=LEGACY,
                redirect_uri=LEGACY_CALLBACK,
                resource=None,
                scope="openid profile email offline_access",
                state="rp-state",
            ),
            user or env.director,
        )
        return response, verifier

    async def test_default_flow_is_unchanged_except_iss(self, env):
        response, verifier = await self._legacy_code(env)

        # First-party client: pre-consented, code issued straight away.
        assert response.status_code == 302
        params = query(response.headers["location"])
        assert response.headers["location"].startswith(LEGACY_CALLBACK + "?")
        assert params["state"] == "rp-state"
        assert params["iss"] == ISSUER  # RFC 9207, now on every response

        exchanged = await exchange(
            env,
            params["code"],
            verifier,
            client_id=LEGACY,
            redirect_uri=LEGACY_CALLBACK,
            resource=None,
            client_secret=LEGACY_SECRET,
        )
        assert exchanged.status_code == 200, exchanged.text
        body = exchanged.json()
        assert body["token_type"] == "Bearer" and body["id_token"] and body["refresh_token"]
        access = jwt_manager.get_unverified_claims(body["access_token"])
        assert access["type"] == "access" and access["aud"] != MAP
        assert jwt.get_unverified_header(body["access_token"]).get("typ") != "at+jwt"

        refreshed = await refresh(
            env, body["refresh_token"], client_id=LEGACY, resource=None, client_secret=LEGACY_SECRET
        )
        assert refreshed.status_code == 200, refreshed.text
        assert (
            jwt_manager.get_unverified_claims(refreshed.json()["access_token"])["type"] == "access"
        )

    async def test_default_errors_keep_janua_envelope(self, env):
        response = await token(
            env,
            {
                "grant_type": "authorization_code",
                "code": "nope",
                "client_id": LEGACY,
                "client_secret": LEGACY_SECRET,
            },
        )
        assert response.status_code == 400
        assert "invalid_grant" in response.json()["error"]["message"]

    async def test_a_resource_at_the_token_endpoint_cannot_upgrade_a_default_code(self, env):
        response, verifier = await self._legacy_code(env)
        code = query(response.headers["location"])["code"]
        exchanged = await exchange(
            env,
            code,
            verifier,
            client_id=LEGACY,
            redirect_uri=LEGACY_CALLBACK,
            client_secret=LEGACY_SECRET,
        )
        assert_oauth_error(exchanged, "invalid_target")


# ---------------------------------------------------------------------------
# /authorize
# ---------------------------------------------------------------------------


class TestAuthorizeTargets:
    @pytest.mark.parametrize(
        "resource",
        [
            "https://evil.example/api/mcp",
            "https://map.creatumundo.mx/api/mcp/",
            "map.creatumundo.mx/api/mcp",
            "/api/mcp",
            "https://map.creatumundo.mx/api/mcp#tools",
            "",
            [MAP, "https://evil.example/api/mcp"],
        ],
    )
    async def test_invalid_target_goes_back_with_state_and_iss(self, env, resource):
        _, challenge = pkce()
        response = await authorize(
            env, authorize_params(challenge, resource=resource), env.director
        )
        assert_redirect_error(response, "invalid_target")

    async def test_cimd_client_without_resource_is_invalid_target(self, env):
        _, challenge = pkce()
        response = await authorize(env, authorize_params(challenge, resource=None), env.director)
        assert_redirect_error(response, "invalid_target")

    async def test_equivalent_spelling_of_the_resource_is_accepted(self, env):
        _, challenge = pkce()
        response = await authorize(
            env,
            authorize_params(challenge, resource="HTTPS://MAP.CREATUMUNDO.MX/api/mcp"),
            env.director,
        )
        assert response.status_code == 200
        assert "MAP de Crea Tu Mundo" in response.text


class TestAuthorizeRefusals:
    async def test_the_form_post_authorize_refuses_resources(self, env):
        """POST /authorize would issue a code not bound to the resource: refused."""
        _, challenge = pkce()
        for form in (
            dict(authorize_params(challenge, client_id=REG_CLAUDE)),
            dict(authorize_params(challenge, resource=None)),
        ):
            form["csrf_token"] = "irrelevant"
            response = await env.http.post(
                "/api/v1/oauth/authorize", data=form, headers=session_bearer(env.director)
            )
            assert response.status_code == 400, response.text
            assert "protected resources" in response.text

    async def test_unknown_cimd_host_is_never_fetched_and_never_redirected(self, env):
        _, challenge = pkce()
        response = await authorize(
            env,
            authorize_params(challenge, client_id="https://evil.example/oauth/client.json"),
            env.director,
        )
        assert response.status_code == 400
        assert "location" not in response.headers
        assert "No se pudo autorizar" in response.text
        assert env.net.requests == []

    async def test_an_unpinned_claude_url_is_never_fetched(self, env):
        _, challenge = pkce()
        response = await authorize(
            env,
            authorize_params(challenge, client_id="https://claude.ai/oauth/another-document"),
            env.director,
        )
        assert response.status_code == 400 and "location" not in response.headers
        assert env.net.requests == []

        token_response = await exchange(
            env, "code", "v" * 43, client_id="https://claude.ai/oauth/another-document"
        )
        assert_oauth_error(token_response, "invalid_client", 401)

    async def test_http_client_id_is_refused(self, env):
        _, challenge = pkce()
        response = await authorize(
            env,
            authorize_params(
                challenge, client_id="http://claude.ai/oauth/mcp-oauth-client-metadata"
            ),
            env.director,
        )
        assert response.status_code == 400 and "location" not in response.headers
        assert env.net.requests == []

    async def test_redirect_uri_outside_the_document_is_not_redirected_to(self, env):
        _, challenge = pkce()
        response = await authorize(
            env,
            authorize_params(challenge, redirect_uri="https://evil.example/callback"),
            env.director,
        )
        assert response.status_code == 400
        assert "location" not in response.headers

    async def test_claude_redirect_needs_the_exact_string(self, env):
        _, challenge = pkce()
        response = await authorize(
            env,
            authorize_params(challenge, redirect_uri=CLAUDE_CALLBACK + "?x=1"),
            env.director,
        )
        assert response.status_code == 400 and "location" not in response.headers

    async def test_only_response_type_code(self, env):
        _, challenge = pkce()
        response = await authorize(
            env, authorize_params(challenge, response_type="token"), env.director
        )
        assert_redirect_error(response, "unsupported_response_type")

    @pytest.mark.parametrize(
        "extra",
        [
            {"code_challenge": None},
            {"code_challenge_method": "plain"},
            {"code_challenge_method": None},
            {"code_challenge": "too-short"},
        ],
    )
    async def test_pkce_s256_is_required(self, env, extra):
        _, challenge = pkce()
        response = await authorize(env, authorize_params(challenge, **extra), env.director)
        assert_redirect_error(response, "invalid_request")

    async def test_no_scope_of_the_resource(self, env):
        _, challenge = pkce()
        response = await authorize(
            env, authorize_params(challenge, scope="openid profile email"), env.director
        )
        assert_redirect_error(response, "invalid_scope")

    async def test_prompt_none_without_session_is_login_required(self, env):
        _, challenge = pkce()
        response = await authorize(env, authorize_params(challenge, prompt="none"))
        assert_redirect_error(response, "login_required")

    async def test_prompt_none_with_session_is_consent_required(self, env):
        _, challenge = pkce()
        response = await authorize(env, authorize_params(challenge, prompt="none"), env.director)
        assert_redirect_error(response, "consent_required")


class TestConsentScreen:
    async def test_spanish_page_names_resource_host_and_scopes(self, env):
        _, challenge = pkce()
        response = await authorize(env, authorize_params(challenge), env.director)

        assert response.status_code == 200
        assert response.headers["cache-control"] == "no-store"
        page = response.text
        assert '<html lang="es">' in page
        assert "claude.ai quiere acceder al MAP de Crea Tu Mundo" in page
        assert "Consultar la operación del MAP, sin nombres ni datos clínicos" in page
        assert "Consultar la cobranza del MAP por clave de familia" in page
        assert "Mantener el acceso sin pedirte que vuelvas a iniciar sesión" in page
        # The self-asserted name is never shown alone: the host leads.
        assert "Se identifica como «Claude»" in page
        assert "Atención" not in page  # not a loopback redirect
        assert "direccion-mcp@janua.test" in page
        assert "Permitir" in page and "Cancelar" in page
        assert "Authorize Application" not in page

    async def test_claude_code_on_loopback_gets_the_local_app_warning(self, env):
        _, challenge = pkce()
        response = await authorize(
            env,
            authorize_params(challenge, client_id=CLAUDE_CODE, redirect_uri=CODE_LOOPBACK),
            env.director,
        )
        assert response.status_code == 200, response.text
        page = response.text
        assert "claude.ai quiere acceder al MAP de Crea Tu Mundo" in page
        assert "una aplicación en esta computadora" in page
        assert "Atención" in page and "localhost" in page
        assert "Se identifica como «Claude Code»" in page

    async def test_only_requested_scopes_are_listed(self, env):
        _, challenge = pkce()
        response = await authorize(
            env, authorize_params(challenge, scope="map.ops:read"), env.director
        )
        page = response.text
        assert "Consultar la operación del MAP" in page
        assert "cobranza" not in page
        assert "Mantener el acceso" not in page  # no offline_access requested

    async def test_consent_is_asked_every_time(self, env):
        await connect(env)
        _, challenge = pkce()
        again = await authorize(env, authorize_params(challenge), env.director)
        assert again.status_code == 200 and "Permitir" in again.text

    async def test_document_text_is_escaped(self, env):
        env.net.documents["/oauth/mcp-oauth-client-metadata"] = dict(
            CLAUDE_DOC, client_name='<script>alert("x")</script>'
        )
        _, challenge = pkce()
        response = await authorize(env, authorize_params(challenge), env.director)
        assert "<script>alert" not in response.text
        assert "&lt;script&gt;" in response.text

    async def test_deny_returns_access_denied_with_iss(self, env):
        _, challenge = pkce()
        page = await authorize(env, authorize_params(challenge), env.director)
        response = await consent(env, page, env.director, action="deny")
        assert_redirect_error(response, "access_denied")

    async def test_consent_needs_the_csrf_token(self, env):
        _, challenge = pkce()
        page = await authorize(env, authorize_params(challenge), env.director)
        auth_request_id, _ = form_fields(page.text)
        response = await env.http.post(
            "/api/v1/oauth/consent",
            data={"auth_request_id": auth_request_id, "csrf_token": "forged", "action": "allow"},
            headers=session_bearer(env.director),
        )
        assert response.status_code == 403

    async def test_another_signed_in_person_cannot_answer(self, env):
        _, challenge = pkce()
        page = await authorize(env, authorize_params(challenge), env.director)
        response = await consent(env, page, env.other)
        assert response.status_code == 403  # the CSRF token is the director's

    async def test_success_redirect_carries_code_state_and_iss(self, env):
        _, _, params = await get_code(env)
        assert params["state"] == "claude-state-123"
        assert params["iss"] == ISSUER
        assert set(params) == {"code", "state", "iss"}


# ---------------------------------------------------------------------------
# Code exchange
# ---------------------------------------------------------------------------


class TestCodeExchange:
    async def test_access_token_is_rfc9068_bound_to_the_map(self, env):
        body = await connect(env)

        assert body["token_type"] == "Bearer"
        assert body["expires_in"] == 900
        assert body["scope"] == "map.ops:read map.cobro:read offline_access"
        assert body["refresh_token"]
        assert "id_token" not in body

        header, claims = jwks_claims(body["access_token"], audience=MAP)
        assert header["typ"] == "at+jwt" and header["alg"] == "RS256"
        assert header["kid"] == "mcp-test-kid"
        assert claims["aud"] == MAP
        assert claims["iss"] == ISSUER
        assert claims["sub"] == str(env.director.id)
        assert claims["client_id"] == CLAUDE
        assert claims["scope"] == "map.ops:read map.cobro:read"
        assert claims["exp"] - claims["iat"] == 900
        assert claims["jti"]
        # Nothing that would make it a Janua session, and no personal data.
        assert "type" not in claims and "email" not in claims and "roles" not in claims

    async def test_token_response_is_never_cached(self, env):
        code, verifier, _ = await get_code(env)
        response = await exchange(env, code, verifier)
        assert response.headers["cache-control"] == "no-store"
        assert response.headers["pragma"] == "no-cache"

    async def test_claude_code_on_any_loopback_port(self, env):
        for redirect in ("http://localhost:61111/callback", "http://127.0.0.1:50000/callback"):
            body = await connect(env, client_id=CLAUDE_CODE, redirect_uri=redirect)
            _, claims = jwks_claims(body["access_token"], audience=MAP)
            assert claims["client_id"] == CLAUDE_CODE

    async def test_the_cimd_document_is_fetched_once_and_cached(self, env):
        await connect(env)
        await connect(env)
        assert len(env.net.requests) == 1

    async def test_sub_is_the_same_subject_as_the_id_token(self, env):
        """crea-map stores the Janua `sub` in Member.januaSubject; the MCP token
        must carry the very same value for the same person."""
        legacy = TestWithoutResource()
        response, verifier = await legacy._legacy_code(env)
        code = query(response.headers["location"])["code"]
        oidc = await exchange(
            env,
            code,
            verifier,
            client_id=LEGACY,
            redirect_uri=LEGACY_CALLBACK,
            resource=None,
            client_secret=LEGACY_SECRET,
        )
        id_token_sub = jwt_manager.get_unverified_claims(oidc.json()["id_token"])["sub"]
        session_sub = jwt_manager.get_unverified_claims(oidc.json()["access_token"])["sub"]

        mcp = await connect(env)
        _, claims = jwks_claims(mcp["access_token"], audience=MAP)
        assert claims["sub"] == id_token_sub == session_sub == str(env.director.id)

    async def test_resource_may_be_omitted_at_the_token_endpoint(self, env):
        code, verifier, _ = await get_code(env)
        response = await exchange(env, code, verifier, resource=None)
        assert response.status_code == 200
        assert jwt_manager.get_unverified_claims(response.json()["access_token"])["aud"] == MAP

    @pytest.mark.parametrize(
        "resource",
        ["https://evil.example/api/mcp", "https://map.creatumundo.mx/api/mcp/", "not a uri"],
    )
    async def test_a_different_resource_is_invalid_target(self, env, resource):
        code, verifier, _ = await get_code(env)
        assert_oauth_error(await exchange(env, code, verifier, resource=resource), "invalid_target")

    async def test_code_is_single_use(self, env):
        code, verifier, _ = await get_code(env)
        assert (await exchange(env, code, verifier)).status_code == 200
        assert_oauth_error(await exchange(env, code, verifier), "invalid_grant")

    async def test_wrong_or_missing_verifier(self, env):
        code, verifier, _ = await get_code(env)
        assert_oauth_error(await exchange(env, code, pkce()[0]), "invalid_grant")
        assert_oauth_error(await exchange(env, code, None, code_verifier=""), "invalid_request")
        # The code survived the failed attempts; the right verifier still works.
        assert (await exchange(env, code, verifier)).status_code == 200

    async def test_code_belongs_to_its_client(self, env):
        code, verifier, _ = await get_code(env)
        assert_oauth_error(
            await exchange(env, code, verifier, client_id=CLAUDE_CODE), "invalid_grant"
        )

    async def test_redirect_uri_must_match(self, env):
        code, verifier, _ = await get_code(env)
        response = await exchange(env, code, verifier, redirect_uri=CLAUDE_CALLBACK + "x")
        assert_oauth_error(response, "invalid_grant")

    async def test_cimd_client_must_not_send_a_secret(self, env):
        code, verifier, _ = await get_code(env)
        response = await exchange(env, code, verifier, client_secret="anything")
        assert_oauth_error(response, "invalid_client", 401)

    async def test_unknown_cimd_host_at_the_token_endpoint(self, env):
        response = await exchange(env, "x", "y" * 43, client_id="https://evil.example/c.json")
        assert_oauth_error(response, "invalid_client", 401)

    async def test_scopes_are_requested_intersect_allowed(self, env):
        body = await connect(env, scope="map.ops:read openid profile offline_access")
        assert body["scope"] == "map.ops:read offline_access"
        _, claims = jwks_claims(body["access_token"], audience=MAP)
        assert claims["scope"] == "map.ops:read"

    async def test_no_offline_access_means_no_refresh_token(self, env):
        body = await connect(env, scope="map.ops:read map.cobro:read")
        assert "refresh_token" not in body
        assert body["scope"] == "map.ops:read map.cobro:read"

    @pytest.mark.parametrize("scope", [None, "", "  "])
    async def test_no_scope_parameter_requests_every_resource_scope(self, env, scope):
        body = await connect(env, scope=scope)
        assert body["scope"] == "map.ops:read map.cobro:read"
        assert "refresh_token" not in body

    async def test_empty_scope_on_refresh_keeps_the_grant(self, env):
        body = await connect(env)
        response = await refresh(env, body["refresh_token"], scope="")
        assert response.status_code == 200, response.text
        assert (
            jwt_manager.get_unverified_claims(response.json()["access_token"])["scope"]
            == "map.ops:read map.cobro:read"
        )

    async def test_form_encoding_is_what_the_endpoint_reads(self, env):
        code, verifier, _ = await get_code(env)
        body = (
            f"grant_type=authorization_code&code={code}&client_id={CLAUDE}"
            f"&redirect_uri={CLAUDE_CALLBACK}&code_verifier={verifier}&resource={MAP}"
        )
        from urllib.parse import quote

        encoded = "&".join(
            f"{k}={quote(v, safe='')}" for k, v in (pair.split("=", 1) for pair in body.split("&"))
        )
        response = await env.http.post(
            "/api/v1/oauth/token",
            content=encoded,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        assert response.status_code == 200, response.text


# ---------------------------------------------------------------------------
# Refresh
# ---------------------------------------------------------------------------


class TestRefresh:
    async def test_rotation_keeps_the_audience(self, env):
        first = await connect(env)
        second = await refresh(env, first["refresh_token"])
        assert second.status_code == 200, second.text
        body = second.json()
        assert body["refresh_token"] and body["refresh_token"] != first["refresh_token"]
        assert body["scope"] == "map.ops:read map.cobro:read offline_access"
        _, claims = jwks_claims(body["access_token"], audience=MAP)
        assert claims["sub"] == str(env.director.id)
        assert second.headers["cache-control"] == "no-store"

        third = await refresh(env, body["refresh_token"], resource=None)  # may be omitted
        assert third.status_code == 200
        assert jwt_manager.get_unverified_claims(third.json()["access_token"])["aud"] == MAP

    async def test_reuse_kills_the_family(self, env):
        first = await connect(env)
        rotated = (await refresh(env, first["refresh_token"])).json()["refresh_token"]

        assert_oauth_error(await refresh(env, first["refresh_token"]), "invalid_grant")
        # The legitimate descendant dies with it: whoever replayed cannot keep going.
        assert_oauth_error(await refresh(env, rotated), "invalid_grant")

    async def test_downscope_without_upscope(self, env):
        first = await connect(env)
        narrowed = await refresh(env, first["refresh_token"], scope="map.ops:read")
        assert narrowed.status_code == 200, narrowed.text
        assert (
            jwt_manager.get_unverified_claims(narrowed.json()["access_token"])["scope"]
            == "map.ops:read"
        )
        # The rotated refresh token keeps the original grant (RFC 6749 §6).
        full = await refresh(env, narrowed.json()["refresh_token"])
        assert (
            jwt_manager.get_unverified_claims(full.json()["access_token"])["scope"]
            == "map.ops:read map.cobro:read"
        )

    async def test_a_refresh_cannot_add_scopes(self, env):
        body = await connect(env, scope="map.ops:read offline_access")
        response = await refresh(env, body["refresh_token"], scope="map.ops:read map.cobro:read")
        assert_oauth_error(response, "invalid_scope")

    async def test_a_different_resource_is_invalid_target(self, env):
        body = await connect(env)
        response = await refresh(env, body["refresh_token"], resource="https://evil.example/mcp")
        assert_oauth_error(response, "invalid_target")

    @pytest.mark.parametrize("bad", ["garbage", "a.b.c", ""])
    async def test_invalid_refresh_token_is_invalid_grant(self, env, bad):
        response = await refresh(env, bad)
        if bad:
            assert_oauth_error(response, "invalid_grant")
        else:
            assert_oauth_error(response, "invalid_request")

    async def test_tampered_refresh_token(self, env):
        body = await connect(env)
        header, payload, signature = body["refresh_token"].split(".")
        claims = json.loads(base64.urlsafe_b64decode(payload + "=="))
        claims["scope"] = "map.ops:read map.cobro:read map.admin:write offline_access"
        forged_payload = base64.urlsafe_b64encode(json.dumps(claims).encode()).rstrip(b"=").decode()
        assert_oauth_error(
            await refresh(env, f"{header}.{forged_payload}.{signature}"), "invalid_grant"
        )

    async def test_refresh_token_belongs_to_its_client(self, env):
        body = await connect(env)
        response = await refresh(env, body["refresh_token"], client_id=CLAUDE_CODE)
        assert_oauth_error(response, "invalid_grant")

    async def test_expired_and_over_the_family_lifetime(self, env):
        now = int(time.time())
        expired = resource_tokens.mint_refresh_token(
            resource=MAP_CREA_TU_MUNDO,
            subject=str(env.director.id),
            client_id=CLAUDE,
            scope=ALL_SCOPES,
            now=now - 8 * 86400,
        )
        assert_oauth_error(await refresh(env, expired), "invalid_grant")

        over_lifetime = resource_tokens.mint_refresh_token(
            resource=MAP_CREA_TU_MUNDO,
            subject=str(env.director.id),
            client_id=CLAUDE,
            scope=ALL_SCOPES,
            family="old-family",
            family_iat=now - 31 * 86400,
            now=now - 60,
        )
        assert jwt_manager.get_unverified_claims(over_lifetime)["exp"] < now
        assert_oauth_error(await refresh(env, over_lifetime), "invalid_grant")

    @pytest.mark.parametrize(
        "change",
        [{"status": UserStatus.SUSPENDED}, {"status": UserStatus.DELETED}, {"is_active": False}],
    )
    async def test_inactive_person_cannot_refresh(self, env, change):
        body = await connect(env)
        async with env.factory() as db:
            await db.execute(update(User).where(User.id == env.director.id).values(**change))
            await db.commit()
        assert_oauth_error(await refresh(env, body["refresh_token"]), "invalid_grant")

    async def test_inactive_person_cannot_redeem_a_code(self, env):
        code, verifier, _ = await get_code(env)
        async with env.factory() as db:
            await db.execute(
                update(User).where(User.id == env.director.id).values(status=UserStatus.SUSPENDED)
            )
            await db.commit()
        assert_oauth_error(await exchange(env, code, verifier), "invalid_grant")

    async def test_revocation_by_claude_ends_the_connection(self, env):
        body = await connect(env)
        response = await env.http.post(
            "/api/v1/oauth/revoke",
            data={
                "token": body["refresh_token"],
                "token_type_hint": "refresh_token",
                "client_id": CLAUDE,
            },
        )
        assert response.status_code == 200
        assert_oauth_error(await refresh(env, body["refresh_token"]), "invalid_grant")

    async def test_another_client_cannot_revoke_it(self, env):
        body = await connect(env)
        response = await env.http.post(
            "/api/v1/oauth/revoke", data={"token": body["refresh_token"], "client_id": CLAUDE_CODE}
        )
        assert response.status_code == 200  # RFC 7009: never says whether it existed
        assert (await refresh(env, body["refresh_token"])).status_code == 200

    async def test_redis_down_is_retryable_not_invalid_grant(self, env):
        body = await connect(env)
        env.server.connected = False
        response = await refresh(env, body["refresh_token"])
        assert response.status_code == 503
        assert response.headers["retry-after"].isdigit()
        env.server.connected = True
        assert (await refresh(env, body["refresh_token"])).status_code == 200


# ---------------------------------------------------------------------------
# Clients registered in Janua (pre-registration; the DCR-shaped path)
# ---------------------------------------------------------------------------


class TestRegisteredClients:
    async def test_public_client_with_claudes_callback(self, env):
        body = await connect(env, client_id=REG_CLAUDE)
        _, claims = jwks_claims(body["access_token"], audience=MAP)
        assert claims["client_id"] == REG_CLAUDE

    async def test_its_consent_page_names_the_redirect_host(self, env):
        _, challenge = pkce()
        response = await authorize(
            env, authorize_params(challenge, client_id=REG_CLAUDE), env.director
        )
        assert "claude.ai quiere acceder al MAP de Crea Tu Mundo" in response.text
        assert "Se identifica como «Claude (registro manual)»" in response.text

    async def test_confidential_loopback_client_any_port_with_secret(self, env):
        redirect = "http://localhost:47001/callback"
        code, verifier, _ = await get_code(env, client_id=REG_LOOPBACK, redirect_uri=redirect)
        no_secret = await exchange(
            env, code, verifier, client_id=REG_LOOPBACK, redirect_uri=redirect
        )
        assert_oauth_error(no_secret, "invalid_client", 401)
        ok = await exchange(
            env,
            code,
            verifier,
            client_id=REG_LOOPBACK,
            redirect_uri=redirect,
            client_secret=REG_LOOPBACK_SECRET,
        )
        assert ok.status_code == 200, ok.text

    async def test_loopback_registered_client_page(self, env):
        _, challenge = pkce()
        response = await authorize(
            env,
            authorize_params(
                challenge, client_id=REG_LOOPBACK, redirect_uri="http://localhost:47001/callback"
            ),
            env.director,
        )
        assert "Una aplicación en esta computadora quiere acceder al MAP" in response.text
        assert "Atención" in response.text

    async def test_client_with_any_redirect_outside_the_policy(self, env):
        _, challenge = pkce()
        response = await authorize(
            env, authorize_params(challenge, client_id=REG_MIXED), env.director
        )
        assert_redirect_error(response, "unauthorized_client")

    async def test_client_whose_redirects_are_all_outside(self, env):
        _, challenge = pkce()
        response = await authorize(
            env,
            authorize_params(challenge, client_id=REG_OUTSIDE, redirect_uri=LEGACY_CALLBACK),
            env.director,
        )
        assert_redirect_error(response, "unauthorized_client", redirect_uri=LEGACY_CALLBACK)

    async def test_unknown_registered_client_is_a_page_not_a_redirect(self, env):
        _, challenge = pkce()
        response = await authorize(
            env, authorize_params(challenge, client_id="jnc_nobody"), env.director
        )
        assert response.status_code == 400 and "location" not in response.headers


# ---------------------------------------------------------------------------
# A resource token is not a Janua session (and the reverse)
# ---------------------------------------------------------------------------


class TestIsolation:
    async def test_mcp_access_token_is_refused_by_janua(self, env):
        access = (await connect(env))["access_token"]
        bearer = {"Authorization": f"Bearer {access}"}
        assert (await env.http.get("/api/v1/oauth/userinfo", headers=bearer)).status_code == 401
        assert (await env.http.get("/api/v1/auth/me", headers=bearer)).status_code == 401

        # As a Bearer at /authorize it authenticates nobody: back to the login.
        _, challenge = pkce()
        response = await env.http.get(
            "/api/v1/oauth/authorize",
            params=authorize_params(
                challenge, client_id=LEGACY, redirect_uri=LEGACY_CALLBACK, resource=None
            ),
            headers=bearer,
        )
        assert response.status_code == 302
        assert response.headers["location"].startswith("/api/v1/auth/login?")

    async def test_resource_refresh_token_is_refused_by_janua_refresh(self, env):
        refresh_token = (await connect(env))["refresh_token"]
        response = await env.http.post(
            "/api/v1/auth/refresh", json={"refresh_token": refresh_token}
        )
        assert response.status_code == 401

    async def test_introspection_reports_resource_tokens_inactive(self, env):
        body = await connect(env, client_id=REG_CLAUDE)
        for token_value in (body["access_token"], body["refresh_token"]):
            response = await env.http.post(
                "/api/v1/oauth/introspect", data={"token": token_value, "client_id": REG_CLAUDE}
            )
            assert response.status_code == 200
            assert response.json() == {"active": False}

    async def test_janua_session_token_is_not_a_map_token(self, env):
        token, _, _ = jwt_manager.create_access_token(
            user_id=str(env.director.id), email=env.director.email, additional_claims={"aud": MAP}
        )
        assert resource_tokens.verify_access_token(token, MAP_CREA_TU_MUNDO) is None

    async def test_resource_verifier_accepts_the_real_token(self, env):
        access = (await connect(env))["access_token"]
        claims = resource_tokens.verify_access_token(access, MAP_CREA_TU_MUNDO)
        assert claims and claims["aud"] == MAP


# ---------------------------------------------------------------------------
# Sign-in in the middle of the flow
# ---------------------------------------------------------------------------


class TestSignInResume:
    async def test_unauthenticated_request_goes_to_the_magic_link_login(self, env):
        _, challenge = pkce()
        response = await authorize(env, authorize_params(challenge))
        assert response.status_code == 302
        location = response.headers["location"]
        assert location.startswith("/api/v1/auth/login?")
        params = query(location)
        assert params["login_method"] == "magic_link"
        assert params["client_name"] == "MAP de Crea Tu Mundo (claude.ai)"
        stored = json.loads(
            await env.redis.strict_get(f"oauth:pre_login:{params['auth_request_id']}")
        )
        assert stored["resource"] == MAP and stored["client_id"] == CLAUDE
        ttl = await env.redis.redis.ttl(f"oauth:pre_login:{params['auth_request_id']}")
        assert 15 * 60 < ttl <= 20 * 60

    async def test_resume_url_rebuilds_the_request_with_its_resource(self, env):
        _, challenge = pkce()
        login = await authorize(env, authorize_params(challenge))
        auth_request_id = query(login.headers["location"])["auth_request_id"]

        resumed = await env.http.get(
            "/api/v1/oauth/authorize/resume", params={"auth_request_id": auth_request_id}
        )
        assert resumed.status_code == 302
        target = resumed.headers["location"]
        assert target.startswith("/api/v1/oauth/authorize?")
        params = parse_qs(urlparse(target).query)
        assert params["resource"] == [MAP]
        assert params["client_id"] == [CLAUDE]
        assert params["code_challenge"] == [challenge]

        # Signed in now: the rebuilt request reaches the consent screen.
        page = await env.http.get(target, headers=session_bearer(env.director))
        assert page.status_code == 200 and "Permitir" in page.text

    async def test_expired_resume_is_a_page(self, env):
        response = await env.http.get(
            "/api/v1/oauth/authorize/resume", params={"auth_request_id": "expired-request-id"}
        )
        assert response.status_code == 400
        assert "location" not in response.headers

    async def test_magic_link_continuation_is_short_for_resource_requests(self, env):
        from app.routers.v1.auth import _oauth_continuation_url

        _, challenge = pkce()
        login = await authorize(env, authorize_params(challenge))
        auth_request_id = query(login.headers["location"])["auth_request_id"]
        async with env.factory() as db:
            url = await _oauth_continuation_url(
                auth_request_id=auth_request_id,
                client_id=CLAUDE,
                next_url="/",
                redis=env.redis,
                db=db,
            )
        assert url.endswith(f"/api/v1/oauth/authorize/resume?auth_request_id={auth_request_id}")
        assert len(url) < 500  # MagicLink.redirect_url is String(500)

    async def test_default_requests_keep_the_full_continuation(self, env):
        from app.routers.v1.auth import _oauth_continuation_url

        await env.redis.strict_set(
            "oauth:pre_login:legacy-id",
            json.dumps(
                {
                    "response_type": "code",
                    "client_id": LEGACY,
                    "redirect_uri": LEGACY_CALLBACK,
                    "state": "s",
                }
            ),
            ex=600,
        )
        async with env.factory() as db:
            url = await _oauth_continuation_url(
                auth_request_id="legacy-id", client_id=LEGACY, next_url="/", redis=env.redis, db=db
            )
        assert "/api/v1/oauth/authorize?" in url and "resume" not in url
        assert "resource" not in url

    async def test_password_and_second_factor_paths_keep_the_resource(self, env):
        from app.routers.v1.auth import _resolve_oauth_redirect_target

        _, challenge = pkce()
        login = await authorize(env, authorize_params(challenge))
        auth_request_id = query(login.headers["location"])["auth_request_id"]
        async with env.factory() as db:
            target = await _resolve_oauth_redirect_target(
                auth_request_id=auth_request_id,
                client_id=CLAUDE,
                next_url="/",
                redis=env.redis,
                db=db,
            )
        assert parse_qs(urlparse(target).query)["resource"] == [MAP]


class TestContentSecurityPolicy:
    async def test_form_action_allows_claudes_callback(self, env):
        response = await env.http.get("/.well-known/oauth-authorization-server")
        csp = response.headers["content-security-policy"]
        form_action = next(d for d in csp.split(";") if d.strip().startswith("form-action"))
        sources = set(form_action.split())
        assert {"https://claude.ai", "http://localhost:*", "http://127.0.0.1:*"} <= sources
