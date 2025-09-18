# Role-Based Access Control (RBAC)

Implement fine-grained permissions with hierarchical roles, custom permissions, and enterprise-grade access control.

## Overview

Plinto's RBAC system provides flexible, scalable access control with hierarchical roles, custom permissions, and resource-level restrictions. The system supports both predefined roles and dynamic custom roles that can inherit from parent roles.

## Core Concepts

### Permissions Format

Permissions follow the pattern: `resource:action[:scope]`

- `user:read` - Read user data
- `project:*` - All actions on projects
- `user:delete:own` - Delete own user data only
- `*:admin` - Admin access to all resources
- `billing:read:organization` - Read organization billing info

### Role Hierarchy

Roles can inherit permissions from parent roles:

```
Owner (all permissions)
  ├── Admin (administrative permissions)
  │     └── Manager (team management)
  │           └── Member (standard permissions)
  └── Viewer (read-only access)
```

### Resource Types

Standard resource types in Plinto:

- `user` - User management
- `organization` - Organization settings
- `project` - Project management
- `role` - Role and permission management
- `billing` - Billing and subscription
- `audit` - Audit log access
- `integration` - Third-party integrations

## Quick Start

### 1. Check User Permissions

```typescript
import { plinto } from '@plinto/typescript-sdk'

// Check if user can perform action
const canDeleteUser = await plinto.rbac.checkPermission({
  userId: currentUser.id,
  resource: 'user',
  action: 'delete',
  resourceId: targetUserId // Optional: for resource-specific checks
})

if (canDeleteUser) {
  // User has permission to delete
  await deleteUser(targetUserId)
} else {
  throw new Error('Permission denied')
}
```

### 2. Use Permission Decorators

```typescript
// Protect route with permission check
@plinto.rbac.requirePermission('project', 'create')
async function createProject(projectData) {
  return await plinto.projects.create(projectData)
}

// Protect with multiple permissions (OR logic)
@plinto.rbac.requireAnyPermission(['user:delete', 'user:suspend'])
async function removeUser(userId) {
  return await plinto.users.delete(userId)
}

// Protect with role requirement
@plinto.rbac.requireRole(['admin', 'manager'])
async function getAnalytics() {
  return await plinto.analytics.getReports()
}
```

### 3. Create Custom Role

```typescript
// Create custom role with specific permissions
const role = await plinto.rbac.createRole({
  organizationId: currentOrg.id,
  name: 'Project Manager',
  description: 'Manages projects and team members',
  permissions: [
    'project:*',           // All project actions
    'user:read',          // Read user data
    'user:invite',        // Invite new users
    'report:read',        // Read reports
    'team:manage:assigned' // Manage assigned teams only
  ],
  parentRoleId: 'role_member' // Inherit from Member role
})

// Assign role to user
await plinto.rbac.assignRole({
  userId: targetUser.id,
  roleId: role.id,
  organizationId: currentOrg.id
})
```

### 4. Permission-Based UI

```jsx
import { usePermissions } from '@plinto/react-sdk'

function ProjectActions({ project }) {
  const { hasPermission } = usePermissions()

  return (
    <div className="project-actions">
      {hasPermission('project:edit', project.id) && (
        <button onClick={() => editProject(project)}>
          Edit Project
        </button>
      )}

      {hasPermission('project:delete', project.id) && (
        <button onClick={() => deleteProject(project)}>
          Delete Project
        </button>
      )}

      {hasPermission('project:share') && (
        <button onClick={() => shareProject(project)}>
          Share Project
        </button>
      )}
    </div>
  )
}
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
  rbac: {
    defaultRoles: ['owner', 'admin', 'member', 'viewer'],
    permissionFormat: 'resource:action:scope',
    hierarchyEnabled: true,
    cachePermissions: true,
    cacheTimeout: 5 * 60 * 1000 // 5 minutes
  }
})

// Permission checking middleware
const requirePermission = (resource, action, scope = null) => {
  return async (req, res, next) => {
    try {
      const { userId, organizationId } = req.session

      if (!userId) {
        return res.status(401).json({ error: 'Authentication required' })
      }

      const hasPermission = await plinto.rbac.checkPermission({
        userId,
        organizationId,
        resource,
        action,
        scope,
        resourceId: req.params.resourceId // For resource-specific checks
      })

      if (!hasPermission) {
        // Log permission denial for audit
        await plinto.audit.log({
          event: 'permission.denied',
          userId,
          organizationId,
          resource,
          action,
          scope,
          ipAddress: req.ip
        })

        return res.status(403).json({
          error: 'Permission denied',
          required: `${resource}:${action}${scope ? ':' + scope : ''}`
        })
      }

      next()
    } catch (error) {
      res.status(500).json({ error: 'Permission check failed' })
    }
  }
}

// Role management endpoints
app.get('/api/roles', requirePermission('role', 'read'), async (req, res) => {
  try {
    const { organizationId } = req.session

    const roles = await plinto.rbac.getRoles({
      organizationId,
      includePermissions: true,
      includeHierarchy: true
    })

    const formattedRoles = roles.map(role => ({
      id: role.id,
      name: role.name,
      description: role.description,
      permissions: role.permissions,
      parentRole: role.parentRole,
      isCustom: role.isCustom,
      memberCount: role.memberCount,
      createdAt: role.createdAt
    }))

    res.json({ roles: formattedRoles })
  } catch (error) {
    res.status(400).json({ error: error.message })
  }
})

app.post('/api/roles', requirePermission('role', 'create'), async (req, res) => {
  try {
    const { name, description, permissions, parentRoleId } = req.body
    const { organizationId, userId } = req.session

    // Validate permissions format
    for (const permission of permissions) {
      if (!isValidPermissionFormat(permission)) {
        return res.status(400).json({
          error: `Invalid permission format: ${permission}`,
          expected: 'resource:action[:scope]'
        })
      }
    }

    // Check if user has all permissions they're trying to grant
    const userPermissions = await plinto.rbac.getUserPermissions({
      userId,
      organizationId
    })

    const unauthorizedPerms = permissions.filter(perm =>
      !hasPermissionToGrant(userPermissions, perm)
    )

    if (unauthorizedPerms.length > 0) {
      return res.status(403).json({
        error: 'Cannot grant permissions you do not have',
        unauthorized: unauthorizedPerms
      })
    }

    const role = await plinto.rbac.createRole({
      organizationId,
      name,
      description,
      permissions,
      parentRoleId,
      createdBy: userId
    })

    // Log role creation
    await plinto.audit.log({
      event: 'role.created',
      userId,
      organizationId,
      roleId: role.id,
      roleName: role.name,
      permissions: role.permissions
    })

    res.json({ role })
  } catch (error) {
    if (error.code === 'role_exists') {
      res.status(409).json({ error: 'Role with this name already exists' })
    } else {
      res.status(400).json({ error: error.message })
    }
  }
})

app.put('/api/roles/:roleId', requirePermission('role', 'update'), async (req, res) => {
  try {
    const { roleId } = req.params
    const { name, description, permissions } = req.body
    const { organizationId, userId } = req.session

    // Verify role belongs to organization
    const existingRole = await plinto.rbac.getRole(roleId, organizationId)
    if (!existingRole) {
      return res.status(404).json({ error: 'Role not found' })
    }

    // Cannot modify system roles
    if (!existingRole.isCustom) {
      return res.status(403).json({ error: 'Cannot modify system roles' })
    }

    // Validate new permissions
    if (permissions) {
      const userPermissions = await plinto.rbac.getUserPermissions({
        userId,
        organizationId
      })

      const unauthorizedPerms = permissions.filter(perm =>
        !hasPermissionToGrant(userPermissions, perm)
      )

      if (unauthorizedPerms.length > 0) {
        return res.status(403).json({
          error: 'Cannot grant permissions you do not have',
          unauthorized: unauthorizedPerms
        })
      }
    }

    const updatedRole = await plinto.rbac.updateRole(roleId, {
      name,
      description,
      permissions,
      updatedBy: userId
    })

    // Log role update
    await plinto.audit.log({
      event: 'role.updated',
      userId,
      organizationId,
      roleId,
      changes: {
        name: { from: existingRole.name, to: name },
        permissions: { from: existingRole.permissions, to: permissions }
      }
    })

    res.json({ role: updatedRole })
  } catch (error) {
    res.status(400).json({ error: error.message })
  }
})

app.delete('/api/roles/:roleId', requirePermission('role', 'delete'), async (req, res) => {
  try {
    const { roleId } = req.params
    const { reassignToRoleId } = req.body
    const { organizationId, userId } = req.session

    const role = await plinto.rbac.getRole(roleId, organizationId)
    if (!role) {
      return res.status(404).json({ error: 'Role not found' })
    }

    if (!role.isCustom) {
      return res.status(403).json({ error: 'Cannot delete system roles' })
    }

    // Check if role has members
    const memberCount = await plinto.rbac.getRoleMemberCount(roleId)
    if (memberCount > 0 && !reassignToRoleId) {
      return res.status(409).json({
        error: 'Role has members',
        memberCount,
        suggestion: 'Provide reassignToRoleId to reassign members'
      })
    }

    const result = await plinto.rbac.deleteRole({
      roleId,
      organizationId,
      reassignToRoleId,
      deletedBy: userId
    })

    // Log role deletion
    await plinto.audit.log({
      event: 'role.deleted',
      userId,
      organizationId,
      roleId,
      roleName: role.name,
      membersReassigned: result.membersReassigned,
      reassignToRoleId
    })

    res.json({
      success: true,
      membersReassigned: result.membersReassigned
    })
  } catch (error) {
    res.status(400).json({ error: error.message })
  }
})

// User role assignment
app.put('/api/users/:userId/role', requirePermission('user', 'update'), async (req, res) => {
  try {
    const { userId: targetUserId } = req.params
    const { roleId } = req.body
    const { organizationId, userId } = req.session

    // Verify target user is in organization
    const membership = await plinto.organizations.getMembership({
      userId: targetUserId,
      organizationId
    })

    if (!membership) {
      return res.status(404).json({ error: 'User not found in organization' })
    }

    // Verify role exists and is valid
    const role = await plinto.rbac.getRole(roleId, organizationId)
    if (!role) {
      return res.status(404).json({ error: 'Role not found' })
    }

    // Check if user can assign this role
    const canAssignRole = await plinto.rbac.canAssignRole({
      assignerId: userId,
      roleId,
      targetUserId,
      organizationId
    })

    if (!canAssignRole) {
      return res.status(403).json({
        error: 'Cannot assign role with higher or equal privileges'
      })
    }

    const previousRole = membership.role

    // Assign new role
    await plinto.rbac.assignRole({
      userId: targetUserId,
      roleId,
      organizationId,
      assignedBy: userId
    })

    // Log role assignment
    await plinto.audit.log({
      event: 'role.assigned',
      userId,
      organizationId,
      targetUserId,
      roleId,
      roleName: role.name,
      previousRoleId: previousRole.id,
      previousRoleName: previousRole.name
    })

    res.json({
      success: true,
      message: `Role updated to ${role.name}`
    })
  } catch (error) {
    res.status(400).json({ error: error.message })
  }
})

// Get user permissions
app.get('/api/users/:userId/permissions', requirePermission('user', 'read'), async (req, res) => {
  try {
    const { userId: targetUserId } = req.params
    const { organizationId } = req.session

    const permissions = await plinto.rbac.getUserPermissions({
      userId: targetUserId,
      organizationId,
      includeInherited: true,
      includeScoped: true
    })

    res.json({
      userId: targetUserId,
      permissions: permissions.all,
      directPermissions: permissions.direct,
      inheritedPermissions: permissions.inherited,
      scopedPermissions: permissions.scoped,
      roles: permissions.roles
    })
  } catch (error) {
    res.status(400).json({ error: error.message })
  }
})

// Permission testing endpoint
app.post('/api/permissions/check', async (req, res) => {
  try {
    const { resource, action, scope, resourceId } = req.body
    const { userId, organizationId } = req.session

    const hasPermission = await plinto.rbac.checkPermission({
      userId,
      organizationId,
      resource,
      action,
      scope,
      resourceId
    })

    res.json({
      hasPermission,
      permission: `${resource}:${action}${scope ? ':' + scope : ''}`,
      userId,
      organizationId
    })
  } catch (error) {
    res.status(400).json({ error: error.message })
  }
})

// Bulk permission check
app.post('/api/permissions/check-bulk', async (req, res) => {
  try {
    const { permissions } = req.body // Array of permission objects
    const { userId, organizationId } = req.session

    const results = await Promise.all(
      permissions.map(async (perm) => {
        const hasPermission = await plinto.rbac.checkPermission({
          userId,
          organizationId,
          resource: perm.resource,
          action: perm.action,
          scope: perm.scope,
          resourceId: perm.resourceId
        })

        return {
          permission: `${perm.resource}:${perm.action}${perm.scope ? ':' + perm.scope : ''}`,
          hasPermission,
          resourceId: perm.resourceId
        }
      })
    )

    res.json({ results })
  } catch (error) {
    res.status(400).json({ error: error.message })
  }
})

// Helper function to validate permission format
function isValidPermissionFormat(permission) {
  const permissionRegex = /^[a-zA-Z_][a-zA-Z0-9_]*:[a-zA-Z_*][a-zA-Z0-9_*]*(?::[a-zA-Z_][a-zA-Z0-9_]*)?$/
  return permissionRegex.test(permission)
}

// Helper function to check if user can grant a permission
function hasPermissionToGrant(userPermissions, permissionToGrant) {
  // System admins can grant any permission
  if (userPermissions.includes('*:*')) return true

  // Direct permission match
  if (userPermissions.includes(permissionToGrant)) return true

  // Check wildcard permissions
  const [resource, action, scope] = permissionToGrant.split(':')

  // Check resource-level wildcards
  if (userPermissions.includes(`${resource}:*`)) return true

  // Check action-level wildcards
  if (userPermissions.includes(`*:${action}`)) return true

  return false
}
```

#### Python FastAPI Implementation

```python
from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.security import HTTPBearer
from plinto import Plinto
from functools import wraps
import os

app = FastAPI()
plinto = Plinto(
    api_key=os.getenv("PLINTO_API_KEY"),
    rbac={
        "default_roles": ["owner", "admin", "member", "viewer"],
        "permission_format": "resource:action:scope",
        "hierarchy_enabled": True,
        "cache_permissions": True
    }
)
security = HTTPBearer()

def require_permission(resource: str, action: str, scope: str = None):
    """Decorator for permission-based access control"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Get request and session from kwargs or dependency injection
            request = kwargs.get('request') or args[0] if args else None

            if not request or not hasattr(request.state, 'user'):
                raise HTTPException(401, "Authentication required")

            user_id = request.state.user.id
            organization_id = request.state.tenant.organization_id
            resource_id = kwargs.get('resource_id')

            has_permission = await plinto.rbac.check_permission(
                user_id=user_id,
                organization_id=organization_id,
                resource=resource,
                action=action,
                scope=scope,
                resource_id=resource_id
            )

            if not has_permission:
                # Log permission denial
                await plinto.audit.log(
                    event="permission.denied",
                    user_id=user_id,
                    organization_id=organization_id,
                    resource=resource,
                    action=action,
                    scope=scope,
                    ip_address=request.client.host
                )

                required_perm = f"{resource}:{action}"
                if scope:
                    required_perm += f":{scope}"

                raise HTTPException(
                    403,
                    f"Permission denied. Required: {required_perm}"
                )

            return await func(*args, **kwargs)
        return wrapper
    return decorator

@app.get("/api/roles")
@require_permission("role", "read")
async def get_roles(request: Request):
    try:
        organization_id = request.state.tenant.organization_id

        roles = await plinto.rbac.get_roles(
            organization_id=organization_id,
            include_permissions=True,
            include_hierarchy=True
        )

        formatted_roles = []
        for role in roles:
            formatted_roles.append({
                "id": role.id,
                "name": role.name,
                "description": role.description,
                "permissions": role.permissions,
                "parent_role": role.parent_role,
                "is_custom": role.is_custom,
                "member_count": role.member_count,
                "created_at": role.created_at
            })

        return {"roles": formatted_roles}
    except Exception as e:
        raise HTTPException(400, str(e))

@app.post("/api/roles")
@require_permission("role", "create")
async def create_role(
    name: str,
    description: str,
    permissions: list,
    parent_role_id: str = None,
    request: Request = None
):
    try:
        user_id = request.state.user.id
        organization_id = request.state.tenant.organization_id

        # Validate permissions format
        for permission in permissions:
            if not is_valid_permission_format(permission):
                raise HTTPException(
                    400,
                    f"Invalid permission format: {permission}"
                )

        # Check if user has all permissions they're trying to grant
        user_permissions = await plinto.rbac.get_user_permissions(
            user_id=user_id,
            organization_id=organization_id
        )

        unauthorized_perms = [
            perm for perm in permissions
            if not has_permission_to_grant(user_permissions.all, perm)
        ]

        if unauthorized_perms:
            raise HTTPException(
                403,
                f"Cannot grant permissions you do not have: {unauthorized_perms}"
            )

        role = await plinto.rbac.create_role(
            organization_id=organization_id,
            name=name,
            description=description,
            permissions=permissions,
            parent_role_id=parent_role_id,
            created_by=user_id
        )

        # Log role creation
        await plinto.audit.log(
            event="role.created",
            user_id=user_id,
            organization_id=organization_id,
            role_id=role.id,
            role_name=role.name,
            permissions=role.permissions
        )

        return {"role": role}
    except Exception as e:
        if "role_exists" in str(e):
            raise HTTPException(409, "Role with this name already exists")
        raise HTTPException(400, str(e))

@app.put("/api/roles/{role_id}")
@require_permission("role", "update")
async def update_role(
    role_id: str,
    name: str = None,
    description: str = None,
    permissions: list = None,
    request: Request = None
):
    try:
        user_id = request.state.user.id
        organization_id = request.state.tenant.organization_id

        # Verify role belongs to organization
        existing_role = await plinto.rbac.get_role(role_id, organization_id)
        if not existing_role:
            raise HTTPException(404, "Role not found")

        if not existing_role.is_custom:
            raise HTTPException(403, "Cannot modify system roles")

        # Validate new permissions if provided
        if permissions:
            user_permissions = await plinto.rbac.get_user_permissions(
                user_id=user_id,
                organization_id=organization_id
            )

            unauthorized_perms = [
                perm for perm in permissions
                if not has_permission_to_grant(user_permissions.all, perm)
            ]

            if unauthorized_perms:
                raise HTTPException(
                    403,
                    f"Cannot grant permissions you do not have: {unauthorized_perms}"
                )

        updated_role = await plinto.rbac.update_role(
            role_id=role_id,
            name=name,
            description=description,
            permissions=permissions,
            updated_by=user_id
        )

        # Log role update
        await plinto.audit.log(
            event="role.updated",
            user_id=user_id,
            organization_id=organization_id,
            role_id=role_id,
            changes={
                "name": {"from": existing_role.name, "to": name},
                "permissions": {"from": existing_role.permissions, "to": permissions}
            }
        )

        return {"role": updated_role}
    except Exception as e:
        raise HTTPException(400, str(e))

@app.delete("/api/roles/{role_id}")
@require_permission("role", "delete")
async def delete_role(
    role_id: str,
    reassign_to_role_id: str = None,
    request: Request = None
):
    try:
        user_id = request.state.user.id
        organization_id = request.state.tenant.organization_id

        role = await plinto.rbac.get_role(role_id, organization_id)
        if not role:
            raise HTTPException(404, "Role not found")

        if not role.is_custom:
            raise HTTPException(403, "Cannot delete system roles")

        # Check if role has members
        member_count = await plinto.rbac.get_role_member_count(role_id)
        if member_count > 0 and not reassign_to_role_id:
            raise HTTPException(
                409,
                f"Role has {member_count} members. Provide reassign_to_role_id."
            )

        result = await plinto.rbac.delete_role(
            role_id=role_id,
            organization_id=organization_id,
            reassign_to_role_id=reassign_to_role_id,
            deleted_by=user_id
        )

        # Log role deletion
        await plinto.audit.log(
            event="role.deleted",
            user_id=user_id,
            organization_id=organization_id,
            role_id=role_id,
            role_name=role.name,
            members_reassigned=result.members_reassigned
        )

        return {
            "success": True,
            "members_reassigned": result.members_reassigned
        }
    except Exception as e:
        raise HTTPException(400, str(e))

@app.put("/api/users/{user_id}/role")
@require_permission("user", "update")
async def assign_user_role(
    user_id: str,
    role_id: str,
    request: Request
):
    try:
        assigner_id = request.state.user.id
        organization_id = request.state.tenant.organization_id

        # Verify target user is in organization
        membership = await plinto.organizations.get_membership(
            user_id=user_id,
            organization_id=organization_id
        )

        if not membership:
            raise HTTPException(404, "User not found in organization")

        # Verify role exists
        role = await plinto.rbac.get_role(role_id, organization_id)
        if not role:
            raise HTTPException(404, "Role not found")

        # Check if user can assign this role
        can_assign = await plinto.rbac.can_assign_role(
            assigner_id=assigner_id,
            role_id=role_id,
            target_user_id=user_id,
            organization_id=organization_id
        )

        if not can_assign:
            raise HTTPException(
                403,
                "Cannot assign role with higher or equal privileges"
            )

        previous_role = membership.role

        # Assign new role
        await plinto.rbac.assign_role(
            user_id=user_id,
            role_id=role_id,
            organization_id=organization_id,
            assigned_by=assigner_id
        )

        # Log role assignment
        await plinto.audit.log(
            event="role.assigned",
            user_id=assigner_id,
            organization_id=organization_id,
            target_user_id=user_id,
            role_id=role_id,
            role_name=role.name,
            previous_role_id=previous_role.id,
            previous_role_name=previous_role.name
        )

        return {
            "success": True,
            "message": f"Role updated to {role.name}"
        }
    except Exception as e:
        raise HTTPException(400, str(e))

def is_valid_permission_format(permission: str) -> bool:
    """Validate permission format: resource:action[:scope]"""
    import re
    pattern = r'^[a-zA-Z_][a-zA-Z0-9_]*:[a-zA-Z_*][a-zA-Z0-9_*]*(?::[a-zA-Z_][a-zA-Z0-9_]*)?$'
    return bool(re.match(pattern, permission))

def has_permission_to_grant(user_permissions: list, permission_to_grant: str) -> bool:
    """Check if user can grant a specific permission"""
    # System admins can grant any permission
    if "*:*" in user_permissions:
        return True

    # Direct permission match
    if permission_to_grant in user_permissions:
        return True

    # Check wildcard permissions
    resource, action, *scope = permission_to_grant.split(':')

    # Check resource-level wildcards
    if f"{resource}:*" in user_permissions:
        return True

    # Check action-level wildcards
    if f"*:{action}" in user_permissions:
        return True

    return False
```

### Frontend Implementation

#### React RBAC Hook

```jsx
import React, { createContext, useContext, useEffect, useState } from 'react'
import { usePlinto } from '@plinto/react-sdk'

const PermissionsContext = createContext()

export function PermissionsProvider({ children }) {
  const { rbac, auth } = usePlinto()
  const [permissions, setPermissions] = useState([])
  const [roles, setRoles] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (auth.user) {
      loadUserPermissions()
    }
  }, [auth.user])

  const loadUserPermissions = async () => {
    try {
      const userPermissions = await rbac.getUserPermissions({
        userId: auth.user.id,
        includeInherited: true,
        includeScoped: true
      })

      setPermissions(userPermissions.all)
      setRoles(userPermissions.roles)
    } catch (error) {
      console.error('Failed to load permissions:', error)
    } finally {
      setLoading(false)
    }
  }

  const hasPermission = (resource, action, scope = null, resourceId = null) => {
    if (loading) return false

    const permission = `${resource}:${action}${scope ? ':' + scope : ''}`

    // Check direct permission
    if (permissions.includes(permission)) return true

    // Check wildcard permissions
    if (permissions.includes(`${resource}:*`)) return true
    if (permissions.includes(`*:${action}`)) return true
    if (permissions.includes('*:*')) return true

    // Resource-specific permissions would need server-side check
    if (resourceId) {
      // This would typically be cached or checked on component mount
      return checkResourcePermission(resource, action, resourceId)
    }

    return false
  }

  const hasRole = (roleNames) => {
    if (!Array.isArray(roleNames)) {
      roleNames = [roleNames]
    }

    return roles.some(role => roleNames.includes(role.name))
  }

  const hasAnyPermission = (permissionList) => {
    return permissionList.some(perm => {
      const [resource, action, scope] = perm.split(':')
      return hasPermission(resource, action, scope)
    })
  }

  const hasAllPermissions = (permissionList) => {
    return permissionList.every(perm => {
      const [resource, action, scope] = perm.split(':')
      return hasPermission(resource, action, scope)
    })
  }

  const checkResourcePermission = async (resource, action, resourceId) => {
    try {
      const result = await rbac.checkPermission({
        resource,
        action,
        resourceId
      })
      return result.hasPermission
    } catch (error) {
      console.error('Resource permission check failed:', error)
      return false
    }
  }

  const value = {
    permissions,
    roles,
    loading,
    hasPermission,
    hasRole,
    hasAnyPermission,
    hasAllPermissions,
    checkResourcePermission,
    refreshPermissions: loadUserPermissions
  }

  return (
    <PermissionsContext.Provider value={value}>
      {children}
    </PermissionsContext.Provider>
  )
}

export function usePermissions() {
  const context = useContext(PermissionsContext)
  if (!context) {
    throw new Error('usePermissions must be used within PermissionsProvider')
  }
  return context
}

// Permission-based components
export function PermissionGate({
  resource,
  action,
  scope,
  resourceId,
  fallback = null,
  children
}) {
  const { hasPermission, loading } = usePermissions()

  if (loading) {
    return <div>Loading permissions...</div>
  }

  if (!hasPermission(resource, action, scope, resourceId)) {
    return fallback
  }

  return children
}

export function RoleGate({ roles, fallback = null, children }) {
  const { hasRole, loading } = usePermissions()

  if (loading) {
    return <div>Loading roles...</div>
  }

  if (!hasRole(roles)) {
    return fallback
  }

  return children
}

// Role management component
function RoleManager() {
  const { rbac } = usePlinto()
  const { hasPermission } = usePermissions()
  const [roles, setRoles] = useState([])
  const [loading, setLoading] = useState(true)
  const [editingRole, setEditingRole] = useState(null)

  useEffect(() => {
    loadRoles()
  }, [])

  const loadRoles = async () => {
    try {
      const { roles } = await rbac.getRoles({
        includePermissions: true,
        includeHierarchy: true
      })
      setRoles(roles)
    } catch (error) {
      console.error('Failed to load roles:', error)
    } finally {
      setLoading(false)
    }
  }

  const createRole = async (roleData) => {
    try {
      const { role } = await rbac.createRole(roleData)
      setRoles([...roles, role])
      return role
    } catch (error) {
      throw new Error(`Failed to create role: ${error.message}`)
    }
  }

  const updateRole = async (roleId, updates) => {
    try {
      const { role } = await rbac.updateRole(roleId, updates)
      setRoles(roles.map(r => r.id === roleId ? role : r))
      return role
    } catch (error) {
      throw new Error(`Failed to update role: ${error.message}`)
    }
  }

  const deleteRole = async (roleId, reassignToRoleId = null) => {
    try {
      await rbac.deleteRole({ roleId, reassignToRoleId })
      setRoles(roles.filter(r => r.id !== roleId))
    } catch (error) {
      throw new Error(`Failed to delete role: ${error.message}`)
    }
  }

  if (loading) return <div>Loading roles...</div>

  return (
    <div className="role-manager">
      <div className="role-header">
        <h2>Role Management</h2>
        <PermissionGate resource="role" action="create">
          <button
            onClick={() => setEditingRole({ isNew: true })}
            className="create-role-button"
          >
            Create Role
          </button>
        </PermissionGate>
      </div>

      <div className="roles-grid">
        {roles.map(role => (
          <div key={role.id} className="role-card">
            <div className="role-header">
              <h3>{role.name}</h3>
              {!role.isCustom && (
                <span className="system-role-badge">System Role</span>
              )}
            </div>

            <p className="role-description">{role.description}</p>

            <div className="role-stats">
              <span className="member-count">
                {role.memberCount} members
              </span>
              <span className="permission-count">
                {role.permissions.length} permissions
              </span>
            </div>

            <div className="role-permissions">
              <h4>Permissions:</h4>
              <div className="permission-tags">
                {role.permissions.slice(0, 5).map(permission => (
                  <span key={permission} className="permission-tag">
                    {permission}
                  </span>
                ))}
                {role.permissions.length > 5 && (
                  <span className="more-permissions">
                    +{role.permissions.length - 5} more
                  </span>
                )}
              </div>
            </div>

            {role.isCustom && (
              <div className="role-actions">
                <PermissionGate resource="role" action="update">
                  <button
                    onClick={() => setEditingRole(role)}
                    className="edit-button"
                  >
                    Edit
                  </button>
                </PermissionGate>

                <PermissionGate resource="role" action="delete">
                  <button
                    onClick={() => handleDeleteRole(role)}
                    className="delete-button"
                  >
                    Delete
                  </button>
                </PermissionGate>
              </div>
            )}
          </div>
        ))}
      </div>

      {editingRole && (
        <RoleEditModal
          role={editingRole}
          onSave={editingRole.isNew ? createRole : updateRole}
          onCancel={() => setEditingRole(null)}
        />
      )}
    </div>
  )

  async function handleDeleteRole(role) {
    if (role.memberCount > 0) {
      const reassignRole = await selectReassignmentRole(roles.filter(r => r.id !== role.id))
      if (!reassignRole) return

      await deleteRole(role.id, reassignRole.id)
    } else {
      if (confirm(`Delete role "${role.name}"?`)) {
        await deleteRole(role.id)
      }
    }
  }
}

// Role editing modal component
function RoleEditModal({ role, onSave, onCancel }) {
  const [formData, setFormData] = useState({
    name: role.name || '',
    description: role.description || '',
    permissions: role.permissions || [],
    parentRoleId: role.parentRoleId || null
  })
  const [availablePermissions] = useState([
    'user:read', 'user:create', 'user:update', 'user:delete',
    'project:read', 'project:create', 'project:update', 'project:delete',
    'role:read', 'role:create', 'role:update', 'role:delete',
    'organization:read', 'organization:update',
    'billing:read', 'billing:update',
    'audit:read'
  ])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const handleSubmit = async (e) => {
    e.preventDefault()
    setLoading(true)
    setError(null)

    try {
      if (role.isNew) {
        await onSave(formData)
      } else {
        await onSave(role.id, formData)
      }
      onCancel()
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const togglePermission = (permission) => {
    const newPermissions = formData.permissions.includes(permission)
      ? formData.permissions.filter(p => p !== permission)
      : [...formData.permissions, permission]

    setFormData({ ...formData, permissions: newPermissions })
  }

  return (
    <div className="modal-overlay">
      <div className="modal">
        <h2>{role.isNew ? 'Create Role' : 'Edit Role'}</h2>

        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label>Role Name</label>
            <input
              type="text"
              value={formData.name}
              onChange={(e) => setFormData({
                ...formData,
                name: e.target.value
              })}
              required
            />
          </div>

          <div className="form-group">
            <label>Description</label>
            <textarea
              value={formData.description}
              onChange={(e) => setFormData({
                ...formData,
                description: e.target.value
              })}
            />
          </div>

          <div className="form-group">
            <label>Permissions</label>
            <div className="permissions-grid">
              {availablePermissions.map(permission => (
                <label key={permission} className="permission-checkbox">
                  <input
                    type="checkbox"
                    checked={formData.permissions.includes(permission)}
                    onChange={() => togglePermission(permission)}
                  />
                  {permission}
                </label>
              ))}
            </div>
          </div>

          {error && (
            <div className="error-message">{error}</div>
          )}

          <div className="form-actions">
            <button
              type="button"
              onClick={onCancel}
              className="cancel-button"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={loading}
              className="save-button"
            >
              {loading ? 'Saving...' : 'Save Role'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
```

## Advanced Features

### Dynamic Permissions

Create context-aware permissions:

```typescript
// Resource ownership permissions
const resourceOwnerPermissions = {
  'project:delete:own': async (userId, resourceId) => {
    const project = await plinto.projects.get(resourceId)
    return project.ownerId === userId
  },

  'user:update:team': async (userId, targetUserId) => {
    const manager = await plinto.users.get(userId)
    const subordinate = await plinto.users.get(targetUserId)
    return manager.teamId === subordinate.teamId && manager.role === 'manager'
  },

  'billing:read:organization': async (userId, organizationId) => {
    const membership = await plinto.organizations.getMembership({
      userId,
      organizationId
    })
    return ['owner', 'admin', 'billing_manager'].includes(membership.role.name)
  }
}

// Register dynamic permission handlers
plinto.rbac.registerDynamicPermissions(resourceOwnerPermissions)
```

### Permission Inheritance

Configure complex role hierarchies:

```typescript
// Multi-level inheritance
const roleHierarchy = {
  owner: {
    permissions: ['*:*'],
    children: ['admin']
  },
  admin: {
    permissions: [
      'user:*', 'project:*', 'role:*',
      'organization:read', 'organization:update',
      'billing:read', 'audit:read'
    ],
    children: ['manager']
  },
  manager: {
    permissions: [
      'user:read', 'user:invite', 'user:update:team',
      'project:*', 'report:read'
    ],
    children: ['member']
  },
  member: {
    permissions: [
      'user:read:own', 'project:read', 'project:create'
    ],
    children: ['viewer']
  },
  viewer: {
    permissions: ['*:read']
  }
}

await plinto.rbac.configureHierarchy(roleHierarchy)
```

### Conditional Permissions

Implement time-based and context-sensitive permissions:

```typescript
// Time-based permissions
const conditionalPermissions = {
  'billing:update': {
    conditions: [
      {
        type: 'time_restriction',
        businessHours: true,
        timezone: 'America/New_York'
      }
    ]
  },

  'audit:export': {
    conditions: [
      {
        type: 'approval_required',
        approvers: ['security_team'],
        expiresIn: 24 * 60 * 60 * 1000 // 24 hours
      }
    ]
  },

  'user:delete': {
    conditions: [
      {
        type: 'mfa_required',
        methods: ['totp', 'passkey']
      },
      {
        type: 'cooling_period',
        duration: 24 * 60 * 60 * 1000 // 24 hours
      }
    ]
  }
}

await plinto.rbac.setConditionalPermissions(conditionalPermissions)
```

## Testing

### Permission Testing

```typescript
describe('RBAC System', () => {
  let testUser, testOrg, adminRole, memberRole

  beforeEach(async () => {
    testOrg = await plinto.organizations.create({
      name: 'Test Organization'
    })

    adminRole = await plinto.rbac.createRole({
      organizationId: testOrg.id,
      name: 'Admin',
      permissions: ['user:*', 'project:*']
    })

    memberRole = await plinto.rbac.createRole({
      organizationId: testOrg.id,
      name: 'Member',
      permissions: ['project:read', 'user:read:own']
    })

    testUser = await plinto.users.create({
      email: 'test@example.com',
      organizationId: testOrg.id
    })
  })

  it('should grant permissions correctly', async () => {
    // Assign admin role
    await plinto.rbac.assignRole({
      userId: testUser.id,
      roleId: adminRole.id,
      organizationId: testOrg.id
    })

    // Check permissions
    const canDeleteUser = await plinto.rbac.checkPermission({
      userId: testUser.id,
      organizationId: testOrg.id,
      resource: 'user',
      action: 'delete'
    })

    expect(canDeleteUser).toBe(true)
  })

  it('should deny permissions correctly', async () => {
    // Assign member role
    await plinto.rbac.assignRole({
      userId: testUser.id,
      roleId: memberRole.id,
      organizationId: testOrg.id
    })

    // Check permissions
    const canDeleteUser = await plinto.rbac.checkPermission({
      userId: testUser.id,
      organizationId: testOrg.id,
      resource: 'user',
      action: 'delete'
    })

    expect(canDeleteUser).toBe(false)
  })

  it('should handle role inheritance', async () => {
    // Create child role that inherits from admin
    const managerRole = await plinto.rbac.createRole({
      organizationId: testOrg.id,
      name: 'Manager',
      permissions: ['team:manage'],
      parentRoleId: adminRole.id
    })

    await plinto.rbac.assignRole({
      userId: testUser.id,
      roleId: managerRole.id,
      organizationId: testOrg.id
    })

    // Should have both own permissions and inherited permissions
    const canManageTeam = await plinto.rbac.checkPermission({
      userId: testUser.id,
      organizationId: testOrg.id,
      resource: 'team',
      action: 'manage'
    })

    const canDeleteUser = await plinto.rbac.checkPermission({
      userId: testUser.id,
      organizationId: testOrg.id,
      resource: 'user',
      action: 'delete'
    })

    expect(canManageTeam).toBe(true) // Own permission
    expect(canDeleteUser).toBe(true) // Inherited permission
  })

  it('should handle wildcard permissions', async () => {
    const superAdminRole = await plinto.rbac.createRole({
      organizationId: testOrg.id,
      name: 'Super Admin',
      permissions: ['*:*']
    })

    await plinto.rbac.assignRole({
      userId: testUser.id,
      roleId: superAdminRole.id,
      organizationId: testOrg.id
    })

    // Should have all permissions
    const canDoAnything = await plinto.rbac.checkPermission({
      userId: testUser.id,
      organizationId: testOrg.id,
      resource: 'anything',
      action: 'any_action'
    })

    expect(canDoAnything).toBe(true)
  })

  it('should enforce resource-specific permissions', async () => {
    const ownProjectRole = await plinto.rbac.createRole({
      organizationId: testOrg.id,
      name: 'Project Owner',
      permissions: ['project:delete:own']
    })

    await plinto.rbac.assignRole({
      userId: testUser.id,
      roleId: ownProjectRole.id,
      organizationId: testOrg.id
    })

    // Create projects
    const ownProject = await plinto.projects.create({
      name: 'Own Project',
      ownerId: testUser.id
    })

    const otherProject = await plinto.projects.create({
      name: 'Other Project',
      ownerId: 'other-user-id'
    })

    // Can delete own project
    const canDeleteOwn = await plinto.rbac.checkPermission({
      userId: testUser.id,
      organizationId: testOrg.id,
      resource: 'project',
      action: 'delete',
      resourceId: ownProject.id
    })

    // Cannot delete other's project
    const canDeleteOther = await plinto.rbac.checkPermission({
      userId: testUser.id,
      organizationId: testOrg.id,
      resource: 'project',
      action: 'delete',
      resourceId: otherProject.id
    })

    expect(canDeleteOwn).toBe(true)
    expect(canDeleteOther).toBe(false)
  })
})
```

## Migration Guide

### From Basic Roles to RBAC

```typescript
// Migration from simple role strings to RBAC
const migrateToRBAC = async () => {
  // Get all users with old role system
  const users = await plinto.tenancy.withSystemContext(() =>
    plinto.users.list({ includeOldRoles: true })
  )

  const roleMapping = {
    'admin': {
      roleName: 'Administrator',
      permissions: [
        'user:*', 'project:*', 'organization:read',
        'organization:update', 'billing:read', 'audit:read'
      ]
    },
    'manager': {
      roleName: 'Manager',
      permissions: [
        'user:read', 'user:invite', 'project:*', 'team:manage'
      ]
    },
    'user': {
      roleName: 'Member',
      permissions: [
        'user:read:own', 'project:read', 'project:create'
      ]
    }
  }

  for (const [oldRole, config] of Object.entries(roleMapping)) {
    // Create new RBAC role
    const newRole = await plinto.rbac.createRole({
      name: config.roleName,
      permissions: config.permissions,
      isSystemRole: true
    })

    // Update users with old role
    const usersWithRole = users.filter(u => u.oldRole === oldRole)

    for (const user of usersWithRole) {
      await plinto.rbac.assignRole({
        userId: user.id,
        roleId: newRole.id,
        organizationId: user.organizationId
      })

      // Remove old role field
      await plinto.users.update(user.id, {
        oldRole: null,
        migratedToRBAC: true
      })
    }

    console.log(`Migrated ${usersWithRole.length} users from ${oldRole} to ${config.roleName}`)
  }
}
```

## API Reference

### `rbac.checkPermission(options)`

Check user permission.

**Parameters:**
- `userId` (string, required): User ID
- `organizationId` (string, required): Organization ID
- `resource` (string, required): Resource type
- `action` (string, required): Action to check
- `scope` (string): Permission scope
- `resourceId` (string): Specific resource ID

**Returns:**
- `hasPermission` (boolean): Permission result

### `rbac.createRole(options)`

Create custom role.

**Parameters:**
- `organizationId` (string, required): Organization ID
- `name` (string, required): Role name
- `description` (string): Role description
- `permissions` (array, required): Permission list
- `parentRoleId` (string): Parent role for inheritance

**Returns:**
- `role` (object): Created role details

### `rbac.assignRole(options)`

Assign role to user.

**Parameters:**
- `userId` (string, required): User ID
- `roleId` (string, required): Role ID
- `organizationId` (string, required): Organization ID

**Returns:**
- `success` (boolean): Assignment result

## Related Guides

- [Multi-Tenant Architecture](/guides/organizations/multi-tenant)
- [SCIM 2.0 Integration](/guides/organizations/scim)
- [Audit Logging](/guides/security/audit-logging)
- [Security Best Practices](/guides/security/best-practices)