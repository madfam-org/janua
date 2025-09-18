# Multi-Tenant Architecture

Build scalable SaaS applications with complete tenant isolation, automatic context propagation, and flexible deployment strategies.

## Overview

Plinto's multi-tenant architecture provides complete isolation between organizations while maintaining optimal performance and security. Every query, session, and operation is automatically scoped to the appropriate tenant context, preventing data leakage and ensuring compliance.

## Key Features

- **Automatic Tenant Isolation**: All database queries filtered by tenant context
- **Row-Level Security**: Database-level isolation for maximum security
- **Flexible Context Resolution**: Subdomain, JWT, headers, or query parameters
- **Cross-Tenant Operations**: Controlled data sharing between tenants
- **Scalable Architecture**: Supports thousands of tenants per instance

## Quick Start

### 1. Enable Multi-Tenancy

```typescript
import { plinto } from '@plinto/typescript-sdk'

// Configure multi-tenancy
plinto.configure({
  multiTenant: {
    enabled: true,
    isolationMode: 'strict', // strict, relaxed, or shared
    contextSources: ['subdomain', 'jwt', 'header'],
    defaultTenant: null // No fallback for strict mode
  }
})
```

### 2. Create Organization

```typescript
// Create new organization (tenant)
const organization = await plinto.organizations.create({
  name: 'Acme Corporation',
  slug: 'acme', // Used for subdomain: acme.yourapp.com
  plan: 'business',
  settings: {
    maxUsers: 100,
    features: ['sso', 'audit-logs', 'advanced-rbac']
  }
})

console.log('Organization created:', organization.id)
console.log('Tenant ID:', organization.tenantId)
```

### 3. Set Tenant Context

```typescript
// Middleware to set tenant context
app.use(async (req, res, next) => {
  try {
    // Multiple ways to resolve tenant context
    const context = await plinto.tenancy.resolveContext(req, {
      sources: ['subdomain', 'jwt', 'header'],
      required: true
    })

    // Set context for this request
    plinto.tenancy.setContext({
      tenantId: context.tenantId,
      organizationId: context.organizationId,
      userId: context.userId
    })

    req.tenant = context
    next()
  } catch (error) {
    res.status(400).json({ error: 'Invalid tenant context' })
  }
})
```

### 4. Tenant-Scoped Operations

```typescript
// All operations are automatically tenant-scoped
const users = await plinto.users.list({
  // Automatically filtered by current tenant context
  limit: 20
})

const projects = await plinto.projects.create({
  name: 'New Project',
  // Automatically assigned to current tenant
})

// Current tenant context
const currentContext = plinto.tenancy.getContext()
console.log('Operating in tenant:', currentContext.tenantId)
```

## Implementation Guide

### Backend Setup

#### Express.js Implementation

```javascript
const express = require('express')
const { Plinto } = require('@plinto/typescript-sdk')

const app = express()
const plinto = new Plinto({
  apiKey: process.env.PLINTO_API_KEY,
  multiTenant: {
    enabled: true,
    isolationMode: 'strict',
    contextSources: ['subdomain', 'jwt', 'header', 'query'],
    subdomainExtraction: {
      pattern: /^(\w+)\./, // Extract 'acme' from 'acme.app.com'
      skipSubdomains: ['www', 'api', 'cdn']
    }
  }
})

// Tenant context middleware
const resolveTenantContext = async (req, res, next) => {
  try {
    let tenantId = null
    let organizationId = null

    // 1. Try subdomain first
    if (req.hostname !== 'localhost') {
      const subdomain = req.hostname.split('.')[0]
      if (subdomain && subdomain !== 'www') {
        const org = await plinto.organizations.getBySlug(subdomain)
        if (org) {
          tenantId = org.tenantId
          organizationId = org.id
        }
      }
    }

    // 2. Try JWT token
    if (!tenantId && req.headers.authorization) {
      const token = req.headers.authorization.split(' ')[1]
      try {
        const decoded = await plinto.auth.verifyToken(token)
        tenantId = decoded.tenantId || decoded.tid
        organizationId = decoded.organizationId || decoded.oid
      } catch (e) {
        // Token invalid, continue trying other methods
      }
    }

    // 3. Try headers
    if (!tenantId) {
      tenantId = req.headers['x-tenant-id']
      organizationId = req.headers['x-organization-id']
    }

    // 4. Try query parameters (least secure, use carefully)
    if (!tenantId) {
      tenantId = req.query.tenant_id
      organizationId = req.query.organization_id
    }

    if (!tenantId) {
      return res.status(400).json({
        error: 'Tenant context required',
        hint: 'Use subdomain, JWT token, or X-Tenant-ID header'
      })
    }

    // Validate tenant exists and is active
    const tenant = await plinto.tenancy.validateTenant(tenantId)
    if (!tenant.active) {
      return res.status(403).json({
        error: 'Tenant suspended or inactive'
      })
    }

    // Set tenant context for this request
    plinto.tenancy.setContext({
      tenantId,
      organizationId,
      userId: req.user?.id,
      ipAddress: req.ip,
      userAgent: req.headers['user-agent']
    })

    req.tenant = {
      id: tenantId,
      organizationId,
      organization: tenant.organization
    }

    next()
  } catch (error) {
    console.error('Tenant context resolution failed:', error)
    res.status(500).json({ error: 'Failed to resolve tenant context' })
  }
}

// Apply tenant context globally
app.use(resolveTenantContext)

// Organization management endpoints
app.post('/api/organizations', async (req, res) => {
  const { name, slug, plan, settings } = req.body

  try {
    // Validate slug availability
    const existing = await plinto.organizations.getBySlug(slug)
    if (existing) {
      return res.status(409).json({ error: 'Organization slug already exists' })
    }

    // Create organization with tenant
    const organization = await plinto.organizations.create({
      name,
      slug,
      plan,
      settings,
      owner: req.user.id,
      billing: {
        plan,
        trialEndsAt: new Date(Date.now() + 14 * 24 * 60 * 60 * 1000) // 14 days
      }
    })

    // Create default roles for the organization
    await plinto.rbac.initializeDefaultRoles(organization.id)

    // Add creator as owner
    await plinto.organizations.addMember({
      organizationId: organization.id,
      userId: req.user.id,
      role: 'owner'
    })

    res.json({
      organization,
      message: 'Organization created successfully'
    })
  } catch (error) {
    res.status(400).json({ error: error.message })
  }
})

app.get('/api/organizations/:orgId', async (req, res) => {
  try {
    const { orgId } = req.params

    // Verify user has access to this organization
    const membership = await plinto.organizations.getMembership({
      organizationId: orgId,
      userId: req.user.id
    })

    if (!membership) {
      return res.status(403).json({ error: 'Access denied' })
    }

    const organization = await plinto.organizations.get(orgId)
    const stats = await plinto.organizations.getStats(orgId)

    res.json({
      organization,
      membership,
      stats,
      permissions: membership.permissions
    })
  } catch (error) {
    res.status(400).json({ error: error.message })
  }
})

// Tenant-scoped user management
app.get('/api/users', async (req, res) => {
  try {
    // Users are automatically filtered by tenant context
    const users = await plinto.users.list({
      page: parseInt(req.query.page) || 1,
      limit: parseInt(req.query.limit) || 20,
      search: req.query.search,
      role: req.query.role
    })

    res.json({
      users: users.data.map(user => ({
        id: user.id,
        email: user.email,
        name: user.name,
        role: user.organizationRole,
        status: user.status,
        lastLoginAt: user.lastLoginAt,
        createdAt: user.createdAt
      })),
      pagination: {
        page: users.page,
        totalPages: users.totalPages,
        totalItems: users.total
      }
    })
  } catch (error) {
    res.status(400).json({ error: error.message })
  }
})

// Cross-tenant operations (admin only)
app.get('/api/admin/tenants', async (req, res) => {
  try {
    // Verify admin privileges
    if (!req.user.isSystemAdmin) {
      return res.status(403).json({ error: 'System admin access required' })
    }

    // Temporarily bypass tenant isolation
    const tenants = await plinto.tenancy.withSystemContext(async () => {
      return await plinto.organizations.list({
        includeStats: true,
        page: parseInt(req.query.page) || 1,
        limit: parseInt(req.query.limit) || 50
      })
    })

    res.json(tenants)
  } catch (error) {
    res.status(400).json({ error: error.message })
  }
})

// Tenant migration endpoint
app.post('/api/organizations/:orgId/migrate', async (req, res) => {
  const { orgId } = req.params
  const { targetTenant } = req.body

  try {
    // Verify permissions
    const canMigrate = await plinto.organizations.canMigrate({
      organizationId: orgId,
      userId: req.user.id,
      targetTenant
    })

    if (!canMigrate) {
      return res.status(403).json({ error: 'Migration not permitted' })
    }

    // Start migration job
    const migrationJob = await plinto.tenancy.startMigration({
      sourceOrganization: orgId,
      targetTenant,
      includeData: req.body.includeData !== false,
      dryRun: req.body.dryRun === true
    })

    res.json({
      migrationId: migrationJob.id,
      status: 'started',
      estimatedDuration: migrationJob.estimatedDuration
    })
  } catch (error) {
    res.status(400).json({ error: error.message })
  }
})

// Health check with tenant info
app.get('/api/health', async (req, res) => {
  const tenantContext = plinto.tenancy.getContext()

  res.json({
    status: 'healthy',
    tenant: {
      id: tenantContext?.tenantId,
      organization: tenantContext?.organizationId
    },
    timestamp: new Date().toISOString()
  })
})
```

#### Python FastAPI Implementation

```python
from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.security import HTTPBearer
from plinto import Plinto
import os
from typing import Optional

app = FastAPI()
plinto = Plinto(
    api_key=os.getenv("PLINTO_API_KEY"),
    multi_tenant={
        "enabled": True,
        "isolation_mode": "strict",
        "context_sources": ["subdomain", "jwt", "header"]
    }
)
security = HTTPBearer()

async def resolve_tenant_context(request: Request):
    """Resolve tenant context from request"""
    tenant_id = None
    organization_id = None

    # Try subdomain
    if request.url.hostname != "localhost":
        subdomain = request.url.hostname.split(".")[0]
        if subdomain and subdomain != "www":
            org = await plinto.organizations.get_by_slug(subdomain)
            if org:
                tenant_id = org.tenant_id
                organization_id = org.id

    # Try JWT token
    if not tenant_id:
        auth_header = request.headers.get("authorization")
        if auth_header:
            try:
                token = auth_header.split(" ")[1]
                decoded = await plinto.auth.verify_token(token)
                tenant_id = decoded.get("tenant_id") or decoded.get("tid")
                organization_id = decoded.get("organization_id") or decoded.get("oid")
            except:
                pass

    # Try headers
    if not tenant_id:
        tenant_id = request.headers.get("x-tenant-id")
        organization_id = request.headers.get("x-organization-id")

    if not tenant_id:
        raise HTTPException(400, "Tenant context required")

    # Validate and set context
    tenant = await plinto.tenancy.validate_tenant(tenant_id)
    if not tenant.active:
        raise HTTPException(403, "Tenant suspended")

    plinto.tenancy.set_context(
        tenant_id=tenant_id,
        organization_id=organization_id,
        ip_address=request.client.host,
        user_agent=request.headers.get("user-agent")
    )

    return {
        "tenant_id": tenant_id,
        "organization_id": organization_id,
        "organization": tenant.organization
    }

@app.middleware("http")
async def tenant_middleware(request: Request, call_next):
    """Apply tenant context to all requests"""
    # Skip tenant resolution for health checks and admin endpoints
    if request.url.path in ["/health", "/metrics"]:
        response = await call_next(request)
        return response

    try:
        tenant_context = await resolve_tenant_context(request)
        request.state.tenant = tenant_context
        response = await call_next(request)
        return response
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Tenant context resolution failed: {str(e)}")

@app.post("/api/organizations")
async def create_organization(
    name: str,
    slug: str,
    plan: str = "free",
    settings: dict = None,
    request: Request = None
):
    try:
        # Check slug availability
        existing = await plinto.organizations.get_by_slug(slug)
        if existing:
            raise HTTPException(409, "Organization slug already exists")

        # Create organization
        organization = await plinto.organizations.create(
            name=name,
            slug=slug,
            plan=plan,
            settings=settings or {},
            owner=request.state.user.id if hasattr(request.state, 'user') else None
        )

        # Initialize default roles
        await plinto.rbac.initialize_default_roles(organization.id)

        return {
            "organization": organization,
            "message": "Organization created successfully"
        }
    except Exception as e:
        raise HTTPException(400, str(e))

@app.get("/api/organizations/{org_id}")
async def get_organization(
    org_id: str,
    request: Request
):
    try:
        # Verify access
        membership = await plinto.organizations.get_membership(
            organization_id=org_id,
            user_id=request.state.user.id
        )

        if not membership:
            raise HTTPException(403, "Access denied")

        organization = await plinto.organizations.get(org_id)
        stats = await plinto.organizations.get_stats(org_id)

        return {
            "organization": organization,
            "membership": membership,
            "stats": stats,
            "permissions": membership.permissions
        }
    except Exception as e:
        raise HTTPException(400, str(e))

@app.get("/api/users")
async def list_users(
    page: int = 1,
    limit: int = 20,
    search: str = None,
    role: str = None,
    request: Request = None
):
    try:
        # Users automatically filtered by tenant context
        users = await plinto.users.list(
            page=page,
            limit=limit,
            search=search,
            role=role
        )

        return {
            "users": [
                {
                    "id": user.id,
                    "email": user.email,
                    "name": user.name,
                    "role": user.organization_role,
                    "status": user.status,
                    "last_login_at": user.last_login_at,
                    "created_at": user.created_at
                }
                for user in users.data
            ],
            "pagination": {
                "page": users.page,
                "total_pages": users.total_pages,
                "total_items": users.total
            }
        }
    except Exception as e:
        raise HTTPException(400, str(e))
```

### Frontend Implementation

#### React Multi-Tenant Hook

```jsx
import React, { createContext, useContext, useEffect, useState } from 'react'
import { usePlinto } from '@plinto/react-sdk'

const TenantContext = createContext()

export function TenantProvider({ children }) {
  const { organizations } = usePlinto()
  const [currentTenant, setCurrentTenant] = useState(null)
  const [tenants, setTenants] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    loadTenantContext()
  }, [])

  const loadTenantContext = async () => {
    try {
      // Get current tenant from subdomain, JWT, etc.
      const context = await organizations.getCurrentContext()

      if (context.tenant) {
        setCurrentTenant(context.tenant)
      }

      // Load user's available tenants
      const userTenants = await organizations.list()
      setTenants(userTenants)
    } catch (error) {
      console.error('Failed to load tenant context:', error)
    } finally {
      setLoading(false)
    }
  }

  const switchTenant = async (tenantId) => {
    try {
      const tenant = tenants.find(t => t.id === tenantId)
      if (!tenant) throw new Error('Tenant not found')

      // Switch context
      await organizations.switchContext(tenantId)

      // Update URL if using subdomain routing
      if (tenant.slug && window.location.hostname.includes('.')) {
        const newHostname = `${tenant.slug}.${getDomain()}`
        window.location.hostname = newHostname
        return
      }

      setCurrentTenant(tenant)

      // Refresh page to reload with new context
      window.location.reload()
    } catch (error) {
      console.error('Failed to switch tenant:', error)
      throw error
    }
  }

  const createTenant = async (tenantData) => {
    try {
      const newTenant = await organizations.create(tenantData)
      setTenants([...tenants, newTenant])
      return newTenant
    } catch (error) {
      console.error('Failed to create tenant:', error)
      throw error
    }
  }

  const value = {
    currentTenant,
    tenants,
    loading,
    switchTenant,
    createTenant,
    refreshContext: loadTenantContext
  }

  return (
    <TenantContext.Provider value={value}>
      {children}
    </TenantContext.Provider>
  )
}

export function useTenant() {
  const context = useContext(TenantContext)
  if (!context) {
    throw new Error('useTenant must be used within TenantProvider')
  }
  return context
}

// Tenant switcher component
function TenantSwitcher() {
  const { currentTenant, tenants, switchTenant } = useTenant()
  const [switching, setSwitching] = useState(false)

  const handleSwitch = async (tenantId) => {
    if (switching || tenantId === currentTenant?.id) return

    setSwitching(true)
    try {
      await switchTenant(tenantId)
    } catch (error) {
      alert('Failed to switch organization: ' + error.message)
    } finally {
      setSwitching(false)
    }
  }

  return (
    <div className="tenant-switcher">
      <button className="current-tenant">
        <span className="tenant-name">
          {currentTenant?.name || 'Select Organization'}
        </span>
        <span className="tenant-slug">
          {currentTenant?.slug}
        </span>
      </button>

      <div className="tenant-dropdown">
        {tenants.map(tenant => (
          <button
            key={tenant.id}
            onClick={() => handleSwitch(tenant.id)}
            disabled={switching}
            className={`tenant-option ${
              tenant.id === currentTenant?.id ? 'current' : ''
            }`}
          >
            <div className="tenant-info">
              <span className="name">{tenant.name}</span>
              <span className="slug">{tenant.slug}</span>
            </div>
            {tenant.id === currentTenant?.id && (
              <span className="current-indicator">✓</span>
            )}
          </button>
        ))}

        <hr />

        <button className="create-tenant-button">
          + Create New Organization
        </button>
      </div>
    </div>
  )
}

// Organization creation form
function CreateOrganizationModal({ isOpen, onClose, onSuccess }) {
  const { createTenant } = useTenant()
  const [formData, setFormData] = useState({
    name: '',
    slug: '',
    plan: 'free'
  })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const handleSubmit = async (e) => {
    e.preventDefault()
    setLoading(true)
    setError(null)

    try {
      const organization = await createTenant(formData)
      onSuccess(organization)
      onClose()
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const generateSlug = (name) => {
    return name
      .toLowerCase()
      .replace(/[^a-z0-9-]/g, '-')
      .replace(/-+/g, '-')
      .replace(/^-|-$/g, '')
  }

  const handleNameChange = (e) => {
    const name = e.target.value
    setFormData({
      ...formData,
      name,
      slug: formData.slug || generateSlug(name)
    })
  }

  if (!isOpen) return null

  return (
    <div className="modal-overlay">
      <div className="modal">
        <h2>Create Organization</h2>

        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label>Organization Name</label>
            <input
              type="text"
              value={formData.name}
              onChange={handleNameChange}
              placeholder="Acme Corporation"
              required
            />
          </div>

          <div className="form-group">
            <label>Subdomain</label>
            <div className="input-group">
              <input
                type="text"
                value={formData.slug}
                onChange={(e) => setFormData({
                  ...formData,
                  slug: e.target.value
                })}
                placeholder="acme"
                required
              />
              <span className="input-suffix">.yourapp.com</span>
            </div>
          </div>

          <div className="form-group">
            <label>Plan</label>
            <select
              value={formData.plan}
              onChange={(e) => setFormData({
                ...formData,
                plan: e.target.value
              })}
            >
              <option value="free">Free</option>
              <option value="starter">Starter</option>
              <option value="business">Business</option>
              <option value="enterprise">Enterprise</option>
            </select>
          </div>

          {error && (
            <div className="error-message">{error}</div>
          )}

          <div className="form-actions">
            <button
              type="button"
              onClick={onClose}
              className="cancel-button"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={loading}
              className="submit-button"
            >
              {loading ? 'Creating...' : 'Create Organization'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
```

## Advanced Features

### Tenant Isolation Modes

Configure different levels of isolation:

```typescript
// Strict isolation (default)
{
  isolationMode: 'strict',
  // - All queries automatically filtered
  // - Cross-tenant access blocked
  // - Separate schemas/databases per tenant
}

// Relaxed isolation
{
  isolationMode: 'relaxed',
  // - Most queries filtered
  // - Some cross-tenant access allowed with explicit permission
  // - Shared schema with tenant_id columns
}

// Shared tenancy
{
  isolationMode: 'shared',
  // - Manual tenant filtering required
  // - Cross-tenant access allowed
  // - Shared data between tenants
}
```

### Dynamic Tenant Resolution

Implement custom tenant resolution logic:

```typescript
// Custom tenant resolver
plinto.tenancy.addResolver('custom', async (request) => {
  // Custom logic for tenant resolution
  const apiKey = request.headers['x-api-key']

  if (apiKey) {
    const tenant = await lookupTenantByApiKey(apiKey)
    return {
      tenantId: tenant.id,
      organizationId: tenant.organizationId,
      source: 'api_key'
    }
  }

  return null
})

// Priority order for resolvers
plinto.tenancy.setResolverPriority([
  'subdomain',
  'jwt',
  'custom',
  'header',
  'query'
])
```

### Cross-Tenant Data Sharing

Control data sharing between tenants:

```typescript
// Allow specific cross-tenant operations
await plinto.tenancy.withCrossTenantAccess({
  sourceTenant: 'tenant-1',
  targetTenant: 'tenant-2',
  operation: 'read',
  resource: 'templates'
}, async () => {
  // Share templates between tenants
  const sharedTemplates = await plinto.templates.share({
    templateIds: ['tpl-1', 'tpl-2'],
    targetTenant: 'tenant-2',
    permissions: ['read', 'copy']
  })

  return sharedTemplates
})

// Global data accessible to all tenants
await plinto.tenancy.withGlobalContext(async () => {
  // Access global settings, announcements, etc.
  const globalSettings = await plinto.settings.getGlobal()
  return globalSettings
})
```

### Tenant-Specific Configuration

Customize behavior per tenant:

```typescript
// Per-tenant configuration
await plinto.tenancy.configure(tenantId, {
  features: {
    sso: true,
    auditLogs: true,
    advancedRbac: true,
    apiRateLimit: 10000 // requests per hour
  },
  limits: {
    maxUsers: 500,
    maxProjects: 100,
    storageQuota: '50GB'
  },
  integrations: {
    slack: { enabled: true, webhook: 'https://...' },
    email: { provider: 'sendgrid', key: '...' }
  },
  branding: {
    logo: 'https://cdn.example.com/logo.png',
    colors: {
      primary: '#007bff',
      secondary: '#6c757d'
    },
    customDomain: 'portal.acme.com'
  }
})

// Get tenant configuration
const config = await plinto.tenancy.getConfiguration(tenantId)
console.log('Max users:', config.limits.maxUsers)
```

## Security Considerations

### 1. Data Isolation

```typescript
// Database-level isolation
{
  database: {
    isolationMethod: 'row_level_security', // or 'separate_schemas'

    // Row-level security policies
    policies: {
      users: 'tenant_id = current_setting("app.tenant_id")',
      projects: 'tenant_id = current_setting("app.tenant_id")',
      documents: 'tenant_id = current_setting("app.tenant_id")'
    }
  }
}

// Application-level checks
const enforceDataIsolation = async (query, tenantId) => {
  // Verify all accessed resources belong to tenant
  const resourceIds = extractResourceIds(query)

  for (const resourceId of resourceIds) {
    const resource = await getResource(resourceId)
    if (resource.tenantId !== tenantId) {
      throw new SecurityError('Cross-tenant access denied')
    }
  }
}
```

### 2. Context Validation

```typescript
// Validate tenant context integrity
const validateContext = async (context) => {
  // Verify tenant is active
  const tenant = await plinto.tenancy.getTenant(context.tenantId)
  if (!tenant || !tenant.active) {
    throw new Error('Invalid or inactive tenant')
  }

  // Verify user belongs to tenant
  if (context.userId) {
    const membership = await plinto.organizations.getMembership({
      userId: context.userId,
      organizationId: context.organizationId
    })

    if (!membership || !membership.active) {
      throw new Error('User not authorized for this tenant')
    }
  }

  // Verify IP restrictions if configured
  if (tenant.ipRestrictions?.length > 0) {
    const allowed = tenant.ipRestrictions.some(range =>
      ipInRange(context.ipAddress, range)
    )

    if (!allowed) {
      throw new Error('IP address not allowed for this tenant')
    }
  }

  return true
}
```

### 3. Audit Logging

```typescript
// Log all tenant context changes
plinto.tenancy.on('contextSet', async (context, previousContext) => {
  await plinto.audit.log({
    event: 'tenant.context_set',
    tenantId: context.tenantId,
    userId: context.userId,
    previousTenant: previousContext?.tenantId,
    ipAddress: context.ipAddress,
    userAgent: context.userAgent
  })
})

// Log cross-tenant access
plinto.tenancy.on('crossTenantAccess', async (operation) => {
  await plinto.audit.log({
    event: 'tenant.cross_tenant_access',
    sourceTenant: operation.sourceTenant,
    targetTenant: operation.targetTenant,
    operation: operation.type,
    resource: operation.resource,
    authorized: operation.authorized
  })
})
```

## Testing

### Unit Tests

```typescript
describe('Multi-Tenant Operations', () => {
  beforeEach(async () => {
    // Set up test tenants
    await plinto.tenancy.setContext({
      tenantId: 'tenant-test-1',
      organizationId: 'org-1'
    })
  })

  it('should isolate data by tenant', async () => {
    // Create data in tenant 1
    const user1 = await plinto.users.create({
      email: 'user@tenant1.com',
      tenantId: 'tenant-test-1'
    })

    // Switch to tenant 2
    await plinto.tenancy.setContext({
      tenantId: 'tenant-test-2',
      organizationId: 'org-2'
    })

    // Should not see tenant 1 data
    const users = await plinto.users.list()
    expect(users.data).not.toContainEqual(
      expect.objectContaining({ id: user1.id })
    )
  })

  it('should resolve tenant context correctly', async () => {
    const mockRequest = {
      hostname: 'acme.example.com',
      headers: {}
    }

    const context = await plinto.tenancy.resolveContext(mockRequest)

    expect(context.tenantId).toBeDefined()
    expect(context.organizationId).toBeDefined()
    expect(context.source).toBe('subdomain')
  })

  it('should enforce tenant limits', async () => {
    // Set tenant limit
    await plinto.tenancy.configure('tenant-test-1', {
      limits: { maxUsers: 2 }
    })

    // Create up to limit
    await plinto.users.create({ email: 'user1@test.com' })
    await plinto.users.create({ email: 'user2@test.com' })

    // Should fail on limit exceeded
    await expect(
      plinto.users.create({ email: 'user3@test.com' })
    ).rejects.toThrow('Tenant user limit exceeded')
  })
})
```

### Integration Tests

```typescript
describe('Multi-Tenant Integration', () => {
  it('should handle complete organization lifecycle', async () => {
    // 1. Create organization
    const org = await plinto.organizations.create({
      name: 'Test Organization',
      slug: 'test-org',
      plan: 'business'
    })

    expect(org.tenantId).toBeDefined()
    expect(org.slug).toBe('test-org')

    // 2. Set tenant context
    await plinto.tenancy.setContext({
      tenantId: org.tenantId,
      organizationId: org.id
    })

    // 3. Create tenant-scoped data
    const project = await plinto.projects.create({
      name: 'Test Project'
    })

    expect(project.tenantId).toBe(org.tenantId)

    // 4. Verify isolation
    await plinto.tenancy.setContext({
      tenantId: 'different-tenant',
      organizationId: 'different-org'
    })

    const projects = await plinto.projects.list()
    expect(projects.data).toHaveLength(0)

    // 5. Clean up
    await plinto.tenancy.withSystemContext(async () => {
      await plinto.organizations.delete(org.id)
    })
  })
})
```

## Migration Guide

### Single to Multi-Tenant

```typescript
// Migration strategy
const migrateToMultiTenant = async () => {
  console.log('Starting multi-tenant migration...')

  // 1. Create default organization for existing data
  const defaultOrg = await plinto.organizations.create({
    name: 'Default Organization',
    slug: 'default',
    plan: 'enterprise',
    isDefault: true
  })

  // 2. Assign all existing users to default organization
  const existingUsers = await plinto.tenancy.withSystemContext(() =>
    plinto.users.list({ includeAll: true })
  )

  for (const user of existingUsers.data) {
    await plinto.organizations.addMember({
      organizationId: defaultOrg.id,
      userId: user.id,
      role: 'member',
      skipInvitation: true
    })

    // Update user record with tenant ID
    await plinto.users.update(user.id, {
      tenantId: defaultOrg.tenantId
    })
  }

  // 3. Update all existing data with tenant ID
  await migrateDataToTenant(defaultOrg.tenantId)

  // 4. Enable multi-tenant mode
  await plinto.configure({
    multiTenant: {
      enabled: true,
      isolationMode: 'strict'
    }
  })

  console.log('Multi-tenant migration completed')
}

const migrateDataToTenant = async (tenantId) => {
  const tables = ['projects', 'documents', 'teams', 'integrations']

  for (const table of tables) {
    const count = await plinto.database.raw(`
      UPDATE ${table}
      SET tenant_id = ?
      WHERE tenant_id IS NULL
    `, [tenantId])

    console.log(`Updated ${count.affectedRows} records in ${table}`)
  }
}
```

### From Other Platforms

```typescript
// Migrate from single-tenant platforms
const migratePlatformData = async (platformData) => {
  for (const orgData of platformData.organizations) {
    // Create organization in Plinto
    const org = await plinto.organizations.create({
      name: orgData.name,
      slug: orgData.slug,
      plan: orgData.subscription?.plan || 'free',
      settings: orgData.settings
    })

    // Set tenant context for migration
    await plinto.tenancy.setContext({
      tenantId: org.tenantId,
      organizationId: org.id
    })

    // Migrate users
    for (const userData of orgData.users) {
      const user = await plinto.users.create({
        email: userData.email,
        name: userData.name,
        externalId: userData.platformId
      })

      await plinto.organizations.addMember({
        organizationId: org.id,
        userId: user.id,
        role: userData.role
      })
    }

    // Migrate data
    for (const projectData of orgData.projects) {
      await plinto.projects.create({
        name: projectData.name,
        description: projectData.description,
        externalId: projectData.platformId
      })
    }

    console.log(`Migrated organization: ${org.name}`)
  }
}
```

## API Reference

### `organizations.create(options)`

Create new organization with tenant.

**Parameters:**
- `name` (string, required): Organization name
- `slug` (string, required): Unique subdomain slug
- `plan` (string): Subscription plan
- `settings` (object): Organization settings
- `owner` (string): Owner user ID

**Returns:**
- `organization` (object): Organization details
- `tenantId` (string): Generated tenant ID

### `tenancy.setContext(options)`

Set tenant context for current request.

**Parameters:**
- `tenantId` (string, required): Tenant identifier
- `organizationId` (string): Organization ID
- `userId` (string): Current user ID
- `ipAddress` (string): Client IP address

**Returns:**
- `context` (object): Set context details

### `tenancy.resolveContext(request, options)`

Resolve tenant context from request.

**Parameters:**
- `request` (object, required): HTTP request object
- `sources` (array): Context sources to try
- `required` (boolean): Whether context is required

**Returns:**
- `tenantId` (string): Resolved tenant ID
- `organizationId` (string): Organization ID
- `source` (string): Resolution source

### `tenancy.withSystemContext(callback)`

Execute callback with system-wide access.

**Parameters:**
- `callback` (function, required): Function to execute

**Returns:**
- Result of callback function

## Related Guides

- [RBAC Implementation](/guides/organizations/rbac)
- [SCIM 2.0 Integration](/guides/organizations/scim)
- [Security Best Practices](/guides/security/best-practices)
- [Audit Logging](/guides/security/audit-logging)