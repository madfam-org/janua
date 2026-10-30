"""MAP allows traced recovery and magic login; shared organization is insufficient."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.auth.map_mail_hold import is_map_login_client, map_auth_mail_held
from app.routers.v1 import auth
from app.services.email_branding import CTM_ORG_ID
from app.services.email_service import EmailService

MAP = "https://map.creatumundo.mx/auth/reset"
ERP = "https://erp.creatumundo.mx/auth/reset"


def test_scope_is_map_destination_or_native_client_and_magic_is_exception():
    assert map_auth_mail_held(template="password_reset", redirect_url=MAP)
    assert not map_auth_mail_held(template="magic_link", redirect_url=MAP)
    assert not map_auth_mail_held(template="password_reset", redirect_url=ERP, org_id=CTM_ORG_ID)
    assert not map_auth_mail_held(template="password_reset", org_id=CTM_ORG_ID)
    assert is_map_login_client(SimpleNamespace(is_active=True, redirect_uris=[MAP]))
    assert not is_map_login_client(SimpleNamespace(is_active=False, redirect_uris=[MAP]))
    assert not is_map_login_client(SimpleNamespace(is_active=True, redirect_uris=[ERP]))


@pytest.mark.parametrize("template", ["welcome", "email_verification", "mfa_recovery"])
def test_non_recovery_templates_remain_held(template):
    assert map_auth_mail_held(template=template, redirect_url=MAP)


async def test_auth_transport_holds_map_nonmagic_but_keeps_same_org_other_product(monkeypatch):
    service = EmailService()
    provider = AsyncMock(return_value=True)
    monkeypatch.setattr(service, "_send_via_resend", provider)
    monkeypatch.setattr(auth.settings, "EMAIL_PROVIDER", "resend")
    monkeypatch.setattr(auth.settings, "RESEND_API_KEY", "synthetic-not-a-live-key")
    args = {
        "to_email": "synthetic@example.com",
        "subject": "Synthetic",
        "html_content": "Synthetic",
        "template": "password_reset",
    }
    assert await service._send_email(**args, redirect_url=MAP, org_id=CTM_ORG_ID) is False
    provider.assert_not_awaited()
    assert await service._send_email(**args, redirect_url=ERP, org_id=CTM_ORG_ID) is True
    provider.assert_awaited_once()


async def test_held_template_stops_before_recipient_diagnostics(monkeypatch, caplog):
    service = EmailService()
    provider = AsyncMock()
    monkeypatch.setattr(service, "_send_email", provider)
    with pytest.raises(ValueError, match="MAP non-magic auth mail held"):
        await service.send_password_reset_email(
            "synthetic@example.com", "synthetic-token", branding_redirect_url=MAP
        )
    provider.assert_not_awaited()
    assert "synthetic@example.com" not in caplog.text
