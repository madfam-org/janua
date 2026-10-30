"""Only verified MAP provenance holds auth mail; shared organization is insufficient."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

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


@pytest.mark.parametrize("source", ["registered-client", "registered-reset-page"])
async def test_map_reset_is_held_before_lookup_token_or_background_mail(monkeypatch, source):
    selected = (
        SimpleNamespace(is_active=True, redirect_uris=[MAP])
        if source == "registered-client"
        else None
    )
    monkeypatch.setattr(
        "app.auth.tenant_login_context.login_client_context", AsyncMock(return_value=(selected, {}))
    )
    monkeypatch.setattr(auth, "get_redis", AsyncMock())
    lookup = AsyncMock()
    monkeypatch.setattr(auth, "get_user_by_email", lookup)
    monkeypatch.setattr(auth.settings, "PASSWORD_RESET_REDIRECT_ORIGINS", MAP)
    tasks, db = MagicMock(), AsyncMock()
    await auth._dispatch_password_reset(
        "synthetic@example.com",
        MAP if source == "registered-reset-page" else None,
        tasks,
        db,
        client_id="synthetic" if selected else None,
    )
    lookup.assert_not_awaited()
    tasks.add_task.assert_not_called()
    db.add.assert_not_called()


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
