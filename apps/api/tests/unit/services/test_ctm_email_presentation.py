"""Render-only CTM proof. Never invoke a send method, route, or provider."""

import ast
import re
from html.parser import HTMLParser
from pathlib import Path

import pytest

from app.services.email_branding import CTM_BRANDING, CTM_ORG_ID, resolve_branding
from app.services.email_i18n import build_email_environment
from app.services.email_presentation import KINDS, render_auth_preview, render_ctm_email
from app.services.email_service import EmailService
from app.services.resend_email_service import ResendEmailService

API = Path(__file__).resolve().parents[3]
ENV = build_email_environment(API / "app/templates/email")
URL = "https://example.invalid/access?token=synthetic-never-valid&next=%2Fsynthetic"
DATA = {
    **CTM_BRANDING,
    "user_name": "Persona sintética <img src=x onerror=alert(1)> ÁÉ",
    "magic_link": URL,
    "magic_url": URL,
    "reset_link": URL,
    "reset_url": URL,
    "verification_link": URL,
    "verification_url": URL,
    "dashboard_link": URL,
    "dashboard_url": URL,
    "invitation_url": URL,
    "inviter_name": "Equipo sintético <b>",
    "organization_name": "Espacio sintético & ejemplo",
    "role": "Integrante",
    "expires_at": "fecha sintética de vigencia",
    "recovery_url": URL,
    "recovery_code": "TEMP-SYNTHETIC",
    "backup_codes": ["NEVER-RENDER-BACKUP"],
    "amount": "NEVER-RENDER-MONEY",
    "clinical_history": "NEVER-RENDER-CLINICAL",
}


class Tags(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.tags = []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))


@pytest.mark.parametrize("kind", sorted(KINDS))
@pytest.mark.parametrize("locale,formality", [("es", "tu"), ("es", "usted"), ("en", "tu")])
def test_ctm_html_text_and_real_render_seams(kind, locale, formality):
    html = render_ctm_email(ENV, kind + ".html", DATA, locale, formality)
    text = render_ctm_email(ENV, kind + ".txt", DATA, locale, formality)
    assert html == EmailService()._render_template(kind + ".html", DATA, locale, formality)
    assert text == EmailService()._render_template(kind + ".txt", DATA, locale, formality)
    resend = ResendEmailService()
    assert html == resend._render_template(
        kind + ".html", {**DATA, "locale": locale, "formality": formality}
    )
    assert "Crea Tu Mundo" in html and "MADFAM" in html
    assert "<img src=x" not in html
    assert "&lt;img src=x" in html
    assert URL in text and "&amp;next=" not in text
    assert all(
        marker not in html + text
        for marker in ("NEVER-RENDER-BACKUP", "NEVER-RENDER-MONEY", "NEVER-RENDER-CLINICAL")
    )
    tags = Tags(html).tags
    assert len([tag for tag, _ in tags if tag == "h1"]) == 1
    assert all(attrs.get("role") == "presentation" for tag, attrs in tags if tag == "table")
    assert not any(tag in {"script", "form", "style", "link"} for tag, _ in tags)
    assert not any("opacity" in attrs.get("style", "") for _, attrs in tags)
    assert "<!--" not in html
    preheader = re.search(r'<div data-preheader="true"[^>]*>(.*?)</div>', html).group(1)
    assert preheader
    assert not any(
        value in preheader
        for value in (DATA["user_name"], DATA["recovery_code"], URL, "token=", "minutes", "minutos")
    )
    changed_private_data = {
        **DATA,
        "user_name": "OTRA-PERSONA",
        "recovery_code": "OTRO-CODIGO",
        "magic_link": URL + "-otro",
    }
    other = render_ctm_email(ENV, kind + ".html", changed_private_data, locale, formality)
    assert preheader == re.search(r'<div data-preheader="true"[^>]*>(.*?)</div>', other).group(1)


def test_known_expiries_are_copy_only_and_not_guessed_for_recovery():
    magic = render_ctm_email(ENV, "magic_link.txt", DATA, "es", "tu")
    reset = render_ctm_email(ENV, "password_reset.txt", DATA, "es", "tu")
    verify = render_ctm_email(
        ENV, "verification.txt", {**DATA, "verification_expiry_hours": 48}, "es", "tu"
    )
    assert "15 minutos" in magic and "una sola vez" in magic
    assert "1 hora" in reset
    assert "48 horas" in verify
    recovery = render_ctm_email(
        ENV, "mfa_recovery.html", {**CTM_BRANDING, "backup_codes": DATA["backup_codes"]}, "es", "tu"
    )
    assert "no contiene un enlace" in recovery
    assert 'href=""' not in recovery and "NEVER-RENDER-BACKUP" not in recovery
    assert "30 minutos" not in recovery


def test_non_ctm_has_no_presentation_override_and_keeps_generic_identity():
    for signal in (None, "https://other.invalid/access", "https://notcreatumundo.mx/access"):
        data = {**DATA, **resolve_branding(redirect_url=signal)}
        data.pop("presentation_family", None)
        assert render_ctm_email(ENV, "magic_link.html", data, "es") is None
        assert "Crea Tu Mundo" not in EmailService()._render_template("magic_link.html", data, "es")


@pytest.mark.parametrize(
    "template,key", [("auth/password-reset", "reset_url"), ("auth/mfa-recovery", "recovery_url")]
)
def test_preview_uses_same_ctm_body_without_sending_capability(template, key):
    data = {key: URL, "user_name": "Persona sintética", "locale": "es"}
    preview = render_auth_preview(template, data, org_id=CTM_ORG_ID, formality="tu")
    kind = "password_reset" if key == "reset_url" else "mfa_recovery"
    assert preview["html"] == render_ctm_email(
        ENV, kind + ".html", {**data, **CTM_BRANDING}, "es", "tu"
    )
    assert preview["text"] == render_ctm_email(
        ENV, kind + ".txt", {**data, **CTM_BRANDING}, "es", "tu"
    )
    source = ast.parse((API / "app/routers/v1/email.py").read_text())
    registry = next(
        node.value
        for node in source.body
        if isinstance(node, ast.AnnAssign) and getattr(node.target, "id", "") == "EMAIL_TEMPLATES"
    )
    assert "auth/mfa-recovery" not in [key.value for key in registry.keys]


def test_map_payment_has_real_text_and_escapes_only_caller_data():
    from app.services.email_presentation import render_map_payment

    rendered = render_map_payment(
        {
            "periodo": "noviembre sintético <img src=x>",
            "sesiones": 2,
            "amount": "NEVER-RENDER-MONEY",
        }
    )
    assert rendered["text"] and "noviembre sintético <img src=x>" in rendered["text"]
    assert "&lt;img src=x&gt;" in rendered["html"]
    assert "<img src=x>" not in rendered["html"]
    assert "NEVER-RENDER-MONEY" not in rendered["html"] + rendered["text"]
    assert "2 sesiones" in rendered["html"] and "2 sesiones" in rendered["text"]
    preheader = re.search(r'<div data-preheader="true"[^>]*>(.*?)</div>', rendered["html"]).group(1)
    assert preheader == "Información de Crea Tu Mundo sobre el estado de un pago."
    tree = ast.parse((API / "app/routers/v1/email.py").read_text())
    renderers = [
        node
        for node in tree.body
        if isinstance(node, ast.AsyncFunctionDef)
        and node.name in {"render_template", "render_text_template"}
    ]
    assert len(renderers) == 2
    assert all(
        any(
            isinstance(node, ast.Call) and getattr(node.func, "id", "") == "render_map_payment"
            for node in ast.walk(renderer)
        )
        for renderer in renderers
    )


def test_trusted_context_reaches_existing_call_sites_without_executing_them():
    paths = [
        "app/services/invitation_service.py",
        "app/organizations/application/commands/invite_member.py",
        "app/routers/v1/organizations.py",
        "app/routers/v1/mfa.py",
    ]
    for file in paths:
        tree = ast.parse((API / file).read_text())
        calls = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and getattr(node.func, "attr", "")
            in {"send_invitation_email", "send_mfa_recovery_email"}
        ]
        assert calls and all("org_id" in {kw.arg for kw in node.keywords} for node in calls), file
    tree = ast.parse((API / "app/routers/v1/auth.py").read_text())
    schedules = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and getattr(node.func, "attr", "") == "add_task"
        and node.args
        and getattr(node.args[0], "id", "")
        in {"send_verification_email_task", "send_password_reset_email_task"}
    ]
    assert len(schedules) == 3
    assert all("org_id" in {kw.arg for kw in call.keywords} for call in schedules)


def test_presentation_and_sender_policy_receive_the_same_trusted_context(monkeypatch):
    from app.services import email_sender
    from app.services.email_branding import presentation_signals

    signals = presentation_signals(CTM_ORG_ID, "https://map.creatumundo.mx/synthetic")
    assert resolve_branding(**signals)["presentation_family"] == "ctm"
    binding = email_sender.binding_for(**signals)
    assert str(binding.org_id) == CTM_ORG_ID
    monkeypatch.setattr(email_sender, "is_vcto_entitled", lambda *args, **kwargs: True)
    monkeypatch.setattr(email_sender, "is_verified_domain", lambda *args, **kwargs: True)
    monkeypatch.setattr(email_sender, "tenant_credential_available", lambda *args, **kwargs: False)
    assert email_sender.sender_for(**signals) == email_sender.sender_for()
    monkeypatch.setattr(email_sender, "tenant_credential_available", lambda *args, **kwargs: True)
    assert email_sender.sender_for(**signals)[:2] == (binding.display_name, binding.from_address)
    for file, method in [
        ("email_service.py", "_send_email"),
        ("resend_email_service.py", "send_email"),
    ]:
        tree = ast.parse((API / "app/services" / file).read_text())
        captured = []
        for node in ast.walk(tree):
            if isinstance(node, ast.AsyncFunctionDef) and node.name in {
                "send_verification_email",
                "send_password_reset_email",
                "send_welcome_email",
                "send_invitation_email",
                "send_mfa_recovery_email",
            }:
                calls = [
                    call
                    for call in ast.walk(node)
                    if isinstance(call, ast.Call) and getattr(call.func, "attr", "") == method
                ]
                for call in calls:
                    assert any(
                        keyword.arg is None
                        and isinstance(keyword.value, ast.Name)
                        and keyword.value.id == "signals"
                        for keyword in call.keywords
                    )
                    captured.append(node.name)
        assert len(captured) >= 4


def test_preview_context_cannot_spoof_the_tenant_and_notice_has_no_empty_cta():
    generic = render_auth_preview(
        "auth/mfa-recovery", {**DATA, "recovery_code": None, "recovery_url": None}
    )
    assert "Crea Tu Mundo" not in generic["html"]
    assert 'href=""' not in generic["html"]
    assert "NEVER-RENDER-BACKUP" not in generic["html"] + generic["text"]


@pytest.mark.parametrize(
    "url",
    [
        "javascript:alert(1)",
        "data:text/html,test",
        "//example.invalid/access",
        "/relative",
        "https://user:secret@example.invalid/access",
        "https://@example.invalid/access",
        "https://example.invalid/\naccess",
        "https://example.invalid/ access",
        "https://example.invalid/\x00access",
        "https://example.invalid/\u200baccess",
    ],
)
def test_unsafe_destinations_have_no_cta_or_raw_fallback(url):
    from app.services.email_presentation import action_destination

    assert action_destination(url) is None
    data = {**CTM_BRANDING, "reset_url": url}
    html = render_ctm_email(ENV, "password_reset.html", data, "es", "tu")
    text = render_ctm_email(ENV, "password_reset.txt", data, "es", "tu")
    assert url not in html + text
    assert "El enlace para continuar no está disponible" in html
    assert 'href=""' not in html
    assert "1 hora" not in html + text


@pytest.mark.parametrize(
    "url",
    [
        "https://example.invalid/reset?token=a%2Fb%2Bc%3D&next=%2Funo%3Fa%3Db",
        "HTTP://Example.invalid:8080/a?token=opaque+value%20kept&x=1#fragment",
    ],
)
def test_destination_preserves_every_token_byte(url):
    from app.services.email_presentation import action_destination

    assert action_destination(url) == url
    text = render_ctm_email(
        ENV, "password_reset.txt", {**CTM_BRANDING, "reset_url": url}, "es", "tu"
    )
    assert url in text


def test_recovery_deadline_is_not_guessed_or_accepted_from_preview_input():
    data = {**DATA, "locale": "es"}
    text = render_ctm_email(ENV, "mfa_recovery.txt", data, "es", "tu")
    assert "30 minutos" not in text
    known = render_ctm_email(
        ENV, "mfa_recovery.txt", {**data, "recovery_expiry_minutes": 30}, "es", "tu"
    )
    assert "expira en 30 minutos" in known
    preview = render_auth_preview(
        "auth/mfa-recovery",
        {**data, "recovery_expiry_minutes": 30},
        org_id=CTM_ORG_ID,
        formality="tu",
    )
    assert "30 minutos" not in preview["text"]


def test_generic_recovery_frame_follows_actual_fallback_language():
    data = {"locale": "es", "recovery_code": "TEMP-SYNTHETIC", "recovery_url": URL}
    html = ResendEmailService()._render_template("mfa_recovery.html", data)
    assert '<html lang="en"' in html
    assert "Account Recovery Request" in html and "Crea Tu Mundo" not in html


def test_verification_without_issuer_metadata_does_not_invent_expiry():
    text = render_ctm_email(ENV, "verification.txt", DATA, "es", "tu")
    assert "horas" not in text


def test_product_invitation_uses_trusted_client_and_existing_issuer_deadline():
    tree = ast.parse((API / "app/routers/v1/internal_product_invites.py").read_text())
    scheduled = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and getattr(node.func, "attr", "") == "add_task"
        and node.args
        and getattr(node.args[0], "id", "") == "send_product_invite_email_task"
    )
    organization = next(kw.value for kw in scheduled.keywords if kw.arg == "org_id")
    assert ast.unparse(organization) == "client.organization_id"
    source = ast.parse((API / "app/services/email_service.py").read_text())
    task = next(
        node
        for node in source.body
        if getattr(node, "name", "") == "send_product_invite_email_task"
    )
    calls = [node for node in ast.walk(task) if isinstance(node, ast.Call)]
    assert any(getattr(call.func, "id", "") == "presentation_signals" for call in calls)
    for call in calls:
        if (
            getattr(call.func, "id", "") == "resolve_branding"
            or getattr(call.func, "attr", "") == "_send_email"
        ):
            assert any(
                kw.arg is None and getattr(kw.value, "id", "") == "signals" for kw in call.keywords
            )
    data = {**CTM_BRANDING, "first_name": "Nombre sintético", "magic_url": URL, "expires_hours": 72}
    text = render_ctm_email(ENV, "product_invite.txt", data, "es", "tu")
    assert "Hola Nombre sintético:" in text
    assert "expira en 72 horas" in text
