"""
POST /api/v1/oauth/clients/register keys by CONSUMER EDGE (client name), not
by audience — and writes audit_logs rows for internal-key registrations.

Before this, the registration upsert key was ``client_key || audience`` with
name only as a fallback. Audience is not an identity: it names the API being
*called*, and several consumer edges legitimately call the same API
(``zavlo-cfdi-emitter`` and ``nauta-legal-drafts`` both target ``karafiel-api``;
see scripts/seed_service_clients.py). Registering a second same-audience client
therefore reached into the FIRST client's row — renaming it, rewriting its
scopes and description — and returned 200 with no secret. The original consumer
kept a client_id whose scopes now belonged to somebody else, and the new
consumer never received a credential at all.

ADR-006 (internal-devops decisions/adr-006-entitlement-claim-and-tier-naming.md)
states the intended contract in as many words: "One such client per consumer
edge — Fashion Cabinet (fashion-cabinet-body-render), white-label, and
Selva→Tablaco-quote each get their own, scoped to exactly what they call."

The token path already honoured that contract — see
test_service_token_clients.py, which mints independently for two karafiel-api
clients. Only the registration key disagreed.

Second gap covered here: internal-key registrations wrote NO audit_logs row, so
machine credentials could be minted or reconfigured with no queryable trace.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.config import settings
from app.core.database import get_db as core_get_db
from app.core.jwt_manager import jwt_manager
from app.core.redis import get_redis
from app.database import get_db
from app.main import app
from app.models import AuditLog, Base, OAuthClient, User, UserStatus

INTERNAL_KEY = "test-internal-api-key-consumer-edge"
REGISTER_URL = "/api/v1/oauth/clients/register"
TOKEN_URL = "/api/v1/oauth/token"

SHARED_AUDIENCE = "karafiel-api"


@pytest_asyncio.fixture
async def registry():
    """Register-capable app plus a handle on the same session factory.

    Tests assert on rows the endpoint wrote (oauth_clients, audit_logs), so
    they need the same in-memory database the app is writing to.
    """
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

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[core_get_db] = override_get_db
    app.dependency_overrides[get_redis] = lambda: redis

    settings.INTERNAL_API_KEY = INTERNAL_KEY

    admin = User(
        id=uuid.uuid4(),
        email="admin-consumer-edge@janua.test",
        email_verified=True,
        status=UserStatus.ACTIVE,
        is_admin=True,
        is_active=True,
    )
    async with session_factory() as session:
        session.add(admin)
        await session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client, session_factory

    app.dependency_overrides.clear()
    settings.INTERNAL_API_KEY = None
    await engine.dispose()


def _machine_payload(name: str, *, audience: str = SHARED_AUDIENCE, scopes: list[str]) -> dict:
    """A confidential client_credentials consumer edge, as ADR-006 describes."""
    return {
        "name": name,
        "description": f"{name} consumer edge",
        "redirect_uris": [],
        "audience": audience,
        "allowed_scopes": scopes,
        "grant_types": ["client_credentials"],
        "is_confidential": True,
    }


async def _register(client: AsyncClient, payload: dict):
    return await client.post(
        REGISTER_URL,
        json=payload,
        headers={"X-Internal-API-Key": INTERNAL_KEY},
    )


class TestMultipleClientsPerAudience:
    """A new NAME creates a new client even when the audience is taken."""

    async def test_second_name_same_audience_creates_a_second_client(self, registry):
        api, session_factory = registry

        first = await _register(
            api, _machine_payload("zavlo-cfdi-emitter", scopes=["cfdi:issue"])
        )
        assert first.status_code == 201, first.text
        assert first.json()["client_secret"] is not None

        # NOTE: the seed list's `legal:client-profile` is not usable here — the
        # HTTP schema's scope regex (`^[a-z][a-z0-9_]*:[a-z][a-z0-9_]*$`) rejects
        # the hyphen, so that scope is reachable only via the DB seed path. That
        # pre-existing divergence between the two provisioning paths is out of
        # scope for this change; `legal:draft` exercises the same behaviour.
        second = await _register(
            api, _machine_payload("nauta-legal-drafts", scopes=["legal:draft"])
        )

        # The whole point: a genuine 201 create, not a 200 upsert onto the first.
        assert second.status_code == 201, second.text
        assert second.json()["client_secret"] is not None
        assert second.json()["client_id"] != first.json()["client_id"]

        # Both rows exist, both on the shared audience.
        async with session_factory() as session:
            rows = (
                (
                    await session.execute(
                        select(OAuthClient).where(OAuthClient.audience == SHARED_AUDIENCE)
                    )
                )
                .scalars()
                .all()
            )
        assert sorted(r.name for r in rows) == ["nauta-legal-drafts", "zavlo-cfdi-emitter"]

    async def test_first_client_is_not_hijacked_by_the_second(self, registry):
        """The old semantics renamed the existing row and rewrote its scopes.

        This is the regression that must stay dead: after registering a second
        same-audience edge, the FIRST client keeps its name, its client_id, and
        its own scope allowlist.
        """
        api, session_factory = registry

        first = await _register(
            api, _machine_payload("zavlo-cfdi-emitter", scopes=["cfdi:issue"])
        )
        assert first.status_code == 201, first.text
        first_client_id = first.json()["client_id"]

        await _register(
            api, _machine_payload("nauta-legal-drafts", scopes=["legal:draft"])
        )

        async with session_factory() as session:
            preserved = (
                await session.execute(
                    select(OAuthClient).where(OAuthClient.client_id == first_client_id)
                )
            ).scalar_one()

        assert preserved.name == "zavlo-cfdi-emitter"
        assert preserved.allowed_scopes == ["cfdi:issue"]
        assert preserved.description == "zavlo-cfdi-emitter consumer edge"

    async def test_four_consumer_edges_coexist_on_overlapping_audiences(self, registry):
        """The edges ADR-006 names, plus the hyperobjects-coverage client.

        fashion-cabinet-body-render, white-label licence minting and
        Selva→Tablaco quotes all target yantra4d-api; under the old key only one
        of them could exist.
        """
        api, session_factory = registry

        edges = [
            ("fashion-cabinet-body-render", "yantra4d-api", ["yantra4d:render"]),
            ("yantra4d-white-label-licence", "yantra4d-api", ["yantra4d:license"]),
            ("selva-tablaco-quote", "yantra4d-api", ["yantra4d:quote"]),
            ("ceq-hyperobjects-coverage", "yantra4d-api", ["yantra4d:coverage"]),
        ]

        client_ids = set()
        for name, audience, scopes in edges:
            response = await _register(
                api, _machine_payload(name, audience=audience, scopes=scopes)
            )
            assert response.status_code == 201, f"{name}: {response.text}"
            assert response.json()["client_secret"] is not None, f"{name} got no secret"
            client_ids.add(response.json()["client_id"])

        # Four distinct credentials, not one row rewritten four times.
        assert len(client_ids) == 4

        async with session_factory() as session:
            rows = (
                (
                    await session.execute(
                        select(OAuthClient).where(OAuthClient.audience == "yantra4d-api")
                    )
                )
                .scalars()
                .all()
            )
        assert sorted(r.name for r in rows) == sorted(e[0] for e in edges)
        # Each kept its own least-privilege scope allowlist.
        assert {r.name: r.allowed_scopes for r in rows} == {
            name: scopes for name, _, scopes in edges
        }

    async def test_both_same_audience_clients_mint_tokens_independently(self, registry):
        """Two edges on one audience each mint their own scoped token.

        Registration is only useful if the credentials it hands out work. Both
        secrets are exercised through the real POST /oauth/token
        client_credentials path, and neither token carries the other's scope.
        """
        api, _ = registry

        zavlo = await _register(
            api, _machine_payload("zavlo-cfdi-emitter", scopes=["cfdi:issue"])
        )
        nauta = await _register(
            api, _machine_payload("nauta-legal-drafts", scopes=["legal:draft"])
        )
        assert zavlo.status_code == 201 and nauta.status_code == 201

        for issued, scope in ((zavlo, "cfdi:issue"), (nauta, "legal:draft")):
            body = issued.json()
            token_response = await api.post(
                TOKEN_URL,
                data={
                    "grant_type": "client_credentials",
                    "client_id": body["client_id"],
                    "client_secret": body["client_secret"],
                    "scope": scope,
                },
            )
            assert token_response.status_code == 200, token_response.text
            claims = jwt_manager.verify_token(
                token_response.json()["access_token"],
                token_type="access",
                audience=SHARED_AUDIENCE,
            )
            assert claims is not None
            assert claims["client_id"] == body["client_id"]
            assert claims["sub"] == f"service-account:{body['client_id']}"
            assert claims["scope"] == scope
            assert claims["aud"] == SHARED_AUDIENCE

        # Fail closed across edges: zavlo cannot mint nauta's scope.
        crossed = await api.post(
            TOKEN_URL,
            data={
                "grant_type": "client_credentials",
                "client_id": zavlo.json()["client_id"],
                "client_secret": zavlo.json()["client_secret"],
                "scope": "legal:draft",
            },
        )
        assert crossed.status_code == 400


class TestSameNameStillUpdates:
    """Backward compatibility: a stable name keeps converging on its own row."""

    async def test_same_name_reregistration_updates_without_secret(self, registry):
        api, session_factory = registry

        created = await _register(
            api, _machine_payload("zavlo-cfdi-emitter", scopes=["cfdi:issue"])
        )
        assert created.status_code == 201
        original_client_id = created.json()["client_id"]

        again = await _register(
            api, _machine_payload("zavlo-cfdi-emitter", scopes=["cfdi:issue", "cfdi:cancel"])
        )
        assert again.status_code == 200, again.text
        assert again.json()["client_id"] == original_client_id
        # An upsert never re-issues a credential.
        assert again.json()["client_secret"] is None
        # ...but it does reconcile non-secret fields.
        assert again.json()["allowed_scopes"] == ["cfdi:issue", "cfdi:cancel"]

        async with session_factory() as session:
            count = len(
                
                    (
                        await session.execute(
                            select(OAuthClient).where(
                                OAuthClient.name == "zavlo-cfdi-emitter"
                            )
                        )
                    )
                    .scalars()
                    .all()
                
            )
        assert count == 1

    async def test_same_name_may_move_its_audience(self, registry):
        """A single-client-per-audience caller that repoints its audience still
        updates in place rather than forking a second row."""
        api, session_factory = registry

        first = await _register(
            api, _machine_payload("routecraft-billing-relay", audience="dhanam-api", scopes=["billing:events"])
        )
        assert first.status_code == 201

        moved = await _register(
            api,
            _machine_payload(
                "routecraft-billing-relay", audience="dhanam-api-v2", scopes=["billing:events"]
            ),
        )
        assert moved.status_code == 200, moved.text
        assert moved.json()["client_id"] == first.json()["client_id"]
        assert moved.json()["audience"] == "dhanam-api-v2"

        async with session_factory() as session:
            rows = (
                (
                    await session.execute(
                        select(OAuthClient).where(
                            OAuthClient.name == "routecraft-billing-relay"
                        )
                    )
                )
                .scalars()
                .all()
            )
        assert len(rows) == 1


class TestInternalRegistrationAuditRows:
    """Internal-key registrations are recorded in audit_logs."""

    @staticmethod
    async def _audit_rows(session_factory, action: str) -> list[AuditLog]:
        async with session_factory() as session:
            return list(
                (await session.execute(select(AuditLog).where(AuditLog.action == action)))
                .scalars()
                .all()
            )

    async def test_create_writes_an_audit_row(self, registry):
        api, session_factory = registry

        created = await _register(
            api, _machine_payload("zavlo-cfdi-emitter", scopes=["cfdi:issue"])
        )
        assert created.status_code == 201

        rows = await self._audit_rows(
            session_factory, "oauth_client_registered_internal_created"
        )
        assert len(rows) == 1
        row = rows[0]
        assert row.resource_type == "oauth_client"
        # The internal API key authenticates a machine, not a person: the row is
        # not falsely attributed to the bootstrap admin.
        assert row.user_id is None
        assert row.details["actor"] == "internal-api-key"
        assert row.details["actor_type"] == "service"
        assert row.details["name"] == "zavlo-cfdi-emitter"
        assert row.details["audience"] == SHARED_AUDIENCE
        assert row.details["client_id"] == created.json()["client_id"]

    async def test_update_writes_an_audit_row(self, registry):
        api, session_factory = registry

        await _register(api, _machine_payload("zavlo-cfdi-emitter", scopes=["cfdi:issue"]))
        again = await _register(
            api, _machine_payload("zavlo-cfdi-emitter", scopes=["cfdi:issue"])
        )
        assert again.status_code == 200

        rows = await self._audit_rows(
            session_factory, "oauth_client_registered_internal_updated"
        )
        assert len(rows) == 1
        assert rows[0].details["name"] == "zavlo-cfdi-emitter"
        assert rows[0].user_id is None

    async def test_audit_rows_never_carry_secret_material(self, registry):
        api, session_factory = registry

        created = await _register(
            api, _machine_payload("zavlo-cfdi-emitter", scopes=["cfdi:issue"])
        )
        secret = created.json()["client_secret"]
        assert secret and secret.startswith("jns_")

        async with session_factory() as session:
            rows = list((await session.execute(select(AuditLog))).scalars().all())

        assert rows
        for row in rows:
            serialized = str(row.details)
            assert secret not in serialized
            assert "jns_" not in serialized
            assert "client_secret" not in serialized

    async def test_each_consumer_edge_registration_is_separately_auditable(self, registry):
        """Two edges on one audience produce two distinct create rows.

        Under the old semantics the second registration silently mutated the
        first client and left no record at all.
        """
        api, session_factory = registry

        await _register(api, _machine_payload("zavlo-cfdi-emitter", scopes=["cfdi:issue"]))
        await _register(api, _machine_payload("nauta-legal-drafts", scopes=["legal:draft"]))

        rows = await self._audit_rows(
            session_factory, "oauth_client_registered_internal_created"
        )
        assert sorted(r.details["name"] for r in rows) == [
            "nauta-legal-drafts",
            "zavlo-cfdi-emitter",
        ]
        assert len({r.details["client_id"] for r in rows}) == 2


class TestSeedListStaysConsistentWithTheEndpoint:
    """The operator seed path already keyed by name; the endpoint now agrees."""

    def test_seed_list_holds_two_clients_on_one_audience(self):
        from scripts.seed_service_clients import SERVICE_CLIENTS

        karafiel = [c for c in SERVICE_CLIENTS if c["audience"] == "karafiel-api"]
        # This is the shipped configuration the old registration key could not
        # express: two named edges, one audience.
        assert sorted(c["name"] for c in karafiel) == [
            "nauta-legal-drafts",
            "zavlo-cfdi-emitter",
        ]
        assert len({c["name"] for c in SERVICE_CLIENTS}) == len(SERVICE_CLIENTS)
