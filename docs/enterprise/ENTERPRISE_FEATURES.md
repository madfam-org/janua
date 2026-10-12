# Janua Enterprise Features Documentation

> [!NOTE]
> **Claim status:** This document describes the enterprise capabilities
> implemented in this repository. Commercial availability is governed by the
> [GA claim matrix](GA_CLAIM_MATRIX.md): RBAC and audit logging are **beta**
> (hosted proof pending), and SCIM 2.0 provisioning is **roadmap** — it must
> not be sold as available until synthetics and monitoring exist.

## Overview

Janua's enterprise features provide comprehensive multi-tenant architecture, advanced security, compliance, and integration capabilities designed for large-scale deployments.

## Table of Contents

1. [Multi-Tenant Architecture](#multi-tenant-architecture)
2. [Role-Based Access Control (RBAC)](#role-based-access-control-rbac)
3. [SCIM 2.0 Integration](#scim-20-integration)
4. [Audit Logging](#audit-logging)
5. [Webhook System](#webhook-system)
6. [API Reference](#api-reference)
7. [Migration Guide](#migration-guide)

## Multi-Tenant Architecture

### Overview

Janua implements complete tenant isolation with automatic context propagation throughout the application stack.

### Key Features

- **Automatic Tenant Isolation**: All queries automatically filtered by tenant context
- **Row-Level Security**: Database-level isolation for maximum security
- **Tenant Context Propagation**: Automatic context passing through middleware
- **Multiple Isolation Strategies**: Subdomain, JWT claims, headers, query params

### Implementation

#### Setting Tenant Context

```python
from app.core.tenant_context import TenantContext

# Set context for a request
TenantContext.set(
    tenant_id=org.tenant_id,
    organization_id=org.id,
    user_id=user.id
)

# Get current context
tenant_id = TenantContext.get_tenant_id()
org_id = TenantContext.get_organization_id()
```

#### Tenant Middleware

The `TenantMiddleware` automatically extracts tenant context from:

1. **Subdomain**: `acme.janua.dev` → Organization: acme
2. **JWT Token**: Claims include `tid` (tenant_id) and `oid` (organization_id)
3. **Headers**: `X-Tenant-ID` and `X-Organization-ID` for service-to-service
4. **Query Parameters**: `?tenant_id=xxx&organization_id=yyy`

### Configuration

```python
# Enable multi-tenancy features
ENABLE_MULTI_TENANCY = True
TENANT_ISOLATION_MODE = "strict"  # strict, relaxed, or disabled
```

## Role-Based Access Control (RBAC)

### Overview

Hierarchical permission system with fine-grained access control and custom role creation.

### Core Concepts

#### Permissions

Permissions follow the format: `resource:action`

- `user:read` - Read user data
- `project:*` - All actions on projects
- `*:admin` - Admin access to all resources

#### Role Hierarchy

Roles can inherit from parent roles:

```
Owner (all permissions)
  ├── Admin (administrative permissions)
  │     └── Manager (team management)
  └── Member (standard permissions)
        └── Viewer (read-only)
```

### Using RBAC

#### Check Permissions

```python
from app.core.rbac_engine import rbac_engine, ResourceType, Action

# Check if user can perform action
can_delete = await rbac_engine.check_permission(
    session=db,
    user_id=user_id,
    resource_type=ResourceType.USER,
    action=Action.DELETE,
    resource_id=target_user_id  # Optional: for resource-specific checks
)
```

#### Decorator-Based Authorization

```python
from app.core.rbac_engine import require_permission

@router.delete("/users/{user_id}")
@require_permission(ResourceType.USER, Action.DELETE)
async def delete_user(user_id: str, db: AsyncSession = Depends(get_db)):
    # Only users with user:delete permission can access
    pass
```

#### Creating Custom Roles

```python
role = OrganizationRole(
    organization_id=org_id,
    name="Project Manager",
    description="Manages projects and team members",
    permissions=[
        "project:*",
        "user:read",
        "user:invite",
        "report:read"
    ],
    parent_role_id=member_role_id  # Inherit from Member role
)
```

### Default Roles

| Role | Permissions | Description |
|------|------------|-------------|
| Owner | `*:*` | Full control over organization |
| Admin | `organization:*`, `user:*`, `role:*` | Administrative access |
| Member | `user:own:*`, `project:create` | Standard member access |
| Viewer | `*:read` | Read-only access |

## SCIM 2.0 Integration

### Overview

System for Cross-domain Identity Management (SCIM) 2.0 support for enterprise identity providers.

### Supported Operations

- User provisioning (create, read, update, delete)
- Group management (roles)
- Bulk operations
- Filtering and pagination
- Schema discovery

### Configuration

1. Enable SCIM for organization:

```python
organization.scim_enabled = True
await db.commit()
```

2. Generate SCIM bearer token:

```python
scim_token = generate_scim_token(organization_id)
```

### SCIM Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/scim/v2/Users` | GET | List users |
| `/scim/v2/Users` | POST | Create user |
| `/scim/v2/Users/{id}` | GET | Get user |
| `/scim/v2/Users/{id}` | PUT | Update user |
| `/scim/v2/Users/{id}` | DELETE | Delete user |
| `/scim/v2/Groups` | GET | List groups (roles) |
| `/scim/v2/ServiceProviderConfig` | GET | Get configuration |
| `/scim/v2/Schemas` | GET | Get supported schemas |

### Example: Provision User via SCIM

```bash
curl -X POST https://api.janua.dev/scim/v2/Users \
  -H "Authorization: Bearer ${SCIM_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "schemas": ["urn:ietf:params:scim:schemas:core:2.0:User"],
    "userName": "john.doe",
    "emails": [
      {
        "value": "john.doe@company.com",
        "type": "work",
        "primary": true
      }
    ],
    "name": {
      "givenName": "John",
      "familyName": "Doe"
    },
    "active": true
  }'
```

## Audit Logging

### Overview

Tamper-proof audit logging with hash chain for compliance (SOC 2, HIPAA, GDPR).

### Features

- **Hash Chain**: Each entry stores the hash of the previous entry of the same tenant
- **Tamper Detection**: `verify_integrity` recomputes the chain and reports the first broken entry
- **Compliance Context**: severity, organization and compliance fields are stored with the entry
- **Session Ownership**: entries commit with the caller's transaction, or in a session the logger owns
- **Export**: JSON export to the dedicated audit bucket

### Creating Audit Logs

`app.services.audit_logger.AuditLogger` writes `audit_logs` rows. Over a
caller's session it flushes the row and never commits; the caller commits.

```python
from app.services.audit_logger import AuditEventType, AuditLogger

await AuditLogger(db).log(
    event_type=AuditEventType.USER_UPDATE,
    tenant_id=str(org_id),
    identity_id=str(current_user.id),
    organization_id=str(org_id),
    resource_type="user",
    resource_id=str(user.id),
    details={"field": "email"},
    ip_address=request.client.host,
    user_agent=request.headers.get("user-agent"),
    severity="info",
    compliance_context={"framework": "SOC2"},
)
await db.commit()
```

Background work with no request session uses a logger that owns its session
and commits each entry:

```python
async with AuditLogger.with_own_session() as audit:
    await audit.log(event_type=AuditEventType.DATA_ARCHIVAL, tenant_id=str(org_id))
```

`severity`, `organization_id` and the compliance fields have no column of their
own; they are stored in `details` under `audit_context`.

### Verifying Log Integrity

```python
result = await AuditLogger(db).verify_integrity(
    tenant_id=str(org_id),
    start_date=datetime(2024, 1, 1),
    end_date=datetime(2024, 12, 31),
)

if not result["valid"]:
    print(result["message"])  # "Hash chain broken at index N"
```

### Exporting Audit Logs

```python
# Returns a presigned URL when the audit bucket is configured, else the export id
url = await AuditLogger(db).export_logs(
    tenant_id=str(org_id),
    start_date=start,
    end_date=end,
    format="json",
)
```

### Retention Policies

Callers pass `retention_period` (days) with the entry. Typical values:

| Compliance | Retention Period |
|------------|-----------------|
| HIPAA | 6 years |
| SOC 2 | 7 years |
| GDPR | 3 years |
| PCI-DSS | 1 year |
| Default | 2 years |

## Webhook System

### Overview

Real-time event notifications with reliable delivery and retry logic.

### Features

- **Event-Driven**: Automatic webhook dispatch on system events
- **HMAC Signatures**: Secure webhook verification
- **Retry Logic**: Exponential backoff with configurable retries
- **Delivery Tracking**: Full request/response logging
- **Batch Operations**: Efficient bulk webhook processing

### Configuring Webhooks

```python
endpoint = WebhookEndpoint(
    organization_id=org_id,
    url="https://your-app.com/webhooks",
    secret="your-webhook-secret",
    events=[
        "user.created",
        "user.updated",
        "organization.member_added"
    ],
    max_retries=3,
    retry_delay=60  # seconds
)
```

### Emitting Events

```python
from app.core.webhook_dispatcher import emit_webhook_event

await emit_webhook_event(
    event_type="user.created",
    data={
        "user_id": str(user.id),
        "email": user.email,
        "created_at": user.created_at.isoformat()
    },
    session=db,
    user_id=str(user.id),
    organization_id=str(org.id)
)
```

### Webhook Payload Format

```json
{
  "id": "evt_1234567890",
  "type": "user.created",
  "created_at": "2024-01-20T12:00:00Z",
  "data": {
    "user_id": "usr_abc123",
    "email": "user@example.com"
  },
  "organization_id": "org_xyz789"
}
```

### Verifying Webhook Signatures

```python
from app.core.webhook_dispatcher import verify_webhook_signature

# In your webhook receiver
def handle_webhook(request):
    payload = request.body
    signature = request.headers["X-Webhook-Signature"]
    timestamp = request.headers["X-Webhook-Timestamp"]

    is_valid = verify_webhook_signature(
        payload=payload,
        signature=signature,
        secret=WEBHOOK_SECRET,
        timestamp=timestamp,
        max_age_seconds=300
    )

    if not is_valid:
        return Response(status=401)
```

### Standard Event Types

| Category | Event Types |
|----------|------------|
| User | `user.created`, `user.updated`, `user.deleted`, `user.suspended` |
| Auth | `auth.login`, `auth.logout`, `auth.failed`, `auth.mfa_enabled` |
| Organization | `organization.created`, `organization.member_added`, `organization.role_changed` |
| Security | `security.threat_detected`, `security.policy_violation` |
| Compliance | `compliance.audit_started`, `compliance.violation` |

## API Reference

### Enterprise Endpoints

#### Organizations

```http
GET /api/v1/organizations/{org_id}/settings
PUT /api/v1/organizations/{org_id}/settings
GET /api/v1/organizations/{org_id}/limits
```

#### RBAC

```http
GET /api/v1/organizations/{org_id}/roles
POST /api/v1/organizations/{org_id}/roles
PUT /api/v1/organizations/{org_id}/roles/{role_id}
DELETE /api/v1/organizations/{org_id}/roles/{role_id}

GET /api/v1/organizations/{org_id}/members/{member_id}/permissions
PUT /api/v1/organizations/{org_id}/members/{member_id}/role
```

#### Audit Logs

```http
GET /api/v1/audit-logs
GET /api/v1/audit-logs/verify
GET /api/v1/audit-logs/export
```

#### Webhooks

```http
GET /api/v1/webhooks
POST /api/v1/webhooks
PUT /api/v1/webhooks/{webhook_id}
DELETE /api/v1/webhooks/{webhook_id}
POST /api/v1/webhooks/{webhook_id}/test
GET /api/v1/webhooks/{webhook_id}/deliveries
```

## Migration Guide

### Enabling Enterprise Features

1. **Run Database Migration**

```bash
alembic upgrade 003
```

2. **Update Environment Variables**

```env
# Enable enterprise features
ENABLE_MULTI_TENANCY=true
ENABLE_RBAC=true
ENABLE_SCIM=true
ENABLE_AUDIT_LOGGING=true
ENABLE_WEBHOOKS=true

# Compliance settings
COMPLIANCE_MODE=SOC2,HIPAA
AUDIT_RETENTION_DAYS=2555
```

3. **Initialize Default Roles**

```python
from app.core.rbac_engine import initialize_default_roles

await initialize_default_roles(session, organization_id)
```

4. **Configure Tenant Isolation**

```python
# In your database session factory
from app.core.tenant_context import configure_tenant_filtering

async def get_db():
    async with SessionLocal() as session:
        configure_tenant_filtering(session)
        yield session
```

### Best Practices

1. **Always Set Tenant Context**: Ensure tenant context is set for all requests
2. **Use RBAC Decorators**: Protect endpoints with permission decorators
3. **Log Critical Events**: Audit log all security and compliance events
4. **Verify Webhook Signatures**: Always validate webhook authenticity
5. **Regular Integrity Checks**: Schedule audit log verification
6. **Monitor Webhook Failures**: Track and alert on webhook delivery issues

### Troubleshooting

#### Tenant Context Not Set

```python
# Check if context is set
if not TenantContext.get_tenant_id():
    raise HTTPException(403, "Tenant context required")
```

#### Permission Denied

```python
# Debug permission checks
permissions = await rbac_engine.get_user_permissions(
    session, user_id, organization_id
)
print(f"User permissions: {permissions}")
```

#### Audit Log Integrity Failed

```python
# Identify the first tampered, reordered or missing entry
result = await AuditLogger(db).verify_integrity(tenant_id=str(org_id))
if not result["valid"]:
    print(f"Chain broken at index {result['broken_at']} of {result['count']}")
```

#### Webhook Not Delivering

```python
# Check webhook endpoint status
endpoint = await db.get(WebhookEndpoint, webhook_id)
print(f"Active: {endpoint.is_active}")
print(f"Failures: {endpoint.failure_count}")
print(f"Last error: {endpoint.last_failure_at}")
```

## Security Considerations

1. **Tenant Isolation**: Never expose data across tenant boundaries
2. **Permission Validation**: Always validate permissions server-side
3. **Audit Everything**: Log all administrative and security events
4. **Webhook Secrets**: Use strong, unique secrets for each endpoint
5. **SCIM Tokens**: Rotate SCIM bearer tokens regularly
6. **Hash Chain**: Never modify audit logs directly in database

## Performance Optimization

1. **Cache Permissions**: Cache role permissions for session duration
2. **Batch Webhooks**: Process webhook deliveries in batches
3. **Async Audit Logging**: Log audit events asynchronously
4. **Index Tenant Columns**: Ensure tenant_id columns are indexed
5. **Partition Large Tables**: Consider partitioning audit logs by date

## Compliance Certifications

Janua's enterprise features support compliance with:

- **SOC 2 Type II**: Comprehensive audit logging and access controls
- **HIPAA**: Healthcare data protection and audit requirements
- **GDPR**: Data privacy and retention policies
- **PCI-DSS**: Payment card industry security standards
- **ISO 27001**: Information security management

## Support

For enterprise support and custom implementations:

- Email: enterprise@janua.dev
- Documentation: https://janua.dev/docs/enterprise
- Enterprise Portal: https://enterprise.janua.dev