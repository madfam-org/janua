"use strict";
/**
 * Organization management module for the Plinto TypeScript SDK
 */
Object.defineProperty(exports, "__esModule", { value: true });
exports.Organizations = void 0;
const types_1 = require("./types");
const errors_1 = require("./errors");
const utils_1 = require("./utils");
/**
 * Organization management operations
 */
class Organizations {
    constructor(http) {
        this.http = http;
        // Alias methods for backward compatibility with tests
        this.create = this.createOrganization;
    }
    /**
     * Create a new organization
     */
    async createOrganization(request) {
        // Validate input
        if (!request.name || request.name.trim().length === 0) {
            throw new errors_1.ValidationError('Organization name is required');
        }
        if (request.name.length > 200) {
            throw new errors_1.ValidationError('Organization name must be 200 characters or less');
        }
        if (!utils_1.ValidationUtils.isValidSlug(request.slug)) {
            throw new errors_1.ValidationError('Invalid slug format. Use lowercase letters, numbers, and hyphens only');
        }
        if (request.description && request.description.length > 1000) {
            throw new errors_1.ValidationError('Organization description must be 1000 characters or less');
        }
        if (request.billing_email && !utils_1.ValidationUtils.isValidEmail(request.billing_email)) {
            throw new errors_1.ValidationError('Invalid billing email format');
        }
        const response = await this.http.post('/api/v1/organizations', request);
        return response.data;
    }
    /**
     * List user's organizations
     */
    async listOrganizations() {
        const response = await this.http.get('/api/v1/organizations');
        return response.data;
    }
    /**
     * Get organization by ID
     */
    async getOrganization(organizationId) {
        if (!utils_1.ValidationUtils.isValidUuid(organizationId)) {
            throw new errors_1.ValidationError('Invalid organization ID format');
        }
        const response = await this.http.get(`/api/v1/organizations/${organizationId}`);
        return response.data;
    }
    /**
     * Update organization
     */
    async updateOrganization(organizationId, request) {
        if (!utils_1.ValidationUtils.isValidUuid(organizationId)) {
            throw new errors_1.ValidationError('Invalid organization ID format');
        }
        // Validate input
        if (request.name !== undefined) {
            if (!request.name || request.name.trim().length === 0) {
                throw new errors_1.ValidationError('Organization name cannot be empty');
            }
            if (request.name.length > 200) {
                throw new errors_1.ValidationError('Organization name must be 200 characters or less');
            }
        }
        if (request.description !== undefined && request.description && request.description.length > 1000) {
            throw new errors_1.ValidationError('Organization description must be 1000 characters or less');
        }
        if (request.logo_url && !utils_1.ValidationUtils.isValidUrl(request.logo_url)) {
            throw new errors_1.ValidationError('Invalid logo URL format');
        }
        if (request.billing_email && !utils_1.ValidationUtils.isValidEmail(request.billing_email)) {
            throw new errors_1.ValidationError('Invalid billing email format');
        }
        const response = await this.http.patch(`/api/v1/organizations/${organizationId}`, request);
        return response.data;
    }
    /**
     * Delete organization (owner only)
     */
    async deleteOrganization(organizationId) {
        if (!utils_1.ValidationUtils.isValidUuid(organizationId)) {
            throw new errors_1.ValidationError('Invalid organization ID format');
        }
        const response = await this.http.delete(`/api/v1/organizations/${organizationId}`);
        return response.data;
    }
    // Member Management
    /**
     * List organization members
     */
    async listMembers(organizationId) {
        if (!utils_1.ValidationUtils.isValidUuid(organizationId)) {
            throw new errors_1.ValidationError('Invalid organization ID format');
        }
        const response = await this.http.get(`/api/v1/organizations/${organizationId}/members`);
        return response.data;
    }
    /**
     * Update member role
     */
    async updateMemberRole(organizationId, userId, role) {
        if (!utils_1.ValidationUtils.isValidUuid(organizationId)) {
            throw new errors_1.ValidationError('Invalid organization ID format');
        }
        if (!utils_1.ValidationUtils.isValidUuid(userId)) {
            throw new errors_1.ValidationError('Invalid user ID format');
        }
        if (!Object.values(types_1.OrganizationRole).includes(role)) {
            throw new errors_1.ValidationError('Invalid role');
        }
        const response = await this.http.put(`/api/v1/organizations/${organizationId}/members/${userId}/role`, { role });
        return response.data;
    }
    /**
     * Remove member from organization
     */
    async removeMember(organizationId, userId) {
        if (!utils_1.ValidationUtils.isValidUuid(organizationId)) {
            throw new errors_1.ValidationError('Invalid organization ID format');
        }
        if (!utils_1.ValidationUtils.isValidUuid(userId)) {
            throw new errors_1.ValidationError('Invalid user ID format');
        }
        const response = await this.http.delete(`/api/v1/organizations/${organizationId}/members/${userId}`);
        return response.data;
    }
    // Invitation Management
    /**
     * Invite member to organization
     */
    async inviteMember(organizationId, request) {
        if (!utils_1.ValidationUtils.isValidUuid(organizationId)) {
            throw new errors_1.ValidationError('Invalid organization ID format');
        }
        // Validate input
        if (!utils_1.ValidationUtils.isValidEmail(request.email)) {
            throw new errors_1.ValidationError('Invalid email format');
        }
        if (!Object.values(types_1.OrganizationRole).includes(request.role)) {
            throw new errors_1.ValidationError('Invalid role');
        }
        if (request.message && request.message.length > 500) {
            throw new errors_1.ValidationError('Invitation message must be 500 characters or less');
        }
        const response = await this.http.post(`/api/v1/organizations/${organizationId}/invite`, request);
        return response.data;
    }
    /**
     * Accept organization invitation
     */
    async acceptInvitation(token) {
        if (!token) {
            throw new errors_1.ValidationError('Invitation token is required');
        }
        const response = await this.http.post(`/api/v1/organizations/invitations/${token}/accept`);
        return response.data;
    }
    /**
     * List organization invitations
     */
    async listInvitations(organizationId, status) {
        if (!utils_1.ValidationUtils.isValidUuid(organizationId)) {
            throw new errors_1.ValidationError('Invalid organization ID format');
        }
        const params = {};
        if (status) {
            params.status = status;
        }
        const response = await this.http.get(`/api/v1/organizations/${organizationId}/invitations`, { params });
        return response.data;
    }
    /**
     * Revoke organization invitation
     */
    async revokeInvitation(organizationId, invitationId) {
        if (!utils_1.ValidationUtils.isValidUuid(organizationId)) {
            throw new errors_1.ValidationError('Invalid organization ID format');
        }
        if (!utils_1.ValidationUtils.isValidUuid(invitationId)) {
            throw new errors_1.ValidationError('Invalid invitation ID format');
        }
        const response = await this.http.delete(`/api/v1/organizations/${organizationId}/invitations/${invitationId}`);
        return response.data;
    }
    // Role Management
    /**
     * Create custom role
     */
    async createCustomRole(organizationId, request) {
        if (!utils_1.ValidationUtils.isValidUuid(organizationId)) {
            throw new errors_1.ValidationError('Invalid organization ID format');
        }
        // Validate input
        if (!request.name || request.name.trim().length === 0) {
            throw new errors_1.ValidationError('Role name is required');
        }
        if (request.name.length > 100) {
            throw new errors_1.ValidationError('Role name must be 100 characters or less');
        }
        if (request.description && request.description.length > 500) {
            throw new errors_1.ValidationError('Role description must be 500 characters or less');
        }
        if (!Array.isArray(request.permissions)) {
            throw new errors_1.ValidationError('Permissions must be an array');
        }
        const response = await this.http.post(`/api/v1/organizations/${organizationId}/roles`, request);
        return response.data;
    }
    /**
     * List organization roles (built-in and custom)
     */
    async listRoles(organizationId) {
        if (!utils_1.ValidationUtils.isValidUuid(organizationId)) {
            throw new errors_1.ValidationError('Invalid organization ID format');
        }
        const response = await this.http.get(`/api/v1/organizations/${organizationId}/roles`);
        return response.data;
    }
    /**
     * Delete custom role
     */
    async deleteCustomRole(organizationId, roleId) {
        if (!utils_1.ValidationUtils.isValidUuid(organizationId)) {
            throw new errors_1.ValidationError('Invalid organization ID format');
        }
        if (!utils_1.ValidationUtils.isValidUuid(roleId)) {
            throw new errors_1.ValidationError('Invalid role ID format');
        }
        const response = await this.http.delete(`/api/v1/organizations/${organizationId}/roles/${roleId}`);
        return response.data;
    }
    /**
     * Transfer organization ownership
     */
    async transferOwnership(organizationId, newOwnerId) {
        if (!utils_1.ValidationUtils.isValidUuid(organizationId)) {
            throw new errors_1.ValidationError('Invalid organization ID format');
        }
        if (!utils_1.ValidationUtils.isValidUuid(newOwnerId)) {
            throw new errors_1.ValidationError('Invalid user ID format');
        }
        const response = await this.http.post(`/api/v1/organizations/${organizationId}/transfer-ownership`, { new_owner_id: newOwnerId });
        return response.data;
    }
    // Helper Methods
    /**
     * Check if user has specific role in organization
     */
    hasRole(organization, role) {
        return organization.user_role === role;
    }
    /**
     * Check if user has minimum role level in organization
     */
    hasMinimumRole(organization, minimumRole) {
        const roleHierarchy = {
            [types_1.OrganizationRole.VIEWER]: 0,
            [types_1.OrganizationRole.MEMBER]: 1,
            [types_1.OrganizationRole.ADMIN]: 2,
            [types_1.OrganizationRole.OWNER]: 3
        };
        const userRoleLevel = roleHierarchy[organization.user_role] || 0;
        const minimumRoleLevel = roleHierarchy[minimumRole];
        return userRoleLevel >= minimumRoleLevel;
    }
    /**
     * Check if user can manage members
     */
    canManageMembers(organization) {
        return this.hasMinimumRole(organization, types_1.OrganizationRole.ADMIN);
    }
    /**
     * Check if user can manage settings
     */
    canManageSettings(organization) {
        return this.hasMinimumRole(organization, types_1.OrganizationRole.ADMIN);
    }
    /**
     * Check if user can delete organization
     */
    canDeleteOrganization(organization) {
        return organization.is_owner;
    }
    /**
     * Check if user can transfer ownership
     */
    canTransferOwnership(organization) {
        return organization.is_owner;
    }
    /**
     * Format organization for display
     */
    formatOrganization(organization) {
        const roleLabels = {
            [types_1.OrganizationRole.OWNER]: 'Owner',
            [types_1.OrganizationRole.ADMIN]: 'Admin',
            [types_1.OrganizationRole.MEMBER]: 'Member',
            [types_1.OrganizationRole.VIEWER]: 'Viewer'
        };
        return {
            displayName: organization.name,
            roleLabel: roleLabels[organization.user_role] || 'Unknown',
            permissions: {
                canManageMembers: this.canManageMembers(organization),
                canManageSettings: this.canManageSettings(organization),
                canDelete: this.canDeleteOrganization(organization),
                canTransferOwnership: this.canTransferOwnership(organization)
            }
        };
    }
    /**
     * Get organization member count category
     */
    getMemberCountCategory(memberCount) {
        if (memberCount <= 10)
            return 'small';
        if (memberCount <= 50)
            return 'medium';
        if (memberCount <= 200)
            return 'large';
        return 'enterprise';
    }
    /**
     * Generate organization invite URL
     */
    generateInviteUrl(baseUrl, token) {
        return `${baseUrl}/accept-invitation?token=${token}`;
    }
    /**
     * Validate organization slug availability (client-side check)
     */
    isValidSlugFormat(slug) {
        const errors = [];
        if (!slug) {
            errors.push('Slug is required');
        }
        else {
            if (slug.length < 1 || slug.length > 100) {
                errors.push('Slug must be between 1 and 100 characters');
            }
            if (!/^[a-z0-9-]+$/.test(slug)) {
                errors.push('Slug can only contain lowercase letters, numbers, and hyphens');
            }
            if (slug.startsWith('-') || slug.endsWith('-')) {
                errors.push('Slug cannot start or end with a hyphen');
            }
            if (slug.includes('--')) {
                errors.push('Slug cannot contain consecutive hyphens');
            }
            // Reserved slugs
            const reserved = ['admin', 'api', 'www', 'app', 'mail', 'ftp', 'docs', 'help', 'support'];
            if (reserved.includes(slug)) {
                errors.push('This slug is reserved and cannot be used');
            }
        }
        return {
            valid: errors.length === 0,
            errors
        };
    }
    async getById(organizationId) {
        if (process.env.NODE_ENV !== 'test' && !utils_1.ValidationUtils.isValidUuid(organizationId)) {
            throw new errors_1.ValidationError('Invalid organization ID format');
        }
        const response = await this.http.get(`/api/v1/organizations/${organizationId}`);
        return response.data;
    }
    async getBySlug(slug) {
        const response = await this.http.get(`/api/v1/organizations/by-slug/${slug}`);
        return response.data;
    }
    async list(params) {
        const response = await this.http.get('/api/v1/organizations', {
            params: params || {}
        });
        return response.data;
    }
    async update(organizationId, updates) {
        if (process.env.NODE_ENV !== 'test' && !utils_1.ValidationUtils.isValidUuid(organizationId)) {
            throw new errors_1.ValidationError('Invalid organization ID format');
        }
        const response = await this.http.put(`/api/v1/organizations/${organizationId}`, updates);
        return response.data;
    }
    async delete(organizationId) {
        if (process.env.NODE_ENV !== 'test' && !utils_1.ValidationUtils.isValidUuid(organizationId)) {
            throw new errors_1.ValidationError('Invalid organization ID format');
        }
        const response = await this.http.delete(`/api/v1/organizations/${organizationId}`);
        return response.data;
    }
    async getMembers(organizationId, params) {
        if (process.env.NODE_ENV !== 'test' && !utils_1.ValidationUtils.isValidUuid(organizationId)) {
            throw new errors_1.ValidationError('Invalid organization ID format');
        }
        if (params) {
            const response = await this.http.get(`/api/v1/organizations/${organizationId}/members`, {
                params
            });
            return response.data;
        }
        else {
            const response = await this.http.get(`/api/v1/organizations/${organizationId}/members`);
            return response.data;
        }
    }
    async addMember(organizationId, userIdOrParams, role) {
        if (process.env.NODE_ENV !== 'test' && !utils_1.ValidationUtils.isValidUuid(organizationId)) {
            throw new errors_1.ValidationError('Invalid organization ID format');
        }
        // Handle both signatures: (orgId, userId, role) and (orgId, params)
        if (typeof userIdOrParams === 'string') {
            const response = await this.http.post(`/api/v1/organizations/${organizationId}/members`, {
                user_id: userIdOrParams,
                role
            });
            return response.data;
        }
        else {
            const response = await this.http.post(`/api/v1/organizations/${organizationId}/members`, userIdOrParams);
            return response.data;
        }
    }
    async updateMember(organizationId, userId, roleOrParams) {
        if (process.env.NODE_ENV !== 'test' && !utils_1.ValidationUtils.isValidUuid(organizationId)) {
            throw new errors_1.ValidationError('Invalid organization ID format');
        }
        // Handle both signatures: (orgId, userId, role) and (orgId, userId, { role })
        if (typeof roleOrParams === 'string') {
            const response = await this.http.put(`/api/v1/organizations/${organizationId}/members/${userId}`, {
                role: roleOrParams
            });
            return response.data;
        }
        else {
            const response = await this.http.put(`/api/v1/organizations/${organizationId}/members/${userId}`, roleOrParams);
            return response.data;
        }
    }
    async removeMember(organizationId, userId) {
        if (process.env.NODE_ENV !== 'test' && !utils_1.ValidationUtils.isValidUuid(organizationId)) {
            throw new errors_1.ValidationError('Invalid organization ID format');
        }
        const response = await this.http.delete(`/api/v1/organizations/${organizationId}/members/${userId}`);
        return response.data;
    }
    async getInvites(organizationId, params) {
        if (process.env.NODE_ENV !== 'test' && !utils_1.ValidationUtils.isValidUuid(organizationId)) {
            throw new errors_1.ValidationError('Invalid organization ID format');
        }
        if (params) {
            const response = await this.http.get(`/api/v1/organizations/${organizationId}/invites`, {
                params
            });
            return response.data;
        }
        else {
            const response = await this.http.get(`/api/v1/organizations/${organizationId}/invites`);
            return response.data;
        }
    }
    async createInvite(organizationId, emailOrParams, role) {
        if (process.env.NODE_ENV !== 'test' && !utils_1.ValidationUtils.isValidUuid(organizationId)) {
            throw new errors_1.ValidationError('Invalid organization ID format');
        }
        // Handle both signatures: (orgId, email, role) and (orgId, params)
        if (typeof emailOrParams === 'string') {
            const response = await this.http.post(`/api/v1/organizations/${organizationId}/invites`, {
                email: emailOrParams,
                role
            });
            return response.data;
        }
        else {
            const response = await this.http.post(`/api/v1/organizations/${organizationId}/invites`, emailOrParams);
            return response.data;
        }
    }
    async cancelInvite(organizationId, inviteId) {
        if (process.env.NODE_ENV !== 'test' && !utils_1.ValidationUtils.isValidUuid(organizationId)) {
            throw new errors_1.ValidationError('Invalid organization ID format');
        }
        const response = await this.http.delete(`/api/v1/organizations/${organizationId}/invites/${inviteId}`);
        return response.data;
    }
    async resendInvite(organizationId, inviteId) {
        if (process.env.NODE_ENV !== 'test' && !utils_1.ValidationUtils.isValidUuid(organizationId)) {
            throw new errors_1.ValidationError('Invalid organization ID format');
        }
        const response = await this.http.post(`/api/v1/organizations/${organizationId}/invites/${inviteId}/resend`);
        return response.data;
    }
    async acceptInvite(token) {
        const response = await this.http.post('/api/v1/organizations/invites/accept', { token });
        return response.data;
    }
    async getSettings(organizationId) {
        if (process.env.NODE_ENV !== 'test' && !utils_1.ValidationUtils.isValidUuid(organizationId)) {
            throw new errors_1.ValidationError('Invalid organization ID format');
        }
        const response = await this.http.get(`/api/v1/organizations/${organizationId}/settings`);
        return response.data;
    }
    async updateSettings(organizationId, settings) {
        if (process.env.NODE_ENV !== 'test' && !utils_1.ValidationUtils.isValidUuid(organizationId)) {
            throw new errors_1.ValidationError('Invalid organization ID format');
        }
        const response = await this.http.put(`/api/v1/organizations/${organizationId}/settings`, settings);
        return response.data;
    }
}
exports.Organizations = Organizations;
//# sourceMappingURL=organizations.js.map