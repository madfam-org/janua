"""Native organization invitation proof; only the ordinary owned test database.

HTTP cases use the mounted router and actual JWT verifier, not an actor override.
Only the final mail transport is recorded; no provider or hosted-login claim.
"""

from uuid import uuid4

import pytest
from sqlalchemy import func, select

from app.models import AuditLog, Base, Invitation, Organization, OrganizationMember
from app.models.invitation import InvitationCreate
from app.services.email_service import EmailService
from app.services.invitation_service import InvitationService
from tests.unit.services.test_organization_create_postgres import pg as pg

pytestmark = [pytest.mark.asyncio, pytest.mark.database]


async def prepare(pg):
    factory, engine, actor = pg
    async with engine.begin() as conn:
        await conn.run_sync(lambda c: Base.metadata.create_all(c, tables=[
            Invitation.__table__, AuditLog.__table__,
        ]))
    async with factory() as db:
        org = Organization(name="Synthetic training", slug="training-" + uuid4().hex,
                           owner_id=actor.id)
        db.add(org)
        await db.flush()
        db.add(OrganizationMember(organization_id=org.id, user_id=actor.id,
                                  role="admin", status="active"))
        await db.commit()
    return factory, actor, org


async def test_native_create_persists_intent(pg, monkeypatch):
    factory, actor, org = await prepare(pg)
    attempts = []

    async def transport(self, **message):
        attempts.append(message)
        return True

    monkeypatch.setattr(EmailService, "_send_email", transport)
    async with factory() as db:
        result = await InvitationService(db).create_invitation(
            InvitationCreate(organization_id=str(org.id), email="invitee@example.com",
                             message="Synthetic lesson"), actor, "",
        )
    async with factory() as db:
        assert (await db.execute(select(func.count()).select_from(Invitation))).scalar_one() == 1
    assert result.email_sent is True
    assert len(attempts) == 1


import asyncio
from datetime import datetime, timedelta
from types import SimpleNamespace

import httpx
import pytest_asyncio
import redis.asyncio as redis
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import FastAPI
from sqlalchemy import text
from sqlalchemy.engine import make_url

from app.config import settings
from app.core.redis import ResilientRedisClient, get_redis
from app.database import get_db
from app.models import User, UserStatus
from app.routers.v1.invitations import router
from app.services.cache import CacheService
from app.services.org_claims_service import get_user_org_claims


@pytest_asyncio.fixture
async def flow(pg, monkeypatch):
    import os

    import app.core.jwt_manager as jwt_module

    factory, actor, org = await prepare(pg)
    async with factory() as db:
        invitee = User(email="invitee@example.com", status=UserStatus.ACTIVE,
                       email_verified=True, is_service_account=False, is_admin=False)
        foreign = User(email="foreign@example.com", status=UserStatus.ACTIVE,
                       email_verified=True, is_service_account=False, is_admin=False)
        db.add_all([invitee, foreign])
        await db.commit()
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    monkeypatch.setattr(settings, "JWT_PRIVATE_KEY", private.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption()).decode())
    monkeypatch.setattr(settings, "JWT_PUBLIC_KEY", "")
    manager = jwt_module.JWTManager()
    assert manager.algorithm == "RS256"
    monkeypatch.setattr(jwt_module, "jwt_manager", manager)
    cache_port = 55520 if make_url(os.environ["JANUA_ORG_CREATE_TEST_DATABASE_URL"]).port == 55519 else 6379
    cache = redis.from_url(f"redis://127.0.0.1:{cache_port}/0", decode_responses=True,
                           socket_connect_timeout=0.2, socket_timeout=0.2)
    monkeypatch.setattr(CacheService, "_redis_client", cache)
    state = {"outcome": True, "attempts": []}

    async def transport(self, **message):
        state["attempts"].append(message)
        if isinstance(state["outcome"], Exception):
            raise state["outcome"]
        return state["outcome"]

    monkeypatch.setattr(EmailService, "_send_email", transport)
    app = FastAPI()
    app.include_router(router, prefix="/api")

    async def database():
        async with factory() as db:
            yield db

    async def native_cache():
        return ResilientRedisClient(cache)

    app.dependency_overrides[get_db] = database
    app.dependency_overrides[get_redis] = native_cache

    def headers(user=actor, claims=None):
        token, _, _ = manager.create_access_token(str(user.id), user.email, claims)
        return {"Authorization": "Bearer " + token}

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app, raise_app_exceptions=False),
                                 base_url="http://fixture") as client:
        yield SimpleNamespace(factory=factory, actor=actor, org=org, invitee=invitee,
                              foreign=foreign, client=client, headers=headers, state=state)
    await cache.aclose()


async def create(flow):
    return await flow.client.post("/api/v1/invitations/", headers=flow.headers(), json={
        "organization_id": str(flow.org.id), "email": flow.invitee.email,
        "role": "member", "message": "Synthetic lesson",
    })


async def token_for(flow):
    async with flow.factory() as db:
        return (await db.execute(select(Invitation.token))).scalar_one()


async def snapshot(flow):
    async with flow.factory() as db:
        inv = (await db.execute(select(Invitation))).scalar_one()
        members = (await db.execute(select(OrganizationMember).where(
            OrganizationMember.user_id == flow.invitee.id,
        ))).scalars().all()
        audits = (await db.execute(select(AuditLog))).scalars().all()
        return inv, members, audits


async def trigger(flow, action, table="audit_logs"):
    async with flow.factory() as db:
        await db.execute(text("CREATE FUNCTION proof_reject() RETURNS trigger LANGUAGE plpgsql "
                              "AS $$ BEGIN RAISE EXCEPTION 'synthetic native rejection'; END $$"))
        condition = f"WHEN (NEW.action = '{action}')" if table == "audit_logs" else ""
        await db.execute(text(f"CREATE TRIGGER proof_reject BEFORE INSERT ON {table} "
                              f"FOR EACH ROW {condition} EXECUTE FUNCTION proof_reject()"))
        await db.commit()


async def remove_trigger(flow, table="audit_logs"):
    async with flow.factory() as db:
        await db.execute(text(f"DROP TRIGGER proof_reject ON {table}"))
        await db.execute(text("DROP FUNCTION proof_reject()"))
        await db.commit()


@pytest.mark.parametrize("outcome,expected", [(True, "acknowledged"), (False, "unconfirmed"),
                                             (RuntimeError("synthetic transport loss"), "unconfirmed")])
async def test_native_send_receipt_fresh_readback(flow, outcome, expected):
    flow.state["outcome"] = outcome
    result = await create(flow)
    assert result.status_code == 201, result.text
    receipt = result.json()
    assert receipt["email_status"] == expected
    assert receipt["message"] == "Synthetic lesson"
    assert receipt["email_sent"] == (expected == "acknowledged")
    read = await flow.client.get("/api/v1/invitations/" + receipt["id"], headers=flow.headers())
    listing = await flow.client.get("/api/v1/invitations/", headers=flow.headers())
    assert read.json()["email_status"] == expected
    assert listing.json()["invitations"][0]["email_status"] == expected
    resend = await flow.client.post("/api/v1/invitations/" + receipt["id"] + "/resend",
                                    headers=flow.headers())
    assert resend.status_code == 400
    assert len(flow.state["attempts"]) == 1
    inv, _, audits = await snapshot(flow)
    attempts = [a for a in audits if a.action == "invitation.email_attempt"]
    assert len(attempts) == 1 and attempts[0].details["attempt_id"] == str(attempts[0].id)
    assert str(inv.id) == attempts[0].details["invitation_id"]
    assert f"token={inv.token}" in flow.state["attempts"][0]["html_content"]


async def test_native_known_not_attempted_then_first_manual_send(flow):
    await trigger(flow, "invitation.email_attempt")
    assert (await create(flow)).status_code == 500
    inv, _, _ = await snapshot(flow)
    response = await flow.client.get(f"/api/v1/invitations/{inv.id}", headers=flow.headers())
    assert response.json()["email_status"] == "not_attempted"
    assert flow.state["attempts"] == []
    await remove_trigger(flow)
    response = await flow.client.post(f"/api/v1/invitations/{inv.id}/resend", headers=flow.headers())
    assert response.status_code == 200 and response.json()["email_status"] == "acknowledged"
    assert len(flow.state["attempts"]) == 1


async def test_native_ack_insert_failure_keeps_unconfirmed(flow):
    await trigger(flow, "invitation.email_ack")
    result = await create(flow)
    assert result.status_code == 201 and result.json()["email_status"] == "unconfirmed"
    inv, _, audits = await snapshot(flow)
    assert inv.email_sent is False
    assert sum(a.action == "invitation.email_attempt" for a in audits) == 1
    assert not any(a.action == "invitation.email_ack" for a in audits)
    assert len(flow.state["attempts"]) == 1
    fresh = await flow.client.get(f"/api/v1/invitations/{inv.id}", headers=flow.headers())
    assert fresh.json()["email_status"] == "unconfirmed"


async def test_native_response_loss_readback_no_second_attempt(flow):
    discarded = await create(flow)
    inv, _, _ = await snapshot(flow)
    read = await flow.client.get(f"/api/v1/invitations/{inv.id}", headers=flow.headers())
    assert read.status_code == 200 and read.json()["id"] == discarded.json()["id"]
    assert read.json()["email_status"] == "acknowledged"
    duplicate = await create(flow)
    assert duplicate.status_code == 400 and len(flow.state["attempts"]) == 1


async def test_native_signed_self_accepts_once_and_claims(flow):
    assert (await create(flow)).status_code == 201
    result = await flow.client.post("/api/v1/invitations/accept", headers=flow.headers(flow.invitee),
                                   json={"token": await token_for(flow), "user_id": str(flow.invitee.id)})
    assert result.status_code == 200, result.text
    inv, members, audits = await snapshot(flow)
    assert inv.status == "accepted" and inv.accepted_at is not None
    assert len(members) == 1 and members[0].role == "member" and members[0].status == "active"
    assert sum(a.action == "invitation.accept" for a in audits) == 1
    async with flow.factory() as db:
        human = (await db.execute(select(User).where(User.id == flow.invitee.id))).scalar_one()
        assert not human.is_admin and not human.is_service_account and human.tenant_id is None
        claims = await get_user_org_claims(human, db)
        assert claims["orgs"] == [{"id": str(flow.org.id), "slug": flow.org.slug, "role": "member"}]
        assert "_app_roles" not in claims and "roles" not in claims


@pytest.mark.parametrize("auth", ["missing", "foreign", "body_mismatch", "bad_audience", "bad_issuer", "expired", "inactive"])
async def test_native_existing_self_denials(flow, auth):
    assert (await create(flow)).status_code == 201
    headers = flow.headers(flow.invitee)
    body_id = str(flow.invitee.id)
    if auth == "missing":
        headers = {}
    elif auth == "foreign":
        headers = flow.headers(flow.foreign)
    elif auth == "body_mismatch":
        body_id = str(flow.foreign.id)
    elif auth in {"bad_audience", "bad_issuer", "expired"}:
        override = {"bad_audience": {"aud": "wrong"}, "bad_issuer": {"iss": "wrong"},
                    "expired": {"exp": datetime.utcnow() - timedelta(seconds=60)}}[auth]
        headers = flow.headers(flow.invitee, override)
    else:
        async with flow.factory() as db:
            user = (await db.execute(select(User).where(User.id == flow.invitee.id))).scalar_one()
            user.status = UserStatus.SUSPENDED
            await db.commit()
    result = await flow.client.post("/api/v1/invitations/accept", headers=headers,
                                   json={"token": await token_for(flow), "user_id": body_id})
    assert result.status_code in {401, 403}, result.text
    inv, members, audits = await snapshot(flow)
    assert inv.status == "pending" and members == []
    assert not any(a.action == "invitation.accept" for a in audits)


async def test_native_creation_audit_failure_is_atomic(flow):
    await trigger(flow, "invitation.create")
    assert (await create(flow)).status_code == 500
    async with flow.factory() as db:
        assert (await db.execute(select(func.count()).select_from(Invitation))).scalar_one() == 0
        assert (await db.execute(select(func.count()).select_from(AuditLog))).scalar_one() == 0
    assert flow.state["attempts"] == []


async def test_native_concurrent_intent_and_acceptance(flow):
    created = await asyncio.gather(create(flow), create(flow))
    assert sorted(r.status_code for r in created) == [201, 400]
    token = await token_for(flow)
    async def accept():
        return await flow.client.post("/api/v1/invitations/accept", headers=flow.headers(flow.invitee),
                                      json={"token": token, "user_id": str(flow.invitee.id)})
    accepted = await asyncio.gather(accept(), accept())
    assert sorted(r.status_code for r in accepted) == [200, 400]
    inv, members, audits = await snapshot(flow)
    assert len(members) == 1 and inv.status == "accepted"
    assert sum(a.action == "invitation.accept" for a in audits) == 1
    assert len(flow.state["attempts"]) == 1


async def test_native_member_insert_rollback(flow):
    assert (await create(flow)).status_code == 201
    await trigger(flow, "", "organization_members")
    response = await flow.client.post("/api/v1/invitations/accept", headers=flow.headers(flow.invitee),
                                     json={"token": await token_for(flow), "user_id": str(flow.invitee.id)})
    assert response.status_code == 500
    inv, members, audits = await snapshot(flow)
    assert inv.status == "pending" and members == []
    assert not any(a.action == "invitation.accept" for a in audits)
    await remove_trigger(flow, "organization_members")
    retry = await flow.client.post("/api/v1/invitations/accept", headers=flow.headers(flow.invitee),
                                  json={"token": await token_for(flow), "user_id": str(flow.invitee.id)})
    assert retry.status_code == 200


async def test_native_multi_org_admin_and_target_denial(flow):
    async with flow.factory() as db:
        extra = Organization(name="Synthetic extra", slug="extra-" + uuid4().hex,
                             owner_id=flow.actor.id)
        db.add(extra)
        await db.flush()
        db.add(OrganizationMember(organization_id=extra.id, user_id=flow.actor.id,
                                  role="admin", status="active"))
        target = (await db.execute(select(Organization).where(Organization.id == flow.org.id))).scalar_one()
        target.owner_id = flow.foreign.id
        member = (await db.execute(select(OrganizationMember).where(
            OrganizationMember.organization_id == flow.org.id))).scalar_one()
        member.status = "removed"
        await db.commit()
    denied = await create(flow)
    assert denied.status_code == 400
    assert flow.state["attempts"] == []
    async with flow.factory() as db:
        member = (await db.execute(select(OrganizationMember).where(
            OrganizationMember.organization_id == flow.org.id))).scalar_one()
        member.status = "active"
        await db.commit()
    assert (await create(flow)).status_code == 201


@pytest.mark.parametrize("status", ["active", "removed", "pending"])
async def test_native_existing_manual_membership_not_adopted(flow, status):
    assert (await create(flow)).status_code == 201
    async with flow.factory() as db:
        db.add(OrganizationMember(organization_id=flow.org.id, user_id=flow.invitee.id,
                                  role="viewer", status=status))
        await db.commit()
    response = await flow.client.post("/api/v1/invitations/accept", headers=flow.headers(flow.invitee),
                                     json={"token": await token_for(flow), "user_id": str(flow.invitee.id)})
    assert response.status_code == 400
    inv, members, _ = await snapshot(flow)
    assert inv.status == "pending" and len(members) == 1
    assert members[0].role == "viewer" and members[0].status == status


async def test_native_legacy_unclassified_cannot_resend(flow):
    async with flow.factory() as db:
        inv = Invitation(organization_id=flow.org.id, email=flow.invitee.email,
                         token="synthetic-legacy-token", created_by=flow.actor.id,
                         expires_at=datetime.utcnow() + timedelta(days=1), email_sent=False)
        db.add(inv)
        await db.commit()
    read = await flow.client.get(f"/api/v1/invitations/{inv.id}", headers=flow.headers())
    assert read.json()["email_status"] is None
    response = await flow.client.post(f"/api/v1/invitations/{inv.id}/resend", headers=flow.headers())
    assert response.status_code == 400 and flow.state["attempts"] == []


async def test_native_unmatched_ack_cannot_confirm_attempt(flow):
    flow.state["outcome"] = False
    assert (await create(flow)).status_code == 201
    async with flow.factory() as db:
        inv = (await db.execute(select(Invitation))).scalar_one()
        inv.email_sent = True
        db.add(AuditLog(user_id=flow.actor.id, action="invitation.email_ack",
                        resource_type="invitation", resource_id=inv.id,
                        details={"invitation_id": str(inv.id), "organization_id": str(flow.org.id),
                                 "attempt_id": str(uuid4()), "email_status": "acknowledged"}))
        await db.commit()
    read = await flow.client.get(f"/api/v1/invitations/{inv.id}", headers=flow.headers())
    assert read.json()["email_status"] == "unconfirmed" and read.json()["email_sent"] is False


async def test_native_ack_commit_response_loss_is_unconfirmed_until_readback(flow, monkeypatch):
    from sqlalchemy.ext.asyncio import AsyncSession

    commit = AsyncSession.commit
    lost = []

    async def response_loss(db):
        ack = any(isinstance(row, AuditLog) and row.action == "invitation.email_ack" for row in db.new)
        await commit(db)
        if ack:
            lost.append(True)
            raise ConnectionError("synthetic acknowledgement response loss")

    monkeypatch.setattr(AsyncSession, "commit", response_loss)
    result = await create(flow)
    assert result.status_code == 201 and result.json()["email_status"] == "unconfirmed"
    assert lost == [True] and len(flow.state["attempts"]) == 1
    read = await flow.client.get("/api/v1/invitations/" + result.json()["id"], headers=flow.headers())
    assert read.json()["email_status"] == "acknowledged"
    resend = await flow.client.post("/api/v1/invitations/" + result.json()["id"] + "/resend",
                                    headers=flow.headers())
    assert resend.status_code == 400 and len(flow.state["attempts"]) == 1
