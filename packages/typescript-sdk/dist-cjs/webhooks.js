"use strict";
/**
 * Webhook management module for the Plinto TypeScript SDK
 */
Object.defineProperty(exports, "__esModule", { value: true });
exports.Webhooks = void 0;
const types_1 = require("./types");
const errors_1 = require("./errors");
const utils_1 = require("./utils");
/**
 * Webhook management operations
 */
class Webhooks {
    constructor(http) {
        this.http = http;
    }
    /**
     * Create a new webhook endpoint
     */
    async createEndpoint(request) {
        // Validate input
        if (!utils_1.ValidationUtils.isValidUrl(request.url)) {
            throw new errors_1.ValidationError('Invalid webhook URL format');
        }
        if (!request.events || request.events.length === 0) {
            throw new errors_1.ValidationError('At least one event type must be specified');
        }
        // Validate event types
        const validEvents = Object.values(types_1.WebhookEventType);
        const invalidEvents = request.events.filter(event => !validEvents.includes(event));
        if (invalidEvents.length > 0) {
            throw new errors_1.ValidationError(`Invalid event types: ${invalidEvents.join(', ')}`);
        }
        if (request.description && request.description.length > 500) {
            throw new errors_1.ValidationError('Description must be 500 characters or less');
        }
        // Validate custom headers
        if (request.headers) {
            const invalidHeaders = Object.keys(request.headers).filter(key => key.toLowerCase().startsWith('authorization') ||
                key.toLowerCase().startsWith('x-webhook'));
            if (invalidHeaders.length > 0) {
                throw new errors_1.ValidationError(`Reserved header names cannot be used: ${invalidHeaders.join(', ')}`);
            }
        }
        const response = await this.http.post('/api/v1/webhooks/', request);
        return response.data;
    }
    /**
     * List webhook endpoints for current user
     */
    async listEndpoints(isActive) {
        const params = {};
        if (isActive !== undefined) {
            params.is_active = isActive;
        }
        const response = await this.http.get('/api/v1/webhooks/', { params });
        return response.data;
    }
    /**
     * Get webhook endpoint details
     */
    async getEndpoint(endpointId) {
        if (!utils_1.ValidationUtils.isValidUuid(endpointId)) {
            throw new errors_1.ValidationError('Invalid endpoint ID format');
        }
        const response = await this.http.get(`/api/v1/webhooks/${endpointId}`);
        return response.data;
    }
    /**
     * Update webhook endpoint
     */
    async updateEndpoint(endpointId, request) {
        if (!utils_1.ValidationUtils.isValidUuid(endpointId)) {
            throw new errors_1.ValidationError('Invalid endpoint ID format');
        }
        // Validate input
        if (request.url && !utils_1.ValidationUtils.isValidUrl(request.url)) {
            throw new errors_1.ValidationError('Invalid webhook URL format');
        }
        if (request.events) {
            if (request.events.length === 0) {
                throw new errors_1.ValidationError('At least one event type must be specified');
            }
            const validEvents = Object.values(types_1.WebhookEventType);
            const invalidEvents = request.events.filter(event => !validEvents.includes(event));
            if (invalidEvents.length > 0) {
                throw new errors_1.ValidationError(`Invalid event types: ${invalidEvents.join(', ')}`);
            }
        }
        if (request.description && request.description.length > 500) {
            throw new errors_1.ValidationError('Description must be 500 characters or less');
        }
        if (request.headers) {
            const invalidHeaders = Object.keys(request.headers).filter(key => key.toLowerCase().startsWith('authorization') ||
                key.toLowerCase().startsWith('x-webhook'));
            if (invalidHeaders.length > 0) {
                throw new errors_1.ValidationError(`Reserved header names cannot be used: ${invalidHeaders.join(', ')}`);
            }
        }
        const response = await this.http.patch(`/api/v1/webhooks/${endpointId}`, request);
        return response.data;
    }
    /**
     * Delete webhook endpoint
     */
    async deleteEndpoint(endpointId) {
        if (!utils_1.ValidationUtils.isValidUuid(endpointId)) {
            throw new errors_1.ValidationError('Invalid endpoint ID format');
        }
        const response = await this.http.delete(`/api/v1/webhooks/${endpointId}`);
        return response.data;
    }
    /**
     * Test webhook endpoint
     */
    async testEndpoint(endpointId) {
        if (!utils_1.ValidationUtils.isValidUuid(endpointId)) {
            throw new errors_1.ValidationError('Invalid endpoint ID format');
        }
        const response = await this.http.post(`/api/v1/webhooks/${endpointId}/test`);
        return response.data;
    }
    /**
     * Get webhook endpoint statistics
     */
    async getEndpointStats(endpointId, days = 7) {
        if (!utils_1.ValidationUtils.isValidUuid(endpointId)) {
            throw new errors_1.ValidationError('Invalid endpoint ID format');
        }
        if (days < 1 || days > 90) {
            throw new errors_1.ValidationError('Days must be between 1 and 90');
        }
        const response = await this.http.get(`/api/v1/webhooks/${endpointId}/stats`, {
            params: { days }
        });
        return response.data;
    }
    /**
     * List webhook events for an endpoint
     */
    async listEvents(endpointId, options) {
        if (!utils_1.ValidationUtils.isValidUuid(endpointId)) {
            throw new errors_1.ValidationError('Invalid endpoint ID format');
        }
        const params = {};
        if (options?.limit !== undefined) {
            if (options.limit < 1 || options.limit > 1000) {
                throw new errors_1.ValidationError('Limit must be between 1 and 1000');
            }
            params.limit = options.limit;
        }
        if (options?.offset !== undefined) {
            if (options.offset < 0) {
                throw new errors_1.ValidationError('Offset must be non-negative');
            }
            params.offset = options.offset;
        }
        const response = await this.http.get(`/api/v1/webhooks/${endpointId}/events`, { params });
        return response.data;
    }
    /**
     * List webhook delivery attempts for an endpoint
     */
    async listDeliveries(endpointId, options) {
        if (!utils_1.ValidationUtils.isValidUuid(endpointId)) {
            throw new errors_1.ValidationError('Invalid endpoint ID format');
        }
        const params = {};
        if (options?.limit !== undefined) {
            if (options.limit < 1 || options.limit > 1000) {
                throw new errors_1.ValidationError('Limit must be between 1 and 1000');
            }
            params.limit = options.limit;
        }
        if (options?.offset !== undefined) {
            if (options.offset < 0) {
                throw new errors_1.ValidationError('Offset must be non-negative');
            }
            params.offset = options.offset;
        }
        const response = await this.http.get(`/api/v1/webhooks/${endpointId}/deliveries`, {
            params
        });
        return response.data;
    }
    /**
     * Regenerate webhook endpoint secret
     */
    async regenerateSecret(endpointId) {
        if (!utils_1.ValidationUtils.isValidUuid(endpointId)) {
            throw new errors_1.ValidationError('Invalid endpoint ID format');
        }
        const response = await this.http.post(`/api/v1/webhooks/${endpointId}/regenerate-secret`);
        return response.data;
    }
    /**
     * Get available webhook event types
     */
    async getEventTypes() {
        const response = await this.http.get('/api/v1/webhooks/events/types');
        return response.data;
    }
    /**
     * Verify webhook signature (for testing)
     */
    async verifySignature(secret, payload, signature) {
        if (!secret || !payload || !signature) {
            throw new errors_1.ValidationError('Secret, payload, and signature are all required');
        }
        const response = await this.http.post('/api/v1/webhooks/verify-signature', {
            secret,
            payload,
            signature
        });
        return response.data;
    }
    // Client-side utilities
    /**
     * Verify webhook signature (client-side)
     */
    async verifyWebhookSignature(payload, signature, secret) {
        try {
            // Validate inputs
            if (!payload || !signature || !secret) {
                return false;
            }
            // Remove 'sha256=' prefix if present
            const cleanSignature = signature.replace(/^sha256=/, '');
            // In browser environment, use Web Crypto API
            if (typeof window !== 'undefined' && window.crypto && window.crypto.subtle) {
                const encoder = new TextEncoder();
                const keyData = encoder.encode(secret);
                const payloadData = encoder.encode(payload);
                const cryptoKey = await window.crypto.subtle.importKey('raw', keyData, { name: 'HMAC', hash: 'SHA-256' }, false, ['sign']);
                const signature_buffer = await window.crypto.subtle.sign('HMAC', cryptoKey, payloadData);
                const computed_signature = Array.from(new Uint8Array(signature_buffer))
                    .map(byte => byte.toString(16).padStart(2, '0'))
                    .join('');
                return computed_signature === cleanSignature;
            }
            // In Node.js environment, delegate to server verification
            // For server environments, verify signature directly
            const timestamp = new Date().getTime() / 1000;
            const expectedSignature = WebhookUtils.calculateSignature(timestamp.toString(), JSON.stringify(payload), secret);
            return signature === expectedSignature;
        }
        catch (error) {
            throw new errors_1.WebhookError('Failed to verify webhook signature', { originalError: error });
        }
    }
    /**
     * Parse webhook payload
     */
    parseWebhookPayload(payload) {
        try {
            const parsed = JSON.parse(payload);
            if (!parsed.event || !parsed.data || !parsed.timestamp || !parsed.id) {
                throw new errors_1.WebhookError('Invalid webhook payload format');
            }
            if (!Object.values(types_1.WebhookEventType).includes(parsed.event)) {
                throw new errors_1.WebhookError(`Unknown webhook event type: ${parsed.event}`);
            }
            return parsed;
        }
        catch (error) {
            if (error instanceof errors_1.WebhookError) {
                throw error;
            }
            throw new errors_1.WebhookError('Failed to parse webhook payload', { originalError: error });
        }
    }
    /**
     * Validate webhook endpoint URL
     */
    validateEndpointUrl(url) {
        const errors = [];
        if (!url) {
            errors.push('URL is required');
            return { valid: false, errors };
        }
        if (!utils_1.ValidationUtils.isValidUrl(url)) {
            errors.push('Invalid URL format');
            return { valid: false, errors };
        }
        try {
            const urlObj = new URL(url);
            // Must use HTTPS in production
            if (urlObj.protocol !== 'https:' && urlObj.protocol !== 'http:') {
                errors.push('URL must use HTTP or HTTPS protocol');
            }
            // Recommend HTTPS
            if (urlObj.protocol === 'http:') {
                errors.push('HTTPS is recommended for webhook endpoints');
            }
            // Check for localhost/private IPs in production
            const hostname = urlObj.hostname;
            if (hostname === 'localhost' || hostname === '127.0.0.1' || hostname.endsWith('.local')) {
                errors.push('Localhost URLs are not recommended for production webhooks');
            }
            // Check for standard webhook path
            if (!urlObj.pathname.includes('webhook')) {
                errors.push('Consider using a path that includes "webhook" for clarity');
            }
        }
        catch (error) {
            errors.push('Invalid URL format');
        }
        return {
            valid: errors.length === 0,
            errors
        };
    }
    /**
     * Get webhook event categories
     */
    getEventCategories() {
        return {
            user: [
                types_1.WebhookEventType.USER_CREATED,
                types_1.WebhookEventType.USER_UPDATED,
                types_1.WebhookEventType.USER_DELETED,
                types_1.WebhookEventType.USER_SIGNED_IN,
                types_1.WebhookEventType.USER_SIGNED_OUT
            ],
            session: [
                types_1.WebhookEventType.SESSION_CREATED,
                types_1.WebhookEventType.SESSION_EXPIRED
            ],
            organization: [
                types_1.WebhookEventType.ORGANIZATION_CREATED,
                types_1.WebhookEventType.ORGANIZATION_UPDATED,
                types_1.WebhookEventType.ORGANIZATION_DELETED,
                types_1.WebhookEventType.ORGANIZATION_MEMBER_ADDED,
                types_1.WebhookEventType.ORGANIZATION_MEMBER_REMOVED
            ]
        };
    }
    /**
     * Get friendly event type names
     */
    getEventTypeNames() {
        return {
            [types_1.WebhookEventType.USER_CREATED]: 'User Created',
            [types_1.WebhookEventType.USER_UPDATED]: 'User Updated',
            [types_1.WebhookEventType.USER_DELETED]: 'User Deleted',
            [types_1.WebhookEventType.USER_SIGNED_IN]: 'User Signed In',
            [types_1.WebhookEventType.USER_SIGNED_OUT]: 'User Signed Out',
            [types_1.WebhookEventType.SESSION_CREATED]: 'Session Created',
            [types_1.WebhookEventType.SESSION_EXPIRED]: 'Session Expired',
            [types_1.WebhookEventType.ORGANIZATION_CREATED]: 'Organization Created',
            [types_1.WebhookEventType.ORGANIZATION_UPDATED]: 'Organization Updated',
            [types_1.WebhookEventType.ORGANIZATION_DELETED]: 'Organization Deleted',
            [types_1.WebhookEventType.ORGANIZATION_MEMBER_ADDED]: 'Organization Member Added',
            [types_1.WebhookEventType.ORGANIZATION_MEMBER_REMOVED]: 'Organization Member Removed'
        };
    }
    /**
     * Calculate delivery success rate
     */
    calculateSuccessRate(stats) {
        if (stats.total_deliveries === 0) {
            return { rate: 0, status: 'poor' };
        }
        const rate = (stats.successful / stats.total_deliveries) * 100;
        let status;
        if (rate >= 95)
            status = 'excellent';
        else if (rate >= 90)
            status = 'good';
        else if (rate >= 75)
            status = 'fair';
        else
            status = 'poor';
        return { rate, status };
    }
    /**
     * Format webhook endpoint for display
     */
    formatEndpoint(endpoint) {
        // Truncate URL for display
        let displayUrl = endpoint.url;
        if (displayUrl.length > 50) {
            displayUrl = displayUrl.substring(0, 47) + '...';
        }
        return {
            displayUrl,
            eventCount: endpoint.events.length,
            statusText: endpoint.is_active ? 'Active' : 'Inactive',
            isHealthy: endpoint.is_active
        };
    }
}
exports.Webhooks = Webhooks;
//# sourceMappingURL=webhooks.js.map