"""POST /api/v1/internal/email/preview and GET .../preview/templates.

The preview's whole promise is PARITY: for the same input it returns the
subject, From and bodies the real send would hand to Resend, and it never
sends. So the central tests run the preview and the real route side by side
(the real one against a recording SDK stub) and compare; a spy test proves the
preview reaches no transport and no database.
"""

from __future__ import annotations

from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

import app.services.resend_email_service as resend_module
from app.config import settings
from app.database import get_db
from app.main import app
from app.services import resend_transport
from app.services.email_branding import CTM_ORG_ID

PREVIEW = "/api/v1/internal/email/preview"
TEMPLATES = "/api/v1/internal/email/preview/templates"
INTERNAL_KEY = "test-internal-api-key-email-preview"
AUTH = {"X-Internal-API-Key": INTERNAL_KEY}
CTM_CREDENTIAL_ENV = "CTM_RESEND_API_KEY"
CTM_FROM = "Crea Tu Mundo <hola@creatumundo.mx>"
MADFAM_FROM = "MADFAM <hola@madfam.io>"


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.delenv(CTM_CREDENTIAL_ENV, raising=False)
    monkeypatch.setattr(settings, "EMAIL_TRACKED_SENDER_DOMAINS", "", raising=False)
    monkeypatch.setattr(settings, "INTERNAL_API_KEY", INTERNAL_KEY, raising=False)
    yield


@pytest.fixture()
def ctm_key(monkeypatch):
    monkeypatch.setenv(CTM_CREDENTIAL_ENV, "re_test_ctm_key_not_real")


@pytest.fixture()
def client():
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.fixture()
def sdk_sends(monkeypatch) -> List[Dict[str, Any]]:
    captured: List[Dict[str, Any]] = []
    monkeypatch.setattr(resend_module.settings, "EMAIL_ENABLED", True, raising=False)
    monkeypatch.setattr(resend_module.settings, "RESEND_API_KEY", "re_test_fake", raising=False)
    monkeypatch.setattr(resend_module.settings, "ENVIRONMENT", "test", raising=False)

    def _fake_send(params: Dict[str, Any]) -> Dict[str, str]:
        captured.append(params)
        return {"id": "resend-email-id-1"}

    monkeypatch.setattr(resend_transport.resend.Emails, "send", staticmethod(_fake_send))
    return captured


async def _preview(client, body):
    return await client.post(PREVIEW, json=body, headers=AUTH)


# --------------------------------------------------------------------------
# Auth
# --------------------------------------------------------------------------


async def test_preview_requires_the_internal_key(client):
    body = {"kind": "raw", "subject": "s", "text": "t"}
    assert (await client.post(PREVIEW, json=body)).status_code == 422
    wrong = await client.post(PREVIEW, json=body, headers={"X-Internal-API-Key": "nope"})
    assert wrong.status_code == 401
    assert (await client.get(TEMPLATES)).status_code == 422
    assert (await client.get(TEMPLATES, headers={"X-Internal-API-Key": "nope"})).status_code == 401


# --------------------------------------------------------------------------
# Template kind
# --------------------------------------------------------------------------


async def test_template_render_with_ctm_sender(client, ctm_key):
    response = await _preview(
        client,
        {
            "kind": "template",
            "template": "map/pago-confirmado",
            "context": {"periodo": "septiembre de 2026", "sesiones": 4},
            "org_id": CTM_ORG_ID,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"subject", "from", "html", "text", "template"}
    assert body["subject"] == "Tu pago quedó confirmado"
    assert body["from"] == CTM_FROM
    assert "septiembre de 2026" in body["html"] and "(4 sesiones)" in body["html"]
    assert body["text"] is None  # /send-template sends HTML only
    assert body["template"] == "map/pago-confirmado"


@pytest.mark.parametrize(
    ("template", "context"),
    [
        ("map/pago-confirmado", {"periodo": "septiembre de 2026"}),
        (
            "auth/magic-link",
            {"magic_link": "https://map.creatumundo.mx/e?token=x", "expires_in": "15 min"},
        ),
        (
            "invitation/team-invite",
            {
                "inviter_name": "Ana",
                "team_name": "CTM",
                "invite_url": "https://map.creatumundo.mx/i/1",
            },
        ),
        (
            "billing/cfdi",
            {"cliente_nombre": "C", "folio_fiscal": "F", "periodo": "P", "total": "1"},
        ),
    ],
)
@pytest.mark.parametrize("tracked_domains", ["", "creatumundo.mx,madfam.io"])
async def test_template_preview_is_exactly_what_send_template_sends(
    client, sdk_sends, ctm_key, monkeypatch, template, context, tracked_domains
):
    """Side by side: preview vs the real /send-template payload, with and
    without tracking enabled (the token rule must hold identically)."""
    monkeypatch.setattr(settings, "EMAIL_TRACKED_SENDER_DOMAINS", tracked_domains)
    preview = (
        await _preview(
            client,
            {"kind": "template", "template": template, "context": context, "org_id": CTM_ORG_ID},
        )
    ).json()
    sent = await client.post(
        "/api/v1/internal/email/send-template",
        headers=AUTH,
        json={
            "to": ["persona@example.com"],
            "template": template,
            "variables": context,
            "source_app": "crea-map",
            "org_id": CTM_ORG_ID,
        },
    )
    assert sent.json()["success"] is True
    wire = sdk_sends[0]
    assert preview["subject"] == wire["subject"]
    assert resend_module.formataddr(_split(preview["from"])) == wire["from"]
    assert preview["html"] == wire.get("html")
    assert preview["text"] == wire.get("text")


def _split(display: str):
    name, _, addr = display.rpartition(" <")
    return name.strip('"'), addr.rstrip(">")


async def test_token_template_on_tracked_domain_previews_text_only(client, ctm_key, monkeypatch):
    monkeypatch.setattr(settings, "EMAIL_TRACKED_SENDER_DOMAINS", "creatumundo.mx")
    body = (
        await _preview(
            client,
            {
                "kind": "template",
                "template": "auth/magic-link",
                "context": {
                    "magic_link": "https://map.creatumundo.mx/e?token=T0K",
                    "expires_in": "15m",
                },
                "org_id": CTM_ORG_ID,
            },
        )
    ).json()
    assert body["html"] is None
    assert "https://map.creatumundo.mx/e?token=T0K" in body["text"]


async def test_unknown_template_is_404(client):
    response = await _preview(client, {"kind": "template", "template": "nope/nada", "context": {}})
    assert response.status_code == 404
    assert response.json() == {"detail": "Unknown template"}


async def test_missing_context_is_422_listing_names(client):
    response = await _preview(
        client, {"kind": "template", "template": "auth/magic-link", "context": {}}
    )
    assert response.status_code == 422
    assert response.json() == {
        "detail": "Missing required variables",
        "missing": ["magic_link", "expires_in"],
    }


# --------------------------------------------------------------------------
# Raw kind
# --------------------------------------------------------------------------


async def test_raw_is_passed_through_unchanged(client):
    html = "<div><p>Hola</p><a href='https://map.creatumundo.mx/agenda'>Abrir</a></div>"
    body = (
        await _preview(
            client, {"kind": "raw", "subject": "Aviso", "text": "Hola\n\nhttps://x", "html": html}
        )
    ).json()
    assert body == {
        "subject": "Aviso",
        "from": MADFAM_FROM,
        "html": html,
        "text": "Hola\n\nhttps://x",
    }


async def test_raw_text_only_and_html_only(client):
    text_only = (await _preview(client, {"kind": "raw", "subject": "s", "text": "t"})).json()
    assert (text_only["html"], text_only["text"]) == (None, "t")
    html_only = (await _preview(client, {"kind": "raw", "subject": "s", "html": "<p>h</p>"})).json()
    assert (html_only["html"], html_only["text"]) == ("<p>h</p>", None)


async def test_raw_matches_what_send_sends(client, sdk_sends, ctm_key):
    request = {
        "subject": "Aviso",
        "text": "Hola",
        "html": "<p>Hola</p>",
        "from_name": "MAP · Crea Tu Mundo",
        "org_id": CTM_ORG_ID,
    }
    preview = (await _preview(client, {"kind": "raw", **request})).json()
    assert preview["from"] == "MAP · Crea Tu Mundo <hola@creatumundo.mx>"
    await client.post(
        "/api/v1/internal/email/send",
        headers=AUTH,
        json={"to": ["persona@example.com"], "source_app": "crea-map", **request},
    )
    wire = sdk_sends[0]
    assert resend_module.formataddr(_split(preview["from"])) == wire["from"]
    assert (preview["html"], preview["text"], preview["subject"]) == (
        wire["html"],
        wire["text"],
        wire["subject"],
    )


@pytest.mark.parametrize(
    ("extra", "expect_html"),
    [
        ({"html": '<a href="https://map.creatumundo.mx/e?token=x">e</a>'}, False),
        ({"html": "<p>x</p>", "contains_token_link": True}, False),
        ({"html": "<p>x</p>"}, True),
    ],
    ids=["detected", "declared", "plain"],
)
async def test_raw_token_rule_on_tracked_domain(client, ctm_key, monkeypatch, extra, expect_html):
    monkeypatch.setattr(settings, "EMAIL_TRACKED_SENDER_DOMAINS", "creatumundo.mx")
    body = (
        await _preview(client, {"kind": "raw", "subject": "s", "org_id": CTM_ORG_ID, **extra})
    ).json()
    assert (body["html"] is not None) is expect_html
    if not expect_html:
        assert body["text"]


# --------------------------------------------------------------------------
# Sender resolution per org
# --------------------------------------------------------------------------


async def test_sender_resolution_per_org(client, monkeypatch):
    raw = {"kind": "raw", "subject": "s", "text": "t"}
    assert (await _preview(client, raw)).json()["from"] == MADFAM_FROM
    # CTM org without CTM's own key: the platform sender, whole (never mixed).
    no_key = (await _preview(client, {**raw, "org_id": CTM_ORG_ID})).json()
    assert no_key["from"] == MADFAM_FROM
    monkeypatch.setenv(CTM_CREDENTIAL_ENV, "re_test_ctm_key_not_real")
    assert (await _preview(client, {**raw, "org_id": CTM_ORG_ID})).json()["from"] == CTM_FROM
    other_org = "00000000-0000-4000-8000-000000000999"
    assert (await _preview(client, {**raw, "org_id": other_org})).json()["from"] == MADFAM_FROM


async def test_non_uuid_org_id_resolves_like_a_send(client):
    """org_id is a plain string on /send; an id the resolver does not know
    yields the platform sender there, so it does here too (no 422)."""
    response = await _preview(client, {"kind": "raw", "subject": "s", "org_id": "not-a-uuid"})
    assert response.status_code == 200
    assert response.json()["from"] == MADFAM_FROM


def _map_send_body() -> Dict[str, Any]:
    """Exactly what crea-map's notify-email.ts POSTs to /internal/email/send,
    plus every optional SendEmailRequest field and one unknown field."""
    url = "https://map.creatumundo.mx/notificaciones/123"
    text = "Tienes una nueva nota en el expediente."
    return {
        "to": ["persona@example.com"],
        "subject": "Nueva nota — MAP",
        "text": f"{text}\n\n{url}",
        "html": (
            '<div style="font-family:system-ui,sans-serif;font-size:15px;line-height:1.6;'
            f'color:#1c1b18"><p style="margin:0">{text}</p><p style="margin:16px 0 0">'
            f'<a href="{url}" style="color:#1a2a8f;font-weight:600">Abrir en el MAP →</a>'
            "</p></div>"
        ),
        "from_name": "MAP · Crea Tu Mundo",
        "source_app": "crea-map",
        "source_type": "notification",
        "org_id": CTM_ORG_ID,
        "reply_to": "hola@creatumundo.mx",
        "cc": ["copia@example.com"],
        "bcc": ["oculta@example.com"],
        "tags": {"kind": "nota"},
        "attachments": [{"filename": "a.txt", "content": "aG9sYQ==", "content_type": "text/plain"}],
        "some_future_field": {"ignored": True},
    }


@pytest.mark.parametrize("tracked_domains", ["", "creatumundo.mx"])
async def test_raw_preview_of_a_real_map_send_body_matches_the_send(
    client, sdk_sends, ctm_key, monkeypatch, tracked_domains
):
    monkeypatch.setattr(settings, "EMAIL_TRACKED_SENDER_DOMAINS", tracked_domains)
    logger = MagicMock()
    monkeypatch.setattr(resend_module, "logger", logger)
    body = _map_send_body()

    preview = await _preview(client, {"kind": "raw", **body})
    assert preview.status_code == 200
    # Spy: the preview reached no transport and emitted no send-path log line.
    assert sdk_sends == []
    assert logger.method_calls == []
    shown = preview.json()
    assert shown["from"] == "MAP · Crea Tu Mundo <hola@creatumundo.mx>"
    assert "template" not in shown

    sent = await client.post("/api/v1/internal/email/send", headers=AUTH, json=body)
    assert sent.json()["success"] is True
    (wire,) = sdk_sends
    assert resend_module.formataddr(_split(shown["from"])) == wire["from"]
    assert shown["subject"] == wire["subject"]
    assert shown["html"] == wire.get("html")
    assert shown["text"] == wire.get("text")
    # No token link in MAP's notification: HTML survives even on a tracked domain.
    assert shown["html"] == body["html"] and shown["text"] == body["text"]


# --------------------------------------------------------------------------
# Never sends, never touches the database
# --------------------------------------------------------------------------


async def test_preview_never_sends_or_logs(client, ctm_key, monkeypatch):
    monkeypatch.setattr(settings, "EMAIL_TRACKED_SENDER_DOMAINS", "creatumundo.mx")
    monkeypatch.setattr(resend_module.settings, "EMAIL_ENABLED", True, raising=False)
    monkeypatch.setattr(resend_module.settings, "RESEND_API_KEY", "re_test_fake", raising=False)
    sdk = MagicMock(side_effect=AssertionError("preview reached the Resend SDK"))
    monkeypatch.setattr(resend_transport.resend.Emails, "send", sdk)
    service_send = AsyncMock(side_effect=AssertionError("preview called send_email"))
    monkeypatch.setattr(resend_module.ResendEmailService, "send_email", service_send)
    logger = MagicMock()
    monkeypatch.setattr(resend_module, "logger", logger)

    def _no_db():
        raise AssertionError("preview opened a database session")

    app.dependency_overrides[get_db] = _no_db
    try:
        with patch("app.services.email_service.httpx.AsyncClient") as http:
            for body in (
                {
                    "kind": "template",
                    "template": "auth/magic-link",
                    "context": {"magic_link": "https://m.test/?token=x", "expires_in": "1"},
                    "org_id": CTM_ORG_ID,
                },
                {"kind": "raw", "subject": "s", "html": "<p>x</p>", "org_id": CTM_ORG_ID},
            ):
                assert (await _preview(client, body)).status_code == 200
        http.assert_not_called()
    finally:
        app.dependency_overrides.pop(get_db, None)
    sdk.assert_not_called()
    service_send.assert_not_called()
    # Not even the send path's operational log lines (text-only notice, etc.).
    assert logger.method_calls == []


# --------------------------------------------------------------------------
# Template listing
# --------------------------------------------------------------------------


async def test_template_listing(client):
    response = await client.get(TEMPLATES, headers=AUTH)
    assert response.status_code == 200
    listing = {t["id"]: t for t in response.json()}
    assert listing["map/pago-confirmado"] == {
        "id": "map/pago-confirmado",
        "description": listing["map/pago-confirmado"]["description"],
        "subject": "Tu pago quedó confirmado",
        "required_variables": ["periodo"],
        "optional_variables": ["sesiones"],
        "token_link": False,
    }
    assert listing["auth/magic-link"]["token_link"] is True
    assert listing["invitation/team-invite"]["token_link"] is True
    assert listing["auth/magic-link"]["required_variables"] == ["magic_link", "expires_in"]
