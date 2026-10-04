"""Ruling R101 (2026-10-04): the platform sender splits by message class.

One question decides the sender — should a person be able to reply?

  * system events (sign-in links, codes, verification, resets, invitations,
    notifications) and security mail leave as `MADFAM <noreply@madfam.io>`
    with a Reply-To on the human inbox that owns the topic
    (`support@madfam.io`; `security@madfam.io` for security mail), an
    `Auto-Submitted: auto-generated` header and a closing line saying a reply
    reaches a person;
  * conversation (welcome) keeps `MADFAM <hola@madfam.io>`, untouched;
  * a tenant's branded sender is untouched for every class, and every
    downgrade returns the platform sender FOR THE CLASS, whole.

No network: the SDK call and the httpx client are replaced by recorders, the
keys are fakes, and recipients are example.com addresses.
"""

from __future__ import annotations

from email.utils import formataddr
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.config import settings
from app.dependencies import verify_internal_api_key
from app.main import app
from app.services import email_service, resend_transport
from app.services.email_sender import (
    MESSAGE_CLASS_CONVERSATION,
    MESSAGE_CLASS_SECURITY,
    MESSAGE_CLASS_SYSTEM,
    TEMPLATE_MESSAGE_CLASS,
    is_platform_address,
    message_class_for_internal_send,
    message_class_for_template,
    sender_for,
    sender_for_address,
    stream_for,
)
from app.services.email_service import EmailService
from app.services.resend_email_service import ResendEmailService
from app.services.sender_binding import all_bindings

#: The vCTO tenant binding, read from the registry rather than named here: this
#: repository is public, and client names stay out of new content (R85).
TENANT_BINDING = next(iter(all_bindings().values()))
TENANT_SENDER = (TENANT_BINDING.display_name, TENANT_BINDING.from_address, TENANT_BINDING.reply_to)
TENANT_REDIRECT = f"https://{TENANT_BINDING.hosts[-1]}/auth/callback"
TENANT_CREDENTIAL_ENV = TENANT_BINDING.credential_ref
FAKE_TENANT_KEY = "re_test_tenant_key_not_real"

MADFAM_HOLA = ("MADFAM", "hola@madfam.io", "hola@madfam.io")
MADFAM_SYSTEM = ("MADFAM", "noreply@madfam.io", "support@madfam.io")
MADFAM_SECURITY = ("MADFAM", "noreply@madfam.io", "security@madfam.io")

#: The ruling's own sentence (the `tú` register).
R101_TU = "Este mensaje es automático; si respondes, te atiende una persona."
R101_USTED = "Este mensaje es automático; si responde, le atiende una persona."
R101_EN = "This message is automated; if you reply, a person will answer."

ALL_CLASSES = (None, MESSAGE_CLASS_SYSTEM, MESSAGE_CLASS_SECURITY, MESSAGE_CLASS_CONVERSATION)

TEMPLATE_DIR = Path(email_service.__file__).parent.parent / "templates" / "email"


def _tags(params: Dict[str, Any]) -> Dict[str, str]:
    return {t["name"]: t["value"] for t in params["tags"]}


@pytest.fixture(autouse=True)
def _r101_defaults(monkeypatch):
    """The shipped defaults, whatever the ambient environment says."""
    monkeypatch.delenv(TENANT_CREDENTIAL_ENV, raising=False)
    monkeypatch.setattr(settings, "EMAIL_TRACKED_SENDER_DOMAINS", "", raising=False)
    monkeypatch.setattr(settings, "EMAIL_SYSTEM_FROM_ADDRESS", "noreply@madfam.io", raising=False)
    monkeypatch.setattr(settings, "EMAIL_SUPPORT_REPLY_TO", "support@madfam.io", raising=False)
    monkeypatch.setattr(settings, "EMAIL_SECURITY_REPLY_TO", "security@madfam.io", raising=False)
    yield


@pytest.fixture()
def tenant_key(monkeypatch):
    monkeypatch.setenv(TENANT_CREDENTIAL_ENV, FAKE_TENANT_KEY)


@pytest.fixture()
def sdk_sends(monkeypatch) -> List[Dict[str, Any]]:
    """Real ResendEmailService send path; the SDK call records its params."""
    captured: List[Dict[str, Any]] = []
    monkeypatch.setattr(settings, "EMAIL_ENABLED", True, raising=False)
    monkeypatch.setattr(settings, "RESEND_API_KEY", "re_test_fake", raising=False)
    monkeypatch.setattr(settings, "ENVIRONMENT", "test", raising=False)

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
# The resolver
# --------------------------------------------------------------------------


class TestPlatformSenderByClass:
    def test_unclassified_and_conversation_keep_hola(self):
        assert sender_for() == MADFAM_HOLA
        assert sender_for(message_class=MESSAGE_CLASS_CONVERSATION) == MADFAM_HOLA

    def test_system_mail_is_noreply_with_a_support_reply_to(self):
        assert sender_for(message_class=MESSAGE_CLASS_SYSTEM) == MADFAM_SYSTEM

    def test_security_mail_replies_reach_security(self):
        assert sender_for(message_class=MESSAGE_CLASS_SECURITY) == MADFAM_SECURITY

    def test_blank_system_address_turns_the_split_off(self, monkeypatch):
        """The one-env-edit rollback: every platform message is hola@ again."""
        monkeypatch.setattr(settings, "EMAIL_SYSTEM_FROM_ADDRESS", "")
        for message_class in ALL_CLASSES:
            assert sender_for(message_class=message_class) == MADFAM_HOLA

    def test_blank_reply_to_still_reaches_a_person(self, monkeypatch):
        monkeypatch.setattr(settings, "EMAIL_SUPPORT_REPLY_TO", "")
        assert sender_for(message_class=MESSAGE_CLASS_SYSTEM) == (
            "MADFAM",
            "noreply@madfam.io",
            "hola@madfam.io",
        )

    def test_both_platform_addresses_are_recognised(self):
        assert is_platform_address("hola@madfam.io")
        assert is_platform_address("NoReply@MADFAM.io")
        assert not is_platform_address(TENANT_SENDER[1])
        assert not is_platform_address(None)


class TestTenantSenderIsUntouched:
    def test_the_tenants_branded_sender_is_the_same_for_every_class(self, tenant_key):
        for message_class in ALL_CLASSES:
            assert (
                sender_for(redirect_url=TENANT_REDIRECT, message_class=message_class)
                == TENANT_SENDER
            )

    def test_a_downgrade_returns_the_platform_sender_for_the_class(self):
        # No tenant key: the credential gate downgrades, whole.
        assert sender_for(redirect_url=TENANT_REDIRECT, message_class=MESSAGE_CLASS_SYSTEM) == (
            MADFAM_SYSTEM
        )
        assert sender_for(redirect_url=TENANT_REDIRECT, message_class=MESSAGE_CLASS_SECURITY) == (
            MADFAM_SECURITY
        )
        assert sender_for(redirect_url=TENANT_REDIRECT) == MADFAM_HOLA

    @pytest.mark.parametrize("key_present", [False, True])
    @pytest.mark.parametrize("message_class", ALL_CLASSES)
    def test_no_tenant_name_ever_sits_on_a_platform_address(
        self, monkeypatch, key_present, message_class
    ):
        """THE RULE (2026-09-07) holds for the new address too."""
        if key_present:
            monkeypatch.setenv(TENANT_CREDENTIAL_ENV, FAKE_TENANT_KEY)
        for entitled in (None, True, False):
            name, address, _ = sender_for(
                redirect_url=TENANT_REDIRECT, vcto_entitled=entitled, message_class=message_class
            )
            if is_platform_address(address):
                assert name == "MADFAM"
            name, address, _ = sender_for_address(
                from_email=None,
                from_name=TENANT_SENDER[0],
                redirect_url=TENANT_REDIRECT,
                vcto_entitled=entitled,
                message_class=message_class,
            )
            if is_platform_address(address):
                assert name == "MADFAM"

    def test_an_explicit_verified_from_keeps_its_own_reply_to(self):
        assert sender_for_address(
            from_email="facturacion@madfam.io", message_class=MESSAGE_CLASS_SYSTEM
        ) == ("MADFAM", "facturacion@madfam.io", "facturacion@madfam.io")


class TestClassification:
    def test_template_classes(self):
        assert message_class_for_template("magic_link") == MESSAGE_CLASS_SYSTEM
        assert message_class_for_template("es/password_reset.txt") == MESSAGE_CLASS_SYSTEM
        assert message_class_for_template("verification.html") == MESSAGE_CLASS_SYSTEM
        assert message_class_for_template("mfa_recovery") == MESSAGE_CLASS_SECURITY
        assert message_class_for_template("welcome.html") == MESSAGE_CLASS_CONVERSATION
        assert message_class_for_template("not_a_template") is None
        assert message_class_for_template(None) is None

    def test_every_classified_template_exists(self):
        for stem in TEMPLATE_MESSAGE_CLASS:
            assert (TEMPLATE_DIR / f"{stem}.html").exists(), stem
            assert (TEMPLATE_DIR / f"{stem}.txt").exists(), stem

    def test_internal_door_token_mail_is_a_system_event(self):
        assert message_class_for_internal_send(True) == MESSAGE_CLASS_SYSTEM
        assert message_class_for_internal_send(False) is None

    def test_streams(self):
        assert stream_for(MESSAGE_CLASS_SYSTEM) == "transactional"
        assert stream_for(MESSAGE_CLASS_SECURITY) == "transactional"
        assert stream_for(MESSAGE_CLASS_CONVERSATION) == "conversational"
        assert stream_for(None) is None


# --------------------------------------------------------------------------
# EmailService (the magic-link transport)
# --------------------------------------------------------------------------


class TestEmailServicePayload:
    async def test_magic_link_without_a_tenant(self, http_sends):
        await EmailService().send_magic_link_email(
            "persona@example.com", "T0KEN", locale="es", formality="tu"
        )
        payload = http_sends[0]
        assert payload["from"] == formataddr(("MADFAM", "noreply@madfam.io"))
        assert payload["reply_to"] == "support@madfam.io"
        assert payload["headers"] == {"Auto-Submitted": "auto-generated"}
        assert _tags(payload)["stream"] == "transactional"
        assert R101_TU in payload["html"]
        assert payload["text"].endswith(R101_TU)

    async def test_password_reset_speaks_usted_by_default(self, http_sends):
        await EmailService().send_password_reset_email("persona@example.com", "R3SET", locale="es")
        payload = http_sends[0]
        assert payload["from"] == formataddr(("MADFAM", "noreply@madfam.io"))
        assert R101_USTED in payload["html"]
        assert payload["text"].endswith(R101_USTED)

    async def test_english_mail_gets_the_english_line(self, http_sends):
        await EmailService().send_verification_email("persona@example.com", locale="en")
        payload = http_sends[0]
        assert payload["reply_to"] == "support@madfam.io"
        assert R101_EN in payload["html"]
        assert payload["text"].endswith(R101_EN)

    async def test_welcome_is_conversation_and_unchanged(self, http_sends):
        await EmailService().send_welcome_email("persona@example.com", locale="es", formality="tu")
        payload = http_sends[0]
        assert payload["from"] == formataddr(("MADFAM", "hola@madfam.io"))
        assert "reply_to" not in payload
        assert "headers" not in payload
        assert _tags(payload)["stream"] == "conversational"
        assert R101_TU not in payload["html"]
        assert R101_TU not in payload["text"]

    async def test_the_tenants_branded_magic_link_is_untouched(self, http_sends, tenant_key):
        await EmailService().send_magic_link_email(
            "persona@example.com",
            "T0KEN",
            redirect_url=TENANT_REDIRECT,
            locale="es",
            hosted_hop=False,
        )
        payload = http_sends[0]
        assert TENANT_SENDER[1] in payload["from"]
        assert "headers" not in payload
        assert "automático" not in payload["html"]
        assert "automático" not in payload["text"]

    async def test_smtp_path_carries_the_same_envelope(self, monkeypatch):
        monkeypatch.setattr(email_service.settings, "EMAIL_PROVIDER", "smtp", raising=False)
        monkeypatch.setattr(email_service.settings, "SMTP_HOST", "smtp.example.test", raising=False)
        monkeypatch.setattr(email_service.settings, "SMTP_TLS", False, raising=False)
        monkeypatch.setattr(email_service.settings, "SMTP_USERNAME", None, raising=False)
        sent: List[str] = []
        smtp = MagicMock()
        smtp.return_value.__enter__.return_value.sendmail = lambda _f, _t, msg: sent.append(msg)
        with patch("app.services.email_service.smtplib.SMTP", smtp):
            assert await EmailService().send_magic_link_email("persona@example.com", "T0KEN")
        message = sent[0]
        assert "From: MADFAM <noreply@madfam.io>" in message
        assert "Reply-To: support@madfam.io" in message
        assert "Auto-Submitted: auto-generated" in message


# --------------------------------------------------------------------------
# ResendEmailService (enterprise mailers)
# --------------------------------------------------------------------------


class TestResendServicePayload:
    async def test_mfa_recovery_replies_reach_security(self, sdk_sends):
        await ResendEmailService().send_mfa_recovery_email(
            "persona@example.com", "Ana", ["1234-5678"]
        )
        params = sdk_sends[0]
        assert params["from"] == formataddr(("MADFAM", "noreply@madfam.io"))
        assert params["reply_to"] == "security@madfam.io"
        assert params["headers"]["Auto-Submitted"] == "auto-generated"
        assert _tags(params)["stream"] == "transactional"
        assert params["text"].endswith(R101_EN)

    async def test_welcome_keeps_hola(self, sdk_sends):
        await ResendEmailService().send_welcome_email("persona@example.com", "Ana")
        params = sdk_sends[0]
        assert params["from"] == formataddr(("MADFAM", "hola@madfam.io"))
        assert "reply_to" not in params
        assert "Auto-Submitted" not in params["headers"]
        assert _tags(params)["stream"] == "conversational"

    async def test_an_unclassified_send_is_unchanged(self, sdk_sends):
        await ResendEmailService().send_email(
            to_email="persona@example.com", subject="Aviso", html_content="<p>Hola</p>"
        )
        params = sdk_sends[0]
        assert params["from"] == formataddr(("MADFAM", "hola@madfam.io"))
        assert "reply_to" not in params
        assert "Auto-Submitted" not in params["headers"]
        assert "stream" not in _tags(params)


# --------------------------------------------------------------------------
# The internal door
# --------------------------------------------------------------------------


class TestInternalDoor:
    async def test_a_token_template_without_a_tenant_uses_the_system_sender(
        self, client, sdk_sends
    ):
        response = await client.post(
            "/api/v1/internal/email/send-template",
            json={
                "to": ["persona@example.com"],
                "template": "auth/magic-link",
                "variables": {
                    "magic_link": "https://app.example.test/e?token=x",
                    "expires_in": "15m",
                },
                "source_app": "forj",
            },
        )
        assert response.json()["success"] is True
        params = sdk_sends[0]
        assert params["from"] == formataddr(("MADFAM", "noreply@madfam.io"))
        assert params["reply_to"] == "support@madfam.io"
        assert params["headers"]["Auto-Submitted"] == "auto-generated"

    async def test_a_plain_send_keeps_hola(self, client, sdk_sends):
        response = await client.post(
            "/api/v1/internal/email/send",
            json={
                "to": ["persona@example.com"],
                "subject": "Aviso",
                "html": "<p>Hola</p>",
                "source_app": "forj",
            },
        )
        assert response.json()["success"] is True
        params = sdk_sends[0]
        assert params["from"] == formataddr(("MADFAM", "hola@madfam.io"))
        assert "reply_to" not in params

    async def test_a_preview_shows_the_from_the_send_would_use(self, client):
        response = await client.post(
            "/api/v1/internal/email/preview",
            json={
                "kind": "template",
                "template": "auth/magic-link",
                "context": {
                    "magic_link": "https://app.example.test/e?token=x",
                    "expires_in": "15m",
                },
            },
        )
        assert response.status_code == 200
        assert response.json()["from"] == "MADFAM <noreply@madfam.io>"
