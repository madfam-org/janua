"""Every Resend send is tagged per app/tenant, and token links are never tracked.

Two properties, tested on every transport Janua sends through:

1. TAGS. Each message carries `source_app` (and `org_id` when known) as Resend
   tags, sanitized to Resend's charset, so webhook events can be scoped back
   to the app that sent the mail (app/services/email_tags.py).
2. TOKEN LINKS. A message carrying a one-time/signed link that leaves FROM a
   domain listed in EMAIL_TRACKED_SENDER_DOMAINS goes out TEXT-ONLY, so
   Resend's click tracking never rewrites the link and no pixel is injected;
   from any other domain the HTML is untouched (app/services/email_tracking.py).

No network: the SDK call and the httpx client are replaced by recorders, the
keys are fakes, and recipients are example.com addresses.
"""

from __future__ import annotations

import os
import re
import uuid
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, patch
from urllib.parse import urlsplit

import pytest
from httpx import ASGITransport, AsyncClient

import app.services.resend_email_service as resend_module
from app.config import settings
from app.dependencies import verify_internal_api_key
from app.main import app
from app.services import (
    email_sender,
    email_service,
    resend_transport,
    sender_binding,
    sender_credentials,
)
from app.services import payment_mail_dispatch as mail
from app.services.email_branding import CTM_ORG_ID
from app.services.email_service import EmailService
from app.services.email_tags import build_tags, normalize_tags, sanitize_tag_value, tag_value
from app.services.email_tracking import (
    html_carries_token_link,
    html_to_text,
    is_tracked_sender,
    untracked_bodies,
)
from app.services.payment_mail_auth import PaymentMailPrincipal

CTM_CREDENTIAL_ENV = "CTM_RESEND_API_KEY"
FAKE_CTM_KEY = "re_test_ctm_key_not_real"
CTM_REDIRECT = "https://map.creatumundo.mx/auth/callback"
TOKEN_HTML = '<p>Hola</p><p><a href="https://map.creatumundo.mx/entrar?token=T0KEN">Entrar</a></p>'
PLAIN_HTML = '<p>Hola</p><p><a href="https://map.creatumundo.mx/agenda">Ver agenda</a></p>'


def _tags(params: Dict[str, Any]) -> Dict[str, str]:
    return {t["name"]: t["value"] for t in params["tags"]}


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    """No ambient CTM key, no ambient tracked domains."""
    monkeypatch.delenv(CTM_CREDENTIAL_ENV, raising=False)
    monkeypatch.setattr(settings, "EMAIL_TRACKED_SENDER_DOMAINS", "", raising=False)
    yield


@pytest.fixture()
def tracked(monkeypatch):
    def _set(*domains: str) -> None:
        monkeypatch.setattr(settings, "EMAIL_TRACKED_SENDER_DOMAINS", ",".join(domains))

    return _set


@pytest.fixture()
def ctm_key(monkeypatch):
    monkeypatch.setenv(CTM_CREDENTIAL_ENV, FAKE_CTM_KEY)


@pytest.fixture()
def sdk_sends(monkeypatch) -> List[Dict[str, Any]]:
    """Real ResendEmailService send path; the SDK call records its params."""
    captured: List[Dict[str, Any]] = []
    monkeypatch.setattr(resend_module.settings, "EMAIL_ENABLED", True, raising=False)
    monkeypatch.setattr(resend_module.settings, "RESEND_API_KEY", "re_test_fake", raising=False)
    monkeypatch.setattr(resend_module.settings, "ENVIRONMENT", "test", raising=False)

    def _fake_send(params: Dict[str, Any]) -> Dict[str, str]:
        captured.append(params)
        return {"id": "resend-email-id-1"}

    monkeypatch.setattr(resend_transport.resend.Emails, "send", staticmethod(_fake_send))
    return captured


@pytest.fixture()
def http_sends(monkeypatch) -> List[Dict[str, Any]]:
    """Real EmailService httpx path; the AsyncClient records each JSON payload."""
    captured: List[Dict[str, Any]] = []
    monkeypatch.setattr(email_service.settings, "EMAIL_PROVIDER", "resend", raising=False)
    monkeypatch.setattr(email_service.settings, "RESEND_API_KEY", "re_test_fake", raising=False)

    async def _post(url, headers=None, json=None):
        captured.append(json)
        response = MagicMock()
        response.status_code = 200
        return response

    client = MagicMock()
    client.post = AsyncMock(side_effect=_post)
    client_cls = MagicMock()
    client_cls.return_value.__aenter__ = AsyncMock(return_value=client)
    client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
    with patch("app.services.email_service.httpx.AsyncClient", client_cls):
        yield captured


@pytest.fixture()
def client():
    app.dependency_overrides[verify_internal_api_key] = lambda: True
    yield AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
    app.dependency_overrides.pop(verify_internal_api_key, None)


# --------------------------------------------------------------------------
# Tag helpers
# --------------------------------------------------------------------------


def test_sanitize_tag_value_matches_resend_charset():
    assert sanitize_tag_value("auth/magic-link") == "auth_magic-link"
    assert sanitize_tag_value("Crea Tu Mundo") == "Crea_Tu_Mundo"
    assert sanitize_tag_value("crea-map") == "crea-map"
    assert sanitize_tag_value("x" * 300) == "x" * 256


def test_build_tags_reserved_first_and_not_overridable():
    tags = build_tags(
        source_app="crea-map",
        source_type="notification",
        org_id=CTM_ORG_ID,
        template="auth/magic-link",
        extra={"source_app": "dhanam", "org_id": "other", "campaña": "sept 2026", "": "x"},
    )
    assert tags[:4] == [
        {"name": "source_app", "value": "crea-map"},
        {"name": "source_type", "value": "notification"},
        {"name": "org_id", "value": CTM_ORG_ID},
        {"name": "template", "value": "auth_magic-link"},
    ]
    assert {"name": "campa_a", "value": "sept_2026"} in tags
    assert [t["name"] for t in tags].count("source_app") == 1


def test_normalize_tags_fills_source_app_and_org_id():
    tags = normalize_tags([{"name": "organization", "value": "Crea Tu Mundo"}], org_id="o-1")
    assert tags == [
        {"name": "source_app", "value": "janua"},
        {"name": "organization", "value": "Crea_Tu_Mundo"},
        {"name": "org_id", "value": "o-1"},
    ]
    assert normalize_tags([{"name": "source_app", "value": "crea-map"}], org_id=None) == [
        {"name": "source_app", "value": "crea-map"}
    ]


def test_tag_value_reads_both_webhook_shapes():
    assert tag_value({"source_app": "crea-map"}, "source_app") == "crea-map"
    assert tag_value([{"name": "source_app", "value": "crea-map"}], "source_app") == "crea-map"
    assert tag_value(None, "source_app") is None
    assert tag_value({"source_app": ""}, "source_app") is None


# --------------------------------------------------------------------------
# Tags on every send path
# --------------------------------------------------------------------------


async def test_send_carries_source_app_and_org_id(client, sdk_sends, ctm_key):
    response = await client.post(
        "/api/v1/internal/email/send",
        json={
            "to": ["persona@example.com"],
            "subject": "Aviso",
            "html": "<p>Hola</p>",
            "text": "Hola",
            "source_app": "crea-map",
            "org_id": CTM_ORG_ID,
            "tags": {"source_app": "spoof", "kind": "aviso semanal"},
        },
    )
    assert response.json()["success"] is True
    # The message_id MAP stores IS Resend's email id (the join key for events).
    assert response.json()["message_id"] == "resend-email-id-1"
    tags = _tags(sdk_sends[0])
    assert tags["source_app"] == "crea-map"
    assert tags["org_id"] == CTM_ORG_ID
    assert tags["source_type"] == "notification"
    assert tags["kind"] == "aviso_semanal"


async def test_send_without_org_id_carries_no_org_tag(client, sdk_sends):
    await client.post(
        "/api/v1/internal/email/send",
        json={
            "to": ["persona@example.com"],
            "subject": "s",
            "html": "<p>x</p>",
            "source_app": "dhanam",
        },
    )
    tags = _tags(sdk_sends[0])
    assert tags["source_app"] == "dhanam"
    assert "org_id" not in tags


async def test_send_template_tag_is_sanitized(client, sdk_sends):
    await client.post(
        "/api/v1/internal/email/send-template",
        json={
            "to": ["persona@example.com"],
            "template": "onboarding/complete",
            "variables": {"user_name": "Ana"},
            "source_app": "forj",
        },
    )
    tags = _tags(sdk_sends[0])
    assert tags["template"] == "onboarding_complete"
    assert tags["source_app"] == "forj"


async def test_service_methods_default_to_source_app_janua(sdk_sends):
    await resend_module.ResendEmailService().send_invitation_email(
        to_email="persona@example.com",
        inviter_name="Ana",
        organization_name="Crea Tu Mundo",
        role="member",
        invitation_url="https://app.janua.dev/invite?token=abc",
        expires_at=__import__("datetime").datetime(2026, 10, 1),
    )
    tags = _tags(sdk_sends[0])
    assert tags["source_app"] == "janua"
    assert tags["organization"] == "Crea_Tu_Mundo"  # was an illegal value before


async def test_auth_mail_is_tagged_janua_with_tenant_org(http_sends, ctm_key):
    await EmailService().send_magic_link_email(
        "persona@example.com", "T0KEN", redirect_url=CTM_REDIRECT, hosted_hop=False
    )
    tags = _tags(http_sends[0])
    assert tags["source_app"] == "janua"
    assert tags["source_type"] == "auth"
    assert tags["template"] == "magic_link"
    assert tags["org_id"] == CTM_ORG_ID


async def test_platform_auth_mail_has_no_org_tag(http_sends):
    await EmailService().send_magic_link_email("persona@example.com", "T0KEN")
    tags = _tags(http_sends[0])
    assert tags["source_app"] == "janua"
    assert "org_id" not in tags


async def test_payment_notice_carries_org_id_tag(monkeypatch):
    principal = PaymentMailPrincipal("fixture-mail", uuid.uuid4())
    intent = mail.PaymentNoticeIntent(
        command_id=uuid.uuid4(), recipient="persona01@example.com", year=2026, month=9
    )
    binding = sender_binding.SenderBinding(
        tenant="fixture",
        display_name="Synthetic Org",
        from_address="notice@example.com",
        reply_to="reply@example.com",
        org_id=str(principal.org_id),
    )
    monkeypatch.setattr(mail.settings, "EMAIL_ENABLED", True)
    monkeypatch.setattr(mail.settings, "ENVIRONMENT", "test")
    monkeypatch.setattr(sender_binding, "resolve_binding", lambda *_: binding)
    monkeypatch.setattr(
        email_sender,
        "sender_for_address",
        lambda from_email, **_: (binding.display_name, binding.from_address, binding.reply_to),
    )
    monkeypatch.setattr(
        sender_credentials, "resolve_bound_credential", AsyncMock(return_value="fixture-secret")
    )
    params, *_ = await mail._envelope(principal, intent)
    tags = _tags(params)
    assert tags["source_app"] == "crea-map"
    assert tags["org_id"] == str(principal.org_id)


# --------------------------------------------------------------------------
# Token-link policy (pure)
# --------------------------------------------------------------------------


def test_tracked_sender_is_exact_domain_and_off_by_default(tracked):
    assert is_tracked_sender("hola@creatumundo.mx") is False
    tracked("creatumundo.mx")
    assert is_tracked_sender("hola@creatumundo.mx") is True
    assert is_tracked_sender("HOLA@CreaTuMundo.MX") is True
    assert is_tracked_sender("hola@sub.creatumundo.mx") is False
    assert is_tracked_sender("hola@madfam.io") is False
    assert is_tracked_sender(None) is False


@pytest.mark.parametrize(
    ("html", "expected"),
    [
        ('<a href="https://x.test/cb?token=abc">x</a>', True),
        ('<a href="https://x.test/cb?next=/&code=abc">x</a>', True),
        ('<a href="https://x.test/cb#access_token=abc">x</a>', True),
        ('<a href="https://x.test/reset?Signature=abc">x</a>', True),
        ('<a href="https://x.test/agenda?semana=38">x</a>', False),
        ("<p>token=abc but not a link</p>", False),
        ("", False),
    ],
)
def test_token_link_detection(html, expected):
    assert html_carries_token_link(html) is expected


def test_html_to_text_keeps_the_link_and_drops_markup():
    text = html_to_text(
        "<html><head><style>p{color:red}</style><title>t</title></head>"
        '<body><p>Hola&nbsp;Ana</p><p><a href="https://x.test/cb?token=abc">Entrar</a></p></body></html>'
    )
    assert "https://x.test/cb?token=abc" in text
    assert "Hola" in text and "Entrar" in text
    assert "<" not in text and "color:red" not in text


def test_untracked_bodies_matrix(tracked):
    # Not tracked: untouched, even with a token.
    assert untracked_bodies("hola@creatumundo.mx", TOKEN_HTML, "t", token_link=True) == (
        TOKEN_HTML,
        "t",
        False,
    )
    tracked("creatumundo.mx")
    # Tracked + declared token: text-only, caller's text kept.
    assert untracked_bodies("hola@creatumundo.mx", TOKEN_HTML, "t", token_link=True) == (
        None,
        "t",
        True,
    )
    # Tracked + detected token, no text given: text derived from the HTML.
    html, text, forced = untracked_bodies("hola@creatumundo.mx", TOKEN_HTML, None)
    assert html is None and forced is True
    assert "https://map.creatumundo.mx/entrar?token=T0KEN" in text
    # Tracked but no token: HTML stays.
    assert untracked_bodies("hola@creatumundo.mx", PLAIN_HTML, None) == (PLAIN_HTML, None, False)


# --------------------------------------------------------------------------
# Token-link policy on every transport
# --------------------------------------------------------------------------


async def test_magic_link_from_tracked_ctm_domain_is_text_only(http_sends, ctm_key, tracked):
    tracked("creatumundo.mx")
    await EmailService().send_magic_link_email(
        "persona@example.com", "T0KEN", redirect_url=CTM_REDIRECT, hosted_hop=False
    )
    payload = http_sends[0]
    assert "hola@creatumundo.mx" in payload["from"]
    assert "html" not in payload
    assert "token=T0KEN" in payload["text"]


async def test_magic_link_from_untracked_domain_keeps_html(http_sends, ctm_key, tracked):
    tracked("some-other.example")
    await EmailService().send_magic_link_email(
        "persona@example.com", "T0KEN", redirect_url=CTM_REDIRECT, hosted_hop=False
    )
    payload = http_sends[0]
    assert "token=T0KEN" in payload["html"]
    assert "text" in payload


@pytest.mark.parametrize(
    "send",
    [
        lambda s: s.send_password_reset_email("persona@example.com", "R3SET"),
        lambda s: s.send_invitation_email(
            "persona@example.com", "https://app.janua.dev/i?token=1NV", "Org", "Ana"
        ),
        lambda s: s.send_verification_email("persona@example.com"),
    ],
    ids=["password_reset", "invitation", "verification"],
)
async def test_platform_token_mail_on_tracked_madfam_is_text_only(http_sends, tracked, send):
    tracked("madfam.io")
    await send(EmailService())
    payload = http_sends[0]
    assert "hola@madfam.io" in payload["from"]
    assert "html" not in payload
    assert payload["text"]


async def test_welcome_mail_is_not_token_bearing(http_sends, tracked):
    tracked("madfam.io")
    await EmailService().send_welcome_email("persona@example.com")
    assert "html" in http_sends[0]


@pytest.mark.parametrize(
    ("template", "variables"),
    [
        (
            "auth/magic-link",
            {"magic_link": "https://map.creatumundo.mx/e?x=1", "expires_in": "15m"},
        ),
        (
            "auth/password-reset",
            {"reset_link": "https://map.creatumundo.mx/r/1", "expires_in": "1h"},
        ),
        (
            "auth/email-verification",
            {"verification_link": "https://map.creatumundo.mx/v/1", "expires_in": "1d"},
        ),
        (
            "invitation/team-invite",
            {
                "inviter_name": "Ana",
                "team_name": "CTM",
                "invite_url": "https://map.creatumundo.mx/i/1",
            },
        ),
        ("invitation/creator-invite", {"invite_url": "https://map.creatumundo.mx/i/2"}),
    ],
)
async def test_token_templates_from_tracked_ctm_are_text_only(
    client, sdk_sends, ctm_key, tracked, template, variables
):
    """Even when the link has no recognisable token parameter, the template's
    own `token_link` flag forces text-only on a tracked domain."""
    tracked("creatumundo.mx")
    response = await client.post(
        "/api/v1/internal/email/send-template",
        json={
            "to": ["persona@example.com"],
            "template": template,
            "variables": variables,
            "source_app": "crea-map",
            "org_id": CTM_ORG_ID,
        },
    )
    assert response.json()["success"] is True
    params = sdk_sends[0]
    assert "hola@creatumundo.mx" in params["from"]
    assert "html" not in params
    link = next(v for k, v in variables.items() if k.endswith(("_link", "_url")))
    assert link in params["text"]


async def test_token_template_from_untracked_domain_keeps_html(client, sdk_sends, ctm_key):
    await client.post(
        "/api/v1/internal/email/send-template",
        json={
            "to": ["persona@example.com"],
            "template": "auth/magic-link",
            "variables": {
                "magic_link": "https://map.creatumundo.mx/e?token=x",
                "expires_in": "15m",
            },
            "source_app": "crea-map",
            "org_id": CTM_ORG_ID,
        },
    )
    assert "html" in sdk_sends[0]


async def test_non_token_template_on_tracked_domain_keeps_html(client, sdk_sends, ctm_key, tracked):
    tracked("creatumundo.mx")
    await client.post(
        "/api/v1/internal/email/send-template",
        json={
            "to": ["persona@example.com"],
            "template": "map/pago-confirmado",
            "variables": {"periodo": "septiembre de 2026"},
            "source_app": "crea-map",
            "org_id": CTM_ORG_ID,
        },
    )
    assert "html" in sdk_sends[0]


@pytest.mark.parametrize(
    ("body", "expect_html"),
    [
        ({"html": PLAIN_HTML, "contains_token_link": True}, False),  # declared
        ({"html": TOKEN_HTML}, False),  # detected
        ({"html": PLAIN_HTML}, True),  # neither
    ],
    ids=["declared", "detected", "plain"],
)
async def test_send_on_tracked_ctm(client, sdk_sends, ctm_key, tracked, body, expect_html):
    tracked("creatumundo.mx")
    await client.post(
        "/api/v1/internal/email/send",
        json={
            "to": ["persona@example.com"],
            "subject": "Aviso",
            "source_app": "crea-map",
            "org_id": CTM_ORG_ID,
            **body,
        },
    )
    params = sdk_sends[0]
    assert ("html" in params) is expect_html
    if not expect_html:
        # The link survives into the text part (compared by parsed host, not substring).
        hosts = {urlsplit(u).hostname for u in re.findall(r"https?://\S+", params["text"])}
        assert "map.creatumundo.mx" in hosts


async def test_resend_service_reset_on_tracked_madfam_is_text_only(sdk_sends, tracked):
    tracked("madfam.io")
    await resend_module.ResendEmailService().send_password_reset_email(
        "persona@example.com", "Ana", "https://auth.madfam.io/r?token=abc"
    )
    params = sdk_sends[0]
    assert "html" not in params
    assert "token=abc" in params["text"]


def test_ctm_key_env_is_not_leaking_between_tests():
    assert os.environ.get(CTM_CREDENTIAL_ENV) is None
