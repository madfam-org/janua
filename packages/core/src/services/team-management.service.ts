import { EventEmitter } from 'events';
import { RedisService, getRedis } from './redis.service';
import { getMultiTenancyService, MultiTenancyService } from './multi-tenancy.service';

interface Team {
  id: string;
  organization_id: string;
  name: string;
  slug: string;
  description?: string;
  avatar_url?: string;
  parent_team_id?: string;
  settings: Record<string, any>;
  metadata: Record<string, any>;
  created_at: Date;
  updated_at: Date;
  created_by: string;
  is_default?: boolean;
}

interface TeamMember {
  team_id: string;
  user_id: string;
  role: TeamRole;
  permissions: string[];
  joined_at: Date;
  invited_by?: string;
  is_lead?: boolean;
  metadata?: Record<string, any>;
}

interface TeamInvitation {
  id: string;
  team_id: string;
  email: string;
  role: TeamRole;
  permissions: string[];
  token: string;
  invited_by: string;
  status: 'pending' | 'accepted' | 'expired' | 'cancelled';
  message?: string;
  created_at: Date;
  expires_at: Date;
  accepted_at?: Date;
}

interface TeamProject {
  id: string;
  team_id: string;
  project_id: string;
  access_level: 'read' | 'write' | 'admin';
  assigned_at: Date;
  assigned_by: string;
  metadata?: Record<string, any>;
}

interface TeamResource {
  id: string;
  team_id: string;
  resource_type: string;
  resource_id: string;
  permissions: string[];
  constraints?: Record<string, any>;
  assigned_at: Date;
  assigned_by: string;
}

enum TeamRole {
  OWNER = 'owner',
  LEAD = 'lead',
  MEMBER = 'member',
  VIEWER = 'viewer',
  GUEST = 'guest'
}

interface TeamHierarchy {
  team: Team;
  children: TeamHierarchy[];
  member_count: number;
  depth: number;
}

interface TeamActivity {
  id: string;
  team_id: string;
  user_id: string;
  action: string;
  target_type?: string;
  target_id?: string;
  details: Record<string, any>;
  timestamp: Date;
}

export class TeamManagementService extends EventEmitter {
  private redis: RedisService;
  private multiTenancy: MultiTenancyService;
  private teams: Map<string, Team> = new Map();
  private teamMembers: Map<string, Set<TeamMember>> = new Map();
  private userTeams: Map<string, Set<string>> = new Map();
  
  constructor() {
    super();
    this.redis = getRedis();
    this.multiTenancy = getMultiTenancyService();
  }
  
  // Team CRUD Operations
  async createTeam(
    organizationId: string,
    data: {
      name: string;
      slug: string;
      description?: string;
      avatar_url?: string;
      parent_team_id?: string;
      settings?: Record<string, any>;
      metadata?: Record<string, any>;
    },
    createdBy: string
  ): Promise<Team> {
    // Check organization limits
    const teamCount = await this.getOrganizationTeamCount(organizationId);
    const limitCheck = await this.multiTenancy.checkLimit(
      organizationId,
      'teams',
      teamCount + 1
    );
    
    if (!limitCheck.allowed) {
      throw new Error(`Team limit reached (${limitCheck.limit}). Upgrade your plan to create more teams.`);
    }
    
    // Validate slug uniqueness within organization
    const existingTeam = await this.getTeamBySlug(organizationId, data.slug);
    if (existingTeam) {
      throw new Error(`Team slug '${data.slug}' already exists in this organization`);
    }
    
    // Validate parent team if specified
    if (data.parent_team_id) {
      const parentTeam = await this.getTeam(data.parent_team_id);
      if (!parentTeam || parentTeam.organization_id !== organizationId) {
        throw new Error('Invalid parent team');
      }
    }
    
    const team: Team = {
      id: this.generateTeamId(),
      organization_id: organizationId,
      name: data.name,
      slug: data.slug,
      description: data.description,
      avatar_url: data.avatar_url,
      parent_team_id: data.parent_team_id,
      settings: data.settings || {},
      metadata: data.metadata || {},
      created_at: new Date(),
      updated_at: new Date(),
      created_by: createdBy,
      is_default: false
    };
    
    // Store team
    await this.storeTeam(team);
    
    // Add creator as team owner
    await this.addTeamMember(team.id, createdBy, TeamRole.OWNER, [], createdBy);
    
    // Track usage
    await this.multiTenancy.trackUsage(organizationId, 'teams', 1);
    
    // Emit event
    this.emit('team_created', {
      team_id: team.id,
      organization_id: organizationId,
      created_by: createdBy,
      timestamp: new Date()
    });
    
    // Log activity
    await this.logActivity({
      team_id: team.id,
      user_id: createdBy,
      action: 'team.created',
      details: { name: team.name, slug: team.slug }
    });
    
    return team;
  }
  
  async updateTeam(
    teamId: string,
    updates: Partial<Omit<Team, 'id' | 'organization_id' | 'created_at' | 'created_by'>>,
    updatedBy: string
  ): Promise<Team> {
    const team = await this.getTeam(teamId);
    if (!team) {
      throw new Error(`Team '${teamId}' not found`);
    }
    
    // Check permissions
    const hasPermission = await this.checkTeamPermission(
      teamId,
      updatedBy,
      'team.update'
    );
    if (!hasPermission) {
      throw new Error('Insufficient permissions to update team');
    }
    
    // Validate slug uniqueness if changed
    if (updates.slug && updates.slug !== team.slug) {
      const existingTeam = await this.getTeamBySlug(team.organization_id, updates.slug);
      if (existingTeam) {
        throw new Error(`Team slug '${updates.slug}' already exists`);
      }
    }
    
    // Update team
    const updatedTeam: Team = {
      ...team,
      ...updates,
      updated_at: new Date()
    };
    
    await this.storeTeam(updatedTeam);
    
    // Emit event
    this.emit('team_updated', {
      team_id: teamId,
      changes: updates,
      updated_by: updatedBy,
      timestamp: new Date()
    });
    
    // Log activity
    await this.logActivity({
      team_id: teamId,
      user_id: updatedBy,
      action: 'team.updated',
      details: { changes: Object.keys(updates) }
    });
    
    return updatedTeam;
  }
  
  async deleteTeam(teamId: string, deletedBy: string): Promise<void> {
    const team = await this.getTeam(teamId);
    if (!team) {
      throw new Error(`Team '${teamId}' not found`);
    }
    
    if (team.is_default) {
      throw new Error('Cannot delete default team');
    }
    
    // Check permissions
    const hasPermission = await this.checkTeamPermission(
      teamId,
      deletedBy,
      'team.delete'
    );
    if (!hasPermission) {
      throw new Error('Insufficient permissions to delete team');
    }
    
    // Check for child teams
    const children = await this.getChildTeams(teamId);
    if (children.length > 0) {
      throw new Error('Cannot delete team with child teams');
    }
    
    // Remove all members
    const members = await this.getTeamMembers(teamId);
    for (const member of members) {
      await this.removeTeamMember(teamId, member.user_id, deletedBy);
    }
    
    // Remove all resources
    await this.removeAllTeamResources(teamId);
    
    // Delete from storage
    await this.redis.hdel('teams', teamId);
    await this.redis.delete(`team:${teamId}:*`);
    
    // Remove from memory
    this.teams.delete(teamId);
    this.teamMembers.delete(teamId);
    
    // Emit event
    this.emit('team_deleted', {
      team_id: teamId,
      deleted_by: deletedBy,
      timestamp: new Date()
    });
    
    // Log activity
    await this.logActivity({
      team_id: teamId,
      user_id: deletedBy,
      action: 'team.deleted',
      details: { team_name: team.name }
    });
  }
  
  async getTeam(teamId: string): Promise<Team | null> {
    // Check memory cache
    if (this.teams.has(teamId)) {
      return this.teams.get(teamId)!;
    }
    
    // Check Redis
    const team = await this.redis.hget<Team>('teams', teamId);
    if (team) {
      this.teams.set(teamId, team);
      return team;
    }
    
    return null;
  }
  
  async getTeamBySlug(organizationId: string, slug: string): Promise<Team | null> {
    const key = `org:${organizationId}:team:slug:${slug}`;
    const teamId = await this.redis.get<string>(key);
    
    if (!teamId) return null;
    
    return this.getTeam(teamId);
  }
  
  // Team Member Management
  async addTeamMember(
    teamId: string,
    userId: string,
    role: TeamRole = TeamRole.MEMBER,
    permissions: string[] = [],
    invitedBy: string
  ): Promise<TeamMember> {
    const team = await this.getTeam(teamId);
    if (!team) {
      throw new Error(`Team '${teamId}' not found`);
    }
    
    // Check if already a member
    const existingMember = await this.getTeamMember(teamId, userId);
    if (existingMember) {
      throw new Error('User is already a team member');
    }
    
    const member: TeamMember = {
      team_id: teamId,
      user_id: userId,
      role,
      permissions,
      joined_at: new Date(),
      invited_by: invitedBy,
      is_lead: role === TeamRole.LEAD || role === TeamRole.OWNER
    };
    
    // Store member
    await this.storeTeamMember(member);
    
    // Update user's team list
    if (!this.userTeams.has(userId)) {
      this.userTeams.set(userId, new Set());
    }
    this.userTeams.get(userId)!.add(teamId);
    
    // Emit event
    this.emit('team_member_added', {
      team_id: teamId,
      user_id: userId,
      role,
      invited_by: invitedBy,
      timestamp: new Date()
    });
    
    // Log activity
    await this.logActivity({
      team_id: teamId,
      user_id: invitedBy,
      action: 'team.member_added',
      target_type: 'user',
      target_id: userId,
      details: { role }
    });
    
    return member;
  }
  
  async updateTeamMember(
    teamId: string,
    userId: string,
    updates: {
      role?: TeamRole;
      permissions?: string[];
      is_lead?: boolean;
    },
    updatedBy: string
  ): Promise<TeamMember> {
    const member = await this.getTeamMember(teamId, userId);
    if (!member) {
      throw new Error('Team member not found');
    }
    
    // Check permissions
    const hasPermission = await this.checkTeamPermission(
      teamId,
      updatedBy,
      'team.member.update'
    );
    if (!hasPermission) {
      throw new Error('Insufficient permissions to update team member');
    }
    
    // Prevent demoting the last owner
    if (member.role === TeamRole.OWNER && updates.role !== TeamRole.OWNER) {
      const owners = await this.getTeamOwners(teamId);
      if (owners.length === 1) {
        throw new Error('Cannot remove the last team owner');
      }
    }
    
    // Update member
    const updatedMember: TeamMember = {
      ...member,
      ...updates,
      is_lead: updates.role === TeamRole.LEAD || updates.role === TeamRole.OWNER || updates.is_lead
    };
    
    await this.storeTeamMember(updatedMember);
    
    // Emit event
    this.emit('team_member_updated', {
      team_id: teamId,
      user_id: userId,
      changes: updates,
      updated_by: updatedBy,
      timestamp: new Date()
    });
    
    // Log activity
    await this.logActivity({
      team_id: teamId,
      user_id: updatedBy,
      action: 'team.member_updated',
      target_type: 'user',
      target_id: userId,
      details: updates
    });
    
    return updatedMember;
  }
  
  async removeTeamMember(
    teamId: string,
    userId: string,
    removedBy: string
  ): Promise<void> {
    const member = await this.getTeamMember(teamId, userId);
    if (!member) {
      throw new Error('Team member not found');
    }
    
    // Prevent removing the last owner
    if (member.role === TeamRole.OWNER) {
      const owners = await this.getTeamOwners(teamId);
      if (owners.length === 1) {
        throw new Error('Cannot remove the last team owner');
      }
    }
    
    // Check permissions
    const hasPermission = await this.checkTeamPermission(
      teamId,
      removedBy,
      'team.member.remove'
    );
    if (!hasPermission && removedBy !== userId) {
      throw new Error('Insufficient permissions to remove team member');
    }
    
    // Remove from storage
    await this.redis.hdel(`team:${teamId}:members`, userId);
    
    // Update memory cache
    const members = this.teamMembers.get(teamId);
    if (members) {
      members.delete(member);
    }
    
    const userTeamSet = this.userTeams.get(userId);
    if (userTeamSet) {
      userTeamSet.delete(teamId);
    }
    
    // Emit event
    this.emit('team_member_removed', {
      team_id: teamId,
      user_id: userId,
      removed_by: removedBy,
      timestamp: new Date()
    });
    
    // Log activity
    await this.logActivity({
      team_id: teamId,
      user_id: removedBy,
      action: removedBy === userId ? 'team.member_left' : 'team.member_removed',
      target_type: 'user',
      target_id: userId,
      details: {}
    });
  }
  
  async getTeamMember(teamId: string, userId: string): Promise<TeamMember | null> {
    const members = await this.getTeamMembers(teamId);
    return members.find(m => m.user_id === userId) || null;
  }
  
  async getTeamMembers(
    teamId: string,
    options?: {
      role?: TeamRole;
      is_lead?: boolean;
      limit?: number;
      offset?: number;
    }
  ): Promise<TeamMember[]> {
    // Get from cache or Redis
    let members: TeamMember[];
    
    if (this.teamMembers.has(teamId)) {
      members = Array.from(this.teamMembers.get(teamId)!);
    } else {
      const stored = await this.redis.hgetall<TeamMember>(`team:${teamId}:members`);
      members = Object.values(stored);
      this.teamMembers.set(teamId, new Set(members));
    }
    
    // Apply filters
    if (options?.role) {
      members = members.filter(m => m.role === options.role);
    }
    
    if (options?.is_lead !== undefined) {
      members = members.filter(m => m.is_lead === options.is_lead);
    }
    
    // Apply pagination
    if (options?.offset !== undefined && options?.limit !== undefined) {
      members = members.slice(options.offset, options.offset + options.limit);
    }
    
    return members;
  }
  
  async getTeamOwners(teamId: string): Promise<TeamMember[]> {
    return this.getTeamMembers(teamId, { role: TeamRole.OWNER });
  }
  
  async getUserTeams(
    userId: string,
    organizationId?: string
  ): Promise<Team[]> {
    const teamIds = this.userTeams.get(userId) || new Set();
    const teams: Team[] = [];
    
    for (const teamId of teamIds) {
      const team = await this.getTeam(teamId);
      if (team && (!organizationId || team.organization_id === organizationId)) {
        teams.push(team);
      }
    }
    
    return teams;
  }
  
  // Team Hierarchy
  async getTeamHierarchy(
    rootTeamId?: string,
    organizationId?: string
  ): Promise<TeamHierarchy[]> {
    let rootTeams: Team[];
    
    if (rootTeamId) {
      const team = await this.getTeam(rootTeamId);
      rootTeams = team ? [team] : [];
    } else if (organizationId) {
      rootTeams = await this.getOrganizationTeams(organizationId);
      rootTeams = rootTeams.filter(t => !t.parent_team_id);
    } else {
      throw new Error('Either rootTeamId or organizationId must be provided');
    }
    
    const hierarchies: TeamHierarchy[] = [];
    
    for (const team of rootTeams) {
      hierarchies.push(await this.buildTeamHierarchy(team, 0));
    }
    
    return hierarchies;
  }
  
  private async buildTeamHierarchy(team: Team, depth: number): Promise<TeamHierarchy> {
    const children = await this.getChildTeams(team.id);
    const memberCount = await this.getTeamMemberCount(team.id);
    
    const childHierarchies: TeamHierarchy[] = [];
    for (const child of children) {
      childHierarchies.push(await this.buildTeamHierarchy(child, depth + 1));
    }
    
    return {
      team,
      children: childHierarchies,
      member_count: memberCount,
      depth
    };
  }
  
  async getChildTeams(parentTeamId: string): Promise<Team[]> {
    const allTeams = await this.redis.hgetall<Team>('teams');
    return Object.values(allTeams).filter(t => t.parent_team_id === parentTeamId);
  }
  
  async getOrganizationTeams(organizationId: string): Promise<Team[]> {
    const allTeams = await this.redis.hgetall<Team>('teams');
    return Object.values(allTeams).filter(t => t.organization_id === organizationId);
  }
  
  async getOrganizationTeamCount(organizationId: string): Promise<number> {
    const teams = await this.getOrganizationTeams(organizationId);
    return teams.length;
  }
  
  async getTeamMemberCount(teamId: string): Promise<number> {
    const members = await this.getTeamMembers(teamId);
    return members.length;
  }
  
  // Team Invitations
  async inviteToTeam(
    teamId: string,
    email: string,
    role: TeamRole,
    permissions: string[],
    invitedBy: string,
    message?: string
  ): Promise<TeamInvitation> {
    const team = await this.getTeam(teamId);
    if (!team) {
      throw new Error(`Team '${teamId}' not found`);
    }
    
    // Check permissions
    const hasPermission = await this.checkTeamPermission(
      teamId,
      invitedBy,
      'team.member.invite'
    );
    if (!hasPermission) {
      throw new Error('Insufficient permissions to invite team members');
    }
    
    // Check for existing invitation
    const existingInvite = await this.getPendingInvitation(teamId, email);
    if (existingInvite) {
      throw new Error('An invitation is already pending for this email');
    }
    
    const invitation: TeamInvitation = {
      id: this.generateInvitationId(),
      team_id: teamId,
      email,
      role,
      permissions,
      token: this.generateInvitationToken(),
      invited_by: invitedBy,
      status: 'pending',
      message,
      created_at: new Date(),
      expires_at: new Date(Date.now() + 7 * 24 * 60 * 60 * 1000) // 7 days
    };
    
    // Store invitation
    await this.redis.hset(`team:${teamId}:invitations`, invitation.id, invitation);
    await this.redis.hset('invitation_tokens', invitation.token, invitation.id);
    
    // Send invitation email (would integrate with email service)
    await this.sendInvitationEmail(invitation, team);
    
    // Emit event
    this.emit('team_invitation_sent', {
      team_id: teamId,
      invitation_id: invitation.id,
      email,
      invited_by: invitedBy,
      timestamp: new Date()
    });
    
    // Log activity
    await this.logActivity({
      team_id: teamId,
      user_id: invitedBy,
      action: 'team.invitation_sent',
      details: { email, role }
    });
    
    return invitation;
  }
  
  async acceptInvitation(
    token: string,
    userId: string
  ): Promise<{ team: Team; member: TeamMember }> {
    const invitationId = await this.redis.hget<string>('invitation_tokens', token);
    if (!invitationId) {
      throw new Error('Invalid invitation token');
    }
    
    const invitation = await this.redis.hget<TeamInvitation>(
      `team:${invitationId}:invitations`,
      invitationId
    );
    if (!invitation) {
      throw new Error('Invitation not found');
    }
    
    if (invitation.status !== 'pending') {
      throw new Error('Invitation has already been used');
    }
    
    if (new Date() > new Date(invitation.expires_at)) {
      throw new Error('Invitation has expired');
    }
    
    // Accept invitation
    invitation.status = 'accepted';
    invitation.accepted_at = new Date();
    await this.redis.hset(
      `team:${invitation.team_id}:invitations`,
      invitationId,
      invitation
    );
    
    // Add user to team
    const member = await this.addTeamMember(
      invitation.team_id,
      userId,
      invitation.role,
      invitation.permissions,
      invitation.invited_by
    );
    
    // Get team
    const team = (await this.getTeam(invitation.team_id))!;
    
    // Clean up token
    await this.redis.hdel('invitation_tokens', token);
    
    // Emit event
    this.emit('team_invitation_accepted', {
      team_id: invitation.team_id,
      invitation_id: invitation.id,
      user_id: userId,
      timestamp: new Date()
    });
    
    return { team, member };
  }
  
  async revokeInvitation(invitationId: string, revokedBy: string): Promise<void> {
    // Find invitation
    const allInvitations = await this.redis.keys('team:*:invitations');
    let invitation: TeamInvitation | null = null;
    let teamId: string | null = null;
    
    for (const key of allInvitations) {
      const inv = await this.redis.hget<TeamInvitation>(key, invitationId);
      if (inv) {
        invitation = inv;
        teamId = inv.team_id;
        break;
      }
    }
    
    if (!invitation || !teamId) {
      throw new Error('Invitation not found');
    }
    
    if (invitation.status !== 'pending') {
      throw new Error('Cannot revoke non-pending invitation');
    }
    
    // Check permissions
    const hasPermission = await this.checkTeamPermission(
      teamId,
      revokedBy,
      'team.invitation.revoke'
    );
    if (!hasPermission) {
      throw new Error('Insufficient permissions to revoke invitation');
    }
    
    // Update status
    invitation.status = 'cancelled';
    await this.redis.hset(`team:${teamId}:invitations`, invitationId, invitation);
    
    // Clean up token
    await this.redis.hdel('invitation_tokens', invitation.token);
    
    // Emit event
    this.emit('team_invitation_revoked', {
      team_id: teamId,
      invitation_id: invitationId,
      revoked_by: revokedBy,
      timestamp: new Date()
    });
  }
  
  // Team Resources & Projects
  async assignTeamResource(
    teamId: string,
    resourceType: string,
    resourceId: string,
    permissions: string[],
    assignedBy: string
  ): Promise<TeamResource> {
    const team = await this.getTeam(teamId);
    if (!team) {
      throw new Error(`Team '${teamId}' not found`);
    }
    
    const resource: TeamResource = {
      id: this.generateResourceId(),
      team_id: teamId,
      resource_type: resourceType,
      resource_id: resourceId,
      permissions,
      assigned_at: new Date(),
      assigned_by: assignedBy
    };
    
    await this.redis.hset(`team:${teamId}:resources`, resource.id, resource);
    
    // Emit event
    this.emit('team_resource_assigned', {
      team_id: teamId,
      resource,
      assigned_by: assignedBy,
      timestamp: new Date()
    });
    
    return resource;
  }
  
  async removeTeamResource(
    teamId: string,
    resourceId: string,
    removedBy: string
  ): Promise<void> {
    const resource = await this.redis.hget<TeamResource>(
      `team:${teamId}:resources`,
      resourceId
    );
    
    if (!resource) {
      throw new Error('Resource not found');
    }
    
    await this.redis.hdel(`team:${teamId}:resources`, resourceId);
    
    // Emit event
    this.emit('team_resource_removed', {
      team_id: teamId,
      resource_id: resourceId,
      removed_by: removedBy,
      timestamp: new Date()
    });
  }
  
  async getTeamResources(
    teamId: string,
    resourceType?: string
  ): Promise<TeamResource[]> {
    const resources = await this.redis.hgetall<TeamResource>(
      `team:${teamId}:resources`
    );
    
    let result = Object.values(resources);
    
    if (resourceType) {
      result = result.filter(r => r.resource_type === resourceType);
    }
    
    return result;
  }
  
  private async removeAllTeamResources(teamId: string): Promise<void> {
    await this.redis.delete(`team:${teamId}:resources`);
  }
  
  // Permissions
  async checkTeamPermission(
    teamId: string,
    userId: string,
    permission: string
  ): Promise<boolean> {
    const member = await this.getTeamMember(teamId, userId);
    if (!member) return false;
    
    // Owners have all permissions
    if (member.role === TeamRole.OWNER) return true;
    
    // Check role-based permissions
    const rolePermissions = this.getRolePermissions(member.role);
    if (rolePermissions.includes(permission) || rolePermissions.includes('*')) {
      return true;
    }
    
    // Check custom permissions
    return member.permissions.includes(permission) || member.permissions.includes('*');
  }
  
  private getRolePermissions(role: TeamRole): string[] {
    switch (role) {
      case TeamRole.OWNER:
        return ['*'];
      case TeamRole.LEAD:
        return [
          'team.update',
          'team.member.invite',
          'team.member.update',
          'team.member.remove',
          'team.resource.manage'
        ];
      case TeamRole.MEMBER:
        return [
          'team.view',
          'team.resource.view'
        ];
      case TeamRole.VIEWER:
        return ['team.view'];
      case TeamRole.GUEST:
        return ['team.view'];
      default:
        return [];
    }
  }
  
  // Activity Logging
  private async logActivity(activity: Omit<TeamActivity, 'id' | 'timestamp'>): Promise<void> {
    const fullActivity: TeamActivity = {
      id: this.generateActivityId(),
      ...activity,
      timestamp: new Date()
    };
    
    const key = `team:${activity.team_id}:activity`;
    await this.redis.lpush(key, fullActivity);
    
    // Keep only last 100 activities
    await this.redis.ltrim(key, 0, 99);
  }
  
  async getTeamActivity(
    teamId: string,
    limit: number = 50
  ): Promise<TeamActivity[]> {
    const activities = await this.redis.lrange<TeamActivity>(
      `team:${teamId}:activity`,
      0,
      limit - 1
    );
    
    return activities;
  }
  
  // Helper Methods
  private async storeTeam(team: Team): Promise<void> {
    await this.redis.hset('teams', team.id, team);
    await this.redis.set(
      `org:${team.organization_id}:team:slug:${team.slug}`,
      team.id
    );
    this.teams.set(team.id, team);
  }
  
  private async storeTeamMember(member: TeamMember): Promise<void> {
    await this.redis.hset(
      `team:${member.team_id}:members`,
      member.user_id,
      member
    );
    
    if (!this.teamMembers.has(member.team_id)) {
      this.teamMembers.set(member.team_id, new Set());
    }
    this.teamMembers.get(member.team_id)!.add(member);
  }
  
  private async getPendingInvitation(
    teamId: string,
    email: string
  ): Promise<TeamInvitation | null> {
    const invitations = await this.redis.hgetall<TeamInvitation>(
      `team:${teamId}:invitations`
    );
    
    return Object.values(invitations).find(
      inv => inv.email === email && inv.status === 'pending'
    ) || null;
  }
  
  private async sendInvitationEmail(
    invitation: TeamInvitation,
    team: Team
  ): Promise<void> {
    // Integration with email service would go here
    console.log(`Sending invitation email to ${invitation.email} for team ${team.name}`);
  }
  
  private generateTeamId(): string {
    return `team_${Date.now()}_${Math.random().toString(36).substring(2, 9)}`;
  }
  
  private generateInvitationId(): string {
    return `inv_${Date.now()}_${Math.random().toString(36).substring(2, 9)}`;
  }
  
  private generateInvitationToken(): string {
    return Buffer.from(
      `${Date.now()}_${Math.random().toString(36).substring(2, 15)}`
    ).toString('base64url');
  }
  
  private generateResourceId(): string {
    return `res_${Date.now()}_${Math.random().toString(36).substring(2, 9)}`;
  }
  
  private generateActivityId(): string {
    return `act_${Date.now()}_${Math.random().toString(36).substring(2, 9)}`;
  }
}

// Export singleton instance
let teamManagementService: TeamManagementService | null = null;

export function getTeamManagementService(): TeamManagementService {
  if (!teamManagementService) {
    teamManagementService = new TeamManagementService();
  }
  return teamManagementService;
}