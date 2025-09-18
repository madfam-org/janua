"""
Role-Based Access Control Service
Enterprise-grade RBAC with policy engine
"""
from typing import Optional, List, Dict, Any, Set
from uuid import UUID
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
import json
import re
from fastapi import HTTPException, status

from ..models import User, OrganizationMember

# Temporary mock classes until models are implemented
class RBACPolicy:
    """Mock RBACPolicy model"""
    id = None
    name = None
    resource_type = None
    resource_id = None
    permission = None
    conditions = None
    effect = 'allow'
    
class Permission:
    """Mock Permission model"""
    id = None
    name = None
    resource = None
    action = None
from ..core.redis_config import RedisService
from ..core.events import EventEmitter


class RBACService:
    """
    Comprehensive RBAC with 5-tier hierarchy and policy engine
    """

    # Role hierarchy definition
    ROLE_HIERARCHY = {
        'super_admin': 4,  # Platform-wide admin
        'owner': 3,        # Organization owner
        'admin': 2,        # Organization admin
        'member': 1,       # Regular member
        'viewer': 0        # Read-only access
    }

    # Permission patterns
    PERMISSIONS = {
        'super_admin': ['*'],  # All permissions
        'owner': [
            'org:*',
            'users:*',
            'billing:*',
            'settings:*',
            'integrations:*'
        ],
        'admin': [
            'org:read',
            'org:update',
            'users:*',
            'settings:read',
            'settings:update',
            'integrations:*'
        ],
        'member': [
            'org:read',
            'users:read',
            'users:update:self',
            'settings:read'
        ],
        'viewer': [
            'org:read',
            'users:read:self'
        ]
    }

    def __init__(self, db: Session, redis: RedisService):
        self.db = db
        self.redis = redis
        self.events = EventEmitter()

    def get_role_level(self, role: str) -> int:
        """Get numeric level for role"""
        return self.ROLE_HIERARCHY.get(role, -1)

    def has_higher_role(self, user_role: str, required_role: str) -> bool:
        """Check if user role is higher or equal to required"""
        return self.get_role_level(user_role) >= self.get_role_level(required_role)

    async def check_permission(
        self,
        user_id: UUID,
        organization_id: Optional[UUID],
        permission: str,
        resource_id: Optional[UUID] = None,
        context: Optional[Dict] = None
    ) -> bool:
        """
        Check if user has specific permission
        Supports wildcards and context-based policies
        """
        # Check cache
        cache_key = f"rbac:{user_id}:{organization_id}:{permission}"
        cached = await self.redis.get(cache_key)

        if cached is not None:
            return cached == 'true'

        # Get user role
        user_role = await self.get_user_role(user_id, organization_id)

        if not user_role:
            await self.redis.set(cache_key, 'false', ex=300)
            return False

        # Check base permissions
        has_permission = self._check_role_permission(user_role, permission)

        # Check policy engine for conditional permissions
        if not has_permission and context:
            has_permission = await self._evaluate_policies(
                user_id,
                organization_id,
                permission,
                resource_id,
                context
            )

        # Cache result
        await self.redis.set(
            cache_key,
            'true' if has_permission else 'false',
            ex=300
        )

        return has_permission

    async def get_user_role(
        self,
        user_id: UUID,
        organization_id: Optional[UUID]
    ) -> Optional[str]:
        """Get user's role in organization"""
        # Platform super admin check
        user = self.db.query(User).filter(User.id == user_id).first()
        if user and user.is_super_admin:
            return 'super_admin'

        if not organization_id:
            return None

        # Organization member role
        member = self.db.query(OrganizationMember).filter(
            and_(
                OrganizationMember.user_id == user_id,
                OrganizationMember.organization_id == organization_id,
                OrganizationMember.status == 'active'
            )
        ).first()

        return member.role if member else None

    def _check_role_permission(self, role: str, permission: str) -> bool:
        """Check if role has permission (with wildcard support)"""
        role_permissions = self.PERMISSIONS.get(role, [])

        for role_perm in role_permissions:
            if self._match_permission(role_perm, permission):
                return True

        return False

    def _match_permission(self, pattern: str, permission: str) -> bool:
        """Match permission against pattern with wildcard support"""
        # Direct match
        if pattern == permission:
            return True

        # Wildcard match
        if '*' in pattern:
            # Convert pattern to regex
            regex_pattern = pattern.replace('*', '.*')
            regex_pattern = f"^{regex_pattern}$"
            return bool(re.match(regex_pattern, permission))

        return False

    async def _evaluate_policies(
        self,
        user_id: UUID,
        organization_id: Optional[UUID],
        permission: str,
        resource_id: Optional[UUID],
        context: Dict
    ) -> bool:
        """Evaluate conditional policies"""
        policies = self.db.query(RBACPolicy).filter(
            and_(
                RBACPolicy.organization_id == organization_id,
                RBACPolicy.permission == permission,
                RBACPolicy.is_active == True
            )
        ).all()

        for policy in policies:
            if self._evaluate_policy(policy, user_id, resource_id, context):
                return True

        return False

    def _evaluate_policy(
        self,
        policy: RBACPolicy,
        user_id: UUID,
        resource_id: Optional[UUID],
        context: Dict
    ) -> bool:
        """Evaluate single policy conditions"""
        conditions = policy.conditions or {}

        # Check user condition
        if 'user_id' in conditions:
            if str(user_id) != conditions['user_id']:
                return False

        # Check resource condition
        if 'resource_id' in conditions:
            if not resource_id or str(resource_id) != conditions['resource_id']:
                return False

        # Check time-based conditions
        if 'time_range' in conditions:
            if not self._check_time_range(conditions['time_range']):
                return False

        # Check custom conditions
        if 'custom' in conditions:
            for key, value in conditions['custom'].items():
                if context.get(key) != value:
                    return False

        return True

    def _check_time_range(self, time_range: Dict) -> bool:
        """Check if current time is within range"""
        now = datetime.utcnow()

        if 'start' in time_range:
            start = datetime.fromisoformat(time_range['start'])
            if now < start:
                return False

        if 'end' in time_range:
            end = datetime.fromisoformat(time_range['end'])
            if now > end:
                return False

        return True

    async def get_user_permissions(
        self,
        user_id: UUID,
        organization_id: Optional[UUID]
    ) -> Set[str]:
        """Get all permissions for user"""
        role = await self.get_user_role(user_id, organization_id)

        if not role:
            return set()

        # Get base permissions
        permissions = set(self.PERMISSIONS.get(role, []))

        # Add policy-based permissions
        if organization_id:
            policies = self.db.query(RBACPolicy).filter(
                and_(
                    RBACPolicy.organization_id == organization_id,
                    RBACPolicy.is_active == True
                )
            ).all()

            for policy in policies:
                if policy.conditions and 'user_id' in policy.conditions:
                    if str(user_id) == policy.conditions['user_id']:
                        permissions.add(policy.permission)

        return permissions

    async def create_policy(
        self,
        organization_id: UUID,
        name: str,
        permission: str,
        conditions: Dict,
        created_by: UUID
    ) -> RBACPolicy:
        """Create conditional access policy"""
        policy = RBACPolicy(
            organization_id=organization_id,
            name=name,
            permission=permission,
            conditions=conditions,
            is_active=True,
            created_by=created_by,
            created_at=datetime.utcnow()
        )

        self.db.add(policy)
        self.db.commit()
        self.db.refresh(policy)

        # Clear cache
        await self._clear_rbac_cache(organization_id)

        # Emit event
        await self.events.emit('policy:created', policy)

        return policy

    async def update_policy(
        self,
        policy_id: UUID,
        updates: Dict,
        updated_by: UUID
    ) -> RBACPolicy:
        """Update existing policy"""
        policy = self.db.query(RBACPolicy).filter(
            RBACPolicy.id == policy_id
        ).first()

        if not policy:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Policy not found"
            )

        # Update fields
        for key, value in updates.items():
            if hasattr(policy, key):
                setattr(policy, key, value)

        policy.updated_at = datetime.utcnow()
        policy.updated_by = updated_by

        self.db.commit()
        self.db.refresh(policy)

        # Clear cache
        await self._clear_rbac_cache(policy.organization_id)

        # Emit event
        await self.events.emit('policy:updated', policy)

        return policy

    async def delete_policy(self, policy_id: UUID) -> None:
        """Delete policy (soft delete)"""
        policy = self.db.query(RBACPolicy).filter(
            RBACPolicy.id == policy_id
        ).first()

        if not policy:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Policy not found"
            )

        policy.is_active = False
        policy.deleted_at = datetime.utcnow()

        self.db.commit()

        # Clear cache
        await self._clear_rbac_cache(policy.organization_id)

        # Emit event
        await self.events.emit('policy:deleted', policy)

    async def _clear_rbac_cache(self, organization_id: UUID) -> None:
        """Clear all RBAC cache for organization"""
        pattern = f"rbac:*:{organization_id}:*"
        keys = await self.redis.keys(pattern)
        if keys:
            await self.redis.delete(*keys)

    async def enforce_permission(
        self,
        user_id: UUID,
        organization_id: Optional[UUID],
        permission: str,
        resource_id: Optional[UUID] = None,
        context: Optional[Dict] = None
    ) -> None:
        """Enforce permission or raise exception"""
        has_permission = await self.check_permission(
            user_id,
            organization_id,
            permission,
            resource_id,
            context
        )

        if not has_permission:
            # Log unauthorized attempt
            await self.events.emit('rbac:unauthorized', {
                'user_id': user_id,
                'organization_id': organization_id,
                'permission': permission,
                'resource_id': resource_id,
                'context': context
            })

            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied: {permission}"
            )

    async def bulk_check_permissions(
        self,
        user_id: UUID,
        organization_id: Optional[UUID],
        permissions: List[str]
    ) -> Dict[str, bool]:
        """Check multiple permissions at once"""
        results = {}

        for permission in permissions:
            results[permission] = await self.check_permission(
                user_id,
                organization_id,
                permission
            )

        return results