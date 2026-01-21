"""
Service for managing organization invitations.
"""

from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta

from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from app.models.invitation import (
    Invitation, InvitationStatus,
    InvitationCreate, InvitationResponse
)
from app.models.user import User
from app.models import Organization, OrganizationMember
from app.models.policy import Role, UserRole
from app.services.email_service import EmailService
from app.services.audit_logger import AuditLogger, AuditAction
from app.services.cache import CacheService
from app.config import settings


class InvitationService:
    """
    Service for managing organization invitations.
    """
    
    def __init__(self, db: Session):
        self.db = db
        self.email_service = EmailService()
        self.audit_logger = AuditLogger(db)
        self.cache = CacheService()
    
    async def create_invitation(
        self,
        invitation_data: InvitationCreate,
        invited_by: User,
        tenant_id: str
    ) -> InvitationResponse:
        """
        Create a new invitation.
        """
        # Verify organization exists and user has permission
        organization = self.db.query(Organization).filter(
            and_(
                Organization.id == invitation_data.organization_id,
                Organization.tenant_id == tenant_id
            )
        ).first()
        
        if not organization:
            raise ValueError("Organization not found")
        
        # Check if user is already a member
        existing_member = self.db.query(OrganizationMember).filter(
            and_(
                OrganizationMember.organization_id == invitation_data.organization_id,
                OrganizationMember.user_email == invitation_data.email
            )
        ).first()
        
        if existing_member:
            raise ValueError("User is already a member of this organization")
        
        # Check for existing pending invitation
        existing_invitation = self.db.query(Invitation).filter(
            and_(
                Invitation.organization_id == invitation_data.organization_id,
                Invitation.email == invitation_data.email,
                Invitation.status == InvitationStatus.PENDING.value
            )
        ).first()
        
        if existing_invitation and not existing_invitation.is_expired:
            raise ValueError("An active invitation already exists for this email")
        
        # Get role if specified
        role = None
        if invitation_data.role:
            role = self.db.query(Role).filter(
                or_(
                    Role.id == invitation_data.role,
                    Role.name == invitation_data.role
                )
            ).first()
        
        # Calculate expiration
        expires_at = datetime.utcnow() + timedelta(
            days=invitation_data.expires_in or 7
        )
        
        # Create invitation
        invitation = Invitation(
            tenant_id=tenant_id,
            organization_id=invitation_data.organization_id,
            email=invitation_data.email,
            role_id=role.id if role else None,
            role_name=role.name if role else invitation_data.role,
            invited_by=invited_by.id,
            message=invitation_data.message,
            expires_at=expires_at
        )
        
        self.db.add(invitation)
        self.db.commit()
        self.db.refresh(invitation)
        
        # Send invitation email
        await self._send_invitation_email(invitation, organization, invited_by)
        
        # Log audit event
        await self.audit_logger.log(
            action=AuditAction.INVITATION_CREATE,
            user_id=str(invited_by.id),
            resource_type="invitation",
            resource_id=str(invitation.id),
            details={
                "email": invitation_data.email,
                "organization": organization.name
            }
        )
        
        # Create response
        response = InvitationResponse(
            id=str(invitation.id),
            organization_id=str(invitation.organization_id),
            email=invitation.email,
            role=invitation.role_name,
            status=invitation.status,
            invited_by=str(invitation.invited_by),
            message=invitation.message,
            expires_at=invitation.expires_at,
            created_at=invitation.created_at,
            invite_url=invitation.generate_invite_url(settings.APP_URL),
            email_sent=invitation.email_sent
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
        tenant_id: str
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
                    expires_in=expires_in
                )
                
                response = await self.create_invitation(
                    invitation_data=invitation_data,
                    invited_by=invited_by,
                    tenant_id=tenant_id
                )
                
                successful.append(response)
                
            except Exception as e:
                failed.append({
                    "email": email,
                    "error": str(e)
                })
        
        return {
            "successful": successful,
            "failed": failed,
            "total_sent": len(successful),
            "total_failed": len(failed)
        }
    
    async def accept_invitation(
        self,
        token: str,
        user: Optional[User] = None,
        new_user_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Accept an invitation.
        """
        # Find invitation by token
        invitation = self.db.query(Invitation).filter(
            Invitation.token == token
        ).first()
        
        if not invitation:
            raise ValueError("Invalid invitation token")
        
        if not invitation.is_valid:
            if invitation.is_expired:
                raise ValueError("Invitation has expired")
            else:
                raise ValueError(f"Invitation is {invitation.status}")
        
        # Create user if needed
        if not user and new_user_data:
            user = User(
                email=invitation.email,
                name=new_user_data.get("name", invitation.email.split("@")[0]),
                password_hash=new_user_data.get("password_hash"),
                tenant_id=invitation.tenant_id,
                email_verified=True  # Auto-verify since they have the invitation
            )
            self.db.add(user)
            self.db.flush()
        elif not user:
            raise ValueError("User account required to accept invitation")
        
        # Verify email matches
        if user.email != invitation.email:
            raise ValueError("Invitation email does not match user email")
        
        # Add user to organization
        org_member = OrganizationMember(
            organization_id=invitation.organization_id,
            user_id=user.id,
            user_email=user.email,
            role=invitation.role_name or "member"
        )
        self.db.add(org_member)
        
        # Assign role if specified
        if invitation.role_id:
            user_role = UserRole(
                user_id=user.id,
                role_id=invitation.role_id,
                organization_id=invitation.organization_id,
                scope="organization"
            )
            self.db.add(user_role)
        
        # Update invitation status
        invitation.status = InvitationStatus.ACCEPTED.value
        invitation.accepted_by = user.id
        invitation.accepted_at = datetime.utcnow()
        
        self.db.commit()
        
        # Clear cache
        await self.cache.delete(f"user:organizations:{user.id}")
        
        # Log audit event
        await self.audit_logger.log(
            action=AuditAction.INVITATION_ACCEPT,
            user_id=str(user.id),
            resource_type="invitation",
            resource_id=str(invitation.id),
            details={
                "organization_id": str(invitation.organization_id)
            }
        )
        
        return {
            "success": True,
            "message": "Invitation accepted successfully",
            "user_id": str(user.id),
            "organization_id": str(invitation.organization_id),
            "role": invitation.role_name,
            "redirect_url": f"/dashboard/org/{invitation.organization_id}"
        }
    
    async def revoke_invitation(
        self,
        invitation_id: str,
        revoked_by: User
    ) -> bool:
        """
        Revoke a pending invitation.
        """
        invitation = self.db.query(Invitation).filter(
            Invitation.id == invitation_id
        ).first()
        
        if not invitation:
            raise ValueError("Invitation not found")
        
        if invitation.status != InvitationStatus.PENDING.value:
            raise ValueError(f"Cannot revoke invitation with status: {invitation.status}")
        
        # Update status
        invitation.status = InvitationStatus.REVOKED.value
        invitation.updated_at = datetime.utcnow()
        
        self.db.commit()
        
        # Log audit event
        await self.audit_logger.log(
            action=AuditAction.INVITATION_REVOKE,
            user_id=str(revoked_by.id),
            resource_type="invitation",
            resource_id=str(invitation.id),
            details={
                "email": invitation.email
            }
        )
        
        return True
    
    async def resend_invitation(
        self,
        invitation_id: str,
        resent_by: User
    ) -> InvitationResponse:
        """
        Resend an invitation email.
        """
        invitation = self.db.query(Invitation).filter(
            Invitation.id == invitation_id
        ).first()
        
        if not invitation:
            raise ValueError("Invitation not found")
        
        if invitation.status != InvitationStatus.PENDING.value:
            raise ValueError(f"Cannot resend invitation with status: {invitation.status}")
        
        # Get organization
        organization = self.db.query(Organization).filter(
            Organization.id == invitation.organization_id
        ).first()
        
        # Resend email
        await self._send_invitation_email(invitation, organization, resent_by)
        
        # Log audit event
        await self.audit_logger.log(
            action=AuditAction.INVITATION_RESEND,
            user_id=str(resent_by.id),
            resource_type="invitation",
            resource_id=str(invitation.id),
            details={
                "email": invitation.email
            }
        )
        
        # Create response
        response = InvitationResponse(
            id=str(invitation.id),
            organization_id=str(invitation.organization_id),
            email=invitation.email,
            role=invitation.role_name,
            status=invitation.status,
            invited_by=str(invitation.invited_by),
            message=invitation.message,
            expires_at=invitation.expires_at,
            created_at=invitation.created_at,
            invite_url=invitation.generate_invite_url(settings.APP_URL),
            email_sent=invitation.email_sent
        )
        
        return response
    
    async def _send_invitation_email(
        self,
        invitation: Invitation,
        organization: Organization,
        inviter: User
    ):
        """
        Send invitation email to the invitee.
        """
        try:
            # Update send attempts
            invitation.email_send_attempts += 1
            
            # Create email content
            subject = f"You're invited to join {organization.name} on Janua"
            
            html_content = f"""
            <html>
                <body style="font-family: Arial, sans-serif; line-height: 1.6;">
                    <h2>You're invited to {organization.name}!</h2>
                    
                    <p>{inviter.name or inviter.email} has invited you to join {organization.name} on Janua.</p>
                    
                    {f'<p><em>"{invitation.message}"</em></p>' if invitation.message else ''}
                    
                    <p>Click the button below to accept this invitation:</p>
                    
                    <p style="margin: 30px 0;">
                        <a href="{invitation.generate_invite_url(settings.APP_URL)}" 
                           style="background-color: #4CAF50; color: white; padding: 14px 28px; 
                                  text-decoration: none; border-radius: 4px; display: inline-block;">
                            Accept Invitation
                        </a>
                    </p>
                    
                    <p style="color: #666; font-size: 14px;">
                        This invitation will expire on {invitation.expires_at.strftime('%B %d, %Y at %I:%M %p UTC')}.
                    </p>
                    
                    <p style="color: #666; font-size: 14px;">
                        If you don't want to accept this invitation, you can safely ignore this email.
                    </p>
                    
                    <hr style="margin: 30px 0; border: none; border-top: 1px solid #eee;">
                    
                    <p style="color: #999; font-size: 12px;">
                        This invitation was sent to {invitation.email}. 
                        If you didn't expect this invitation, please ignore this email.
                    </p>
                </body>
            </html>
            """
            
            text_content = f"""
            You're invited to {organization.name}!
            
            {inviter.name or inviter.email} has invited you to join {organization.name} on Janua.
            
            {invitation.message if invitation.message else ''}
            
            Accept this invitation:
            {invitation.generate_invite_url(settings.APP_URL)}
            
            This invitation will expire on {invitation.expires_at.strftime('%B %d, %Y at %I:%M %p UTC')}.
            
            If you don't want to accept this invitation, you can safely ignore this email.
            """
            
            # Send email
            await self.email_service.send_email(
                to_email=invitation.email,
                subject=subject,
                html_content=html_content,
                text_content=text_content
            )
            
            # Update invitation
            invitation.email_sent = True
            invitation.email_sent_at = datetime.utcnow()
            
            self.db.commit()
            
        except Exception as e:
            # Log error but don't fail the invitation creation
            print(f"Failed to send invitation email: {str(e)}")
            
    def get_pending_invitations(
        self,
        organization_id: str,
        skip: int = 0,
        limit: int = 100
    ) -> List[Invitation]:
        """
        Get pending invitations for an organization.
        """
        return self.db.query(Invitation).filter(
            and_(
                Invitation.organization_id == organization_id,
                Invitation.status == InvitationStatus.PENDING.value
            )
        ).offset(skip).limit(limit).all()
    
    def cleanup_expired_invitations(self):
        """
        Mark expired invitations as expired.
        """
        expired_invitations = self.db.query(Invitation).filter(
            and_(
                Invitation.status == InvitationStatus.PENDING.value,
                Invitation.expires_at < datetime.utcnow()
            )
        ).all()
        
        for invitation in expired_invitations:
            invitation.status = InvitationStatus.EXPIRED.value
        
        self.db.commit()
        
        return len(expired_invitations)