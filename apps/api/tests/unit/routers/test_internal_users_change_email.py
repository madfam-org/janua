"""
Unit tests for POST /api/v1/internal/users/change-email.

Addresses are synthetic (example.com). The SQLite fixtures come from
``test_internal_users.py`` through ``conftest.py``.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from structlog.testing import capture_logs

from app.core.redis_circuit_breaker import RedisUnavailableError
from app.models import (
    MagicLink,
    Organization,
    OrganizationMember,
    PasswordReset,
    User,
    UserStatus,
)
from app.models import Session as UserSession
from app.routers.v1.internal_users import CHANGE_EMAIL_REFUSED_EVENT
from app.services.audit_logger import AuditEventType

URL = "/api/v1/internal/users/change-email"
AUTH = {"X-Internal-API-Key": "test-internal-api-key-provisioning"}
AUDIT_LOG = "app.routers.v1.internal_users.AuditLogger.log"
GET_REDIS = "app.services.auth_service.get_redis"

OLD = "integrante@crea.example.com"
NEW = "integrante.nueva@crea.example.com"


@pytest.fixture
def redis():
    """The revocation list: records strict writes, never reaches a real Redis."""
    client = AsyncMock()
    with patch(GET_REDIS, AsyncMock(return_value=client)):
        yield client


async def _org(factory, slug: str) -> uuid.UUID:
    org_id = uuid.uuid4()
    async with factory() as session:
        session.add(Organization(id=org_id, name=slug, slug=slug))
        await session.commit()
    return org_id


async def _person(
    factory,
    email: str,
    org_id: uuid.UUID | None,
    *,
    membership_status: str = "active",
    tenant_id: uuid.UUID | None = None,
    **fields,
) -> uuid.UUID:
    user_id = uuid.uuid4()
    async with factory() as session:
        session.add(
            User(
                id=user_id,
                email=email,
                status=UserStatus.ACTIVE,
                email_verified=True,
                email_verified_at=datetime.utcnow(),
                password_hash="stored-hash",
                mfa_enabled=True,
                mfa_secret="stored-secret",
                user_metadata={},
                tenant_id=tenant_id,
                **fields,
            )
        )
        if org_id is not None:
            session.add(
                OrganizationMember(
                    organization_id=org_id, user_id=user_id, role="member", status=membership_status
                )
            )
        await session.commit()
    return user_id


async def _session_row(factory, user_id: uuid.UUID) -> uuid.UUID:
    row_id = uuid.uuid4()
    async with factory() as session:
        session.add(
            UserSession(
                id=row_id,
                user_id=user_id,
                token=f"t-{row_id}",
                access_token_jti=f"a-{row_id}",
                refresh_token_jti=f"r-{row_id}",
                refresh_token_family=f"f-{row_id}",
                expires_at=datetime.utcnow() + timedelta(days=7),
            )
        )
        await session.commit()
    return row_id


async def _user(factory, user_id: uuid.UUID) -> User:
    async with factory() as session:
        return (await session.execute(select(User).where(User.id == user_id))).scalar_one()


def _body(org_id, current=OLD, new=NEW, **extra) -> dict:
    return {"organization_id": str(org_id), "current_email": current, "new_email": new, **extra}


def _refusals(logs: list[dict]) -> list[str]:
    return [entry["reason"] for entry in logs if entry.get("event") == CHANGE_EMAIL_REFUSED_EVENT]


@pytest.mark.asyncio
async def test_change_keeps_the_user_id_and_unverifies_the_new_address(provisioning_env, redis):
    client, factory = provisioning_env
    org = await _org(factory, "crea")
    user_id = await _person(factory, OLD, org)

    with patch(AUDIT_LOG, AsyncMock(return_value="evt")) as audit:
        response = await client.post(
            URL, json=_body(org, current=OLD.upper(), new=f"  {NEW.title()} "), headers=AUTH
        )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body == {
        "id": str(user_id),
        "email": NEW,
        "email_verified": False,
        "changed": True,
        "sessions_revoked": 0,
    }
    user = await _user(factory, user_id)
    assert user.email == NEW
    assert user.email_verified is False
    assert user.email_verified_at is None
    # Credentials are untouched.
    assert user.password_hash == "stored-hash"
    assert user.mfa_enabled is True
    assert user.mfa_secret == "stored-secret"

    audit.assert_awaited_once()
    kwargs = audit.await_args.kwargs
    assert kwargs["event_type"] == AuditEventType.USER_UPDATE
    assert kwargs["details"]["field"] == "email"
    assert kwargs["details"]["via"] == "internal.users.change_email"
    assert kwargs["tenant_id"] == str(org)
    assert kwargs["resource_id"] == str(user_id)
    details = kwargs["details"]
    assert details["previous_email_masked"] == "in***@crea.example.com"
    assert details["new_email_masked"] == "in***@crea.example.com"
    # Neither address appears in plain anywhere in the entry.
    flat = repr(kwargs)
    assert OLD not in flat and NEW not in flat
    assert details["previous_email_hash"] != details["new_email_hash"]


@pytest.mark.asyncio
async def test_change_revokes_every_open_session_and_its_refresh_family(provisioning_env, redis):
    client, factory = provisioning_env
    org = await _org(factory, "crea")
    user_id = await _person(factory, OLD, org)
    first = await _session_row(factory, user_id)
    second = await _session_row(factory, user_id)
    bystander = await _session_row(factory, await _person(factory, "otra@crea.example.com", org))

    response = await client.post(URL, json=_body(org), headers=AUTH)

    assert response.status_code == 200, response.text
    assert response.json()["sessions_revoked"] == 2
    async with factory() as session:
        rows = {row.id: row for row in (await session.execute(select(UserSession))).scalars().all()}
    for row_id in (first, second):
        assert rows[row_id].revoked is True
        assert rows[row_id].is_active is False
        assert rows[row_id].revoked_reason == "email_changed"
    assert rows[bystander].revoked is not True

    written = {call.args[0] for call in redis.strict_set.await_args_list}
    for row_id in (first, second):
        assert f"blacklist:r-{row_id}" in written
        assert f"blacklist:a-{row_id}" in written
        assert any(key.endswith(f"f-{row_id}") for key in written)


@pytest.mark.asyncio
async def test_change_spends_links_mailed_to_the_old_address(provisioning_env, redis):
    client, factory = provisioning_env
    org = await _org(factory, "crea")
    user_id = await _person(factory, OLD, org)
    later = datetime.utcnow() + timedelta(hours=1)
    async with factory() as session:
        session.add(PasswordReset(user_id=user_id, token="reset-1", expires_at=later, used=False))
        session.add(MagicLink(user_id=user_id, email=OLD, token="magic-1", expires_at=later))
        await session.commit()

    response = await client.post(URL, json=_body(org), headers=AUTH)

    assert response.status_code == 200, response.text
    async with factory() as session:
        reset = (await session.execute(select(PasswordReset))).scalar_one()
        magic = (await session.execute(select(MagicLink))).scalar_one()
    assert reset.used is True
    assert magic.used_at is not None


@pytest.mark.asyncio
async def test_repeat_after_success_is_idempotent(provisioning_env, redis):
    client, factory = provisioning_env
    org = await _org(factory, "crea")
    user_id = await _person(factory, OLD, org)

    with patch(AUDIT_LOG, AsyncMock(return_value="evt")) as audit:
        first = await client.post(URL, json=_body(org, user_id=str(user_id)), headers=AUTH)
        await _session_row(factory, user_id)  # a new sign-in between the two calls
        second = await client.post(URL, json=_body(org, user_id=str(user_id)), headers=AUTH)

    assert first.status_code == 200 and first.json()["changed"] is True
    assert second.status_code == 200, second.text
    assert second.json() == {
        "id": str(user_id),
        "email": NEW,
        "email_verified": False,
        "changed": False,
        "sessions_revoked": 0,
    }
    # The repeat neither audits again nor signs the person out again.
    audit.assert_awaited_once()
    async with factory() as session:
        live = (
            (await session.execute(select(UserSession).where(UserSession.revoked.isnot(True))))
            .scalars()
            .all()
        )
    assert len(live) == 1


@pytest.mark.asyncio
async def test_same_address_is_a_no_op(provisioning_env, redis):
    client, factory = provisioning_env
    org = await _org(factory, "crea")
    user_id = await _person(factory, OLD, org)

    response = await client.post(URL, json=_body(org, new=OLD.upper()), headers=AUTH)

    assert response.status_code == 200
    assert response.json()["changed"] is False
    assert (await _user(factory, user_id)).email_verified is True


@pytest.mark.asyncio
async def test_new_address_held_by_someone_else_is_409(provisioning_env, redis):
    client, factory = provisioning_env
    org = await _org(factory, "crea")
    user_id = await _person(factory, OLD, org)
    await _person(factory, NEW.upper(), None)

    with capture_logs() as logs:
        response = await client.post(URL, json=_body(org), headers=AUTH)

    assert response.status_code == 409
    assert _refusals(logs) == ["email_in_use"]
    assert (await _user(factory, user_id)).email == OLD
    redis.strict_set.assert_not_awaited()


@pytest.mark.asyncio
async def test_new_address_held_in_another_pool_is_409(provisioning_env, redis):
    client, factory = provisioning_env
    org = await _org(factory, "crea")
    other_tenant = await _org(factory, "tenant")
    await _person(factory, OLD, org)
    await _person(factory, NEW, None, tenant_id=other_tenant)

    with capture_logs() as logs:
        response = await client.post(URL, json=_body(org), headers=AUTH)

    assert response.status_code == 409
    assert _refusals(logs) == ["email_in_use_other_pool"]


@pytest.mark.asyncio
async def test_person_of_another_organization_is_404(provisioning_env, redis):
    client, factory = provisioning_env
    org = await _org(factory, "crea")
    other = await _org(factory, "otra")
    user_id = await _person(factory, OLD, other)

    with capture_logs() as logs:
        response = await client.post(URL, json=_body(org), headers=AUTH)

    assert response.status_code == 404
    assert _refusals(logs) == ["not_a_member"]
    assert (await _user(factory, user_id)).email == OLD


@pytest.mark.asyncio
async def test_removed_membership_is_not_a_member(provisioning_env, redis):
    client, factory = provisioning_env
    org = await _org(factory, "crea")
    await _person(factory, OLD, org, membership_status="removed")

    with capture_logs() as logs:
        response = await client.post(URL, json=_body(org), headers=AUTH)

    assert response.status_code == 404
    assert _refusals(logs) == ["not_a_member"]


@pytest.mark.asyncio
async def test_unknown_address_is_404(provisioning_env, redis):
    client, factory = provisioning_env
    org = await _org(factory, "crea")

    with capture_logs() as logs:
        response = await client.post(URL, json=_body(org), headers=AUTH)

    assert response.status_code == 404
    assert _refusals(logs) == ["not_found"]


@pytest.mark.asyncio
async def test_platform_admin_is_refused(provisioning_env, redis):
    client, factory = provisioning_env
    org = await _org(factory, "crea")
    user_id = await _person(factory, OLD, org, is_admin=True)

    with capture_logs() as logs:
        response = await client.post(URL, json=_body(org), headers=AUTH)

    assert response.status_code == 403
    assert _refusals(logs) == ["platform_admin"]
    assert (await _user(factory, user_id)).email == OLD


@pytest.mark.asyncio
async def test_service_account_is_refused(provisioning_env, redis):
    client, factory = provisioning_env
    org = await _org(factory, "crea")
    user_id = await _person(factory, OLD, org, is_service_account=True)

    with capture_logs() as logs:
        response = await client.post(URL, json=_body(org), headers=AUTH)

    assert response.status_code == 403
    assert _refusals(logs) == ["service_account"]
    assert (await _user(factory, user_id)).email == OLD


@pytest.mark.asyncio
async def test_person_active_in_another_organization_is_refused(provisioning_env, redis):
    client, factory = provisioning_env
    org = await _org(factory, "crea")
    other = await _org(factory, "otra")
    user_id = await _person(factory, OLD, org)
    async with factory() as session:
        session.add(
            OrganizationMember(
                organization_id=other, user_id=user_id, role="member", status="active"
            )
        )
        await session.commit()

    with capture_logs() as logs:
        response = await client.post(URL, json=_body(org), headers=AUTH)

    assert response.status_code == 403
    assert _refusals(logs) == ["member_of_other_organization"]


@pytest.mark.asyncio
async def test_user_id_that_does_not_match_is_409(provisioning_env, redis):
    client, factory = provisioning_env
    org = await _org(factory, "crea")
    await _person(factory, OLD, org)

    with capture_logs() as logs:
        response = await client.post(URL, json=_body(org, user_id=str(uuid.uuid4())), headers=AUTH)

    assert response.status_code == 409
    assert _refusals(logs) == ["user_id_mismatch"]


@pytest.mark.asyncio
async def test_redis_down_changes_nothing(provisioning_env, redis):
    client, factory = provisioning_env
    org = await _org(factory, "crea")
    user_id = await _person(factory, OLD, org)
    await _session_row(factory, user_id)
    redis.strict_set.side_effect = RedisUnavailableError("down")

    with capture_logs() as logs:
        response = await client.post(URL, json=_body(org), headers=AUTH)

    assert response.status_code == 503
    assert _refusals(logs) == ["revocation_unavailable"]
    user = await _user(factory, user_id)
    assert user.email == OLD
    assert user.email_verified is True


@pytest.mark.asyncio
@pytest.mark.parametrize("bad", ["not-an-address", "a@", "@example.com"])
async def test_malformed_new_address_is_422(provisioning_env, redis, bad):
    client, factory = provisioning_env
    org = await _org(factory, "crea")
    await _person(factory, OLD, org)

    response = await client.post(URL, json=_body(org, new=bad), headers=AUTH)

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_missing_internal_key_header_is_422(provisioning_client: AsyncClient):
    response = await provisioning_client.post(URL, json=_body(uuid.uuid4()))
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_wrong_internal_key_is_401(provisioning_env, redis):
    client, factory = provisioning_env
    org = await _org(factory, "crea")
    user_id = await _person(factory, OLD, org)

    response = await client.post(URL, json=_body(org), headers={"X-Internal-API-Key": "wrong-key"})

    assert response.status_code == 401
    assert (await _user(factory, user_id)).email == OLD


@pytest.mark.asyncio
async def test_no_email_is_sent(provisioning_env, redis):
    client, factory = provisioning_env
    org = await _org(factory, "crea")
    await _person(factory, OLD, org)

    with (
        patch("app.services.email_service.EmailService._send_email", AsyncMock()) as send,
        patch("app.services.email_service.EmailService._send_via_resend", AsyncMock()) as via,
        patch(
            "app.services.resend_email_service.ResendEmailService.send_email", AsyncMock()
        ) as resend,
    ):
        response = await client.post(URL, json=_body(org), headers=AUTH)

    assert response.status_code == 200
    send.assert_not_awaited()
    via.assert_not_awaited()
    resend.assert_not_awaited()
