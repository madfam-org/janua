"""Authorization of OAuth client registration and reconfiguration.

Real models on an in-memory database, the real app and routers; only the
signed-in person is injected. The rules under test live in
``services/oauth_client_authority.py`` and the reserved values in
``core/reserved_oauth_boundaries.py``:

- binding a client to an organization needs its owner or an ACTIVE
  ``admin``/``owner`` member (or a platform admin);
- reserved names, audiences and scopes, a pinned ``client_id``, and a
  ``client_credentials`` client with no organization need a platform admin;
- an edit is judged on the resulting row, and a client that already holds a
  reserved value is managed by platform admins only;
- the internal ``/register`` path converges only onto rows a platform admin
  registered;
- the payment-mail boundary honours only clients a platform admin registered.

Every refusal is checked to have written nothing.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, Mock

import bcrypt
import pytest
import pytest_asyncio
from cryptography.hazmat.primitives.asymmetric import rsa
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.config import settings
from app.core.database import get_db as core_get_db
from app.core.jwt_manager import jwt_manager
from app.core.redis import get_redis
from app.core.reserved_oauth_boundaries import (
    BRANDING_AUDIENCE,
    BRANDING_SCOPE,
    MAIL_AUDIENCE,
    PAYMENT_MAIL_SCOPE,
)
from app.database import get_db
from app.dependencies import get_current_user
from app.main import app
from app.models import (
    AuditLog,
    Base,
    OAuthClient,
    Organization,
    OrganizationMember,
    PaymentMailDispatch,
    User,
    UserStatus,
)
from app.services import payment_mail_dispatch as mail

pytestmark = pytest.mark.asyncio

CLIENTS_URL = "/api/v1/oauth/clients"
REGISTER_URL = "/api/v1/oauth/clients/register"
TOKEN_URL = "/api/v1/oauth/token"
NOTICE_URL = "/api/v1/email/payment-notices"
INTERNAL_KEY = "test-internal-api-key-registration-authz"


def _user(email: str, *, is_admin: bool = False) -> User:
    return User(
        id=uuid.uuid4(),
        email=email,
        email_verified=True,
        status=UserStatus.ACTIVE,
        is_admin=is_admin,
        is_active=True,
    )


class Env:
    """Handles to the app client, the database and the fixture identities."""

    def __init__(self, http, factory):
        self.http = http
        self.factory = factory
        self.acting = None

    def act_as(self, user: User) -> Env:
        self.acting = user
        return self

    async def count(self, model) -> int:
        async with self.factory() as db:
            return (await db.execute(select(func.count()).select_from(model))).scalar_one()

    async def client_row(self, client_db_id) -> OAuthClient:
        async with self.factory() as db:
            return await db.get(OAuthClient, uuid.UUID(str(client_db_id)))

    async def add(self, *rows) -> None:
        async with self.factory.begin() as db:
            for row in rows:
                db.add(row)


@pytest_asyncio.fixture
async def env():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db():
        async with factory() as session:
            yield session

    redis = AsyncMock()
    redis.ping.return_value = True
    redis.get.return_value = None
    redis.set.return_value = True

    platform_admin = _user("platform-admin@janua.test", is_admin=True)
    org_admin = _user("org-admin@janua.test")
    org_member = _user("org-member@janua.test")
    former_admin = _user("former-admin@janua.test")
    org_owner = _user("org-owner@janua.test")
    outsider = _user("outsider@janua.test")
    own_org = Organization(id=uuid.uuid4(), name="Own Org", slug="own-org", owner_id=org_owner.id)
    other_org = Organization(id=uuid.uuid4(), name="Other Org", slug="other-org")

    async with factory.begin() as db:
        db.add_all([platform_admin, org_admin, org_member, former_admin, org_owner, outsider])
        await db.flush()
        db.add_all([own_org, other_org])
        await db.flush()
        db.add_all(
            [
                OrganizationMember(
                    organization_id=own_org.id, user_id=org_admin.id, role="admin", status="active"
                ),
                OrganizationMember(
                    organization_id=own_org.id,
                    user_id=org_member.id,
                    role="member",
                    status="active",
                ),
                OrganizationMember(
                    organization_id=own_org.id,
                    user_id=former_admin.id,
                    role="admin",
                    status="removed",
                ),
            ]
        )

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[core_get_db] = override_get_db
    app.dependency_overrides[get_redis] = lambda: redis

    previous_key = settings.INTERNAL_API_KEY
    settings.INTERNAL_API_KEY = INTERNAL_KEY

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http:
        handle = Env(http, factory)
        app.dependency_overrides[get_current_user] = lambda: handle.acting
        handle.platform_admin = platform_admin
        handle.org_admin = org_admin
        handle.org_member = org_member
        handle.former_admin = former_admin
        handle.org_owner = org_owner
        handle.outsider = outsider
        handle.own_org = own_org
        handle.other_org = other_org
        yield handle

    settings.INTERNAL_API_KEY = previous_key
    app.dependency_overrides.clear()
    await engine.dispose()


def _interactive(name: str = "tenant-portal", **extra) -> dict:
    return {
        "name": name,
        "redirect_uris": ["https://portal.example.test/auth/callback"],
        "allowed_scopes": ["openid", "profile", "email"],
        "grant_types": ["authorization_code", "refresh_token"],
        "is_confidential": True,
        **extra,
    }


def _machine(name: str = "tenant-worker", **extra) -> dict:
    return {
        "name": name,
        "redirect_uris": [],
        "allowed_scopes": ["hcm:hr"],
        "grant_types": ["client_credentials"],
        "is_confidential": True,
        **extra,
    }


def _payment_mail_shape(name: str = "mail-sender") -> dict:
    return _machine(name, audience=MAIL_AUDIENCE, allowed_scopes=[PAYMENT_MAIL_SCOPE])


def _branding_shape(name: str = "x") -> dict:
    return _machine(name, audience=BRANDING_AUDIENCE, allowed_scopes=[BRANDING_SCOPE])


async def _create(env: Env, payload: dict, organization_id=None):
    params = {"organization_id": str(organization_id)} if organization_id else None
    return await env.http.post(CLIENTS_URL, json=payload, params=params)


async def _assert_nothing_written(env: Env) -> None:
    assert await env.count(OAuthClient) == 0
    assert await env.count(AuditLog) == 0


# ---------------------------------------------------------------------------
# Organization binding
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("who", ["outsider", "org_member", "former_admin"])
async def test_binding_to_an_org_needs_its_admin(env, who):
    env.act_as(getattr(env, who))
    response = await _create(env, _interactive(), env.own_org.id)
    assert response.status_code == 403, response.text
    await _assert_nothing_written(env)


async def test_binding_to_an_org_via_the_body_is_checked_too(env):
    env.act_as(env.outsider)
    response = await _create(env, _interactive(organization_id=str(env.own_org.id)))
    assert response.status_code == 403, response.text
    await _assert_nothing_written(env)


async def test_org_admin_of_another_org_is_refused(env):
    env.act_as(env.org_admin)
    response = await _create(env, _machine(), env.other_org.id)
    assert response.status_code == 403, response.text
    await _assert_nothing_written(env)


async def test_unknown_organization_answers_like_a_foreign_one(env):
    env.act_as(env.org_admin)
    response = await _create(env, _interactive(), uuid.uuid4())
    assert response.status_code == 403, response.text
    await _assert_nothing_written(env)


@pytest.mark.parametrize("payload", [_interactive(), _machine()])
async def test_org_admin_registers_an_ordinary_client(env, payload):
    env.act_as(env.org_admin)
    response = await _create(env, payload, env.own_org.id)
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["organization_id"] == str(env.own_org.id)
    assert body["client_secret"]
    row = await env.client_row(body["id"])
    assert row.created_by == env.org_admin.id


async def test_org_owner_without_membership_row_registers(env):
    env.act_as(env.org_owner)
    response = await _create(env, _machine(), env.own_org.id)
    assert response.status_code == 201, response.text


async def test_unbound_interactive_client_is_unchanged_for_any_account(env):
    env.act_as(env.outsider)
    response = await _create(env, _interactive())
    assert response.status_code == 201, response.text
    assert response.json()["organization_id"] is None


async def test_unbound_client_credentials_needs_platform_admin(env):
    env.act_as(env.org_admin)
    response = await _create(env, _machine())
    assert response.status_code == 403, response.text
    await _assert_nothing_written(env)

    env.act_as(env.platform_admin)
    response = await _create(env, _machine())
    assert response.status_code == 201, response.text


async def test_pinned_client_id_needs_platform_admin(env):
    env.act_as(env.org_admin)
    pinned = _interactive(client_id="jnc_pinned_fixture_id")
    response = await _create(env, pinned, env.own_org.id)
    assert response.status_code == 403, response.text
    await _assert_nothing_written(env)


# ---------------------------------------------------------------------------
# Reserved names, audiences and scopes
# ---------------------------------------------------------------------------

RESERVED_PAYLOADS = {
    "payment-mail boundary": _payment_mail_shape(),
    "branding boundary": _branding_shape(),
    "janua-* audience": _machine(audience="janua-anything"),
    "connections audience": _machine(audience="janua-connections"),
    "sibling service audience": _machine(audience="karafiel-api"),
    "consent subject audience": _interactive(audience="creator-census-api"),
    "audience via client_key": _machine(client_key="janua-email"),
    "payment-mail scope alone": _machine(allowed_scopes=[PAYMENT_MAIL_SCOPE]),
    "branding scope alone": _machine(allowed_scopes=[BRANDING_SCOPE]),
    "delegation scope": _machine(allowed_scopes=["connections:delegate"]),
    "platform admin scope": _machine(allowed_scopes=["admin"]),
    "product admin scope": _machine(allowed_scopes=["hcm:admin"]),
    "sibling service scope": _machine(allowed_scopes=["cfdi:issue"]),
    "silent-auth scope": _interactive(allowed_scopes=["openid", "madfam:silent_auth"]),
    "first-party name": _interactive("madfam-portal"),
    "first-party name, other case": _interactive("Selva-Office-web"),
    "consent purpose client name": _machine("creator-census-reauth"),
}


@pytest.mark.parametrize("payload", RESERVED_PAYLOADS.values(), ids=RESERVED_PAYLOADS.keys())
async def test_reserved_values_need_platform_admin(env, payload):
    env.act_as(env.org_admin)
    response = await _create(env, payload, env.own_org.id)
    assert response.status_code == 403, response.text
    await _assert_nothing_written(env)


@pytest.mark.parametrize(
    "payload",
    [_payment_mail_shape(), _branding_shape(), _interactive("madfam-portal")],
    ids=["payment-mail", "branding", "first-party name"],
)
async def test_platform_admin_registers_reserved_clients(env, payload):
    env.act_as(env.platform_admin)
    response = await _create(env, payload, env.other_org.id)
    assert response.status_code == 201, response.text
    assert response.json()["organization_id"] == str(env.other_org.id)


async def test_refusal_precedes_the_duplicate_lookup(env):
    """A refused request learns nothing, not even another client's id."""
    env.act_as(env.platform_admin)
    existing = await _create(env, _payment_mail_shape("shared-name"), env.other_org.id)
    assert existing.status_code == 201

    env.act_as(env.outsider)
    response = await _create(env, _payment_mail_shape("shared-name"), env.other_org.id)
    assert response.status_code == 403
    assert existing.json()["client_id"] not in response.text


# ---------------------------------------------------------------------------
# Regression: registering a service client for someone else's organization
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "payload",
    [
        {
            "name": "x",
            "redirect_uris": [],
            "allowed_scopes": [BRANDING_SCOPE],
            "grant_types": ["client_credentials"],
            "audience": BRANDING_AUDIENCE,
            "is_confidential": True,
        },
        _payment_mail_shape("x"),
    ],
    ids=["branding", "payment-mail"],
)
async def test_foreign_org_service_client_stops_at_registration(env, payload):
    env.act_as(env.outsider)
    response = await _create(env, payload, env.other_org.id)
    assert response.status_code == 403, response.text
    assert "client_secret" not in response.text
    await _assert_nothing_written(env)

    # With no row there is nothing to mint a service token from.
    token = await env.http.post(
        TOKEN_URL,
        data={"grant_type": "client_credentials", "client_id": "x", "client_secret": "x"},
    )
    assert token.status_code in (400, 401), token.text


# ---------------------------------------------------------------------------
# Updates and secret rotation
# ---------------------------------------------------------------------------


async def _org_admin_client(env: Env, payload=None) -> dict:
    env.act_as(env.org_admin)
    response = await _create(env, payload or _machine(), env.own_org.id)
    assert response.status_code == 201, response.text
    return response.json()


@pytest.mark.parametrize(
    "change",
    [
        {"allowed_scopes": [PAYMENT_MAIL_SCOPE]},
        {"allowed_scopes": ["hcm:hr", "admin"]},
        {"audience": MAIL_AUDIENCE},
        {"audience": "janua-white-label"},
        {"name": "madfam-worker"},
        {"name": "creator-census"},
    ],
)
async def test_update_cannot_introduce_reserved_values(env, change):
    created = await _org_admin_client(env)
    response = await env.http.patch(f"{CLIENTS_URL}/{created['id']}", json=change)
    assert response.status_code == 403, response.text
    row = await env.client_row(created["id"])
    assert row.allowed_scopes == ["hcm:hr"]
    assert row.audience is None
    assert row.name == "tenant-worker"


async def test_update_of_ordinary_fields_is_unchanged(env):
    created = await _org_admin_client(env)
    response = await env.http.patch(
        f"{CLIENTS_URL}/{created['id']}",
        json={"description": "nightly sync", "allowed_scopes": ["hcm:hr", "hcm:employee"]},
    )
    assert response.status_code == 200, response.text
    assert response.json()["allowed_scopes"] == ["hcm:hr", "hcm:employee"]


async def test_former_org_admin_cannot_change_an_org_clients_grant(env):
    """The creator keeps read/edit of harmless fields, not the org's authority."""
    created = await _org_admin_client(env)
    async with env.factory.begin() as db:
        membership = (
            await db.execute(
                select(OrganizationMember).where(
                    OrganizationMember.user_id == env.org_admin.id,
                )
            )
        ).scalar_one()
        membership.status = "removed"

    grant = await env.http.patch(
        f"{CLIENTS_URL}/{created['id']}", json={"allowed_scopes": ["hcm:hr", "hcm:payroll"]}
    )
    assert grant.status_code == 403, grant.text
    assert (await env.client_row(created["id"])).allowed_scopes == ["hcm:hr"]

    harmless = await env.http.patch(f"{CLIENTS_URL}/{created['id']}", json={"description": "d"})
    assert harmless.status_code == 200, harmless.text


async def test_unbound_client_cannot_gain_client_credentials(env):
    env.act_as(env.outsider)
    created = await _create(env, _interactive())
    assert created.status_code == 201
    response = await env.http.patch(
        f"{CLIENTS_URL}/{created.json()['id']}",
        json={"grant_types": ["authorization_code", "client_credentials"]},
    )
    assert response.status_code == 403, response.text
    row = await env.client_row(created.json()["id"])
    assert "client_credentials" not in row.grant_types


async def test_reserved_client_is_managed_by_platform_admins_only(env):
    env.act_as(env.platform_admin)
    created = await _create(env, _payment_mail_shape(), env.own_org.id)
    assert created.status_code == 201
    client_db_id = created.json()["id"]

    # The org admin can see the org's client but not reconfigure or re-key it.
    env.act_as(env.org_admin)
    edit = await env.http.patch(f"{CLIENTS_URL}/{client_db_id}", json={"description": "d"})
    assert edit.status_code == 403, edit.text
    rotate = await env.http.post(f"{CLIENTS_URL}/{client_db_id}/rotate")
    assert rotate.status_code == 403, rotate.text
    assert "client_secret" not in rotate.text

    env.act_as(env.platform_admin)
    rotate = await env.http.post(f"{CLIENTS_URL}/{client_db_id}/rotate")
    assert rotate.status_code == 200, rotate.text


# ---------------------------------------------------------------------------
# Internal /register convergence
# ---------------------------------------------------------------------------


async def test_register_does_not_converge_onto_a_non_admin_row(env):
    env.act_as(env.outsider)
    created = await _create(env, _interactive("upcoming-consumer-edge"))
    assert created.status_code == 201

    response = await env.http.post(
        REGISTER_URL,
        headers={"X-Internal-API-Key": INTERNAL_KEY},
        json=_machine(
            "upcoming-consumer-edge", audience="karafiel-api", allowed_scopes=["cfdi:issue"]
        ),
    )
    assert response.status_code == 409, response.text
    row = await env.client_row(created.json()["id"])
    assert row.audience is None
    assert row.allowed_scopes == ["openid", "profile", "email"]


async def test_register_still_converges_onto_admin_rows(env):
    headers = {"X-Internal-API-Key": INTERNAL_KEY}
    payload = _machine("consumer-edge", audience="karafiel-api", allowed_scopes=["cfdi:issue"])
    first = await env.http.post(REGISTER_URL, headers=headers, json=payload)
    assert first.status_code == 201, first.text
    again = await env.http.post(REGISTER_URL, headers=headers, json=payload)
    assert again.status_code == 200, again.text
    assert again.json()["client_id"] == first.json()["client_id"]


# ---------------------------------------------------------------------------
# The payment-mail boundary refuses rows a platform admin did not register
# ---------------------------------------------------------------------------

MAIL_CLIENT_ID = "jnc_fixture_legacy_mail_client"
MAIL_SECRET = "jns_fixture_placeholder_not_a_secret"


@pytest.fixture
def rs256(monkeypatch):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    monkeypatch.setattr(jwt_manager, "algorithm", "RS256")
    monkeypatch.setattr(jwt_manager, "private_key", key)
    monkeypatch.setattr(jwt_manager, "public_key", key.public_key())


@pytest.fixture
def mail_provider(monkeypatch):
    envelope = AsyncMock(
        return_value=({"subject": "fixture", "to": ["x"]}, "fixture-key", "a" * 64, "b" * 64)
    )
    provider = Mock(return_value={"id": "fixture-provider-id"})
    monkeypatch.setattr(mail, "_envelope", envelope)
    monkeypatch.setattr(mail, "send_on_account", provider)
    return provider


def _legacy_mail_client(created_by: uuid.UUID, org_id: uuid.UUID) -> OAuthClient:
    """A row shaped like the reserved grant, as it could exist from before."""
    return OAuthClient(
        id=uuid.uuid4(),
        organization_id=org_id,
        created_by=created_by,
        client_id=MAIL_CLIENT_ID,
        client_secret_hash=bcrypt.hashpw(MAIL_SECRET.encode(), bcrypt.gensalt(rounds=4)).decode(),
        client_secret_prefix="jns_fixt",
        name="legacy mail client",
        redirect_uris=[],
        audience=MAIL_AUDIENCE,
        allowed_scopes=[PAYMENT_MAIL_SCOPE],
        grant_types=["client_credentials"],
        is_active=True,
        is_confidential=True,
    )


async def _notice_with_minted_token(env: Env):
    token = await env.http.post(
        TOKEN_URL,
        data={
            "grant_type": "client_credentials",
            "client_id": MAIL_CLIENT_ID,
            "client_secret": MAIL_SECRET,
            "scope": PAYMENT_MAIL_SCOPE,
        },
    )
    assert token.status_code == 200, token.text
    notice = {
        "command_id": str(uuid.uuid4()),
        "recipient": "persona02@example.com",
        "year": 2026,
        "month": 9,
        "sessions": 4,
    }
    return await env.http.post(
        NOTICE_URL,
        json=notice,
        headers={"Authorization": f"Bearer {token.json()['access_token']}"},
    )


async def test_mail_boundary_refuses_a_legacy_row_from_a_non_admin(env, rs256, mail_provider):
    await env.add(_legacy_mail_client(env.outsider.id, env.other_org.id))
    response = await _notice_with_minted_token(env)
    assert response.status_code == 403, response.text
    assert "mail_service_grant_unavailable" in response.text
    mail_provider.assert_not_called()
    assert await env.count(PaymentMailDispatch) == 0


async def test_mail_boundary_accepts_the_same_row_from_a_platform_admin(env, rs256, mail_provider):
    await env.add(_legacy_mail_client(env.platform_admin.id, env.other_org.id))
    response = await _notice_with_minted_token(env)
    assert response.status_code == 200, response.text
    assert response.json()["delivery_status"] == "accepted"
    mail_provider.assert_called_once()
