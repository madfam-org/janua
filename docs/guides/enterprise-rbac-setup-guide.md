# Enterprise RBAC (Role-Based Access Control) Setup Guide

> **Complete guide to implementing hierarchical role-based access control with custom permissions and advanced security policies**

## Overview

Janua API provides enterprise-grade RBAC with hierarchical roles, custom permissions, fine-grained access control, and comprehensive audit logging. This system supports complex organizational structures and compliance requirements.

## 🎭 RBAC Features

### Core Capabilities
- **Hierarchical Roles** with inheritance and delegation
- **Custom Permissions** with granular resource control
- **Policy-Based Access Control** with conditional rules
- **Multi-Tenancy Support** with organization isolation
- **Dynamic Role Assignment** based on user attributes
- **Audit Trail** for all role and permission changes

### Advanced Features
- **Role Templates** for common organizational patterns
- **Permission Groups** for logical access management
- **Conditional Access** based on context (IP, time, device)
- **Resource-Level Permissions** with fine-grained control
- **Delegation Chains** for temporary access grants
- **Compliance Frameworks** (SOX, HIPAA, GDPR ready)

### Built-in Roles
- **Owner**: Full organizational control
- **Admin**: Administrative privileges without ownership transfer
- **Manager**: Team and project management
- **Member**: Standard user access
- **Viewer**: Read-only access
- **Guest**: Limited temporary access

## 🚀 Quick Start

### 1. Create Custom Role

```bash
curl -X POST "https://api.janua.dev/api/v1/organizations/org_123/roles" \
  -H "Authorization: Bearer <admin_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "DevOps Engineer",
    "description": "Full deployment and infrastructure access",
    "permissions": [
      "organizations.deploy",
      "organizations.monitor",
      "users.read",
      "projects.admin",
      "secrets.read"
    ],
    "is_custom": true,
    "inherits_from": "member",
    "max_assignments": 10
  }'
```

### 2. Assign Role to User

```bash
curl -X PUT "https://api.janua.dev/api/v1/organizations/org_123/members/user_456" \
  -H "Authorization: Bearer <admin_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "role": "DevOps Engineer",
    "valid_until": "2025-12-31T23:59:59Z",
    "assigned_by": "admin_789"
  }'
```

### 3. Check User Permissions

```bash
curl "https://api.janua.dev/api/v1/organizations/org_123/members/user_456/permissions" \
  -H "Authorization: Bearer <token>"
```

**Response:**
```json
{
  "user_id": "user_456",
  "role": "DevOps Engineer",
  "effective_permissions": [
    "organizations.deploy",
    "organizations.monitor",
    "users.read",
    "projects.admin",
    "secrets.read",
    "organizations.read",
    "projects.read"
  ],
  "inherited_permissions": [
    "organizations.read",
    "projects.read"
  ],
  "role_hierarchy": ["member", "DevOps Engineer"]
}
```

## 🏗️ RBAC Architecture

### Permission Structure

```yaml
# Core Permission Categories
users:
  - users.read          # View user profiles
  - users.write         # Update user information
  - users.create        # Create new users
  - users.delete        # Delete users
  - users.admin         # Full user management

organizations:
  - organizations.read  # View organization info
  - organizations.write # Update organization
  - organizations.admin # Full organization control
  - organizations.deploy # Deployment access
  - organizations.monitor # Monitoring access

projects:
  - projects.read       # View projects
  - projects.write      # Update projects
  - projects.create     # Create projects
  - projects.delete     # Delete projects
  - projects.admin      # Full project control

security:
  - security.read       # View security settings
  - security.write      # Update security settings
  - security.admin      # Full security control
  - security.audit      # Access audit logs

billing:
  - billing.read        # View billing info
  - billing.write       # Update billing
  - billing.admin       # Full billing control

webhooks:
  - webhooks.read       # View webhooks
  - webhooks.write      # Manage webhooks
  - webhooks.admin      # Full webhook control

api_keys:
  - api_keys.read       # View API keys
  - api_keys.write      # Manage API keys
  - api_keys.admin      # Full API key control

secrets:
  - secrets.read        # Access secrets
  - secrets.write       # Manage secrets
  - secrets.admin       # Full secrets control
```

### Role Hierarchy

```yaml
# Built-in Role Hierarchy (lowest to highest)
guest:
  permissions: []
  description: "Temporary limited access"

viewer:
  inherits_from: guest
  permissions:
    - "organizations.read"
    - "users.read"
    - "projects.read"

member:
  inherits_from: viewer
  permissions:
    - "projects.write"
    - "users.write" # own profile only

manager:
  inherits_from: member
  permissions:
    - "projects.create"
    - "projects.admin"
    - "users.admin" # team members only

admin:
  inherits_from: manager
  permissions:
    - "organizations.write"
    - "security.admin"
    - "billing.admin"
    - "webhooks.admin"

owner:
  inherits_from: admin
  permissions:
    - "organizations.admin"
    - "organizations.delete"
    - "users.admin" # all users
    - "billing.admin"
  special_privileges:
    - "transfer_ownership"
    - "delete_organization"
```

## 💻 Implementation Examples

### Frontend RBAC Integration

```javascript
class RBACManager {
  constructor(apiClient) {
    this.api = apiClient;
    this.userPermissions = new Set();
    this.userRole = null;
  }

  // Initialize user permissions
  async initializePermissions(organizationId) {
    try {
      const response = await this.api.get(
        `/api/v1/organizations/${organizationId}/members/me/permissions`
      );

      this.userPermissions = new Set(response.data.effective_permissions);
      this.userRole = response.data.role;

      return response.data;
    } catch (error) {
      throw new Error(`Failed to load permissions: ${error.message}`);
    }
  }

  // Check single permission
  hasPermission(permission) {
    return this.userPermissions.has(permission);
  }

  // Check multiple permissions (all required)
  hasAllPermissions(permissions) {
    return permissions.every(permission =>
      this.userPermissions.has(permission)
    );
  }

  // Check multiple permissions (any required)
  hasAnyPermission(permissions) {
    return permissions.some(permission =>
      this.userPermissions.has(permission)
    );
  }

  // Check role
  hasRole(role) {
    return this.userRole === role;
  }

  // Check minimum role level
  hasMinimumRole(role) {
    const roleHierarchy = ['guest', 'viewer', 'member', 'manager', 'admin', 'owner'];
    const userLevel = roleHierarchy.indexOf(this.userRole);
    const requiredLevel = roleHierarchy.indexOf(role);
    return userLevel >= requiredLevel;
  }

  // Check if user can perform action on resource
  canPerformAction(action, resource, resourceOwnerId = null) {
    const permission = `${resource}.${action}`;

    // Check basic permission
    if (!this.hasPermission(permission)) {
      return false;
    }

    // Additional checks for resource ownership
    if (resourceOwnerId && action !== 'read') {
      // Users can always modify their own resources
      if (resourceOwnerId === this.getCurrentUserId()) {
        return true;
      }

      // Otherwise, check for admin permissions
      return this.hasPermission(`${resource}.admin`);
    }

    return true;
  }

  getCurrentUserId() {
    // Get current user ID from token or context
    return localStorage.getItem('user_id');
  }
}
```

### React RBAC Components

```jsx
import React, { createContext, useContext, useEffect, useState } from 'react';

// RBAC Context
const RBACContext = createContext();

export const RBACProvider = ({ children, organizationId }) => {
  const [rbacManager, setRBACManager] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    initializeRBAC();
  }, [organizationId]);

  const initializeRBAC = async () => {
    try {
      const manager = new RBACManager(apiClient);
      await manager.initializePermissions(organizationId);
      setRBACManager(manager);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <RBACContext.Provider value={{ rbacManager, loading, error }}>
      {children}
    </RBACContext.Provider>
  );
};

// Permission Guard Component
export const PermissionGuard = ({
  permission,
  permissions,
  requireAll = true,
  fallback = null,
  children
}) => {
  const { rbacManager } = useContext(RBACContext);

  if (!rbacManager) return fallback;

  let hasAccess = false;

  if (permission) {
    hasAccess = rbacManager.hasPermission(permission);
  } else if (permissions) {
    hasAccess = requireAll
      ? rbacManager.hasAllPermissions(permissions)
      : rbacManager.hasAnyPermission(permissions);
  }

  return hasAccess ? children : fallback;
};

// Role Guard Component
export const RoleGuard = ({
  role,
  minimumRole = false,
  fallback = null,
  children
}) => {
  const { rbacManager } = useContext(RBACContext);

  if (!rbacManager) return fallback;

  const hasAccess = minimumRole
    ? rbacManager.hasMinimumRole(role)
    : rbacManager.hasRole(role);

  return hasAccess ? children : fallback;
};

// Action Guard Component
export const ActionGuard = ({
  action,
  resource,
  resourceOwnerId,
  fallback = null,
  children
}) => {
  const { rbacManager } = useContext(RBACContext);

  if (!rbacManager) return fallback;

  const canPerform = rbacManager.canPerformAction(action, resource, resourceOwnerId);

  return canPerform ? children : fallback;
};

// Usage Examples
const UserManagementPage = () => {
  return (
    <div>
      <h1>User Management</h1>

      <PermissionGuard permission="users.read">
        <UserList />
      </PermissionGuard>

      <PermissionGuard permission="users.create">
        <button>Create User</button>
      </PermissionGuard>

      <RoleGuard minimumRole="admin">
        <AdminPanel />
      </RoleGuard>

      <ActionGuard action="delete" resource="users">
        <button>Delete User</button>
      </ActionGuard>
    </div>
  );
};
```

### Vue.js RBAC Integration

```vue
<template>
  <div>
    <h1>Project Management</h1>

    <PermissionGuard permission="projects.read">
      <ProjectList />
    </PermissionGuard>

    <PermissionGuard permission="projects.create">
      <button @click="createProject">Create Project</button>
    </PermissionGuard>

    <RoleGuard minimum-role="manager">
      <ProjectSettings />
    </RoleGuard>
  </div>
</template>

<script setup>
import { ref, onMounted, provide } from 'vue';
import { useRBAC } from './composables/useRBAC';

const props = defineProps({
  organizationId: String
});

const { rbacManager, initializePermissions } = useRBAC();

onMounted(async () => {
  await initializePermissions(props.organizationId);
});

// Provide RBAC to child components
provide('rbacManager', rbacManager);

const createProject = () => {
  // Project creation logic
};
</script>
```

### Vue.js RBAC Composable

```javascript
// composables/useRBAC.js
import { ref, computed } from 'vue';

export function useRBAC() {
  const rbacManager = ref(null);
  const loading = ref(false);
  const error = ref(null);

  const initializePermissions = async (organizationId) => {
    loading.value = true;
    error.value = null;

    try {
      const manager = new RBACManager(apiClient);
      await manager.initializePermissions(organizationId);
      rbacManager.value = manager;
    } catch (err) {
      error.value = err.message;
    } finally {
      loading.value = false;
    }
  };

  const hasPermission = computed(() => (permission) => {
    return rbacManager.value?.hasPermission(permission) || false;
  });

  const hasRole = computed(() => (role) => {
    return rbacManager.value?.hasRole(role) || false;
  });

  const canPerformAction = computed(() => (action, resource, resourceOwnerId) => {
    return rbacManager.value?.canPerformAction(action, resource, resourceOwnerId) || false;
  });

  return {
    rbacManager,
    loading,
    error,
    initializePermissions,
    hasPermission,
    hasRole,
    canPerformAction
  };
}
```

## 🔧 Backend RBAC Implementation

### Custom Role Management

```python
from app.services.rbac_service import RBACService
from app.models import Role, Permission, UserRole

class CustomRoleManager:
    def __init__(self):
        self.rbac_service = RBACService()

    async def create_custom_role(
        self,
        organization_id: str,
        role_data: dict,
        created_by: str,
        db: AsyncSession
    ):
        """Create custom role with permissions"""

        # Validate role data
        await self.validate_role_data(role_data, organization_id, db)

        # Create role
        role = Role(
            name=role_data["name"],
            description=role_data.get("description", ""),
            organization_id=organization_id,
            is_custom=True,
            inherits_from=role_data.get("inherits_from"),
            max_assignments=role_data.get("max_assignments"),
            created_by=created_by
        )

        db.add(role)
        await db.flush()

        # Assign permissions
        await self.assign_permissions_to_role(
            role.id, role_data["permissions"], db
        )

        # Log role creation
        await self.log_role_event(
            "role_created", role.id, created_by,
            {"role_name": role.name}, db
        )

        await db.commit()
        return role

    async def assign_permissions_to_role(
        self,
        role_id: str,
        permissions: list,
        db: AsyncSession
    ):
        """Assign permissions to role"""

        # Remove existing permissions
        await db.execute(
            delete(RolePermission).where(RolePermission.role_id == role_id)
        )

        # Add new permissions
        for permission_name in permissions:
            permission = await self.get_or_create_permission(permission_name, db)

            role_permission = RolePermission(
                role_id=role_id,
                permission_id=permission.id
            )
            db.add(role_permission)

    async def validate_role_data(self, role_data: dict, org_id: str, db: AsyncSession):
        """Validate role creation data"""

        # Check role name uniqueness
        existing_role = await db.execute(
            select(Role).where(
                Role.name == role_data["name"],
                Role.organization_id == org_id
            )
        )
        if existing_role.scalar_one_or_none():
            raise ValueError(f"Role '{role_data['name']}' already exists")

        # Validate inheritance
        if role_data.get("inherits_from"):
            parent_role = await self.get_role_by_name(
                role_data["inherits_from"], org_id, db
            )
            if not parent_role:
                raise ValueError(f"Parent role '{role_data['inherits_from']}' not found")

        # Validate permissions
        invalid_permissions = await self.validate_permissions(
            role_data["permissions"], db
        )
        if invalid_permissions:
            raise ValueError(f"Invalid permissions: {invalid_permissions}")
```

### Permission Checking Middleware

```python
from functools import wraps
from fastapi import HTTPException, Depends
from app.dependencies import get_current_user

def require_permission(permission: str, resource_id_param: str = None):
    """Decorator for permission-based access control"""

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Get dependencies
            current_user = kwargs.get('current_user')
            if not current_user:
                raise HTTPException(401, "Authentication required")

            # Get organization from request context
            organization_id = kwargs.get('organization_id') or \
                             getattr(current_user, 'current_organization_id', None)

            if not organization_id:
                raise HTTPException(400, "Organization context required")

            # Check permission
            rbac_service = RBACService()
            has_permission = await rbac_service.user_has_permission(
                current_user.id, organization_id, permission
            )

            if not has_permission:
                # Check resource-level permissions if applicable
                if resource_id_param and resource_id_param in kwargs:
                    resource_id = kwargs[resource_id_param]
                    has_resource_permission = await rbac_service.user_has_resource_permission(
                        current_user.id, organization_id, permission, resource_id
                    )

                    if not has_resource_permission:
                        raise HTTPException(403, f"Permission '{permission}' required")
                else:
                    raise HTTPException(403, f"Permission '{permission}' required")

            return await func(*args, **kwargs)
        return wrapper
    return decorator

# Usage examples
@router.get("/projects")
@require_permission("projects.read")
async def list_projects(
    organization_id: str,
    current_user: User = Depends(get_current_user)
):
    """List projects - requires projects.read permission"""
    pass

@router.delete("/projects/{project_id}")
@require_permission("projects.delete", resource_id_param="project_id")
async def delete_project(
    organization_id: str,
    project_id: str,
    current_user: User = Depends(get_current_user)
):
    """Delete project - requires projects.delete permission"""
    pass
```

### Dynamic Role Assignment

```python
from app.models import UserRole, ActivityLog

class DynamicRoleAssigner:
    def __init__(self):
        self.rbac_service = RBACService()

    async def assign_role_based_on_attributes(
        self,
        user: User,
        organization: Organization,
        user_attributes: dict,
        db: AsyncSession
    ):
        """Assign role based on user attributes (from SSO, etc.)"""

        # Role assignment rules
        role_rules = await self.get_role_assignment_rules(organization.id, db)

        assigned_role = "member"  # default

        for rule in role_rules:
            if self.evaluate_rule(rule, user_attributes):
                assigned_role = rule.target_role
                break

        # Assign role
        await self.assign_role_to_user(
            user.id, organization.id, assigned_role,
            assignment_reason="attribute_based", db=db
        )

        return assigned_role

    def evaluate_rule(self, rule: dict, attributes: dict) -> bool:
        """Evaluate role assignment rule against user attributes"""

        conditions = rule.get("conditions", [])

        for condition in conditions:
            attribute_name = condition["attribute"]
            operator = condition["operator"]
            expected_value = condition["value"]
            actual_value = attributes.get(attribute_name)

            if not self.evaluate_condition(actual_value, operator, expected_value):
                return False

        return True

    def evaluate_condition(self, actual, operator, expected) -> bool:
        """Evaluate individual condition"""

        if operator == "equals":
            return actual == expected
        elif operator == "contains":
            return expected in (actual or "")
        elif operator == "starts_with":
            return (actual or "").startswith(expected)
        elif operator == "in":
            return actual in expected
        elif operator == "not_equals":
            return actual != expected

        return False

    async def get_role_assignment_rules(self, organization_id: str, db: AsyncSession):
        """Get role assignment rules for organization"""

        # Example rules structure
        return [
            {
                "priority": 1,
                "target_role": "admin",
                "conditions": [
                    {"attribute": "department", "operator": "equals", "value": "IT"},
                    {"attribute": "job_title", "operator": "contains", "value": "Administrator"}
                ]
            },
            {
                "priority": 2,
                "target_role": "manager",
                "conditions": [
                    {"attribute": "job_title", "operator": "contains", "value": "Manager"}
                ]
            },
            {
                "priority": 3,
                "target_role": "member",
                "conditions": [
                    {"attribute": "employee_type", "operator": "equals", "value": "Full-time"}
                ]
            }
        ]
```

## 🛡️ Security & Compliance

### Audit Logging for RBAC

```python
from app.models import AuditLog
from datetime import datetime

class RBACAuditLogger:
    async def log_permission_check(
        self,
        user_id: str,
        organization_id: str,
        permission: str,
        resource_id: str = None,
        access_granted: bool = False,
        ip_address: str = None,
        user_agent: str = None,
        db: AsyncSession = None
    ):
        """Log permission check for audit purposes"""

        audit_entry = AuditLog(
            event_type="permission_check",
            user_id=user_id,
            organization_id=organization_id,
            resource_type="permission",
            resource_id=resource_id,
            details={
                "permission": permission,
                "access_granted": access_granted,
                "resource_id": resource_id
            },
            ip_address=ip_address,
            user_agent=user_agent,
            timestamp=datetime.utcnow()
        )

        db.add(audit_entry)
        await db.commit()

    async def log_role_assignment(
        self,
        user_id: str,
        organization_id: str,
        role: str,
        assigned_by: str,
        assignment_reason: str = None,
        valid_until: datetime = None,
        db: AsyncSession = None
    ):
        """Log role assignment"""

        audit_entry = AuditLog(
            event_type="role_assigned",
            user_id=assigned_by,
            organization_id=organization_id,
            resource_type="user_role",
            resource_id=user_id,
            details={
                "target_user_id": user_id,
                "role": role,
                "assignment_reason": assignment_reason,
                "valid_until": valid_until.isoformat() if valid_until else None
            },
            timestamp=datetime.utcnow()
        )

        db.add(audit_entry)
        await db.commit()

    async def generate_access_report(
        self,
        organization_id: str,
        start_date: datetime,
        end_date: datetime,
        db: AsyncSession
    ):
        """Generate comprehensive access report for compliance"""

        # Get all permission checks in date range
        permission_checks = await db.execute(
            select(AuditLog).where(
                AuditLog.organization_id == organization_id,
                AuditLog.event_type == "permission_check",
                AuditLog.timestamp >= start_date,
                AuditLog.timestamp <= end_date
            )
        )

        # Analyze access patterns
        report = {
            "period": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat()
            },
            "total_access_attempts": 0,
            "successful_access": 0,
            "denied_access": 0,
            "most_accessed_resources": [],
            "users_with_access_violations": [],
            "permissions_summary": {}
        }

        # Process audit logs
        for log in permission_checks.scalars():
            report["total_access_attempts"] += 1

            if log.details.get("access_granted"):
                report["successful_access"] += 1
            else:
                report["denied_access"] += 1

            # Track permission usage
            permission = log.details.get("permission")
            if permission not in report["permissions_summary"]:
                report["permissions_summary"][permission] = {
                    "total_attempts": 0,
                    "successful": 0,
                    "denied": 0
                }

            report["permissions_summary"][permission]["total_attempts"] += 1
            if log.details.get("access_granted"):
                report["permissions_summary"][permission]["successful"] += 1
            else:
                report["permissions_summary"][permission]["denied"] += 1

        return report
```

### Policy-Based Access Control

```python
from typing import Dict, Any
import json

class PolicyEngine:
    def __init__(self):
        self.policies = {}

    async def evaluate_policy(
        self,
        policy_name: str,
        context: Dict[str, Any]
    ) -> bool:
        """Evaluate access policy against context"""

        policy = await self.get_policy(policy_name)
        if not policy:
            return False

        return self.evaluate_rules(policy["rules"], context)

    def evaluate_rules(self, rules: list, context: Dict[str, Any]) -> bool:
        """Evaluate policy rules"""

        for rule in rules:
            rule_type = rule.get("type")

            if rule_type == "time_based":
                if not self.evaluate_time_rule(rule, context):
                    return False

            elif rule_type == "ip_based":
                if not self.evaluate_ip_rule(rule, context):
                    return False

            elif rule_type == "device_based":
                if not self.evaluate_device_rule(rule, context):
                    return False

            elif rule_type == "risk_based":
                if not self.evaluate_risk_rule(rule, context):
                    return False

        return True

    def evaluate_time_rule(self, rule: dict, context: Dict[str, Any]) -> bool:
        """Evaluate time-based access rule"""

        current_time = context.get("current_time")
        allowed_hours = rule.get("allowed_hours", [])
        allowed_days = rule.get("allowed_days", [])

        if allowed_hours and current_time.hour not in allowed_hours:
            return False

        if allowed_days and current_time.weekday() not in allowed_days:
            return False

        return True

    def evaluate_ip_rule(self, rule: dict, context: Dict[str, Any]) -> bool:
        """Evaluate IP-based access rule"""

        client_ip = context.get("ip_address")
        allowed_ips = rule.get("allowed_ips", [])
        blocked_ips = rule.get("blocked_ips", [])

        if blocked_ips and client_ip in blocked_ips:
            return False

        if allowed_ips and client_ip not in allowed_ips:
            # Check IP ranges
            for ip_range in allowed_ips:
                if self.ip_in_range(client_ip, ip_range):
                    return True
            return False

        return True

    async def create_policy(
        self,
        organization_id: str,
        policy_data: dict,
        db: AsyncSession
    ):
        """Create access control policy"""

        policy = AccessPolicy(
            organization_id=organization_id,
            name=policy_data["name"],
            description=policy_data.get("description", ""),
            rules=policy_data["rules"],
            enabled=policy_data.get("enabled", True),
            priority=policy_data.get("priority", 100)
        )

        db.add(policy)
        await db.commit()

        return policy

# Example policy definitions
TIME_BASED_POLICY = {
    "name": "business_hours_only",
    "description": "Allow access only during business hours",
    "rules": [
        {
            "type": "time_based",
            "allowed_hours": list(range(9, 18)),  # 9 AM to 6 PM
            "allowed_days": list(range(0, 5))     # Monday to Friday
        }
    ]
}

IP_WHITELIST_POLICY = {
    "name": "office_ip_only",
    "description": "Allow access only from office IP ranges",
    "rules": [
        {
            "type": "ip_based",
            "allowed_ips": [
                "192.168.1.0/24",
                "10.0.0.0/8",
                "203.0.113.0/24"
            ]
        }
    ]
}

RISK_BASED_POLICY = {
    "name": "high_privilege_protection",
    "description": "Additional security for high-privilege operations",
    "rules": [
        {
            "type": "risk_based",
            "max_risk_score": 30,
            "require_mfa": True,
            "require_device_trust": True
        }
    ]
}
```

## 📊 RBAC Analytics

### Role Usage Analytics

```python
from sqlalchemy import func
from app.models import UserRole, AuditLog

class RBACAnalytics:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_role_distribution(self, organization_id: str):
        """Get distribution of roles in organization"""

        role_counts = await self.db.execute(
            select(
                UserRole.role,
                func.count(UserRole.user_id).label('count')
            ).where(
                UserRole.organization_id == organization_id,
                UserRole.is_active == True
            ).group_by(UserRole.role)
        )

        return {
            role: count for role, count in role_counts.all()
        }

    async def get_permission_usage(
        self,
        organization_id: str,
        days: int = 30
    ):
        """Get permission usage statistics"""

        cutoff_date = datetime.utcnow() - timedelta(days=days)

        permission_usage = await self.db.execute(
            select(
                AuditLog.details['permission'].astext.label('permission'),
                func.count(AuditLog.id).label('usage_count'),
                func.sum(
                    case((AuditLog.details['access_granted'].astext == 'true', 1), else_=0)
                ).label('successful_accesses'),
                func.sum(
                    case((AuditLog.details['access_granted'].astext == 'false', 1), else_=0)
                ).label('denied_accesses')
            ).where(
                AuditLog.organization_id == organization_id,
                AuditLog.event_type == 'permission_check',
                AuditLog.timestamp >= cutoff_date
            ).group_by(AuditLog.details['permission'].astext)
        )

        return [
            {
                "permission": permission,
                "total_checks": usage_count,
                "successful": successful_accesses,
                "denied": denied_accesses,
                "success_rate": (successful_accesses / usage_count * 100) if usage_count > 0 else 0
            }
            for permission, usage_count, successful_accesses, denied_accesses in permission_usage.all()
        ]

    async def identify_over_privileged_users(self, organization_id: str):
        """Identify users with permissions they rarely use"""

        # Users who haven't used high-privilege permissions in 30 days
        cutoff_date = datetime.utcnow() - timedelta(days=30)

        high_privilege_permissions = [
            'organizations.admin', 'users.admin', 'security.admin',
            'billing.admin', 'organizations.delete'
        ]

        over_privileged = []

        for permission in high_privilege_permissions:
            # Find users with this permission
            users_with_permission = await self.get_users_with_permission(
                organization_id, permission
            )

            # Check usage
            for user in users_with_permission:
                usage_count = await self.get_user_permission_usage(
                    user.id, permission, cutoff_date
                )

                if usage_count == 0:
                    over_privileged.append({
                        "user_id": user.id,
                        "user_email": user.email,
                        "permission": permission,
                        "last_used": await self.get_last_permission_usage(
                            user.id, permission
                        )
                    })

        return over_privileged

    async def generate_compliance_report(self, organization_id: str):
        """Generate compliance report for auditors"""

        report = {
            "organization_id": organization_id,
            "report_date": datetime.utcnow().isoformat(),
            "role_distribution": await self.get_role_distribution(organization_id),
            "permission_usage": await self.get_permission_usage(organization_id),
            "over_privileged_users": await self.identify_over_privileged_users(organization_id),
            "custom_roles": await self.get_custom_roles(organization_id),
            "recent_role_changes": await self.get_recent_role_changes(organization_id, 30),
            "policy_violations": await self.get_policy_violations(organization_id, 30)
        }

        return report
```

## 🔍 Troubleshooting

### Common RBAC Issues

**Issue: "Permission denied" for valid users**
```python
def debug_permission_issue(user_id: str, organization_id: str, permission: str):
    """Debug permission access issues"""

    debug_info = {
        "user_role": None,
        "effective_permissions": [],
        "inheritance_chain": [],
        "organization_membership": False,
        "role_status": None
    }

    # Check organization membership
    membership = check_organization_membership(user_id, organization_id)
    debug_info["organization_membership"] = membership is not None

    if membership:
        debug_info["user_role"] = membership.role
        debug_info["role_status"] = membership.status

        # Get effective permissions
        permissions = get_effective_permissions(user_id, organization_id)
        debug_info["effective_permissions"] = permissions

        # Check inheritance chain
        inheritance = get_role_inheritance_chain(membership.role)
        debug_info["inheritance_chain"] = inheritance

    return debug_info
```

**Issue: Role assignment not taking effect**
```python
def debug_role_assignment():
    """Debug role assignment issues"""

    common_issues = [
        "1. Check if user is active member of organization",
        "2. Verify role exists and is enabled",
        "3. Check role assignment expiration date",
        "4. Verify role inheritance is correctly configured",
        "5. Clear permission cache if using caching",
        "6. Check for conflicting role assignments"
    ]

    return common_issues
```

## 📚 API Reference

### Complete RBAC Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/organizations/{id}/roles` | List organization roles |
| POST | `/organizations/{id}/roles` | Create custom role |
| GET | `/organizations/{id}/roles/{role_id}` | Get role details |
| PUT | `/organizations/{id}/roles/{role_id}` | Update role |
| DELETE | `/organizations/{id}/roles/{role_id}` | Delete role |
| GET | `/organizations/{id}/permissions` | List available permissions |
| GET | `/organizations/{id}/members/{user_id}/permissions` | Get user permissions |
| PUT | `/organizations/{id}/members/{user_id}` | Update user role |
| GET | `/organizations/{id}/roles/{role_id}/permissions` | Get role permissions |
| PUT | `/organizations/{id}/roles/{role_id}/permissions` | Update role permissions |

For complete API documentation, see:
- [Organization Management API](../api/organizations.md)
- [User Management API](../api/users.md)

## 🎯 Advanced Features

### Role Templates

```python
ROLE_TEMPLATES = {
    "developer": {
        "name": "Developer",
        "description": "Software development team member",
        "permissions": [
            "projects.read", "projects.write",
            "organizations.read",
            "users.read"
        ],
        "inherits_from": "member"
    },

    "devops_engineer": {
        "name": "DevOps Engineer",
        "description": "Deployment and infrastructure management",
        "permissions": [
            "projects.admin", "organizations.deploy",
            "organizations.monitor", "secrets.read",
            "webhooks.read"
        ],
        "inherits_from": "member"
    },

    "security_officer": {
        "name": "Security Officer",
        "description": "Security and compliance management",
        "permissions": [
            "security.admin", "organizations.audit",
            "users.admin", "policies.admin"
        ],
        "inherits_from": "admin"
    }
}
```

### Integration with External Systems

```python
class ExternalSystemIntegration:
    async def sync_roles_from_hr_system(self, organization_id: str):
        """Sync roles from HR system"""

        # Fetch from HR API
        hr_data = await self.fetch_hr_data(organization_id)

        # Map HR roles to Janua roles
        role_mapping = {
            "Software Engineer": "developer",
            "Senior Engineer": "senior_developer",
            "Engineering Manager": "manager",
            "Director": "admin"
        }

        # Update user roles
        for employee in hr_data:
            hr_role = employee.get("job_title")
            janua_role = role_mapping.get(hr_role, "member")

            await self.update_user_role(
                employee["email"], organization_id, janua_role
            )
```

---

**🏢 [Enterprise SSO Guide](enterprise-sso-saml-setup-guide.md)** • **👨‍💼 [SCIM Documentation](../api/scim.md)** • **🔐 [Security Framework](../security/README.md)**