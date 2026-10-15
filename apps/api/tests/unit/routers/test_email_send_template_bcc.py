"""`bcc` on POST /api/v1/internal/email/send-template.

/send-template sends each `to` recipient a message of its own (rendered in that
recipient's register), so a BCC cannot simply ride on every message: a BCC
holder would get one copy per recipient, in mixed registers. The contract:

- the BCC rides on the message to the FIRST address in `to` only, so a BCC
  holder gets exactly one copy, and it is exactly that recipient's message;
- an address that is also in `to` (case-insensitive) is dropped, and a repeated
  address is kept once;
- absent, null or empty: no `bcc` on any message (unchanged behaviour).

The real send path runs; only the SDK's ``resend.Emails.send`` boundary is
patched. Every address and value here is synthetic.
"""

from __future__ import annotations

import importlib
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

import app.services.resend_email_service as resend_module
from app.dependencies import verify_internal_api_key
from app.main import app
from app.services import resend_transport

# The module object, to patch names the handler looks up at call time.
email_module = importlib.import_module("app.routers.v1.email")

SEND_TEMPLATE_URL = "/api/v1/internal/email/send-template"
CFDI = "billing/cfdi"
ADVISOR = "asesor@example.com"


@pytest.fixture()
def client():
    app.dependency_overrides[verify_internal_api_key] = lambda: True
    yield AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
    app.dependency_overrides.pop(verify_internal_api_key, None)


@pytest.fixture()
def sent(monkeypatch):
    """Enable the real Resend send path and record each SDK params dict, in order."""
    captured = []
    monkeypatch.setattr(resend_module.settings, "EMAIL_ENABLED", True, raising=False)
    monkeypatch.setattr(resend_module.settings, "RESEND_API_KEY", "re_test_fake", raising=False)
    monkeypatch.setattr(resend_module.settings, "ENVIRONMENT", "test", raising=False)
    assert resend_transport.resend is not None, "resend SDK must be installed for this test"
    monkeypatch.setattr(
        resend_transport.resend.Emails,
        "send",
        staticmethod(lambda params: captured.append(params) or {"id": "fixture-id"}),
    )
    return captured


@pytest.fixture()
def no_stored_register(monkeypatch):
    """No recipient has a stored register (and no database is touched)."""
    lookup = AsyncMock(return_value=None)
    monkeypatch.setattr(email_module, "_stored_formality_for", lookup)
    return lookup


@pytest.fixture()
def service_calls(monkeypatch):
    """Replace ResendService with a recorder of each send_email call's kwargs."""
    calls = []

    class RecordingService:
        async def send_email(self, **kwargs):
            calls.append(kwargs)
            return SimpleNamespace(status="sent", message_id=f"msg-{len(calls)}", error_code=None)

    monkeypatch.setattr(email_module, "ResendService", RecordingService)
    return calls


def _body(variables: dict, to: list, **extra) -> dict:
    return {
        "to": to,
        "template": CFDI,
        "variables": variables,
        "source_app": "nauta",
        "source_type": "billing",
        **extra,
    }


def _recipient(params: dict) -> str:
    return params["to"][0] if isinstance(params["to"], list) else params["to"]


# --------------------------------------------------------------------------- #
# (a) the first recipient's message only
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_bcc_rides_on_the_first_recipients_message_only(
    sent, client, cfdi_variables, no_stored_register
):
    to = ["uno@example.com", "dos@example.com", "tres@example.com"]
    async with client as c:
        resp = await c.post(SEND_TEMPLATE_URL, json=_body(cfdi_variables, to, bcc=[ADVISOR]))
    assert resp.status_code == 200, resp.text
    assert resp.json()["success"] is True
    assert [_recipient(p) for p in sent] == to
    assert sent[0]["bcc"] == [ADVISOR]
    for params in sent[1:]:
        assert "bcc" not in params, _recipient(params)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "registers, bcc_subject",
    [
        ({"uno@example.com": "tu", "dos@example.com": None}, "Tu CFDI"),
        ({"uno@example.com": None, "dos@example.com": "tu"}, "Su CFDI"),
    ],
)
async def test_the_bcc_copy_is_exactly_the_first_recipients_rendering(
    sent, client, cfdi_variables, monkeypatch, registers, bcc_subject
):
    """Recipients in different registers: the BCC holder sees the FIRST one's message."""

    async def lookup(email, org_id):
        return registers[email]

    monkeypatch.setattr(email_module, "_stored_formality_for", lookup)
    to = ["uno@example.com", "dos@example.com"]
    async with client as c:
        resp = await c.post(SEND_TEMPLATE_URL, json=_body(cfdi_variables, to, bcc=[ADVISOR]))
    assert resp.status_code == 200, resp.text
    first, second = sent
    assert first["bcc"] == [ADVISOR]
    assert first["subject"].startswith(bcc_subject)
    assert "bcc" not in second
    assert not second["subject"].startswith(bcc_subject)


@pytest.mark.asyncio
async def test_bcc_is_passed_to_the_first_send_call_and_none_to_the_rest(
    service_calls, client, cfdi_variables, no_stored_register
):
    to = ["uno@example.com", "dos@example.com"]
    async with client as c:
        resp = await c.post(SEND_TEMPLATE_URL, json=_body(cfdi_variables, to, bcc=[ADVISOR]))
    assert resp.status_code == 200, resp.text
    assert [call["to_email"] for call in service_calls] == to
    assert service_calls[0]["bcc"] == [ADVISOR]
    assert service_calls[1]["bcc"] is None
    # Everything else is the same on both messages.
    for key in ("tags", "reply_to", "from_email", "from_name", "attachments", "org_id"):
        assert service_calls[0][key] == service_calls[1][key], key


# --------------------------------------------------------------------------- #
# (b) an address already in `to` is dropped
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_a_bcc_address_that_is_also_a_recipient_is_dropped(
    sent, client, cfdi_variables, no_stored_register
):
    to = ["uno@example.com", "dos@example.com"]
    bcc = ["DOS@example.com", ADVISOR, "Uno@Example.com"]
    async with client as c:
        resp = await c.post(SEND_TEMPLATE_URL, json=_body(cfdi_variables, to, bcc=bcc))
    assert resp.status_code == 200, resp.text
    assert sent[0]["bcc"] == [ADVISOR]
    assert "bcc" not in sent[1]


@pytest.mark.asyncio
async def test_a_bcc_made_only_of_recipients_adds_no_bcc_at_all(
    sent, client, cfdi_variables, no_stored_register
):
    to = ["uno@example.com", "dos@example.com"]
    async with client as c:
        resp = await c.post(
            SEND_TEMPLATE_URL, json=_body(cfdi_variables, to, bcc=["Dos@example.com"])
        )
    assert resp.status_code == 200, resp.text
    assert len(sent) == 2
    assert all("bcc" not in params for params in sent)


@pytest.mark.asyncio
async def test_a_repeated_bcc_address_gets_one_copy(
    sent, client, cfdi_variables, no_stored_register
):
    bcc = [ADVISOR, "Asesor@example.com", "otra@example.com"]
    async with client as c:
        resp = await c.post(
            SEND_TEMPLATE_URL, json=_body(cfdi_variables, ["uno@example.com"], bcc=bcc)
        )
    assert resp.status_code == 200, resp.text
    assert sent[0]["bcc"] == [ADVISOR, "otra@example.com"]


# --------------------------------------------------------------------------- #
# (c) no bcc: unchanged
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
@pytest.mark.parametrize("extra", [{}, {"bcc": None}, {"bcc": []}], ids=["absent", "null", "empty"])
async def test_without_bcc_no_message_carries_one(
    sent, client, cfdi_variables, no_stored_register, extra
):
    to = ["uno@example.com", "dos@example.com"]
    async with client as c:
        resp = await c.post(SEND_TEMPLATE_URL, json=_body(cfdi_variables, to, **extra))
    assert resp.status_code == 200, resp.text
    assert resp.json() == {
        "success": True,
        "delivery_status": "accepted",
        "message_id": "fixture-id",
        "error": None,
        "error_code": None,
    }
    assert len(sent) == 2
    assert all("bcc" not in params for params in sent)


@pytest.mark.asyncio
async def test_without_bcc_every_send_call_gets_none(
    service_calls, client, cfdi_variables, no_stored_register
):
    to = ["uno@example.com", "dos@example.com"]
    async with client as c:
        resp = await c.post(SEND_TEMPLATE_URL, json=_body(cfdi_variables, to))
    assert resp.status_code == 200, resp.text
    assert [call["bcc"] for call in service_calls] == [None, None]


# --------------------------------------------------------------------------- #
# (d) a single recipient
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_a_single_recipient_send_carries_the_bcc(
    sent, client, cfdi_variables, no_stored_register
):
    reply_to = "facturas@example.com"
    async with client as c:
        resp = await c.post(
            SEND_TEMPLATE_URL,
            json=_body(cfdi_variables, ["cliente@example.com"], bcc=[ADVISOR], reply_to=reply_to),
        )
    assert resp.status_code == 200, resp.text
    (params,) = sent
    assert _recipient(params) == "cliente@example.com"
    assert params["bcc"] == [ADVISOR]
    assert params["reply_to"] == reply_to


# --------------------------------------------------------------------------- #
# Validation
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_an_invalid_bcc_address_is_refused_before_any_send(
    sent, client, cfdi_variables, no_stored_register
):
    async with client as c:
        resp = await c.post(
            SEND_TEMPLATE_URL,
            json=_body(cfdi_variables, ["cliente@example.com"], bcc=["no-es-un-correo"]),
        )
    assert resp.status_code == 422
    assert sent == []


@pytest.mark.parametrize(
    "to, bcc, expected",
    [
        (["a@example.com"], None, None),
        (["a@example.com"], [], None),
        (["a@example.com"], ["A@example.com"], None),
        (["a@example.com"], ["b@example.com", "B@example.com"], ["b@example.com"]),
        (["a@example.com", "b@example.com"], ["c@example.com", "b@example.com"], ["c@example.com"]),
    ],
)
def test_first_message_bcc(to, bcc, expected):
    assert email_module._first_message_bcc(to, bcc) == expected
