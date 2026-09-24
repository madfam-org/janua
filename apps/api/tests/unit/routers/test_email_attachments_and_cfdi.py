"""Unit tests for attachment forwarding and the CFDI-delivery template.

Two gaps this slice closed:

1. The email request models declared ``attachments`` on both /email/send and
   /email/send-template, but the field never reached ``resend.Emails.send`` —
   ResendEmailService.send_email built its ``params`` dict without an
   ``attachments`` key, so a caller's files were silently dropped. That blocked
   the downstream CFDI-delivery feature (a stamped XML + PDF mailed to a
   client). These tests drive the real send path (patching only the SDK's
   ``resend.Emails.send`` boundary) and assert ``params["attachments"]`` carries
   the files, for BOTH handlers.

2. ``billing/invoice`` was registered but had no backing HTML file, so it fell
   back to the generic HTML. A ``billing/cfdi`` template (Spanish, fiscal
   madfam.io sender) was added; a test renders it with its required vars.

The service short-circuits to a console/disabled no-op unless EMAIL_ENABLED is
true and a RESEND_API_KEY is present, so the fixtures set both to fake values
and patch the SDK call — no network, no real key, no real recipient.
"""

from __future__ import annotations

import base64
from typing import Any, Dict, List

import pytest

from app.services import resend_transport
from httpx import ASGITransport, AsyncClient

import app.services.resend_email_service as resend_module
from app.dependencies import verify_internal_api_key
from app.main import app
from app.routers.v1.email import EMAIL_TEMPLATES, render_template

SEND_URL = "/api/v1/internal/email/send"
SEND_TEMPLATE_URL = "/api/v1/internal/email/send-template"

# A tiny, entirely synthetic "attachment" — not a real document.
_XML_B64 = base64.b64encode(b"<cfdi>fixture</cfdi>").decode()
_PDF_B64 = base64.b64encode(b"%PDF-1.4 fixture").decode()


@pytest.fixture()
def client():
    app.dependency_overrides[verify_internal_api_key] = lambda: True
    transport = ASGITransport(app=app)
    yield AsyncClient(transport=transport, base_url="http://test")
    app.dependency_overrides.pop(verify_internal_api_key, None)


@pytest.fixture()
def capture_resend(monkeypatch):
    """Enable the real Resend send path and capture every params dict.

    Patches settings so the service does not short-circuit to the disabled /
    console no-op, and replaces ``resend.Emails.send`` with a recorder. Returns
    the list the recorder appends each call's params to.
    """
    captured: List[Dict[str, Any]] = []

    monkeypatch.setattr(resend_module.settings, "EMAIL_ENABLED", True, raising=False)
    monkeypatch.setattr(resend_module.settings, "RESEND_API_KEY", "re_test_fake", raising=False)
    monkeypatch.setattr(resend_module.settings, "ENVIRONMENT", "test", raising=False)

    def _fake_send(params: Dict[str, Any]) -> Dict[str, str]:
        captured.append(params)
        return {"id": "resend-fixture-id"}

    # resend may be None if the SDK is absent; the send path needs it here.
    assert resend_transport.resend is not None, "resend SDK must be installed for this test"
    monkeypatch.setattr(resend_transport.resend.Emails, "send", staticmethod(_fake_send))
    return captured


def _attachments_payload() -> List[Dict[str, str]]:
    return [
        {"filename": "cfdi.xml", "content": _XML_B64, "content_type": "application/xml"},
        {"filename": "cfdi.pdf", "content": _PDF_B64, "content_type": "application/pdf"},
    ]


@pytest.mark.asyncio
async def test_send_forwards_attachments_to_resend(capture_resend, client):
    """Raw /email/send must pass attachments through to resend.Emails.send."""
    body = {
        "to": ["cliente@example.com"],
        "subject": "CFDI de prueba",
        "html": "<p>adjunto</p>",
        "attachments": _attachments_payload(),
        "source_app": "nauta",
        "source_type": "billing",
    }
    async with client as c:
        resp = await c.post(SEND_URL, json=body)

    assert resp.status_code == 200, resp.text
    assert resp.json()["success"] is True
    assert len(capture_resend) == 1
    params = capture_resend[0]
    assert "attachments" in params, "attachments were dropped before Resend"
    filenames = [a["filename"] for a in params["attachments"]]
    assert filenames == ["cfdi.xml", "cfdi.pdf"]
    assert params["attachments"][0]["content"] == _XML_B64
    assert params["attachments"][0]["content_type"] == "application/xml"


@pytest.mark.asyncio
async def test_send_template_forwards_attachments_to_resend(capture_resend, client, cfdi_variables):
    """/email/send-template must also forward attachments (CFDI delivery)."""
    body = {
        "to": ["cliente@example.com"],
        "template": "billing/cfdi",
        "variables": cfdi_variables,
        "attachments": _attachments_payload(),
        "source_app": "nauta",
        "source_type": "billing",
    }
    async with client as c:
        resp = await c.post(SEND_TEMPLATE_URL, json=body)

    assert resp.status_code == 200, resp.text
    assert resp.json()["success"] is True
    assert len(capture_resend) == 1
    params = capture_resend[0]
    assert "attachments" in params, "template send dropped attachments"
    assert [a["filename"] for a in params["attachments"]] == ["cfdi.xml", "cfdi.pdf"]


@pytest.mark.asyncio
async def test_send_template_cfdi_defaults_to_madfam_fiscal_sender(
    capture_resend, client, cfdi_variables
):
    """With no caller from_email, the CFDI template sends from the madfam.io
    fiscal address (facturacion@madfam.io), never a client domain."""
    body = {
        "to": ["cliente@example.com"],
        "template": "billing/cfdi",
        "variables": cfdi_variables,
        "source_app": "nauta",
        "source_type": "billing",
    }
    async with client as c:
        resp = await c.post(SEND_TEMPLATE_URL, json=body)

    assert resp.status_code == 200, resp.text
    params = capture_resend[0]
    assert "facturacion@madfam.io" in params["from"]


@pytest.mark.asyncio
async def test_send_honors_multiple_recipients(capture_resend, client):
    """A multi-recipient ``to`` list results in one Resend call per recipient,
    each addressed to exactly that recipient."""
    body = {
        "to": ["uno@example.com", "dos@example.com", "tres@example.com"],
        "subject": "Multi",
        "html": "<p>hola</p>",
        "source_app": "nauta",
        "source_type": "notification",
    }
    async with client as c:
        resp = await c.post(SEND_URL, json=body)

    assert resp.status_code == 200, resp.text
    assert resp.json()["success"] is True
    sent_to = [params["to"] for params in capture_resend]
    assert sent_to == [["uno@example.com"], ["dos@example.com"], ["tres@example.com"]]


@pytest.mark.asyncio
async def test_send_without_attachments_omits_the_key(capture_resend, client):
    """An ordinary message must not grow an empty attachments key."""
    body = {
        "to": ["cliente@example.com"],
        "subject": "Sin adjuntos",
        "html": "<p>hola</p>",
        "source_app": "nauta",
        "source_type": "notification",
    }
    async with client as c:
        resp = await c.post(SEND_URL, json=body)

    assert resp.status_code == 200, resp.text
    assert "attachments" not in capture_resend[0]


def test_cfdi_template_is_registered_with_required_vars(cfdi_variables):
    entry = EMAIL_TEMPLATES.get("billing/cfdi")
    assert entry is not None, "billing/cfdi template must be registered"
    # The v2 contract: every fiscal value is required (see test_email_cfdi_v2.py).
    assert set(entry["required"]) == set(cfdi_variables)
    assert entry["optional"] == ["portal_url"]
    assert entry["default_from_email"] == "facturacion@madfam.io"


@pytest.mark.asyncio
async def test_cfdi_template_renders_with_required_vars(cfdi_variables):
    """The CFDI template file exists and its placeholders are substituted (not
    falling back to the generic HTML), and the body is Spanish."""
    html = await render_template("billing/cfdi", cfdi_variables)

    # Values are substituted (proves the backing file resolved, not fallback).
    assert cfdi_variables["folio_fiscal"] in html
    assert cfdi_variables["total"] in html
    assert "{{" not in html
    # Spanish, client-facing.
    assert "comprobante fiscal" in html.lower()
    assert 'lang="es"' in html
