"use strict";
/**
 * Admin operations module for the Plinto TypeScript SDK
 */
Object.defineProperty(exports, "__esModule", { value: true });
exports.Admin = void 0;
const types_1 = require("./types");
const errors_1 = require("./errors");
const utils_1 = require("./utils");
/**
 * Administrative operations (admin only)
 */
class Admin {
    constructor(http) {
        this.http = http;
    }
    /**
     * Get system statistics
     */
    async getStats() {
        const response = await this.http.get('/api/v1/admin/stats');
        return response.data;
    }
    /**
     * Get system health status
     */
    async getSystemHealth() {
        const response = await this.http.get('/api/v1/admin/health');
        return response.data;
    }
    /**
     * Get system configuration
     */
    async getSystemConfig() {
        const response = await this.http.get('/api/v1/admin/config');
        return response.data;
    }
    // User Management
    /**
     * List all users (admin only)
     */
    async listAllUsers(params) {
        // Validate pagination parameters
        if (params?.page && params.page < 1) {
            throw new errors_1.ValidationError('Page must be greater than 0');
        }
        if (params?.per_page && (params.per_page < 1 || params.per_page > 100)) {
            throw new errors_1.ValidationError('Per page must be between 1 and 100');
        }
        const response = await this.http.get('/api/v1/admin/users', {
            params: params || {}
        });
        // Since the API returns an array, we need to simulate pagination
        const users = response.data;
        const page = params?.page || 1;
        const perPage = params?.per_page || 20;
        return {
            data: users,
            total: users.length,
            page,
            per_page: perPage,
            total_pages: Math.ceil(users.length / perPage)
        };
    }
    /**
     * Update user as admin
     */
    async updateUser(userId, updates) {
        if (!utils_1.ValidationUtils.isValidUuid(userId)) {
            throw new errors_1.ValidationError('Invalid user ID format');
        }
        // Validate status if provided
        if (updates.status && !Object.values(types_1.UserStatus).includes(updates.status)) {
            throw new errors_1.ValidationError('Invalid user status');
        }
        const response = await this.http.patch(`/api/v1/admin/users/${userId}`, updates);
        return response.data;
    }
    /**
     * Delete user as admin
     */
    async deleteUser(userId, permanent = false) {
        if (!utils_1.ValidationUtils.isValidUuid(userId)) {
            throw new errors_1.ValidationError('Invalid user ID format');
        }
        const response = await this.http.delete(`/api/v1/admin/users/${userId}`, {
            params: { permanent }
        });
        return response.data;
    }
    // Organization Management
    /**
     * List all organizations (admin only)
     */
    async listAllOrganizations(params) {
        // Validate pagination parameters
        if (params?.page && params.page < 1) {
            throw new errors_1.ValidationError('Page must be greater than 0');
        }
        if (params?.per_page && (params.per_page < 1 || params.per_page > 100)) {
            throw new errors_1.ValidationError('Per page must be between 1 and 100');
        }
        const response = await this.http.get('/api/v1/admin/organizations', {
            params: params || {}
        });
        // Since the API returns an array, we need to simulate pagination
        const organizations = response.data;
        const page = params?.page || 1;
        const perPage = params?.per_page || 20;
        return {
            data: organizations,
            total: organizations.length,
            page,
            per_page: perPage,
            total_pages: Math.ceil(organizations.length / perPage)
        };
    }
    /**
     * Delete organization as admin
     */
    async deleteOrganization(organizationId) {
        if (!utils_1.ValidationUtils.isValidUuid(organizationId)) {
            throw new errors_1.ValidationError('Invalid organization ID format');
        }
        const response = await this.http.delete(`/api/v1/admin/organizations/${organizationId}`);
        return response.data;
    }
    // Activity Logs
    /**
     * Get activity logs
     */
    async getActivityLogs(options) {
        // Validate parameters
        if (options?.page && options.page < 1) {
            throw new errors_1.ValidationError('Page must be greater than 0');
        }
        if (options?.per_page && (options.per_page < 1 || options.per_page > 200)) {
            throw new errors_1.ValidationError('Per page must be between 1 and 200');
        }
        if (options?.user_id && !utils_1.ValidationUtils.isValidUuid(options.user_id)) {
            throw new errors_1.ValidationError('Invalid user ID format');
        }
        if (options?.start_date && isNaN(Date.parse(options.start_date))) {
            throw new errors_1.ValidationError('Invalid start date format');
        }
        if (options?.end_date && isNaN(Date.parse(options.end_date))) {
            throw new errors_1.ValidationError('Invalid end date format');
        }
        const response = await this.http.get('/api/v1/admin/activity-logs', {
            params: options || {}
        });
        // Since the API returns an array, we need to simulate pagination
        const logs = response.data;
        const page = options?.page || 1;
        const perPage = options?.per_page || 50;
        return {
            data: logs,
            total: logs.length,
            page,
            per_page: perPage,
            total_pages: Math.ceil(logs.length / perPage)
        };
    }
    // Session Management
    /**
     * Revoke all sessions (optionally for specific user)
     */
    async revokeAllSessions(userId) {
        if (userId && !utils_1.ValidationUtils.isValidUuid(userId)) {
            throw new errors_1.ValidationError('Invalid user ID format');
        }
        const response = await this.http.post('/api/v1/admin/sessions/revoke-all', {
            user_id: userId
        });
        return response.data;
    }
    /**
     * Toggle maintenance mode
     */
    async toggleMaintenanceMode(enabled, message) {
        const response = await this.http.post('/api/v1/admin/maintenance-mode', {
            enabled,
            message
        });
        return response.data;
    }
    // Helper Methods
    /**
     * Format user status for display
     */
    formatUserStatus(status) {
        switch (status) {
            case types_1.UserStatus.ACTIVE:
                return {
                    label: 'Active',
                    color: 'green',
                    description: 'User account is active and can sign in'
                };
            case types_1.UserStatus.SUSPENDED:
                return {
                    label: 'Suspended',
                    color: 'yellow',
                    description: 'User account is suspended and cannot sign in'
                };
            case types_1.UserStatus.DELETED:
                return {
                    label: 'Deleted',
                    color: 'red',
                    description: 'User account has been deleted'
                };
            default:
                return {
                    label: 'Unknown',
                    color: 'gray',
                    description: 'Unknown user status'
                };
        }
    }
    /**
     * Calculate system health score
     */
    calculateHealthScore(health) {
        const services = ['database', 'cache', 'storage', 'email'];
        const healthyServices = services.filter(service => health[service] === 'healthy');
        const score = (healthyServices.length / services.length) * 100;
        const issues = [];
        services.forEach(service => {
            const status = health[service];
            if (status !== 'healthy') {
                issues.push(`${service} is ${status}`);
            }
        });
        let status;
        if (score === 100)
            status = 'healthy';
        else if (score >= 75)
            status = 'degraded';
        else
            status = 'unhealthy';
        return { score, status, issues };
    }
    /**
     * Format statistics for dashboard
     */
    formatStats(stats) {
        const mfaAdoption = stats.total_users > 0 ? (stats.mfa_enabled_users / stats.total_users) * 100 : 0;
        return {
            userGrowth: {
                total: stats.total_users,
                active: stats.active_users,
                recent: stats.users_last_24h,
                growthRate: stats.total_users > 0 ? (stats.users_last_24h / stats.total_users) * 100 : 0
            },
            security: {
                mfaAdoption: Math.round(mfaAdoption * 100) / 100,
                oauthAccounts: stats.oauth_accounts,
                passkeysRegistered: stats.passkeys_registered
            },
            activity: {
                totalSessions: stats.total_sessions,
                activeSessions: stats.active_sessions,
                recentSessions: stats.sessions_last_24h
            }
        };
    }
    /**
     * Get organization size category
     */
    getOrganizationSizeCategory(memberCount) {
        if (memberCount <= 5) {
            return {
                category: 'startup',
                label: 'Startup',
                description: '1-5 members'
            };
        }
        else if (memberCount <= 25) {
            return {
                category: 'small',
                label: 'Small',
                description: '6-25 members'
            };
        }
        else if (memberCount <= 100) {
            return {
                category: 'medium',
                label: 'Medium',
                description: '26-100 members'
            };
        }
        else if (memberCount <= 500) {
            return {
                category: 'large',
                label: 'Large',
                description: '101-500 members'
            };
        }
        else {
            return {
                category: 'enterprise',
                label: 'Enterprise',
                description: '500+ members'
            };
        }
    }
}
exports.Admin = Admin;
//# sourceMappingURL=admin.js.map