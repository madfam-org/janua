"""
GraphQL Resolvers for Janua Platform
Implements all queries, mutations, and subscriptions defined in the schema
"""

from typing import Dict, List, Optional
from graphql import GraphQLError

from app.auth import require_permissions
from app.services import (
    UserService,
    OrganizationService,
    TeamService,
    SessionManager,
    AuditService,
    PolicyEngine,
    WebhookService,
    BillingService,
    AnalyticsService,
    MFAService,
    InvitationsService,
    RateLimiter
)
from app.exceptions import ValidationError, AuthenticationError

# Initialize services
user_service = UserService()
org_service = OrganizationService()
team_service = TeamService()
session_manager = SessionManager()
audit_service = AuditService()
policy_engine = PolicyEngine()
webhook_service = WebhookService()
billing_service = BillingService()
analytics_service = AnalyticsService()
mfa_service = MFAService()
invitations_service = InvitationsService()
rate_limiter = RateLimiter()

# ==================== QUERY RESOLVERS ====================

class Query:
    """GraphQL Query Resolvers"""
    
    # User queries
    async def me(self, info) -> Optional[Dict]:
        """Get current authenticated user"""
        user = info.context.get("user")
        if not user:
            return None
        
        return user_service.get_user(user.id)
    
    async def user(self, info, id: str) -> Optional[Dict]:
        """Get user by ID"""
        current_user = info.context.get("user")
        if not current_user:
            raise GraphQLError("Authentication required")
        
        # Check permissions
        if current_user.id != id:
            await policy_engine.enforce(
                principal=current_user.id,
                action="users:read",
                resource=f"user:{id}"
            )
        
        return user_service.get_user(id)
    
    async def users(self, info, pagination: Dict = None) -> List[Dict]:
        """List users with pagination"""
        current_user = info.context.get("user")
        if not current_user:
            raise GraphQLError("Authentication required")
        
        # Require admin permissions
        await require_permissions(current_user, ["users:list"])
        
        limit = pagination.get("limit", 20) if pagination else 20
        offset = pagination.get("offset", 0) if pagination else 0
        
        return user_service.list_users(limit=limit, offset=offset)
    
    # Organization queries
    async def organization(self, info, id: str) -> Optional[Dict]:
        """Get organization by ID"""
        current_user = info.context.get("user")
        if not current_user:
            raise GraphQLError("Authentication required")
        
        # Check if user is member
        is_member = await org_service.is_member(id, current_user.id)
        if not is_member:
            await policy_engine.enforce(
                principal=current_user.id,
                action="organizations:read",
                resource=f"org:{id}"
            )
        
        return org_service.get_organization(id)
    
    async def organization_by_slug(self, info, slug: str) -> Optional[Dict]:
        """Get organization by slug"""
        return org_service.get_organization_by_slug(slug)
    
    async def my_organizations(self, info) -> List[Dict]:
        """Get current user's organizations"""
        current_user = info.context.get("user")
        if not current_user:
            raise GraphQLError("Authentication required")
        
        return org_service.get_user_organizations(current_user.id)
    
    # Team queries
    async def team(self, info, id: str) -> Optional[Dict]:
        """Get team by ID"""
        current_user = info.context.get("user")
        if not current_user:
            raise GraphQLError("Authentication required")
        
        team = team_service.get_team(id)
        if not team:
            return None
        
        # Check permissions
        is_member = await org_service.is_member(team["organization_id"], current_user.id)
        if not is_member:
            raise GraphQLError("Access denied")
        
        return team
    
    async def organization_teams(self, info, organization_id: str) -> List[Dict]:
        """Get organization's teams"""
        current_user = info.context.get("user")
        if not current_user:
            raise GraphQLError("Authentication required")
        
        # Check permissions
        is_member = await org_service.is_member(organization_id, current_user.id)
        if not is_member:
            raise GraphQLError("Access denied")
        
        return team_service.get_organization_teams(organization_id)
    
    # Session queries
    async def my_sessions(self, info) -> List[Dict]:
        """Get current user's sessions"""
        current_user = info.context.get("user")
        if not current_user:
            raise GraphQLError("Authentication required")
        
        return session_manager.get_user_sessions(current_user.id)
    
    async def session(self, info, id: str) -> Optional[Dict]:
        """Get session by ID"""
        current_user = info.context.get("user")
        if not current_user:
            raise GraphQLError("Authentication required")
        
        session = session_manager.get_session(id)
        if not session or session["user_id"] != current_user.id:
            raise GraphQLError("Session not found")
        
        return session
    
    # Audit queries
    async def audit_logs(
        self,
        info,
        organization_id: str = None,
        user_id: str = None,
        event_type: str = None,
        date_range: Dict = None,
        pagination: Dict = None
    ) -> List[Dict]:
        """Query audit logs with filters"""
        current_user = info.context.get("user")
        if not current_user:
            raise GraphQLError("Authentication required")
        
        # Check permissions
        if organization_id:
            is_admin = await org_service.is_admin(organization_id, current_user.id)
            if not is_admin:
                raise GraphQLError("Admin access required")
        elif user_id and user_id != current_user.id:
            raise GraphQLError("Access denied")
        
        filters = {
            "organization_id": organization_id,
            "user_id": user_id or current_user.id,
            "event_type": event_type
        }
        
        if date_range:
            filters["start_date"] = date_range.get("start")
            filters["end_date"] = date_range.get("end")
        
        limit = pagination.get("limit", 20) if pagination else 20
        offset = pagination.get("offset", 0) if pagination else 0
        
        return audit_service.query_logs(filters, limit=limit, offset=offset)
    
    # Analytics queries
    async def analytics(
        self,
        info,
        organization_id: str = None,
        date_range: Dict = None
    ) -> Dict:
        """Get comprehensive analytics"""
        current_user = info.context.get("user")
        if not current_user:
            raise GraphQLError("Authentication required")
        
        # Check permissions
        if organization_id:
            is_admin = await org_service.is_admin(organization_id, current_user.id)
            if not is_admin:
                raise GraphQLError("Admin access required")
        else:
            # Global analytics require super admin
            await require_permissions(current_user, ["analytics:global"])
        
        start_date = date_range.get("start") if date_range else None
        end_date = date_range.get("end") if date_range else None
        
        return analytics_service.get_comprehensive_analytics(
            organization_id=organization_id,
            start_date=start_date,
            end_date=end_date
        )
    
    # Subscription queries
    async def subscription_plans(self, info) -> List[Dict]:
        """Get available subscription plans"""
        return billing_service.get_available_plans()
    
    async def organization_subscription(self, info, organization_id: str) -> Optional[Dict]:
        """Get organization's subscription"""
        current_user = info.context.get("user")
        if not current_user:
            raise GraphQLError("Authentication required")
        
        # Check permissions
        is_admin = await org_service.is_admin(organization_id, current_user.id)
        if not is_admin:
            raise GraphQLError("Admin access required")
        
        return billing_service.get_organization_subscription(organization_id)
    
    async def usage_summary(self, info, organization_id: str) -> Dict:
        """Get organization's usage summary"""
        current_user = info.context.get("user")
        if not current_user:
            raise GraphQLError("Authentication required")
        
        # Check permissions
        is_member = await org_service.is_member(organization_id, current_user.id)
        if not is_member:
            raise GraphQLError("Access denied")
        
        return billing_service.get_usage_summary(organization_id)
    
    # Rate limit query
    async def my_rate_limit(self, info) -> Dict:
        """Get current user's rate limit status"""
        current_user = info.context.get("user")
        if not current_user:
            raise GraphQLError("Authentication required")
        
        return rate_limiter.get_rate_limit_status(current_user.id)


# ==================== MUTATION RESOLVERS ====================

class Mutation:
    """GraphQL Mutation Resolvers"""
    
    # Authentication mutations
    async def sign_up(self, info, input: Dict) -> Dict:
        """Create new user account"""
        try:
            # Create user
            user = await user_service.create_user(
                email=input["email"],
                password=input["password"],
                name=input.get("name")
            )
            
            # Create session
            session = await session_manager.create_session(
                user_id=user["id"],
                ip_address=info.context.get("ip_address"),
                user_agent=info.context.get("user_agent")
            )
            
            # Log event
            await audit_service.log(
                event_type="USER_CREATED",
                user_id=user["id"],
                metadata={"email": user["email"]}
            )
            
            return {
                "user": user,
                "accessToken": session["access_token"],
                "refreshToken": session["refresh_token"],
                "expiresAt": session["expires_at"]
            }
        except ValidationError as e:
            raise GraphQLError(str(e))
    
    async def sign_in(self, info, email: str, password: str) -> Dict:
        """Sign in with email and password"""
        try:
            # Authenticate user
            user = await user_service.authenticate(email, password)
            if not user:
                raise GraphQLError("Invalid credentials")
            
            # Check MFA
            if user.get("mfa_enabled"):
                # Return MFA challenge instead
                challenge = await mfa_service.create_challenge(user["id"])
                return {
                    "mfa_required": True,
                    "challenge_id": challenge["id"]
                }
            
            # Create session
            session = await session_manager.create_session(
                user_id=user["id"],
                ip_address=info.context.get("ip_address"),
                user_agent=info.context.get("user_agent")
            )
            
            # Log event
            await audit_service.log(
                event_type="USER_LOGIN",
                user_id=user["id"],
                metadata={"method": "password"}
            )
            
            return {
                "user": user,
                "accessToken": session["access_token"],
                "refreshToken": session["refresh_token"],
                "expiresAt": session["expires_at"]
            }
        except AuthenticationError as e:
            raise GraphQLError(str(e))
    
    async def sign_out(self, info) -> bool:
        """Sign out current session"""
        current_user = info.context.get("user")
        if not current_user:
            raise GraphQLError("Authentication required")
        
        session_id = info.context.get("session_id")
        if session_id:
            await session_manager.revoke_session(session_id)
            
            # Log event
            await audit_service.log(
                event_type="USER_LOGOUT",
                user_id=current_user.id
            )
        
        return True
    
    # Organization mutations
    async def create_organization(self, info, input: Dict) -> Dict:
        """Create new organization"""
        current_user = info.context.get("user")
        if not current_user:
            raise GraphQLError("Authentication required")
        
        try:
            org = await org_service.create_organization(
                name=input["name"],
                slug=input.get("slug"),
                description=input.get("description"),
                owner_id=current_user.id
            )
            
            # Log event
            await audit_service.log(
                event_type="ORGANIZATION_CREATED",
                user_id=current_user.id,
                organization_id=org["id"],
                metadata={"name": org["name"]}
            )
            
            return org
        except ValidationError as e:
            raise GraphQLError(str(e))
    
    async def update_organization(self, info, id: str, input: Dict) -> Dict:
        """Update organization details"""
        current_user = info.context.get("user")
        if not current_user:
            raise GraphQLError("Authentication required")
        
        # Check permissions
        is_admin = await org_service.is_admin(id, current_user.id)
        if not is_admin:
            raise GraphQLError("Admin access required")
        
        try:
            org = await org_service.update_organization(id, input)
            
            # Log event
            await audit_service.log(
                event_type="ORGANIZATION_UPDATED",
                user_id=current_user.id,
                organization_id=id,
                metadata={"changes": input}
            )
            
            return org
        except ValidationError as e:
            raise GraphQLError(str(e))
    
    # Team mutations
    async def create_team(self, info, organization_id: str, input: Dict) -> Dict:
        """Create new team"""
        current_user = info.context.get("user")
        if not current_user:
            raise GraphQLError("Authentication required")
        
        # Check permissions
        is_admin = await org_service.is_admin(organization_id, current_user.id)
        if not is_admin:
            raise GraphQLError("Admin access required")
        
        try:
            team = await team_service.create_team(
                organization_id=organization_id,
                name=input["name"],
                description=input.get("description"),
                parent_team_id=input.get("parentTeamId"),
                lead_user_id=input.get("leadUserId"),
                permissions=input.get("permissions", [])
            )
            
            # Log event
            await audit_service.log(
                event_type="TEAM_CREATED",
                user_id=current_user.id,
                organization_id=organization_id,
                metadata={"team_id": team["id"], "name": team["name"]}
            )
            
            return team
        except ValidationError as e:
            raise GraphQLError(str(e))
    
    # Member management mutations
    async def invite_member(self, info, input: Dict) -> Dict:
        """Invite member to organization"""
        current_user = info.context.get("user")
        if not current_user:
            raise GraphQLError("Authentication required")
        
        organization_id = input["organizationId"]
        
        # Check permissions
        is_admin = await org_service.is_admin(organization_id, current_user.id)
        if not is_admin:
            raise GraphQLError("Admin access required")
        
        try:
            invitation = await invitations_service.create_invitation(
                organization_id=organization_id,
                email=input["email"],
                role=input["role"],
                permissions=input.get("permissions", []),
                inviter_id=current_user.id,
                inviter_email=current_user.email,
                custom_message=input.get("customMessage")
            )
            
            # Send invitation email
            await send_invitation_email(invitation)
            
            # Log event
            await audit_service.log(
                event_type="INVITATION_SENT",
                user_id=current_user.id,
                organization_id=organization_id,
                metadata={
                    "invitation_id": invitation["id"],
                    "email": invitation["email"],
                    "role": invitation["role"]
                }
            )
            
            return invitation
        except ValidationError as e:
            raise GraphQLError(str(e))
    
    async def accept_invitation(self, info, token: str) -> Dict:
        """Accept organization invitation"""
        current_user = info.context.get("user")
        if not current_user:
            raise GraphQLError("Authentication required")
        
        try:
            result = await invitations_service.accept_invitation(
                token=token,
                user_id=current_user.id
            )
            
            # Add user to organization
            member = await org_service.add_member(
                organization_id=result["organization_id"],
                user_id=current_user.id,
                role=result["role"],
                permissions=result.get("permissions", [])
            )
            
            # Log event
            await audit_service.log(
                event_type="INVITATION_ACCEPTED",
                user_id=current_user.id,
                organization_id=result["organization_id"],
                metadata={"invitation_id": result["invitation"]["id"]}
            )
            
            return member
        except ValidationError as e:
            raise GraphQLError(str(e))
    
    # Subscription mutations
    async def subscribe_to_plan(
        self,
        info,
        organization_id: str,
        plan_id: str,
        billing_cycle: str
    ) -> Dict:
        """Subscribe organization to a plan"""
        current_user = info.context.get("user")
        if not current_user:
            raise GraphQLError("Authentication required")
        
        # Check permissions
        is_owner = await org_service.is_owner(organization_id, current_user.id)
        if not is_owner:
            raise GraphQLError("Owner access required")
        
        try:
            subscription = await billing_service.subscribe_organization(
                organization_id=organization_id,
                plan_id=plan_id,
                billing_cycle=billing_cycle,
                billing_email=current_user.email
            )
            
            # Log event
            await audit_service.log(
                event_type="SUBSCRIPTION_CREATED",
                user_id=current_user.id,
                organization_id=organization_id,
                metadata={
                    "plan_id": plan_id,
                    "billing_cycle": billing_cycle
                }
            )
            
            return subscription
        except ValidationError as e:
            raise GraphQLError(str(e))


# ==================== SUBSCRIPTION RESOLVERS ====================

class Subscription:
    """GraphQL Subscription Resolvers for real-time events"""
    
    async def user_updated(self, user_id: str):
        """Subscribe to user update events"""
        async for event in user_service.subscribe_to_updates(user_id):
            yield event
    
    async def organization_updated(self, organization_id: str):
        """Subscribe to organization update events"""
        async for event in org_service.subscribe_to_updates(organization_id):
            yield event
    
    async def member_joined(self, organization_id: str):
        """Subscribe to new member events"""
        async for event in org_service.subscribe_to_member_events(organization_id, "joined"):
            yield event
    
    async def member_left(self, organization_id: str):
        """Subscribe to member removal events"""
        async for event in org_service.subscribe_to_member_events(organization_id, "left"):
            yield event
    
    async def audit_log_created(self, organization_id: str):
        """Subscribe to new audit log events"""
        async for event in audit_service.subscribe_to_logs(organization_id):
            yield event
    
    async def security_alert(self, organization_id: str):
        """Subscribe to security alert events"""
        async for event in audit_service.subscribe_to_security_alerts(organization_id):
            yield event
    
    async def quota_warning(self, organization_id: str):
        """Subscribe to quota warning events"""
        async for event in billing_service.subscribe_to_quota_warnings(organization_id):
            yield event
    
    async def analytics_update(self, organization_id: str):
        """Subscribe to real-time analytics updates"""
        async for event in analytics_service.subscribe_to_updates(organization_id):
            yield event


# ==================== HELPER FUNCTIONS ====================

async def send_invitation_email(invitation: Dict):
    """Send invitation email to user"""
    # Implementation would send actual email


# ==================== EXPORT RESOLVERS ====================

resolvers = {
    "Query": Query(),
    "Mutation": Mutation(),
    "Subscription": Subscription()
}