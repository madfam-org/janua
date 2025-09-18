/**
 * Organization Members Management Service
 * Manages organization membership, roles, permissions, and team structures
 */

import { EventEmitter } from 'events';
import crypto from 'crypto';

export interface OrganizationMember {
  id: string;
  organization_id: string;
  user_id: string;
  email: string;
  name?: string;
  role: string;
  permissions: string[];
  teams: string[];
  status: 'active' | 'inactive' | 'suspended' | 'pending';
  joined_at: Date;
  invited_at?: Date;
  last_active_at?: Date;
  suspended_at?: Date;
  suspended_by?: string;
  suspension_reason?: string;
  metadata?: Record<string, any>;
  custom_attributes?: Record<string, any>;
  access_level?: 'owner' | 'admin' | 'member' | 'guest';
}

export interface Team {
  id: string;
  organization_id: string;
  name: string;
  description?: string;
  parent_team_id?: string;
  lead_user_id?: string;
  member_count: number;
  permissions: string[];
  metadata?: Record<string, any>;
  created_at: Date;
  updated_at: Date;
}

export interface MemberRole {
  id: string;
  organization_id: string;
  name: string;
  description?: string;
  permissions: string[];
  priority: number; // For role hierarchy
  is_default: boolean;
  is_system: boolean;
  can_be_deleted: boolean;
  created_at: Date;
  updated_at: Date;
}

export interface MembershipChange {
  id: string;
  organization_id: string;
  member_id: string;
  change_type: 'role_change' | 'team_change' | 'permission_change' | 'status_change';
  old_value: any;
  new_value: any;
  changed_by: string;
  reason?: string;
  timestamp: Date;
}

export interface BulkOperationResult {
  successful: string[];
  failed: Array<{ member_id: string; error: string }>;
  total: number;
  success_count: number;
  failure_count: number;
}

export interface OrganizationStats {
  total_members: number;
  active_members: number;
  inactive_members: number;
  suspended_members: number;
  pending_members: number;
  members_by_role: Record<string, number>;
  members_by_team: Record<string, number>;
  growth_rate_30d: number;
  churn_rate_30d: number;
}

export class OrganizationMembersService extends EventEmitter {
  private members: Map<string, OrganizationMember> = new Map();
  private organizationMembers: Map<string, Set<string>> = new Map();
  private userMemberships: Map<string, Set<string>> = new Map();
  private teams: Map<string, Team> = new Map();
  private teamMembers: Map<string, Set<string>> = new Map();
  private roles: Map<string, MemberRole> = new Map();
  private membershipHistory: Map<string, MembershipChange[]> = new Map();

  constructor(
    private readonly config: {
      max_members_per_org?: number;
      max_teams_per_org?: number;
      require_email_verification?: boolean;
      auto_suspend_inactive_days?: number;
      allow_custom_roles?: boolean;
      enforce_role_hierarchy?: boolean;
    } = {}
  ) {
    super();
    this.initializeSystemRoles();
    this.startMaintenanceTimer();
  }

  /**
   * Add a member to an organization
   */
  async addMember(params: {
    organization_id: string;
    user_id: string;
    email: string;
    name?: string;
    role: string;
    permissions?: string[];
    teams?: string[];
    invited_by?: string;
    metadata?: Record<string, any>;
  }): Promise<OrganizationMember> {
    // Check member limit
    const orgMembers = this.organizationMembers.get(params.organization_id) || new Set();
    if (this.config.max_members_per_org && orgMembers.size >= this.config.max_members_per_org) {
      throw new Error(`Organization has reached maximum member limit of ${this.config.max_members_per_org}`);
    }

    // Check if already a member
    const existing = this.findMember(params.organization_id, params.user_id);
    if (existing) {
      throw new Error('User is already a member of this organization');
    }

    // Validate role
    const role = this.getRole(params.role);
    if (!role) {
      throw new Error(`Invalid role: ${params.role}`);
    }

    // Create member
    const member: OrganizationMember = {
      id: crypto.randomUUID(),
      organization_id: params.organization_id,
      user_id: params.user_id,
      email: params.email.toLowerCase(),
      name: params.name,
      role: params.role,
      permissions: params.permissions || role.permissions,
      teams: params.teams || [],
      status: this.config.require_email_verification ? 'pending' : 'active',
      joined_at: new Date(),
      invited_at: params.invited_by ? new Date() : undefined,
      metadata: params.metadata,
      access_level: this.determineAccessLevel(params.role)
    };

    // Store member
    this.storeMember(member);

    // Add to teams
    if (params.teams) {
      for (const teamId of params.teams) {
        await this.addToTeam(member.id, teamId);
      }
    }

    // Record change
    this.recordChange({
      organization_id: params.organization_id,
      member_id: member.id,
      change_type: 'status_change',
      old_value: null,
      new_value: 'active',
      changed_by: params.invited_by || 'system'
    });

    // Emit event
    this.emit('member:added', {
      organization_id: member.organization_id,
      member_id: member.id,
      user_id: member.user_id,
      role: member.role
    });

    return member;
  }

  /**
   * Remove a member from an organization
   */
  async removeMember(
    organization_id: string,
    member_id: string,
    removed_by: string,
    reason?: string
  ): Promise<void> {
    const member = this.getMember(member_id);
    
    if (!member || member.organization_id !== organization_id) {
      throw new Error('Member not found in organization');
    }

    // Check if trying to remove owner
    if (member.access_level === 'owner') {
      const owners = this.getOrganizationMembers(organization_id, { access_level: 'owner' });
      if (owners.length === 1) {
        throw new Error('Cannot remove the last owner of an organization');
      }
    }

    // Remove from teams
    for (const teamId of member.teams) {
      this.removeFromTeam(member.id, teamId);
    }

    // Remove member
    this.members.delete(member.id);

    // Update indexes
    const orgMembers = this.organizationMembers.get(organization_id);
    if (orgMembers) {
      orgMembers.delete(member.id);
    }

    const userMemberships = this.userMemberships.get(member.user_id);
    if (userMemberships) {
      userMemberships.delete(member.id);
    }

    // Record change
    this.recordChange({
      organization_id,
      member_id,
      change_type: 'status_change',
      old_value: member.status,
      new_value: 'removed',
      changed_by: removed_by,
      reason
    });

    // Emit event
    this.emit('member:removed', {
      organization_id,
      member_id,
      user_id: member.user_id,
      removed_by,
      reason
    });
  }

  /**
   * Update member role
   */
  async updateMemberRole(
    member_id: string,
    new_role: string,
    updated_by: string,
    reason?: string
  ): Promise<OrganizationMember> {
    const member = this.getMember(member_id);
    
    if (!member) {
      throw new Error('Member not found');
    }

    // Validate new role
    const role = this.getRole(new_role);
    if (!role) {
      throw new Error(`Invalid role: ${new_role}`);
    }

    // Check role hierarchy
    if (this.config.enforce_role_hierarchy) {
      const updaterMember = this.findMemberByUserId(member.organization_id, updated_by);
      if (updaterMember) {
        const updaterRole = this.getRole(updaterMember.role);
        if (updaterRole && updaterRole.priority < role.priority) {
          throw new Error('Cannot assign a role higher than your own');
        }
      }
    }

    const oldRole = member.role;
    
    // Update member
    member.role = new_role;
    member.permissions = role.permissions;
    member.access_level = this.determineAccessLevel(new_role);

    // Record change
    this.recordChange({
      organization_id: member.organization_id,
      member_id: member.id,
      change_type: 'role_change',
      old_value: oldRole,
      new_value: new_role,
      changed_by: updated_by,
      reason
    });

    // Emit event
    this.emit('member:role-updated', {
      organization_id: member.organization_id,
      member_id: member.id,
      old_role: oldRole,
      new_role: new_role,
      updated_by
    });

    return member;
  }

  /**
   * Update member permissions
   */
  async updateMemberPermissions(
    member_id: string,
    permissions: string[],
    updated_by: string
  ): Promise<OrganizationMember> {
    const member = this.getMember(member_id);
    
    if (!member) {
      throw new Error('Member not found');
    }

    const oldPermissions = [...member.permissions];
    member.permissions = permissions;

    // Record change
    this.recordChange({
      organization_id: member.organization_id,
      member_id: member.id,
      change_type: 'permission_change',
      old_value: oldPermissions,
      new_value: permissions,
      changed_by: updated_by
    });

    // Emit event
    this.emit('member:permissions-updated', {
      organization_id: member.organization_id,
      member_id: member.id,
      permissions,
      updated_by
    });

    return member;
  }

  /**
   * Suspend a member
   */
  async suspendMember(
    member_id: string,
    suspended_by: string,
    reason: string
  ): Promise<void> {
    const member = this.getMember(member_id);
    
    if (!member) {
      throw new Error('Member not found');
    }

    if (member.status === 'suspended') {
      throw new Error('Member is already suspended');
    }

    const oldStatus = member.status;
    
    member.status = 'suspended';
    member.suspended_at = new Date();
    member.suspended_by = suspended_by;
    member.suspension_reason = reason;

    // Record change
    this.recordChange({
      organization_id: member.organization_id,
      member_id: member.id,
      change_type: 'status_change',
      old_value: oldStatus,
      new_value: 'suspended',
      changed_by: suspended_by,
      reason
    });

    // Emit event
    this.emit('member:suspended', {
      organization_id: member.organization_id,
      member_id: member.id,
      suspended_by,
      reason
    });
  }

  /**
   * Unsuspend a member
   */
  async unsuspendMember(
    member_id: string,
    unsuspended_by: string
  ): Promise<void> {
    const member = this.getMember(member_id);
    
    if (!member) {
      throw new Error('Member not found');
    }

    if (member.status !== 'suspended') {
      throw new Error('Member is not suspended');
    }

    member.status = 'active';
    member.suspended_at = undefined;
    member.suspended_by = undefined;
    member.suspension_reason = undefined;

    // Record change
    this.recordChange({
      organization_id: member.organization_id,
      member_id: member.id,
      change_type: 'status_change',
      old_value: 'suspended',
      new_value: 'active',
      changed_by: unsuspended_by
    });

    // Emit event
    this.emit('member:unsuspended', {
      organization_id: member.organization_id,
      member_id: member.id,
      unsuspended_by
    });
  }

  /**
   * Bulk update members
   */
  async bulkUpdateMembers(
    organization_id: string,
    updates: Array<{
      member_id: string;
      role?: string;
      permissions?: string[];
      teams?: string[];
      status?: OrganizationMember['status'];
    }>,
    updated_by: string
  ): Promise<BulkOperationResult> {
    const result: BulkOperationResult = {
      successful: [],
      failed: [],
      total: updates.length,
      success_count: 0,
      failure_count: 0
    };

    for (const update of updates) {
      try {
        const member = this.getMember(update.member_id);
        
        if (!member || member.organization_id !== organization_id) {
          throw new Error('Member not found in organization');
        }

        if (update.role) {
          await this.updateMemberRole(update.member_id, update.role, updated_by);
        }

        if (update.permissions) {
          await this.updateMemberPermissions(update.member_id, update.permissions, updated_by);
        }

        if (update.teams) {
          // Remove from all teams
          for (const teamId of member.teams) {
            this.removeFromTeam(member.id, teamId);
          }
          // Add to new teams
          for (const teamId of update.teams) {
            await this.addToTeam(member.id, teamId);
          }
        }

        if (update.status) {
          member.status = update.status;
        }

        result.successful.push(update.member_id);
        result.success_count++;
      } catch (error: any) {
        result.failed.push({
          member_id: update.member_id,
          error: error.message
        });
        result.failure_count++;
      }
    }

    this.emit('members:bulk-updated', result);

    return result;
  }

  /**
   * Create a team
   */
  async createTeam(params: {
    organization_id: string;
    name: string;
    description?: string;
    parent_team_id?: string;
    lead_user_id?: string;
    permissions?: string[];
    metadata?: Record<string, any>;
  }): Promise<Team> {
    // Check team limit
    const orgTeams = Array.from(this.teams.values()).filter(
      t => t.organization_id === params.organization_id
    );

    if (this.config.max_teams_per_org && orgTeams.length >= this.config.max_teams_per_org) {
      throw new Error(`Organization has reached maximum team limit of ${this.config.max_teams_per_org}`);
    }

    // Validate parent team
    if (params.parent_team_id) {
      const parentTeam = this.teams.get(params.parent_team_id);
      if (!parentTeam || parentTeam.organization_id !== params.organization_id) {
        throw new Error('Invalid parent team');
      }
    }

    // Create team
    const team: Team = {
      id: crypto.randomUUID(),
      organization_id: params.organization_id,
      name: params.name,
      description: params.description,
      parent_team_id: params.parent_team_id,
      lead_user_id: params.lead_user_id,
      member_count: 0,
      permissions: params.permissions || [],
      metadata: params.metadata,
      created_at: new Date(),
      updated_at: new Date()
    };

    // Store team
    this.teams.set(team.id, team);
    this.teamMembers.set(team.id, new Set());

    // Emit event
    this.emit('team:created', {
      organization_id: team.organization_id,
      team_id: team.id,
      name: team.name
    });

    return team;
  }

  /**
   * Add member to team
   */
  async addToTeam(member_id: string, team_id: string): Promise<void> {
    const member = this.getMember(member_id);
    const team = this.teams.get(team_id);

    if (!member || !team) {
      throw new Error('Member or team not found');
    }

    if (member.organization_id !== team.organization_id) {
      throw new Error('Member and team must be in the same organization');
    }

    // Add to team
    if (!member.teams.includes(team_id)) {
      member.teams.push(team_id);
    }

    const teamMemberSet = this.teamMembers.get(team_id);
    if (teamMemberSet) {
      teamMemberSet.add(member_id);
      team.member_count = teamMemberSet.size;
    }

    // Emit event
    this.emit('member:added-to-team', {
      member_id,
      team_id,
      organization_id: member.organization_id
    });
  }

  /**
   * Remove member from team
   */
  removeFromTeam(member_id: string, team_id: string): void {
    const member = this.getMember(member_id);
    const team = this.teams.get(team_id);

    if (!member || !team) {
      return;
    }

    // Remove from member's teams
    member.teams = member.teams.filter(t => t !== team_id);

    // Remove from team members
    const teamMemberSet = this.teamMembers.get(team_id);
    if (teamMemberSet) {
      teamMemberSet.delete(member_id);
      team.member_count = teamMemberSet.size;
    }

    // Emit event
    this.emit('member:removed-from-team', {
      member_id,
      team_id,
      organization_id: member.organization_id
    });
  }

  /**
   * Get organization members
   */
  getOrganizationMembers(
    organization_id: string,
    filters?: {
      role?: string;
      status?: OrganizationMember['status'];
      team?: string;
      access_level?: OrganizationMember['access_level'];
    }
  ): OrganizationMember[] {
    const memberIds = this.organizationMembers.get(organization_id) || new Set();
    let members = Array.from(memberIds).map(id => this.members.get(id)!).filter(m => m);

    // Apply filters
    if (filters) {
      if (filters.role) {
        members = members.filter(m => m.role === filters.role);
      }
      if (filters.status) {
        members = members.filter(m => m.status === filters.status);
      }
      if (filters.team) {
        members = members.filter(m => m.teams.includes(filters.team!));
      }
      if (filters.access_level) {
        members = members.filter(m => m.access_level === filters.access_level);
      }
    }

    return members;
  }

  /**
   * Get member
   */
  getMember(member_id: string): OrganizationMember | null {
    return this.members.get(member_id) || null;
  }

  /**
   * Find member by user ID
   */
  findMemberByUserId(organization_id: string, user_id: string): OrganizationMember | null {
    const members = this.getOrganizationMembers(organization_id);
    return members.find(m => m.user_id === user_id) || null;
  }

  /**
   * Get team members
   */
  getTeamMembers(team_id: string): OrganizationMember[] {
    const memberIds = this.teamMembers.get(team_id) || new Set();
    return Array.from(memberIds).map(id => this.members.get(id)!).filter(m => m);
  }

  /**
   * Get organization teams
   */
  getOrganizationTeams(organization_id: string): Team[] {
    return Array.from(this.teams.values()).filter(
      t => t.organization_id === organization_id
    );
  }

  /**
   * Get member history
   */
  getMemberHistory(member_id: string): MembershipChange[] {
    return this.membershipHistory.get(member_id) || [];
  }

  /**
   * Get organization statistics
   */
  getOrganizationStats(organization_id: string): OrganizationStats {
    const members = this.getOrganizationMembers(organization_id);
    
    const stats: OrganizationStats = {
      total_members: members.length,
      active_members: members.filter(m => m.status === 'active').length,
      inactive_members: members.filter(m => m.status === 'inactive').length,
      suspended_members: members.filter(m => m.status === 'suspended').length,
      pending_members: members.filter(m => m.status === 'pending').length,
      members_by_role: {},
      members_by_team: {},
      growth_rate_30d: 0,
      churn_rate_30d: 0
    };

    // Count by role
    for (const member of members) {
      stats.members_by_role[member.role] = (stats.members_by_role[member.role] || 0) + 1;
    }

    // Count by team
    for (const team of this.getOrganizationTeams(organization_id)) {
      stats.members_by_team[team.name] = this.getTeamMembers(team.id).length;
    }

    // Calculate growth and churn rates (simplified)
    const thirtyDaysAgo = new Date(Date.now() - 30 * 24 * 60 * 60 * 1000);
    const newMembers = members.filter(m => m.joined_at > thirtyDaysAgo).length;
    const removedMembers = this.getRemovedMembersCount(organization_id, thirtyDaysAgo);
    
    if (stats.total_members > 0) {
      stats.growth_rate_30d = newMembers / stats.total_members;
      stats.churn_rate_30d = removedMembers / (stats.total_members + removedMembers);
    }

    return stats;
  }

  /**
   * Private: Store member
   */
  private storeMember(member: OrganizationMember): void {
    this.members.set(member.id, member);

    // Update organization index
    if (!this.organizationMembers.has(member.organization_id)) {
      this.organizationMembers.set(member.organization_id, new Set());
    }
    this.organizationMembers.get(member.organization_id)!.add(member.id);

    // Update user index
    if (!this.userMemberships.has(member.user_id)) {
      this.userMemberships.set(member.user_id, new Set());
    }
    this.userMemberships.get(member.user_id)!.add(member.id);
  }

  /**
   * Private: Find member
   */
  private findMember(organization_id: string, user_id: string): OrganizationMember | null {
    const orgMembers = this.organizationMembers.get(organization_id) || new Set();
    
    for (const memberId of orgMembers) {
      const member = this.members.get(memberId);
      if (member && member.user_id === user_id) {
        return member;
      }
    }

    return null;
  }

  /**
   * Private: Initialize system roles
   */
  private initializeSystemRoles(): void {
    const systemRoles: MemberRole[] = [
      {
        id: 'owner',
        organization_id: 'system',
        name: 'Owner',
        description: 'Full organization control',
        permissions: ['*'],
        priority: 100,
        is_default: false,
        is_system: true,
        can_be_deleted: false,
        created_at: new Date(),
        updated_at: new Date()
      },
      {
        id: 'admin',
        organization_id: 'system',
        name: 'Admin',
        description: 'Administrative access',
        permissions: [
          'members:read', 'members:write', 'members:delete',
          'teams:read', 'teams:write', 'teams:delete',
          'settings:read', 'settings:write'
        ],
        priority: 80,
        is_default: false,
        is_system: true,
        can_be_deleted: false,
        created_at: new Date(),
        updated_at: new Date()
      },
      {
        id: 'member',
        organization_id: 'system',
        name: 'Member',
        description: 'Standard member access',
        permissions: [
          'profile:read', 'profile:write',
          'teams:read',
          'members:read'
        ],
        priority: 50,
        is_default: true,
        is_system: true,
        can_be_deleted: false,
        created_at: new Date(),
        updated_at: new Date()
      },
      {
        id: 'guest',
        organization_id: 'system',
        name: 'Guest',
        description: 'Limited guest access',
        permissions: ['profile:read'],
        priority: 20,
        is_default: false,
        is_system: true,
        can_be_deleted: false,
        created_at: new Date(),
        updated_at: new Date()
      }
    ];

    for (const role of systemRoles) {
      this.roles.set(role.id, role);
    }
  }

  /**
   * Private: Get role
   */
  private getRole(role_id: string): MemberRole | null {
    return this.roles.get(role_id) || null;
  }

  /**
   * Private: Determine access level
   */
  private determineAccessLevel(role: string): OrganizationMember['access_level'] {
    switch (role) {
      case 'owner':
        return 'owner';
      case 'admin':
        return 'admin';
      case 'guest':
        return 'guest';
      default:
        return 'member';
    }
  }

  /**
   * Private: Record membership change
   */
  private recordChange(change: Omit<MembershipChange, 'id' | 'timestamp'>): void {
    const fullChange: MembershipChange = {
      ...change,
      id: crypto.randomUUID(),
      timestamp: new Date()
    };

    if (!this.membershipHistory.has(change.member_id)) {
      this.membershipHistory.set(change.member_id, []);
    }

    const history = this.membershipHistory.get(change.member_id)!;
    history.push(fullChange);

    // Keep only last 100 changes per member
    if (history.length > 100) {
      history.shift();
    }
  }

  /**
   * Private: Get removed members count
   */
  private getRemovedMembersCount(organization_id: string, since: Date): number {
    let count = 0;
    
    for (const history of this.membershipHistory.values()) {
      const removals = history.filter(
        change => 
          change.organization_id === organization_id &&
          change.change_type === 'status_change' &&
          change.new_value === 'removed' &&
          change.timestamp > since
      );
      count += removals.length;
    }

    return count;
  }

  /**
   * Private: Start maintenance timer
   */
  private startMaintenanceTimer(): void {
    setInterval(() => {
      // Auto-suspend inactive members
      if (this.config.auto_suspend_inactive_days) {
        const threshold = new Date(
          Date.now() - this.config.auto_suspend_inactive_days * 24 * 60 * 60 * 1000
        );

        for (const member of this.members.values()) {
          if (
            member.status === 'active' &&
            member.last_active_at &&
            member.last_active_at < threshold
          ) {
            member.status = 'inactive';
            this.emit('member:auto-suspended', {
              member_id: member.id,
              organization_id: member.organization_id,
              reason: 'inactivity'
            });
          }
        }
      }
    }, 86400000); // Daily
  }
}

// Export factory function
export function createOrganizationMembersService(config?: any): OrganizationMembersService {
  return new OrganizationMembersService(config);
}