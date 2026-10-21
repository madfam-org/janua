"""
Unit tests for the internal capability-link endpoints
(POST /api/v1/internal/capability-links{,/resolve,/{id}/revoke,/{id}/rotate}).

Mirrors tests/unit/routers/test_internal_users.py's fixture and coverage style:
the same SQLite-backed ASGI client, the same auth matrix (422 missing header /
401 wrong key / 503 unconfigured), and the same insistence on asserting the ROW
rather than only the response body where the row is the actual guarantee.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.config import settings
from app.core.redis import get_redis
from app.database import get_db
from app.main import app
from app.models import Base
from app.models.capability_link import CapabilityLink, hash_token

INTERNAL_KEY = "test-internal-api-key-caplinks"
CREATE_URL = "/api/v1/internal/capability-links"
RESOLVE_URL = "/api/v1/internal/capability-links/resolve"

TENANT_A = str(uuid.uuid4())
TENANT_B = str(uuid.uuid4())

AUTH = {"X-Internal-API-Key": INTERNAL_KEY}

# The one refusal text every failed resolve must produce, verbatim.
GENERIC_REFUSAL = "Invalid or expired capability link"


def _error_message(response) -> str:
    """Pull the human-facing message out of the app's error envelope.

    `app.core.error_handling` wraps every HTTPException as
    ``{"error": {"code", "message", "request_id", "timestamp"}}`` — so the
    detail is NOT at the top level, and two otherwise-identical refusals differ
    in their raw text by `request_id`/`timestamp`. Comparing `response.text`
    across calls therefore can never prove indistinguishability; comparing the
    (code, message) pair is the assertion that actually means it.
    """
    return response.json()["error"]["message"]


def _error_identity(response) -> tuple:
    """The part of a refusal a CLIENT could use to tell two failures apart.

    Deliberately excludes `request_id` and `timestamp`: those vary per request
    by design and carry no information about the token.
    """
    payload = response.json()["error"]
    return (response.status_code, payload["code"], payload["message"])


def _revoke_url(link_id: str) -> str:
    return f"/api/v1/internal/capability-links/{link_id}/revoke"


def _rotate_url(link_id: str) -> str:
    return f"/api/v1/internal/capability-links/{link_id}/rotate"


@pytest_asyncio.fixture
async def caplinks_env():
    """SQLite-backed app client plus a session factory for direct row asserts."""
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

    from unittest.mock import AsyncMock

    redis = AsyncMock()
    redis.ping.return_value = True

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_redis] = lambda: redis

    settings.INTERNAL_API_KEY = INTERNAL_KEY

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client, session_factory

    app.dependency_overrides.clear()
    settings.INTERNAL_API_KEY = None
    await engine.dispose()


@pytest_asyncio.fixture
async def caplinks_client(caplinks_env):
    client, _ = caplinks_env
    return client


def _create_payload(
    tenant_id: str = TENANT_A,
    subject_type: str = "usuario",
    subject_id: str = "usuario-123",
    scopes: list[str] | None = None,
    ttl_seconds: int = 3600,
    use_mode: str = "multi_use",
    metadata: dict | None = None,
) -> dict:
    return {
        "tenant_id": tenant_id,
        "subject_type": subject_type,
        "subject_id": subject_id,
        "scopes": scopes if scopes is not None else ["expediente:read", "expediente:write"],
        "ttl_seconds": ttl_seconds,
        "use_mode": use_mode,
        "metadata": metadata if metadata is not None else {},
    }


async def _get_link(session_factory, link_id: str) -> CapabilityLink:
    async with session_factory() as session:
        result = await session.execute(
            select(CapabilityLink).where(CapabilityLink.id == uuid.UUID(link_id))
        )
        return result.scalar_one()


# ----------------------------------------------------------------- create


@pytest.mark.asyncio
async def test_create_returns_token_once_and_stores_only_its_hash(caplinks_env):
    """The core security property: janua keeps the hash, never the plaintext."""
    client, session_factory = caplinks_env
    response = await client.post(CREATE_URL, json=_create_payload(), headers=AUTH)

    assert response.status_code == 201
    body = response.json()
    token = body["token"]
    assert token

    link = await _get_link(session_factory, body["id"])
    # The stored value is the SHA-256 of the token, and NOT the token itself.
    assert link.token_hash == hash_token(token)
    assert link.token_hash != token
    assert len(link.token_hash) == 64

    # No column anywhere on the row holds the plaintext.
    stored_values = [v for v in vars(link).values() if isinstance(v, str)]
    assert token not in stored_values

    assert str(link.tenant_id) == TENANT_A
    assert link.subject_type == "usuario"
    assert link.subject_id == "usuario-123"
    assert link.scopes == ["expediente:read", "expediente:write"]
    assert link.use_count == 0
    assert link.revoked_at is None
    assert link.replaced_by_id is None
    assert link.created_by == "internal-api-key"


@pytest.mark.asyncio
async def test_create_is_not_idempotent_two_calls_two_distinct_tokens(caplinks_client):
    """Unlike provision: identical arguments mint INDEPENDENT grants."""
    first = await caplinks_client.post(CREATE_URL, json=_create_payload(), headers=AUTH)
    second = await caplinks_client.post(CREATE_URL, json=_create_payload(), headers=AUTH)

    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["id"] != second.json()["id"]
    assert first.json()["token"] != second.json()["token"]


@pytest.mark.asyncio
async def test_create_honours_ttl(caplinks_env):
    client, session_factory = caplinks_env
    response = await client.post(CREATE_URL, json=_create_payload(ttl_seconds=7200), headers=AUTH)
    assert response.status_code == 201

    link = await _get_link(session_factory, response.json()["id"])
    delta = link.expires_at - link.created_at
    # Both stamps come from the same `_utcnow()` call, so this is exact.
    assert delta == timedelta(seconds=7200)


@pytest.mark.asyncio
async def test_create_rejects_empty_scopes(caplinks_client):
    """A link that grants nothing is always a caller bug, never a valid grant."""
    response = await caplinks_client.post(CREATE_URL, json=_create_payload(scopes=[]), headers=AUTH)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_rejects_duplicate_and_blank_scopes(caplinks_client):
    dupes = await caplinks_client.post(
        CREATE_URL, json=_create_payload(scopes=["a", "a"]), headers=AUTH
    )
    assert dupes.status_code == 422

    blank = await caplinks_client.post(
        CREATE_URL, json=_create_payload(scopes=["  "]), headers=AUTH
    )
    assert blank.status_code == 422


@pytest.mark.asyncio
async def test_create_rejects_out_of_range_ttl(caplinks_client):
    too_short = await caplinks_client.post(
        CREATE_URL, json=_create_payload(ttl_seconds=1), headers=AUTH
    )
    assert too_short.status_code == 422

    too_long = await caplinks_client.post(
        CREATE_URL, json=_create_payload(ttl_seconds=91 * 24 * 3600), headers=AUTH
    )
    assert too_long.status_code == 422


@pytest.mark.asyncio
async def test_tenant_id_is_required(caplinks_client):
    """Never defaulted: a missing tenant must fail loudly, not pick a pool."""
    payload = _create_payload()
    del payload["tenant_id"]
    response = await caplinks_client.post(CREATE_URL, json=payload, headers=AUTH)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_subject_and_scopes_are_opaque_to_janua(caplinks_env):
    """Janua stores and echoes them verbatim; it parses nothing."""
    client, session_factory = caplinks_env
    weird_scope = "urn:crea:expediente/anexo-a::write"
    response = await client.post(
        CREATE_URL,
        json=_create_payload(
            subject_type="engagement",
            subject_id="ENG/2026-08/31 #7",
            scopes=[weird_scope],
        ),
        headers=AUTH,
    )
    assert response.status_code == 201
    assert response.json()["scopes"] == [weird_scope]

    link = await _get_link(session_factory, response.json()["id"])
    assert link.subject_id == "ENG/2026-08/31 #7"
    assert link.scopes == [weird_scope]


# ---------------------------------------------------------------- resolve


@pytest.mark.asyncio
async def test_resolve_returns_subject_and_scopes_and_no_token(caplinks_client):
    created = await caplinks_client.post(CREATE_URL, json=_create_payload(), headers=AUTH)
    token = created.json()["token"]

    response = await caplinks_client.post(RESOLVE_URL, json={"token": token}, headers=AUTH)
    assert response.status_code == 200
    body = response.json()
    assert body["subject_type"] == "usuario"
    assert body["subject_id"] == "usuario-123"
    assert body["scopes"] == ["expediente:read", "expediente:write"]
    assert body["tenant_id"] == TENANT_A
    assert body["use_count"] == 1
    # Resolve never hands the secret back.
    assert "token" not in body


@pytest.mark.asyncio
async def test_resolve_unknown_token_is_generic_404(caplinks_client):
    response = await caplinks_client.post(
        RESOLVE_URL, json={"token": "not-a-real-token"}, headers=AUTH
    )
    assert response.status_code == 404
    assert _error_message(response) == GENERIC_REFUSAL


@pytest.mark.asyncio
async def test_all_resolve_failure_modes_are_indistinguishable(caplinks_env):
    """Enumeration resistance: unknown / revoked / expired / spent / wrong-tenant
    must return the SAME status AND the SAME body. If any branch ever grows its
    own message, a caller can tell a real token from a fake one."""
    client, session_factory = caplinks_env

    # 1. unknown
    unknown = await client.post(RESOLVE_URL, json={"token": "totally-made-up"}, headers=AUTH)

    # 2. revoked
    revoked_created = await client.post(CREATE_URL, json=_create_payload(), headers=AUTH)
    revoked_token = revoked_created.json()["token"]
    await client.post(
        _revoke_url(revoked_created.json()["id"]), json={"tenant_id": TENANT_A}, headers=AUTH
    )
    revoked = await client.post(RESOLVE_URL, json={"token": revoked_token}, headers=AUTH)

    # 3. expired — backdate the row rather than sleeping.
    expired_created = await client.post(CREATE_URL, json=_create_payload(), headers=AUTH)
    expired_token = expired_created.json()["token"]
    async with session_factory() as session:
        link = await session.get(CapabilityLink, uuid.UUID(expired_created.json()["id"]))
        link.expires_at = datetime.utcnow() - timedelta(seconds=1)
        await session.commit()
    expired = await client.post(RESOLVE_URL, json={"token": expired_token}, headers=AUTH)

    # 4. single-use already spent
    spent_created = await client.post(
        CREATE_URL, json=_create_payload(use_mode="single_use"), headers=AUTH
    )
    spent_token = spent_created.json()["token"]
    await client.post(RESOLVE_URL, json={"token": spent_token}, headers=AUTH)
    spent = await client.post(RESOLVE_URL, json={"token": spent_token}, headers=AUTH)

    # 5. wrong tenant asserted by the caller
    other_created = await client.post(CREATE_URL, json=_create_payload(), headers=AUTH)
    wrong_tenant = await client.post(
        RESOLVE_URL,
        json={"token": other_created.json()["token"], "tenant_id": TENANT_B},
        headers=AUTH,
    )

    responses = [unknown, revoked, expired, spent, wrong_tenant]
    assert [r.status_code for r in responses] == [404] * 5

    # Every failure is the SAME (status, code, message). request_id/timestamp
    # vary per request by design and tell a client nothing about the token.
    identities = {_error_identity(r) for r in responses}
    assert len(identities) == 1, f"resolve failures are distinguishable: {identities}"
    assert _error_message(unknown) == GENERIC_REFUSAL


@pytest.mark.asyncio
async def test_resolve_with_matching_tenant_succeeds(caplinks_client):
    created = await caplinks_client.post(CREATE_URL, json=_create_payload(), headers=AUTH)
    response = await caplinks_client.post(
        RESOLVE_URL,
        json={"token": created.json()["token"], "tenant_id": TENANT_A},
        headers=AUTH,
    )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_multi_use_link_resolves_repeatedly_and_counts(caplinks_client):
    created = await caplinks_client.post(
        CREATE_URL, json=_create_payload(use_mode="multi_use"), headers=AUTH
    )
    token = created.json()["token"]

    for expected in (1, 2, 3):
        response = await caplinks_client.post(RESOLVE_URL, json={"token": token}, headers=AUTH)
        assert response.status_code == 200
        assert response.json()["use_count"] == expected


@pytest.mark.asyncio
async def test_single_use_link_burns_after_first_resolve(caplinks_client):
    created = await caplinks_client.post(
        CREATE_URL, json=_create_payload(use_mode="single_use"), headers=AUTH
    )
    token = created.json()["token"]

    first = await caplinks_client.post(RESOLVE_URL, json={"token": token}, headers=AUTH)
    assert first.status_code == 200
    assert first.json()["use_count"] == 1

    second = await caplinks_client.post(RESOLVE_URL, json={"token": token}, headers=AUTH)
    assert second.status_code == 404


@pytest.mark.asyncio
async def test_failed_resolve_does_not_burn_a_single_use_link(caplinks_env):
    """A refused resolve must not advance use_count — otherwise a stranger with a
    revoked token could pre-spend a live single-use grant."""
    client, session_factory = caplinks_env
    created = await client.post(
        CREATE_URL, json=_create_payload(use_mode="single_use"), headers=AUTH
    )
    link_id = created.json()["id"]

    # A wrong-tenant resolve is refused...
    refused = await client.post(
        RESOLVE_URL,
        json={"token": created.json()["token"], "tenant_id": TENANT_B},
        headers=AUTH,
    )
    assert refused.status_code == 404

    link = await _get_link(session_factory, link_id)
    assert link.use_count == 0
    assert link.last_used_at is None

    # ...and the grant is still spendable by its rightful holder.
    ok = await client.post(
        RESOLVE_URL, json={"token": created.json()["token"], "tenant_id": TENANT_A}, headers=AUTH
    )
    assert ok.status_code == 200


# ----------------------------------------------------------------- revoke


@pytest.mark.asyncio
async def test_revoke_sets_revoked_at_and_keeps_the_row(caplinks_env):
    client, session_factory = caplinks_env
    created = await client.post(CREATE_URL, json=_create_payload(), headers=AUTH)
    link_id = created.json()["id"]

    response = await client.post(_revoke_url(link_id), json={"tenant_id": TENANT_A}, headers=AUTH)
    assert response.status_code == 200
    assert response.json()["changed"] is True
    assert response.json()["revoked"] is True

    # Row survives — revocation is a retirement, not a deletion.
    link = await _get_link(session_factory, link_id)
    assert link.revoked_at is not None
    assert link.revoked_reason == "revoked"


@pytest.mark.asyncio
async def test_revoke_is_idempotent(caplinks_client):
    created = await caplinks_client.post(CREATE_URL, json=_create_payload(), headers=AUTH)
    link_id = created.json()["id"]

    first = await caplinks_client.post(
        _revoke_url(link_id), json={"tenant_id": TENANT_A}, headers=AUTH
    )
    assert first.json()["changed"] is True

    second = await caplinks_client.post(
        _revoke_url(link_id), json={"tenant_id": TENANT_A}, headers=AUTH
    )
    assert second.status_code == 200
    assert second.json()["changed"] is False
    assert second.json()["revoked"] is True


@pytest.mark.asyncio
async def test_revoke_is_tenant_scoped(caplinks_env):
    """A link in tenant A must not be revocable by tenant B."""
    client, session_factory = caplinks_env
    created = await client.post(CREATE_URL, json=_create_payload(tenant_id=TENANT_A), headers=AUTH)
    link_id = created.json()["id"]

    response = await client.post(_revoke_url(link_id), json={"tenant_id": TENANT_B}, headers=AUTH)
    assert response.status_code == 404

    # And the grant is genuinely untouched, not merely reported as missing.
    link = await _get_link(session_factory, link_id)
    assert link.revoked_at is None


@pytest.mark.asyncio
async def test_revoked_link_no_longer_resolves(caplinks_client):
    created = await caplinks_client.post(CREATE_URL, json=_create_payload(), headers=AUTH)
    token = created.json()["token"]

    await caplinks_client.post(
        _revoke_url(created.json()["id"]), json={"tenant_id": TENANT_A}, headers=AUTH
    )

    response = await caplinks_client.post(RESOLVE_URL, json={"token": token}, headers=AUTH)
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_revoke_unknown_id_is_404(caplinks_client):
    response = await caplinks_client.post(
        _revoke_url(str(uuid.uuid4())), json={"tenant_id": TENANT_A}, headers=AUTH
    )
    assert response.status_code == 404


# ----------------------------------------------------------------- rotate


@pytest.mark.asyncio
async def test_rotate_kills_the_old_token_and_issues_a_new_one(caplinks_env):
    """The central rotation guarantee: old dies, new works, same grant."""
    client, session_factory = caplinks_env
    created = await client.post(CREATE_URL, json=_create_payload(), headers=AUTH)
    old_id = created.json()["id"]
    old_token = created.json()["token"]

    rotated = await client.post(_rotate_url(old_id), json={"tenant_id": TENANT_A}, headers=AUTH)
    assert rotated.status_code == 201
    new_token = rotated.json()["token"]
    new_id = rotated.json()["id"]

    assert new_token != old_token
    assert new_id != old_id

    # OLD token is dead, with the generic refusal like every other failure.
    dead = await client.post(RESOLVE_URL, json={"token": old_token}, headers=AUTH)
    assert dead.status_code == 404
    assert _error_message(dead) == GENERIC_REFUSAL

    # NEW token carries the same subject and scopes.
    alive = await client.post(RESOLVE_URL, json={"token": new_token}, headers=AUTH)
    assert alive.status_code == 200
    assert alive.json()["subject_id"] == "usuario-123"
    assert alive.json()["scopes"] == ["expediente:read", "expediente:write"]

    # The old row survives and points at its replacement (chain of custody).
    old_link = await _get_link(session_factory, old_id)
    assert old_link.revoked_at is not None
    assert old_link.revoked_reason == "rotated"
    assert str(old_link.replaced_by_id) == new_id


@pytest.mark.asyncio
async def test_rotate_resets_the_use_counter(caplinks_env):
    client, session_factory = caplinks_env
    created = await client.post(CREATE_URL, json=_create_payload(), headers=AUTH)
    await client.post(RESOLVE_URL, json={"token": created.json()["token"]}, headers=AUTH)

    rotated = await client.post(
        _rotate_url(created.json()["id"]), json={"tenant_id": TENANT_A}, headers=AUTH
    )
    new_link = await _get_link(session_factory, rotated.json()["id"])
    assert new_link.use_count == 0


@pytest.mark.asyncio
async def test_rotate_inherits_original_full_ttl_when_omitted(caplinks_env):
    """Not the REMAINING time: a rotation must not be dead on arrival."""
    client, session_factory = caplinks_env
    created = await client.post(CREATE_URL, json=_create_payload(ttl_seconds=7200), headers=AUTH)
    link_id = created.json()["id"]

    # Age the link so "remaining" (200s) and "original" (7200s) differ sharply.
    # BOTH stamps derive from ONE `now`, so the stored span is exactly 7200s —
    # two separate utcnow() calls would leave a few microseconds of drift in the
    # fixture itself and the exact assertion below would fail on the test's own
    # imprecision rather than on router behaviour.
    async with session_factory() as session:
        link = await session.get(CapabilityLink, uuid.UUID(link_id))
        now = datetime.utcnow()
        link.created_at = now - timedelta(seconds=7000)
        link.expires_at = now + timedelta(seconds=200)
        await session.commit()

    rotated = await client.post(_rotate_url(link_id), json={"tenant_id": TENANT_A}, headers=AUTH)
    assert rotated.status_code == 201

    new_link = await _get_link(session_factory, rotated.json()["id"])
    inherited = new_link.expires_at - new_link.created_at
    assert inherited == timedelta(seconds=7200)


@pytest.mark.asyncio
async def test_rotate_accepts_an_explicit_ttl(caplinks_env):
    client, session_factory = caplinks_env
    created = await client.post(CREATE_URL, json=_create_payload(), headers=AUTH)
    rotated = await client.post(
        _rotate_url(created.json()["id"]),
        json={"tenant_id": TENANT_A, "ttl_seconds": 600},
        headers=AUTH,
    )
    assert rotated.status_code == 201

    new_link = await _get_link(session_factory, rotated.json()["id"])
    assert new_link.expires_at - new_link.created_at == timedelta(seconds=600)


@pytest.mark.asyncio
async def test_rotate_is_tenant_scoped(caplinks_env):
    client, session_factory = caplinks_env
    created = await client.post(CREATE_URL, json=_create_payload(tenant_id=TENANT_A), headers=AUTH)
    link_id = created.json()["id"]

    response = await client.post(_rotate_url(link_id), json={"tenant_id": TENANT_B}, headers=AUTH)
    assert response.status_code == 404

    # The original token must still be live — a refused rotation changes nothing.
    link = await _get_link(session_factory, link_id)
    assert link.revoked_at is None
    ok = await client.post(RESOLVE_URL, json={"token": created.json()["token"]}, headers=AUTH)
    assert ok.status_code == 200


@pytest.mark.asyncio
async def test_rotate_a_revoked_link_is_409(caplinks_client):
    """Rotation must not resurrect authority an operator already withdrew."""
    created = await caplinks_client.post(CREATE_URL, json=_create_payload(), headers=AUTH)
    link_id = created.json()["id"]
    await caplinks_client.post(_revoke_url(link_id), json={"tenant_id": TENANT_A}, headers=AUTH)

    response = await caplinks_client.post(
        _rotate_url(link_id), json={"tenant_id": TENANT_A}, headers=AUTH
    )
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_rotate_an_expired_link_is_409(caplinks_env):
    client, session_factory = caplinks_env
    created = await client.post(CREATE_URL, json=_create_payload(), headers=AUTH)
    link_id = created.json()["id"]

    async with session_factory() as session:
        link = await session.get(CapabilityLink, uuid.UUID(link_id))
        link.expires_at = datetime.utcnow() - timedelta(seconds=1)
        await session.commit()

    response = await client.post(_rotate_url(link_id), json={"tenant_id": TENANT_A}, headers=AUTH)
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_rotate_unknown_id_is_404(caplinks_client):
    response = await caplinks_client.post(
        _rotate_url(str(uuid.uuid4())), json={"tenant_id": TENANT_A}, headers=AUTH
    )
    assert response.status_code == 404


# ------------------------------------------------------------------- auth


def _auth_matrix_targets() -> list[tuple[str, dict]]:
    """(url, body) pairs covering every endpoint for the auth tests.

    The placeholder id is fixed, not uuid4(): it ends up in the test ids, and
    pytest-xdist requires every worker to collect identical ids.
    """
    placeholder_id = "00000000-0000-4000-8000-00000000c0de"
    return [
        (CREATE_URL, _create_payload()),
        (RESOLVE_URL, {"token": "irrelevant"}),
        (_revoke_url(placeholder_id), {"tenant_id": TENANT_A}),
        (_rotate_url(placeholder_id), {"tenant_id": TENANT_A}),
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize("url,body", _auth_matrix_targets())
async def test_missing_internal_key_header_is_422(caplinks_client, url: str, body: dict):
    response = await caplinks_client.post(url, json=body)
    assert response.status_code == 422


@pytest.mark.asyncio
@pytest.mark.parametrize("url,body", _auth_matrix_targets())
async def test_wrong_internal_key_is_401(caplinks_client, url: str, body: dict):
    response = await caplinks_client.post(
        url, json=body, headers={"X-Internal-API-Key": "wrong-key"}
    )
    assert response.status_code == 401


@pytest.mark.asyncio
@pytest.mark.parametrize("url,body", _auth_matrix_targets())
async def test_unset_internal_key_is_503(caplinks_client, url: str, body: dict):
    settings.INTERNAL_API_KEY = None
    try:
        response = await caplinks_client.post(url, json=body, headers=AUTH)
        assert response.status_code == 503
    finally:
        settings.INTERNAL_API_KEY = INTERNAL_KEY


@pytest.mark.asyncio
async def test_auth_is_checked_before_the_token_is_looked_up(caplinks_client):
    """An unauthenticated caller must not be able to probe token validity."""
    created = await caplinks_client.post(CREATE_URL, json=_create_payload(), headers=AUTH)
    real_token = created.json()["token"]

    # A REAL token with a bad key is 401 — same as a fake one with a bad key.
    real = await caplinks_client.post(
        RESOLVE_URL, json={"token": real_token}, headers={"X-Internal-API-Key": "wrong"}
    )
    fake = await caplinks_client.post(
        RESOLVE_URL, json={"token": "fake"}, headers={"X-Internal-API-Key": "wrong"}
    )
    assert real.status_code == fake.status_code == 401
    # Same (status, code, message) for a real and a fake token, so a caller
    # without the internal key learns nothing about which tokens exist.
    assert _error_identity(real) == _error_identity(fake)
