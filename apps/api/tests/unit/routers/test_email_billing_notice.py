"""billing/aviso-de-cobro and the register on /send-template.

Two things nauta sends to POST /api/v1/internal/email/send-template that janua
did not support before:

1. `formality` ("tu" | "usted"), the highest tier of the register precedence
   (request > the recipient's stored users.spanish_formality > the template's or
   product's voice > usted), and the tú variant of billing/cfdi it selects.
2. The monthly billing notice, billing/aviso-de-cobro: required scalars and
   lists, optional sections that vanish whole when their keys are absent, and
   every caller value escaped — inside the expanded list rows too.

Every person, company, address and amount here is synthetic.
"""

from __future__ import annotations

import html as html_lib
import importlib
import re
import uuid
from email.utils import parseaddr
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

import app.services.resend_email_service as resend_module
from app.dependencies import verify_internal_api_key
from app.main import app
from app.models import Base, User, UserStatus
from app.routers.v1.email import (
    EMAIL_TEMPLATES,
    TEMPLATE_FILENAMES,
    TEMPLATE_FILENAMES_TU,
    TEXT_TEMPLATE_FILENAMES,
    TEXT_TEMPLATE_FILENAMES_TU,
    InvalidTemplateVariablesError,
    MissingTemplateVariablesError,
    _get_safe_template_path,
    _read_template_source,
    _read_text_template_source,
    render_registered_template,
    resolve_template_formality,
    template_voice,
)
from app.routers.v1.email_billing_notice import _tile_row_sizes
from app.services import resend_transport
from app.services.user_lookup import AmbiguousEmailAcrossPools

# One way in for this module: CodeQL flags a module imported with both `import`
# and `from … import`, and the tests need the module object to patch it.
email_module = importlib.import_module("app.routers.v1.email")

AVISO = "billing/aviso-de-cobro"
CFDI = "billing/cfdi"
SEND_TEMPLATE_URL = "/api/v1/internal/email/send-template"
PREVIEW_URL = "/api/v1/internal/email/preview"
CTM_REDIRECT = "https://crea-map.madfam.io/portal/verify?next=/"
PLACEHOLDER = re.compile(r"\{\{\s*([A-Za-z_][A-Za-z0-9_]*)\s*\}\}")

OPTIONAL_HEADINGS = ("Lo que entregamos", "Lo que viene", "Lo que necesitamos de su parte")


def _required_only(variables: dict) -> dict:
    return {k: v for k, v in variables.items() if k in EMAIL_TEMPLATES[AVISO]["required"]}


@pytest.fixture()
def aviso_variables() -> dict:
    """A complete billing notice: every required and optional variable."""
    return {
        "asunto": "Aviso de cobro · octubre 2026",
        "preencabezado": "Total $23,200.00 · fecha de pago 10 de noviembre",
        "marca": "MADFAM",
        "etiqueta": "Aviso de cobro · octubre 2026",
        "titulo": "Su aviso de cobro de octubre",
        "saludo": "Hola, equipo de Cliente de Ejemplo:",
        "introduccion": "Le compartimos el resumen del mes.",
        "total": "$23,200.00",
        "moneda": "MXN",
        "total_nota": "IVA incluido",
        "periodo": "1 al 31 de octubre de 2026",
        "fecha_pago": "10 de noviembre de 2026",
        "factura_cuando": "Al confirmar su pago",
        "subtotal": "$20,000.00",
        "iva_etiqueta": "IVA 16%",
        "iva": "$3,200.00",
        "total_linea": "$23,200.00",
        "pago_titulo": "Cómo pagar",
        "pago_nota": "Use su número de cliente como referencia.",
        "factura_nota": "Emitimos el CFDI al confirmar el pago.",
        "cierre": "Gracias por su confianza.",
        "firma_nombre": "Persona Sintética",
        "firma_cargo": "Asesoría vCTO",
        "pie": "Recibe este aviso porque es cliente de MADFAM.",
        "pie_nota": "Cuernavaca, Morelos, México",
        "conceptos": [
            {"concepto": "Acompañamiento vCTO", "detalle": "Octubre 2026", "monto": "$20,000.00"}
        ],
        "pago_datos": [
            {"etiqueta": "Banco", "valor": "Banco de Ejemplo"},
            {"etiqueta": "CLABE", "valor": "000000000000000000"},
        ],
        "fecha_pago_nota": "Antes de las 18:00",
        "cta_comprobante_etiqueta": "Enviar comprobante",
        "cta_comprobante_url": "mailto:pagos@example.com?subject=Comprobante",
        "entregado_titulo": "Lo que entregamos",
        "entregado_periodo": "Octubre 2026",
        "entregado_destacados": [
            {"valor": "12", "etiqueta": "tareas cerradas"},
            {"valor": "3", "etiqueta": "despliegues"},
        ],
        "entregado": [
            {"titulo": "Migración de base de datos", "detalle": "Sin tiempo fuera"},
            {"titulo": "Revisión de seguridad"},
        ],
        "viene_titulo": "Lo que viene",
        "viene": [{"cuando": "Semana 1", "que": "Plan de noviembre"}],
        "acciones_titulo": "Lo que necesitamos de su parte",
        "acciones": [{"titulo": "Aprobar el plan", "detalle": "Antes del día 5"}],
        "acciones_enlace_etiqueta": "Abrir el portal",
        "acciones_enlace_url": "https://portal.example.com/acciones",
        "estado_cuenta_etiqueta": "Ver estado de cuenta",
        "estado_cuenta_url": "https://portal.example.com/estado",
    }


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
    """No recipient has a stored register (and no database is touched)."""
    lookup = AsyncMock(return_value=None)
    monkeypatch.setattr(email_module, "_stored_formality_for", lookup)
    return lookup


# =========================================================================== #
# billing/aviso-de-cobro: registration and contract
# =========================================================================== #
def test_aviso_is_registered_with_html_and_text_and_no_default_sender():
    entry = EMAIL_TEMPLATES[AVISO]
    assert entry["subject"] == "{asunto}"
    assert entry["escape_html"] is True
    assert "default_from_email" not in entry and "default_from_name" not in entry
    assert Path(_get_safe_template_path(AVISO)).is_file()
    assert TEMPLATE_FILENAMES[AVISO] == "billing_aviso-de-cobro.html"
    assert TEXT_TEMPLATE_FILENAMES[AVISO] == "billing_aviso-de-cobro.txt"
    assert AVISO not in TEMPLATE_FILENAMES_TU  # one register-neutral variant


def test_aviso_variable_contract_matches_nauta():
    entry = EMAIL_TEMPLATES[AVISO]
    assert set(entry["required"]) == {
        "asunto", "preencabezado", "marca", "etiqueta", "titulo", "saludo",
        "introduccion", "total", "moneda", "total_nota", "periodo", "fecha_pago",
        "factura_cuando", "subtotal", "iva_etiqueta", "iva", "total_linea",
        "pago_titulo", "pago_nota", "factura_nota", "cierre", "firma_nombre",
        "firma_cargo", "pie", "pie_nota", "conceptos", "pago_datos",
    }  # fmt: skip
    assert set(entry["optional"]) == {
        "fecha_pago_nota", "cta_comprobante_etiqueta", "cta_comprobante_url",
        "entregado_titulo", "entregado_periodo", "viene_titulo", "acciones_titulo",
        "acciones_enlace_etiqueta", "acciones_enlace_url", "estado_cuenta_etiqueta",
        "estado_cuenta_url", "entregado_destacados", "entregado", "viene", "acciones",
    }  # fmt: skip


@pytest.mark.asyncio
async def test_full_notice_renders_every_value_and_no_placeholder(aviso_variables):
    r = await render_registered_template(AVISO, aviso_variables)
    assert r.subject == "Aviso de cobro · octubre 2026"
    assert "{{" not in r.html and "{{" not in r.text
    for key, value in aviso_variables.items():
        if isinstance(value, str) and not key.endswith("_url"):
            assert html_lib.escape(value, quote=True) in r.html, key
            if key != "preencabezado":  # the inbox preview line is HTML-only
                assert value in r.text, key
    for heading in OPTIONAL_HEADINGS:
        assert heading in r.html and heading in r.text
    assert "Banco de Ejemplo" in r.html and "CLABE: 000000000000000000" in r.text
    assert 'href="https://portal.example.com/estado"' in r.html
    assert "mailto:pagos@example.com?subject=Comprobante" in r.text


@pytest.mark.asyncio
async def test_it_is_the_madfam_billing_design(aviso_variables):
    r = await render_registered_template(AVISO, aviso_variables)
    assert 'src="https://madfam.io/assets/brand/email/madfam-logo-224.png"' in r.html
    assert 'width="64"' in r.html and "width:64px" in r.html
    for colour in ("#0A0E27", "#9B59B6", "#6BCB77", "#FFD93D"):
        assert colour in r.html, colour
    assert '<meta name="color-scheme" content="light">' in r.html
    assert 'width="600"' in r.html
    # The phone layout stacks the three summary columns.
    assert "max-width: 620px" in r.html and ".mf-col { display: block !important" in r.html
    assert r.html.count('class="mf-col mf-summary"') == 3
    assert "<!--" not in r.html


# --------------------------------------------------------------- enforcement
@pytest.mark.asyncio
@pytest.mark.parametrize("name", ["total", "pie_nota", "conceptos", "pago_datos"])
async def test_a_missing_required_variable_refuses_the_render(aviso_variables, name):
    variables = dict(aviso_variables)
    variables.pop(name)
    with pytest.raises(MissingTemplateVariablesError) as exc:
        await render_registered_template(AVISO, variables)
    assert name in exc.value.missing


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "overrides, problem",
    [
        ({"conceptos": []}, "conceptos"),
        ({"conceptos": "una línea"}, "conceptos"),
        ({"pago_datos": [{"etiqueta": "CLABE"}]}, "pago_datos[0].valor"),
        ({"conceptos": [{"concepto": "X", "monto": "  "}]}, "conceptos[0].monto"),
        ({"conceptos": ["X"]}, "conceptos[0]"),
        ({"viene": {"cuando": "hoy"}}, "viene"),
        ({"acciones": [{"titulo": "Aprobar", "detalle": {"x": 1}}]}, "acciones[0].detalle"),
    ],
)
async def test_lists_that_break_their_item_shape_are_refused(aviso_variables, overrides, problem):
    with pytest.raises(InvalidTemplateVariablesError) as exc:
        await render_registered_template(AVISO, {**aviso_variables, **overrides})
    assert problem in exc.value.missing


@pytest.mark.asyncio
async def test_an_optional_list_may_be_empty_and_secondary_keys_may_be_absent(aviso_variables):
    variables = {**aviso_variables, "viene": [], "conceptos": [{"concepto": "X", "monto": "$1"}]}
    r = await render_registered_template(AVISO, variables)
    assert "Lo que viene" not in r.html


# ------------------------------------------------------------ optional parts
@pytest.mark.asyncio
async def test_required_only_notice_has_no_optional_section_heading_or_placeholder(
    aviso_variables,
):
    r = await render_registered_template(AVISO, _required_only(aviso_variables))
    assert "{{" not in r.html and "{{" not in r.text
    for absent in OPTIONAL_HEADINGS + (
        "Enviar comprobante",
        "Ver estado de cuenta",
        "Abrir el portal",
        "Antes de las 18:00",
        "&#10003;",
        'class="mf-col mf-tile"',
    ):
        assert absent not in r.html, absent
        assert absent not in r.text, absent
    # The required parts are all there.
    assert "Acompañamiento vCTO" in r.html and "Cómo pagar" in r.html


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "keep, gone",
    [
        # A heading without its list, or a list without its heading, is not a section.
        ({"entregado_titulo": "Lo que entregamos"}, "Lo que entregamos"),
        ({"entregado": [{"titulo": "Revisión de seguridad"}]}, "Revisión de seguridad"),
        ({"viene_titulo": "Lo que viene"}, "Lo que viene"),
        ({"viene": [{"cuando": "Semana 1", "que": "Plan"}]}, "Semana 1"),
        ({"acciones_titulo": "Pendientes"}, "Pendientes"),
        # A link needs both its label and a safe URL.
        ({"estado_cuenta_etiqueta": "Ver estado de cuenta"}, "Ver estado de cuenta"),
        ({"cta_comprobante_url": "https://portal.example.com/x"}, "portal.example.com/x"),
        (
            {"cta_comprobante_etiqueta": "Enviar", "cta_comprobante_url": "javascript:alert(1)"},
            "javascript:",
        ),
        (
            {"estado_cuenta_etiqueta": "Estado", "estado_cuenta_url": "http://portal.example.com"},
            "http://portal.example.com",
        ),
    ],
)
async def test_a_partial_optional_section_renders_nothing(aviso_variables, keep, gone):
    r = await render_registered_template(AVISO, {**_required_only(aviso_variables), **keep})
    assert gone not in r.html
    assert gone not in r.text
    assert "{{" not in r.html and "{{" not in r.text


@pytest.mark.asyncio
async def test_the_delivered_section_shows_whichever_parts_it_has(aviso_variables):
    base = {**_required_only(aviso_variables), "entregado_titulo": "Lo que entregamos"}
    tiles = await render_registered_template(
        AVISO, {**base, "entregado_destacados": aviso_variables["entregado_destacados"]}
    )
    assert "Lo que entregamos" in tiles.html and "tareas cerradas" in tiles.html
    assert "&#10003;" not in tiles.html
    checklist = await render_registered_template(
        AVISO, {**base, "entregado": aviso_variables["entregado"]}
    )
    assert "Revisión de seguridad" in checklist.html
    assert 'class="mf-col mf-tile"' not in checklist.html


@pytest.mark.parametrize(
    "count, sizes", [(1, [1]), (3, [3]), (4, [2, 2]), (5, [3, 2]), (7, [3, 2, 2])]
)
def test_tiles_are_laid_out_in_balanced_rows(count, sizes):
    assert _tile_row_sizes(count) == sizes


# ------------------------------------------------------------------- escaping
HOSTILE = 'A & B <img src=x onerror="alert(1)">'


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "overrides",
    [
        {"titulo": HOSTILE},
        {"pie_nota": HOSTILE},
        {"conceptos": [{"concepto": HOSTILE, "detalle": HOSTILE, "monto": HOSTILE}]},
        {"pago_datos": [{"etiqueta": HOSTILE, "valor": HOSTILE}]},
        {"entregado_destacados": [{"valor": HOSTILE, "etiqueta": HOSTILE}]},
        {"entregado": [{"titulo": HOSTILE, "detalle": HOSTILE}]},
        {"viene": [{"cuando": HOSTILE, "que": HOSTILE}]},
        {"acciones": [{"titulo": HOSTILE, "detalle": HOSTILE}]},
        {"acciones_titulo": HOSTILE, "estado_cuenta_etiqueta": HOSTILE},
    ],
)
async def test_every_value_is_escaped_in_html_including_list_rows(aviso_variables, overrides):
    r = await render_registered_template(AVISO, {**aviso_variables, **overrides})
    assert "<img src=x" not in r.html
    assert html_lib.escape(HOSTILE, quote=True) in r.html
    assert HOSTILE in r.text  # the text part is never escaped


@pytest.mark.asyncio
async def test_a_caller_cannot_supply_the_composed_rows(aviso_variables):
    r = await render_registered_template(
        AVISO,
        {**aviso_variables, "conceptos_filas": "<b>inyectado</b>", "mostrar_viene": ""},
    )
    assert "inyectado" not in r.html
    assert "Lo que viene" in r.html  # the derived flag, not the caller's, decides


@pytest.mark.asyncio
async def test_a_link_with_quotes_never_breaks_out_of_its_attribute(aviso_variables):
    r = await render_registered_template(
        AVISO, {**aviso_variables, "estado_cuenta_url": 'https://x.example.com/"><b>'}
    )
    assert "Ver estado de cuenta" not in r.html


# =========================================================================== #
# The register: billing/cfdi's two variants
# =========================================================================== #
def _placeholders(source: str) -> set:
    return set(PLACEHOLDER.findall(source))


def test_cfdi_variants_use_exactly_the_same_placeholders():
    assert _placeholders(_read_template_source(CFDI)) == _placeholders(
        _read_template_source(CFDI, "tu")
    )
    assert _placeholders(_read_text_template_source(CFDI)) == _placeholders(
        _read_text_template_source(CFDI, "tu")
    )
    assert TEMPLATE_FILENAMES_TU[CFDI] == "billing_cfdi_tu.html"
    assert TEXT_TEMPLATE_FILENAMES_TU[CFDI] == "billing_cfdi_tu.txt"


USTED_MARKERS = ("Le enviamos", "Conserve el archivo", "Responda a este correo", "su portal")
TU_MARKERS = ("Te enviamos", "Conserva el archivo", "Responde a este correo", "tu portal")
PORTAL = "https://erp.ejemplo.mx/facturas"


@pytest.mark.asyncio
async def test_the_tu_variant_of_cfdi(cfdi_variables):
    r = await render_registered_template(CFDI, {**cfdi_variables, "portal_url": PORTAL}, "tu")
    assert r.formality == "tu"
    assert r.subject.startswith("Tu CFDI F4 de MADFAM")
    assert (
        "Tu comprobante fiscal (CFDI)" in r.html and "Hola, equipo de Cliente de Ejemplo:" in r.html
    )
    assert "Recibes este correo porque eres cliente de MADFAM" in r.html
    for marker in TU_MARKERS:
        assert marker in r.html and marker in r.text, marker
    for marker in USTED_MARKERS:
        assert marker not in r.html and marker not in r.text, marker
    assert "{{" not in r.html and "{{" not in r.text


@pytest.mark.asyncio
async def test_the_usted_variant_of_cfdi_is_unchanged(cfdi_variables):
    r = await render_registered_template(CFDI, {**cfdi_variables, "portal_url": PORTAL}, "usted")
    default = await render_registered_template(CFDI, {**cfdi_variables, "portal_url": PORTAL})
    assert r.html == default.html and r.subject == default.subject
    assert r.formality == "usted"
    assert r.subject.startswith("Su CFDI F4 de MADFAM")
    for marker in USTED_MARKERS:
        assert marker in r.html and marker in r.text, marker
    for marker in TU_MARKERS:
        assert marker not in r.html and marker not in r.text, marker


# =========================================================================== #
# The register: precedence
# =========================================================================== #
@pytest.mark.parametrize(
    "requested, stored, expected",
    [
        ("tu", None, "tu"),
        ("usted", "tu", "usted"),  # the request outranks the reader
        (None, "tu", "tu"),  # the reader outranks the template's voice
        (None, None, "usted"),  # the template's voice
    ],
)
def test_precedence_for_cfdi(requested, stored, expected):
    assert resolve_template_formality(CFDI, requested, stored) == expected


def test_cfdi_keeps_madfams_voice_on_a_tu_product_host():
    """billing/cfdi is MADFAM's fiscal mail; a CTM host must not make it tú."""
    assert template_voice(CFDI, redirect_url=CTM_REDIRECT) == "usted"
    assert resolve_template_formality(CFDI, redirect_url=CTM_REDIRECT) == "usted"


def test_a_template_without_a_declared_voice_takes_the_products():
    assert template_voice(AVISO, redirect_url=CTM_REDIRECT) == "tu"
    assert template_voice(AVISO) == "usted"


def _send_body(template: str, variables: dict, **extra) -> dict:
    return {
        "to": ["cliente@example.com"],
        "template": template,
        "variables": variables,
        "source_app": "nauta",
        "source_type": "billing",
        **extra,
    }


@pytest.mark.asyncio
async def test_send_template_honours_the_requested_register(
    sent, client, cfdi_variables, no_stored_register
):
    async with client as c:
        tu = await c.post(SEND_TEMPLATE_URL, json=_send_body(CFDI, cfdi_variables, formality="tu"))
        usted = await c.post(
            SEND_TEMPLATE_URL, json=_send_body(CFDI, cfdi_variables, formality="usted")
        )
    assert tu.status_code == 200 and usted.status_code == 200, (tu.text, usted.text)
    assert sent[0]["subject"].startswith("Tu CFDI") and "Te enviamos" in sent[0]["text"]
    assert sent[1]["subject"].startswith("Su CFDI") and "Le enviamos" in sent[1]["text"]
    # The request named a register, so nobody's stored one was looked up.
    no_stored_register.assert_not_awaited()


@pytest.mark.asyncio
async def test_send_template_reads_each_recipients_stored_register(
    sent, client, cfdi_variables, monkeypatch
):
    stored = {"tu@example.com": "tu", "nadie@example.com": None}

    async def lookup(email, org_id):
        return stored[email]

    monkeypatch.setattr(email_module, "_stored_formality_for", lookup)
    body = _send_body(CFDI, cfdi_variables, to=["tu@example.com", "nadie@example.com"])
    async with client as c:
        resp = await c.post(SEND_TEMPLATE_URL, json=body)
    assert resp.status_code == 200, resp.text
    by_recipient = {p["to"][0] if isinstance(p["to"], list) else p["to"]: p for p in sent}
    assert by_recipient["tu@example.com"]["subject"].startswith("Tu CFDI")
    assert by_recipient["nadie@example.com"]["subject"].startswith("Su CFDI")


@pytest.mark.asyncio
async def test_the_request_outranks_a_stored_register(sent, client, cfdi_variables, monkeypatch):
    monkeypatch.setattr(email_module, "_stored_formality_for", AsyncMock(return_value="tu"))
    async with client as c:
        resp = await c.post(
            SEND_TEMPLATE_URL, json=_send_body(CFDI, cfdi_variables, formality="usted")
        )
    assert resp.status_code == 200
    assert sent[0]["subject"].startswith("Su CFDI")


@pytest.mark.asyncio
async def test_a_tu_product_host_does_not_change_cfdi(
    sent, client, cfdi_variables, no_stored_register
):
    async with client as c:
        resp = await c.post(
            SEND_TEMPLATE_URL, json=_send_body(CFDI, cfdi_variables, redirect_url=CTM_REDIRECT)
        )
    assert resp.status_code == 200
    assert sent[0]["subject"].startswith("Su CFDI")


@pytest.mark.asyncio
@pytest.mark.parametrize("bad", ["tú", "TU", "vosotros", "", 1])
async def test_send_template_refuses_an_unsupported_register(
    sent, client, cfdi_variables, no_stored_register, bad
):
    async with client as c:
        resp = await c.post(SEND_TEMPLATE_URL, json=_send_body(CFDI, cfdi_variables, formality=bad))
    assert resp.status_code == 422
    assert sent == []


@pytest.mark.asyncio
async def test_a_template_the_register_cannot_change_never_looks_it_up(
    sent, client, aviso_variables, no_stored_register
):
    async with client as c:
        resp = await c.post(SEND_TEMPLATE_URL, json=_send_body(AVISO, aviso_variables))
    assert resp.status_code == 200, resp.text
    no_stored_register.assert_not_awaited()
    params = sent[0]
    assert params["subject"] == "Aviso de cobro · octubre 2026"
    assert "Acompañamiento vCTO" in params["html"] and "Acompañamiento vCTO" in params["text"]
    # No default sender: the platform sender, never the fiscal mailbox.
    _, from_address = parseaddr(params["from"])
    assert from_address.split("@", 1)[1] == "madfam.io"
    assert from_address.split("@", 1)[0] != "facturacion"


@pytest.mark.asyncio
async def test_send_template_names_a_broken_list(sent, client, aviso_variables, no_stored_register):
    body = _send_body(AVISO, {**aviso_variables, "pago_datos": [{"etiqueta": "CLABE"}]})
    async with client as c:
        resp = await c.post(SEND_TEMPLATE_URL, json=body)
    assert resp.status_code == 400
    assert "pago_datos[0].valor" in resp.json()["error"]["message"]
    assert sent == []


@pytest.mark.asyncio
async def test_preview_renders_the_requested_register(client, cfdi_variables):
    async with client as c:
        resp = await c.post(
            PREVIEW_URL,
            json={
                "kind": "template",
                "template": CFDI,
                "context": cfdi_variables,
                "formality": "tu",
            },
        )
    assert resp.status_code == 200, resp.text
    assert resp.json()["subject"].startswith("Tu CFDI")
    assert "Te enviamos" in resp.json()["text"]


# =========================================================================== #
# The person tier's lookup
# =========================================================================== #
@pytest.fixture()
async def user_db(monkeypatch):
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    monkeypatch.setattr(email_module, "AsyncSessionLocal", factory)
    yield factory
    await engine.dispose()


async def _add(factory, email, formality):
    async with factory() as session:
        session.add(
            User(
                id=uuid.uuid4(),
                email=email,
                status=UserStatus.ACTIVE,
                spanish_formality=formality,
                user_metadata={},
            )
        )
        await session.commit()


@pytest.mark.asyncio
async def test_the_lookup_reads_the_stored_register(user_db):
    await _add(user_db, "persona@example.com", "tu")
    await _add(user_db, "sin-respuesta@example.com", None)
    assert await email_module._stored_formality_for("persona@example.com", None) == "tu"
    assert await email_module._stored_formality_for("Persona@Example.com", None) == "tu"
    assert await email_module._stored_formality_for("sin-respuesta@example.com", None) is None
    assert await email_module._stored_formality_for("nadie@example.com", None) is None


@pytest.mark.asyncio
async def test_an_ambiguous_address_or_a_database_error_never_blocks(user_db, monkeypatch):
    # SQLite cannot hold one address in two pools (it drops migration 013's
    # partial-index predicate), so the resolver's refusal is simulated.
    async def ambiguous(*_args, **_kwargs):
        raise AmbiguousEmailAcrossPools("compartido@example.com", 2)

    monkeypatch.setattr(email_module, "resolve_user_by_email_across_pools", ambiguous)
    assert await email_module._stored_formality_for("compartido@example.com", None) is None

    def broken():
        raise RuntimeError("database down")

    monkeypatch.setattr(email_module, "AsyncSessionLocal", broken)
    assert await email_module._stored_formality_for("persona@example.com", None) is None
