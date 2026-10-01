"""The SSO orchestrator's audit rows, through the logger it is given.

``SSOController._get_orchestrator`` hands ``SSOOrchestrator`` an
``app.services.audit_logger.AuditLogger``. The orchestrator called
``audit_logger.log_event(...)``, which that class does not have, so SSO
initiation, the callback and logout each raised AttributeError after their
work was done. They now call ``log()`` and commit the audit row; an audit
failure is rolled back and does not fail the sign-in, as in
``app.routers.v1.auth.log_audit_event``.

The audit logger and its table are real (SQLite); the protocol handlers,
repositories, provisioning and token service are stand-ins.
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import settings
from app.models import AuditLog, Base
from app.services import audit_logger as audit_logger_module
from app.services.audit_logger import AUDIT_CONTEXT_KEY, AuditEventType, AuditLogger
from app.sso.application.services.sso_orchestrator import SSOOrchestrator
from app.sso.domain.protocols.base import SSOConfiguration, SSOSession
from tests.unit.services.test_audit_logger_chain import sqlite_with_real_transactions

ORG = str(uuid.uuid4())


@pytest.fixture(autouse=True)
def no_archive_no_encryption(monkeypatch):
    monkeypatch.setattr(audit_logger_module, "_shared_r2_client", None)
    monkeypatch.setattr(settings, "R2_ENDPOINT", None)
    monkeypatch.setattr(settings, "AUDIT_LOG_ENCRYPTION", False)


@pytest.fixture
async def factory(tmp_path):
    engine = sqlite_with_real_transactions(
        create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'sso.db'}", poolclass=NullPool)
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    try:
        yield async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    finally:
        await engine.dispose()


def _config() -> SSOConfiguration:
    return SSOConfiguration(
        organization_id=ORG, protocol="oidc", provider_name="example-idp", config={}
    )


def _orchestrator(db) -> SSOOrchestrator:
    """As SSOController._get_orchestrator builds it, with stand-in collaborators."""
    config_repository = MagicMock()
    config_repository.db = db
    config_repository.get_by_organization = AsyncMock(return_value=_config())
    session_repository = MagicMock()
    session_repository.create = AsyncMock()
    session_repository.invalidate = AsyncMock(return_value=True)
    jwt_service = MagicMock()
    jwt_service.create_token_pair.return_value = {"access_token": "a", "refresh_token": "r"}
    orchestrator = SSOOrchestrator(
        config_repository=config_repository,
        session_repository=session_repository,
        user_provisioning=MagicMock(),
        cache_service=MagicMock(),
        jwt_service=jwt_service,
        audit_logger=AuditLogger(db),
    )
    handler = MagicMock()
    handler.initiate_authentication = AsyncMock(
        return_value={"auth_url": "https://idp.example.com/auth", "protocol": "oidc"}
    )
    handler.initiate_logout = AsyncMock(return_value={"logout_url": "https://idp.example.com/out"})
    orchestrator.protocols["oidc"] = handler
    return orchestrator


async def _rows(factory, event_type):
    async with factory() as fresh:
        result = await fresh.execute(
            select(AuditLog).where(AuditLog.event_type == event_type.value)
        )
        return result.scalars().all()


async def test_initiation_is_audited(factory):
    # A request-scoped session closed without a commit, as get_db does.
    async with factory() as db:
        result = await _orchestrator(db).initiate_authentication(
            organization_id=ORG, protocol="oidc", return_url="https://app.example.com/back"
        )
    assert result["auth_url"] == "https://idp.example.com/auth"

    (row,) = await _rows(factory, AuditEventType.SSO_AUTH_INITIATE)
    assert row.action == "sso.authentication_initiated"
    assert row.tenant_id == ORG
    assert row.user_id is None
    assert row.details["protocol"] == "oidc"
    assert row.details["provider"] == "example-idp"
    assert row.details[AUDIT_CONTEXT_KEY]["organization_id"] == ORG


async def test_callback_success_is_audited(factory):
    user = SimpleNamespace(id=uuid.uuid4(), email="person@example.com", role="member")
    async with factory() as db:
        orchestrator = _orchestrator(db)
        orchestrator.protocols["oidc"].handle_callback = AsyncMock(
            return_value={
                "organization_id": ORG,
                "user_data": {"email": user.email},
                "session_data": {},
            }
        )
        orchestrator.user_provisioning.provision_user = AsyncMock(return_value=user)
        orchestrator.user_provisioning.validate_user_access = AsyncMock(return_value=True)
        result = await orchestrator.handle_authentication_callback("oidc", {"code": "x"})
    assert result["user"] is user

    (row,) = await _rows(factory, AuditEventType.SSO_AUTH_SUCCESS)
    assert row.tenant_id == ORG
    assert row.user_id == user.id
    assert row.details["session_id"] == result["session"].session_id


async def test_logout_is_audited(factory):
    user_id = str(uuid.uuid4())
    async with factory() as db:
        orchestrator = _orchestrator(db)
        orchestrator.session_repository.get_by_session_id = AsyncMock(
            return_value=SSOSession(
                user_id=user_id,
                session_id="sso_1",
                protocol="oidc",
                provider_name="example-idp",
                attributes={},
                expires_at=None,
            )
        )
        result = await orchestrator.initiate_logout(user_id=user_id, session_id="sso_1")
    assert result == {"logout_url": "https://idp.example.com/out"}

    (row,) = await _rows(factory, AuditEventType.SSO_LOGOUT_INITIATE)
    assert str(row.user_id) == user_id
    assert row.tenant_id == ORG
    assert row.details["session_id"] == "sso_1"


async def test_audit_failure_does_not_fail_initiation(factory, monkeypatch):
    async def failing_log(self, **kwargs):
        raise RuntimeError("audit store unavailable")

    monkeypatch.setattr(AuditLogger, "log", failing_log)
    async with factory() as db:
        orchestrator = _orchestrator(db)
        rollback = AsyncMock(wraps=db.rollback)
        db.rollback = rollback
        result = await orchestrator.initiate_authentication(organization_id=ORG, protocol="oidc")
    assert result["protocol"] == "oidc"
    rollback.assert_awaited_once()
    assert await _rows(factory, AuditEventType.SSO_AUTH_INITIATE) == []


async def test_no_audit_logger(factory):
    async with factory() as db:
        orchestrator = _orchestrator(db)
        orchestrator.audit_logger = None
        result = await orchestrator.initiate_authentication(organization_id=ORG, protocol="oidc")
    assert result["protocol"] == "oidc"
    assert await _rows(factory, AuditEventType.SSO_AUTH_INITIATE) == []
