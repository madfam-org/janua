"""
Service-token (client_credentials) tests for the RFC 0024 §P4 consolidation
clients — zavlo-cfdi-emitter (cfdi:issue → karafiel-api) and
routecraft-billing-relay (billing:events → dhanam-api).

Covers, end-to-end through POST /api/v1/oauth/token:
- happy-path token issuance (scoped RS256/HS256 JWT, verifiable claims)
- wrong-secret rejection
- scope enforcement (fail closed on scopes outside the client allowlist)
- expiry (token exp == advertised expires_in; expired tokens are inactive)

See docs/service-tokens.md for the integration contract.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

import bcrypt
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.database import get_db as core_get_db
from app.core.jwt_manager import jwt_manager
from app.core.redis import get_redis
from app.database import get_db
from app.main import app
from app.models import Base, OAuthClient, User, UserStatus
from app.routers.v1.oauth_provider import SERVICE_TOKEN_TTL_SECONDS
from app.routers.v1.oauth_provider import get_redis as oauth_provider_get_redis

TOKEN_URL = "/api/v1/oauth/token"
INTROSPECT_URL = "/api/v1/oauth/introspect"

# Placeholder credentials for tests only — never real secrets.
ZAVLO_CLIENT_ID = "jnc_test_zavlo_cfdi_emitter"
ZAVLO_SECRET = "jns_test_zavlo_secret_placeholder"
NAUTA_CLIENT_ID = "jnc_test_nauta_legal_drafts"
NAUTA_SECRET = "jns_test_nauta_secret_placeholder"
ROUTECRAFT_CLIENT_ID = "jnc_test_routecraft_billing_relay"
ROUTECRAFT_SECRET = "jns_test_routecraft_secret_placeholder"
INTERACTIVE_CLIENT_ID = "jnc_test_interactive_only"
INTERACTIVE_SECRET = "jns_test_interactive_secret_placeholder"


def _hash(secret: str) -> str:
    return bcrypt.hashpw(secret.encode(), bcrypt.gensalt(rounds=4)).decode()


def _service_client(
    *,
    created_by: uuid.UUID,
    name: str,
    client_id: str,
    secret: str,
    audience: str,
    allowed_scopes: list[str],
    grant_types: list[str],
) -> OAuthClient:
    return OAuthClient(
        id=uuid.uuid4(),
        created_by=created_by,
        client_id=client_id,
        client_secret_hash=_hash(secret),
        client_secret_prefix=secret[:8],
        name=name,
        redirect_uris=[],
        allowed_scopes=allowed_scopes,
        grant_types=grant_types,
        audience=audience,
        is_active=True,
        is_confidential=True,
    )


@pytest_asyncio.fixture
async def service_token_client():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db():
        async with session_factory() as session:
            yield session

    redis = AsyncMock()
    redis.ping.return_value = True
    redis.get.return_value = None
    redis.set.return_value = True
    # Revocation-list reads (introspection, refresh grant): nothing revoked.
    redis.strict_exists.return_value = 0

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[core_get_db] = override_get_db
    app.dependency_overrides[get_redis] = lambda: redis
    # tests/conftest.py rebinds app.core.redis.get_redis after some routers
    # imported the original, so override the router's own reference too.
    app.dependency_overrides[oauth_provider_get_redis] = lambda: redis

    admin_id = uuid.uuid4()
    admin = User(
        id=admin_id,
        email="admin-service-tokens@janua.test",
        email_verified=True,
        status=UserStatus.ACTIVE,
        is_admin=True,
        is_active=True,
    )

    async with session_factory() as session:
        session.add(admin)
        session.add(
            _service_client(
                created_by=admin_id,
                name="zavlo-cfdi-emitter",
                client_id=ZAVLO_CLIENT_ID,
                secret=ZAVLO_SECRET,
                audience="karafiel-api",
                allowed_scopes=["cfdi:issue"],
                grant_types=["client_credentials"],
            )
        )
        session.add(
            _service_client(
                created_by=admin_id,
                name="nauta-legal-drafts",
                client_id=NAUTA_CLIENT_ID,
                secret=NAUTA_SECRET,
                audience="karafiel-api",
                allowed_scopes=["legal:draft", "legal:client-profile"],
                grant_types=["client_credentials"],
            )
        )
        session.add(
            _service_client(
                created_by=admin_id,
                name="routecraft-billing-relay",
                client_id=ROUTECRAFT_CLIENT_ID,
                secret=ROUTECRAFT_SECRET,
                audience="dhanam-api",
                allowed_scopes=["billing:events"],
                grant_types=["client_credentials"],
            )
        )
        # Interactive-only client: client_credentials must be refused.
        session.add(
            _service_client(
                created_by=admin_id,
                name="interactive-only-app",
                client_id=INTERACTIVE_CLIENT_ID,
                secret=INTERACTIVE_SECRET,
                audience="janua.dev",
                allowed_scopes=["openid", "profile", "email"],
                grant_types=["authorization_code", "refresh_token"],
            )
        )
        await session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()
    await engine.dispose()


def _error_message(response) -> str:
    """Extract the error detail regardless of error-envelope shape.

    Plain FastAPI HTTPExceptions render as {"detail": ...}; the app's
    error-handling middleware re-wraps them as {"error": {"message": ...}}.
    """
    body = response.json()
    if "detail" in body:
        return str(body["detail"])
    return str(body.get("error", {}).get("message", ""))


async def _request_token(client: AsyncClient, **overrides) -> object:
    data = {
        "grant_type": "client_credentials",
        "client_id": ZAVLO_CLIENT_ID,
        "client_secret": ZAVLO_SECRET,
        "scope": "cfdi:issue",
    }
    data.update(overrides)
    return await client.post(TOKEN_URL, data=data)


class TestServiceTokenIssuance:
    """Happy-path client_credentials issuance for the consolidation clients."""

    async def test_zavlo_client_receives_scoped_service_token(self, service_token_client):
        response = await _request_token(service_token_client)
        assert response.status_code == 200, response.text

        body = response.json()
        assert body["token_type"] == "Bearer"
        assert body["scope"] == "cfdi:issue"
        assert body["expires_in"] == SERVICE_TOKEN_TTL_SECONDS
        assert body["refresh_token"] is None
        assert body["id_token"] is None

        # The token must verify against the karafiel-api audience with the
        # machine-identity claim shape documented in docs/service-tokens.md.
        claims = jwt_manager.verify_token(
            body["access_token"], token_type="access", audience="karafiel-api"
        )
        assert claims is not None
        assert claims["sub"] == f"service-account:{ZAVLO_CLIENT_ID}"
        assert claims["client_id"] == ZAVLO_CLIENT_ID
        assert claims["token_use"] == "client_credentials"
        assert claims["actor_type"] == "service_account"
        assert "service_account" in claims["roles"]
        assert claims["scope"] == "cfdi:issue"
        assert claims["aud"] == "karafiel-api"

    async def test_nauta_legal_drafts_client_receives_scoped_service_token(
        self, service_token_client
    ):
        # The Nauta -> Karafiel legal-drafts edge (nauta plan doc, step D3.5):
        # audience karafiel-api, scope legal:draft, machine-identity sub.
        response = await _request_token(
            service_token_client,
            client_id=NAUTA_CLIENT_ID,
            client_secret=NAUTA_SECRET,
            scope="legal:draft",
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["scope"] == "legal:draft"
        claims = jwt_manager.verify_token(
            body["access_token"], token_type="access", audience="karafiel-api"
        )
        assert claims is not None
        assert claims["sub"] == f"service-account:{NAUTA_CLIENT_ID}"
        assert claims["actor_type"] == "service_account"
        assert claims["scope"] == "legal:draft"

    async def test_nauta_client_receives_client_profile_scoped_token(self, service_token_client):
        # karafiel PR #148: legal:client-profile lets Nauta create/update a
        # client's OWN ClientProfile at /api/v1/legal/clients.
        response = await _request_token(
            service_token_client,
            client_id=NAUTA_CLIENT_ID,
            client_secret=NAUTA_SECRET,
            scope="legal:client-profile",
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["scope"] == "legal:client-profile"
        claims = jwt_manager.verify_token(
            body["access_token"], token_type="access", audience="karafiel-api"
        )
        assert claims is not None
        assert claims["sub"] == f"service-account:{NAUTA_CLIENT_ID}"
        assert claims["actor_type"] == "service_account"
        assert claims["scope"] == "legal:client-profile"

    async def test_nauta_legal_scopes_are_independent(self, service_token_client):
        """Neither legal scope implies the other — each token carries only
        what it asked for, so Karafiel can guard drafts and client-profile
        routes separately."""
        draft_only = await _request_token(
            service_token_client,
            client_id=NAUTA_CLIENT_ID,
            client_secret=NAUTA_SECRET,
            scope="legal:draft",
        )
        assert draft_only.status_code == 200, draft_only.text
        assert draft_only.json()["scope"] == "legal:draft"

        profile_only = await _request_token(
            service_token_client,
            client_id=NAUTA_CLIENT_ID,
            client_secret=NAUTA_SECRET,
            scope="legal:client-profile",
        )
        assert profile_only.status_code == 200, profile_only.text
        assert profile_only.json()["scope"] == "legal:client-profile"

        # The grant is per-request, not per-client: holding both on the
        # allowlist must not silently widen a single-scope token.
        for issued, granted, withheld in (
            (draft_only, "legal:draft", "legal:client-profile"),
            (profile_only, "legal:client-profile", "legal:draft"),
        ):
            claims = jwt_manager.verify_token(
                issued.json()["access_token"],
                token_type="access",
                audience="karafiel-api",
            )
            assert claims is not None
            scopes = claims["scope"].split()
            assert granted in scopes
            assert withheld not in scopes

    async def test_nauta_client_defaults_to_both_legal_scopes(self, service_token_client):
        """Omitting scope grants the client's full allowlist — both legal scopes."""
        response = await _request_token(
            service_token_client,
            client_id=NAUTA_CLIENT_ID,
            client_secret=NAUTA_SECRET,
            scope="",
        )
        assert response.status_code == 200, response.text
        assert sorted(response.json()["scope"].split()) == [
            "legal:client-profile",
            "legal:draft",
        ]

    def test_seed_list_pins_the_nauta_legal_drafts_contract(self):
        from scripts.seed_service_clients import SERVICE_CLIENTS

        entry = next(c for c in SERVICE_CLIENTS if c["name"] == "nauta-legal-drafts")
        assert entry["audience"] == "karafiel-api"
        assert entry["allowed_scopes"] == ["legal:draft", "legal:client-profile"]
        assert entry["grant_types"] == ["client_credentials"]
        assert entry["is_confidential"] is True
        assert entry["redirect_uris"] == []

    async def test_routecraft_client_defaults_to_full_allowlist(self, service_token_client):
        """Omitting scope grants the client's (single-scope) allowlist."""
        response = await _request_token(
            service_token_client,
            client_id=ROUTECRAFT_CLIENT_ID,
            client_secret=ROUTECRAFT_SECRET,
            scope="",
        )
        assert response.status_code == 200, response.text

        body = response.json()
        assert body["scope"] == "billing:events"
        claims = jwt_manager.verify_token(
            body["access_token"], token_type="access", audience="dhanam-api"
        )
        assert claims is not None
        assert claims["sub"] == f"service-account:{ROUTECRAFT_CLIENT_ID}"
        assert claims["scope"] == "billing:events"
        assert claims["aud"] == "dhanam-api"


class TestServiceTokenRejection:
    """Fail-closed behavior: bad secrets, foreign scopes, wrong grants."""

    async def test_wrong_secret_is_rejected(self, service_token_client):
        response = await _request_token(
            service_token_client, client_secret="jns_wrong_secret_placeholder"
        )
        assert response.status_code == 401
        assert "invalid_client" in _error_message(response)

    async def test_scope_outside_allowlist_is_rejected(self, service_token_client):
        """zavlo-cfdi-emitter must not be able to mint billing:events tokens."""
        response = await _request_token(service_token_client, scope="billing:events")
        assert response.status_code == 400
        detail = _error_message(response)
        assert "invalid_scope" in detail
        assert "billing:events" in detail

    async def test_legal_client_profile_scope_is_not_globally_grantable(self, service_token_client):
        """Registering legal:client-profile in discovery must not make it
        mintable by any client — only nauta-legal-drafts has it allowlisted."""
        response = await _request_token(service_token_client, scope="legal:client-profile")
        assert response.status_code == 400
        detail = _error_message(response)
        assert "invalid_scope" in detail
        assert "legal:client-profile" in detail

    async def test_partially_escalated_scope_is_rejected(self, service_token_client):
        """One allowed + one foreign scope must still fail closed."""
        response = await _request_token(service_token_client, scope="cfdi:issue cfdi:cancel")
        assert response.status_code == 400
        assert "invalid_scope" in _error_message(response)

    async def test_client_without_client_credentials_grant_is_rejected(self, service_token_client):
        response = await _request_token(
            service_token_client,
            client_id=INTERACTIVE_CLIENT_ID,
            client_secret=INTERACTIVE_SECRET,
            scope="openid",
        )
        assert response.status_code == 400
        assert "unauthorized_client" in _error_message(response)


class TestServiceTokenExpiry:
    """Service tokens are short-lived and expire honestly."""

    async def test_token_exp_matches_advertised_expires_in(self, service_token_client):
        response = await _request_token(service_token_client)
        assert response.status_code == 200, response.text
        body = response.json()

        claims = jwt_manager.get_unverified_claims(body["access_token"])
        assert claims["exp"] - claims["iat"] == body["expires_in"] == SERVICE_TOKEN_TTL_SECONDS

    async def test_expired_service_token_fails_verification_and_introspection(
        self, service_token_client
    ):
        now = datetime.now(timezone.utc)
        expired_token = jwt_manager.encode_token(
            {
                "sub": f"service-account:{ZAVLO_CLIENT_ID}",
                "client_id": ZAVLO_CLIENT_ID,
                "scope": "cfdi:issue",
                "token_use": "client_credentials",
                "type": "access",
                "iss": jwt_manager.issuer,
                "aud": "karafiel-api",
                "iat": int((now - timedelta(hours=2)).timestamp()),
                "exp": int((now - timedelta(hours=1)).timestamp()),
            }
        )

        # Offline (JWKS-style) verification rejects it.
        assert (
            jwt_manager.verify_token(expired_token, token_type="access", audience="karafiel-api")
            is None
        )

        # RFC 7662 introspection reports it inactive.
        response = await service_token_client.post(
            INTROSPECT_URL,
            data={
                "token": expired_token,
                "client_id": ZAVLO_CLIENT_ID,
                "client_secret": ZAVLO_SECRET,
            },
        )
        assert response.status_code == 200
        assert response.json() == {"active": False}

    async def test_live_service_token_is_active_via_introspection(self, service_token_client):
        issued = await _request_token(service_token_client)
        assert issued.status_code == 200, issued.text
        access_token = issued.json()["access_token"]

        response = await service_token_client.post(
            INTROSPECT_URL,
            data={
                "token": access_token,
                "client_id": ZAVLO_CLIENT_ID,
                "client_secret": ZAVLO_SECRET,
            },
        )
        assert response.status_code == 200
        body = response.json()
        assert body["active"] is True
        assert body["sub"] == f"service-account:{ZAVLO_CLIENT_ID}"
        assert body["client_id"] == ZAVLO_CLIENT_ID
        assert body["scope"] == "cfdi:issue"
