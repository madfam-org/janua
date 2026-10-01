"""The invitation email must actually be composed, addressed and sent.

Before the fix this path was dead in three stacked ways, all of them silent:
the service called `EmailService.send_email`, which does not exist on that
class; it first touched columns (`email_send_attempts`) the invitations table
does not have; and a bare `except Exception: print(...)` swallowed both. The
maintained invitation templates were never rendered by any live path.
"""

import uuid
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models import Invitation
from app.services.email_service import EmailService
from app.services.invitation_service import InvitationService

pytestmark = pytest.mark.asyncio


TOKEN = "inv-token-abc123"


def _invitation():
    """An invitation shaped like the row the schema actually defines."""
    invitation = Invitation(
        email="invitee@example.com",
        role="admin",
        status="pending",
        token=TOKEN,
        expires_at=datetime.utcnow() + timedelta(days=7),
    )
    invitation.id = "11111111-1111-1111-1111-111111111111"
    invitation.organization_id = "22222222-2222-2222-2222-222222222222"
    return invitation


def _service(sent=True):
    """InvitationService with the transport — and only the transport — faked."""
    service = InvitationService(MagicMock())
    service.email_service._send_email = AsyncMock(return_value=sent)
    return service


async def _send(service):
    return await service._send_invitation_email(
        _invitation(),
        SimpleNamespace(name="Acme Corp"),
        SimpleNamespace(name="Ada Lovelace", email="ada@example.com"),
    )


def _payload(service):
    """The single message handed to the transport."""
    assert service.email_service._send_email.await_count == 1
    return service.email_service._send_email.await_args.kwargs


class TestSend:
    async def test_reports_sent(self):
        # The regression: this returned None because AttributeError was caught
        # and printed, so nothing could tell a sent invitation from a dead one.
        service = _service()
        assert await _send(service) is True

    async def test_transport_called(self):
        service = _service()
        await _send(service)
        assert _payload(service)["to_email"] == "invitee@example.com"

    async def test_reports_failure(self):
        # _send_email returns False when no transport is configured; that must
        # surface rather than read as success.
        service = _service(sent=False)
        assert await _send(service) is False


class TestContent:
    async def test_href_carries_token(self):
        # An action button with no usable href is the failure mode this whole
        # path exists to avoid: the token is what /accept looks up.
        service = _service()
        await _send(service)
        html = _payload(service)["html_content"]
        assert 'href="' in html
        assert f"token={TOKEN}" in html
        assert 'href=""' not in html

    async def test_uses_template(self):
        # Proves the maintained invitation.html is what shipped, not a
        # hand-rolled string: these markers exist only in the template.
        service = _service()
        await _send(service)
        html = _payload(service)["html_content"]
        # es is the default locale, so the Spanish template is what ships;
        # this marker exists only in es/invitation.html.
        assert "Le invitaron a colaborar" in html
        assert "Acme Corp" in html
        assert "Ada Lovelace" in html
        assert "admin" in html

    async def test_extends_base(self):
        # base.html supplies the wrapper; a template that failed to resolve
        # its parent would render without it.
        service = _service()
        await _send(service)
        html = _payload(service)["html_content"]
        assert "<html" in html.lower()
        assert str(datetime.utcnow().year) in html

    async def test_text_part(self):
        service = _service()
        await _send(service)
        text = _payload(service)["text_content"]
        assert f"token={TOKEN}" in text
        assert "Acme Corp" in text
        assert "<" not in text.split("http")[0]

    async def test_subject(self):
        service = _service()
        await _send(service)
        assert "Acme Corp" in _payload(service)["subject"]


class TestUrl:
    def test_token_in_url(self):
        url = _invitation().generate_invite_url("https://app.example.com")
        assert url == f"https://app.example.com/invitations/accept?token={TOKEN}"

    def test_trailing_slash(self):
        url = _invitation().generate_invite_url("https://app.example.com/")
        assert "//invitations" not in url.replace("https://", "")


class TestValidity:
    def test_pending_is_valid(self):
        assert _invitation().is_valid is True
        assert _invitation().is_expired is False

    def test_expired(self):
        invitation = _invitation()
        invitation.expires_at = datetime.utcnow() - timedelta(seconds=1)
        assert invitation.is_expired is True
        assert invitation.is_valid is False

    def test_accepted_not_valid(self):
        invitation = _invitation()
        invitation.status = "accepted"
        assert invitation.is_valid is False


class TestEmailService:
    """The seam the invitation service now calls."""

    async def test_method_exists(self):
        # The original defect in one line: this attribute was absent, so every
        # call raised AttributeError.
        assert callable(getattr(EmailService, "send_invitation_email", None))

    async def test_returns_transport_result(self):
        service = EmailService()
        service._send_email = AsyncMock(return_value=False)
        result = await service.send_invitation_email(
            email="invitee@example.com",
            invite_url="https://app.example.com/invitations/accept?token=x",
            organization_name="Acme Corp",
            inviter_name="Ada Lovelace",
        )
        assert result is False

    async def test_render_failure_keeps_url(self):
        # Even if a template blows up, the recipient must still get a link.
        service = EmailService()
        service._send_email = AsyncMock(return_value=True)
        with patch.object(service.jinja_env, "get_template", side_effect=RuntimeError("boom")):
            await service.send_invitation_email(
                email="invitee@example.com",
                invite_url=f"https://app.example.com/invitations/accept?token={TOKEN}",
                organization_name="Acme Corp",
                inviter_name="Ada Lovelace",
            )
        assert TOKEN in service._send_email.await_args.kwargs["html_content"]


def _rows(db, rows):
    """Answer the service's ``await db.execute(...)`` calls with ``rows``, in order."""

    def result(row):
        answer = MagicMock()
        answer.scalars.return_value.first.return_value = row
        return answer

    db.execute = AsyncMock(side_effect=[result(row) for row in rows])


class TestCreate:
    """create_invitation is the entry point to the send path."""

    def _service(self, owner_id="u-1"):
        organization = MagicMock()
        organization.id = "22222222-2222-2222-2222-222222222222"
        organization.name = "Acme Corp"
        organization.owner_id = owner_id

        db = MagicMock()
        db.commit = AsyncMock()
        # organization -> invitee User -> existing invitation
        _rows(db, [organization, None, None])

        def flush(obj=None, *args, **kwargs):
            """Stand in for the defaults SQLAlchemy applies at flush time."""
            if obj is None:
                return
            if getattr(obj, "created_at", None) is None:
                obj.created_at = datetime.utcnow()
            if getattr(obj, "id", None) is None:
                obj.id = uuid.uuid4()

        db.add.side_effect = flush
        db.refresh = AsyncMock(side_effect=flush)

        service = InvitationService(db)
        service.email_service._send_email = AsyncMock(return_value=True)
        service.audit_logger = MagicMock()
        service.audit_logger.log = AsyncMock()
        return service

    async def _create(self, service, inviter_id="u-1"):
        from app.models.invitation import InvitationCreate

        inviter = MagicMock()
        inviter.id = inviter_id
        inviter.email = "ada@example.com"
        inviter.name = "Ada Lovelace"
        return await service.create_invitation(
            InvitationCreate(
                organization_id="22222222-2222-2222-2222-222222222222",
                email="invitee@example.com",
                role="admin",
                expires_in=7,
            ),
            inviter,
            "tenant-1",
        )

    async def test_mails_invitee(self):
        service = self._service()
        response = await self._create(service)
        assert response.email_sent is True
        assert _payload(service)["to_email"] == "invitee@example.com"

    async def test_token_minted(self):
        # token is NOT NULL and is the only thing /accept looks up, yet
        # nothing ever generated one.
        service = self._service()
        response = await self._create(service)
        token = response.invite_url.split("token=")[1]
        assert len(token) >= 32

    async def test_mailed_token_matches(self):
        # The link the invitee receives must be the one the API reports —
        # otherwise the invitation can never be redeemed.
        service = self._service()
        response = await self._create(service)
        assert f'href="{response.invite_url}"' in _payload(service)["html_content"]

    async def test_send_failure_reported(self):
        service = self._service()
        service.email_service._send_email = AsyncMock(return_value=False)
        response = await self._create(service)
        # The invitation still exists and stays redeemable; the caller is just
        # told the truth about delivery.
        assert response.email_sent is False
        assert "token=" in response.invite_url

    async def test_foreign_org_refused(self):
        # require_org_admin only proves the caller administers SOME org, so
        # this per-organization check is what stops a cross-org invite.
        service = self._service(owner_id="someone-else")
        organization = MagicMock()
        organization.id = "22222222-2222-2222-2222-222222222222"
        organization.owner_id = "someone-else"
        _rows(service.db, [organization, None])  # no admin membership for the caller
        with pytest.raises(ValueError):
            await self._create(service, inviter_id="u-1")
        service.email_service._send_email.assert_not_awaited()

    async def test_ownerless_org_refused(self):
        # An ownerless organization and an id-less caller must not compare
        # equal as "None" and grant each other access.
        service = self._service(owner_id=None)
        organization = MagicMock()
        organization.id = "22222222-2222-2222-2222-222222222222"
        organization.owner_id = None
        _rows(service.db, [organization, None])  # no admin membership
        inviter = MagicMock()
        inviter.id = None
        inviter.email = "ada@example.com"
        inviter.name = "Ada Lovelace"
        from app.models.invitation import InvitationCreate

        with pytest.raises(ValueError):
            await service.create_invitation(
                InvitationCreate(
                    organization_id="22222222-2222-2222-2222-222222222222",
                    email="invitee@example.com",
                    role="admin",
                    expires_in=7,
                ),
                inviter,
                "tenant-1",
            )
        service.email_service._send_email.assert_not_awaited()
