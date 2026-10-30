"""Neutral auth responses and server-derived MAP provenance, no outbound I/O."""

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException, Response
from starlette.background import BackgroundTasks
from starlette.requests import Request

from app.routers.v1 import auth
from app.services.email_branding import CTM_ORG_ID
from app.services.email_send_audit import CORRELATION_HEADER


def incoming():
    return Request(
        {
            "type": "http",
            "headers": [(b"x-request-id", b"caller-untrusted")],
            "method": "POST",
            "path": "/",
            "query_string": b"",
            "scheme": "https",
            "server": ("auth.test", 443),
            "client": ("127.0.0.1", 1234),
        }
    )


async def test_magic_response_header_never_reveals_account_existence(monkeypatch):
    issue = AsyncMock(return_value=None)
    monkeypatch.setattr(auth, "_issue_magic_link", issue)
    seen = []
    for user in [None, SimpleNamespace(id=uuid.uuid4())]:
        issue.return_value = user
        response = Response()
        body = await auth.send_magic_link(
            incoming(),
            auth.MagicLinkRequest(email="synthetic@example.com"),
            BackgroundTasks(),
            db=object(),
            response=response,
        )
        assert body == {"message": "Magic link sent to email"}
        seen.append(uuid.UUID(response.headers[CORRELATION_HEADER]))
    assert seen[0] != seen[1]


async def test_map_classification_requires_registered_active_org_bound_destination(monkeypatch):
    registered = SimpleNamespace(organization_id=CTM_ORG_ID)
    resolver = AsyncMock(return_value=registered)
    monkeypatch.setattr(auth, "_oauth_client_for_redirect", resolver)
    assert (
        await auth._map_mail_client(
            object(), "https://map.creatumundo.mx/api/auth/magic-verify", None
        )
        is registered
    )
    resolver.return_value = None
    with pytest.raises(HTTPException) as failure:
        await auth._map_mail_client(
            object(), "https://map.creatumundo.mx/api/auth/magic-verify", None
        )
    assert failure.value.status_code == 503
    resolver.return_value = SimpleNamespace(organization_id=uuid.uuid4())
    with pytest.raises(HTTPException):
        await auth._map_mail_client(
            object(), "https://map.creatumundo.mx/api/auth/magic-verify", None
        )
    resolver.reset_mock()
    assert (
        await auth._map_mail_client(
            object(), "https://map.creatumundo.mx.attacker.invalid/callback", None
        )
        is None
    )
    resolver.assert_not_awaited()


@pytest.mark.parametrize("audit_available", [False, True])
async def test_map_issuer_never_schedules_before_intent_commits(monkeypatch, audit_available):
    from unittest.mock import MagicMock

    from app.models.email_send_audit import EmailSendAudit

    monkeypatch.setattr(auth.settings, "ENABLE_MAGIC_LINKS", True)
    monkeypatch.setattr(auth.settings, "EMAIL_ENABLED", True)
    monkeypatch.setattr(auth, "enforce_magic_link_limits", AsyncMock())
    monkeypatch.setattr(
        auth,
        "get_user_by_email",
        AsyncMock(
            return_value=SimpleNamespace(
                id=uuid.uuid4(),
                email="synthetic@example.com",
                locale=None,
                spanish_formality=None,
            )
        ),
    )
    monkeypatch.setattr(auth, "validate_redirect_url", lambda value, **_: value)
    monkeypatch.setattr(
        auth,
        "_map_mail_client",
        AsyncMock(return_value=SimpleNamespace(organization_id=CTM_ORG_ID)),
    )
    sequence = []
    db = AsyncMock()
    added = []
    db.add = MagicMock(side_effect=added.append)
    db.execute = AsyncMock(return_value=SimpleNamespace(rowcount=1))
    db.flush = AsyncMock(
        side_effect=None if audit_available else RuntimeError("synthetic unavailable store")
    )

    async def commit():
        sequence.append("durable")

    db.commit = AsyncMock(side_effect=commit)
    tasks = MagicMock()
    tasks.add_task.side_effect = lambda *_, **__: sequence.append("scheduled")
    response = Response()
    data = auth.MagicLinkRequest(
        email="synthetic@example.com",
        redirect_url="https://map.creatumundo.mx/api/auth/magic-verify",
    )
    if not audit_available:
        with pytest.raises(HTTPException) as error:
            await auth.send_magic_link(incoming(), data, tasks, db=db, response=response)
        assert error.value.status_code == 503
        tasks.add_task.assert_not_called()
        db.rollback.assert_awaited_once()
        auth.get_user_by_email.assert_not_awaited()
    else:
        await auth.send_magic_link(incoming(), data, tasks, db=db, response=response)
        assert sequence == ["durable", "durable", "scheduled"]
        intent = next(row for row in added if isinstance(row, EmailSendAudit))
        assert str(intent.id) == response.headers[CORRELATION_HEADER]
        assert intent.source_app == "crea-map" and intent.message_kind == "magic_login"
        assert tasks.add_task.call_args.kwargs["mail_audit_id"] == str(intent.id)
