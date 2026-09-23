"""No provider call leaves this process; account races use controlled threads."""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from threading import Event

import pytest

from app.services import resend_email_service as primary
from app.services import resend_transport as transport
from app.services.email.resend_service import ResendService


def test_all_adapters_and_constructors_preserve_an_inflight_tenant_account(monkeypatch):
    entered, release = Event(), Event()
    seen = []
    monkeypatch.setattr(transport.resend, "api_key", "ambient-fixture")
    monkeypatch.setattr(primary.settings, "RESEND_API_KEY", "platform-fixture")

    def provider(params):
        if params["subject"] == "tenant-fixture":
            entered.set()
            assert release.wait(5)
        seen.append((params["subject"], transport.resend.api_key))
        return {"id": "provider-fixture"}

    monkeypatch.setattr(transport.resend.Emails, "send", provider)
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(
            transport.send_on_account, {"subject": "tenant-fixture"}, "tenant-key-fixture"
        )
        try:
            assert entered.wait(5)
            primary.ResendEmailService()
            platform = ResendService(api_key="platform-fixture")
            # Construction used to overwrite the in-flight tenant key.
            assert transport.resend.api_key == "tenant-key-fixture"
            second = pool.submit(
                asyncio.run,
                platform.send_email(
                    to="persona01@ejemplo.test", subject="platform-fixture", html="<p>Fixture</p>"
                ),
            )
        finally:
            release.set()
        first.result(timeout=5)
        second.result(timeout=5)
    assert seen == [
        ("tenant-fixture", "tenant-key-fixture"),
        ("platform-fixture", "platform-fixture"),
    ]
    assert transport.resend.api_key == "ambient-fixture"


@pytest.mark.parametrize("response", [{}, {"id": None}, {"id": ""}, {"id": " "}, None])
def test_missing_provider_receipt_is_not_acceptance(monkeypatch, response):
    monkeypatch.setattr(transport.resend, "api_key", "ambient-fixture")
    monkeypatch.setattr(transport.resend.Emails, "send", lambda _p: response)
    with pytest.raises(ValueError, match="acceptance receipt"):
        transport.send_on_account({}, "tenant-fixture")
    assert transport.resend.api_key == "ambient-fixture"


def test_failed_send_restores_account(monkeypatch):
    monkeypatch.setattr(transport.resend, "api_key", "ambient-fixture")

    def fail(_params):
        raise RuntimeError("fixture failure")

    monkeypatch.setattr(transport.resend.Emails, "send", fail)
    with pytest.raises(RuntimeError):
        transport.send_on_account({}, "tenant-fixture")
    assert transport.resend.api_key == "ambient-fixture"


@pytest.mark.asyncio
async def test_console_is_simulation_and_does_not_log_message_contents(caplog):
    result = await primary.ResendEmailService()._send_with_console(
        "persona01@example.com",
        "private fixture subject",
        "private fixture body",
        None,
        "fixture-message-id",
    )
    assert result.status == "simulated"
    assert "persona01@example.com" not in caplog.text
    assert "private fixture" not in caplog.text


def test_stable_provider_key_is_forwarded_and_account_restored(monkeypatch):
    from datetime import datetime, timedelta
    from unittest.mock import Mock

    provider = Mock(return_value={"id": "fixture-provider-id"})
    monkeypatch.setattr(transport.resend.Emails, "send", provider)
    monkeypatch.setattr(transport.resend, "api_key", "ambient-fixture")
    transport.send_on_account(
        {"subject": "fixture"},
        "tenant-fixture",
        idempotency_key="fixture-command",
        send_before=datetime.utcnow() + timedelta(minutes=1),
    )
    provider.assert_called_once_with({"subject": "fixture"}, {"idempotency_key": "fixture-command"})
    assert transport.resend.api_key == "ambient-fixture"


def test_deadline_is_checked_after_waiting_for_shared_account_lock(monkeypatch):
    from datetime import datetime, timedelta
    from unittest.mock import Mock

    provider = Mock()
    monkeypatch.setattr(transport.resend.Emails, "send", provider)
    monkeypatch.setattr(transport.resend, "api_key", "ambient-fixture")
    # The lock changes the test clock as it would advance during a stalled send.
    now = datetime.utcnow()
    clock = Mock()
    clock.utcnow.return_value = now
    monkeypatch.setattr(transport, "datetime", clock)

    class DelayedLock:
        def __enter__(self):
            clock.utcnow.return_value = now + timedelta(hours=24)

        def __exit__(self, *_):
            pass

    monkeypatch.setattr(transport, "_ACCOUNT_LOCK", DelayedLock())
    with pytest.raises(TimeoutError, match="window expired"):
        transport.send_on_account(
            {},
            "tenant-fixture",
            idempotency_key="fixture-command",
            send_before=now + timedelta(hours=23),
        )
    provider.assert_not_called()
    assert transport.resend.api_key == "ambient-fixture"
