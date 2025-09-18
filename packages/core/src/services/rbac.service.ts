/**
 * Role-Based Access Control (RBAC) Service
 * Basic permission system for MVP with extensibility for enterprise features
 */

import { EventEmitter } from 'events';
import { logger } from '../utils/logger';

export interface Permission {
  id: string;
  name: string;
  resource: string;
  action: string;
  conditions?: Record<string, any>;
}

export interface Role {
  id: string;
  name: string;
  description: string;
  permissions: Permission[];
  isSystem: boolean; // System roles cannot be modified
  priority: number; // For role hierarchy
}

export interface Policy {
  id: string;
  name: string;
  effect: 'allow' | 'deny';
  resources: string[];
  actions: string[];
  conditions?: PolicyCondition[];
}

export interface PolicyCondition {
  type: 'ip' | 'time' | 'mfa' | 'location' | 'custom';
  operator: 'equals' | 'not_equals' | 'in' | 'not_in' | 'contains' | 'greater_than' | 'less_than';
  value: any;
}

export interface PermissionCheck {
  userId: string;
  resource: string;
  action: string;
  context?: Record<string, any>;
}

export class RBACService extends EventEmitter {
  private roles: Map<string, Role> = new Map();
  private userRoles: Map<string, Set<string>> = new Map();
  private policies: Map<string, Policy> = new Map();
  private redisService: any;

  // Default system roles
  private readonly systemRoles: Role[] = [
    {
      id: 'superadmin',
      name: 'Super Admin',
      description: 'Full system access',
      permissions: [{ id: '*', name: 'All', resource: '*', action: '*' }],
      isSystem: true,
      priority: 100,
    },
    {
      id: 'org_owner',
      name: 'Organization Owner',
      description: 'Full organization access',
      permissions: [
        { id: 'org_all', name: 'All Organization', resource: 'organization:*', action: '*' },
        { id: 'member_all', name: 'All Members', resource: 'member:*', action: '*' },
        { id: 'billing_all', name: 'All Billing', resource: 'billing:*', action: '*' },
      ],
      isSystem: true,
      priority: 90,
    },
    {
      id: 'org_admin',
      name: 'Organization Admin',
      description: 'Organization administration',
      permissions: [
        { id: 'org_read', name: 'Read Organization', resource: 'organization:*', action: 'read' },
        { id: 'org_update', name: 'Update Organization', resource: 'organization:*', action: 'update' },
        { id: 'member_manage', name: 'Manage Members', resource: 'member:*', action: '*' },
        { id: 'settings_manage', name: 'Manage Settings', resource: 'settings:*', action: '*' },
      ],
      isSystem: true,
      priority: 80,
    },
    {
      id: 'org_member',
      name: 'Organization Member',
      description: 'Basic member access',
      permissions: [
        { id: 'org_read', name: 'Read Organization', resource: 'organization:*', action: 'read' },
        { id: 'profile_manage', name: 'Manage Own Profile', resource: 'profile:self', action: '*' },
        { id: 'project_create', name: 'Create Projects', resource: 'project:*', action: 'create' },
        { id: 'project_read', name: 'Read Projects', resource: 'project:*', action: 'read' },
      ],
      isSystem: true,
      priority: 50,
    },
    {
      id: 'org_viewer',
      name: 'Organization Viewer',
      description: 'Read-only access',
      permissions: [
        { id: 'org_read', name: 'Read Organization', resource: 'organization:*', action: 'read' },
        { id: 'project_read', name: 'Read Projects', resource: 'project:*', action: 'read' },
        { id: 'member_read', name: 'Read Members', resource: 'member:*', action: 'read' },
      ],
      isSystem: true,
      priority: 20,
    },
  ];

  constructor(redisService?: any) {
    super();
    this.redisService = redisService;
    this.initializeSystemRoles();
  }

  /**
   * Initialize system roles
   */
  private initializeSystemRoles(): void {
    for (const role of this.systemRoles) {
      this.roles.set(role.id, role);
    }
    logger.info('RBAC system roles initialized', {
      count: this.systemRoles.length,
    });
  }

  /**
   * Check if user has permission
   */
  async hasPermission(check: PermissionCheck): Promise<boolean> {
    try {
      // Get user roles
      const userRoleIds = await this.getUserRoles(check.userId);
      
      if (userRoleIds.size === 0) {
        return false;
      }

      // Check each role for permission
      for (const roleId of userRoleIds) {
        const role = this.roles.get(roleId);
        if (!role) continue;

        // Check role permissions
        if (this.roleHasPermission(role, check.resource, check.action)) {
          // Check if there are any deny policies
          const denied = await this.checkDenyPolicies(check);
          if (!denied) {
            // Check conditions if context provided
            if (check.context) {
              const conditionsMet = await this.evaluateConditions(role, check.context);
              if (conditionsMet) {
                this.emit('permission:granted', {
                  ...check,
                  roleId,
                });
                return true;
              }
            } else {
              this.emit('permission:granted', {
                ...check,
                roleId,
              });
              return true;
            }
          }
        }
      }

      this.emit('permission:denied', check);
      return false;
    } catch (error) {
      logger.error('Error checking permission', error as Error, { check });
      return false;
    }
  }

  /**
   * Check if role has specific permission
   */
  private roleHasPermission(role: Role, resource: string, action: string): boolean {
    for (const permission of role.permissions) {
      // Check for wildcard permissions
      if (permission.resource === '*' && permission.action === '*') {
        return true;
      }

      // Check resource match
      if (this.matchResource(permission.resource, resource)) {
        // Check action match
        if (permission.action === '*' || permission.action === action) {
          return true;
        }
      }
    }

    return false;
  }

  /**
   * Match resource pattern
   */
  private matchResource(pattern: string, resource: string): boolean {
    if (pattern === resource) {
      return true;
    }

    // Handle wildcards
    if (pattern.endsWith(':*')) {
      const prefix = pattern.slice(0, -2);
      return resource.startsWith(prefix + ':');
    }

    // Handle self reference
    if (pattern.includes(':self')) {
      // This would need actual implementation based on context
      return true; // Simplified for MVP
    }

    return false;
  }

  /**
   * Assign role to user
   */
  async assignRole(userId: string, roleId: string): Promise<void> {
    if (!this.roles.has(roleId)) {
      throw new Error(`Role ${roleId} does not exist`);
    }

    if (!this.userRoles.has(userId)) {
      this.userRoles.set(userId, new Set());
    }

    this.userRoles.get(userId)!.add(roleId);

    // Store in Redis for persistence
    if (this.redisService) {
      const roles = Array.from(this.userRoles.get(userId)!);
      await this.redisService.set(
        `user:${userId}:roles`,
        JSON.stringify(roles)
      );
    }

    this.emit('role:assigned', { userId, roleId });
    
    logger.info('Role assigned to user', {
      userId,
      roleId,
    });
  }

  /**
   * Remove role from user
   */
  async removeRole(userId: string, roleId: string): Promise<void> {
    const userRoles = this.userRoles.get(userId);
    if (userRoles) {
      userRoles.delete(roleId);

      // Update Redis
      if (this.redisService) {
        const roles = Array.from(userRoles);
        await this.redisService.set(
          `user:${userId}:roles`,
          JSON.stringify(roles)
        );
      }
    }

    this.emit('role:removed', { userId, roleId });

    logger.info('Role removed from user', {
      userId,
      roleId,
    });
  }

  /**
   * Get user roles
   */
  async getUserRoles(userId: string): Promise<Set<string>> {
    // Check cache first
    if (this.userRoles.has(userId)) {
      return this.userRoles.get(userId)!;
    }

    // Load from Redis
    if (this.redisService) {
      const rolesJson = await this.redisService.get(`user:${userId}:roles`);
      if (rolesJson) {
        const roles = JSON.parse(rolesJson) as string[];
        const roleSet = new Set(roles);
        this.userRoles.set(userId, roleSet);
        return roleSet;
      }
    }

    return new Set();
  }

  /**
   * Create custom role
   */
  async createRole(role: Omit<Role, 'isSystem'>): Promise<Role> {
    if (this.roles.has(role.id)) {
      throw new Error(`Role ${role.id} already exists`);
    }

    const newRole: Role = {
      ...role,
      isSystem: false,
    };

    this.roles.set(role.id, newRole);

    // Store in Redis
    if (this.redisService) {
      await this.redisService.set(
        `role:${role.id}`,
        JSON.stringify(newRole)
      );
    }

    this.emit('role:created', newRole);

    logger.info('Custom role created', {
      roleId: role.id,
      name: role.name,
    });

    return newRole;
  }

  /**
   * Update custom role
   */
  async updateRole(roleId: string, updates: Partial<Role>): Promise<Role> {
    const role = this.roles.get(roleId);
    
    if (!role) {
      throw new Error(`Role ${roleId} not found`);
    }

    if (role.isSystem) {
      throw new Error('Cannot modify system roles');
    }

    const updatedRole = {
      ...role,
      ...updates,
      id: role.id, // Prevent ID change
      isSystem: false, // Ensure it remains non-system
    };

    this.roles.set(roleId, updatedRole);

    // Update Redis
    if (this.redisService) {
      await this.redisService.set(
        `role:${roleId}`,
        JSON.stringify(updatedRole)
      );
    }

    this.emit('role:updated', updatedRole);

    logger.info('Role updated', {
      roleId,
      updates: Object.keys(updates),
    });

    return updatedRole;
  }

  /**
   * Create policy
   */
  async createPolicy(policy: Policy): Promise<Policy> {
    if (this.policies.has(policy.id)) {
      throw new Error(`Policy ${policy.id} already exists`);
    }

    this.policies.set(policy.id, policy);

    // Store in Redis
    if (this.redisService) {
      await this.redisService.set(
        `policy:${policy.id}`,
        JSON.stringify(policy)
      );
    }

    this.emit('policy:created', policy);

    logger.info('Policy created', {
      policyId: policy.id,
      name: policy.name,
      effect: policy.effect,
    });

    return policy;
  }

  /**
   * Check deny policies
   */
  private async checkDenyPolicies(check: PermissionCheck): Promise<boolean> {
    for (const [_, policy] of this.policies) {
      if (policy.effect !== 'deny') continue;

      // Check if policy applies to this resource and action
      const resourceMatch = policy.resources.some(r => 
        this.matchResource(r, check.resource)
      );
      const actionMatch = policy.actions.includes('*') || 
        policy.actions.includes(check.action);

      if (resourceMatch && actionMatch) {
        // Evaluate conditions if present
        if (policy.conditions && check.context) {
          const conditionsMet = this.evaluatePolicyConditions(
            policy.conditions,
            check.context
          );
          if (conditionsMet) {
            return true; // Deny applies
          }
        } else if (!policy.conditions) {
          return true; // Unconditional deny
        }
      }
    }

    return false;
  }

  /**
   * Evaluate policy conditions
   */
  private evaluatePolicyConditions(
    conditions: PolicyCondition[],
    context: Record<string, any>
  ): boolean {
    for (const condition of conditions) {
      const contextValue = context[condition.type];
      
      if (!contextValue) {
        return false;
      }

      switch (condition.operator) {
        case 'equals':
          if (contextValue !== condition.value) return false;
          break;
        case 'not_equals':
          if (contextValue === condition.value) return false;
          break;
        case 'in':
          if (!condition.value.includes(contextValue)) return false;
          break;
        case 'not_in':
          if (condition.value.includes(contextValue)) return false;
          break;
        case 'contains':
          if (!contextValue.includes(condition.value)) return false;
          break;
        case 'greater_than':
          if (contextValue <= condition.value) return false;
          break;
        case 'less_than':
          if (contextValue >= condition.value) return false;
          break;
      }
    }

    return true;
  }

  /**
   * Evaluate role conditions
   */
  private async evaluateConditions(
    role: Role,
    context: Record<string, any>
  ): Promise<boolean> {
    // Basic implementation for MVP
    // Can be extended for more complex conditions
    
    // Example: Check MFA requirement for admin roles
    if (role.priority >= 80 && !context.mfa) {
      return false;
    }

    return true;
  }

  /**
   * Get all roles
   */
  getAllRoles(): Role[] {
    return Array.from(this.roles.values());
  }

  /**
   * Get all policies
   */
  getAllPolicies(): Policy[] {
    return Array.from(this.policies.values());
  }
}