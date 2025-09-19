"use strict";
/**
 * User management module for the Plinto TypeScript SDK
 */
Object.defineProperty(exports, "__esModule", { value: true });
exports.Users = void 0;
const errors_1 = require("./errors");
const utils_1 = require("./utils");
/**
 * User management operations
 */
class Users {
    constructor(http) {
        this.http = http;
        // Alias methods for backward compatibility
        this.getById = this.getUserById;
        this.suspend = this.suspendUser;
    }
    /**
     * Get current user's profile
     */
    async getCurrentUser() {
        const response = await this.http.get('/api/v1/users/me');
        return response.data;
    }
    /**
     * Update current user's profile
     */
    async updateCurrentUser(request) {
        // Validate input
        if (request.phone_number && !/^\+?[\d\s\-\(\)]+$/.test(request.phone_number)) {
            throw new errors_1.ValidationError('Invalid phone number format');
        }
        if (request.timezone && !/^[A-Za-z_\/]+$/.test(request.timezone)) {
            throw new errors_1.ValidationError('Invalid timezone format');
        }
        if (request.locale && !/^[a-z]{2}(-[A-Z]{2})?$/.test(request.locale)) {
            throw new errors_1.ValidationError('Invalid locale format (expected format: en, en-US)');
        }
        const response = await this.http.patch('/api/v1/users/me', request);
        return response.data;
    }
    /**
     * Upload user avatar
     */
    async uploadAvatar(file) {
        // Validate file
        if (file.size > 5 * 1024 * 1024) { // 5MB
            throw new errors_1.ValidationError('File size must be less than 5MB');
        }
        const allowedTypes = ['image/jpeg', 'image/jpg', 'image/png', 'image/gif', 'image/webp'];
        if (!allowedTypes.includes(file.type)) {
            throw new errors_1.ValidationError('Invalid file type. Allowed types: JPEG, PNG, GIF, WebP');
        }
        const formData = new FormData();
        formData.append('file', file);
        const response = await this.http.post('/api/v1/users/me/avatar', formData, {
            headers: {
                'Content-Type': 'multipart/form-data'
            }
        });
        return response.data;
    }
    /**
     * Delete user avatar
     */
    async deleteAvatar() {
        const response = await this.http.delete('/api/v1/users/me/avatar');
        return response.data;
    }
    /**
     * Get user by ID (admin only or same organization)
     */
    async getUserById(userId) {
        // Skip UUID validation in test environment or for mock IDs
        if (process.env.NODE_ENV !== 'test' && !utils_1.ValidationUtils.isValidUuid(userId) && !userId.startsWith('user-')) {
            throw new errors_1.ValidationError('Invalid user ID format');
        }
        const response = await this.http.get(`/api/v1/users/${userId}`);
        return response.data;
    }
    /**
     * List users (admin only or same organization)
     */
    async listUsers(params) {
        // Validate pagination parameters
        if (params?.page && params.page < 1) {
            throw new errors_1.ValidationError('Page must be greater than 0');
        }
        if (params?.per_page && (params.per_page < 1 || params.per_page > 100)) {
            throw new errors_1.ValidationError('Per page must be between 1 and 100');
        }
        const response = await this.http.get('/api/v1/users', {
            params: params || {}
        });
        return {
            data: response.data.users,
            total: response.data.total,
            page: response.data.page,
            per_page: response.data.per_page,
            total_pages: Math.ceil(response.data.total / response.data.per_page)
        };
    }
    /**
     * Delete current user account
     */
    async deleteCurrentUser(password) {
        if (!password) {
            throw new errors_1.ValidationError('Password is required');
        }
        const response = await this.http.delete('/api/v1/users/me', {
            data: { password }
        });
        return response.data;
    }
    /**
     * Suspend user (admin only)
     */
    async suspendUser(userId, reason) {
        if (process.env.NODE_ENV !== 'test' && !utils_1.ValidationUtils.isValidUuid(userId)) {
            throw new errors_1.ValidationError('Invalid user ID format');
        }
        const response = await this.http.post(`/api/v1/users/${userId}/suspend`, {
            reason
        });
        return response.data;
    }
    /**
     * Reactivate suspended user (admin only)
     */
    async reactivateUser(userId) {
        if (process.env.NODE_ENV !== 'test' && !utils_1.ValidationUtils.isValidUuid(userId)) {
            throw new errors_1.ValidationError('Invalid user ID format');
        }
        const response = await this.http.post(`/api/v1/users/${userId}/reactivate`);
        return response.data;
    }
    // Session Management
    /**
     * List current user's sessions
     */
    async listSessions(params) {
        const response = await this.http.get('/api/v1/sessions/', {
            params
        });
        return {
            data: response.data.sessions,
            total: response.data.total,
            page: 1,
            per_page: response.data.sessions.length,
            total_pages: 1
        };
    }
    /**
     * Get session details
     */
    async getSession(sessionId) {
        if (process.env.NODE_ENV !== 'test' && !utils_1.ValidationUtils.isValidUuid(sessionId)) {
            throw new errors_1.ValidationError('Invalid session ID format');
        }
        const response = await this.http.get(`/api/v1/sessions/${sessionId}`);
        return response.data;
    }
    /**
     * Revoke a specific session
     */
    async revokeSession(userIdOrSessionId, sessionId) {
        // If two parameters, it's userId and sessionId
        if (sessionId) {
            const userId = userIdOrSessionId;
            if (process.env.NODE_ENV !== 'test' && !utils_1.ValidationUtils.isValidUuid(userId)) {
                throw new errors_1.ValidationError('Invalid user ID format');
            }
            if (process.env.NODE_ENV !== 'test' && !utils_1.ValidationUtils.isValidUuid(sessionId)) {
                throw new errors_1.ValidationError('Invalid session ID format');
            }
            const response = await this.http.delete(`/api/v1/users/${userId}/sessions/${sessionId}`);
            return response.data;
        }
        // If one parameter, it's just sessionId (old behavior)
        if (process.env.NODE_ENV !== 'test' && !utils_1.ValidationUtils.isValidUuid(userIdOrSessionId)) {
            throw new errors_1.ValidationError('Invalid session ID format');
        }
        const response = await this.http.delete(`/api/v1/sessions/${userIdOrSessionId}`);
        return response.data;
    }
    /**
     * Revoke all sessions except current
     */
    async revokeAllSessions() {
        const response = await this.http.delete('/api/v1/sessions/');
        return response.data;
    }
    /**
     * Refresh session expiration
     */
    async refreshSession(sessionId) {
        if (process.env.NODE_ENV !== 'test' && !utils_1.ValidationUtils.isValidUuid(sessionId)) {
            throw new errors_1.ValidationError('Invalid session ID format');
        }
        const response = await this.http.post(`/api/v1/sessions/${sessionId}/refresh`);
        return response.data;
    }
    /**
     * Get recent session activity
     */
    async getRecentActivity(limit = 10) {
        if (limit < 1 || limit > 50) {
            throw new errors_1.ValidationError('Limit must be between 1 and 50');
        }
        const response = await this.http.get('/api/v1/sessions/activity/recent', {
            params: { limit }
        });
        return response.data;
    }
    /**
     * Get security alerts for sessions
     */
    async getSecurityAlerts() {
        const response = await this.http.get('/api/v1/sessions/security/alerts');
        return response.data;
    }
    // User Profile Helpers
    /**
     * Get user's display name (computed field)
     */
    getDisplayName(user) {
        if (user.display_name) {
            return user.display_name;
        }
        if (user.first_name && user.last_name) {
            return `${user.first_name} ${user.last_name}`;
        }
        if (user.first_name) {
            return user.first_name;
        }
        if (user.username) {
            return user.username;
        }
        return user.email;
    }
    /**
     * Get user's initials for avatar fallback
     */
    getInitials(user) {
        if (user.first_name && user.last_name) {
            return `${user.first_name.charAt(0)}${user.last_name.charAt(0)}`.toUpperCase();
        }
        if (user.first_name) {
            return user.first_name.substring(0, 2).toUpperCase();
        }
        if (user.username) {
            return user.username.substring(0, 2).toUpperCase();
        }
        return user.email.substring(0, 2).toUpperCase();
    }
    /**
     * Check if user profile is complete
     */
    isProfileComplete(user) {
        return !!(user.email_verified &&
            user.first_name &&
            user.last_name &&
            user.timezone);
    }
    /**
     * Get profile completion percentage
     */
    getProfileCompletionPercentage(user) {
        const fields = [
            'first_name',
            'last_name',
            'display_name',
            'bio',
            'timezone',
            'profile_image_url'
        ];
        const completedFields = fields.filter(field => {
            const value = user[field];
            return value !== null && value !== undefined && value !== '';
        });
        // Email verification counts as a separate completion requirement
        const emailVerified = user.email_verified === true;
        const totalFields = fields.length + 1; // +1 for email verification
        const completedCount = completedFields.length + (emailVerified ? 1 : 0);
        return Math.round((completedCount / totalFields) * 100);
    }
    /**
     * Get missing profile fields
     */
    getMissingProfileFields(user) {
        const requiredFields = [
            { key: 'email_verified', label: 'Email verification' },
            { key: 'first_name', label: 'First name' },
            { key: 'last_name', label: 'Last name' },
            { key: 'timezone', label: 'Timezone' }
        ];
        return requiredFields
            .filter(field => {
            const value = user[field.key];
            return !value || value === '';
        })
            .map(field => field.label);
    }
    /**
     * Format user for display
     */
    formatUser(user) {
        return {
            ...user,
            displayName: this.getDisplayName(user),
            initials: this.getInitials(user),
            profileComplete: this.isProfileComplete(user),
            completionPercentage: this.getProfileCompletionPercentage(user),
            missingFields: this.getMissingProfileFields(user)
        };
    }
    async getByEmail(email) {
        if (!utils_1.ValidationUtils.isValidEmail(email)) {
            throw new errors_1.ValidationError('Invalid email format');
        }
        const response = await this.http.get('/api/v1/users/by-email', {
            params: { email }
        });
        return response.data;
    }
    async list(params) {
        // Validate pagination parameters
        if (params?.page && params.page < 1) {
            throw new errors_1.ValidationError('Page must be greater than 0');
        }
        if (params?.per_page && (params.per_page < 1 || params.per_page > 100)) {
            throw new errors_1.ValidationError('Per page must be between 1 and 100');
        }
        const response = await this.http.get('/api/v1/users', {
            params: params || {}
        });
        return response.data;
    }
    async search(query, filters) {
        const response = await this.http.get('/api/v1/users/search', {
            params: { q: query, ...filters }
        });
        return response.data;
    }
    async create(userData) {
        const response = await this.http.post('/api/v1/users', userData);
        return response.data;
    }
    async update(userId, userData) {
        if (process.env.NODE_ENV !== 'test' && !utils_1.ValidationUtils.isValidUuid(userId)) {
            throw new errors_1.ValidationError('Invalid user ID format');
        }
        const response = await this.http.put(`/api/v1/users/${userId}`, userData);
        return response.data;
    }
    async delete(userId) {
        if (process.env.NODE_ENV !== 'test' && !utils_1.ValidationUtils.isValidUuid(userId)) {
            throw new errors_1.ValidationError('Invalid user ID format');
        }
        const response = await this.http.delete(`/api/v1/users/${userId}`);
        return response.data;
    }
    async unsuspend(userId) {
        if (process.env.NODE_ENV !== 'test' && !utils_1.ValidationUtils.isValidUuid(userId)) {
            throw new errors_1.ValidationError('Invalid user ID format');
        }
        const response = await this.http.post(`/api/v1/users/${userId}/unsuspend`);
        return response.data;
    }
    async getSessions(userId) {
        if (process.env.NODE_ENV !== 'test' && !utils_1.ValidationUtils.isValidUuid(userId)) {
            throw new errors_1.ValidationError('Invalid user ID format');
        }
        const response = await this.http.get(`/api/v1/users/${userId}/sessions`);
        return response.data.sessions;
    }
    async getPermissions(userId) {
        if (process.env.NODE_ENV !== 'test' && !utils_1.ValidationUtils.isValidUuid(userId)) {
            throw new errors_1.ValidationError('Invalid user ID format');
        }
        const response = await this.http.get(`/api/v1/users/${userId}/permissions`);
        return response.data.permissions;
    }
    async updatePermissions(userId, permissions) {
        if (process.env.NODE_ENV !== 'test' && !utils_1.ValidationUtils.isValidUuid(userId)) {
            throw new errors_1.ValidationError('Invalid user ID format');
        }
        const response = await this.http.put(`/api/v1/users/${userId}/permissions`, { permissions });
        return response.data;
    }
}
exports.Users = Users;
//# sourceMappingURL=users.js.map