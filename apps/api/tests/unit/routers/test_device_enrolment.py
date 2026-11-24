"""Shared devices end to end: register, poll, approve, token, disable, clone flag.

Through the real app (`ASGITransport`), a SQLite database built from the
models, and a fakeredis behind the strict Redis operations. Covers:

- the happy path: a device registers, polls, an organization admin approves,
  the device polls its ``client_id`` and gets a fifteen-minute token of kind
  ``device`` on Pravara's audience with the terminal scope and no email;
- the device's secret is never stored, returned or logged in clear;
- limits and the pending cap refuse before any hash is computed, and refuse
  (503) when the counter store cannot answer;
- a disabled device, a device without its record, a missing boot identifier and
  a scope outside the template are refused at the token endpoint;
- boot identifiers that alternate flag the device and notify its
  administrators once, and the device is NOT disabled;
- the administrators' routes are for people who administer the organization:
  members without the role, non-members, service accounts, machine tokens and
  the device's own token are refused;
- the device's token is refused where Janua requires a person.

Test values only: every secret here is generated per test.
"""

from __future__ import annotations

import logging
import secrets
import uuid
from datetime import datetime, timedelta

import bcrypt
import fakeredis.aioredis
import jwt as pyjwt
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.auth import device_admin
from app.config import settings
from app.core import redis as core_redis
from app.core.database import get_db as core_get_db
from app.core.jwt_manager import jwt_manager
from app.core.redis import get_redis
from app.core.redis_circuit_breaker import ResilientRedisClient
from app.database import get_db
from app.main import app
from app.models import (
    AuditLog,
    Base,
    OAuthClient,
    Organization,
    OrganizationMember,
    User,
    UserStatus,
)
from app.models.device_client import DeviceClient, DeviceEnrolment
from app.routers.v1 import device_enrolment as enrolment_router
from app.routers.v1 import oauth_provider_device_grant, oauth_provider_shared

REGISTER_URL = "/api/v1/device-enrolments"
TOKEN_URL = "/api/v1/oauth/token"
ORG_SLUG = "floor-test"
OTHER_SLUG = "other-floor-test"


def _devices_url(org_id) -> str:
    return f"/api/v1/organizations/{org_id}/devices"


def _secret() -> str:
    return secrets.token_hex(32)


def _boot() -> str:
    return secrets.token_urlsafe(16)


def _person_token(user_id, **extra) -> str:
    token, _, _ = jwt_manager.create_access_token(
        user_id=str(user_id), email=f"{user_id}@janua.test", additional_claims=extra or None
    )
    return token


def _bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


class World:
    """Users, organizations and the HTTP client of one test."""

    def __init__(self, client, session_factory, redis_holder):
        self.client = client
        self.session_factory = session_factory
        self.redis_holder = redis_holder
        self.org_id = uuid.uuid4()
        self.other_org_id = uuid.uuid4()
        self.admin_id = uuid.uuid4()
        self.owner_id = uuid.uuid4()
        self.member_id = uuid.uuid4()
        self.outsider_id = uuid.uuid4()
        self.service_user_id = uuid.uuid4()
        self.other_admin_id = uuid.uuid4()

    async def seed(self):
        async with self.session_factory() as session:
            for user_id, is_service in [
                (self.admin_id, False),
                (self.owner_id, False),
                (self.member_id, False),
                (self.outsider_id, False),
                (self.service_user_id, True),
                (self.other_admin_id, False),
            ]:
                session.add(
                    User(
                        id=user_id,
                        email=f"{user_id}@janua.test",
                        email_verified=True,
                        status=UserStatus.ACTIVE,
                        is_active=True,
                        is_admin=False,
                        is_service_account=is_service,
                    )
                )
            await session.flush()
            session.add(
                Organization(
                    id=self.org_id, name="Floor Test", slug=ORG_SLUG, owner_id=self.owner_id
                )
            )
            session.add(Organization(id=self.other_org_id, name="Other Floor", slug=OTHER_SLUG))
            await session.flush()
            for user_id, org_id, role in [
                (self.admin_id, self.org_id, "admin"),
                (self.member_id, self.org_id, "member"),
                (self.service_user_id, self.org_id, "admin"),
                (self.other_admin_id, self.other_org_id, "admin"),
            ]:
                session.add(
                    OrganizationMember(
                        id=uuid.uuid4(),
                        organization_id=org_id,
                        user_id=user_id,
                        role=role,
                        status="active",
                    )
                )
            await session.commit()

    # -- device side ------------------------------------------------------

    async def register(self, secret=None, **body):
        payload = {
            "organization": ORG_SLUG,
            "label": "Fabrication cell terminal 1",
            "secret": secret or _secret(),
        }
        payload.update(body)
        return await self.client.post(REGISTER_URL, json=payload)

    async def poll(self, enrolment_id):
        return await self.client.get(f"{REGISTER_URL}/{enrolment_id}")

    async def token(self, client_id, secret, boot_id=None, **extra):
        data = {"grant_type": "client_credentials", "client_id": client_id, "client_secret": secret}
        if boot_id is not None:
            data["boot_id"] = boot_id
        data.update(extra)
        return await self.client.post(TOKEN_URL, data=data)

    # -- administrator side -----------------------------------------------

    async def approve(self, user_code, user_id=None, org_id=None):
        return await self.client.post(
            f"{_devices_url(org_id or self.org_id)}/enrolments/approve",
            json={"user_code": user_code},
            headers=_bearer(_person_token(user_id or self.admin_id)),
        )

    async def enrol(self, secret=None, **body):
        """Register and approve; returns (client_id, secret, enrolment_id)."""
        secret = secret or _secret()
        registered = await self.register(secret=secret, **body)
        assert registered.status_code == 201, registered.text
        approved = await self.approve(registered.json()["user_code"])
        assert approved.status_code == 200, approved.text
        return approved.json()["device"]["client_id"], secret, registered.json()["enrolment_id"]

    async def rows(self, model):
        async with self.session_factory() as session:
            return list((await session.execute(select(model))).scalars().all())


@pytest_asyncio.fixture
async def world(monkeypatch):
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

    redis_holder = {
        "client": ResilientRedisClient(fakeredis.aioredis.FakeRedis(decode_responses=True))
    }

    def override_get_redis():
        return redis_holder["client"]

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[core_get_db] = override_get_db
    for dependency in {
        get_redis,
        core_redis.get_redis,
        enrolment_router.get_redis,
        device_admin.get_redis,
        oauth_provider_shared.get_redis,
    }:
        app.dependency_overrides[dependency] = override_get_redis

    monkeypatch.setattr(settings, "DEVICE_ENROLMENT_ORGANIZATIONS", f"{ORG_SLUG},{OTHER_SLUG}")
    monkeypatch.setattr(settings, "BCRYPT_ROUNDS", 4)

    sent = []

    async def fake_send(notice):
        sent.append(notice)

    monkeypatch.setattr(oauth_provider_device_grant, "send_clone_suspicion_notice", fake_send)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        w = World(client, session_factory, redis_holder)
        w.sent_notices = sent
        await w.seed()
        yield w

    app.dependency_overrides.clear()
    await engine.dispose()


# ----------------------------------------------------------------- happy path


async def test_register_poll_approve_and_get_a_device_token(world):
    secret = _secret()
    registered = await world.register(secret=secret)
    assert registered.status_code == 201, registered.text
    body = registered.json()
    assert body["status"] == "pending"
    assert len(body["user_code"]) == 9 and body["user_code"][4] == "-"
    assert body["poll_interval_seconds"] > 0
    assert "secret" not in str(body).lower()

    polled = await world.poll(body["enrolment_id"])
    assert polled.status_code == 200
    assert polled.json()["status"] == "pending" and polled.json()["client_id"] is None
    assert polled.headers["cache-control"] == "no-store"

    approved = await world.approve(body["user_code"].lower().replace("-", " "))
    assert approved.status_code == 200, approved.text
    device = approved.json()["device"]
    assert approved.json()["re_enrolment"] is False
    assert device["status"] == "active"
    assert device["client_id"].startswith("jnd_")
    assert device["approved_by"] == str(world.admin_id)

    polled = await world.poll(body["enrolment_id"])
    assert polled.json() == {
        "enrolment_id": body["enrolment_id"],
        "status": "approved",
        "expires_at": polled.json()["expires_at"],
        "client_id": device["client_id"],
    }

    issued = await world.token(device["client_id"], secret, boot_id=_boot())
    assert issued.status_code == 200, issued.text
    token = issued.json()
    assert token["expires_in"] == 900
    assert token["scope"] == "pravara-mes:terminal"
    assert token["refresh_token"] is None

    claims = jwt_manager.decode_verified(
        token["access_token"], issuer=jwt_manager.issuer, audience="pravara-api"
    )
    assert claims is not None
    assert claims["exp"] - claims["iat"] == 900
    assert claims["client_kind"] == "device"
    assert claims["client_id"] == device["client_id"]
    assert claims["sub"] == f"service-account:{device['client_id']}"
    assert claims["token_use"] == "client_credentials"
    assert claims["actor_type"] == "service_account"
    assert claims["aud"] == "pravara-api"
    assert claims["scope"] == "pravara-mes:terminal"
    assert claims["org_id"] == claims["tenant_id"] == str(world.org_id)
    assert claims["is_admin"] is False
    assert "email" not in claims and "name" not in claims

    devices = await world.rows(DeviceClient)
    assert devices[0].last_token_at is not None
    assert devices[0].clone_suspected_at is None

    actions = sorted(row.action for row in await world.rows(AuditLog))
    assert actions == ["device.enrolment_approved", "device.enrolment_requested"]


async def test_the_client_is_built_from_the_template_only(world):
    client_id, _, _ = await world.enrol(template="nauta-edge-terminal")
    [client] = [c for c in await world.rows(OAuthClient) if c.client_id == client_id]
    assert client.audience == "pravara-api"
    assert client.allowed_scopes == ["pravara-mes:terminal"]
    assert client.grant_types == ["client_credentials"]
    assert client.organization_id == world.org_id
    assert client.is_confidential and client.is_active
    assert client.redirect_uris == []
    assert client.created_by == world.admin_id

    unknown = await world.register(template="something-else")
    assert unknown.status_code == 422


async def test_a_service_client_token_still_lives_an_hour_with_no_device_claim(world):
    secret = "jns_test_placeholder_" + secrets.token_hex(8)
    async with world.session_factory() as session:
        session.add(
            OAuthClient(
                id=uuid.uuid4(),
                organization_id=world.org_id,
                created_by=world.admin_id,
                client_id="jnc_test_service_client",
                client_secret_hash=bcrypt.hashpw(secret.encode(), bcrypt.gensalt(4)).decode(),
                client_secret_prefix="jns_test",
                name="test-service-client",
                redirect_uris=[],
                allowed_scopes=["pravara-mes:read"],
                grant_types=["client_credentials"],
                audience="pravara-api",
                is_active=True,
                is_confidential=True,
            )
        )
        await session.commit()
    issued = await world.token("jnc_test_service_client", secret)
    assert issued.status_code == 200, issued.text
    assert issued.json()["expires_in"] == 3600
    claims = pyjwt.decode(issued.json()["access_token"], options={"verify_signature": False})
    assert "client_kind" not in claims


# ------------------------------------------------------------- the secret


async def test_the_secret_is_never_stored_returned_or_logged_in_clear(world, caplog, capsys):
    caplog.set_level(logging.DEBUG)
    secret = _secret()
    registered = await world.register(secret=secret)
    assert secret not in registered.text

    [pending] = await world.rows(DeviceEnrolment)
    assert pending.secret_hash and secret not in pending.secret_hash
    assert bcrypt.checkpw(secret.encode(), pending.secret_hash.encode())

    approved = await world.approve(registered.json()["user_code"])
    assert secret not in approved.text
    polled = await world.poll(registered.json()["enrolment_id"])
    assert secret not in polled.text

    [enrolment] = await world.rows(DeviceEnrolment)
    assert enrolment.secret_hash is None, "an approved enrolment keeps no hash"
    client_id = approved.json()["device"]["client_id"]
    [client] = [c for c in await world.rows(OAuthClient) if c.client_id == client_id]
    assert bcrypt.checkpw(secret.encode(), client.client_secret_hash.encode())
    assert secret[:8] not in client.client_secret_prefix

    issued = await world.token(client_id, secret, boot_id=_boot())
    assert issued.status_code == 200
    assert secret not in issued.text

    async with world.session_factory() as session:
        for table in ("device_enrolments", "device_clients", "oauth_clients", "audit_logs"):
            for row in (await session.execute(text(f"SELECT * FROM {table}"))).all():
                assert secret not in " ".join(str(value) for value in row), table

    captured = capsys.readouterr()
    assert secret not in caplog.text
    assert secret not in captured.out + captured.err


async def test_a_wrong_secret_gets_no_token(world):
    client_id, _, _ = await world.enrol()
    refused = await world.token(client_id, _secret(), boot_id=_boot())
    assert refused.status_code == 401


@pytest.mark.parametrize(
    "secret", ["00" * 32, "not-a-secret-" * 4, "ab" * 16], ids=["zeros", "text", "16-bytes"]
)
async def test_a_malformed_or_constant_secret_is_refused(world, secret):
    refused = await world.register(secret=secret)
    assert refused.status_code == 422
    assert await world.rows(DeviceEnrolment) == []


# ------------------------------------------------------- limits, configuration


async def test_an_organization_outside_the_configuration_is_unknown(world, monkeypatch):
    monkeypatch.setattr(settings, "DEVICE_ENROLMENT_ORGANIZATIONS", OTHER_SLUG)
    not_configured = await world.register()
    missing = await world.register(organization="no-such-org")
    assert not_configured.status_code == missing.status_code == 404
    assert not_configured.json()["error"]["message"] == missing.json()["error"]["message"]

    monkeypatch.setattr(settings, "DEVICE_ENROLMENT_ORGANIZATIONS", "")
    assert (await world.register()).status_code == 404
    assert await world.rows(DeviceEnrolment) == []


async def test_registrations_are_limited_per_address_before_hashing(world, monkeypatch):
    monkeypatch.setattr(settings, "DEVICE_ENROLMENT_REGISTER_PER_ADDRESS_PER_HOUR", 2)
    hashes = []
    real_hash = enrolment_router._hash_secret
    monkeypatch.setattr(
        enrolment_router, "_hash_secret", lambda s: hashes.append(1) or real_hash(s)
    )
    assert (await world.register()).status_code == 201
    assert (await world.register()).status_code == 201
    limited = await world.register()
    assert limited.status_code == 429
    assert len(hashes) == 2


async def test_registrations_are_limited_per_organization(world, monkeypatch):
    monkeypatch.setattr(settings, "DEVICE_ENROLMENT_REGISTER_PER_ORGANIZATION_PER_HOUR", 1)
    assert (await world.register()).status_code == 201
    assert (await world.register()).status_code == 429
    # Another organization has its own budget.
    assert (await world.register(organization=OTHER_SLUG)).status_code == 201


async def test_the_pending_cap_refuses_before_hashing(world, monkeypatch):
    monkeypatch.setattr(settings, "DEVICE_ENROLMENT_MAX_PENDING", 1)
    hashes = []
    real_hash = enrolment_router._hash_secret
    monkeypatch.setattr(
        enrolment_router, "_hash_secret", lambda s: hashes.append(1) or real_hash(s)
    )
    assert (await world.register()).status_code == 201
    capped = await world.register()
    assert capped.status_code == 429
    assert len(hashes) == 1
    assert len(await world.rows(DeviceEnrolment)) == 1


async def test_registration_refuses_when_the_counter_store_cannot_answer(world):
    world.redis_holder["client"] = ResilientRedisClient(None)
    refused = await world.register()
    assert refused.status_code == 503
    assert refused.headers.get("retry-after")
    assert await world.rows(DeviceEnrolment) == []


async def test_polling_refuses_when_the_counter_store_cannot_answer(world):
    registered = await world.register()
    world.redis_holder["client"] = ResilientRedisClient(None)
    assert (await world.poll(registered.json()["enrolment_id"])).status_code == 503


async def test_polling_an_unknown_enrolment_is_404(world):
    assert (await world.poll(uuid.uuid4())).status_code == 404


async def test_an_expired_code_cannot_be_approved_and_forgets_its_hash(world):
    registered = await world.register()
    async with world.session_factory() as session:
        enrolment = (await session.execute(select(DeviceEnrolment))).scalar_one()
        enrolment.expires_at = datetime.utcnow() - timedelta(seconds=1)
        await session.commit()

    assert (await world.poll(registered.json()["enrolment_id"])).json()["status"] == "expired"
    [enrolment] = await world.rows(DeviceEnrolment)
    assert enrolment.secret_hash is None
    refused = await world.approve(registered.json()["user_code"])
    assert refused.status_code == 404
    assert await world.rows(DeviceClient) == []


async def test_an_expired_code_is_gone_at_approval(world):
    registered = await world.register()
    async with world.session_factory() as session:
        enrolment = (await session.execute(select(DeviceEnrolment))).scalar_one()
        enrolment.expires_at = datetime.utcnow() - timedelta(seconds=1)
        await session.commit()
    refused = await world.approve(registered.json()["user_code"])
    assert refused.status_code == 410
    [enrolment] = await world.rows(DeviceEnrolment)
    assert enrolment.secret_hash is None


async def test_a_code_cannot_be_approved_from_another_organization(world):
    registered = await world.register()
    crossed = await world.approve(
        registered.json()["user_code"], user_id=world.other_admin_id, org_id=world.other_org_id
    )
    assert crossed.status_code == 404
    assert await world.rows(DeviceClient) == []


async def test_a_code_is_approved_once(world):
    registered = await world.register()
    assert (await world.approve(registered.json()["user_code"])).status_code == 200
    assert (await world.approve(registered.json()["user_code"])).status_code == 404
    assert len(await world.rows(DeviceClient)) == 1


# ------------------------------------------------------ the token endpoint


async def test_a_disabled_device_gets_no_token(world):
    client_id, secret, _ = await world.enrol()
    [device] = await world.rows(DeviceClient)
    assert (await world.token(client_id, secret, boot_id=_boot())).status_code == 200

    disabled = await world.client.post(
        f"{_devices_url(world.org_id)}/{device.id}/disable",
        json={"reason": "left the floor"},
        headers=_bearer(_person_token(world.owner_id)),
    )
    assert disabled.status_code == 200, disabled.text
    assert disabled.json()["changed"] is True
    assert disabled.json()["device"]["status"] == "disabled"
    assert disabled.json()["device"]["disabled_by"] == str(world.owner_id)

    refused = await world.token(client_id, secret, boot_id=_boot())
    assert refused.status_code == 401

    again = await world.client.post(
        f"{_devices_url(world.org_id)}/{device.id}/disable",
        headers=_bearer(_person_token(world.admin_id)),
    )
    assert again.status_code == 200 and again.json()["changed"] is False

    [client] = [c for c in await world.rows(OAuthClient) if c.client_id == client_id]
    assert client.is_active is False
    disabled_rows = [r for r in await world.rows(AuditLog) if r.action == "device.disabled"]
    assert len(disabled_rows) == 1 and disabled_rows[0].user_id == world.owner_id


async def test_a_device_whose_record_is_missing_or_disabled_is_refused_even_if_its_client_is_active(
    world,
):
    client_id, secret, _ = await world.enrol()
    async with world.session_factory() as session:
        device = (await session.execute(select(DeviceClient))).scalar_one()
        device.status = "disabled"
        await session.commit()
    assert (await world.token(client_id, secret, boot_id=_boot())).status_code == 401

    async with world.session_factory() as session:
        await session.execute(text("DELETE FROM device_clients"))
        await session.commit()
    assert (await world.token(client_id, secret, boot_id=_boot())).status_code == 401


async def test_a_device_must_send_its_boot_identifier(world):
    client_id, secret, _ = await world.enrol()
    assert (await world.token(client_id, secret)).status_code == 400
    assert (await world.token(client_id, secret, boot_id="short")).status_code == 400


async def test_a_device_gets_nothing_outside_its_template(world):
    client_id, secret, _ = await world.enrol()
    refused = await world.token(client_id, secret, boot_id=_boot(), scope="pravara-mes:read")
    assert refused.status_code == 400
    # Even when someone widens the client row, the template still decides.
    async with world.session_factory() as session:
        client = (
            await session.execute(select(OAuthClient).where(OAuthClient.client_id == client_id))
        ).scalar_one()
        client.allowed_scopes = ["pravara-mes:terminal", "pravara-mes:read"]
        await session.commit()
    widened = await world.token(client_id, secret, boot_id=_boot(), scope="pravara-mes:read")
    assert widened.status_code == 400
    default = await world.token(client_id, secret, boot_id=_boot())
    assert default.status_code == 400  # the default asks for every allowed scope


async def test_a_device_cannot_use_another_grant(world):
    client_id, secret, _ = await world.enrol()
    refused = await world.client.post(
        TOKEN_URL,
        data={
            "grant_type": "refresh_token",
            "client_id": client_id,
            "client_secret": secret,
            "refresh_token": "x",
        },
    )
    assert refused.status_code == 400


# ------------------------------------------------------------ clone signal


async def test_a_restarting_device_is_not_flagged(world):
    client_id, secret, _ = await world.enrol()
    for boot in [_boot(), _boot(), _boot()]:
        for _ in range(2):
            assert (await world.token(client_id, secret, boot_id=boot)).status_code == 200
    [device] = await world.rows(DeviceClient)
    assert device.clone_suspected_at is None and device.boot_alternations == 0
    assert world.sent_notices == []


async def test_alternating_boots_flag_and_notify_once_and_never_disable(world):
    client_id, secret, _ = await world.enrol()
    first, second = _boot(), _boot()
    assert (await world.token(client_id, secret, boot_id=first)).status_code == 200
    assert (await world.token(client_id, secret, boot_id=second)).status_code == 200
    assert world.sent_notices == []

    flagged = await world.token(client_id, secret, boot_id=first)
    assert flagged.status_code == 200, "a flagged device keeps getting tokens"

    [device] = await world.rows(DeviceClient)
    assert device.status == "active"
    assert device.clone_suspected_at is not None
    assert device.boot_alternations == 1
    assert first not in (device.recent_boot_ids or "")

    [notice] = world.sent_notices
    assert notice.recipients == tuple(
        sorted([f"{world.admin_id}@janua.test", f"{world.owner_id}@janua.test"])
    )
    assert client_id in notice.text and "NOT disabled" in notice.text
    assert first not in notice.text and secret not in notice.text

    flags = [r for r in await world.rows(AuditLog) if r.action == "device.clone_suspected"]
    assert len(flags) == 1 and flags[0].user_id is None
    assert flags[0].details["disabled"] is False

    # Further alternation counts, but notifies nobody again.
    assert (await world.token(client_id, secret, boot_id=second)).status_code == 200
    assert (await world.token(client_id, secret, boot_id=first)).status_code == 200
    [device] = await world.rows(DeviceClient)
    assert device.boot_alternations == 3 and device.status == "active"
    assert len(world.sent_notices) == 1

    listed = await world.client.get(
        _devices_url(world.org_id), headers=_bearer(_person_token(world.admin_id))
    )
    [view] = listed.json()["data"]
    assert view["clone_suspected_at"] is not None and view["boot_alternations"] == 3


async def test_re_enrolment_rotates_the_credential_and_clears_the_flag(world):
    client_id, old_secret, _ = await world.enrol()
    a, b = _boot(), _boot()
    for boot in (a, b, a):
        await world.token(client_id, old_secret, boot_id=boot)
    [device] = await world.rows(DeviceClient)
    assert device.clone_suspected_at is not None
    await world.client.post(
        f"{_devices_url(world.org_id)}/{device.id}/disable",
        headers=_bearer(_person_token(world.admin_id)),
    )

    new_secret = _secret()
    registered = await world.register(secret=new_secret, device_client_id=client_id)
    pending = await world.client.get(
        f"{_devices_url(world.org_id)}/enrolments", headers=_bearer(_person_token(world.admin_id))
    )
    [entry] = pending.json()["data"]
    assert entry["replaces_device"]["client_id"] == client_id
    assert entry["label_is_unverified"] is True

    approved = await world.approve(registered.json()["user_code"])
    assert approved.status_code == 200
    assert approved.json()["re_enrolment"] is True
    assert approved.json()["device"]["client_id"] == client_id
    assert approved.json()["device"]["status"] == "active"
    assert approved.json()["device"]["clone_suspected_at"] is None

    assert (await world.token(client_id, old_secret, boot_id=_boot())).status_code == 401
    assert (await world.token(client_id, new_secret, boot_id=_boot())).status_code == 200
    assert len(await world.rows(DeviceClient)) == 1


async def test_re_enrolment_naming_a_device_of_another_organization_is_a_new_device(world):
    registered = await world.register(organization=OTHER_SLUG)
    approved = await world.approve(
        registered.json()["user_code"], user_id=world.other_admin_id, org_id=world.other_org_id
    )
    foreign_client_id = approved.json()["device"]["client_id"]

    again = await world.register(device_client_id=foreign_client_id)
    result = await world.approve(again.json()["user_code"])
    assert result.json()["re_enrolment"] is False
    assert result.json()["device"]["client_id"] != foreign_client_id


# ----------------------------------------------- the administrators' routes


async def test_listing_pending_enrolments_shows_what_the_approver_needs(world):
    await world.client.post(
        REGISTER_URL,
        json={"organization": ORG_SLUG, "label": "Warehouse  terminal\t2", "secret": _secret()},
        headers={"User-Agent": "nauta-edge-test/0.1"},
    )
    listed = await world.client.get(
        f"{_devices_url(world.org_id)}/enrolments", headers=_bearer(_person_token(world.admin_id))
    )
    assert listed.status_code == 200
    [entry] = listed.json()["data"]
    assert entry["label"] == "Warehouse terminal 2"
    assert entry["label_is_unverified"] is True
    assert entry["requested_user_agent"] == "nauta-edge-test/0.1"
    assert entry["requested_from"] == "127.0.0.1"
    assert entry["replaces_device"] is None
    assert "secret" not in str(entry).lower()


@pytest.mark.parametrize(
    "who, expected",
    [("member", 403), ("outsider", 404), ("service_user", 403), ("other_admin", 404)],
)
async def test_only_the_organizations_administrators_may_act(world, who, expected):
    registered = await world.register()
    user_id = getattr(world, f"{who}_id")
    headers = _bearer(_person_token(user_id))
    base = _devices_url(world.org_id)

    assert (await world.client.get(base, headers=headers)).status_code == expected
    assert (await world.client.get(f"{base}/enrolments", headers=headers)).status_code == expected
    approve = await world.approve(registered.json()["user_code"], user_id=user_id)
    assert approve.status_code == expected
    assert await world.rows(DeviceClient) == []


async def test_machine_tokens_are_refused_on_the_administrators_routes(world):
    client_id, secret, _ = await world.enrol()
    [device] = await world.rows(DeviceClient)
    device_token = (await world.token(client_id, secret, boot_id=_boot())).json()["access_token"]
    base = _devices_url(world.org_id)

    # The device's own token: not Janua's audience, so not a Janua session.
    for method, path in [("get", base), ("post", f"{base}/{device.id}/disable")]:
        response = await getattr(world.client, method)(path, headers=_bearer(device_token))
        assert response.status_code == 401

    # Machine markers on Janua's own audience are refused even for an admin's id.
    for marker in [
        {"token_use": "client_credentials"},
        {"actor_type": "service_account"},
        {"client_kind": "device"},
        {"is_service_account": True},
    ]:
        token = _person_token(world.admin_id, **marker)
        assert (await world.client.get(base, headers=_bearer(token))).status_code == 403

    service_sub, _, _ = jwt_manager.create_access_token(
        user_id=f"service-account:{client_id}", email="x@service.test"
    )
    assert (await world.client.get(base, headers=_bearer(service_sub))).status_code == 403

    assert (await world.client.get(base)).status_code == 401
    assert (
        await world.client.get(base, headers={"Authorization": f"Basic {secret}"})
    ).status_code == 401
    [device] = await world.rows(DeviceClient)
    assert device.status == "active"


async def test_the_device_token_is_refused_where_janua_requires_a_person(world):
    client_id, secret, _ = await world.enrol()
    device_token = (await world.token(client_id, secret, boot_id=_boot())).json()["access_token"]
    for path in ["/api/v1/oauth/clients", "/api/v1/auth/me"]:
        response = await world.client.get(path, headers=_bearer(device_token))
        assert response.status_code == 401, path


async def test_disabling_a_device_of_another_organization_is_404(world):
    await world.enrol()
    [device] = await world.rows(DeviceClient)
    crossed = await world.client.post(
        f"{_devices_url(world.other_org_id)}/{device.id}/disable",
        headers=_bearer(_person_token(world.other_admin_id)),
    )
    assert crossed.status_code == 404
    [device] = await world.rows(DeviceClient)
    assert device.status == "active"
