"""Async native invitation intents, membership and bounded mail receipts."""

import asyncio
import secrets
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

import structlog
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import AuditLog, Organization, OrganizationMember, UserStatus
from app.models.invitation import (
    Invitation,
    InvitationCreate,
    InvitationEmailStatus,
    InvitationResponse,
    InvitationStatus,
)
from app.models.user import User
from app.services.cache import CacheService
from app.services.email_service import EmailService

logger = structlog.get_logger()


class InvitationService:
    """One retained intent/attempt; acknowledgement never means delivery."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.email_service = EmailService()
        self.cache = CacheService()

    @staticmethod
    def _uuid(value) -> UUID:
        try:
            return UUID(str(value))
        except (ValueError, TypeError, AttributeError) as exc:
            raise ValueError("Invalid invitation or organization identifier") from exc

    async def _organization(self, organization_id) -> Organization:
        org = (await self.db.execute(select(Organization).where(
            Organization.id == self._uuid(organization_id),
        ).with_for_update())).scalar_one_or_none()
        if org is None:
            raise ValueError("Organization not found")
        return org

    async def require_admin(self, organization: Organization, user: User, role="member"):
        """Native active authority for this target; no policy-role translation."""
        if not user or not user.id:
            raise ValueError("Organization not found")
        actor = (await self.db.execute(select(User).where(
            User.id == user.id, User.status == UserStatus.ACTIVE,
        ))).scalar_one_or_none()
        if actor is None:
            raise ValueError("Organization not found")
        if organization.owner_id and organization.owner_id == actor.id:
            actual_role = "owner"
        else:
            actual_role = (await self.db.execute(select(OrganizationMember.role).where(
                OrganizationMember.organization_id == organization.id,
                OrganizationMember.user_id == actor.id,
                OrganizationMember.status == "active",
                OrganizationMember.role.in_(["admin", "owner"]),
            ).limit(1).with_for_update())).scalar_one_or_none()
        hierarchy = {"viewer": 0, "member": 1, "admin": 2, "owner": 3}
        if actual_role not in {"admin", "owner"}:
            raise ValueError("Organization not found")
        if role not in hierarchy or hierarchy[role] > hierarchy[actual_role]:
            raise ValueError("Cannot invite with a higher organization role")

    def _audit(self, action: str, invitation: Invitation, actor_id, **details) -> AuditLog:
        row = AuditLog(id=uuid4(), user_id=actor_id, action=action,
                       resource_type="invitation", resource_id=invitation.id,
                       details={"organization_id": str(invitation.organization_id),
                                "invitation_id": str(invitation.id), **details})
        self.db.add(row)
        return row

    async def email_statuses(self, invitations) -> dict:
        """Classify only retained, correctly paired native metadata."""
        by_id = {inv.id: inv for inv in invitations}
        if not by_id:
            return {}
        rows = (await self.db.execute(select(AuditLog).where(
            AuditLog.resource_type == "invitation",
            AuditLog.resource_id.in_(by_id),
            AuditLog.action.in_(["invitation.create", "invitation.email_attempt",
                                "invitation.email_ack"]),
        ))).scalars().all()
        classified = {}
        for inv_id, inv in by_id.items():
            matching = [r for r in rows if r.resource_id == inv_id
                        and isinstance(r.details, dict)
                        and r.details.get("organization_id") == str(inv.organization_id)
                        and r.details.get("invitation_id") == str(inv_id)]
            attempts = {str(r.id) for r in matching if r.action == "invitation.email_attempt"
                        and r.details.get("attempt_id") == str(r.id)
                        and r.details.get("email_status") == "unconfirmed"}
            acknowledged = any(r.action == "invitation.email_ack"
                               and r.details.get("attempt_id") in attempts
                               and r.details.get("email_status") == "acknowledged"
                               for r in matching)
            if attempts:
                classified[inv_id] = (InvitationEmailStatus.ACKNOWLEDGED
                                      if acknowledged and inv.email_sent
                                      else InvitationEmailStatus.UNCONFIRMED)
            elif any(r.resource_id == inv_id and r.action == "invitation.email_attempt"
                     for r in rows):
                classified[inv_id] = None  # Unclassified attempts never become not-attempted.
            elif any(r.action == "invitation.create"
                     and r.details.get("email_status") == "not_attempted" for r in matching):
                classified[inv_id] = (None if inv.email_sent
                                      else InvitationEmailStatus.NOT_ATTEMPTED)
            else:
                classified[inv_id] = None  # Legacy or unclassified, never retry authority.
        return classified

    async def response(self, invitation: Invitation) -> InvitationResponse:
        email_status = (await self.email_statuses([invitation]))[invitation.id]
        return InvitationResponse(
            id=str(invitation.id), organization_id=str(invitation.organization_id),
            email=invitation.email, role=invitation.role or "member", status=invitation.status,
            invited_by=str(invitation.created_by), message=invitation.message,
            expires_at=invitation.expires_at, created_at=invitation.created_at,
            invite_url=invitation.generate_invite_url(settings.FRONTEND_URL or settings.BASE_URL),
            email_sent=(bool(invitation.email_sent) if email_status is None else
                        email_status == InvitationEmailStatus.ACKNOWLEDGED),
            email_status=email_status,
        )

    async def create_invitation(self, invitation_data: InvitationCreate,
                                invited_by: User, tenant_id: str) -> InvitationResponse:
        # tenant_id is a legacy argument; this model's tenancy is organization_id.
        try:
            org = await self._organization(invitation_data.organization_id)
            await self.require_admin(org, invited_by, invitation_data.role)
            invitee = (await self.db.execute(select(User).where(
                User.email == invitation_data.email, User.tenant_id.is_(None),
            ))).scalar_one_or_none()
            if invitee is not None and (await self.db.execute(select(OrganizationMember.id).where(
                OrganizationMember.organization_id == org.id,
                OrganizationMember.user_id == invitee.id,
            ).limit(1))).scalar_one_or_none() is not None:
                raise ValueError("User already has a membership; no automatic reactivation")
            existing = (await self.db.execute(select(Invitation).where(
                Invitation.organization_id == org.id, Invitation.email == invitation_data.email,
                Invitation.status == InvitationStatus.PENDING.value,
                Invitation.expires_at >= datetime.utcnow(),
            ).limit(1))).scalar_one_or_none()
            if existing is not None:
                raise ValueError("An active invitation already exists for this email")
            invitation = Invitation(id=uuid4(), organization_id=org.id,
                                    email=invitation_data.email, role=invitation_data.role,
                                    message=invitation_data.message, email_sent=False,
                                    token=secrets.token_urlsafe(32), created_by=invited_by.id,
                                    expires_at=datetime.utcnow() + timedelta(
                                        days=invitation_data.expires_in))
            self.db.add(invitation)
            self._audit("invitation.create", invitation, invited_by.id,
                        email_status="not_attempted")
            await self.db.commit()
            await self.db.refresh(invitation)
        except Exception:
            await self.db.rollback()
            raise
        return await self._send_once(invitation, invited_by)

    async def _send_once(self, invitation: Invitation, actor: User) -> InvitationResponse:
        """Commit one attempt before the provider; unconfirmed attempts cannot replay."""
        try:
            org = await self._organization(invitation.organization_id)
            await self.require_admin(org, actor)
            invitation = (await self.db.execute(select(Invitation).where(
                Invitation.id == invitation.id,
            ).with_for_update().execution_options(populate_existing=True))).scalar_one()
            prior = (await self.db.execute(select(AuditLog.id).where(
                AuditLog.resource_type == "invitation", AuditLog.resource_id == invitation.id,
                AuditLog.action == "invitation.email_attempt",
            ).limit(1))).scalar_one_or_none()
            classified = (await self.email_statuses([invitation]))[invitation.id]
            if (prior is not None or classified != InvitationEmailStatus.NOT_ATTEMPTED
                    or not invitation.is_valid):
                raise ValueError("Previous mail attempt is not replayable; reconciliation required")
            attempt = self._audit("invitation.email_attempt", invitation, actor.id,
                                  email_status="unconfirmed")
            attempt.details = {**attempt.details, "attempt_id": str(attempt.id)}
            attempt_id = str(attempt.id)
            await self.db.commit()
            await self.db.refresh(invitation)
            retained = await self.response(invitation)
        except Exception:
            await self.db.rollback()
            raise
        # Even a crash before this call leaves an honest may-have-been-sent attempt.
        try:
            sent = await asyncio.wait_for(
                self._send_invitation_email(invitation, org, actor), timeout=15,
            )
        except Exception:
            sent = False
        if sent:
            try:
                invitation.email_sent = True
                self._audit("invitation.email_ack", invitation, actor.id,
                            attempt_id=attempt_id, email_status="acknowledged")
                await self.db.commit()
                await self.db.refresh(invitation)
                return await self.response(invitation)
            except Exception as exc:
                await self.db.rollback()
                logger.warning("Invitation acknowledgement unconfirmed",
                               invitation_id=retained.id, error_type=type(exc).__name__)
        # The retained attempt already proves this state, even if ACK commit/read lost its response.
        return retained.model_copy(update={"email_sent": False,
                                           "email_status": InvitationEmailStatus.UNCONFIRMED})

    async def create_bulk_invitations(self, emails: List[str], organization_id: str,
                                      role: Optional[str], message: Optional[str],
                                      expires_in: Optional[int], invited_by: User,
                                      tenant_id: str) -> Dict[str, Any]:
        successful, failed = [], []
        for email in emails:
            try:
                successful.append(await self.create_invitation(InvitationCreate(
                    organization_id=organization_id, email=email, role=role or "member",
                    message=message, expires_in=expires_in or 7,
                ), invited_by, tenant_id))
            except ValueError as exc:
                failed.append({"email": email, "error": str(exc)})
        return {"successful": successful, "failed": failed,
                "total_sent": sum(response.email_sent for response in successful),
                "total_failed": len(failed)}

    async def accept_invitation(self, token: str, user: Optional[User] = None,
                                new_user_data: Optional[Dict[str, Any]] = None,
                                locale: Optional[str] = None) -> Dict[str, Any]:
        try:
            found = (await self.db.execute(select(Invitation).where(
                Invitation.token == token,
            ))).scalar_one_or_none()
            if found is None:
                raise ValueError("Invalid invitation token")
            org = await self._organization(found.organization_id)
            invitation = (await self.db.execute(select(Invitation).where(
                Invitation.id == found.id,
            ).with_for_update().execution_options(populate_existing=True))).scalar_one()
            if not invitation.is_valid:
                raise ValueError("Invitation expired or no longer pending")
            is_new_user = user is None
            if user is not None:
                user = (await self.db.execute(select(User).where(
                    User.id == user.id, User.status == UserStatus.ACTIVE,
                ))).scalar_one_or_none()
                if user is None:
                    raise ValueError("Active authenticated user required")
            elif new_user_data:
                if (await self.db.execute(select(User.id).where(
                    User.email == invitation.email, User.tenant_id.is_(None),
                ).limit(1))).scalar_one_or_none() is not None:
                    raise ValueError("Existing account must sign in to accept")
                user = User(email=invitation.email, display_name=new_user_data.get("name"),
                            password_hash=new_user_data.get("password_hash"),
                            tenant_id=getattr(org, "tenant_id", None),
                            email_verified=True, locale=locale)
                self.db.add(user)
                await self.db.flush()
            else:
                raise ValueError("User account required to accept invitation")
            if user.email != invitation.email:
                raise ValueError("Invitation email does not match authenticated user")
            if (await self.db.execute(select(OrganizationMember.id).where(
                OrganizationMember.organization_id == org.id,
                OrganizationMember.user_id == user.id,
            ).limit(1))).scalar_one_or_none() is not None:
                raise ValueError("Existing membership cannot be adopted or reactivated")
            self.db.add(OrganizationMember(organization_id=org.id, user_id=user.id,
                                           role=invitation.role or "member", status="active",
                                           joined_at=datetime.utcnow()))
            invitation.status = InvitationStatus.ACCEPTED.value
            invitation.accepted_at = datetime.utcnow()
            self._audit("invitation.accept", invitation, user.id)
            await self.db.commit()
        except Exception:
            await self.db.rollback()
            raise
        await self.cache.delete(f"user:organizations:{user.id}")
        return {"success": True, "message": "Invitation accepted successfully",
                "user_id": str(user.id), "organization_id": str(invitation.organization_id),
                "is_new_user": is_new_user}

    async def revoke_invitation(self, invitation_id: str, revoked_by: User) -> bool:
        try:
            invitation = (await self.db.execute(select(Invitation).where(
                Invitation.id == self._uuid(invitation_id),
            ))).scalar_one_or_none()
            if invitation is None:
                raise ValueError("Invitation not found")
            org = await self._organization(invitation.organization_id)
            await self.require_admin(org, revoked_by)
            invitation = (await self.db.execute(select(Invitation).where(
                Invitation.id == invitation.id,
            ).with_for_update().execution_options(populate_existing=True))).scalar_one()
            if invitation.status != InvitationStatus.PENDING.value:
                raise ValueError("Only pending invitations can be revoked")
            invitation.status = InvitationStatus.REVOKED.value
            self._audit("invitation.revoke", invitation, revoked_by.id)
            await self.db.commit()
        except Exception:
            await self.db.rollback()
            raise
        return True

    async def resend_invitation(self, invitation_id: str, resent_by: User) -> InvitationResponse:
        invitation = (await self.db.execute(select(Invitation).where(
            Invitation.id == self._uuid(invitation_id),
        ))).scalar_one_or_none()
        if invitation is None:
            raise ValueError("Invitation not found")
        return await self._send_once(invitation, resent_by)

    async def _send_invitation_email(self, invitation: Invitation,
                                     organization: Organization, inviter: User) -> bool:
        try:
            return await self.email_service.send_invitation_email(
                email=invitation.email,
                invite_url=invitation.generate_invite_url(settings.FRONTEND_URL or settings.BASE_URL),
                organization_name=organization.name or "your organization",
                inviter_name=getattr(inviter, "name", None) or inviter.email,
                role=invitation.role or "member", expires_at=invitation.expires_at,
                org_id=organization.id,
            )
        except Exception as exc:
            logger.warning("Invitation transport unconfirmed", invitation_id=str(invitation.id),
                           error_type=type(exc).__name__)
            return False

    async def get_pending_invitations(self, organization_id: str, skip: int = 0,
                                      limit: int = 100) -> List[Invitation]:
        return list((await self.db.execute(select(Invitation).where(
            Invitation.organization_id == self._uuid(organization_id),
            Invitation.status == InvitationStatus.PENDING.value,
        ).offset(skip).limit(limit))).scalars().all())

    async def cleanup_expired_invitations(self) -> int:
        """Legacy internal helper; the mounted API uses its own scoped cleanup."""
        result = await self.db.execute(update(Invitation).where(
            Invitation.status == InvitationStatus.PENDING.value,
            Invitation.expires_at < datetime.utcnow(),
        ).values(status=InvitationStatus.EXPIRED.value))
        await self.db.commit()
        return result.rowcount
