"""Unit tests for the MAP integrante payment-confirmation template.

Slice 1 of 2 for MAP-comms decision #3 ("emails built in janua, MAP calls a
pipe"). This slice builds the janua-side template + registry entry; the MAP
side (calling send-template) is a separate later slice.

The template `map/pago-confirmado` is DELIBERATELY MONEY-LIGHT: it tells a
colaboradora that the period's work was paid and thanks her, and carries NO
amount, currency, rate, bank/CLABE, beca/percentage, or clinical field. Those
figures live in HCM and the CFDI cockpit, never in this notice. A money-safety
guard test renders the template with a variables dict a buggy caller might
over-supply (an extra `amount`, `total`, `clabe`, `beca`) and asserts none of it
reaches the body, because the template never references those slots.

Its variable contract, which slice 2 (the MAP call) must match EXACTLY:
    required: ["periodo"]          e.g. "septiembre de 2026"
    optional: ["sesiones"]         a non-fiscal session COUNT (integer)
    subject : "Tu pago quedó confirmado"

SENDER. Unlike billing/cfdi (a madfam.io fiscal sender set as a per-template
default), this is a team notice FROM the CTM org: it declares NO
default_from_email and resolves to Crea Tu Mundo <hola@creatumundo.mx> via
org_id, the same envelope as MAP's other campana mail.

The service short-circuits to a console/disabled no-op unless EMAIL_ENABLED is
true and a RESEND_API_KEY is present, so the fixtures set both to fake values
and patch the SDK call — no network, no real key, no real recipient.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient

import app.services.resend_email_service as resend_module
from app.dependencies import verify_internal_api_key
from app.main import app
from app.routers.v1.email import (
    EMAIL_TEMPLATES,
    TEMPLATE_FILENAMES,
    _get_safe_template_path,
    render_template,
)
from app.services import resend_transport
from app.services.email_branding import CTM_BRANDING, CTM_ORG_ID

SEND_TEMPLATE_URL = "/api/v1/internal/email/send-template"
TEMPLATE_ID = "map/pago-confirmado"

# Word markers a money-safe integrante notice must NEVER contain. If a future
# edit adds an amount/bank/beca/clinical slot, or a buggy caller's extra vars
# leak into the body, one of these fires. Bare "$"/"%" are deliberately NOT
# here: they collide with legitimate layout markup (width="100%") and CSS; the
# concrete over-supplied VALUES ("50%", "4,500.00 MXN", a CLABE) are asserted
# separately below, which is the sharper guard.
MONEY_MARKERS = ["amount", "total", "monto", "mxn", "clabe", "beca", "diagn"]

# CTM's own Resend key: its binding is account="tenant", so the branded sender
# only resolves when this env var is present (mirror of test_email_sender.py).
CTM_CREDENTIAL_ENV = "CTM_RESEND_API_KEY"
FAKE_CTM_KEY = "re_test_ctm_key_not_real"

_HTML_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
_STYLE_BLOCK = re.compile(r"<style.*?</style>", re.DOTALL | re.IGNORECASE)


def _visible_body(html: str) -> str:
    """The part a recipient actually sees: the rendered HTML minus comments
    and the <style> block.

    Comments never display in a mail client, and the leading comment documents
    the money-safety rule (so it legitimately names the words this notice must
    not SHOW). The <style> block carries CSS like ``width: 100%`` whose ``%``
    is not a money figure. Stripping both leaves the message text the guarantee
    is actually about; the shipped source is kept clean of specific money values
    independently.
    """
    return _STYLE_BLOCK.sub("", _HTML_COMMENT.sub("", html))


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

    assert resend_transport.resend is not None, "resend SDK must be installed for this test"
    monkeypatch.setattr(resend_transport.resend.Emails, "send", staticmethod(_fake_send))
    return captured


# --------------------------------------------------------------------------
# Registry contract
# --------------------------------------------------------------------------


def test_template_is_registered_with_exact_contract():
    """The variable contract slice 2 (the MAP call) must match exactly."""
    entry = EMAIL_TEMPLATES.get(TEMPLATE_ID)
    assert entry is not None, "map/pago-confirmado template must be registered"
    assert entry["required"] == ["periodo"]
    assert entry["optional"] == ["sesiones"]
    assert entry["subject"] == "Tu pago quedó confirmado"


def test_template_is_mapped_to_a_backing_file():
    assert TEMPLATE_ID in TEMPLATE_FILENAMES
    assert TEMPLATE_FILENAMES[TEMPLATE_ID] == "map_pago-confirmado.html"
    assert Path(_get_safe_template_path(TEMPLATE_ID)).is_file()


def test_contract_declares_no_money_or_clinical_variable():
    """The whole safety point: the contract carries no fiscal/bank/clinical
    field. If a future edit adds one, this fails."""
    entry = EMAIL_TEMPLATES[TEMPLATE_ID]
    forbidden = {
        "amount",
        "currency",
        "total",
        "monto",
        "rate",
        "tarifa",
        "clabe",
        "banco",
        "beca",
        "percentage",
        "porcentaje",
    }
    declared = set(entry["required"]) | set(entry["optional"])
    assert declared.isdisjoint(forbidden), f"money/clinical var declared: {declared & forbidden}"


def test_template_declares_no_default_from_email():
    """Unlike billing/cfdi, this template must NOT pin a per-template sender:
    it defers to the CTM org sender resolved from org_id."""
    entry = EMAIL_TEMPLATES[TEMPLATE_ID]
    assert "default_from_email" not in entry
    assert "default_from_name" not in entry


# --------------------------------------------------------------------------
# Rendering
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_renders_with_periodo_only():
    """periodo alone renders cleanly: value substituted, Spanish body, and NO
    leftover placeholder for the omitted optional count."""
    html = await render_template(TEMPLATE_ID, {"periodo": "septiembre de 2026"})
    body = _visible_body(html)

    assert "septiembre de 2026" in body
    assert 'lang="es"' in html
    assert "Gracias por tu labor" in body
    # The backing file resolved (not the generic fallback).
    assert "{{periodo}}" not in html
    # The optional count was omitted, so the derived phrase is empty and no
    # literal slot leaks into the family-facing body.
    assert "{{sesiones}}" not in html
    assert "{{sesiones_detalle}}" not in html
    assert "sesión" not in body and "sesiones" not in body


@pytest.mark.asyncio
async def test_renders_with_singular_sesion():
    html = await render_template(TEMPLATE_ID, {"periodo": "septiembre de 2026", "sesiones": 1})
    assert "(1 sesión)" in html
    assert "sesiones)" not in html


@pytest.mark.asyncio
async def test_renders_with_plural_sesiones():
    html = await render_template(TEMPLATE_ID, {"periodo": "septiembre de 2026", "sesiones": 8})
    assert "(8 sesiones)" in html


@pytest.mark.asyncio
async def test_zero_or_blank_sesiones_shows_nothing():
    """A 0 / blank / non-integer count is treated as absent, never rendered raw,
    so a malformed caller cannot inject text through the slot."""
    for bad in (0, "", "muchas", None):
        html = await render_template(
            TEMPLATE_ID, {"periodo": "septiembre de 2026", "sesiones": bad}
        )
        body = _visible_body(html)
        assert "sesión" not in body and "sesiones" not in body, bad
        assert "{{sesiones" not in html, bad


# --------------------------------------------------------------------------
# Money safety
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_money_and_clinical_fields_never_reach_the_body():
    """A buggy caller over-supplies amount/total/bank/beca/clinical vars. The
    template references none of them, so none may appear in the rendered body.
    This is the money-email guard for the integrante notice."""
    html = await render_template(
        TEMPLATE_ID,
        {
            "periodo": "septiembre de 2026",
            "sesiones": 3,
            # Nothing below is in the contract; a careless caller passes them.
            "amount": "4500.00",
            "total": "4,500.00 MXN",
            "monto": "4500",
            "currency": "MXN",
            "clabe": "002010077777777771",
            "beca": "50%",
            "diagnostico": "TEA nivel 2",
        },
    )
    body = _visible_body(html)
    lowered = body.lower()
    for marker in MONEY_MARKERS:
        assert marker not in lowered, f"money/bank marker leaked into body: {marker!r}"
    # The over-supplied fiscal/clinical VALUES specifically must be absent.
    for value in ("4500.00", "4,500.00", "MXN", "002010077777777771", "50%", "TEA nivel 2"):
        assert value not in body, f"over-supplied value leaked: {value!r}"


# --------------------------------------------------------------------------
# Send path + subject + CTM-org sender
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_missing_periodo_is_rejected_by_registry_validation(client):
    """A send with the required `periodo` absent is a 400 from the registry
    validation, before any render or send."""
    body = {
        "to": ["integrante@example.com"],
        "template": TEMPLATE_ID,
        "variables": {"sesiones": 4},  # no periodo
        "source_app": "crea-map",
        "source_type": "notification",
        "org_id": CTM_ORG_ID,
    }
    async with client as c:
        resp = await c.post(SEND_TEMPLATE_URL, json=body)

    assert resp.status_code == 400, resp.text
    # The app's global error handler reshapes HTTPException.detail into
    # {"error": {"code", "message", ...}}.
    assert "periodo" in resp.json()["error"]["message"]


@pytest.mark.asyncio
async def test_send_returns_message_id_and_spanish_subject(capture_resend, client):
    """A well-formed send succeeds with a message_id and the verbatim Spanish
    subject MAP already uses (so the change is invisible to recipients)."""
    body = {
        "to": ["integrante@example.com"],
        "template": TEMPLATE_ID,
        "variables": {"periodo": "septiembre de 2026", "sesiones": 2},
        "source_app": "crea-map",
        "source_type": "notification",
        "org_id": CTM_ORG_ID,
    }
    with (
        patch.dict(os.environ, {CTM_CREDENTIAL_ENV: FAKE_CTM_KEY}),
        patch.object(resend_module.settings, "RESEND_VERIFIED_DOMAINS", "madfam.io,creatumundo.mx"),
    ):
        async with client as c:
            resp = await c.post(SEND_TEMPLATE_URL, json=body)

    assert resp.status_code == 200, resp.text
    payload = resp.json()
    assert payload["success"] is True
    assert payload["message_id"] == "resend-fixture-id"
    assert len(capture_resend) == 1
    assert capture_resend[0]["subject"] == "Tu pago quedó confirmado"


@pytest.mark.asyncio
async def test_resolves_to_ctm_org_sender_via_org_id(capture_resend, client):
    """With no caller from_email and no per-template default, org_id=CTM resolves
    the sender to Crea Tu Mundo <hola@creatumundo.mx> — NOT a madfam.io/platform
    address. The CTM binding is account="tenant", so its own key must be present
    and its domain verified for the branded envelope to ship (mirror of the
    sender-module tests)."""
    body = {
        "to": ["integrante@example.com"],
        "template": TEMPLATE_ID,
        "variables": {"periodo": "septiembre de 2026"},
        "source_app": "crea-map",
        "source_type": "notification",
        "org_id": CTM_ORG_ID,
    }
    with (
        patch.dict(os.environ, {CTM_CREDENTIAL_ENV: FAKE_CTM_KEY}),
        patch.object(resend_module.settings, "RESEND_VERIFIED_DOMAINS", "madfam.io,creatumundo.mx"),
    ):
        async with client as c:
            resp = await c.post(SEND_TEMPLATE_URL, json=body)

    assert resp.status_code == 200, resp.text
    params = capture_resend[0]
    assert "hola@creatumundo.mx" in params["from"]
    assert "madfam.io" not in params["from"]


# --------------------------------------------------------------------------
# The Crea frame (2026-09-28): presentation only, values from CTM_BRANDING
# --------------------------------------------------------------------------

_STYLE_TAG = re.compile(r"<style\b", re.IGNORECASE)
_SLOT = re.compile(r"\{\{\s*[A-Za-z_][A-Za-z0-9_]*\s*\}\}")


async def _render_full(**extra: Any) -> str:
    return await render_template(
        TEMPLATE_ID, {"periodo": "septiembre de 2026", "sesiones": 8, **extra}
    )


@pytest.mark.asyncio
async def test_renders_in_the_crea_frame_from_ctm_branding():
    """Header ground, header text, both logos and the platform credit are the
    CTM registry's values: the same ones base.html's CTM frame draws."""
    html = await _render_full()
    header = html.split("Tu pago quedó confirmado</h1>")[0]
    assert CTM_BRANDING["header_bg"] == "#2d2f86"
    assert f'bgcolor="{CTM_BRANDING["header_bg"]}"' in header
    assert f"background-color: {CTM_BRANDING['header_bg']}" in header
    assert f"color: {CTM_BRANDING['header_fg']}" in header
    assert CTM_BRANDING["header_fg"] == "#fdf6e3"
    assert (
        f'<img src="{CTM_BRANDING["header_logo_url"]}" width="60" height="60" '
        f'alt="{CTM_BRANDING["header_name"]}"' in header
    )
    footer = html.split("con gusto te apoyamos.")[1]
    assert CTM_BRANDING["footer_logo_url"] in footer
    assert "Con tecnología de" in footer
    assert f'<a href="{CTM_BRANDING["platform_url"]}"' in footer
    assert f">{CTM_BRANDING['platform_name']}</a>" in footer
    assert CTM_BRANDING["platform_name"] == "MADFAM"


@pytest.mark.asyncio
async def test_crea_frame_keeps_every_variable_and_all_copy():
    """Presentation only: the period, the session parenthetical and every line
    of the previous copy are still there, and no slot is left unfilled."""
    html = await _render_full()
    body = _visible_body(html)
    for text in (
        "Tu pago quedó confirmado",
        "Hola,",
        "Tu pago por el trabajo entregado de <strong>septiembre de 2026</strong> (8 sesiones)",
        "quedó confirmado.",
        "Gracias por tu labor. Tu trabajo hace posible lo que hacemos.",
        "Si tienes alguna duda sobre tu pago, responde a este correo y",
        "con gusto te apoyamos.",
        "Este correo fue enviado por <strong>Crea Tu Mundo</strong>",
        "Sitio web",
        "© Crea Tu Mundo. Todos los derechos reservados.",
        ">Crea Tu Mundo</a>",
    ):
        assert text in body, text
    assert not _SLOT.search(html), _SLOT.findall(html)


@pytest.mark.asyncio
async def test_crea_frame_is_inline_styles_only():
    """Mail clients strip <style>; every rule must sit on its element."""
    html = await _render_full()
    assert not _STYLE_TAG.search(html)
    assert 'class="' not in html


@pytest.mark.asyncio
async def test_crea_frame_drops_the_old_generic_palette():
    """No grey header, green box, generic link blue or old indigo."""
    html = (await _render_full()).lower()
    for old in ("#1f2937", "#ecfdf5", "#059669", "#065f46", "#2563eb", "#1a2a8f"):
        assert old not in html, old


@pytest.mark.asyncio
async def test_crea_frame_links_go_to_the_www_site():
    """The bare apex did not answer on 2026-09-28; the site is www."""
    html = await _render_full()
    assert "https://www.creatumundo.mx" in html
    assert 'href="https://creatumundo.mx"' not in html


@pytest.mark.asyncio
async def test_caller_cannot_restyle_the_frame():
    """The frame slots are set from the registry AFTER the caller's variables,
    so a same-named caller value never reaches the body."""
    html = await _render_full(
        header_bg="red", header_logo_url="https://evil.test/x.png", platform_url="https://evil.test"
    )
    assert "evil.test" not in html
    assert 'bgcolor="red"' not in html
    assert "background-color: red" not in html
    assert CTM_BRANDING["header_bg"] in html
