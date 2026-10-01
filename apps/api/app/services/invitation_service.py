"""
Service for managing organization invitations.
"""

import secrets
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import structlog
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import Organization, OrganizationMember
from app.models.invitation import Invitation, InvitationCreate, InvitationResponse, InvitationStatus
from app.models.user import User
from app.services.audit_logger import AuditAction, AuditLogger
from app.services.cache import CacheService
from app.services.email_service import EmailService

logger = structlog.get_logger()


def _as_uuid(value: Any, not_found: str) -> uuid.UUID:
    """Parse an id, raising ``ValueError(not_found)`` when it is not a UUID."""
    try:
        return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))
    except (AttributeError, TypeError, ValueError):
        raise ValueError(not_found)


class InvitationService:
    """
    Service for managing organization invitations.

    ``db`` is the request's ``AsyncSession``. Each operation's audit row is
    written on the organization's audit chain (``tenant_id`` is the
    organization id) and commits with the operation.
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.email_service = EmailService()
        self.audit_logger = AuditLogger(db)
        self.cache = CacheService()

    async def create_invitation(
        self, invitation_data: InvitationCreate, invited_by: User, tenant_id: str
    ) -> InvitationResponse:
        """
        Create a new invitation.

        ``tenant_id`` (the inviter's tenant) is not used: invitations belong to
        an organization, and their audit rows go on its chain.
        """
        # Verify the organization exists.
        #
        # This used to filter on `Organization.tenant_id`, a column the
        # organizations table does not have, so the query raised before it
        # could scope anything. The scoping it was reaching for is restored
        # below against columns that exist — it must not simply be dropped:
        # `require_org_admin` only proves the caller administers SOME
        # organization, so without a per-organization check any org admin
        # could invite members into an organization they have nothing to do
        # with.
        organization_id = _as_uuid(invitation_data.organization_id, "Organization not found")
        organization = await self._first(
            select(Organization).where(Organization.id == organization_id)
        )

        if not organization:
            raise ValueError("Organization not found")

        # The caller must administer THIS organization — as its owner, or via
        # an admin/owner membership row. Both ids must be present before they
        # can match: an ownerless organization and an id-less caller would
        # otherwise compare equal as "None" and grant access to neither party's
        # organization.
        owner_id = getattr(organization, "owner_id", None)
        is_owner = bool(owner_id) and bool(invited_by.id) and str(owner_id) == str(invited_by.id)
        if not is_owner:
            admin_membership = await self._first(
                select(OrganizationMember).where(
                    and_(
                        OrganizationMember.organization_id == organization.id,
                        OrganizationMember.user_id == invited_by.id,
                        OrganizationMember.role.in_(["admin", "owner"]),
                    )
                )
            )
            if not admin_membership:
                raise ValueError("Organization not found")

        # Check if the invitee is already a member. Membership is keyed by
        # user_id, not by email, so resolve the address first; an address with
        # no account cannot already be a member. Resolve in the untenanted /
        # staff pool: invitees are platform identities and membership is via
        # OrganizationMember (decoupled from tenant_id). Email is per-tenant
        # since migration 013, so scope the lookup to that pool.
        invitee = await self._first(
            select(User).where(User.email == invitation_data.email, User.tenant_id.is_(None))
        )
        if invitee is not None:
            existing_member = await self._first(
                select(OrganizationMember).where(
                    and_(
                        OrganizationMember.organization_id == organization.id,
                        OrganizationMember.user_id == invitee.id,
                    )
                )
            )

            if existing_member:
                raise ValueError("User is already a member of this organization")

        # Check for existing pending invitation
        existing_invitation = await self._first(
            select(Invitation).where(
                and_(
                    Invitation.organization_id == organization.id,
                    Invitation.email == invitation_data.email,
                    Invitation.status == InvitationStatus.PENDING.value,
                )
            )
        )

        if existing_invitation and not existing_invitation.is_expired:
            raise ValueError("An active invitation already exists for this email")

        # Calculate expiration
        expires_at = datetime.utcnow() + timedelta(days=invitation_data.expires_in or 7)

        # Create invitation.
        #
        # `token` is NOT NULL and unique, and it is the only thing
        # /invitations/validate/{token} and /invitations/accept look up — yet
        # nothing here ever generated one. Every invitation was therefore
        # un-redeemable even before the email failed to send. Mint it here so
        # the value that gets mailed is the value the verify path validates.
        # `role` is validated by InvitationCreate as one of the organization
        # role names, so it is stored as given.
        invitation = Invitation(
            organization_id=organization.id,
            email=invitation_data.email,
            role=invitation_data.role or "member",
            status=InvitationStatus.PENDING.value,
            token=secrets.token_urlsafe(32),
            created_by=invited_by.id,
            expires_at=expires_at,
            message=invitation_data.message,
        )

        self.db.add(invitation)
        await self.db.commit()
        await self.db.refresh(invitation)

        # Send invitation email, and record the outcome on the row
        email_sent = await self._send_invitation_email(invitation, organization, invited_by)
        invitation.email_sent = email_sent

        # Log audit event; it commits with the delivery flag.
        await self._audit(
            AuditAction.INVITATION_CREATE,
            invitation,
            actor=invited_by,
            details={"email": invitation_data.email, "organization": organization.name},
        )
        await self.db.commit()

        # Create response. `email_sent` reports what actually happened on this
        # request rather than reading a column that does not exist.
        response = InvitationResponse(
            id=str(invitation.id),
            organization_id=str(invitation.organization_id),
            email=invitation.email,
            role=invitation.role,
            status=invitation.status,
            invited_by=str(invitation.created_by),
            message=invitation_data.message,
            expires_at=invitation.expires_at,
            created_at=invitation.created_at,
            invite_url=invitation.generate_invite_url(settings.FRONTEND_URL or settings.BASE_URL),
            email_sent=email_sent,
        )

        return response

    async def create_bulk_invitations(
        self,
        emails: List[str],
        organization_id: str,
        role: Optional[str],
        message: Optional[str],
        expires_in: Optional[int],
        invited_by: User,
        tenant_id: str,
    ) -> Dict[str, Any]:
        """
        Create multiple invitations at once.
        """
        successful = []
        failed = []

        for email in emails:
            try:
                invitation_data = InvitationCreate(
                    organization_id=organization_id,
                    email=email,
                    role=role,
                    message=message,
                    expires_in=expires_in,
                )

                response = await self.create_invitation(
                    invitation_data=invitation_data, invited_by=invited_by, tenant_id=tenant_id
                )

                successful.append(response)

            except Exception as e:
                failed.append({"email": email, "error": str(e)})

        return {
            "successful": successful,
            "failed": failed,
            "total_sent": len(successful),
            "total_failed": len(failed),
        }

    async def accept_invitation(
        self,
        token: str,
        user: Optional[User] = None,
        new_user_data: Optional[Dict[str, Any]] = None,
        locale: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Accept an invitation.

        `locale` is the language negotiated from the acceptance request. It is
        applied only to a user created here — an existing account keeps the
        preference it already has.
        """
        # Find invitation by token
        invitation = await self._first(select(Invitation).where(Invitation.token == token))

        if not invitation:
            raise ValueError("Invalid invitation token")

        if not invitation.is_valid:
            if invitation.is_expired:
                raise ValueError("Invitation has expired")
            else:
                raise ValueError(f"Invitation is {invitation.status}")

        # Create user if needed.
        # `name` is a read-only property on User (derived from first/last/display),
        # and invitations carry no tenant of their own — both kwargs used to
        # raise before a single account could be created this way. The tenant
        # comes from the organization being joined, which is the only place it
        # is actually recorded.
        is_new_user = False
        if not user and new_user_data:
            organization = await self._first(
                select(Organization).where(Organization.id == invitation.organization_id)
            )
            user = User(
                email=invitation.email,
                display_name=new_user_data.get("name") or invitation.email.split("@")[0],
                password_hash=new_user_data.get("password_hash"),
                tenant_id=getattr(organization, "tenant_id", None),
                email_verified=True,  # Auto-verify since they have the invitation
                locale=locale,
            )
            self.db.add(user)
            await self.db.flush()
            is_new_user = True
        elif not user:
            raise ValueError("User account required to accept invitation")

        # Verify email matches
        if user.email != invitation.email:
            raise ValueError("Invitation email does not match user email")

        # Add user to organization. Membership is keyed by user_id; there is
        # no user_email column, and passing one raised before any invitation
        # could ever be redeemed.
        org_member = OrganizationMember(
            organization_id=invitation.organization_id,
            user_id=user.id,
            role=invitation.role or "member",
        )
        self.db.add(org_member)

        # Update invitation status. There is no accepted_by column; accepted_at
        # plus the membership row record who redeemed it.
        invitation.status = InvitationStatus.ACCEPTED.value
        invitation.accepted_at = datetime.utcnow()

        # The membership, the status change and the audit row commit together.
        await self._audit(
            AuditAction.INVITATION_ACCEPT,
            invitation,
            actor=user,
            details={"organization_id": str(invitation.organization_id)},
        )
        await self.db.commit()

        # Clear cache
        await self.cache.delete(f"user:organizations:{user.id}")

        return {
            "is_new_user": is_new_user,
            "success": True,
            "message": "Invitation accepted successfully",
            "user_id": str(user.id),
            "organization_id": str(invitation.organization_id),
            "role": invitation.role,
            "redirect_url": f"/dashboard/org/{invitation.organization_id}",
        }

    async def revoke_invitation(self, invitation_id: str, revoked_by: User) -> bool:
        """
        Revoke a pending invitation.
        """
        invitation = await self._get(invitation_id)

        if invitation.status != InvitationStatus.PENDING.value:
            raise ValueError(f"Cannot revoke invitation with status: {invitation.status}")

        # Update status. `invitations` has no updated_at column; the audit row
        # records when it was revoked and by whom.
        invitation.status = InvitationStatus.REVOKED.value

        await self._audit(
            AuditAction.INVITATION_REVOKE,
            invitation,
            actor=revoked_by,
            details={"email": invitation.email},
        )
        await self.db.commit()

        return True

    async def resend_invitation(self, invitation_id: str, resent_by: User) -> InvitationResponse:
        """
        Resend an invitation email.
        """
        invitation = await self._get(invitation_id)

        if invitation.status != InvitationStatus.PENDING.value:
            raise ValueError(f"Cannot resend invitation with status: {invitation.status}")

        # Get organization
        organization = await self._first(
            select(Organization).where(Organization.id == invitation.organization_id)
        )

        # Resend email, and record the outcome on the row
        email_sent = await self._send_invitation_email(invitation, organization, resent_by)
        invitation.email_sent = email_sent

        await self._audit(
            AuditAction.INVITATION_RESEND,
            invitation,
            actor=resent_by,
            details={"email": invitation.email},
        )
        await self.db.commit()

        # Create response
        response = InvitationResponse(
            id=str(invitation.id),
            organization_id=str(invitation.organization_id),
            email=invitation.email,
            role=invitation.role,
            status=invitation.status,
            invited_by=str(invitation.created_by),
            message=invitation.message,
            expires_at=invitation.expires_at,
            created_at=invitation.created_at,
            invite_url=invitation.generate_invite_url(settings.FRONTEND_URL or settings.BASE_URL),
            email_sent=email_sent,
        )

        return response

    async def _send_invitation_email(
        self, invitation: Invitation, organization: Organization, inviter: User
    ) -> bool:
        """
        Send invitation email to the invitee. Returns whether it was sent.

        This used to compose its own HTML and hand it to
        `EmailService.send_email`, a method that does not exist on that class,
        so every invitation raised AttributeError into a bare `except` that
        printed and moved on. Nothing was ever mailed and nothing ever said so.

        It now renders the maintained invitation templates and reports the
        outcome instead of swallowing it. A send failure still does not undo
        the invitation — the row is real and the link stays redeemable — but
        the caller can now tell the difference.
        """
        try:
            invite_url = invitation.generate_invite_url(settings.FRONTEND_URL or settings.BASE_URL)
            sent = await self.email_service.send_invitation_email(
                email=invitation.email,
                invite_url=invite_url,
                organization_name=getattr(organization, "name", None) or "your organization",
                inviter_name=(getattr(inviter, "name", None) or inviter.email),
                role=invitation.role or "member",
                expires_at=invitation.expires_at,
            )
        except Exception:
            logger.exception(
                "Invitation email raised", invitation_id=str(getattr(invitation, "id", ""))
            )
            return False

        if not sent:
            logger.warning(
                "Invitation email NOT sent — the recipient will never receive a link",
                invitation_id=str(getattr(invitation, "id", "")),
            )
        return sent

    async def get_pending_invitations(
        self, organization_id: str, skip: int = 0, limit: int = 100
    ) -> List[Invitation]:
        """
        Get pending invitations for an organization.
        """
        result = await self.db.execute(
            select(Invitation)
            .where(
                and_(
                    Invitation.organization_id
                    == _as_uuid(organization_id, "Organization not found"),
                    Invitation.status == InvitationStatus.PENDING.value,
                )
            )
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def _first(self, statement) -> Any:
        """The first row of ``statement``, or None."""
        result = await self.db.execute(statement.limit(1))
        return result.scalars().first()

    async def _get(self, invitation_id: Any) -> Invitation:
        invitation = await self._first(
            select(Invitation).where(
                Invitation.id == _as_uuid(invitation_id, "Invitation not found")
            )
        )
        if not invitation:
            raise ValueError("Invitation not found")
        return invitation

    async def _audit(
        self, event_type: Any, invitation: Invitation, *, actor: Any, details: Dict[str, Any]
    ) -> None:
        """Write the invitation's audit row into this session; the caller commits."""
        organization_id = str(invitation.organization_id)
        await self.audit_logger.log(
            event_type=event_type,
            tenant_id=organization_id,
            organization_id=organization_id,
            identity_id=str(actor.id),
            resource_type="invitation",
            resource_id=str(invitation.id),
            details=details,
        )
