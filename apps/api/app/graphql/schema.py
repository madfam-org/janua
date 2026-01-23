"""
GraphQL schema definition for Janua API.
"""

import json
from datetime import datetime
from typing import AsyncGenerator, List, Optional

import strawberry
from app.models.organization import Organization as OrgModel
from strawberry.types import Info

from app.models.invitation import Invitation as InvitationModel
from app.models.policy import Policy as PolicyModel
from app.models.policy import Role as RoleModel
from app.models.user import User as UserModel
from app.services.auth_service import AuthService
from app.services.policy_engine import PolicyEngine

# GraphQL Types


@strawberry.type
class User:
    id: str
    email: str
    name: Optional[str]
    email_verified: bool
    created_at: datetime
    updated_at: datetime
    organization_ids: List[str]
    roles: List[str]

    @strawberry.field
    async def organizations(self, info: Info) -> List["Organization"]:
        db = info.context["db"]
        orgs = db.query(OrgModel).filter(OrgModel.members.any(user_id=self.id)).all()
        return [Organization.from_orm(org) for org in orgs]

    @strawberry.field
    async def permissions(self, info: Info) -> List[str]:
        db = info.context["db"]
        engine = PolicyEngine(db)
        return engine.get_user_permissions(self.id, info.context["tenant_id"])


@strawberry.type
class Organization:
    id: str
    name: str
    slug: str
    description: Optional[str]
    created_at: datetime
    updated_at: datetime
    member_count: int

    @strawberry.field
    async def members(self, info: Info) -> List[User]:
        db = info.context["db"]
        members = db.query(UserModel).filter(UserModel.organizations.any(id=self.id)).all()
        return [User.from_orm(member) for member in members]

    @strawberry.field
    async def invitations(self, info: Info, status: Optional[str] = None) -> List["Invitation"]:
        db = info.context["db"]
        query = db.query(InvitationModel).filter(InvitationModel.organization_id == self.id)
        if status:
            query = query.filter(InvitationModel.status == status)
        invitations = query.all()
        return [Invitation.from_orm(inv) for inv in invitations]


@strawberry.type
class Policy:
    id: str
    name: str
    description: Optional[str]
    effect: str
    priority: int
    enabled: bool
    target_type: Optional[str]
    target_id: Optional[str]
    resource_type: Optional[str]
    resource_pattern: Optional[str]
    actions: List[str]
    created_at: datetime
    updated_at: datetime

    @strawberry.field
    async def evaluations_count(self, info: Info) -> int:
        db = info.context["db"]
        from app.models.policy import PolicyEvaluation

        return db.query(PolicyEvaluation).filter(PolicyEvaluation.policy_id == self.id).count()


@strawberry.type
class Role:
    id: str
    name: str
    description: Optional[str]
    permissions: List[str]
    is_system: bool
    created_at: datetime
    updated_at: datetime

    @strawberry.field
    async def users_count(self, info: Info) -> int:
        db = info.context["db"]
        from app.models.policy import UserRole

        return db.query(UserRole).filter(UserRole.role_id == self.id).count()


@strawberry.type
class Invitation:
    id: str
    email: str
    organization_id: str
    role_name: Optional[str]
    status: str
    message: Optional[str]
    expires_at: datetime
    created_at: datetime
    email_sent: bool

    @strawberry.field
    async def organization(self, info: Info) -> Organization:
        db = info.context["db"]
        org = db.query(OrgModel).filter(OrgModel.id == self.organization_id).first()
        return Organization.from_orm(org)

    @strawberry.field
    async def inviter(self, info: Info) -> Optional[User]:
        db = info.context["db"]
        if self.invited_by:
            user = db.query(UserModel).filter(UserModel.id == self.invited_by).first()
            return User.from_orm(user) if user else None
        return None


@strawberry.type
class Session:
    id: str
    user_id: str
    token: str
    expires_at: datetime
    created_at: datetime
    ip_address: Optional[str]
    user_agent: Optional[str]

    @strawberry.field
    async def user(self, info: Info) -> User:
        db = info.context["db"]
        user = db.query(UserModel).filter(UserModel.id == self.user_id).first()
        return User.from_orm(user)


@strawberry.type
class AuditLog:
    id: str
    action: str
    user_id: Optional[str]
    resource_type: Optional[str]
    resource_id: Optional[str]
    details: Optional[str]
    ip_address: Optional[str]
    timestamp: datetime

    @strawberry.field
    async def user(self, info: Info) -> Optional[User]:
        if not self.user_id:
            return None
        db = info.context["db"]
        user = db.query(UserModel).filter(UserModel.id == self.user_id).first()
        return User.from_orm(user) if user else None


@strawberry.type
class PolicyEvaluation:
    allowed: bool
    reasons: List[str]
    applied_policies: List[str]
    evaluation_time_ms: int


# Input Types


@strawberry.input
class SignUpInput:
    email: str
    password: str
    name: Optional[str] = None
    organization_name: Optional[str] = None


@strawberry.input
class SignInInput:
    email: str
    password: str


@strawberry.input
class CreateOrganizationInput:
    name: str
    slug: str
    description: Optional[str] = None


@strawberry.input
class CreateInvitationInput:
    organization_id: str
    email: str
    role: Optional[str] = None
    message: Optional[str] = None
    expires_in_days: Optional[int] = 7


@strawberry.input
class CreatePolicyInput:
    name: str
    description: Optional[str] = None
    rules: str  # JSON string
    effect: str = "allow"
    priority: int = 0
    target_type: Optional[str] = None
    target_id: Optional[str] = None
    resource_type: Optional[str] = None
    resource_pattern: Optional[str] = None
    actions: Optional[List[str]] = None


@strawberry.input
class EvaluatePolicyInput:
    subject: str
    action: str
    resource: str
    context: Optional[str] = None  # JSON string


# Mutations


@strawberry.type
class Mutation:
    @strawberry.mutation
    async def sign_up(self, info: Info, input: SignUpInput) -> User:
        """Create a new user account."""
        db = info.context["db"]
        auth_service = AuthService(db)

        user = await auth_service.sign_up(
            email=input.email, password=input.password, name=input.name
        )

        if input.organization_name:
            # Create organization for user
            org = OrgModel(
                name=input.organization_name,
                slug=input.organization_name.lower().replace(" ", "-"),
                owner_id=user.id,
                tenant_id=user.tenant_id,
            )
            db.add(org)
            db.commit()

        return User.from_orm(user)

    @strawberry.mutation
    async def sign_in(self, info: Info, input: SignInInput) -> Session:
        """Authenticate user and create session."""
        db = info.context["db"]
        auth_service = AuthService(db)

        session = await auth_service.sign_in(
            email=input.email,
            password=input.password,
            ip_address=info.context.get("ip_address"),
            user_agent=info.context.get("user_agent"),
        )

        return Session.from_orm(session)

    @strawberry.mutation
    async def create_organization(self, info: Info, input: CreateOrganizationInput) -> Organization:
        """Create a new organization."""
        db = info.context["db"]
        user = info.context["user"]

        if not user:
            raise Exception("Authentication required")

        org = OrgModel(
            name=input.name,
            slug=input.slug,
            description=input.description,
            owner_id=user.id,
            tenant_id=user.tenant_id,
        )

        db.add(org)
        db.commit()
        db.refresh(org)

        return Organization.from_orm(org)

    @strawberry.mutation
    async def create_invitation(self, info: Info, input: CreateInvitationInput) -> Invitation:
        """Create an invitation to join an organization."""
        db = info.context["db"]
        user = info.context["user"]

        if not user:
            raise Exception("Authentication required")

        from app.services.invitation_service import InvitationService

        service = InvitationService(db)

        from app.models.invitation import InvitationCreate

        invitation_data = InvitationCreate(
            organization_id=input.organization_id,
            email=input.email,
            role=input.role,
            message=input.message,
            expires_in=input.expires_in_days,
        )

        invitation = await service.create_invitation(
            invitation_data=invitation_data, invited_by=user, tenant_id=user.tenant_id
        )

        return Invitation.from_orm(invitation)

    @strawberry.mutation
    async def create_policy(self, info: Info, input: CreatePolicyInput) -> Policy:
        """Create a new policy."""
        db = info.context["db"]
        user = info.context["user"]

        if not user or not user.is_admin:
            raise Exception("Admin access required")

        policy = PolicyModel(
            tenant_id=user.tenant_id,
            name=input.name,
            description=input.description,
            rules=json.loads(input.rules) if input.rules else {},
            effect=input.effect,
            priority=input.priority,
            target_type=input.target_type,
            target_id=input.target_id,
            resource_type=input.resource_type,
            resource_pattern=input.resource_pattern,
            actions=input.actions,
        )

        db.add(policy)
        db.commit()
        db.refresh(policy)

        return Policy.from_orm(policy)

    @strawberry.mutation
    async def evaluate_policy(self, info: Info, input: EvaluatePolicyInput) -> PolicyEvaluation:
        """Evaluate policies for a given request."""
        db = info.context["db"]
        user = info.context["user"]

        if not user:
            raise Exception("Authentication required")

        from app.models.policy import PolicyEvaluateRequest
        from app.services.policy_engine import PolicyEngine

        engine = PolicyEngine(db)

        request = PolicyEvaluateRequest(
            subject=input.subject,
            action=input.action,
            resource=input.resource,
            context=json.loads(input.context) if input.context else None,
        )

        result = await engine.evaluate(request=request, tenant_id=user.tenant_id)

        return PolicyEvaluation(
            allowed=result.allowed,
            reasons=result.reasons,
            applied_policies=result.applied_policies,
            evaluation_time_ms=result.evaluation_time_ms,
        )


# Queries


@strawberry.type
class Query:
    @strawberry.field
    async def me(self, info: Info) -> Optional[User]:
        """Get current authenticated user."""
        user = info.context.get("user")
        return User.from_orm(user) if user else None

    @strawberry.field
    async def user(self, info: Info, id: str) -> Optional[User]:
        """Get user by ID."""
        db = info.context["db"]
        user = db.query(UserModel).filter(UserModel.id == id).first()
        return User.from_orm(user) if user else None

    @strawberry.field
    async def users(self, info: Info, limit: int = 100, offset: int = 0) -> List[User]:
        """List users."""
        db = info.context["db"]
        users = db.query(UserModel).offset(offset).limit(limit).all()
        return [User.from_orm(user) for user in users]

    @strawberry.field
    async def organization(self, info: Info, id: str) -> Optional[Organization]:
        """Get organization by ID."""
        db = info.context["db"]
        org = db.query(OrgModel).filter(OrgModel.id == id).first()
        return Organization.from_orm(org) if org else None

    @strawberry.field
    async def organizations(
        self, info: Info, limit: int = 100, offset: int = 0
    ) -> List[Organization]:
        """List organizations."""
        db = info.context["db"]
        orgs = db.query(OrgModel).offset(offset).limit(limit).all()
        return [Organization.from_orm(org) for org in orgs]

    @strawberry.field
    async def policies(
        self, info: Info, enabled: Optional[bool] = None, limit: int = 100, offset: int = 0
    ) -> List[Policy]:
        """List policies."""
        db = info.context["db"]
        query = db.query(PolicyModel)

        if enabled is not None:
            query = query.filter(PolicyModel.enabled == enabled)

        policies = query.offset(offset).limit(limit).all()
        return [Policy.from_orm(policy) for policy in policies]

    @strawberry.field
    async def roles(self, info: Info, limit: int = 100, offset: int = 0) -> List[Role]:
        """List roles."""
        db = info.context["db"]
        roles = db.query(RoleModel).offset(offset).limit(limit).all()
        return [Role.from_orm(role) for role in roles]

    @strawberry.field
    async def invitations(
        self,
        info: Info,
        organization_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Invitation]:
        """List invitations."""
        db = info.context["db"]
        query = db.query(InvitationModel)

        if organization_id:
            query = query.filter(InvitationModel.organization_id == organization_id)

        if status:
            query = query.filter(InvitationModel.status == status)

        invitations = query.offset(offset).limit(limit).all()
        return [Invitation.from_orm(inv) for inv in invitations]

    @strawberry.field
    async def audit_logs(
        self,
        info: Info,
        user_id: Optional[str] = None,
        action: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[AuditLog]:
        """Query audit logs."""
        db = info.context["db"]
        from app.models import AuditLog as AuditLogModel

        query = db.query(AuditLogModel)

        if user_id:
            query = query.filter(AuditLogModel.user_id == user_id)

        if action:
            query = query.filter(AuditLogModel.action == action)

        logs = query.order_by(AuditLogModel.timestamp.desc()).offset(offset).limit(limit).all()
        return [AuditLog.from_orm(log) for log in logs]


# Subscriptions


@strawberry.type
class Subscription:
    @strawberry.subscription
    async def organization_events(
        self, info: Info, organization_id: str
    ) -> AsyncGenerator[str, None]:
        """Subscribe to organization events."""
        # This would connect to a message queue or event stream
        # For now, it's a placeholder
        import asyncio

        while True:
            await asyncio.sleep(5)
            yield f"Event for org {organization_id} at {datetime.utcnow()}"

    @strawberry.subscription
    async def policy_evaluations(
        self, info: Info, user_id: Optional[str] = None
    ) -> AsyncGenerator[PolicyEvaluation, None]:
        """Subscribe to policy evaluation events."""
        # Placeholder for real-time policy evaluation monitoring
        import asyncio

        while True:
            await asyncio.sleep(10)
            yield PolicyEvaluation(
                allowed=True,
                reasons=["Test evaluation"],
                applied_policies=["policy_123"],
                evaluation_time_ms=5,
            )


# Create schema
schema = strawberry.Schema(
    query=Query,
    mutation=Mutation,
    subscription=Subscription,
    extensions=[
        # Add any GraphQL extensions here
    ],
)
