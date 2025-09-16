import { EventEmitter } from 'events';
import { RedisService, getRedis } from './redis.service';
import { getMultiTenancyService, MultiTenancyService } from './multi-tenancy.service';
import { getTeamManagementService, TeamManagementService } from './team-management.service';

interface Role {
  id: string;
  organization_id: string;
  name: string;
  description?: string;
  permissions: Permission[];
  parent_role_id?: string;
  is_system: boolean;
  is_default: boolean;
  priority: number;
  constraints?: RoleConstraints;
  metadata?: Record<string, any>;
  created_at: Date;
  updated_at: Date;
  created_by: string;
}

interface Permission {
  id: string;
  resource: string;
  action: string;
  conditions?: PermissionCondition[];
  effect: 'allow' | 'deny';
  scope?: 'organization' | 'team' | 'user' | 'global';
  description?: string;
}

interface PermissionCondition {
  field: string;
  operator: 'eq' | 'neq' | 'gt' | 'gte' | 'lt' | 'lte' | 'in' | 'nin' | 'contains' | 'regex';
  value: any;
  combine?: 'and' | 'or';
}

interface RoleConstraints {
  max_users?: number;
  time_restriction?: {
    start_time?: string; // HH:MM format
    end_time?: string;
    days?: number[]; // 0-6, Sunday-Saturday
    timezone?: string;
  };
  ip_restriction?: {
    allowed_ips?: string[];
    denied_ips?: string[];
  };
  resource_limits?: {
    [resource: string]: number;
  };
  require_mfa?: boolean;
  session_duration?: number; // minutes
}

interface RoleAssignment {
  id: string;
  role_id: string;
  principal_type: 'user' | 'team' | 'service';
  principal_id: string;
  organization_id: string;
  scope?: {
    type: 'organization' | 'team' | 'project' | 'resource';
    id: string;
  };
  conditions?: AssignmentCondition[];
  expires_at?: Date;
  assigned_by: string;
  assigned_at: Date;
}

interface AssignmentCondition {
  type: 'time' | 'location' | 'device' | 'custom';
  parameters: Record<string, any>;
}

interface PolicyDocument {
  version: string;
  statements: PolicyStatement[];
}

interface PolicyStatement {
  sid?: string;
  effect: 'allow' | 'deny';
  principals?: string[];
  actions: string[];
  resources: string[];
  conditions?: Record<string, any>;
}

interface AccessRequest {
  principal: {
    type: 'user' | 'team' | 'service';
    id: string;
    attributes?: Record<string, any>;
  };
  resource: {
    type: string;
    id: string;
    attributes?: Record<string, any>;
  };
  action: string;
  context?: {
    ip?: string;
    time?: Date;
    location?: { country?: string; city?: string };
    device?: { id?: string; type?: string };
    session?: { id?: string; mfa_verified?: boolean };
    [key: string]: any;
  };
}

interface AccessDecision {
  allowed: boolean;
  reason?: string;
  applied_roles?: string[];
  applied_permissions?: string[];
  conditions_met?: boolean;
  audit_trail?: AuditEntry[];
}

interface AuditEntry {
  timestamp: Date;
  action: string;
  result: 'allow' | 'deny';
  role?: string;
  permission?: string;
  condition?: string;
  details?: Record<string, any>;
}

export class RBACService extends EventEmitter {
  private redis: RedisService;
  private multiTenancy: MultiTenancyService;
  private teamManagement: TeamManagementService;
  private roles: Map<string, Role> = new Map();
  private assignments: Map<string, RoleAssignment[]> = new Map();
  private permissionCache: Map<string, { decision: AccessDecision; expires: Date }> = new Map();
  
  constructor() {
    super();
    this.redis = getRedis();
    this.multiTenancy = getMultiTenancyService();
    this.teamManagement = getTeamManagementService();
    this.initializeSystemRoles();
  }
  
  // Role Management
  async createRole(
    organizationId: string,
    data: {
      name: string;
      description?: string;
      permissions: Permission[];
      parent_role_id?: string;
      constraints?: RoleConstraints;
      metadata?: Record<string, any>;
    },
    createdBy: string
  ): Promise<Role> {
    // Check organization limits
    const roleCount = await this.getOrganizationRoleCount(organizationId);
    const limitCheck = await this.multiTenancy.checkLimit(
      organizationId,
      'custom_roles',
      roleCount + 1
    );
    
    if (!limitCheck.allowed) {
      throw new Error(`Custom role limit reached (${limitCheck.limit}). Upgrade your plan.`);
    }
    
    // Validate role name uniqueness
    const existingRole = await this.getRoleByName(organizationId, data.name);
    if (existingRole) {
      throw new Error(`Role '${data.name}' already exists`);
    }
    
    // Validate parent role
    if (data.parent_role_id) {
      const parentRole = await this.getRole(data.parent_role_id);
      if (!parentRole || parentRole.organization_id !== organizationId) {
        throw new Error('Invalid parent role');
      }
    }
    
    // Validate permissions
    this.validatePermissions(data.permissions);
    
    const role: Role = {
      id: this.generateRoleId(),
      organization_id: organizationId,
      name: data.name,
      description: data.description,
      permissions: data.permissions,
      parent_role_id: data.parent_role_id,
      is_system: false,
      is_default: false,
      priority: await this.getNextPriority(organizationId),
      constraints: data.constraints,
      metadata: data.metadata,
      created_at: new Date(),
      updated_at: new Date(),
      created_by: createdBy
    };
    
    // Store role
    await this.storeRole(role);
    
    // Track usage
    await this.multiTenancy.trackUsage(organizationId, 'custom_roles', 1);
    
    // Emit event
    this.emit('role_created', {
      role_id: role.id,
      organization_id: organizationId,
      created_by: createdBy,
      timestamp: new Date()
    });
    
    return role;
  }
  
  async updateRole(
    roleId: string,
    updates: Partial<Omit<Role, 'id' | 'organization_id' | 'is_system' | 'created_at' | 'created_by'>>,
    updatedBy: string
  ): Promise<Role> {
    const role = await this.getRole(roleId);
    if (!role) {
      throw new Error(`Role '${roleId}' not found`);
    }
    
    if (role.is_system) {
      throw new Error('Cannot modify system roles');
    }
    
    // Validate permissions if updated
    if (updates.permissions) {
      this.validatePermissions(updates.permissions);
    }
    
    // Update role
    const updatedRole: Role = {
      ...role,
      ...updates,
      updated_at: new Date()
    };
    
    await this.storeRole(updatedRole);
    
    // Clear permission cache for affected users
    await this.clearRolePermissionCache(roleId);
    
    // Emit event
    this.emit('role_updated', {
      role_id: roleId,
      changes: updates,
      updated_by: updatedBy,
      timestamp: new Date()
    });
    
    return updatedRole;
  }
  
  async deleteRole(roleId: string, deletedBy: string): Promise<void> {
    const role = await this.getRole(roleId);
    if (!role) {
      throw new Error(`Role '${roleId}' not found`);
    }
    
    if (role.is_system) {
      throw new Error('Cannot delete system roles');
    }
    
    if (role.is_default) {
      throw new Error('Cannot delete default role');
    }
    
    // Check if role has assignments
    const assignments = await this.getRoleAssignments(roleId);
    if (assignments.length > 0) {
      throw new Error('Cannot delete role with active assignments');
    }
    
    // Delete role
    await this.redis.hdel('roles', roleId);
    this.roles.delete(roleId);
    
    // Clear caches
    await this.clearRolePermissionCache(roleId);
    
    // Emit event
    this.emit('role_deleted', {
      role_id: roleId,
      deleted_by: deletedBy,
      timestamp: new Date()
    });
  }
  
  async getRole(roleId: string): Promise<Role | null> {
    if (this.roles.has(roleId)) {
      return this.roles.get(roleId)!;
    }
    
    const role = await this.redis.hget<Role>('roles', roleId);
    if (role) {
      this.roles.set(roleId, role);
      return role;
    }
    
    return null;
  }
  
  async getRoleByName(organizationId: string, name: string): Promise<Role | null> {
    const roles = await this.getOrganizationRoles(organizationId);
    return roles.find(r => r.name === name) || null;
  }
  
  async getOrganizationRoles(organizationId: string): Promise<Role[]> {
    const allRoles = await this.redis.hgetall<Role>('roles');
    return Object.values(allRoles)
      .filter(r => r.organization_id === organizationId)
      .sort((a, b) => a.priority - b.priority);
  }
  
  // Role Assignment
  async assignRole(
    roleId: string,
    principal: { type: 'user' | 'team' | 'service'; id: string },
    scope: { type: 'organization' | 'team' | 'project' | 'resource'; id: string },
    options: {
      conditions?: AssignmentCondition[];
      expires_at?: Date;
    },
    assignedBy: string
  ): Promise<RoleAssignment> {
    const role = await this.getRole(roleId);
    if (!role) {
      throw new Error(`Role '${roleId}' not found`);
    }
    
    // Check for existing assignment
    const existingAssignment = await this.getPrincipalRoleAssignment(
      principal.type,
      principal.id,
      roleId,
      scope
    );
    if (existingAssignment) {
      throw new Error('Role already assigned to this principal in this scope');
    }
    
    const assignment: RoleAssignment = {
      id: this.generateAssignmentId(),
      role_id: roleId,
      principal_type: principal.type,
      principal_id: principal.id,
      organization_id: role.organization_id,
      scope,
      conditions: options.conditions,
      expires_at: options.expires_at,
      assigned_by: assignedBy,
      assigned_at: new Date()
    };
    
    await this.storeAssignment(assignment);
    
    // Clear permission cache
    await this.clearPrincipalPermissionCache(principal.type, principal.id);
    
    // Emit event
    this.emit('role_assigned', {
      assignment_id: assignment.id,
      role_id: roleId,
      principal,
      scope,
      assigned_by: assignedBy,
      timestamp: new Date()
    });
    
    return assignment;
  }
  
  async revokeRole(
    assignmentId: string,
    revokedBy: string
  ): Promise<void> {
    const assignment = await this.getAssignment(assignmentId);
    if (!assignment) {
      throw new Error(`Assignment '${assignmentId}' not found`);
    }
    
    // Remove assignment
    await this.redis.hdel('role_assignments', assignmentId);
    
    // Update cache
    const principalKey = `${assignment.principal_type}:${assignment.principal_id}`;
    const principalAssignments = this.assignments.get(principalKey);
    if (principalAssignments) {
      const index = principalAssignments.findIndex(a => a.id === assignmentId);
      if (index !== -1) {
        principalAssignments.splice(index, 1);
      }
    }
    
    // Clear permission cache
    await this.clearPrincipalPermissionCache(
      assignment.principal_type,
      assignment.principal_id
    );
    
    // Emit event
    this.emit('role_revoked', {
      assignment_id: assignmentId,
      role_id: assignment.role_id,
      principal: {
        type: assignment.principal_type,
        id: assignment.principal_id
      },
      revoked_by: revokedBy,
      timestamp: new Date()
    });
  }
  
  async getPrincipalRoles(
    principalType: 'user' | 'team' | 'service',
    principalId: string
  ): Promise<Role[]> {
    const assignments = await this.getPrincipalAssignments(principalType, principalId);
    const roles: Role[] = [];
    
    for (const assignment of assignments) {
      // Check expiration
      if (assignment.expires_at && new Date() > new Date(assignment.expires_at)) {
        continue;
      }
      
      const role = await this.getRole(assignment.role_id);
      if (role) {
        roles.push(role);
      }
    }
    
    return roles;
  }
  
  // Permission Checking
  async checkAccess(request: AccessRequest): Promise<AccessDecision> {
    // Check cache first
    const cacheKey = this.getAccessCacheKey(request);
    const cached = this.permissionCache.get(cacheKey);
    if (cached && new Date() < cached.expires) {
      return cached.decision;
    }
    
    const audit: AuditEntry[] = [];
    const appliedRoles: string[] = [];
    const appliedPermissions: string[] = [];
    
    // Get principal's roles
    const roles = await this.getPrincipalRoles(request.principal.type, request.principal.id);
    
    // Add team roles if principal is a user
    if (request.principal.type === 'user') {
      const userTeams = await this.teamManagement.getUserTeams(request.principal.id);
      for (const team of userTeams) {
        const teamRoles = await this.getPrincipalRoles('team', team.id);
        roles.push(...teamRoles);
      }
    }
    
    // Sort roles by priority
    roles.sort((a, b) => a.priority - b.priority);
    
    let allowed = false;
    let deniedByPolicy = false;
    let conditionsMet = true;
    
    // Evaluate each role
    for (const role of roles) {
      appliedRoles.push(role.id);
      
      // Check role constraints
      if (role.constraints) {
        const constraintCheck = await this.evaluateRoleConstraints(
          role.constraints,
          request.context
        );
        if (!constraintCheck) {
          audit.push({
            timestamp: new Date(),
            action: request.action,
            result: 'deny',
            role: role.id,
            condition: 'role_constraints',
            details: { constraints: role.constraints }
          });
          continue;
        }
      }
      
      // Evaluate permissions
      for (const permission of role.permissions) {
        if (!this.matchesResource(permission.resource, request.resource.type)) {
          continue;
        }
        
        if (!this.matchesAction(permission.action, request.action)) {
          continue;
        }
        
        appliedPermissions.push(permission.id);
        
        // Evaluate conditions
        if (permission.conditions) {
          const conditionResult = await this.evaluatePermissionConditions(
            permission.conditions,
            request
          );
          if (!conditionResult) {
            conditionsMet = false;
            audit.push({
              timestamp: new Date(),
              action: request.action,
              result: 'deny',
              role: role.id,
              permission: permission.id,
              condition: 'permission_conditions',
              details: { conditions: permission.conditions }
            });
            continue;
          }
        }
        
        // Apply effect
        if (permission.effect === 'deny') {
          deniedByPolicy = true;
          audit.push({
            timestamp: new Date(),
            action: request.action,
            result: 'deny',
            role: role.id,
            permission: permission.id,
            details: { effect: 'explicit_deny' }
          });
          break;
        } else {
          allowed = true;
          audit.push({
            timestamp: new Date(),
            action: request.action,
            result: 'allow',
            role: role.id,
            permission: permission.id,
            details: { effect: 'allow' }
          });
        }
      }
      
      if (deniedByPolicy) {
        break;
      }
    }
    
    // Final decision
    const decision: AccessDecision = {
      allowed: allowed && !deniedByPolicy,
      reason: deniedByPolicy ? 'Explicitly denied by policy' :
              !allowed ? 'No matching allow permission' :
              !conditionsMet ? 'Conditions not met' : 'Allowed',
      applied_roles: appliedRoles,
      applied_permissions: appliedPermissions,
      conditions_met: conditionsMet,
      audit_trail: audit
    };
    
    // Cache decision
    this.permissionCache.set(cacheKey, {
      decision,
      expires: new Date(Date.now() + 300000) // 5 minutes
    });
    
    // Emit event for audit
    this.emit('access_checked', {
      request,
      decision,
      timestamp: new Date()
    });
    
    return decision;
  }
  
  async getUserPermissions(
    userId: string,
    organizationId: string
  ): Promise<Permission[]> {
    const roles = await this.getPrincipalRoles('user', userId);
    const permissions: Permission[] = [];
    const seen = new Set<string>();
    
    for (const role of roles) {
      if (role.organization_id !== organizationId) {
        continue;
      }
      
      for (const permission of role.permissions) {
        const key = `${permission.resource}:${permission.action}`;
        if (!seen.has(key)) {
          permissions.push(permission);
          seen.add(key);
        }
      }
    }
    
    return permissions;
  }
  
  // Resource-Based Access Control
  async grantResourceAccess(
    resourceType: string,
    resourceId: string,
    principal: { type: 'user' | 'team' | 'service'; id: string },
    permissions: string[],
    grantedBy: string
  ): Promise<void> {
    const key = `resource:${resourceType}:${resourceId}:access`;
    const grant = {
      principal_type: principal.type,
      principal_id: principal.id,
      permissions,
      granted_by: grantedBy,
      granted_at: new Date()
    };
    
    await this.redis.hset(key, `${principal.type}:${principal.id}`, grant);
    
    // Clear cache
    await this.clearPrincipalPermissionCache(principal.type, principal.id);
    
    // Emit event
    this.emit('resource_access_granted', {
      resource_type: resourceType,
      resource_id: resourceId,
      principal,
      permissions,
      granted_by: grantedBy,
      timestamp: new Date()
    });
  }
  
  async revokeResourceAccess(
    resourceType: string,
    resourceId: string,
    principal: { type: 'user' | 'team' | 'service'; id: string },
    revokedBy: string
  ): Promise<void> {
    const key = `resource:${resourceType}:${resourceId}:access`;
    await this.redis.hdel(key, `${principal.type}:${principal.id}`);
    
    // Clear cache
    await this.clearPrincipalPermissionCache(principal.type, principal.id);
    
    // Emit event
    this.emit('resource_access_revoked', {
      resource_type: resourceType,
      resource_id: resourceId,
      principal,
      revoked_by: revokedBy,
      timestamp: new Date()
    });
  }
  
  async getResourceAccessList(
    resourceType: string,
    resourceId: string
  ): Promise<Array<{
    principal_type: string;
    principal_id: string;
    permissions: string[];
    granted_by: string;
    granted_at: Date;
  }>> {
    const key = `resource:${resourceType}:${resourceId}:access`;
    const grants = await this.redis.hgetall(key);
    return Object.values(grants);
  }
  
  // Policy Management
  async createPolicy(
    organizationId: string,
    name: string,
    document: PolicyDocument,
    createdBy: string
  ): Promise<{ id: string; policy: PolicyDocument }> {
    const policyId = this.generatePolicyId();
    const key = `policy:${organizationId}:${policyId}`;
    
    await this.redis.set(key, {
      id: policyId,
      name,
      document,
      created_by: createdBy,
      created_at: new Date(),
      updated_at: new Date()
    });
    
    return { id: policyId, policy: document };
  }
  
  async attachPolicy(
    policyId: string,
    target: { type: 'role' | 'user' | 'team'; id: string },
    attachedBy: string
  ): Promise<void> {
    const key = `policy:attachment:${target.type}:${target.id}`;
    await this.redis.sadd(key, policyId);
    
    // Clear cache
    if (target.type === 'role') {
      await this.clearRolePermissionCache(target.id);
    } else {
      await this.clearPrincipalPermissionCache(target.type as any, target.id);
    }
    
    // Emit event
    this.emit('policy_attached', {
      policy_id: policyId,
      target,
      attached_by: attachedBy,
      timestamp: new Date()
    });
  }
  
  // Helper Methods
  private validatePermissions(permissions: Permission[]): void {
    for (const permission of permissions) {
      if (!permission.resource || !permission.action) {
        throw new Error('Permission must have resource and action');
      }
      
      if (!['allow', 'deny'].includes(permission.effect)) {
        throw new Error('Permission effect must be allow or deny');
      }
      
      if (permission.conditions) {
        for (const condition of permission.conditions) {
          if (!condition.field || !condition.operator || condition.value === undefined) {
            throw new Error('Invalid permission condition');
          }
        }
      }
    }
  }
  
  private async evaluateRoleConstraints(
    constraints: RoleConstraints,
    context?: Record<string, any>
  ): Promise<boolean> {
    if (!context) return true;
    
    // Check time restriction
    if (constraints.time_restriction) {
      const now = new Date();
      const currentDay = now.getDay();
      
      if (constraints.time_restriction.days &&
          !constraints.time_restriction.days.includes(currentDay)) {
        return false;
      }
      
      if (constraints.time_restriction.start_time || constraints.time_restriction.end_time) {
        const currentTime = now.getHours() * 60 + now.getMinutes();
        
        if (constraints.time_restriction.start_time) {
          const [startHour, startMin] = constraints.time_restriction.start_time.split(':').map(Number);
          const startTime = startHour * 60 + startMin;
          if (currentTime < startTime) return false;
        }
        
        if (constraints.time_restriction.end_time) {
          const [endHour, endMin] = constraints.time_restriction.end_time.split(':').map(Number);
          const endTime = endHour * 60 + endMin;
          if (currentTime > endTime) return false;
        }
      }
    }
    
    // Check IP restriction
    if (constraints.ip_restriction && context.ip) {
      if (constraints.ip_restriction.denied_ips?.includes(context.ip)) {
        return false;
      }
      
      if (constraints.ip_restriction.allowed_ips &&
          !constraints.ip_restriction.allowed_ips.includes(context.ip)) {
        return false;
      }
    }
    
    // Check MFA requirement
    if (constraints.require_mfa && context.session) {
      if (!context.session.mfa_verified) {
        return false;
      }
    }
    
    return true;
  }
  
  private async evaluatePermissionConditions(
    conditions: PermissionCondition[],
    request: AccessRequest
  ): Promise<boolean> {
    let result = true;
    let combineWithOr = false;
    
    for (const condition of conditions) {
      const conditionResult = await this.evaluateCondition(condition, request);
      
      if (condition.combine === 'or') {
        result = result || conditionResult;
        combineWithOr = true;
      } else {
        result = combineWithOr ? conditionResult : result && conditionResult;
        combineWithOr = false;
      }
    }
    
    return result;
  }
  
  private async evaluateCondition(
    condition: PermissionCondition,
    request: AccessRequest
  ): Promise<boolean> {
    const value = this.getFieldValue(condition.field, request);
    
    switch (condition.operator) {
      case 'eq':
        return value === condition.value;
      case 'neq':
        return value !== condition.value;
      case 'gt':
        return value > condition.value;
      case 'gte':
        return value >= condition.value;
      case 'lt':
        return value < condition.value;
      case 'lte':
        return value <= condition.value;
      case 'in':
        return Array.isArray(condition.value) && condition.value.includes(value);
      case 'nin':
        return Array.isArray(condition.value) && !condition.value.includes(value);
      case 'contains':
        return String(value).includes(String(condition.value));
      case 'regex':
        return new RegExp(condition.value).test(String(value));
      default:
        return false;
    }
  }
  
  private getFieldValue(field: string, request: AccessRequest): any {
    const parts = field.split('.');
    let value: any = request;
    
    for (const part of parts) {
      value = value?.[part];
      if (value === undefined) break;
    }
    
    return value;
  }
  
  private matchesResource(pattern: string, resource: string): boolean {
    if (pattern === '*') return true;
    if (pattern === resource) return true;
    
    // Support wildcards
    const regex = new RegExp('^' + pattern.replace(/\*/g, '.*') + '$');
    return regex.test(resource);
  }
  
  private matchesAction(pattern: string, action: string): boolean {
    if (pattern === '*') return true;
    if (pattern === action) return true;
    
    // Support wildcards
    const regex = new RegExp('^' + pattern.replace(/\*/g, '.*') + '$');
    return regex.test(action);
  }
  
  private async initializeSystemRoles(): Promise<void> {
    // Initialize default system roles
    const systemRoles: Role[] = [
      {
        id: 'system_admin',
        organization_id: 'system',
        name: 'System Admin',
        description: 'Full system access',
        permissions: [{
          id: 'admin_all',
          resource: '*',
          action: '*',
          effect: 'allow',
          scope: 'global'
        }],
        is_system: true,
        is_default: false,
        priority: 0,
        created_at: new Date(),
        updated_at: new Date(),
        created_by: 'system'
      },
      {
        id: 'org_owner',
        organization_id: 'system',
        name: 'Organization Owner',
        description: 'Full organization access',
        permissions: [{
          id: 'org_all',
          resource: 'organization:*',
          action: '*',
          effect: 'allow',
          scope: 'organization'
        }],
        is_system: true,
        is_default: false,
        priority: 10,
        created_at: new Date(),
        updated_at: new Date(),
        created_by: 'system'
      },
      {
        id: 'org_member',
        organization_id: 'system',
        name: 'Organization Member',
        description: 'Basic organization access',
        permissions: [
          {
            id: 'org_read',
            resource: 'organization:*',
            action: 'read',
            effect: 'allow',
            scope: 'organization'
          },
          {
            id: 'team_manage',
            resource: 'team:*',
            action: '*',
            effect: 'allow',
            scope: 'team'
          }
        ],
        is_system: true,
        is_default: true,
        priority: 50,
        created_at: new Date(),
        updated_at: new Date(),
        created_by: 'system'
      }
    ];
    
    for (const role of systemRoles) {
      await this.storeRole(role);
    }
  }
  
  private async storeRole(role: Role): Promise<void> {
    await this.redis.hset('roles', role.id, role);
    this.roles.set(role.id, role);
  }
  
  private async storeAssignment(assignment: RoleAssignment): Promise<void> {
    await this.redis.hset('role_assignments', assignment.id, assignment);
    
    const principalKey = `${assignment.principal_type}:${assignment.principal_id}`;
    if (!this.assignments.has(principalKey)) {
      this.assignments.set(principalKey, []);
    }
    this.assignments.get(principalKey)!.push(assignment);
  }
  
  private async getAssignment(assignmentId: string): Promise<RoleAssignment | null> {
    return await this.redis.hget<RoleAssignment>('role_assignments', assignmentId);
  }
  
  private async getPrincipalAssignments(
    principalType: string,
    principalId: string
  ): Promise<RoleAssignment[]> {
    const principalKey = `${principalType}:${principalId}`;
    
    if (this.assignments.has(principalKey)) {
      return this.assignments.get(principalKey)!;
    }
    
    const allAssignments = await this.redis.hgetall<RoleAssignment>('role_assignments');
    const principalAssignments = Object.values(allAssignments).filter(
      a => a.principal_type === principalType && a.principal_id === principalId
    );
    
    this.assignments.set(principalKey, principalAssignments);
    return principalAssignments;
  }
  
  private async getRoleAssignments(roleId: string): Promise<RoleAssignment[]> {
    const allAssignments = await this.redis.hgetall<RoleAssignment>('role_assignments');
    return Object.values(allAssignments).filter(a => a.role_id === roleId);
  }
  
  private async getPrincipalRoleAssignment(
    principalType: string,
    principalId: string,
    roleId: string,
    scope: { type: string; id: string }
  ): Promise<RoleAssignment | null> {
    const assignments = await this.getPrincipalAssignments(principalType, principalId);
    return assignments.find(
      a => a.role_id === roleId &&
           a.scope?.type === scope.type &&
           a.scope?.id === scope.id
    ) || null;
  }
  
  private async getOrganizationRoleCount(organizationId: string): Promise<number> {
    const roles = await this.getOrganizationRoles(organizationId);
    return roles.filter(r => !r.is_system).length;
  }
  
  private async getNextPriority(organizationId: string): Promise<number> {
    const roles = await this.getOrganizationRoles(organizationId);
    const maxPriority = Math.max(...roles.map(r => r.priority), 100);
    return maxPriority + 10;
  }
  
  private getAccessCacheKey(request: AccessRequest): string {
    return `${request.principal.type}:${request.principal.id}:${request.resource.type}:${request.resource.id}:${request.action}`;
  }
  
  private async clearRolePermissionCache(roleId: string): Promise<void> {
    // Clear cache for all principals with this role
    const assignments = await this.getRoleAssignments(roleId);
    for (const assignment of assignments) {
      await this.clearPrincipalPermissionCache(
        assignment.principal_type,
        assignment.principal_id
      );
    }
  }
  
  private async clearPrincipalPermissionCache(
    principalType: string,
    principalId: string
  ): Promise<void> {
    // Clear from memory cache
    const keysToDelete: string[] = [];
    for (const key of this.permissionCache.keys()) {
      if (key.startsWith(`${principalType}:${principalId}:`)) {
        keysToDelete.push(key);
      }
    }
    keysToDelete.forEach(key => this.permissionCache.delete(key));
  }
  
  private generateRoleId(): string {
    return `role_${Date.now()}_${Math.random().toString(36).substring(2, 9)}`;
  }
  
  private generateAssignmentId(): string {
    return `assign_${Date.now()}_${Math.random().toString(36).substring(2, 9)}`;
  }
  
  private generatePolicyId(): string {
    return `policy_${Date.now()}_${Math.random().toString(36).substring(2, 9)}`;
  }
}

// Export singleton instance
let rbacService: RBACService | null = null;

export function getRBACService(): RBACService {
  if (!rbacService) {
    rbacService = new RBACService();
  }
  return rbacService;
}