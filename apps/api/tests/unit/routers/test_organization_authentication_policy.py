"""Real SQLite policy/CAS/authority tests; only identity and recent factor proof are stubbed."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from fastapi import FastAPI, HTTPException
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.database import get_db
from app.models import Base, Organization, OrganizationMember, Session, User, UserStatus
from app.models.app_role import OrganizationMemberAppRole
from app.models.organization_authentication_policy import (
    OrganizationAuthenticationPolicy,
    OrganizationAuthenticationPolicyChange,
)
from app.routers.v1.organizations.authentication_policy import get_policy_user, router
from app.services.organization_authentication_policy import (
    PolicyVersionConflict,
    get_authentication_policy,
    organization_requires_mfa,
    update_authentication_policy,
)


@pytest_asyncio.fixture
async def env(monkeypatch):
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", poolclass=StaticPool)
    tables = [
        User.__table__,
        Organization.__table__,
        OrganizationMember.__table__,
        OrganizationMemberAppRole.__table__,
        Session.__table__,
        OrganizationAuthenticationPolicy.__table__,
        OrganizationAuthenticationPolicyChange.__table__,
    ]
    async with engine.begin() as conn:
        await conn.run_sync(lambda bind: Base.metadata.create_all(bind, tables=tables))
    sf = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    user_id, org_id, member_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    async with sf() as db:
        db.add(Organization(id=org_id, name="Example", slug="policy-example", owner_id=user_id))
        db.add(
            User(
                id=user_id,
                email="director@example.invalid",
                status=UserStatus.ACTIVE,
                is_admin=True,
                is_active=True,
                is_service_account=False,
                mfa_enabled=True,
                mfa_secret="synthetic-test-secret",
            )
        )
        db.add(
            OrganizationMember(
                id=member_id, organization_id=org_id, user_id=user_id, role="owner", status="active"
            )
        )
        await db.commit()
    state = {"sf": sf, "user_id": user_id, "org_id": org_id, "member_id": member_id}
    app = FastAPI()
    app.include_router(router, prefix="/api/v1/organizations")
    state["app"] = app

    async def database():
        async with sf() as db:
            yield db

    async def user():
        async with sf() as db:
            row = await db.get(User, state["user_id"])
            if row is None:
                raise HTTPException(401)
            return row

    app.dependency_overrides[get_db] = database
    app.dependency_overrides[get_policy_user] = user
    from app.auth.authentication_assurance import require_recent_authentication

    state["real_recent"] = require_recent_authentication
    recent = AsyncMock()
    monkeypatch.setattr("app.auth.authentication_assurance.require_recent_authentication", recent)
    state["recent"] = recent
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        state["client"] = client
        yield state
    await engine.dispose()


def url(env, org=None):
    return f"/api/v1/organizations/{org or env['org_id']}/authentication-policy"


def body(**overrides):
    return {
        "mfa_mode": "required",
        "expected_version": 0,
        "reason": "Require a verified second factor",
        **overrides,
    }


AUTH = {"Authorization": "Bearer synthetic-test-credential"}


async def grant(env):
    async with env["sf"]() as db:
        db.add(
            OrganizationMemberAppRole(
                organization_member_id=env["member_id"],
                app="crea-map",
                role="security-policy-admin",
                granted_by="test",
                granted_at=datetime.utcnow(),
            )
        )
        await db.commit()


@pytest.mark.asyncio
async def test_missing_policy_is_optional_and_get_never_creates_it(env):
    response = await env["client"].get(url(env), headers=AUTH)
    assert response.status_code == 200
    assert response.json()["mfa_mode"] == "optional"
    assert response.json()["version"] == 0
    async with env["sf"]() as db:
        assert not await organization_requires_mfa(db, env["org_id"])
        assert (
            await db.execute(select(func.count()).select_from(OrganizationAuthenticationPolicy))
        ).scalar_one() == 0


@pytest.mark.asyncio
async def test_org_owner_and_platform_admin_do_not_imply_security_authority(env):
    response = await env["client"].put(url(env), headers=AUTH, json=body())
    assert response.status_code == 403
    env["recent"].assert_not_awaited()


@pytest.mark.asyncio
async def test_explicit_permission_real_update_and_atomic_journal(env):
    await grant(env)
    response = await env["client"].put(url(env), headers=AUTH, json=body())
    assert response.status_code == 200
    assert response.json()["version"] == 1
    assert response.json()["mfa_mode"] == "required"
    env["recent"].assert_awaited_once()
    assert env["recent"].await_args.kwargs == {"max_age_seconds": 300, "require_mfa": True}
    async with env["sf"]() as db:
        assert await organization_requires_mfa(db, env["org_id"])
        changes = (await db.execute(select(OrganizationAuthenticationPolicyChange))).scalars().all()
        assert len(changes) == 1
        assert changes[0].actor_id == env["user_id"]
        assert changes[0].previous_mode == "optional"
        assert changes[0].mfa_mode == "required"


@pytest.mark.asyncio
async def test_stale_update_cannot_overwrite_policy_or_journal(env):
    await grant(env)
    assert (await env["client"].put(url(env), headers=AUTH, json=body())).status_code == 200
    response = await env["client"].put(url(env), headers=AUTH, json=body(mfa_mode="optional"))
    assert response.status_code == 409
    async with env["sf"]() as db:
        policy = await get_authentication_policy(db, env["org_id"])
        assert policy.mfa_mode == "required" and policy.version == 1
        assert (
            await db.execute(
                select(func.count()).select_from(OrganizationAuthenticationPolicyChange)
            )
        ).scalar_one() == 1


@pytest.mark.asyncio
async def test_lowering_requirement_needs_fresh_mfa_and_is_versioned(env):
    await grant(env)
    assert (await env["client"].put(url(env), headers=AUTH, json=body())).status_code == 200
    env["recent"].side_effect = HTTPException(428, "Recent MFA required")
    response = await env["client"].put(
        url(env), headers=AUTH, json=body(mfa_mode="optional", expected_version=1)
    )
    assert response.status_code == 428
    async with env["sf"]() as db:
        assert await organization_requires_mfa(db, env["org_id"])
    env["recent"].side_effect = None
    response = await env["client"].put(
        url(env), headers=AUTH, json=body(mfa_mode="optional", expected_version=1)
    )
    assert response.status_code == 200 and response.json()["version"] == 2


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "service,inactive,revoked", [(True, False, False), (False, True, False), (False, False, True)]
)
async def test_authority_is_read_live_not_from_claims(env, service, inactive, revoked):
    await grant(env)
    async with env["sf"]() as db:
        if service:
            await db.execute(
                update(User).where(User.id == env["user_id"]).values(is_service_account=True)
            )
        if inactive:
            await db.execute(
                update(OrganizationMember)
                .where(OrganizationMember.id == env["member_id"])
                .values(status="inactive")
            )
        if revoked:
            await db.execute(
                update(OrganizationMemberAppRole)
                .where(OrganizationMemberAppRole.organization_member_id == env["member_id"])
                .values(revoked_at=datetime.utcnow())
            )
        await db.commit()
    response = await env["client"].put(url(env), headers=AUTH, json=body())
    assert response.status_code in (403, 404)
    env["recent"].assert_not_awaited()


@pytest.mark.asyncio
async def test_other_organization_refused_without_creating_any_policy(env):
    await grant(env)
    target = uuid.uuid4()
    assert (await env["client"].get(url(env, target), headers=AUTH)).status_code == 404
    assert (await env["client"].put(url(env, target), headers=AUTH, json=body())).status_code == 404


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload",
    [
        body(mfa_mode="sometimes"),
        body(expected_version=True),
        body(expected_version=-1),
        body(reason=" "),
        body(reason="a" * 301),
        body(actor_id=str(uuid.uuid4())),
    ],
)
async def test_typed_update_rejects_unknown_modes_and_identity_injection(env, payload):
    await grant(env)
    assert (await env["client"].put(url(env), headers=AUTH, json=payload)).status_code == 422


@pytest.mark.asyncio
async def test_cookie_or_internal_key_alone_cannot_mutate_policy(env):
    await grant(env)
    response = await env["client"].put(
        url(env), json=body(), headers={"X-Internal-API-Key": "test-operator-key"}
    )
    assert response.status_code == 401
    env["recent"].assert_not_awaited()


@pytest.mark.asyncio
async def test_policy_read_failure_propagates_instead_of_optional():
    db = AsyncMock()
    db.execute.side_effect = RuntimeError("unavailable")
    with pytest.raises(RuntimeError):
        await organization_requires_mfa(db, uuid.uuid4())


@pytest.mark.asyncio
async def test_duplicate_first_save_is_a_conflict(env):
    async with env["sf"]() as db:
        await update_authentication_policy(
            db,
            env["org_id"],
            mfa_mode="required",
            expected_version=0,
            actor_id=env["user_id"],
            reason="Initial policy",
        )
    async with env["sf"]() as db:
        with pytest.raises(PolicyVersionConflict):
            await update_authentication_policy(
                db,
                env["org_id"],
                mfa_mode="optional",
                expected_version=0,
                actor_id=env["user_id"],
                reason="Stale initial save",
            )


@pytest.mark.asyncio
async def test_real_product_audience_token_is_accepted_and_revocation_is_enforced(env, monkeypatch):
    import fakeredis.aioredis

    from app.services import token_revocation
    from app.services.auth_service import AuthService

    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    redis.strict_exists = redis.exists

    async def fake_redis():
        return redis

    monkeypatch.setattr("app.services.auth_service.get_redis", fake_redis)
    env["app"].dependency_overrides.pop(get_policy_user)
    token, jti, _ = AuthService.create_access_token(
        user_id=str(env["user_id"]),
        tenant_id=str(env["org_id"]),
        audience="crea-map",
    )
    response = await env["client"].get(url(env), headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    await token_revocation.revoke_jti(redis, jti, 300, reason="test_revoked")
    response = await env["client"].get(url(env), headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401
    await redis.aclose()


@pytest.mark.asyncio
async def test_real_product_policy_write_needs_live_fresh_factor_evidence(env, monkeypatch):
    import fakeredis.aioredis

    from app.auth.authentication_assurance import assurance_claims
    from app.services.auth_service import AuthService

    await grant(env)
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    redis.strict_exists = redis.exists

    async def fake_redis():
        return redis

    monkeypatch.setattr("app.services.auth_service.get_redis", fake_redis)
    monkeypatch.setattr(
        "app.auth.authentication_assurance.require_recent_authentication", env["real_recent"]
    )
    env["app"].dependency_overrides.pop(get_policy_user)

    async def credential(*, old=False, revoked=False, disabled=False):
        sid = uuid.uuid4()
        when = datetime.utcnow() - timedelta(minutes=10 if old else 1)
        proof = assurance_claims(["pwd", "otp"], when, when, sid)
        token, jti, _ = AuthService.create_access_token(
            user_id=str(env["user_id"]),
            tenant_id=str(env["org_id"]),
            audience="crea-map",
            additional_claims=proof,
        )
        async with env["sf"]() as db:
            db.add(
                Session(
                    id=sid,
                    user_id=env["user_id"],
                    token=token,
                    access_token_jti=jti,
                    expires_at=datetime.utcnow() + timedelta(days=1),
                    revoked=revoked,
                    is_active=True,
                    authentication_methods=["pwd", "otp"],
                    authenticated_at=when,
                    mfa_verified_at=when,
                )
            )
            if disabled:
                await db.execute(
                    update(User).where(User.id == env["user_id"]).values(is_active=False)
                )
            await db.commit()
        return {"Authorization": f"Bearer {token}"}

    response = await env["client"].put(url(env), headers=await credential(old=True), json=body())
    assert response.status_code == 428
    response = await env["client"].put(
        url(env), headers=await credential(revoked=True), json=body()
    )
    assert response.status_code == 401
    response = await env["client"].put(url(env), headers=await credential(), json=body())
    assert response.status_code == 200 and response.json()["mfa_mode"] == "required"
    response = await env["client"].put(
        url(env),
        headers=await credential(disabled=True),
        json=body(mfa_mode="optional", expected_version=1),
    )
    assert response.status_code == 401
    await redis.aclose()


@pytest.mark.asyncio
async def test_enabling_required_mfa_cannot_lock_out_an_unenrolled_director(env):
    await grant(env)
    async with env["sf"]() as db:
        await db.execute(update(User).where(User.id == env["user_id"]).values(mfa_enabled=False))
        await db.commit()
    response = await env["client"].put(url(env), headers=AUTH, json=body())
    assert response.status_code == 428
