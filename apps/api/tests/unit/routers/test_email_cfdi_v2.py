"""billing/cfdi v2: the CFDI email a client receives, and the renderer's guards.

The first real send (CTM Ciclo 2, 2026-09-24) reached the client with:
- a literal ``{{rfc_receptor}}`` (optional, never passed, left in by the naive
  renderer);
- a total of ``19000.00``;
- the tú register and no MADFAM branding;
- maintainer comments in the HTML source.

These tests pin what replaced it:

- a complete, formal (usted), MADFAM-branded message;
- caller values escaped in HTML;
- a plain-text part and a reply-to on the wire;
- a renderer that REFUSES to send any placeholder nothing fills, and blanks
  declared optionals instead of leaking them, for every template.
"""

from __future__ import annotations

import html as html_lib
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest
from httpx import ASGITransport, AsyncClient

import app.routers.v1.email as email_module
import app.services.resend_email_service as resend_module
from app.dependencies import verify_internal_api_key
from app.main import app
from app.routers.v1.email import (
    EMAIL_TEMPLATES,
    MissingTemplateVariablesError,
    UnresolvedTemplateVariablesError,
    render_registered_template,
)
from app.services import resend_transport

SEND_TEMPLATE_URL = "/api/v1/internal/email/send-template"
PREVIEW_URL = "/api/v1/internal/email/preview"
PORTAL = "https://erp.ejemplo.mx/facturas"


@pytest.fixture()
def client():
    app.dependency_overrides[verify_internal_api_key] = lambda: True
    yield AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
    app.dependency_overrides.pop(verify_internal_api_key, None)


@pytest.fixture()
def sent(monkeypatch):
    """Enable the real Resend send path and record each SDK params dict."""
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


async def _render(variables):
    return await render_registered_template("billing/cfdi", variables)


# --------------------------------------------------------------------------- #
# The message
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_every_value_lands_and_no_placeholder_survives(cfdi_variables):
    r = await _render({**cfdi_variables, "portal_url": PORTAL})
    assert "{{" not in r.html
    assert r.text is not None and "{{" not in r.text
    for key, value in cfdi_variables.items():
        assert html_lib.escape(value, quote=True) in r.html, key
        assert value in r.text, key
    assert r.subject == "Su CFDI F4 de MADFAM — 16 de septiembre de 2026 a 15 de octubre de 2026"


@pytest.mark.asyncio
async def test_it_is_madfam_branded_formal_and_clean(cfdi_variables):
    r = await _render(cfdi_variables)
    # Logo as a hosted PNG (no SVG in email) plus a live-text wordmark.
    assert 'src="https://madfam.io/assets/brand/email/madfam-logo-112.png"' in r.html
    assert 'alt="MADFAM"' in r.html
    for colour in ("#2c8136", "#58326f", "#eebc15"):  # the logo's green, purple, gold
        assert colour in r.html
    # usted, addressed to the team, never the tú of v1.
    assert "Estimado equipo de Cliente de Ejemplo:" in r.html
    assert "Responda a este correo" in r.html
    for informal in ("Hola", "Tu CFDI", "tu comprobante", "Encontrarás", "responde a este"):
        assert informal not in r.html and informal not in r.text, informal
    # Fiscal footer, privacy notice, a real year; no maintainer comments.
    assert "https://madfam.io/es/privacy" in r.html
    years = {datetime.now(ZoneInfo("America/Mexico_City")).year + d for d in (-1, 0)}
    assert any(f"© {y} MADFAM" in r.html for y in years)
    assert "<!--" not in r.html
    # The SAT link survives as a proper attribute.
    href = html_lib.escape(cfdi_variables["verificacion_url"], quote=True)
    assert f'href="{href}"' in r.html
    assert cfdi_variables["verificacion_url"] in r.text


@pytest.mark.asyncio
async def test_caller_values_are_escaped_in_html_but_not_in_text(cfdi_variables):
    hostile = 'A & B <img src=x onerror="alert(1)">'
    r = await _render({**cfdi_variables, "receptor_nombre": hostile})
    assert "<img src=x" not in r.html
    assert html_lib.escape(hostile, quote=True) in r.html
    assert hostile in r.text


@pytest.mark.asyncio
async def test_the_portal_row_appears_only_for_a_safe_https_url(cfdi_variables):
    with_portal = await _render({**cfdi_variables, "portal_url": PORTAL})
    assert f'href="{PORTAL}"' in with_portal.html
    assert PORTAL in with_portal.text

    without = await _render(cfdi_variables)
    assert "su portal" not in without.html and "su portal" not in without.text

    for bad in ("http://erp.ejemplo.mx/facturas", "javascript:alert(1)", 'https://x.mx/"><b>'):
        r = await _render({**cfdi_variables, "portal_url": bad})
        assert "su portal" not in r.html, bad


# --------------------------------------------------------------------------- #
# The renderer's guards
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_the_first_real_payload_is_refused_naming_what_is_missing(cfdi_variables):
    # Exactly the four variables nauta sent on 2026-09-24.
    v1 = {k: cfdi_variables[k] for k in ("cliente_nombre", "folio_fiscal", "periodo", "total")}
    with pytest.raises(MissingTemplateVariablesError) as exc:
        await _render(v1)
    assert "rfc_receptor" in exc.value.missing


@pytest.mark.asyncio
async def test_a_placeholder_nothing_fills_refuses_the_render(cfdi_variables, monkeypatch):
    monkeypatch.setattr(
        email_module, "_read_text_template_source", lambda _tid: "Total {{total}} {{desconocido}}"
    )
    with pytest.raises(UnresolvedTemplateVariablesError) as exc:
        await _render(cfdi_variables)
    assert exc.value.missing == ["desconocido"]


@pytest.mark.asyncio
async def test_braces_inside_a_value_never_trip_the_guard(cfdi_variables):
    r = await _render({**cfdi_variables, "cliente_nombre": "Equipo {{no-es-plantilla}}"})
    assert "Equipo {{no-es-plantilla}}" in r.text


@pytest.mark.asyncio
@pytest.mark.parametrize("template_id", sorted(EMAIL_TEMPLATES))
async def test_every_template_renders_with_its_required_vars_and_leaks_nothing(template_id):
    entry = EMAIL_TEMPLATES[template_id]
    variables = {name: f"valor-{name}" for name in entry["required"]}
    r = await render_registered_template(template_id, variables)
    assert "{{" not in r.html, template_id
    assert r.text is None or "{{" not in r.text, template_id


# --------------------------------------------------------------------------- #
# The wire
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_send_template_carries_text_part_and_reply_to(sent, client, cfdi_variables):
    body = {
        "to": ["cliente@example.com"],
        "template": "billing/cfdi",
        "variables": {**cfdi_variables, "portal_url": PORTAL},
        "reply_to": "asesor@madfam.io",
        "source_app": "nauta",
        "source_type": "billing",
    }
    async with client as c:
        resp = await c.post(SEND_TEMPLATE_URL, json=body)
    assert resp.status_code == 200, resp.text
    params = sent[0]
    assert params["reply_to"] == "asesor@madfam.io"
    assert "Folio fiscal (UUID): 11111111-2222-4333-8444-555555555555" in params["text"]
    assert "madfam-logo-112.png" in params["html"]
    assert "facturacion@madfam.io" in params["from"]


@pytest.mark.asyncio
async def test_send_template_answers_400_naming_an_unfilled_placeholder(
    sent, client, cfdi_variables, monkeypatch
):
    monkeypatch.setattr(email_module, "_read_text_template_source", lambda _tid: "{{desconocido}}")
    body = {
        "to": ["cliente@example.com"],
        "template": "billing/cfdi",
        "variables": cfdi_variables,
        "source_app": "nauta",
    }
    async with client as c:
        resp = await c.post(SEND_TEMPLATE_URL, json=body)
    assert resp.status_code == 400
    assert "desconocido" in resp.json()["error"]["message"]
    assert sent == []  # nothing left


@pytest.mark.asyncio
async def test_preview_shows_the_same_text_part_a_send_carries(client, cfdi_variables):
    async with client as c:
        resp = await c.post(
            PREVIEW_URL,
            json={"kind": "template", "template": "billing/cfdi", "context": cfdi_variables},
        )
    assert resp.status_code == 200, resp.text
    assert "Serie y folio: F4" in resp.json()["text"]
