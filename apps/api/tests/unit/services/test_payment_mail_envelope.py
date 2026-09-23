"""Exercise the real renderer/binding gate with only the secret resolver replaced."""

import uuid
from dataclasses import replace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from app.services import email_sender, sender_binding, sender_credentials
from app.services import payment_mail_dispatch as mail
from app.services.payment_mail_auth import PaymentMailPrincipal

pytestmark = pytest.mark.asyncio


@pytest.fixture
def envelope_env(monkeypatch):
    principal = PaymentMailPrincipal("fixture-mail", uuid.uuid4())
    intent = mail.PaymentNoticeIntent(
        command_id=uuid.uuid4(), recipient="persona01@example.com", year=2026, month=9, sessions=4
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
    secret = AsyncMock(return_value="fixture-provider-secret")
    monkeypatch.setattr(sender_credentials, "resolve_bound_credential", secret)
    return principal, intent, binding, secret


async def test_real_template_and_envelope_are_stable_without_persisting_secret(envelope_env):
    principal, intent, _, _ = envelope_env
    first = await mail._envelope(principal, intent)
    assert first == await mail._envelope(principal, intent)
    params, credential, binding_hash, fingerprint = first
    assert credential == "fixture-provider-secret"
    assert len(binding_hash) == len(fingerprint) == 64
    assert "fixture-provider-secret" not in str(params)
    assert "septiembre de 2026" in params["html"]
    assert params["to"] == ["persona01@example.com"]
    assert params["reply_to"] == "reply@example.com"
    assert params["headers"]["X-Message-ID"].startswith("janua-payment/")


@pytest.mark.parametrize("field,value", [("org_id", str(uuid.uuid4())), ("provider", "smtp")])
async def test_foreign_or_unsupported_binding_refuses(envelope_env, monkeypatch, field, value):
    principal, intent, binding, secret = envelope_env
    monkeypatch.setattr(
        sender_binding, "resolve_binding", lambda *_: replace(binding, **{field: value})
    )
    with pytest.raises(HTTPException) as error:
        await mail._envelope(principal, intent)
    assert error.value.status_code == 503
    secret.assert_not_called()


async def test_platform_sender_fallback_is_not_used(envelope_env, monkeypatch):
    principal, intent, _, secret = envelope_env
    monkeypatch.setattr(
        email_sender,
        "sender_for_address",
        lambda *a, **kw: ("Platform fixture", "platform@example.com", None),
    )
    with pytest.raises(HTTPException) as error:
        await mail._envelope(principal, intent)
    assert error.value.detail["code"] == "mail_tenant_sender_unavailable"
    secret.assert_not_called()


@pytest.mark.parametrize("credential", [None, ""])
async def test_missing_credential_does_not_fallback(envelope_env, credential):
    principal, intent, _, secret = envelope_env
    secret.return_value = credential
    with pytest.raises(HTTPException) as error:
        await mail._envelope(principal, intent)
    assert error.value.detail["code"] == "mail_credential_unavailable"


@pytest.mark.parametrize("field,value", [("EMAIL_ENABLED", False), ("ENVIRONMENT", "development")])
async def test_simulation_is_refused(envelope_env, monkeypatch, field, value):
    monkeypatch.setattr(mail.settings, field, value)
    with pytest.raises(HTTPException) as error:
        await mail._envelope(*envelope_env[:2])
    assert error.value.detail["code"] == "mail_transport_inactive"


async def test_explicit_platform_binding_resolves_its_credential_without_ambient_sdk(monkeypatch):
    binding = sender_binding.SenderBinding(
        tenant="fixture",
        display_name="Synthetic Org",
        from_address="notice@example.com",
        reply_to="reply@example.com",
        account=sender_binding.ACCOUNT_MADFAM,
        credential_ref=sender_binding.MADFAM_RESEND_CREDENTIAL_REF,
    )
    reader = AsyncMock(return_value="fixture-bound-platform-key")
    monkeypatch.setattr(sender_credentials, "_read_reference", reader)
    assert (
        await sender_credentials.resolve_bound_credential(binding) == "fixture-bound-platform-key"
    )
    reader.assert_awaited_once_with(sender_binding.MADFAM_RESEND_CREDENTIAL_REF)


async def test_missing_alternate_account_never_falls_back(monkeypatch):
    binding = sender_binding.SenderBinding(
        tenant="fixture",
        display_name="Synthetic Org",
        from_address="notice@example.com",
        reply_to="reply@example.com",
        credential_ref="FIXTURE_ALTERNATE_RESEND_KEY",
    )
    reader = AsyncMock(return_value=None)
    monkeypatch.setattr(sender_credentials, "_read_reference", reader)
    with pytest.raises(sender_credentials.SenderCredentialError):
        await sender_credentials.resolve_bound_credential(binding)
    reader.assert_awaited_once_with("FIXTURE_ALTERNATE_RESEND_KEY")
