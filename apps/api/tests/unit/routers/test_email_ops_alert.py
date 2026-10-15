"""ops/alert: the generic operator alert other MADFAM services send through Janua.

First caller: nauta's worker, for an hourly probe of the fiscal edge ("unreadable",
then "recovered"). Pinned here:

- registration: HTML + text, subject `{asunto}`, values escaped, no default
  sender (the platform sender), one register-neutral variant;
- the variable contract;
- `detalle` is multi-line plain text: escaped line by line, newlines as `<br>`;
- the action link shows only for an https URL, with a neutral default label;
- the static copy carries no tú/usted marker.

Every value here is synthetic (example.com hosts).
"""

from __future__ import annotations

import html as html_lib
import importlib
import re
from email.utils import parseaddr
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

import app.services.resend_email_service as resend_module
from app.dependencies import verify_internal_api_key
from app.main import app
from app.routers.v1.email import (
    EMAIL_TEMPLATES,
    TEMPLATE_FILENAMES,
    TEMPLATE_FILENAMES_TU,
    TEXT_TEMPLATE_FILENAMES,
    TEXT_TEMPLATE_FILENAMES_TU,
    MissingTemplateVariablesError,
    _get_safe_template_path,
    _read_template_source,
    _read_text_template_source,
    has_register_variants,
    render_registered_template,
)
from app.routers.v1.email_ops_alert import DEFAULT_ACTION_LABEL, detalle_html
from app.services import resend_transport

email_module = importlib.import_module("app.routers.v1.email")

OPS = "ops/alert"
SEND_TEMPLATE_URL = "/api/v1/internal/email/send-template"
PREVIEW_URL = "/api/v1/internal/email/preview"
ACTION_URL = "https://nauta.example.com/ops/fiscal"
HOSTILE = 'A & B <img src=x onerror="alert(1)">'

#: Words that address the reader in tú or usted. The alert's own copy has none.
REGISTER_MARKERS = re.compile(
    r"\b(t[uú]|tus|te|ti|contigo|su|sus|usted|ustedes|le|les|"
    r"puedes|puede|tienes|eres|est[aá]s|revisa|revise|consulta|consulte|"
    r"responde|responda|recibes|recibe)\b",
    re.IGNORECASE,
)


@pytest.fixture()
def alert_variables() -> dict:
    """A complete alert: every required and optional variable."""
    return {
        "asunto": "[Nauta] El borde fiscal no se puede leer",
        "titulo": "El borde fiscal no se puede leer",
        "detalle": (
            "GET https://fiscal.example.com/health -> 503\n"
            "Último éxito: 15 de octubre de 2026, 12:00 (CDMX)\n"
            "Intentos fallidos consecutivos: 2"
        ),
        "servicio": "Nauta · worker",
        "ocurrio": "15 de octubre de 2026, 14:05 (CDMX)",
        "accion_url": ACTION_URL,
        "accion_texto": "Abrir el panel fiscal",
    }


def _required_only(variables: dict) -> dict:
    return {k: v for k, v in variables.items() if k in EMAIL_TEMPLATES[OPS]["required"]}


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


@pytest.fixture()
def no_stored_register(monkeypatch):
    lookup = AsyncMock(return_value=None)
    monkeypatch.setattr(email_module, "_stored_formality_for", lookup)
    return lookup


# =========================================================================== #
# Registration and contract
# =========================================================================== #
def test_ops_alert_is_registered_with_html_and_text_and_no_default_sender():
    entry = EMAIL_TEMPLATES[OPS]
    assert entry["subject"] == "{asunto}"
    assert entry["escape_html"] is True
    assert "default_from_email" not in entry and "default_from_name" not in entry
    assert "token_link" not in entry
    assert TEMPLATE_FILENAMES[OPS] == "ops_alert.html"
    assert TEXT_TEMPLATE_FILENAMES[OPS] == "ops_alert.txt"
    assert Path(_get_safe_template_path(OPS)).is_file()
    assert _read_text_template_source(OPS) is not None


def test_ops_alert_has_one_register_neutral_variant():
    assert OPS not in TEMPLATE_FILENAMES_TU and OPS not in TEXT_TEMPLATE_FILENAMES_TU
    assert "default_formality" not in EMAIL_TEMPLATES[OPS]
    assert "subject_tu" not in EMAIL_TEMPLATES[OPS]
    assert not has_register_variants(OPS)


def test_ops_alert_variable_contract():
    entry = EMAIL_TEMPLATES[OPS]
    assert entry["required"] == ["asunto", "titulo", "detalle", "servicio", "ocurrio"]
    assert entry["optional"] == ["accion_url", "accion_texto"]


# =========================================================================== #
# The message
# =========================================================================== #
@pytest.mark.asyncio
async def test_full_alert_renders_every_value_and_no_placeholder(alert_variables):
    r = await render_registered_template(OPS, alert_variables)
    assert r.subject == alert_variables["asunto"]
    assert r.text is not None
    assert "{{" not in r.html and "{{" not in r.text
    assert "<!--" not in r.html
    for key in ("titulo", "servicio", "ocurrio"):
        assert html_lib.escape(alert_variables[key], quote=True) in r.html, key
        assert alert_variables[key] in r.text, key
    assert alert_variables["detalle"] in r.text
    assert f'href="{ACTION_URL}"' in r.html
    assert "Abrir el panel fiscal" in r.html
    assert f"Abrir el panel fiscal: {ACTION_URL}" in r.text


@pytest.mark.asyncio
async def test_it_is_the_madfam_frame(alert_variables):
    r = await render_registered_template(OPS, alert_variables)
    assert 'src="https://madfam.io/assets/brand/email/madfam-logo-224.png"' in r.html
    for colour in ("#0A0E27", "#9B59B6", "#6BCB77", "#FFD93D"):
        assert colour in r.html, colour
    assert '<meta name="color-scheme" content="light">' in r.html
    assert 'width="600"' in r.html
    assert "Aviso operativo" in r.html and "Aviso operativo" in r.text
    assert "© " in r.html and " MADFAM" in r.text


@pytest.mark.asyncio
async def test_detalle_keeps_its_lines_in_html(alert_variables):
    r = await render_registered_template(OPS, alert_variables)
    assert (
        "GET https://fiscal.example.com/health -&gt; 503<br>\n"
        "Último éxito: 15 de octubre de 2026, 12:00 (CDMX)<br>\n"
        "Intentos fallidos consecutivos: 2"
    ) in r.html


@pytest.mark.asyncio
async def test_detalle_is_escaped_in_html_and_raw_in_text(alert_variables):
    detalle = f"primera línea\n{HOSTILE}\n<script>alert(1)</script>"
    r = await render_registered_template(OPS, {**alert_variables, "detalle": detalle})
    assert "<img src=x" not in r.html and "<script>" not in r.html
    assert html_lib.escape(HOSTILE, quote=True) in r.html
    assert (
        "primera línea<br>\n"
        f"{html_lib.escape(HOSTILE, quote=True)}<br>\n"
        "&lt;script&gt;alert(1)&lt;/script&gt;"
    ) in r.html
    assert detalle in r.text  # the text part is never escaped


@pytest.mark.parametrize(
    "raw, html",
    [
        ("una línea", "una línea"),
        ("a\r\nb\rc\nd", "a<br>\nb<br>\nc<br>\nd"),
        ("\n\nantes y después\n\n", "antes y después"),
        ("x < y\n", "x &lt; y"),
        ("", ""),
        (42, "42"),
    ],
)
def test_detalle_html(raw, html):
    assert detalle_html(raw) == html


@pytest.mark.asyncio
@pytest.mark.parametrize("key", ["titulo", "servicio", "ocurrio", "accion_texto"])
async def test_every_scalar_is_escaped_in_html(alert_variables, key):
    r = await render_registered_template(OPS, {**alert_variables, key: HOSTILE})
    assert "<img src=x" not in r.html
    assert html_lib.escape(HOSTILE, quote=True) in r.html
    assert HOSTILE in r.text


@pytest.mark.asyncio
async def test_a_caller_cannot_supply_the_composed_slots(alert_variables):
    r = await render_registered_template(
        OPS,
        {
            **_required_only(alert_variables),
            "detalle_html": "<b>inyectado</b>",
            "mostrar_accion": "1",
            "accion_href": "https://otro.example.com",
            "accion_etiqueta": "<b>otro</b>",
        },
    )
    assert "inyectado" not in r.html and "otro.example.com" not in r.html
    assert "<b>" not in r.html
    assert "Intentos fallidos consecutivos: 2" in r.html


# =========================================================================== #
# The optional action link
# =========================================================================== #
@pytest.mark.asyncio
async def test_without_an_action_there_is_no_button_and_no_link_line(alert_variables):
    r = await render_registered_template(OPS, _required_only(alert_variables))
    assert "{{" not in r.html and "{{" not in r.text
    assert "nauta.example.com" not in r.html and "nauta.example.com" not in r.text
    assert DEFAULT_ACTION_LABEL not in r.html and DEFAULT_ACTION_LABEL not in r.text
    assert 'target="_blank" style="display:inline-block' not in r.html
    # The text part closes cleanly: one blank line between the detail and the footer.
    assert "Intentos fallidos consecutivos: 2\n\n--\n" in r.text


@pytest.mark.asyncio
async def test_a_url_without_a_label_uses_the_neutral_default(alert_variables):
    variables = {**_required_only(alert_variables), "accion_url": ACTION_URL}
    r = await render_registered_template(OPS, variables)
    assert f'href="{ACTION_URL}"' in r.html and DEFAULT_ACTION_LABEL in r.html
    assert f"{DEFAULT_ACTION_LABEL}: {ACTION_URL}" in r.text


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "action",
    [
        {"accion_texto": "Abrir el panel"},  # a label without a URL
        {"accion_url": "", "accion_texto": "Abrir el panel"},
        {"accion_url": "http://nauta.example.com/ops", "accion_texto": "Abrir el panel"},
        {"accion_url": "javascript:alert(1)", "accion_texto": "Abrir el panel"},
        {"accion_url": "mailto:ops@example.com", "accion_texto": "Abrir el panel"},
        {"accion_url": 'https://nauta.example.com/"><b>', "accion_texto": "Abrir el panel"},
        {"accion_url": ["https://nauta.example.com"], "accion_texto": "Abrir el panel"},
    ],
)
async def test_an_unusable_action_renders_nothing(alert_variables, action):
    r = await render_registered_template(OPS, {**_required_only(alert_variables), **action})
    for body in (r.html, r.text):
        assert "Abrir el panel" not in body
        assert "nauta.example.com" not in body
        assert "javascript:" not in body and "mailto:" not in body
        assert "{{" not in body


# =========================================================================== #
# Register neutrality
# =========================================================================== #
def _visible_copy(source: str) -> str:
    """The template's own words: no style block, tags or placeholders."""
    source = re.sub(r"<style.*?</style>", " ", source, flags=re.DOTALL)
    source = re.sub(r"<title>.*?</title>", " ", source, flags=re.DOTALL)
    source = re.sub(r"<[^>]+>", " ", source)
    source = re.sub(r"\{\{[#/]?[A-Za-z_][A-Za-z0-9_]*\}\}", " ", source)
    return html_lib.unescape(source)


def test_the_static_copy_addresses_nobody():
    html_copy = _visible_copy(_read_template_source(OPS))
    text_copy = _visible_copy(_read_text_template_source(OPS))
    assert "Aviso operativo" in html_copy and "Detalle" in text_copy
    for copy in (html_copy, text_copy, DEFAULT_ACTION_LABEL):
        assert REGISTER_MARKERS.search(copy) is None, REGISTER_MARKERS.search(copy)


@pytest.mark.asyncio
@pytest.mark.parametrize("formality", ["tu", "usted"])
async def test_both_registers_render_the_same_message(alert_variables, formality):
    neutral = await render_registered_template(OPS, alert_variables)
    r = await render_registered_template(OPS, alert_variables, formality)
    assert (r.subject, r.html, r.text) == (neutral.subject, neutral.html, neutral.text)


# =========================================================================== #
# Enforcement and the wire
# =========================================================================== #
@pytest.mark.asyncio
@pytest.mark.parametrize("name", ["asunto", "titulo", "detalle", "servicio", "ocurrio"])
async def test_a_missing_required_variable_refuses_the_render(alert_variables, name):
    variables = dict(alert_variables)
    variables.pop(name)
    with pytest.raises(MissingTemplateVariablesError) as exc:
        await render_registered_template(OPS, variables)
    assert name in exc.value.missing


def _nauta_payload(variables: dict, **extra) -> dict:
    """The shape nauta's worker sends."""
    return {
        "to": ["operaciones@example.com"],
        "template": OPS,
        "variables": variables,
        "source_app": "nauta",
        "source_type": "notification",
        **extra,
    }


@pytest.mark.asyncio
async def test_send_template_sends_the_alert_from_the_platform_sender(
    sent, client, alert_variables, no_stored_register
):
    body = _nauta_payload(alert_variables, bcc=["guardia@example.com"])
    async with client as c:
        resp = await c.post(SEND_TEMPLATE_URL, json=body)
    assert resp.status_code == 200, resp.text
    assert resp.json()["success"] is True
    no_stored_register.assert_not_awaited()  # nothing to choose: one variant
    (params,) = sent
    assert params["subject"] == alert_variables["asunto"]
    assert params["bcc"] == ["guardia@example.com"]
    assert "Intentos fallidos consecutivos: 2" in params["text"]
    assert f'href="{ACTION_URL}"' in params["html"]
    _, from_address = parseaddr(params["from"])
    assert from_address.split("@", 1)[1] == "madfam.io"
    assert from_address.split("@", 1)[0] != "facturacion"


@pytest.mark.asyncio
async def test_send_template_names_a_missing_alert_variable(
    sent, client, alert_variables, no_stored_register
):
    variables = dict(alert_variables)
    variables.pop("ocurrio")
    async with client as c:
        resp = await c.post(SEND_TEMPLATE_URL, json=_nauta_payload(variables))
    assert resp.status_code == 400
    assert "ocurrio" in resp.json()["error"]["message"]
    assert sent == []


@pytest.mark.asyncio
async def test_preview_shows_what_a_send_carries(client, alert_variables):
    async with client as c:
        resp = await c.post(
            PREVIEW_URL, json={"kind": "template", "template": OPS, "context": alert_variables}
        )
    assert resp.status_code == 200, resp.text
    payload = resp.json()
    assert payload["subject"] == alert_variables["asunto"]
    assert "Intentos fallidos consecutivos: 2" in payload["text"]
