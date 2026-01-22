"""
Organization Member Service
Ported from TypeScript implementation with full feature parity
"""
from typing import Optional, List, Dict
from uuid import UUID, uuid4
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_
import secrets
import json
from fastapi import HTTPException, status

from ..models import OrganizationMember, OrganizationInvitation
from ..core.redis_config import RedisService
from ..core.events import EventEmitter


class OrganizationMemberService:
    """
    Complete organization member lifecycle management
    Handles members, invitations, and permissions
    """

    def __init__(self, db: Session, redis: RedisService):
        self.db = db
        self.redis = redis
        self.events = EventEmitter()

    async def add_member(
        self,
        organization_id: UUID,
        user_id: UUID,
        role: str,
        invited_by: UUID,
        metadata: Optional[Dict] = None,
    ) -> OrganizationMember:
        """Add a new member to organization"""
        # Check if already member
        existing = (
            self.db.query(OrganizationMember)
            .filter(
                and_(
                    OrganizationMember.organization_id == organization_id,
                    OrganizationMember.user_id == user_id,
                )
            )
            .first()
        )

        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="User is already a member of this organization",
            )

        # Create member
        member = OrganizationMember(
            id=uuid4(),
            organization_id=organization_id,
            user_id=user_id,
            role=role,
            status="active",
            joined_at=datetime.utcnow(),
            invited_by=invited_by,
            metadata=metadata or {},
        )

        self.db.add(member)
        self.db.commit()
        self.db.refresh(member)

        # Clear cache
        await self.redis.delete(f"org_members:{organization_id}")

        # Emit event
        await self.events.emit("member:added", member)

        return member

    async def remove_member(self, organization_id: UUID, user_id: UUID, removed_by: UUID) -> None:
        """Remove member from organization"""
        member = (
            self.db.query(OrganizationMember)
            .filter(
                and_(
                    OrganizationMember.organization_id == organization_id,
                    OrganizationMember.user_id == user_id,
                )
            )
            .first()
        )

        if not member:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")

        # Prevent removing last owner
        if member.role == "owner":
            owner_count = (
                self.db.query(OrganizationMember)
                .filter(
                    and_(
                        OrganizationMember.organization_id == organization_id,
                        OrganizationMember.role == "owner",
                        OrganizationMember.status == "active",
                    )
                )
                .count()
            )

            if owner_count <= 1:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot remove the last owner of the organization",
                )

        # Soft delete
        member.status = "removed"
        member.removed_at = datetime.utcnow()
        member.removed_by = removed_by

        if not member.metadata:
            member.metadata = {}
        member.metadata["removal"] = {
            "removed_by": str(removed_by),
            "removed_at": datetime.utcnow().isoformat(),
        }

        self.db.commit()

        # Clear cache
        await self.redis.delete(f"org_members:{organization_id}")

        # Emit event
        await self.events.emit("member:removed", member)

    async def update_member_role(
        self, organization_id: UUID, user_id: UUID, new_role: str, updated_by: UUID
    ) -> OrganizationMember:
        """Update member's role"""
        member = (
            self.db.query(OrganizationMember)
            .filter(
                and_(
                    OrganizationMember.organization_id == organization_id,
                    OrganizationMember.user_id == user_id,
                    OrganizationMember.status == "active",
                )
            )
            .first()
        )

        if not member:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Active member not found"
            )

        old_role = member.role

        # Prevent demoting last owner
        if old_role == "owner" and new_role != "owner":
            owner_count = (
                self.db.query(OrganizationMember)
                .filter(
                    and_(
                        OrganizationMember.organization_id == organization_id,
                        OrganizationMember.role == "owner",
                        OrganizationMember.status == "active",
                    )
                )
                .count()
            )

            if owner_count <= 1:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot demote the last owner"
                )

        # Update role
        member.role = new_role
        member.updated_at = datetime.utcnow()

        if not member.metadata:
            member.metadata = {}
        member.metadata["last_role_change"] = {
            "from": old_role,
            "to": new_role,
            "updated_by": str(updated_by),
            "updated_at": datetime.utcnow().isoformat(),
        }

        self.db.commit()
        self.db.refresh(member)

        # Clear cache
        await self.redis.delete(f"org_members:{organization_id}")
        await self.redis.delete(f"member_perms:{user_id}:{organization_id}")

        # Emit event
        await self.events.emit(
            "member:role_updated", {"member": member, "old_role": old_role, "new_role": new_role}
        )

        return member

    async def create_invitation(
        self,
        organization_id: UUID,
        email: str,
        role: str,
        invited_by: UUID,
        expires_in_days: int = 7,
    ) -> OrganizationInvitation:
        """Create invitation for new member"""
        # Check for existing pending invitation
        existing = (
            self.db.query(OrganizationInvitation)
            .filter(
                and_(
                    OrganizationInvitation.organization_id == organization_id,
                    OrganizationInvitation.email == email,
                    OrganizationInvitation.status == "pending",
                )
            )
            .first()
        )

        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="An invitation already exists for this email",
            )

        # Generate secure token
        token = secrets.urlsafe_token(32)

        # Create invitation
        invitation = OrganizationInvitation(
            id=uuid4(),
            organization_id=organization_id,
            email=email,
            role=role,
            token=token,
            status="pending",
            expires_at=datetime.utcnow() + timedelta(days=expires_in_days),
            invited_by=invited_by,
            created_at=datetime.utcnow(),
        )

        self.db.add(invitation)
        self.db.commit()
        self.db.refresh(invitation)

        # Cache invitation
        await self.redis.set(
            f"invitation:{token}",
            json.dumps(
                {
                    "id": str(invitation.id),
                    "organization_id": str(invitation.organization_id),
                    "email": invitation.email,
                    "role": invitation.role,
                    "expires_at": invitation.expires_at.isoformat(),
                }
            ),
            ex=expires_in_days * 86400,
        )

        # Emit event
        await self.events.emit("invitation:created", invitation)

        return invitation

    async def accept_invitation(self, token: str, user_id: UUID) -> OrganizationMember:
        """Accept invitation and become member"""
        # Check cache first
        cached = await self.redis.get(f"invitation:{token}")

        if cached:
            invitation_data = json.loads(cached)
            invitation = (
                self.db.query(OrganizationInvitation)
                .filter(OrganizationInvitation.id == UUID(invitation_data["id"]))
                .first()
            )
        else:
            invitation = (
                self.db.query(OrganizationInvitation)
                .filter(OrganizationInvitation.token == token)
                .first()
            )

        if not invitation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Invalid or expired invitation"
            )

        # Check expiration
        if invitation.expires_at < datetime.utcnow():
            raise HTTPException(status_code=status.HTTP_410_GONE, detail="Invitation has expired")

        # Check if already used
        if invitation.status != "pending":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Invitation has already been used"
            )

        # Create member in transaction
        try:
            # Add member
            member = OrganizationMember(
                id=uuid4(),
                organization_id=invitation.organization_id,
                user_id=user_id,
                role=invitation.role,
                status="active",
                joined_at=datetime.utcnow(),
                invited_by=invitation.invited_by,
                metadata={"invitation_id": str(invitation.id)},
            )

            self.db.add(member)

            # Update invitation
            invitation.status = "accepted"
            invitation.accepted_at = datetime.utcnow()
            invitation.accepted_by = user_id

            self.db.commit()
            self.db.refresh(member)

            # Clear cache
            await self.redis.delete(f"invitation:{token}")
            await self.redis.delete(f"org_members:{invitation.organization_id}")

            # Emit events
            await self.events.emit("invitation:accepted", invitation)
            await self.events.emit("member:added", member)

            return member

        except Exception as e:
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to accept invitation: {str(e)}",
            )

    async def get_members(
        self, organization_id: UUID, include_removed: bool = False
    ) -> List[OrganizationMember]:
        """Get organization members"""
        # Check cache
        cache_key = f"org_members:{organization_id}{'_all' if include_removed else ''}"
        cached = await self.redis.get(cache_key)

        if cached:
            return json.loads(cached)

        # Query database
        query = self.db.query(OrganizationMember).filter(
            OrganizationMember.organization_id == organization_id
        )

        if not include_removed:
            query = query.filter(OrganizationMember.status == "active")

        members = query.all()

        # Cache result
        await self.redis.set(
            cache_key, json.dumps([m.dict() for m in members]), ex=300  # 5 minutes
        )

        return members

    async def has_permission(
        self, user_id: UUID, organization_id: UUID, required_role: str
    ) -> bool:
        """Check if user has required role or higher"""
        # Role hierarchy
        role_hierarchy = {"viewer": 0, "member": 1, "admin": 2, "owner": 3, "super_admin": 4}

        # Check cache
        cache_key = f"member_perms:{user_id}:{organization_id}"
        cached = await self.redis.get(cache_key)

        if cached:
            member_role = cached
        else:
            member = (
                self.db.query(OrganizationMember)
                .filter(
                    and_(
                        OrganizationMember.organization_id == organization_id,
                        OrganizationMember.user_id == user_id,
                        OrganizationMember.status == "active",
                    )
                )
                .first()
            )

            if not member:
                return False

            member_role = member.role

            # Cache for 5 minutes
            await self.redis.set(cache_key, member_role, ex=300)

        # Compare hierarchy
        return role_hierarchy.get(member_role, -1) >= role_hierarchy.get(required_role, 99)
