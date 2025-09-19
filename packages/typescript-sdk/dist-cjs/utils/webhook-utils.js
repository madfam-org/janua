"use strict";
/**
 * Webhook utilities for signature verification and payload handling
 */
var __createBinding = (this && this.__createBinding) || (Object.create ? (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    var desc = Object.getOwnPropertyDescriptor(m, k);
    if (!desc || ("get" in desc ? !m.__esModule : desc.writable || desc.configurable)) {
      desc = { enumerable: true, get: function() { return m[k]; } };
    }
    Object.defineProperty(o, k2, desc);
}) : (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    o[k2] = m[k];
}));
var __setModuleDefault = (this && this.__setModuleDefault) || (Object.create ? (function(o, v) {
    Object.defineProperty(o, "default", { enumerable: true, value: v });
}) : function(o, v) {
    o["default"] = v;
});
var __importStar = (this && this.__importStar) || function (mod) {
    if (mod && mod.__esModule) return mod;
    var result = {};
    if (mod != null) for (var k in mod) if (k !== "default" && Object.prototype.hasOwnProperty.call(mod, k)) __createBinding(result, mod, k);
    __setModuleDefault(result, mod);
    return result;
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.WebhookUtils = void 0;
const crypto = __importStar(require("crypto"));
class WebhookUtils {
    /**
     * Verify webhook signature using HMAC
     */
    static verifySignature(payload, signature, secret, algorithm = 'sha256') {
        const expectedSignature = this.generateSignature(payload, secret, algorithm);
        return this.timingSafeEqual(signature, expectedSignature);
    }
    /**
     * Generate webhook signature
     */
    static generateSignature(payload, secret, algorithm = 'sha256') {
        const hmac = crypto.createHmac(algorithm, secret);
        hmac.update(payload);
        return hmac.digest('hex');
    }
    /**
     * Timing-safe string comparison
     */
    static timingSafeEqual(a, b) {
        if (a.length !== b.length) {
            return false;
        }
        const bufferA = Buffer.from(a);
        const bufferB = Buffer.from(b);
        return crypto.timingSafeEqual(bufferA, bufferB);
    }
    /**
     * Verify webhook timestamp to prevent replay attacks
     */
    static verifyTimestamp(timestamp, maxAge = 300 // 5 minutes default
    ) {
        const webhookTime = typeof timestamp === 'string' ? parseInt(timestamp, 10) : timestamp;
        const currentTime = Math.floor(Date.now() / 1000);
        return Math.abs(currentTime - webhookTime) <= maxAge;
    }
    /**
     * Parse webhook headers
     */
    static parseHeaders(headers) {
        const normalizeHeader = (value) => {
            return Array.isArray(value) ? value[0] : value;
        };
        return {
            signature: headers['x-webhook-signature']
                ? normalizeHeader(headers['x-webhook-signature'])
                : undefined,
            timestamp: headers['x-webhook-timestamp']
                ? normalizeHeader(headers['x-webhook-timestamp'])
                : undefined,
            eventType: headers['x-webhook-event']
                ? normalizeHeader(headers['x-webhook-event'])
                : undefined,
            webhookId: headers['x-webhook-id']
                ? normalizeHeader(headers['x-webhook-id'])
                : undefined
        };
    }
    /**
     * Construct webhook payload for signing
     */
    static constructPayload(timestamp, body) {
        const bodyString = typeof body === 'object' ? JSON.stringify(body) : body;
        return `${timestamp}.${bodyString}`;
    }
    /**
     * Verify complete webhook request
     */
    static verifyWebhook(body, headers, secret, options = {}) {
        const { signature, timestamp } = this.parseHeaders(headers);
        if (!signature) {
            return { valid: false, error: 'Missing signature header' };
        }
        if (!timestamp) {
            return { valid: false, error: 'Missing timestamp header' };
        }
        // Verify timestamp
        if (!this.verifyTimestamp(timestamp, options.maxAge)) {
            return { valid: false, error: 'Webhook timestamp too old' };
        }
        // Construct and verify payload
        const payload = this.constructPayload(timestamp, body);
        const valid = this.verifySignature(payload, signature, secret, options.algorithm);
        return valid
            ? { valid: true }
            : { valid: false, error: 'Invalid signature' };
    }
    /**
     * Create webhook test payload
     */
    static createTestPayload(eventType, data, options = {}) {
        const timestamp = options.timestamp || Math.floor(Date.now() / 1000);
        const webhookId = options.webhookId || this.generateWebhookId();
        const body = JSON.stringify({
            id: webhookId,
            type: eventType,
            created_at: new Date(timestamp * 1000).toISOString(),
            data
        });
        return {
            headers: {
                'x-webhook-id': webhookId,
                'x-webhook-event': eventType,
                'x-webhook-timestamp': timestamp.toString()
            },
            body
        };
    }
    /**
     * Generate unique webhook ID
     */
    static generateWebhookId() {
        return `whk_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    }
}
exports.WebhookUtils = WebhookUtils;
//# sourceMappingURL=webhook-utils.js.map