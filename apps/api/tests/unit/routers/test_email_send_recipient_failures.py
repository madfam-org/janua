"""Unit tests for POST /api/v1/email/send failure surfacing.

Regression guard for the money-mail Phase 0 fix: a Resend rejection comes
back from ResendService.send_email as a result whose ``status`` is
"failed"/"bounced" (a VALUE, not an exception). The endpoint used to return
``success=True`` as long as no exception was raised, so a caller (e.g.
crea-map billing/payment mail) could believe a statement was sent when it
never left. The handler now inspects each recipient's status and returns
``success=False`` with an error when any recipient did not reach a delivered
state (sent/delivered/disabled).
"""

from __future__ import annotations

from dataclasses import dataclass
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.dependencies import verify_internal_api_key
from app.main import app

SEND_URL = "/api/v1/internal/email/send"


@dataclass
class _Result:
    """Mimics EmailDeliveryStatus enough for the handler's status check."""

    status: str
    message_id: str = "janua-test-msgid"


def _mock_resend(monkeypatch, status: str) -> None:
    """Patch the ResendService the handler instantiates so send_email yields
    a result with the given status."""
    instance = AsyncMock()
    instance.send_email = AsyncMock(return_value=_Result(status=status))
    monkeypatch.setattr("app.routers.v1.email.ResendService", lambda *a, **k: instance)


@pytest.fixture()
def client():
    app.dependency_overrides[verify_internal_api_key] = lambda: True
    transport = ASGITransport(app=app)
    yield AsyncClient(transport=transport, base_url="http://test")
    app.dependency_overrides.pop(verify_internal_api_key, None)


def _body(**over):
    base = {
        "to": ["familia@example.com"],
        "subject": "Estado de cuenta",
        "html": "<p>hola</p>",
        "text": "hola",
        "source_app": "crea-map",
        "source_type": "billing",
        "org_id": "e6cbd51d-8329-4c4e-8c74-aba643ab4575",
    }
    base.update(over)
    return base


@pytest.mark.asyncio
async def test_failed_recipient_returns_success_false(monkeypatch, client):
    """A Resend 'failed' status must surface as success=False with an error —
    not the old masked success=True."""
    _mock_resend(monkeypatch, status="failed")
    async with client as c:
        resp = await c.post(SEND_URL, json=_body())
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is False
    assert data["error"] and "failed" in data["error"]


@pytest.mark.asyncio
async def test_bounced_recipient_returns_success_false(monkeypatch, client):
    """A 'bounced' status is also a non-delivery and must not read as success."""
    _mock_resend(monkeypatch, status="bounced")
    async with client as c:
        resp = await c.post(SEND_URL, json=_body())
    assert resp.json()["success"] is False


@pytest.mark.asyncio
async def test_sent_recipient_returns_success_true(monkeypatch, client):
    """A delivered state still returns success=True with a message id."""
    _mock_resend(monkeypatch, status="sent")
    async with client as c:
        resp = await c.post(SEND_URL, json=_body())
    data = resp.json()
    assert data["success"] is True
    assert data["message_id"] == "janua-test-msgid"


@pytest.mark.asyncio
async def test_disabled_state_is_reported_as_simulation(monkeypatch, client):
    """A no-op never certifies transmission to the recipient."""
    _mock_resend(monkeypatch, status="disabled")
    async with client as c:
        resp = await c.post(SEND_URL, json=_body())
    assert resp.json()["success"] is False
    assert resp.json()["delivery_status"] == "simulated"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "send_status,expected",
    [
        ("sent", "accepted"),
        ("delivered", "accepted"),
        ("failed", "failed"),
        ("bounced", "failed"),
        ("pending", "failed"),
        ("disabled", "simulated"),
        ("simulated", "simulated"),
    ],
)
async def test_template_reports_the_provider_outcome(monkeypatch, client, send_status, expected):
    _mock_resend(monkeypatch, status=send_status)
    async with client as c:
        response = await c.post(
            SEND_URL + "-template",
            json={
                "to": ["persona01@example.com"],
                "template": "map/pago-confirmado",
                "variables": {"periodo": "septiembre de 2026"},
                "source_app": "crea-map",
            },
        )
    assert response.status_code == 200
    assert response.json()["delivery_status"] == expected
    assert response.json()["success"] is (expected == "accepted")


@pytest.mark.asyncio
@pytest.mark.parametrize("endpoint", [SEND_URL, SEND_URL + "-template"])
async def test_no_recipient_is_rejected_before_sending(monkeypatch, client, endpoint):
    _mock_resend(monkeypatch, status="sent")
    body = (
        _body(to=[])
        if endpoint == SEND_URL
        else {
            "to": [],
            "template": "map/pago-confirmado",
            "variables": {"periodo": "fixture"},
            "source_app": "crea-map",
        }
    )
    async with client as c:
        response = await c.post(endpoint, json=body)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_template_partial_failure_is_not_success(monkeypatch, client):
    instance = AsyncMock()
    instance.send_email = AsyncMock(side_effect=[_Result("sent"), _Result("failed")])
    monkeypatch.setattr("app.routers.v1.email.ResendService", lambda: instance)
    async with client as c:
        response = await c.post(
            SEND_URL + "-template",
            json={
                "to": ["persona01@example.com", "persona02@example.com"],
                "template": "map/pago-confirmado",
                "variables": {"periodo": "fixture"},
                "source_app": "crea-map",
            },
        )
    assert response.json()["success"] is False
    assert response.json()["delivery_status"] == "failed"


@pytest.mark.asyncio
async def test_provider_exception_does_not_disclose_recipient_or_payload(
    monkeypatch, client, caplog
):
    instance = AsyncMock()
    instance.send_email = AsyncMock(side_effect=RuntimeError("private-provider-payload-fixture"))
    monkeypatch.setattr("app.routers.v1.email.ResendService", lambda: instance)
    async with client as c:
        response = await c.post(SEND_URL, json=_body())
    assert response.json()["success"] is False
    assert "private-provider-payload-fixture" not in response.text
    assert "private-provider-payload-fixture" not in caplog.text
