"""The two writers of `users.spanish_formality`, over HTTP against SQLite.

* `PATCH /api/v1/users/me` — the person's own answer.
* `POST /api/v1/internal/users/spanish-formality` — a product relaying the
  answer the person gave inside it.

Before these existed nothing could write the column, so it was NULL for
everyone and tier 2 of the email register precedence ("the reader") never
fired. These tests pin: strict values, NULL refused (it means "never asked"),
idempotency, the audit row (who / which product / old -> new) committed with the
value, the internal-key gate, membership scoping, and that the stored answer is
what `resolve_formality_for_request` then picks over a product's own voice.

All people, addresses and products here are synthetic.
"""

from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from fastapi import Depends
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.config import settings
from app.core.redis import get_redis
from app.database import get_db
from app.dependencies import get_current_user
from app.main import app
from app.models import AuditLog, Base, Organization, OrganizationMember, User, UserStatus
from app.routers.v1.oauth_clients import INTERNAL_API_KEY_PRINCIPAL
from app.services.email_i18n import resolve_formality_for_request

INTERNAL_KEY = "test-internal-api-key-formality"
AUTH = {"X-Internal-API-Key": INTERNAL_KEY}
ME_URL = "/api/v1/users/me"
RELAY_URL = "/api/v1/internal/users/spanish-formality"


@pytest_asyncio.fixture
async def env():
    """SQLite-backed app client, a session factory, and a signed-in person.

    `get_current_user` is overridden with a resolver that loads the person
    through the SAME request-scoped session the route commits on, so a write
    the handler makes is a real write.
    """
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    person_id = uuid.uuid4()
    async with session_factory() as session:
        session.add(
            User(
                id=person_id,
                email="persona@example.com",
                status=UserStatus.ACTIVE,
                user_metadata={},
            )
        )
        await session.commit()

    async def override_get_db():
        async with session_factory() as session:
            yield session

    async def override_current_user(db: AsyncSession = Depends(get_db)) -> User:
        result = await db.execute(select(User).where(User.id == person_id))
        return result.scalar_one()

    from unittest.mock import AsyncMock

    redis = AsyncMock()
    redis.ping.return_value = True

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_redis] = lambda: redis
    app.dependency_overrides[get_current_user] = override_current_user
    settings.INTERNAL_API_KEY = INTERNAL_KEY

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client, session_factory, person_id

    app.dependency_overrides.clear()
    settings.INTERNAL_API_KEY = None
    await engine.dispose()


async def _row(session_factory, user_id) -> User:
    async with session_factory() as session:
        result = await session.execute(select(User).where(User.id == user_id))
        return result.scalar_one()


async def _audit_rows(session_factory, user_id) -> list[AuditLog]:
    async with session_factory() as session:
        result = await session.execute(
            select(AuditLog)
            .where(AuditLog.resource_id == user_id)
            .order_by(AuditLog.created_at, AuditLog.id)
        )
        return [
            row
            for row in result.scalars().all()
            if (row.details or {}).get("field") == "spanish_formality"
        ]


async def _add_user(session_factory, email: str, *, status=UserStatus.ACTIVE) -> uuid.UUID:
    user_id = uuid.uuid4()
    async with session_factory() as session:
        session.add(User(id=user_id, email=email, status=status, user_metadata={}))
        await session.commit()
    return user_id


async def _add_membership(session_factory, user_id: uuid.UUID) -> uuid.UUID:
    org_id = uuid.uuid4()
    slug = f"org-{org_id.hex[:8]}"
    async with session_factory() as session:
        session.add(Organization(id=org_id, name=slug, slug=slug))
        session.add(
            OrganizationMember(
                organization_id=org_id, user_id=user_id, role="member", status="active"
            )
        )
        await session.commit()
    return org_id


# =========================================================================
# Self-service: PATCH /users/me
# =========================================================================


@pytest.mark.asyncio
async def test_self_write_stores_the_answer_and_reports_it(env):
    client, session_factory, person_id = env

    response = await client.patch(ME_URL, json={"spanish_formality": "tu"})

    assert response.status_code == 200, response.text
    assert response.json()["spanish_formality"] == "tu"
    assert (await _row(session_factory, person_id)).spanish_formality == "tu"

    me = await client.get(ME_URL)
    assert me.status_code == 200
    assert me.json()["spanish_formality"] == "tu"


@pytest.mark.asyncio
async def test_unanswered_person_reads_as_null(env):
    client, _, _ = env
    me = await client.get(ME_URL)
    assert me.status_code == 200
    assert me.json()["spanish_formality"] is None


@pytest.mark.asyncio
async def test_self_write_is_audited_with_old_and_new(env):
    client, session_factory, person_id = env

    await client.patch(ME_URL, json={"spanish_formality": "tu"}, headers={"user-agent": "ua/1"})
    await client.patch(ME_URL, json={"spanish_formality": "usted"})

    rows = await _audit_rows(session_factory, person_id)
    assert len(rows) == 2
    first, second = rows
    assert first.action == "user.update"
    assert first.resource_type == "user"
    # The actor is the person themself.
    assert first.user_id == person_id
    assert first.user_agent == "ua/1"
    assert first.details["old"] is None
    assert first.details["new"] == "tu"
    assert first.details["source"] == "self"
    assert first.details["actor_type"] == "user"
    assert first.details["via"] == "users.me.patch"
    assert "source_app" not in first.details
    assert (second.details["old"], second.details["new"]) == ("tu", "usted")


@pytest.mark.asyncio
async def test_self_write_of_the_stored_value_is_a_no_op(env):
    client, session_factory, person_id = env

    await client.patch(ME_URL, json={"spanish_formality": "usted"})
    again = await client.patch(ME_URL, json={"spanish_formality": "usted"})

    assert again.status_code == 200
    assert len(await _audit_rows(session_factory, person_id)) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("value", ["tú", "TU", "Usted", "vosotros", "", "formal", 1, True])
async def test_self_write_refuses_anything_but_tu_or_usted(env, value):
    client, session_factory, person_id = env

    response = await client.patch(ME_URL, json={"spanish_formality": value})

    assert response.status_code == 422
    assert (await _row(session_factory, person_id)).spanish_formality is None
    assert await _audit_rows(session_factory, person_id) == []


@pytest.mark.asyncio
async def test_self_write_refuses_null_and_keeps_the_answer(env):
    """NULL means "never asked"; an answer, once given, cannot be cleared."""
    client, session_factory, person_id = env
    await client.patch(ME_URL, json={"spanish_formality": "tu"})

    response = await client.patch(ME_URL, json={"spanish_formality": None})

    assert response.status_code == 422
    assert "cannot be cleared" in response.text
    assert (await _row(session_factory, person_id)).spanish_formality == "tu"
    assert len(await _audit_rows(session_factory, person_id)) == 1


@pytest.mark.asyncio
async def test_profile_patch_without_the_field_leaves_it_alone(env):
    client, session_factory, person_id = env
    await client.patch(ME_URL, json={"spanish_formality": "tu"})

    response = await client.patch(ME_URL, json={"first_name": "Persona"})

    assert response.status_code == 200
    assert response.json()["spanish_formality"] == "tu"
    row = await _row(session_factory, person_id)
    assert row.first_name == "Persona"
    assert row.spanish_formality == "tu"
    assert len(await _audit_rows(session_factory, person_id)) == 1


@pytest.mark.asyncio
async def test_stored_answer_now_outranks_the_product_voice(env):
    """The point of the whole change: tier 2 of the email precedence fires.

    Before, the row was NULL and a `usted` product's mail addressed a person
    who wanted `tú` as `usted`. Now the stored answer wins over the product's
    voice (tier 3); only an explicit per-request register (tier 1) beats it.
    """
    client, session_factory, person_id = env

    before = await _row(session_factory, person_id)
    assert resolve_formality_for_request(user=before, client_default="usted") == "usted"

    await client.patch(ME_URL, json={"spanish_formality": "tu"})

    after = await _row(session_factory, person_id)
    assert resolve_formality_for_request(user=after, client_default="usted") == "tu"
    assert resolve_formality_for_request(user=after) == "tu"
    assert resolve_formality_for_request(explicit="usted", user=after) == "usted"


# =========================================================================
# Service relay: POST /internal/users/spanish-formality
# =========================================================================


def _relay(user_id=None, **overrides) -> dict:
    payload: dict = {"spanish_formality": "tu", "source_app": "nauta"}
    if user_id is not None:
        payload["user_id"] = str(user_id)
    payload.update(overrides)
    return payload


@pytest.mark.asyncio
async def test_relay_without_the_internal_key_header_is_refused(env):
    client, session_factory, person_id = env
    response = await client.post(RELAY_URL, json=_relay(person_id))
    assert response.status_code == 422
    assert (await _row(session_factory, person_id)).spanish_formality is None


@pytest.mark.asyncio
async def test_relay_with_a_wrong_internal_key_is_401(env):
    client, session_factory, person_id = env
    response = await client.post(
        RELAY_URL, json=_relay(person_id), headers={"X-Internal-API-Key": "wrong-key"}
    )
    assert response.status_code == 401
    assert (await _row(session_factory, person_id)).spanish_formality is None
    assert await _audit_rows(session_factory, person_id) == []


@pytest.mark.asyncio
async def test_relay_with_the_internal_key_unset_is_503(env):
    client, session_factory, person_id = env
    settings.INTERNAL_API_KEY = None
    try:
        response = await client.post(RELAY_URL, json=_relay(person_id), headers=AUTH)
        assert response.status_code == 503
    finally:
        settings.INTERNAL_API_KEY = INTERNAL_KEY
    assert (await _row(session_factory, person_id)).spanish_formality is None


@pytest.mark.asyncio
async def test_relay_by_user_id_stores_and_audits_the_product(env):
    client, session_factory, person_id = env

    response = await client.post(RELAY_URL, json=_relay(person_id), headers=AUTH)

    assert response.status_code == 200, response.text
    assert response.json() == {
        "id": str(person_id),
        "spanish_formality": "tu",
        "previous_spanish_formality": None,
        "changed": True,
    }
    assert (await _row(session_factory, person_id)).spanish_formality == "tu"

    (row,) = await _audit_rows(session_factory, person_id)
    assert row.action == "user.update"
    # A service did it, not a person: no human id is put on the row.
    assert row.user_id is None
    assert row.created_at is not None
    assert row.details["actor"] == INTERNAL_API_KEY_PRINCIPAL
    assert row.details["actor_type"] == "service"
    assert row.details["source"] == "product"
    assert row.details["source_app"] == "nauta"
    assert row.details["via"] == "internal.users.spanish_formality"
    assert (row.details["old"], row.details["new"]) == (None, "tu")


@pytest.mark.asyncio
async def test_relay_is_idempotent(env):
    client, session_factory, person_id = env

    await client.post(RELAY_URL, json=_relay(person_id), headers=AUTH)
    again = await client.post(RELAY_URL, json=_relay(person_id), headers=AUTH)

    assert again.status_code == 200
    assert again.json()["changed"] is False
    assert again.json()["previous_spanish_formality"] == "tu"
    assert len(await _audit_rows(session_factory, person_id)) == 1


@pytest.mark.asyncio
async def test_relay_of_a_new_answer_records_old_to_new(env):
    client, session_factory, person_id = env
    await client.patch(ME_URL, json={"spanish_formality": "tu"})

    response = await client.post(
        RELAY_URL,
        json=_relay(person_id, spanish_formality="usted", source_app="phynd-crm"),
        headers=AUTH,
    )

    assert response.status_code == 200
    assert response.json()["previous_spanish_formality"] == "tu"
    assert response.json()["changed"] is True
    rows = await _audit_rows(session_factory, person_id)
    assert [(r.details["source"], r.details["old"], r.details["new"]) for r in rows] == [
        ("self", None, "tu"),
        ("product", "tu", "usted"),
    ]
    assert rows[1].details["source_app"] == "phynd-crm"


@pytest.mark.asyncio
async def test_relay_refuses_null(env):
    client, session_factory, person_id = env
    await client.post(RELAY_URL, json=_relay(person_id), headers=AUTH)

    response = await client.post(
        RELAY_URL, json=_relay(person_id, spanish_formality=None), headers=AUTH
    )

    assert response.status_code == 422
    assert (await _row(session_factory, person_id)).spanish_formality == "tu"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "overrides",
    [
        {"spanish_formality": "tú"},
        {"spanish_formality": "vosotros"},
        {"spanish_formality": "USTED"},
        {"source_app": "Nauta App"},
        {"source_app": ""},
    ],
)
async def test_relay_validates_strictly(env, overrides):
    client, session_factory, person_id = env
    response = await client.post(RELAY_URL, json=_relay(person_id, **overrides), headers=AUTH)
    assert response.status_code == 422
    assert (await _row(session_factory, person_id)).spanish_formality is None


@pytest.mark.asyncio
async def test_relay_requires_the_answer_and_the_product(env):
    client, _, person_id = env
    for missing in ("spanish_formality", "source_app"):
        payload = _relay(person_id)
        payload.pop(missing)
        response = await client.post(RELAY_URL, json=payload, headers=AUTH)
        assert response.status_code == 422, missing


@pytest.mark.asyncio
async def test_relay_needs_exactly_one_address(env):
    client, _, person_id = env

    neither = await client.post(RELAY_URL, json=_relay(), headers=AUTH)
    both = await client.post(
        RELAY_URL,
        json=_relay(person_id, email="persona@example.com", organization_id=str(uuid.uuid4())),
        headers=AUTH,
    )
    email_without_org = await client.post(
        RELAY_URL, json=_relay(email="persona@example.com"), headers=AUTH
    )

    assert neither.status_code == 422
    assert "exactly one of user_id or email" in neither.text
    assert both.status_code == 422
    assert "exactly one of user_id or email" in both.text
    assert email_without_org.status_code == 422
    assert "organization_id is required with email" in email_without_org.text


@pytest.mark.asyncio
async def test_relay_for_an_unknown_user_is_404(env):
    client, _, _ = env
    response = await client.post(RELAY_URL, json=_relay(uuid.uuid4()), headers=AUTH)
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_relay_for_a_deleted_user_is_404(env):
    client, session_factory, _ = env
    gone = await _add_user(session_factory, "gone@example.com", status=UserStatus.DELETED)

    response = await client.post(RELAY_URL, json=_relay(gone), headers=AUTH)

    assert response.status_code == 404
    assert (await _row(session_factory, gone)).spanish_formality is None


@pytest.mark.asyncio
async def test_relay_by_user_id_scoped_to_an_organization_needs_a_membership(env):
    client, session_factory, person_id = env
    member = await _add_user(session_factory, "member@example.com")
    org_id = await _add_membership(session_factory, member)

    outsider = await client.post(
        RELAY_URL, json=_relay(person_id, organization_id=str(org_id)), headers=AUTH
    )
    insider = await client.post(
        RELAY_URL, json=_relay(member, organization_id=str(org_id)), headers=AUTH
    )

    assert outsider.status_code == 404
    assert (await _row(session_factory, person_id)).spanish_formality is None
    assert insider.status_code == 200
    (row,) = await _audit_rows(session_factory, member)
    assert row.details["organization_id"] == str(org_id)


@pytest.mark.asyncio
async def test_relay_by_email_within_an_organization(env):
    client, session_factory, _ = env
    member = await _add_user(session_factory, "member2@example.com")
    org_id = await _add_membership(session_factory, member)

    response = await client.post(
        RELAY_URL,
        json=_relay(email="Member2@Example.com", organization_id=str(org_id)),
        headers=AUTH,
    )

    assert response.status_code == 200, response.text
    assert response.json()["id"] == str(member)
    assert (await _row(session_factory, member)).spanish_formality == "tu"


@pytest.mark.asyncio
async def test_relay_by_email_never_reaches_another_organizations_person(env):
    client, session_factory, person_id = env
    other_member = await _add_user(session_factory, "member3@example.com")
    org_id = await _add_membership(session_factory, other_member)

    # The signed-in person exists, but is not a member of the organization named.
    response = await client.post(
        RELAY_URL,
        json=_relay(email="persona@example.com", organization_id=str(org_id)),
        headers=AUTH,
    )

    assert response.status_code == 404
    assert (await _row(session_factory, person_id)).spanish_formality is None


@pytest.mark.asyncio
async def test_relayed_answer_is_what_the_mailer_and_userinfo_now_read(env):
    client, session_factory, person_id = env
    await client.post(RELAY_URL, json=_relay(person_id), headers=AUTH)

    row = await _row(session_factory, person_id)
    assert resolve_formality_for_request(user=row, client_default="usted") == "tu"
    me = await client.get(ME_URL)
    assert me.json()["spanish_formality"] == "tu"
