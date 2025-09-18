/**
 * Invitations Service
 * Manages organization invitations with role-based permissions and secure token generation
 */

import { EventEmitter } from 'events';
import crypto from 'crypto';
import { createHash } from 'crypto';

export interface Invitation {
  id: string;
  organization_id: string;
  email: string;
  role: string;
  permissions?: string[];
  inviter_id: string;
  inviter_email: string;
  token: string;
  token_hash: string;
  status: 'pending' | 'accepted' | 'declined' | 'expired' | 'cancelled';
  created_at: Date;
  expires_at: Date;
  accepted_at?: Date;
  declined_at?: Date;
  cancelled_at?: Date;
  accepted_by_user_id?: string;
  metadata?: Record<string, any>;
  resend_count: number;
  last_resent_at?: Date;
  custom_message?: string;
  redirect_url?: string;
}

export interface InvitationTemplate {
  id: string;
  name: string;
  subject: string;
  body: string;
  variables: string[];
  organization_id?: string;
  is_default: boolean;
}

export interface BulkInvitationResult {
  successful: string[];
  failed: Array<{ email: string; error: string }>;
  total: number;
  success_count: number;
  failure_count: number;
}

export interface InvitationConfig {
  default_expiry_hours: number;
  max_resend_count: number;
  resend_cooldown_minutes: number;
  allow_bulk_invites: boolean;
  max_bulk_size: number;
  require_email_verification: boolean;
  auto_accept_domain?: string;
  restricted_domains?: string[];
  allowed_domains?: string[];
}

export class InvitationsService extends EventEmitter {
  private invitations: Map<string, Invitation> = new Map();
  private tokenIndex: Map<string, string> = new Map(); // token_hash -> invitation_id
  private organizationInvitations: Map<string, Set<string>> = new Map();
  private emailInvitations: Map<string, Set<string>> = new Map();
  private templates: Map<string, InvitationTemplate> = new Map();

  constructor(
    private readonly config: InvitationConfig = {
      default_expiry_hours: 72,
      max_resend_count: 3,
      resend_cooldown_minutes: 60,
      allow_bulk_invites: true,
      max_bulk_size: 100,
      require_email_verification: true
    }
  ) {
    super();
    this.startCleanupTimer();
  }

  /**
   * Create a new invitation
   */
  async createInvitation(params: {
    organization_id: string;
    email: string;
    role: string;
    permissions?: string[];
    inviter_id: string;
    inviter_email: string;
    custom_message?: string;
    redirect_url?: string;
    expiry_hours?: number;
    metadata?: Record<string, any>;
  }): Promise<Invitation> {
    // Validate email domain
    this.validateEmailDomain(params.email);

    // Check for existing pending invitation
    const existing = await this.findPendingInvitation(
      params.organization_id,
      params.email
    );

    if (existing) {
      throw new Error('An invitation for this email already exists');
    }

    // Generate secure token
    const token = this.generateSecureToken();
    const tokenHash = this.hashToken(token);

    // Create invitation
    const invitation: Invitation = {
      id: crypto.randomUUID(),
      organization_id: params.organization_id,
      email: params.email.toLowerCase(),
      role: params.role,
      permissions: params.permissions,
      inviter_id: params.inviter_id,
      inviter_email: params.inviter_email,
      token: token,
      token_hash: tokenHash,
      status: 'pending',
      created_at: new Date(),
      expires_at: new Date(
        Date.now() + (params.expiry_hours || this.config.default_expiry_hours) * 3600000
      ),
      resend_count: 0,
      custom_message: params.custom_message,
      redirect_url: params.redirect_url,
      metadata: params.metadata
    };

    // Check for auto-accept domain
    if (this.shouldAutoAccept(params.email)) {
      invitation.status = 'accepted';
      invitation.accepted_at = new Date();
    }

    // Store invitation
    this.storeInvitation(invitation);

    // Emit event
    this.emit('invitation:created', {
      invitation_id: invitation.id,
      organization_id: invitation.organization_id,
      email: invitation.email,
      role: invitation.role,
      inviter_id: invitation.inviter_id
    });

    return invitation;
  }

  /**
   * Create multiple invitations at once
   */
  async createBulkInvitations(params: {
    organization_id: string;
    invitations: Array<{
      email: string;
      role: string;
      permissions?: string[];
      custom_message?: string;
    }>;
    inviter_id: string;
    inviter_email: string;
    expiry_hours?: number;
  }): Promise<BulkInvitationResult> {
    if (!this.config.allow_bulk_invites) {
      throw new Error('Bulk invitations are not allowed');
    }

    if (params.invitations.length > this.config.max_bulk_size) {
      throw new Error(`Cannot send more than ${this.config.max_bulk_size} invitations at once`);
    }

    const result: BulkInvitationResult = {
      successful: [],
      failed: [],
      total: params.invitations.length,
      success_count: 0,
      failure_count: 0
    };

    for (const inviteParams of params.invitations) {
      try {
        const invitation = await this.createInvitation({
          organization_id: params.organization_id,
          email: inviteParams.email,
          role: inviteParams.role,
          permissions: inviteParams.permissions,
          inviter_id: params.inviter_id,
          inviter_email: params.inviter_email,
          custom_message: inviteParams.custom_message,
          expiry_hours: params.expiry_hours
        });

        result.successful.push(invitation.email);
        result.success_count++;
      } catch (error: any) {
        result.failed.push({
          email: inviteParams.email,
          error: error.message
        });
        result.failure_count++;
      }
    }

    this.emit('invitation:bulk-created', result);

    return result;
  }

  /**
   * Accept an invitation
   */
  async acceptInvitation(
    token: string,
    user_id?: string
  ): Promise<{
    invitation: Invitation;
    organization_id: string;
    role: string;
    permissions?: string[];
  }> {
    const tokenHash = this.hashToken(token);
    const invitationId = this.tokenIndex.get(tokenHash);

    if (!invitationId) {
      throw new Error('Invalid invitation token');
    }

    const invitation = this.invitations.get(invitationId);
    if (!invitation) {
      throw new Error('Invitation not found');
    }

    // Check status
    if (invitation.status !== 'pending') {
      throw new Error(`Invitation has already been ${invitation.status}`);
    }

    // Check expiry
    if (invitation.expires_at < new Date()) {
      invitation.status = 'expired';
      throw new Error('Invitation has expired');
    }

    // Accept invitation
    invitation.status = 'accepted';
    invitation.accepted_at = new Date();
    invitation.accepted_by_user_id = user_id;

    // Emit event
    this.emit('invitation:accepted', {
      invitation_id: invitation.id,
      organization_id: invitation.organization_id,
      email: invitation.email,
      role: invitation.role,
      user_id
    });

    return {
      invitation,
      organization_id: invitation.organization_id,
      role: invitation.role,
      permissions: invitation.permissions
    };
  }

  /**
   * Decline an invitation
   */
  async declineInvitation(token: string): Promise<void> {
    const tokenHash = this.hashToken(token);
    const invitationId = this.tokenIndex.get(tokenHash);

    if (!invitationId) {
      throw new Error('Invalid invitation token');
    }

    const invitation = this.invitations.get(invitationId);
    if (!invitation) {
      throw new Error('Invitation not found');
    }

    // Check status
    if (invitation.status !== 'pending') {
      throw new Error(`Invitation has already been ${invitation.status}`);
    }

    // Decline invitation
    invitation.status = 'declined';
    invitation.declined_at = new Date();

    // Emit event
    this.emit('invitation:declined', {
      invitation_id: invitation.id,
      organization_id: invitation.organization_id,
      email: invitation.email
    });
  }

  /**
   * Cancel an invitation
   */
  async cancelInvitation(
    invitation_id: string,
    canceller_id: string
  ): Promise<void> {
    const invitation = this.invitations.get(invitation_id);
    
    if (!invitation) {
      throw new Error('Invitation not found');
    }

    // Check if already processed
    if (invitation.status !== 'pending') {
      throw new Error(`Cannot cancel invitation that has been ${invitation.status}`);
    }

    // Cancel invitation
    invitation.status = 'cancelled';
    invitation.cancelled_at = new Date();

    // Emit event
    this.emit('invitation:cancelled', {
      invitation_id: invitation.id,
      organization_id: invitation.organization_id,
      email: invitation.email,
      cancelled_by: canceller_id
    });
  }

  /**
   * Resend an invitation
   */
  async resendInvitation(
    invitation_id: string,
    resender_id: string
  ): Promise<Invitation> {
    const invitation = this.invitations.get(invitation_id);
    
    if (!invitation) {
      throw new Error('Invitation not found');
    }

    // Check status
    if (invitation.status !== 'pending') {
      throw new Error(`Cannot resend invitation that has been ${invitation.status}`);
    }

    // Check resend limit
    if (invitation.resend_count >= this.config.max_resend_count) {
      throw new Error('Maximum resend limit reached');
    }

    // Check resend cooldown
    if (invitation.last_resent_at) {
      const elapsed = (Date.now() - invitation.last_resent_at.getTime()) / 60000;
      if (elapsed < this.config.resend_cooldown_minutes) {
        throw new Error(
          `Please wait ${Math.ceil(this.config.resend_cooldown_minutes - elapsed)} minutes before resending`
        );
      }
    }

    // Generate new token
    const newToken = this.generateSecureToken();
    const newTokenHash = this.hashToken(newToken);

    // Remove old token from index
    this.tokenIndex.delete(invitation.token_hash);

    // Update invitation
    invitation.token = newToken;
    invitation.token_hash = newTokenHash;
    invitation.resend_count++;
    invitation.last_resent_at = new Date();
    invitation.expires_at = new Date(
      Date.now() + this.config.default_expiry_hours * 3600000
    );

    // Update token index
    this.tokenIndex.set(newTokenHash, invitation.id);

    // Emit event
    this.emit('invitation:resent', {
      invitation_id: invitation.id,
      organization_id: invitation.organization_id,
      email: invitation.email,
      resend_count: invitation.resend_count,
      resent_by: resender_id
    });

    return invitation;
  }

  /**
   * Get invitation by token
   */
  async getInvitationByToken(token: string): Promise<Invitation | null> {
    const tokenHash = this.hashToken(token);
    const invitationId = this.tokenIndex.get(tokenHash);

    if (!invitationId) {
      return null;
    }

    const invitation = this.invitations.get(invitationId);
    
    // Check if expired
    if (invitation && invitation.expires_at < new Date() && invitation.status === 'pending') {
      invitation.status = 'expired';
    }

    return invitation || null;
  }

  /**
   * Get invitation by ID
   */
  getInvitation(invitation_id: string): Invitation | null {
    const invitation = this.invitations.get(invitation_id);
    
    // Check if expired
    if (invitation && invitation.expires_at < new Date() && invitation.status === 'pending') {
      invitation.status = 'expired';
    }

    return invitation || null;
  }

  /**
   * List invitations for an organization
   */
  getOrganizationInvitations(
    organization_id: string,
    options: {
      status?: Invitation['status'];
      email?: string;
      role?: string;
      limit?: number;
      offset?: number;
    } = {}
  ): Invitation[] {
    const invitationIds = this.organizationInvitations.get(organization_id) || new Set();
    let invitations = Array.from(invitationIds)
      .map(id => this.invitations.get(id)!)
      .filter(inv => inv);

    // Apply filters
    if (options.status) {
      invitations = invitations.filter(inv => inv.status === options.status);
    }

    if (options.email) {
      invitations = invitations.filter(inv => inv.email === options.email!.toLowerCase());
    }

    if (options.role) {
      invitations = invitations.filter(inv => inv.role === options.role);
    }

    // Sort by created_at desc
    invitations.sort((a, b) => b.created_at.getTime() - a.created_at.getTime());

    // Apply pagination
    const offset = options.offset || 0;
    const limit = options.limit || 50;

    return invitations.slice(offset, offset + limit);
  }

  /**
   * Get invitations by email
   */
  getInvitationsByEmail(email: string): Invitation[] {
    const normalizedEmail = email.toLowerCase();
    const invitationIds = this.emailInvitations.get(normalizedEmail) || new Set();
    
    return Array.from(invitationIds)
      .map(id => this.invitations.get(id)!)
      .filter(inv => inv && inv.status === 'pending')
      .sort((a, b) => b.created_at.getTime() - a.created_at.getTime());
  }

  /**
   * Create or update invitation template
   */
  createTemplate(template: InvitationTemplate): void {
    this.templates.set(template.id, template);
    this.emit('invitation:template-created', template);
  }

  /**
   * Get template
   */
  getTemplate(template_id: string): InvitationTemplate | null {
    return this.templates.get(template_id) || null;
  }

  /**
   * Get organization templates
   */
  getOrganizationTemplates(organization_id: string): InvitationTemplate[] {
    return Array.from(this.templates.values()).filter(
      t => !t.organization_id || t.organization_id === organization_id
    );
  }

  /**
   * Generate invitation link
   */
  generateInvitationLink(
    invitation: Invitation,
    base_url: string
  ): string {
    const params = new URLSearchParams({
      token: invitation.token,
      email: invitation.email,
      org: invitation.organization_id
    });

    if (invitation.redirect_url) {
      params.append('redirect', invitation.redirect_url);
    }

    return `${base_url}/invitations/accept?${params.toString()}`;
  }

  /**
   * Validate invitation
   */
  async validateInvitation(token: string): Promise<{
    valid: boolean;
    invitation?: Invitation;
    error?: string;
  }> {
    try {
      const invitation = await this.getInvitationByToken(token);
      
      if (!invitation) {
        return { valid: false, error: 'Invalid invitation token' };
      }

      if (invitation.status !== 'pending') {
        return { 
          valid: false, 
          error: `Invitation has already been ${invitation.status}` 
        };
      }

      if (invitation.expires_at < new Date()) {
        invitation.status = 'expired';
        return { valid: false, error: 'Invitation has expired' };
      }

      return { valid: true, invitation };
    } catch (error: any) {
      return { valid: false, error: error.message };
    }
  }

  /**
   * Get statistics
   */
  getStatistics(): {
    total_invitations: number;
    pending_count: number;
    accepted_count: number;
    declined_count: number;
    expired_count: number;
    cancelled_count: number;
    acceptance_rate: number;
    avg_time_to_accept_hours: number;
  } {
    const stats = {
      total_invitations: 0,
      pending_count: 0,
      accepted_count: 0,
      declined_count: 0,
      expired_count: 0,
      cancelled_count: 0,
      acceptance_rate: 0,
      avg_time_to_accept_hours: 0
    };

    let totalAcceptTime = 0;

    for (const invitation of this.invitations.values()) {
      stats.total_invitations++;

      switch (invitation.status) {
        case 'pending':
          stats.pending_count++;
          break;
        case 'accepted':
          stats.accepted_count++;
          if (invitation.accepted_at) {
            totalAcceptTime += 
              (invitation.accepted_at.getTime() - invitation.created_at.getTime()) / 3600000;
          }
          break;
        case 'declined':
          stats.declined_count++;
          break;
        case 'expired':
          stats.expired_count++;
          break;
        case 'cancelled':
          stats.cancelled_count++;
          break;
      }
    }

    if (stats.accepted_count + stats.declined_count > 0) {
      stats.acceptance_rate = 
        stats.accepted_count / (stats.accepted_count + stats.declined_count);
    }

    if (stats.accepted_count > 0) {
      stats.avg_time_to_accept_hours = totalAcceptTime / stats.accepted_count;
    }

    return stats;
  }

  /**
   * Private: Generate secure token
   */
  private generateSecureToken(): string {
    return crypto.randomBytes(32).toString('base64url');
  }

  /**
   * Private: Hash token for storage
   */
  private hashToken(token: string): string {
    return createHash('sha256').update(token).digest('hex');
  }

  /**
   * Private: Store invitation
   */
  private storeInvitation(invitation: Invitation): void {
    // Store in main map
    this.invitations.set(invitation.id, invitation);

    // Update token index
    this.tokenIndex.set(invitation.token_hash, invitation.id);

    // Update organization index
    if (!this.organizationInvitations.has(invitation.organization_id)) {
      this.organizationInvitations.set(invitation.organization_id, new Set());
    }
    this.organizationInvitations.get(invitation.organization_id)!.add(invitation.id);

    // Update email index
    const email = invitation.email.toLowerCase();
    if (!this.emailInvitations.has(email)) {
      this.emailInvitations.set(email, new Set());
    }
    this.emailInvitations.get(email)!.add(invitation.id);
  }

  /**
   * Private: Find pending invitation
   */
  private async findPendingInvitation(
    organization_id: string,
    email: string
  ): Promise<Invitation | null> {
    const invitations = this.getOrganizationInvitations(organization_id, {
      email,
      status: 'pending'
    });

    return invitations[0] || null;
  }

  /**
   * Private: Validate email domain
   */
  private validateEmailDomain(email: string): void {
    const domain = email.split('@')[1];
    
    if (!domain) {
      throw new Error('Invalid email address');
    }

    // Check restricted domains
    if (this.config.restricted_domains?.includes(domain)) {
      throw new Error('Email domain is not allowed');
    }

    // Check allowed domains
    if (this.config.allowed_domains && 
        this.config.allowed_domains.length > 0 &&
        !this.config.allowed_domains.includes(domain)) {
      throw new Error('Email domain is not in the allowed list');
    }
  }

  /**
   * Private: Check if should auto-accept
   */
  private shouldAutoAccept(email: string): boolean {
    if (!this.config.auto_accept_domain) return false;
    
    const domain = email.split('@')[1];
    return domain === this.config.auto_accept_domain;
  }

  /**
   * Private: Cleanup expired invitations
   */
  private startCleanupTimer(): void {
    setInterval(() => {
      const now = new Date();
      
      for (const invitation of this.invitations.values()) {
        if (invitation.status === 'pending' && invitation.expires_at < now) {
          invitation.status = 'expired';
          this.emit('invitation:expired', {
            invitation_id: invitation.id,
            organization_id: invitation.organization_id,
            email: invitation.email
          });
        }
      }
    }, 3600000); // Every hour
  }
}

// Export factory function
export function createInvitationsService(config?: InvitationConfig): InvitationsService {
  return new InvitationsService(config);
}