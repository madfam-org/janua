import { NextResponse } from 'next/server'

/**
 * LLM-Optimized Documentation Endpoint
 *
 * Provides comprehensive API documentation in plain text format
 * optimized for AI/LLM consumption with structured patterns.
 */

const LLM_DOCS = `# JANUA_API_DOCS_LLM_VERSION_1.0

## AUTHENTICATION_ENDPOINTS

### POST /api/v1/auth/signup
PURPOSE: Create new user account with email and password
INPUTS: email(string,required,valid_email), password(string,required,min:8,max:128), metadata(object,optional)
OUTPUTS: user(object:id,email,created_at), session(object:token,expires_at,refresh_token)
ERRORS: 400(invalid_input), 409(email_exists), 422(validation_failed), 500(server_error)
RATE_LIMIT: 5/minute per IP
EXAMPLE_REQUEST: {"email":"user@example.com","password":"SecurePass123!","metadata":{"source":"web"}}
EXAMPLE_RESPONSE: {"user":{"id":"usr_abc123","email":"user@example.com","created_at":"2024-01-20T12:00:00Z"},"session":{"token":"jwt_token","expires_at":"2024-01-20T13:00:00Z","refresh_token":"refresh_token"}}

### POST /api/v1/auth/signin
PURPOSE: Authenticate existing user with email and password
INPUTS: email(string,required), password(string,required), remember_me(boolean,optional,default:false)
OUTPUTS: user(object), session(object), organization(object,optional)
ERRORS: 401(invalid_credentials), 403(account_suspended), 429(rate_limited)
RATE_LIMIT: 10/minute per IP
EXAMPLE_REQUEST: {"email":"user@example.com","password":"SecurePass123!","remember_me":true}
EXAMPLE_RESPONSE: {"user":{"id":"usr_abc123","email":"user@example.com"},"session":{"token":"jwt_token","expires_at":"2024-01-27T12:00:00Z"}}

### POST /api/v1/auth/signout
PURPOSE: Terminate user session and invalidate tokens
INPUTS: refresh_token(string,optional), everywhere(boolean,optional,default:false)
OUTPUTS: success(boolean), message(string)
ERRORS: 401(invalid_session)
EXAMPLE_REQUEST: {"everywhere":true}
EXAMPLE_RESPONSE: {"success":true,"message":"Successfully signed out"}

### POST /api/v1/auth/refresh
PURPOSE: Refresh access token using refresh token
INPUTS: refresh_token(string,required)
OUTPUTS: access_token(string), expires_at(datetime), refresh_token(string,optional)
ERRORS: 401(invalid_refresh_token), 403(refresh_token_expired)
EXAMPLE_REQUEST: {"refresh_token":"refresh_token_value"}
EXAMPLE_RESPONSE: {"access_token":"new_jwt_token","expires_at":"2024-01-20T14:00:00Z"}

### POST /api/v1/auth/magic-link
PURPOSE: Send passwordless authentication magic link via email
INPUTS: email(string,required), redirect_url(string,optional), expires_in(integer,optional,default:900)
OUTPUTS: success(boolean), message(string)
ERRORS: 400(invalid_email), 429(rate_limited)
RATE_LIMIT: 3/hour per email
EXAMPLE_REQUEST: {"email":"user@example.com","redirect_url":"https://app.example.com/dashboard"}
EXAMPLE_RESPONSE: {"success":true,"message":"Magic link sent to email"}

### GET /api/v1/auth/magic-link/verify
PURPOSE: Verify magic link token and create session
INPUTS: token(string,required,query_param)
OUTPUTS: user(object), session(object), redirect_url(string)
ERRORS: 400(invalid_token), 410(token_expired), 409(token_used)
EXAMPLE_REQUEST: GET /api/v1/auth/magic-link/verify?token=magic_token_123
EXAMPLE_RESPONSE: {"user":{"id":"usr_abc123"},"session":{"token":"jwt_token"},"redirect_url":"/dashboard"}

### POST /api/v1/auth/passkey/register
PURPOSE: Register WebAuthn passkey for passwordless authentication
INPUTS: user_id(string,required), challenge(string,required), credential(object,required)
OUTPUTS: passkey_id(string), created_at(datetime)
ERRORS: 400(invalid_credential), 409(passkey_exists)
EXAMPLE_REQUEST: {"user_id":"usr_abc123","challenge":"challenge_string","credential":{...webauthn_credential}}
EXAMPLE_RESPONSE: {"passkey_id":"pass_xyz789","created_at":"2024-01-20T12:00:00Z"}

### POST /api/v1/auth/passkey/authenticate
PURPOSE: Authenticate user with WebAuthn passkey
INPUTS: credential(object,required), challenge(string,required)
OUTPUTS: user(object), session(object)
ERRORS: 401(invalid_passkey), 403(passkey_revoked)
EXAMPLE_REQUEST: {"credential":{...webauthn_assertion},"challenge":"challenge_string"}
EXAMPLE_RESPONSE: {"user":{"id":"usr_abc123"},"session":{"token":"jwt_token"}}

### GET /api/v1/auth/oauth/authorize
PURPOSE: Get OAuth provider authorization URL
INPUTS: provider(string,required,enum:google|github|microsoft|apple|discord|twitter|linkedin), state(string,required), redirect_uri(string,optional)
OUTPUTS: auth_url(string), state(string)
ERRORS: 400(invalid_provider), 503(provider_unavailable)
EXAMPLE_REQUEST: GET /api/v1/auth/oauth/authorize?provider=google&state=random_state
EXAMPLE_RESPONSE: {"auth_url":"https://accounts.google.com/oauth/authorize?...","state":"random_state"}

### POST /api/v1/auth/oauth/callback
PURPOSE: Handle OAuth provider callback and create session
INPUTS: provider(string,required), code(string,required), state(string,required)
OUTPUTS: user(object), session(object), is_new_user(boolean)
ERRORS: 400(invalid_code), 401(state_mismatch), 503(provider_error)
EXAMPLE_REQUEST: {"provider":"google","code":"auth_code_123","state":"random_state"}
EXAMPLE_RESPONSE: {"user":{"id":"usr_abc123"},"session":{"token":"jwt_token"},"is_new_user":false}

### POST /api/v1/auth/mfa/enable
PURPOSE: Enable multi-factor authentication for user
INPUTS: method(string,required,enum:totp|sms|email), phone_number(string,conditional), backup_codes(boolean,optional)
OUTPUTS: secret(string,conditional), qr_code(string,conditional), backup_codes(array,optional)
ERRORS: 400(invalid_method), 409(mfa_already_enabled)
EXAMPLE_REQUEST: {"method":"totp","backup_codes":true}
EXAMPLE_RESPONSE: {"secret":"TOTP_SECRET","qr_code":"data:image/png;base64,...","backup_codes":["code1","code2"]}

### POST /api/v1/auth/mfa/verify
PURPOSE: Verify MFA code during authentication
INPUTS: code(string,required), method(string,required,enum:totp|sms|email|backup)
OUTPUTS: verified(boolean), session(object,conditional)
ERRORS: 401(invalid_code), 429(too_many_attempts)
EXAMPLE_REQUEST: {"code":"123456","method":"totp"}
EXAMPLE_RESPONSE: {"verified":true,"session":{"token":"jwt_token"}}

## USER_MANAGEMENT_ENDPOINTS

### GET /api/v1/users/profile
PURPOSE: Get current authenticated user profile
INPUTS: none (uses session token)
OUTPUTS: user(object:id,email,name,avatar,created_at,updated_at,email_verified,mfa_enabled)
ERRORS: 401(unauthorized)
EXAMPLE_REQUEST: GET /api/v1/users/profile
EXAMPLE_RESPONSE: {"id":"usr_abc123","email":"user@example.com","name":"John Doe","email_verified":true,"mfa_enabled":false}

### PUT /api/v1/users/profile
PURPOSE: Update current user profile
INPUTS: name(string,optional), avatar(string,optional,url), metadata(object,optional)
OUTPUTS: user(object,updated)
ERRORS: 400(invalid_input), 401(unauthorized)
EXAMPLE_REQUEST: {"name":"Jane Doe","avatar":"https://example.com/avatar.jpg"}
EXAMPLE_RESPONSE: {"id":"usr_abc123","name":"Jane Doe","avatar":"https://example.com/avatar.jpg","updated_at":"2024-01-20T12:00:00Z"}

### DELETE /api/v1/users/profile
PURPOSE: Delete user account and all associated data
INPUTS: confirmation(string,required,value:"DELETE"), password(string,required)
OUTPUTS: success(boolean), message(string)
ERRORS: 400(invalid_confirmation), 401(invalid_password)
EXAMPLE_REQUEST: {"confirmation":"DELETE","password":"current_password"}
EXAMPLE_RESPONSE: {"success":true,"message":"Account deleted successfully"}

### POST /api/v1/users/verify-email
PURPOSE: Send email verification link
INPUTS: none (uses session token)
OUTPUTS: success(boolean), message(string)
ERRORS: 400(already_verified), 429(rate_limited)
EXAMPLE_REQUEST: POST /api/v1/users/verify-email
EXAMPLE_RESPONSE: {"success":true,"message":"Verification email sent"}

### GET /api/v1/users/sessions
PURPOSE: List all active sessions for current user
INPUTS: none (uses session token)
OUTPUTS: sessions(array:id,device,ip,location,created_at,last_used_at,current)
ERRORS: 401(unauthorized)
EXAMPLE_REQUEST: GET /api/v1/users/sessions
EXAMPLE_RESPONSE: {"sessions":[{"id":"sess_123","device":"Chrome on Mac","ip":"192.168.1.1","location":"San Francisco, CA","created_at":"2024-01-20T12:00:00Z","current":true}]}

### DELETE /api/v1/users/sessions/{session_id}
PURPOSE: Revoke specific user session
INPUTS: session_id(string,required,path_param)
OUTPUTS: success(boolean), message(string)
ERRORS: 404(session_not_found), 401(unauthorized)
EXAMPLE_REQUEST: DELETE /api/v1/users/sessions/sess_123
EXAMPLE_RESPONSE: {"success":true,"message":"Session revoked"}

## ORGANIZATION_ENDPOINTS

### POST /api/v1/organizations
PURPOSE: Create new organization
INPUTS: name(string,required), slug(string,optional), description(string,optional), metadata(object,optional)
OUTPUTS: organization(object:id,name,slug,created_at), membership(object:role,joined_at)
ERRORS: 400(invalid_input), 409(slug_exists)
EXAMPLE_REQUEST: {"name":"Acme Corp","slug":"acme","description":"Innovation company"}
EXAMPLE_RESPONSE: {"organization":{"id":"org_xyz789","name":"Acme Corp","slug":"acme"},"membership":{"role":"owner","joined_at":"2024-01-20T12:00:00Z"}}

### GET /api/v1/organizations
PURPOSE: List user's organizations
INPUTS: page(integer,optional,default:1), limit(integer,optional,default:20,max:100)
OUTPUTS: organizations(array), total(integer), page(integer), pages(integer)
ERRORS: 401(unauthorized)
EXAMPLE_REQUEST: GET /api/v1/organizations?page=1&limit=10
EXAMPLE_RESPONSE: {"organizations":[{"id":"org_xyz789","name":"Acme Corp","role":"owner"}],"total":1,"page":1,"pages":1}

### GET /api/v1/organizations/{org_id}
PURPOSE: Get organization details
INPUTS: org_id(string,required,path_param)
OUTPUTS: organization(object:full_details), user_role(string), permissions(array)
ERRORS: 404(not_found), 403(forbidden)
EXAMPLE_REQUEST: GET /api/v1/organizations/org_xyz789
EXAMPLE_RESPONSE: {"organization":{"id":"org_xyz789","name":"Acme Corp","member_count":25},"user_role":"admin","permissions":["user:*","project:*"]}

### PUT /api/v1/organizations/{org_id}
PURPOSE: Update organization settings
INPUTS: org_id(string,required,path_param), name(string,optional), description(string,optional), settings(object,optional)
OUTPUTS: organization(object,updated)
ERRORS: 403(insufficient_permissions), 404(not_found)
EXAMPLE_REQUEST: {"name":"Acme Corporation","settings":{"allow_signup":false}}
EXAMPLE_RESPONSE: {"id":"org_xyz789","name":"Acme Corporation","updated_at":"2024-01-20T12:00:00Z"}

### DELETE /api/v1/organizations/{org_id}
PURPOSE: Delete organization (owner only)
INPUTS: org_id(string,required,path_param), confirmation(string,required,value:org_slug)
OUTPUTS: success(boolean), message(string)
ERRORS: 403(not_owner), 400(invalid_confirmation)
EXAMPLE_REQUEST: {"confirmation":"acme"}
EXAMPLE_RESPONSE: {"success":true,"message":"Organization deleted"}

### POST /api/v1/organizations/{org_id}/invites
PURPOSE: Invite user to organization
INPUTS: org_id(string,required,path_param), email(string,required), role(string,required), expires_in(integer,optional,default:604800)
OUTPUTS: invite(object:id,email,role,expires_at,invite_url)
ERRORS: 403(insufficient_permissions), 409(already_member)
EXAMPLE_REQUEST: {"email":"newuser@example.com","role":"member"}
EXAMPLE_RESPONSE: {"invite":{"id":"inv_abc123","email":"newuser@example.com","role":"member","expires_at":"2024-01-27T12:00:00Z"}}

### GET /api/v1/organizations/{org_id}/members
PURPOSE: List organization members
INPUTS: org_id(string,required,path_param), page(integer,optional), limit(integer,optional), role(string,optional)
OUTPUTS: members(array), total(integer), page(integer)
ERRORS: 403(insufficient_permissions)
EXAMPLE_REQUEST: GET /api/v1/organizations/org_xyz789/members?role=admin
EXAMPLE_RESPONSE: {"members":[{"id":"usr_abc123","email":"admin@example.com","role":"admin","joined_at":"2024-01-01T00:00:00Z"}],"total":1}

### PUT /api/v1/organizations/{org_id}/members/{user_id}
PURPOSE: Update member role or permissions
INPUTS: org_id(string,required), user_id(string,required), role(string,optional), permissions(array,optional)
OUTPUTS: member(object,updated)
ERRORS: 403(insufficient_permissions), 404(member_not_found)
EXAMPLE_REQUEST: {"role":"admin","permissions":["project:create","user:invite"]}
EXAMPLE_RESPONSE: {"id":"usr_abc123","role":"admin","permissions":["project:create","user:invite"],"updated_at":"2024-01-20T12:00:00Z"}

### DELETE /api/v1/organizations/{org_id}/members/{user_id}
PURPOSE: Remove member from organization
INPUTS: org_id(string,required), user_id(string,required)
OUTPUTS: success(boolean), message(string)
ERRORS: 403(insufficient_permissions), 404(member_not_found), 400(cannot_remove_owner)
EXAMPLE_REQUEST: DELETE /api/v1/organizations/org_xyz789/members/usr_abc123
EXAMPLE_RESPONSE: {"success":true,"message":"Member removed"}

## RBAC_ENDPOINTS

### GET /api/v1/organizations/{org_id}/roles
PURPOSE: List available roles in organization
INPUTS: org_id(string,required), include_custom(boolean,optional,default:true)
OUTPUTS: roles(array:id,name,description,permissions,parent_role,is_custom)
ERRORS: 403(insufficient_permissions)
EXAMPLE_REQUEST: GET /api/v1/organizations/org_xyz789/roles
EXAMPLE_RESPONSE: {"roles":[{"id":"role_owner","name":"Owner","permissions":["*:*"],"is_custom":false}]}

### POST /api/v1/organizations/{org_id}/roles
PURPOSE: Create custom role
INPUTS: org_id(string,required), name(string,required), permissions(array,required), parent_role_id(string,optional)
OUTPUTS: role(object:id,name,permissions,created_at)
ERRORS: 403(insufficient_permissions), 409(role_exists)
EXAMPLE_REQUEST: {"name":"Project Manager","permissions":["project:*","user:read"],"parent_role_id":"role_member"}
EXAMPLE_RESPONSE: {"id":"role_pm123","name":"Project Manager","permissions":["project:*","user:read"],"created_at":"2024-01-20T12:00:00Z"}

### PUT /api/v1/organizations/{org_id}/roles/{role_id}
PURPOSE: Update custom role
INPUTS: org_id(string,required), role_id(string,required), name(string,optional), permissions(array,optional)
OUTPUTS: role(object,updated)
ERRORS: 403(insufficient_permissions), 404(role_not_found), 400(cannot_edit_system_role)
EXAMPLE_REQUEST: {"permissions":["project:*","user:read","report:read"]}
EXAMPLE_RESPONSE: {"id":"role_pm123","permissions":["project:*","user:read","report:read"],"updated_at":"2024-01-20T12:00:00Z"}

### DELETE /api/v1/organizations/{org_id}/roles/{role_id}
PURPOSE: Delete custom role
INPUTS: org_id(string,required), role_id(string,required), reassign_to(string,required)
OUTPUTS: success(boolean), members_reassigned(integer)
ERRORS: 403(insufficient_permissions), 400(cannot_delete_system_role), 409(role_in_use_no_reassign)
EXAMPLE_REQUEST: {"reassign_to":"role_member"}
EXAMPLE_RESPONSE: {"success":true,"members_reassigned":3}

### GET /api/v1/organizations/{org_id}/permissions
PURPOSE: Get current user's permissions in organization
INPUTS: org_id(string,required), resource_type(string,optional), resource_id(string,optional)
OUTPUTS: permissions(array), role(string), inherited_from(string,optional)
ERRORS: 403(not_member)
EXAMPLE_REQUEST: GET /api/v1/organizations/org_xyz789/permissions?resource_type=project
EXAMPLE_RESPONSE: {"permissions":["project:create","project:read","project:update"],"role":"admin"}

## SCIM_ENDPOINTS

### GET /scim/v2/Users
PURPOSE: List users via SCIM protocol
INPUTS: filter(string,optional), startIndex(integer,optional), count(integer,optional)
OUTPUTS: schemas(array), totalResults(integer), Resources(array)
ERRORS: 401(invalid_bearer_token)
HEADERS: Authorization: Bearer {scim_token}
EXAMPLE_REQUEST: GET /scim/v2/Users?filter=userName eq "john.doe"
EXAMPLE_RESPONSE: {"schemas":["urn:ietf:params:scim:api:messages:2.0:ListResponse"],"totalResults":1,"Resources":[{...scim_user}]}

### POST /scim/v2/Users
PURPOSE: Create user via SCIM protocol
INPUTS: schemas(array,required), userName(string,required), emails(array,required), name(object,optional), active(boolean,optional)
OUTPUTS: schemas(array), id(string), userName(string), meta(object)
ERRORS: 401(invalid_bearer_token), 409(user_exists)
HEADERS: Authorization: Bearer {scim_token}
EXAMPLE_REQUEST: {"schemas":["urn:ietf:params:scim:schemas:core:2.0:User"],"userName":"john.doe","emails":[{"value":"john@example.com","primary":true}]}
EXAMPLE_RESPONSE: {"schemas":["urn:ietf:params:scim:schemas:core:2.0:User"],"id":"usr_abc123","userName":"john.doe"}

### PUT /scim/v2/Users/{user_id}
PURPOSE: Update user via SCIM protocol
INPUTS: user_id(string,required), schemas(array,required), active(boolean,optional), emails(array,optional)
OUTPUTS: schemas(array), id(string), updated_fields(object)
ERRORS: 404(user_not_found), 401(invalid_bearer_token)
EXAMPLE_REQUEST: {"schemas":["urn:ietf:params:scim:schemas:core:2.0:User"],"active":false}
EXAMPLE_RESPONSE: {"schemas":["urn:ietf:params:scim:schemas:core:2.0:User"],"id":"usr_abc123","active":false}

### DELETE /scim/v2/Users/{user_id}
PURPOSE: Delete user via SCIM protocol
INPUTS: user_id(string,required,path_param)
OUTPUTS: none (204 No Content on success)
ERRORS: 404(user_not_found), 401(invalid_bearer_token)
EXAMPLE_REQUEST: DELETE /scim/v2/Users/usr_abc123
EXAMPLE_RESPONSE: HTTP 204 No Content

### GET /scim/v2/Groups
PURPOSE: List groups (roles) via SCIM protocol
INPUTS: filter(string,optional), startIndex(integer,optional), count(integer,optional)
OUTPUTS: schemas(array), totalResults(integer), Resources(array)
ERRORS: 401(invalid_bearer_token)
EXAMPLE_REQUEST: GET /scim/v2/Groups
EXAMPLE_RESPONSE: {"schemas":["urn:ietf:params:scim:api:messages:2.0:ListResponse"],"totalResults":4,"Resources":[{...scim_groups}]}

## AUDIT_LOG_ENDPOINTS

### GET /api/v1/audit-logs
PURPOSE: Query audit logs for organization
INPUTS: org_id(string,required), start_date(datetime,optional), end_date(datetime,optional), event_type(string,optional), user_id(string,optional), limit(integer,optional)
OUTPUTS: logs(array:id,event_type,event_name,user_id,ip_address,timestamp,metadata), total(integer)
ERRORS: 403(insufficient_permissions)
EXAMPLE_REQUEST: GET /api/v1/audit-logs?org_id=org_xyz789&event_type=AUTH
EXAMPLE_RESPONSE: {"logs":[{"id":"log_123","event_type":"AUTH","event_name":"user.login","timestamp":"2024-01-20T12:00:00Z"}],"total":150}

### GET /api/v1/audit-logs/verify
PURPOSE: Verify audit log integrity via hash chain
INPUTS: org_id(string,required), start_date(datetime,required), end_date(datetime,required)
OUTPUTS: verified(boolean), total_logs(integer), broken_links(array,optional), integrity_score(float)
ERRORS: 403(insufficient_permissions)
EXAMPLE_REQUEST: GET /api/v1/audit-logs/verify?org_id=org_xyz789&start_date=2024-01-01&end_date=2024-01-31
EXAMPLE_RESPONSE: {"verified":true,"total_logs":1523,"integrity_score":1.0}

### GET /api/v1/audit-logs/export
PURPOSE: Export audit logs in various formats
INPUTS: org_id(string,required), format(string,required,enum:json|csv|cef), start_date(datetime,optional), compliance_filter(string,optional,enum:SOC2|HIPAA|GDPR)
OUTPUTS: download_url(string), expires_at(datetime), file_size(integer)
ERRORS: 403(insufficient_permissions), 400(invalid_format)
EXAMPLE_REQUEST: GET /api/v1/audit-logs/export?org_id=org_xyz789&format=json&compliance_filter=HIPAA
EXAMPLE_RESPONSE: {"download_url":"https://downloads.example.com/audit_123.json","expires_at":"2024-01-20T13:00:00Z","file_size":1048576}

## WEBHOOK_ENDPOINTS

### GET /api/v1/webhooks
PURPOSE: List configured webhooks for organization
INPUTS: org_id(string,required)
OUTPUTS: webhooks(array:id,url,events,is_active,created_at,last_triggered_at,failure_count)
ERRORS: 403(insufficient_permissions)
EXAMPLE_REQUEST: GET /api/v1/webhooks?org_id=org_xyz789
EXAMPLE_RESPONSE: {"webhooks":[{"id":"wh_123","url":"https://example.com/webhook","events":["user.created"],"is_active":true}]}

### POST /api/v1/webhooks
PURPOSE: Create new webhook endpoint
INPUTS: org_id(string,required), url(string,required,valid_url), events(array,required), secret(string,optional), max_retries(integer,optional,default:3)
OUTPUTS: webhook(object:id,url,events,secret,created_at)
ERRORS: 403(insufficient_permissions), 400(invalid_url)
EXAMPLE_REQUEST: {"org_id":"org_xyz789","url":"https://example.com/webhook","events":["user.created","user.deleted"]}
EXAMPLE_RESPONSE: {"id":"wh_123","url":"https://example.com/webhook","events":["user.created","user.deleted"],"secret":"whsec_abc123"}

### PUT /api/v1/webhooks/{webhook_id}
PURPOSE: Update webhook configuration
INPUTS: webhook_id(string,required), url(string,optional), events(array,optional), is_active(boolean,optional)
OUTPUTS: webhook(object,updated)
ERRORS: 404(webhook_not_found), 403(insufficient_permissions)
EXAMPLE_REQUEST: {"events":["user.created","user.updated","user.deleted"],"is_active":true}
EXAMPLE_RESPONSE: {"id":"wh_123","events":["user.created","user.updated","user.deleted"],"is_active":true,"updated_at":"2024-01-20T12:00:00Z"}

### DELETE /api/v1/webhooks/{webhook_id}
PURPOSE: Delete webhook endpoint
INPUTS: webhook_id(string,required,path_param)
OUTPUTS: success(boolean), message(string)
ERRORS: 404(webhook_not_found), 403(insufficient_permissions)
EXAMPLE_REQUEST: DELETE /api/v1/webhooks/wh_123
EXAMPLE_RESPONSE: {"success":true,"message":"Webhook deleted"}

### POST /api/v1/webhooks/{webhook_id}/test
PURPOSE: Send test event to webhook endpoint
INPUTS: webhook_id(string,required), event_type(string,required)
OUTPUTS: success(boolean), response_code(integer), response_time_ms(integer), response_body(string,truncated)
ERRORS: 404(webhook_not_found), 503(webhook_unreachable)
EXAMPLE_REQUEST: {"event_type":"user.created"}
EXAMPLE_RESPONSE: {"success":true,"response_code":200,"response_time_ms":145,"response_body":"OK"}

### GET /api/v1/webhooks/{webhook_id}/deliveries
PURPOSE: Get webhook delivery history
INPUTS: webhook_id(string,required), limit(integer,optional,default:20)
OUTPUTS: deliveries(array:id,event_type,timestamp,response_code,response_time_ms,success,retry_count)
ERRORS: 404(webhook_not_found), 403(insufficient_permissions)
EXAMPLE_REQUEST: GET /api/v1/webhooks/wh_123/deliveries?limit=10
EXAMPLE_RESPONSE: {"deliveries":[{"id":"del_456","event_type":"user.created","timestamp":"2024-01-20T12:00:00Z","response_code":200,"success":true}]}

## ERROR_CODES

### Authentication Errors (4xx)
- 400: Bad Request - Invalid input parameters
- 401: Unauthorized - Invalid or missing authentication
- 403: Forbidden - Insufficient permissions
- 404: Not Found - Resource does not exist
- 409: Conflict - Resource already exists
- 410: Gone - Resource expired (tokens, invites)
- 422: Unprocessable Entity - Validation failed
- 429: Too Many Requests - Rate limit exceeded

### Server Errors (5xx)
- 500: Internal Server Error - Unexpected server error
- 502: Bad Gateway - Upstream service error
- 503: Service Unavailable - Service temporarily down
- 504: Gateway Timeout - Request timeout

## RATE_LIMITS

### Default Limits
- Anonymous: 60 requests/hour
- Authenticated: 600 requests/hour
- Organization: 6000 requests/hour

### Endpoint-Specific Limits
- Authentication: 10/minute per IP
- Password Reset: 3/hour per email
- Magic Links: 3/hour per email
- Email Verification: 3/hour per user
- Webhook Test: 10/hour per webhook

### Rate Limit Headers
- X-RateLimit-Limit: Maximum requests allowed
- X-RateLimit-Remaining: Requests remaining
- X-RateLimit-Reset: Unix timestamp when limit resets
- Retry-After: Seconds until retry allowed (429 responses)

## WEBHOOK_EVENTS

### User Events
- user.created: New user account created
- user.updated: User profile updated
- user.deleted: User account deleted
- user.suspended: User account suspended
- user.reactivated: User account reactivated
- user.email_verified: Email address verified
- user.password_changed: Password changed

### Authentication Events
- auth.login: Successful login
- auth.logout: User logged out
- auth.failed: Failed login attempt
- auth.mfa_enabled: MFA enabled
- auth.mfa_disabled: MFA disabled
- auth.passkey_added: Passkey registered
- auth.passkey_removed: Passkey deleted

### Organization Events
- organization.created: New organization created
- organization.updated: Organization settings updated
- organization.deleted: Organization deleted
- organization.member_added: Member joined organization
- organization.member_removed: Member left organization
- organization.member_role_changed: Member role updated
- organization.invite_sent: Invitation sent
- organization.invite_accepted: Invitation accepted

### Security Events
- security.suspicious_activity: Unusual activity detected
- security.threat_blocked: Security threat prevented
- security.policy_violation: Security policy violated
- security.api_key_created: API key generated
- security.api_key_revoked: API key revoked

### Compliance Events
- compliance.audit_exported: Audit logs exported
- compliance.data_exported: User data exported (GDPR)
- compliance.data_deleted: User data deleted (GDPR)
- compliance.consent_updated: User consent updated

## COMPLIANCE_STANDARDS

### SOC2_REQUIREMENTS
- Audit logging for all data access
- Encryption at rest and in transit
- Access control with least privilege
- Regular security assessments
- Incident response procedures

### HIPAA_REQUIREMENTS
- PHI encryption (AES-256)
- Access logging and monitoring
- Business Associate Agreements (BAA)
- Data retention policies (6 years)
- Breach notification procedures

### GDPR_REQUIREMENTS
- User consent management
- Right to access data
- Right to deletion
- Data portability
- Privacy by design

### PCI_DSS_REQUIREMENTS
- No credit card storage
- Tokenization for payment data
- Network segmentation
- Regular security scanning
- Access control measures

## SDK_INITIALIZATION

### TypeScript/JavaScript
const janua = new Janua({
  apiKey: process.env.JANUA_API_KEY,
  environment: 'production', // or 'sandbox'
  organizationId: 'org_xyz789', // optional, for multi-tenant
  timeout: 30000, // 30 seconds
  retries: 3
})

### Python
from janua import Janua

janua = Janua(
    api_key=os.getenv('JANUA_API_KEY'),
    environment='production',
    organization_id='org_xyz789',
    timeout=30,
    retries=3
)

### Go
import "github.com/madfam-io/janua-go"

client := janua.NewClient(
    janua.WithAPIKey(os.Getenv("JANUA_API_KEY")),
    janua.WithEnvironment("production"),
    janua.WithOrgID("org_xyz789"),
)

## BEST_PRACTICES

### Security
1. Always use HTTPS for API calls
2. Store API keys in environment variables
3. Implement rate limiting on your side
4. Validate webhook signatures
5. Use short-lived tokens
6. Enable MFA for sensitive operations
7. Regular security audits

### Performance
1. Use pagination for list endpoints
2. Cache frequently accessed data
3. Batch operations when possible
4. Implement exponential backoff
5. Use webhooks instead of polling
6. Compress request/response bodies

### Error Handling
1. Always check error responses
2. Implement retry logic with backoff
3. Log errors for debugging
4. Handle rate limits gracefully
5. Validate inputs client-side
6. Use idempotency keys for critical operations

### Data Management
1. Regular backups of critical data
2. Implement data retention policies
3. Use audit logs for compliance
4. Encrypt sensitive data
5. Implement GDPR compliance
6. Regular data validation

END_JANUA_API_DOCS_LLM_VERSION_1.0`

export async function GET() {
  return new NextResponse(LLM_DOCS, {
    status: 200,
    headers: {
      'Content-Type': 'text/plain; charset=utf-8',
      'Cache-Control': 'public, max-age=3600', // Cache for 1 hour
      'X-Robots-Tag': 'noindex', // Prevent search engine indexing
    },
  })
}

// Also support POST for potential future features like filtered documentation
export async function POST(request: Request) {
  try {
    const body = await request.json()
    const { filter, format } = body

    // For now, return the same full documentation
    // In the future, this could filter by endpoints, compliance, or format
    if (filter || format) {
      // Placeholder for filtered/formatted responses
      return new NextResponse(LLM_DOCS, {
        status: 200,
        headers: {
          'Content-Type': format === 'json' ? 'application/json' : 'text/plain',
        },
      })
    }

    return new NextResponse(LLM_DOCS, {
      status: 200,
      headers: {
        'Content-Type': 'text/plain; charset=utf-8',
      },
    })
  } catch (_error) {
    return new NextResponse('Invalid request', { status: 400 })
  }
}