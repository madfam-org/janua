"""The operator invitation mail (internal product-invites, 2026-10-22).

ONE message, sent through the real renderer with only the transport faked: it
names the product in the subject, the heading and the button; carries the one
link, which lands on Janua's own callback (never on the product); speaks the
operator's language and register; and is classed `system` (R101) like every
token link.
"""

from unittest.mock import AsyncMock, patch

import pytest

from app.config import settings
from app.services.email_sender import message_class_for_template
from app.services.email_service import EmailService, send_product_invite_email_task

pytestmark = pytest.mark.asyncio

TOKEN = "invite-token-abc123"


async def _send(**kwargs):
    with patch.object(EmailService, "_send_email", AsyncMock(return_value=True)) as transport:
        await send_product_invite_email_task(
            "invitee@beta-cv.example.com",
            TOKEN,
            app_name="MADFAM CV",
            expires_hours=72,
            **kwargs,
        )
    assert transport.await_count == 1
    return transport.await_args.kwargs


async def test_spanish_tu_invitation_names_the_product_and_carries_one_link(monkeypatch):
    monkeypatch.setattr(settings, "JANUA_CUSTOM_DOMAIN", "auth.example.com")
    sent = await _send(locale="es", formality="tu", first_name="Ana")
    link = f"https://auth.example.com/api/v1/auth/magic-link/callback?token={TOKEN}"
    assert sent["to_email"] == "invitee@beta-cv.example.com"
    assert sent["subject"].startswith("Tu invitación a MADFAM CV | ")
    html = sent["html_content"]
    assert "Invitación a MADFAM CV" in html
    assert "Hola Ana:" in html
    assert "Entrar a MADFAM CV" in html
    assert "Usa el siguiente botón para entrar" in html
    assert "vence en 72 horas" in html
    assert html.count(link) == 2  # the button and the copy-paste fallback
    assert 'lang="es-MX"' in html
    text = sent["text_content"]
    assert link in text and "Entra con este enlace" in text
    assert sent["template"] == "product_invite" and sent["token_link"] is True
    assert message_class_for_template("product_invite") == "system"


async def test_spanish_defaults_to_usted():
    sent = await _send(locale="es")
    assert sent["subject"].startswith("Su invitación a MADFAM CV | ")
    assert "Use el siguiente botón para entrar" in sent["html_content"]
    assert "Hola:" in sent["html_content"]


async def test_english_invitation():
    sent = await _send(locale="en")
    assert sent["subject"].startswith("Your invitation to MADFAM CV | ")
    assert "Sign in to MADFAM CV" in sent["html_content"]
    assert "expires in 72 hours" in sent["text_content"]
