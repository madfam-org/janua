"""The invitation path over the AsyncSession the router injects.

``app/routers/v1/invitations.py`` passes ``get_db``'s ``AsyncSession`` to
``InvitationService``, which drove it through the synchronous ``Session.query``
API, so create, bulk create, resend, revoke and accept all raised before
touching a row. The service is now async end to end, and each operation's audit
row commits with it, on the organization's audit chain.

Real models on SQLite, router handlers called directly; only the email
transport and the cache are faked.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from unittest.mock import AsyncMock

import pytest
from fastapi import BackgroundTasks, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool
from starlette.requests import Request

from app.config import settings
from app.models import AuditLog, Base, Invitation, Organization, OrganizationMember, User
from app.models.invitation import (
    BulkInvitationCreate,
    InvitationAcceptRequest,
    InvitationCreate,
    InvitationStatus,
)
from app.routers.v1 import invitations as router
from app.services import audit_logger as audit_logger_module
from app.services.audit_logger import AUDIT_CONTEXT_KEY, AuditEventType
from app.services.cache import CacheService
from app.services.email_service import EmailService
from app.services.invitation_service import InvitationService
from tests.unit.services.test_audit_logger_chain import sqlite_with_real_transactions


@pytest.fixture(autouse=True)
def no_archive_no_encryption(monkeypatch):
    monkeypatch.setattr(audit_logger_module, "_shared_r2_client", None)
    monkeypatch.setattr(settings, "R2_ENDPOINT", None)
    monkeypatch.setattr(settings, "AUDIT_LOG_ENCRYPTION", False)


@pytest.fixture(autouse=True)
def transport(monkeypatch):
    """Fake only the outbound email transport and the cache."""
    send = AsyncMock(return_value=True)
    monkeypatch.setattr(EmailService, "_send_email", send)
    monkeypatch.setattr(CacheService, "delete", AsyncMock(return_value=True))
    return send


@pytest.fixture
async def factory(tmp_path):
    engine = sqlite_with_real_transactions(
        create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'inv.db'}", poolclass=NullPool)
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    try:
        yield async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    finally:
        await engine.dispose()


@pytest.fixture
async def org_admin(factory):
    """An organization and an admin member of it (the authenticated principal)."""
    async with factory() as db:
        org = Organization(id=uuid.uuid4(), name="Acme", slug="acme")
        admin = User(id=uuid.uuid4(), email="admin@acme.example.com")
        db.add_all([org, admin])
        await db.flush()
        db.add(OrganizationMember(organization_id=org.id, user_id=admin.id, role="admin"))
        await db.commit()
        return org, admin


async def _create(factory, org, admin, email="invitee@example.com", **fields):
    async with factory() as db:
        return await router.create_invitation(
            InvitationCreate(organization_id=str(org.id), email=email, **fields),
            BackgroundTasks(),
            current_user=admin,
            db=db,
        )


async def _invitations(factory):
    async with factory() as fresh:
        return (await fresh.execute(select(Invitation))).scalars().all()


async def _audit(factory, event_type):
    async with factory() as fresh:
        result = await fresh.execute(
            select(AuditLog).where(AuditLog.event_type == event_type.value)
        )
        return result.scalars().all()


def _request() -> Request:
    return Request({"type": "http", "method": "POST", "path": "/", "headers": []})


class TestCreate:
    async def test_creates_mails_and_audits(self, factory, org_admin, transport):
        org, admin = org_admin
        response = await _create(factory, org, admin, role="admin", message="join us")

        assert response.email == "invitee@example.com"
        assert response.role == "admin"
        assert response.email_sent is True
        assert response.message == "join us"
        assert transport.await_count == 1

        (invitation,) = await _invitations(factory)
        assert str(invitation.id) == response.id
        assert invitation.status == InvitationStatus.PENDING.value
        assert invitation.created_by == admin.id
        assert invitation.email_sent is True
        assert invitation.message == "join us"
        assert invitation.token and invitation.token in response.invite_url

        (row,) = await _audit(factory, AuditEventType.INVITATION_CREATE)
        assert row.tenant_id == str(org.id)
        assert row.user_id == admin.id
        assert row.resource_id == invitation.id
        assert row.details[AUDIT_CONTEXT_KEY]["organization_id"] == str(org.id)

    async def test_unsent_email_is_recorded(self, factory, org_admin, transport):
        transport.return_value = False
        org, admin = org_admin
        response = await _create(factory, org, admin)
        assert response.email_sent is False
        (invitation,) = await _invitations(factory)
        assert invitation.email_sent is False

    async def test_admin_of_another_organization_is_refused(self, factory, org_admin):
        org, _ = org_admin
        async with factory() as db:
            outsider = User(id=uuid.uuid4(), email="outsider@example.com")
            db.add(outsider)
            await db.commit()
        with pytest.raises(HTTPException) as refused:
            await _create(factory, org, outsider)
        assert refused.value.status_code == 400
        assert await _invitations(factory) == []
        assert await _audit(factory, AuditEventType.INVITATION_CREATE) == []

    async def test_existing_member_is_refused(self, factory, org_admin):
        org, admin = org_admin
        with pytest.raises(HTTPException) as refused:
            await _create(factory, org, admin, email="admin@acme.example.com")
        assert "already a member" in refused.value.detail

    async def test_second_active_invitation_is_refused(self, factory, org_admin):
        org, admin = org_admin
        await _create(factory, org, admin)
        with pytest.raises(HTTPException) as refused:
            await _create(factory, org, admin)
        assert "active invitation" in refused.value.detail
        assert len(await _invitations(factory)) == 1

    async def test_bulk(self, factory, org_admin):
        org, admin = org_admin
        async with factory() as db:
            result = await router.create_bulk_invitations(
                BulkInvitationCreate(
                    organization_id=str(org.id),
                    emails=["a@example.com", "b@example.com", "admin@acme.example.com"],
                ),
                BackgroundTasks(),
                current_user=admin,
                db=db,
            )
        assert result.total_sent == 2
        assert result.total_failed == 1
        assert len(await _invitations(factory)) == 2
        assert len(await _audit(factory, AuditEventType.INVITATION_CREATE)) == 2


class TestResendAndRevoke:
    async def test_resend(self, factory, org_admin, transport):
        org, admin = org_admin
        created = await _create(factory, org, admin)
        async with factory() as db:
            response = await router.resend_invitation(
                created.id, BackgroundTasks(), current_user=admin, db=db
            )
        assert response.id == created.id
        assert response.email_sent is True
        assert transport.await_count == 2
        (row,) = await _audit(factory, AuditEventType.INVITATION_RESEND)
        assert row.tenant_id == str(org.id)

    async def test_revoke(self, factory, org_admin):
        org, admin = org_admin
        created = await _create(factory, org, admin)
        async with factory() as db:
            await router.revoke_invitation(created.id, current_user=admin, db=db)
        (invitation,) = await _invitations(factory)
        assert invitation.status == InvitationStatus.REVOKED.value
        (row,) = await _audit(factory, AuditEventType.INVITATION_REVOKE)
        assert row.user_id == admin.id
        assert row.tenant_id == str(org.id)

    async def test_revoke_twice_is_refused(self, factory, org_admin):
        org, admin = org_admin
        created = await _create(factory, org, admin)
        async with factory() as db:
            await router.revoke_invitation(created.id, current_user=admin, db=db)
        async with factory() as db:
            with pytest.raises(HTTPException) as refused:
                await router.revoke_invitation(created.id, current_user=admin, db=db)
        assert refused.value.status_code == 400
        assert len(await _audit(factory, AuditEventType.INVITATION_REVOKE)) == 1


class TestAccept:
    async def _token(self, factory):
        (invitation,) = await _invitations(factory)
        return invitation.token

    async def test_new_user(self, factory, org_admin):
        org, admin = org_admin
        await _create(factory, org, admin)
        token = await self._token(factory)

        async with factory() as db:
            result = await router.accept_invitation(
                InvitationAcceptRequest(token=token, name="New Person", password="long-enough-1"),
                _request(),
                db=db,
            )
        assert result.success is True
        assert result.organization_id == str(org.id)

        async with factory() as fresh:
            user = (
                await fresh.execute(select(User).where(User.email == "invitee@example.com"))
            ).scalar_one()
            membership = (
                await fresh.execute(
                    select(OrganizationMember).where(OrganizationMember.user_id == user.id)
                )
            ).scalar_one()
        assert result.user_id == str(user.id)
        assert membership.organization_id == org.id
        assert user.email_verified is True
        (invitation,) = await _invitations(factory)
        assert invitation.status == InvitationStatus.ACCEPTED.value
        assert invitation.accepted_at is not None
        (row,) = await _audit(factory, AuditEventType.INVITATION_ACCEPT)
        assert row.user_id == user.id
        assert row.tenant_id == str(org.id)

    async def test_existing_user(self, factory, org_admin):
        org, admin = org_admin
        await _create(factory, org, admin)
        token = await self._token(factory)
        async with factory() as db:
            person = User(id=uuid.uuid4(), email="invitee@example.com")
            db.add(person)
            await db.commit()

        async with factory() as db:
            result = await router.accept_invitation(
                InvitationAcceptRequest(token=token, user_id=str(person.id)), _request(), db=db
            )
        assert result.user_id == str(person.id)

    async def test_expired(self, factory, org_admin):
        org, admin = org_admin
        await _create(factory, org, admin)
        async with factory() as db:
            (invitation,) = (await db.execute(select(Invitation))).scalars().all()
            invitation.expires_at = datetime.utcnow() - timedelta(minutes=1)
            await db.commit()
            token = invitation.token
        async with factory() as db:
            with pytest.raises(HTTPException) as refused:
                await router.accept_invitation(
                    InvitationAcceptRequest(token=token, name="Late", password="long-enough-1"),
                    _request(),
                    db=db,
                )
        assert "expired" in refused.value.detail
        assert await _audit(factory, AuditEventType.INVITATION_ACCEPT) == []

    async def test_unknown_token(self, factory):
        async with factory() as db:
            with pytest.raises(HTTPException) as refused:
                await router.accept_invitation(
                    InvitationAcceptRequest(token="nope", name="X", password="long-enough-1"),
                    _request(),
                    db=db,
                )
        assert refused.value.detail == "Invalid invitation token"


class TestPendingListing:
    async def test_get_pending_invitations(self, factory, org_admin):
        org, admin = org_admin
        await _create(factory, org, admin)
        async with factory() as db:
            pending = await InvitationService(db).get_pending_invitations(str(org.id))
        assert [i.email for i in pending] == ["invitee@example.com"]


def test_service_uses_no_sync_session_api():
    """No ``.query(`` on the session: it is an AsyncSession."""
    import inspect

    from app.services import invitation_service

    assert ".query(" not in inspect.getsource(invitation_service)

