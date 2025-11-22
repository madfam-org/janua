# Production TODOs Roadmap - Beta Launch
**Created**: November 17, 2025  
**Target**: Beta launch in 4-6 weeks  
**Status**: 30 items → Tracked for implementation

---

## Overview

This document tracks all 30 production TODOs identified in the cleanup analysis, organized by implementation phase and priority.

**Reference**: See [cleanup-analysis-nov17-2025.md](cleanup-analysis-nov17-2025.md) for detailed analysis.

---

## Phase 1: Critical Path (Weeks 1-2) - 21 TODOs

### Week 1: Authentication & Security (9 TODOs) 🔴

#### ✅ Email Integration (Already Complete)
**Status**: Resend email service fully implemented and operational

**Implementation Verified**:
- ✅ Email Provider: **Resend** (configured in app/config.py)
- ✅ Service Wrapper: `apps/api/app/services/resend_email_service.py` (609 lines)
- ✅ Email Templates: `apps/api/app/templates/email/` (21 templates)
- ✅ Delivery Tracking: Redis-based tracking system
- ✅ Enterprise Features: Invitations, SSO, compliance, security alerts

**Available Email Methods**:
- `send_verification_email()` - Email verification flow
- `send_password_reset_email()` - Password reset flow
- `send_welcome_email()` - New user welcome
- `send_invitation_email()` - Organization invitations ✅
- `send_mfa_recovery_email()` - MFA recovery codes ✅ (template exists)
- `send_sso_configuration_email()` - SSO setup notifications
- `send_sso_enabled_email()` - SSO activation notifications
- `send_compliance_alert_email()` - Compliance alerts
- `send_data_export_ready_email()` - GDPR data exports

**No Action Required**: Email infrastructure is production-ready

---

#### MFA & Authentication TODOs

**TODO 1**: MFA Recovery Email
- **File**: `apps/api/app/routers/v1/mfa.py:444`
- **Code**: `# TODO: Send recovery email with instructions`
- **Priority**: P0 (Week 1)
- **Dependencies**: ✅ Resend email service (already exists)
- **Template**: ✅ `mfa_recovery.html` and `mfa_recovery.txt` (already exist)
- **Implementation**:
  ```python
  # Step 1: Add send_mfa_recovery_email method to resend_email_service.py
  async def send_mfa_recovery_email(
      self,
      to_email: str,
      user_name: str,
      backup_codes: List[str]
  ) -> EmailDeliveryStatus:
      """Send MFA recovery email with backup codes"""
      context = {
          "user_name": user_name,
          "backup_codes": backup_codes,
          "base_url": settings.BASE_URL,
          "company_name": "Janua",
          "support_email": settings.SUPPORT_EMAIL or "support@janua.dev",
      }
      
      html_content = self._render_template("mfa_recovery.html", context)
      text_content = self._render_template("mfa_recovery.txt", context)
      
      return await self.send_email(
          to_email=to_email,
          subject="MFA Recovery Codes - Janua",
          html_content=html_content,
          text_content=text_content,
          priority=EmailPriority.HIGH,
          tags=[{"name": "category", "value": "mfa_recovery"}],
          metadata={"type": "mfa_recovery", "user_email": to_email}
      )
  
  # Step 2: Use in mfa.py:444
  from app.services.resend_email_service import get_resend_email_service
  
  email_service = get_resend_email_service(redis_client)
  await email_service.send_mfa_recovery_email(
      to_email=user.email,
      user_name=user.full_name or user.email,
      backup_codes=codes
  )
  ```

**TODO 2**: Passkey Redis Storage (Challenge)
- **File**: `apps/api/app/routers/v1/passkeys.py:129`
- **Code**: `# TODO: Store in Redis with expiry`
- **Priority**: P0 (Week 1)
- **Dependencies**: Redis connection
- **Implementation**:
  ```python
  # Store WebAuthn challenge in Redis with 5-minute expiry
  await redis_client.setex(
      f"passkey_challenge:{user_id}",
      300,  # 5 minutes
      challenge_json
  )
  ```

**TODO 3**: Passkey Redis Storage (Credential)
- **File**: `apps/api/app/routers/v1/passkeys.py:274`
- **Code**: `# TODO: Store in Redis with session ID`
- **Priority**: P0 (Week 1)
- **Dependencies**: Redis connection
- **Implementation**:
  ```python
  # Store credential temporarily for verification
  await redis_client.setex(
      f"passkey_credential:{session_id}",
      600,  # 10 minutes
      credential_json
  )
  ```

**TODO 4**: JWT Refresh Token Blacklist
- **File**: `apps/api/app/core/jwt_manager.py:180`
- **Code**: `# TODO: Check if refresh token is blacklisted or session is revoked`
- **Priority**: P0 (Week 1)
- **Dependencies**: Redis connection
- **Implementation**:
  ```python
  # Check token blacklist before refresh
  is_blacklisted = await redis_client.exists(f"blacklist:{token_id}")
  if is_blacklisted:
      raise InvalidTokenError("Token has been revoked")
  
  # Check session status
  session = await session_service.get_session(session_id)
  if not session or session.revoked:
      raise InvalidTokenError("Session has been revoked")
  ```

**TODO 5**: WebAuthn Registration Options
- **File**: `apps/api/app/auth/router.py:470`
- **Code**: `# TODO: Implement WebAuthn registration options`
- **Priority**: P1 (Week 1)
- **Dependencies**: None
- **Implementation**:
  ```python
  # Generate WebAuthn registration options
  from webauthn import generate_registration_options
  
  options = generate_registration_options(
      rp_id=settings.WEBAUTHN_RP_ID,
      rp_name=settings.WEBAUTHN_RP_NAME,
      user_id=user.id.bytes,
      user_name=user.email,
      user_display_name=user.full_name or user.email
  )
  
  # Store challenge in Redis (see TODO 2)
  await redis_client.setex(
      f"webauthn_challenge:{user.id}",
      300,
      options.challenge.hex()
  )
  
  return options
  ```

**TODO 6**: WebAuthn Registration Verification
- **File**: `apps/api/app/auth/router.py:489`
- **Code**: `# TODO: Implement WebAuthn registration`
- **Priority**: P1 (Week 1)
- **Dependencies**: WebAuthn options (TODO 5)
- **Implementation**:
  ```python
  # Verify WebAuthn registration response
  from webauthn import verify_registration_response
  
  challenge = await redis_client.get(f"webauthn_challenge:{user.id}")
  if not challenge:
      raise ValueError("Challenge expired or not found")
  
  credential = verify_registration_response(
      credential=registration_data,
      expected_challenge=bytes.fromhex(challenge),
      expected_rp_id=settings.WEBAUTHN_RP_ID,
      expected_origin=settings.WEBAUTHN_ORIGIN
  )
  
  # Store credential in database
  await passkey_service.create_passkey(user.id, credential)
  ```

**TODO 7**: Session Storage Implementation
- **File**: `apps/api/app/core/jwt_manager.py:224`
- **Code**: `# TODO: Implement with session storage`
- **Priority**: P1 (Week 1)
- **Dependencies**: Session service
- **Implementation**:
  ```python
  # Create session record when issuing tokens
  session = await session_service.create_session(
      user_id=user.id,
      device_info=device_info,
      ip_address=request.client.host
  )
  
  # Include session ID in JWT claims
  access_token = create_access_token(
      data={"sub": str(user.id), "session_id": str(session.id)}
  )
  ```

**TODO 8**: Get IP Address from Request
- **File**: `apps/api/app/routers/v1/passkeys.py:351`
- **Code**: `ip_address=None,  # TODO: Get from request`
- **Priority**: P2 (Week 1)
- **Dependencies**: None
- **Implementation**:
  ```python
  # Extract IP address from request
  ip_address = request.client.host
  
  # Handle proxy headers if behind load balancer
  if forwarded_for := request.headers.get("X-Forwarded-For"):
      ip_address = forwarded_for.split(",")[0].strip()
  ```

---

### Week 2: Admin Monitoring & SSO (12 TODOs) 🔴

#### Admin Health Checks (5 TODOs)

**TODO 9**: Redis Connection Check
- **File**: `apps/api/app/routers/v1/admin.py:211`
- **Code**: `cache_status = "not_configured"  # TODO: Check Redis connection`
- **Priority**: P0 (Week 2)
- **Implementation**:
  ```python
  try:
      await redis_client.ping()
      cache_status = "healthy"
  except Exception as e:
      cache_status = f"unhealthy: {str(e)}"
  ```

**TODO 10**: S3/Storage Connection Check
- **File**: `apps/api/app/routers/v1/admin.py:214`
- **Code**: `storage_status = "healthy"  # TODO: Check S3/storage connection`
- **Priority**: P0 (Week 2)
- **Implementation**:
  ```python
  try:
      # Try to list buckets or head bucket
      await s3_client.head_bucket(Bucket=settings.S3_BUCKET)
      storage_status = "healthy"
  except Exception as e:
      storage_status = f"unhealthy: {str(e)}"
  ```

**TODO 11**: Email Service Status Check
- **File**: `apps/api/app/routers/v1/admin.py:217`
- **Code**: `email_status = "not_configured"  # TODO: Check email service`
- **Priority**: P0 (Week 2)
- **Dependencies**: ✅ Resend email service (already exists)
- **Implementation**:
  ```python
  # Step 1: Add health check method to resend_email_service.py
  async def check_health(self) -> Dict[str, Any]:
      """Check Resend email service health"""
      if not settings.EMAIL_ENABLED:
          return {"status": "disabled", "message": "Email service disabled"}
      
      if not settings.RESEND_API_KEY:
          return {"status": "not_configured", "message": "Resend API key not configured"}
      
      try:
          # Verify API key is valid by checking API status
          # Resend doesn't have a dedicated health endpoint, so we check configuration
          if settings.ENVIRONMENT == "production" and not settings.RESEND_API_KEY.startswith("re_"):
              return {"status": "unhealthy", "message": "Invalid Resend API key format"}
          
          # Check Redis connection for delivery tracking
          if self.redis_client:
              await self.redis_client.ping()
          
          return {"status": "healthy", "message": "Email service operational"}
      except Exception as e:
          return {"status": "unhealthy", "message": str(e)}
  
  # Step 2: Use in admin.py:217
  from app.services.resend_email_service import get_resend_email_service
  
  email_service = get_resend_email_service(redis_client)
  health = await email_service.check_health()
  email_status = health["status"]
  ```

**TODO 12**: Uptime Calculation
- **File**: `apps/api/app/routers/v1/admin.py:220`
- **Code**: `uptime = 0.0  # TODO: Calculate from application start time`
- **Priority**: P1 (Week 2)
- **Implementation**:
  ```python
  # Store app start time as global variable in main.py
  # In admin.py:
  import time
  from app.main import APP_START_TIME
  
  uptime = time.time() - APP_START_TIME
  ```

**TODO 13**: Maintenance Mode Implementation
- **File**: `apps/api/app/routers/v1/admin.py:618`
- **Code**: `# TODO: Implement maintenance mode in Redis/cache`
- **Priority**: P2 (Week 2)
- **Implementation**:
  ```python
  # Set maintenance mode flag in Redis
  await redis_client.setex(
      "maintenance_mode",
      3600,  # 1 hour default
      json.dumps({
          "enabled": True,
          "message": maintenance_request.message,
          "enabled_at": datetime.utcnow().isoformat()
      })
  )
  
  # Check in middleware
  if await redis_client.exists("maintenance_mode"):
      if not is_admin_user(request):
          raise HTTPException(503, "System under maintenance")
  ```

---

#### SSO Integration (5 TODOs)

**TODO 14**: SSO Dependency Injection
- **File**: `apps/api/app/routers/v1/sso.py:119`
- **Code**: `# TODO: Replace with actual dependency injection`
- **Priority**: P0 (Week 2)
- **Implementation**:
  ```python
  from fastapi import Depends
  from app.services.sso_service import SSOService
  
  async def get_sso_service() -> SSOService:
      return SSOService()
  
  # In endpoint:
  async def sso_endpoint(
      sso_service: SSOService = Depends(get_sso_service)
  ):
      ...
  ```

**TODO 15**: Organization Membership Check (SSO)
- **File**: `apps/api/app/routers/v1/sso.py:209`
- **Code**: `# TODO: Add proper organization membership check`
- **Priority**: P0 (Week 2)
- **Implementation**:
  ```python
  # Verify user is member of organization
  membership = await org_service.get_membership(
      user_id=user.id,
      organization_id=organization_id
  )
  
  if not membership:
      raise HTTPException(403, "User is not a member of this organization")
  
  if membership.role not in allowed_roles:
      raise HTTPException(403, "Insufficient permissions")
  ```

**TODO 16**: JWT/Session Creation (SSO)
- **File**: `apps/api/app/routers/v1/sso.py:341`
- **Code**: `# TODO: Create JWT tokens and session`
- **Priority**: P0 (Week 2)
- **Implementation**:
  ```python
  # After successful SSO authentication
  session = await session_service.create_session(
      user_id=user.id,
      organization_id=organization_id,
      sso_provider=provider_name,
      device_info=device_info,
      ip_address=request.client.host
  )
  
  access_token = create_access_token(
      data={
          "sub": str(user.id),
          "org_id": str(organization_id),
          "session_id": str(session.id)
      }
  )
  
  refresh_token = create_refresh_token(
      data={"sub": str(user.id), "session_id": str(session.id)}
  )
  
  return {"access_token": access_token, "refresh_token": refresh_token}
  ```

**TODO 17**: OIDC Discovery
- **File**: `apps/api/app/sso/routers/configuration.py:179`
- **Code**: `# TODO: Implement OIDC discovery`
- **Priority**: P1 (Week 2)
- **Implementation**:
  ```python
  import httpx
  
  async def discover_oidc_configuration(issuer_url: str):
      """Fetch OIDC discovery document"""
      discovery_url = f"{issuer_url}/.well-known/openid-configuration"
      
      async with httpx.AsyncClient() as client:
          response = await client.get(discovery_url)
          response.raise_for_status()
          config = response.json()
      
      return {
          "issuer": config["issuer"],
          "authorization_endpoint": config["authorization_endpoint"],
          "token_endpoint": config["token_endpoint"],
          "userinfo_endpoint": config["userinfo_endpoint"],
          "jwks_uri": config["jwks_uri"]
      }
  ```

**TODO 18**: Get Session ID from Token
- **File**: `apps/api/app/routers/v1/admin.py:595`
- **Code**: `# TODO: Get current session ID from token`
- **Priority**: P2 (Week 2)
- **Implementation**:
  ```python
  # Extract session ID from JWT claims
  token_data = decode_token(token)
  session_id = token_data.get("session_id")
  
  if not session_id:
      raise HTTPException(401, "Invalid token: missing session ID")
  ```

---

#### Organizations (2 TODOs)

**TODO 19**: Organization Email Sending
- **File**: `apps/api/app/routers/v1/organizations.py:596`
- **Code**: `# TODO: Implement email sending`
- **Priority**: P1 (Week 2)
- **Dependencies**: ✅ Resend email service (already exists)
- **Method**: ✅ `send_invitation_email()` (already implemented)
- **Template**: ✅ `invitation.html` and `invitation.txt` (already exist)
- **Implementation**:
  ```python
  # Use existing send_invitation_email method from resend_email_service.py
  from app.services.resend_email_service import get_resend_email_service
  from datetime import datetime, timedelta
  
  email_service = get_resend_email_service(redis_client)
  
  # Calculate invitation expiry (e.g., 7 days from now)
  expires_at = datetime.utcnow() + timedelta(days=7)
  
  await email_service.send_invitation_email(
      to_email=invitation.email,
      inviter_name=current_user.full_name or current_user.email,
      organization_name=organization.name,
      role=invitation.role,
      invitation_url=f"{settings.FRONTEND_URL}/invitations/{invitation.token}",
      expires_at=expires_at,
      teams=invitation.teams if hasattr(invitation, 'teams') else None
  )
  ```

**TODO 20**: Role Usage Check
- **File**: `apps/api/app/routers/v1/organizations.py:923`
- **Code**: `# TODO: Check if role is in use by any members`
- **Priority**: P2 (Week 2)
- **Implementation**:
  ```python
  # Before deleting role, check if assigned to members
  members_with_role = await org_service.count_members_with_role(
      organization_id=organization_id,
      role_id=role_id
  )
  
  if members_with_role > 0:
      raise HTTPException(
          400,
          f"Cannot delete role: {members_with_role} members still assigned to this role"
      )
  ```

**TODO 21**: Webhook Organization Check
- **File**: `apps/api/app/routers/v1/webhooks.py:132`
- **Code**: `# TODO: Check organization membership and role`
- **Priority**: P2 (Week 2)
- **Implementation**:
  ```python
  # Verify user can manage webhooks for organization
  membership = await org_service.get_membership(
      user_id=current_user.id,
      organization_id=organization_id
  )
  
  if not membership or membership.role not in ["owner", "admin"]:
      raise HTTPException(403, "Insufficient permissions to manage webhooks")
  ```

---

## Phase 2: Infrastructure & Resilience (Weeks 3-4) - 9 TODOs

### Infrastructure TODOs (5 items) 🟡

**TODO 22**: Rate Limit Database Fallback
- **File**: `apps/api/app/middleware/rate_limit.py:364`
- **Code**: `# TODO: Fetch from database if not in cache`
- **Priority**: P0 (Week 3)
- **Implementation**:
  ```python
  # Fallback to database if Redis unavailable
  try:
      limit = await redis_client.get(f"rate_limit:{user_id}")
  except RedisError:
      # Fallback to database
      limit = await db.execute(
          "SELECT rate_limit FROM users WHERE id = :user_id",
          {"user_id": user_id}
      )
  ```

**TODO 23**: User Tier Fetching
- **File**: `apps/api/app/middleware/global_rate_limit.py:382`
- **Code**: `# TODO: Fetch actual user tier from database`
- **Priority**: P0 (Week 3)
- **Implementation**:
  ```python
  # Get user tier for rate limiting
  user = await user_service.get_user(user_id)
  tier = user.subscription_tier or "free"
  
  # Apply tier-based limits
  rate_limits = {
      "free": {"requests": 100, "window": 3600},
      "pro": {"requests": 1000, "window": 3600},
      "enterprise": {"requests": 10000, "window": 3600}
  }
  
  limit_config = rate_limits.get(tier, rate_limits["free"])
  ```

**TODO 24**: Circuit Breaker Logic
- **File**: `apps/api/app/middleware/global_rate_limit.py:424`
- **Code**: `# TODO: Implement circuit breaker logic`
- **Priority**: P1 (Week 3)
- **Implementation**:
  ```python
  from circuitbreaker import circuit
  
  @circuit(failure_threshold=5, recovery_timeout=60)
  async def call_external_service():
      """External service call with circuit breaker"""
      try:
          response = await external_api_call()
          return response
      except Exception as e:
          logger.error(f"External service error: {e}")
          raise
  ```

**TODO 25**: Tier-Based Limits
- **File**: `apps/api/app/core/tenant_context.py:283`
- **Code**: `# TODO: Implement tier-based limits`
- **Priority**: P1 (Week 3)
- **Implementation**:
  ```python
  # Get organization tier and apply limits
  org_tier = organization.subscription_tier or "free"
  
  tier_limits = {
      "free": {"max_users": 5, "max_storage_gb": 1},
      "pro": {"max_users": 50, "max_storage_gb": 100},
      "enterprise": {"max_users": -1, "max_storage_gb": -1}  # unlimited
  }
  
  limits = tier_limits.get(org_tier, tier_limits["free"])
  
  # Enforce limits
  if limits["max_users"] > 0 and org.user_count >= limits["max_users"]:
      raise HTTPException(403, "Organization user limit reached")
  ```

**TODO 26**: Subdomain Organization Lookup
- **File**: `apps/api/app/core/tenant_context.py:124`
- **Code**: `# TODO: Implement organization lookup by subdomain`
- **Priority**: P2 (Week 3)
- **Implementation**:
  ```python
  # Extract subdomain from request
  host = request.headers.get("host", "")
  subdomain = host.split(".")[0] if "." in host else None
  
  if subdomain and subdomain not in ["www", "api"]:
      # Look up organization by subdomain
      organization = await org_service.get_by_subdomain(subdomain)
      if organization:
          request.state.organization_id = organization.id
  ```

---

### OAuth & Webhook TODOs (4 items)

**TODO 27**: OAuth State Storage
- **File**: `apps/api/app/routers/v1/oauth.py:88`
- **Code**: `# TODO: Implement state storage in Redis with expiry`
- **Priority**: P1 (Week 3)
- **Implementation**:
  ```python
  # Store OAuth state token in Redis with 10-minute expiry
  state_token = secrets.token_urlsafe(32)
  
  await redis_client.setex(
      f"oauth_state:{state_token}",
      600,  # 10 minutes
      json.dumps({
          "provider": provider,
          "redirect_uri": redirect_uri,
          "created_at": datetime.utcnow().isoformat()
      })
  )
  
  return state_token
  ```

**TODO 28**: OAuth State Validation
- **File**: `apps/api/app/routers/v1/oauth.py:143`
- **Code**: `# TODO: Validate state token from Redis`
- **Priority**: P1 (Week 3)
- **Implementation**:
  ```python
  # Validate OAuth state token
  state_data = await redis_client.get(f"oauth_state:{state_token}")
  
  if not state_data:
      raise HTTPException(400, "Invalid or expired state token")
  
  state = json.loads(state_data)
  
  # Delete state token after validation (one-time use)
  await redis_client.delete(f"oauth_state:{state_token}")
  
  return state
  ```

**TODO 29**: Webhook Organization Support
- **File**: `apps/api/app/routers/v1/webhooks.py:157`
- **Code**: `organization_id=None,  # TODO: Add organization support`
- **Priority**: P2 (Week 3)
- **Implementation**:
  ```python
  # Extract organization from request context
  organization_id = request.state.organization_id
  
  # Create webhook with organization context
  webhook = await webhook_service.create_webhook(
      url=webhook_data.url,
      events=webhook_data.events,
      organization_id=organization_id,
      created_by=current_user.id
  )
  ```

**TODO 30**: Organization Invitation Email
- **File**: `apps/api/app/organizations/application/commands/invite_member.py:105`
- **Code**: `# TODO: Send invitation email`
- **Priority**: P1 (Week 3)
- **Dependencies**: ✅ Resend email service (already exists)
- **Method**: ✅ `send_invitation_email()` (already implemented)
- **Template**: ✅ `invitation.html` and `invitation.txt` (already exist)
- **Implementation**:
  ```python
  # Use existing send_invitation_email method from resend_email_service.py
  from app.services.resend_email_service import get_resend_email_service
  from datetime import datetime, timedelta
  
  email_service = get_resend_email_service(redis_client)
  
  # Calculate invitation expiry (e.g., 7 days from now)
  expires_at = datetime.utcnow() + timedelta(days=7)
  
  await email_service.send_invitation_email(
      to_email=email,
      inviter_name=inviter.full_name or inviter.email,
      organization_name=organization.name,
      role=role,
      invitation_url=f"{settings.FRONTEND_URL}/invitations/accept/{token}",
      expires_at=expires_at,
      teams=teams if teams else None
  )
  ```

---

## Implementation Tracking

### Status Legend
- ⬜ Not Started
- 🟡 In Progress
- ✅ Complete
- 🔴 Blocked

### Week 1 Progress (9 TODOs)
- ⬜ Email service integration (prerequisite)
- ⬜ MFA recovery email
- ⬜ Passkey Redis storage (challenge)
- ⬜ Passkey Redis storage (credential)
- ⬜ JWT refresh blacklist
- ⬜ WebAuthn registration options
- ⬜ WebAuthn registration verification
- ⬜ Session storage implementation
- ⬜ IP address extraction

### Week 2 Progress (12 TODOs)
- ⬜ Redis health check
- ⬜ S3 health check
- ⬜ Email health check
- ⬜ Uptime calculation
- ⬜ Maintenance mode
- ⬜ SSO dependency injection
- ⬜ Organization membership check (SSO)
- ⬜ JWT/session creation (SSO)
- ⬜ OIDC discovery
- ⬜ Organization email sending
- ⬜ Role usage check
- ⬜ Webhook organization check

### Week 3-4 Progress (9 TODOs)
- ⬜ Rate limit DB fallback
- ⬜ User tier fetching
- ⬜ Circuit breaker logic
- ⬜ Tier-based limits
- ⬜ Subdomain lookup
- ⬜ OAuth state storage
- ⬜ OAuth state validation
- ⬜ Webhook organization support
- ⬜ Organization invitation email

---

## Testing Requirements

Each TODO implementation must include:

1. **Unit Tests**
   - Test success path
   - Test error conditions
   - Test edge cases

2. **Integration Tests** (where applicable)
   - Test with real Redis connection
   - Test with real email service
   - Test with real external services

3. **Documentation**
   - Update API documentation
   - Add code comments
   - Update README if user-facing

---

## Dependencies Matrix

| TODO | Depends On | Blocks |
|------|------------|--------|
| Email Service | None | TODOs 1, 11, 19, 30 |
| Redis Connection | None | TODOs 2, 3, 4, 9, 13, 22, 27, 28 |
| WebAuthn Options (5) | None | TODO 6 |
| Session Service | None | TODOs 4, 7 |

---

## Success Metrics

**Week 1 Complete**:
- ✅ Email service operational
- ✅ MFA fully functional with recovery
- ✅ Passkey authentication production-ready
- ✅ JWT security hardened

**Week 2 Complete**:
- ✅ All admin health checks working
- ✅ SSO fully integrated and tested
- ✅ Organization features complete

**Week 3-4 Complete**:
- ✅ All 30 TODOs resolved
- ✅ Infrastructure resilient
- ✅ OAuth flows tested
- ✅ Webhook system complete

---

## Next Steps

1. **Choose email provider** (SendGrid/Mailgun/AWS SES)
2. **Create GitHub issues** for each TODO
3. **Start Week 1 implementation** (TODOs 1-9)
4. **Write tests** as you implement
5. **Update this document** with progress

---

**Maintained by**: Development team  
**Updated**: Track progress weekly  
**Review**: Update status after each TODO completion
