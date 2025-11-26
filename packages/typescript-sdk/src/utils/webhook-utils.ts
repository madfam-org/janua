/**
 * Webhook utility functions
 */

import { ConfigurationError } from '../errors';

/**
 * Webhook utility functions for signature generation and verification
 */
export class WebhookUtils {
  /**
   * Generate a unique webhook ID
   */
  static generateWebhookId(): string {
    const timestamp = Date.now();
    const randomPart = Math.random().toString(36).substring(2, 11);
    return `whk_${timestamp}_${randomPart}`;
  }

  /**
   * Generate HMAC signature for payload
   */
  static generateSignature(
    payload: string | Buffer,
    secret: string,
    algorithm: string = 'sha256'
  ): string {
    // In Node.js environment
    if (typeof require !== 'undefined') {
      try {
        const crypto = require('crypto');
        return crypto
          .createHmac(algorithm, secret)
          .update(payload)
          .digest('hex');
      } catch (e) {
        // Fall through to browser implementation
      }
    }

    // In browser environment - simplified version
    if (typeof window !== 'undefined') {
      // Note: This is a simplified version for browser
      const payloadStr = typeof payload === 'string' ? payload : payload.toString();
      return this.browserHmac(payloadStr, secret);
    }

    throw new ConfigurationError('No suitable crypto implementation available');
  }

  /**
   * Calculate webhook signature with timestamp
   */
  static calculateSignature(timestamp: string, payload: string, secret: string): string {
    const message = `${timestamp}.${payload}`;

    // In browser environment
    if (typeof window !== 'undefined' && window.crypto && window.crypto.subtle) {
      // Use Web Crypto API for browser
      // Note: This is synchronous for now, but in a real implementation
      // you'd want to make this async and use crypto.subtle.sign
      return this.browserHmac(message, secret);
    }

    // In Node.js environment
    if (typeof require !== 'undefined') {
      const crypto = require('crypto');
      return crypto
        .createHmac('sha256', secret)
        .update(message)
        .digest('hex');
    }

    throw new ConfigurationError('No suitable crypto implementation available');
  }

  /**
   * Browser HMAC implementation
   * Note: This is a simplified version. In production, you'd use crypto.subtle
   */
  private static browserHmac(message: string, secret: string): string {
    // Simple hash for browser (not cryptographically secure)
    // In production, you should use crypto.subtle.sign with HMAC
    let hash = 0;
    const str = message + secret;
    for (let i = 0; i < str.length; i++) {
      const char = str.charCodeAt(i);
      hash = ((hash << 5) - hash) + char;
      hash = hash & hash; // Convert to 32bit integer
    }
    return Math.abs(hash).toString(16).padStart(64, '0');
  }

  /**
   * Verify webhook signature
   */
  static verifySignature(
    signature: string,
    timestamp: string,
    payload: string,
    secret: string,
    tolerance: number = 300
  ): boolean {
    // Check timestamp to prevent replay attacks
    const currentTime = Math.floor(Date.now() / 1000);
    const webhookTime = parseInt(timestamp, 10);

    if (Math.abs(currentTime - webhookTime) > tolerance) {
      return false; // Timestamp too old or in the future
    }

    // Calculate expected signature
    const expectedSignature = this.calculateSignature(timestamp, payload, secret);

    // Constant-time comparison to prevent timing attacks
    return this.constantTimeCompare(signature, expectedSignature);
  }

  /**
   * Constant-time string comparison
   */
  private static constantTimeCompare(a: string, b: string): boolean {
    if (a.length !== b.length) {
      return false;
    }

    let result = 0;
    for (let i = 0; i < a.length; i++) {
      result |= a.charCodeAt(i) ^ b.charCodeAt(i);
    }

    return result === 0;
  }

  /**
   * Timing-safe string comparison
   */
  static timingSafeEqual(a: string, b: string): boolean {
    return this.constantTimeCompare(a, b);
  }

  /**
   * Verify webhook signature (simplified version for payload + signature + secret)
   */
  static verifyPayloadSignature(
    payload: string | Buffer,
    signature: string,
    secret: string,
    algorithm: string = 'sha256'
  ): boolean {
    const expectedSignature = this.generateSignature(payload, secret, algorithm);
    return this.constantTimeCompare(signature, expectedSignature);
  }

  /**
   * Verify timestamp is within acceptable range
   */
  static verifyTimestamp(
    timestamp: number | string,
    maxAge: number = 300
  ): boolean {
    const timestampNum = typeof timestamp === 'string' ? parseInt(timestamp, 10) : timestamp;
    const currentTime = Math.floor(Date.now() / 1000);
    return Math.abs(currentTime - timestampNum) <= maxAge;
  }

  /**
   * Parse webhook headers
   */
  static parseWebhookHeaders(headers: Record<string, string>): {
    signature?: string;
    timestamp?: string;
    eventType?: string;
    webhookId?: string;
  } {
    return {
      signature: headers['x-webhook-signature'] || headers['X-Webhook-Signature'],
      timestamp: headers['x-webhook-timestamp'] || headers['X-Webhook-Timestamp'],
      eventType: headers['x-webhook-event'] || headers['X-Webhook-Event'],
      webhookId: headers['x-webhook-id'] || headers['X-Webhook-Id']
    };
  }

  /**
   * Parse webhook headers
   */
  static parseHeaders(headers: Record<string, string | string[] | undefined>): {
    signature?: string;
    timestamp?: string;
    eventType?: string;
    webhookId?: string;
  } {
    const getHeader = (key: string): string | undefined => {
      const value = headers[key] || headers[key.toLowerCase()] ||
                   headers[key.replace(/-/g, '_').toUpperCase()];
      return Array.isArray(value) ? value[0] : value;
    };

    return {
      signature: getHeader('X-Webhook-Signature'),
      timestamp: getHeader('X-Webhook-Timestamp'),
      eventType: getHeader('X-Webhook-Event'),
      webhookId: getHeader('X-Webhook-Id')
    };
  }

  /**
   * Construct webhook payload for signature verification
   */
  static constructPayload(timestamp: number | string, body: string | object): string {
    const timestampStr = typeof timestamp === 'string' ? timestamp : timestamp.toString();
    const bodyStr = typeof body === 'string' ? body : JSON.stringify(body);
    return `${timestampStr}.${bodyStr}`;
  }

  /**
   * Verify webhook authenticity
   */
  static verifyWebhook(
    body: string | object,
    headers: Record<string, string | string[] | undefined>,
    secret: string,
    options?: {
      maxAge?: number;
      algorithm?: string;
    }
  ): {
    valid: boolean;
    error?: string;
  } {
    const parsed = this.parseHeaders(headers);

    if (!parsed.signature) {
      return { valid: false, error: 'Missing signature header' };
    }

    if (!parsed.timestamp) {
      return { valid: false, error: 'Missing timestamp header' };
    }

    // Verify timestamp
    if (!this.verifyTimestamp(parsed.timestamp, options?.maxAge)) {
      return { valid: false, error: 'Webhook timestamp too old' };
    }

    // Construct and verify payload
    const payload = this.constructPayload(parsed.timestamp, body);
    const expectedSignature = this.generateSignature(
      payload,
      secret,
      options?.algorithm
    );

    if (!this.constantTimeCompare(parsed.signature, expectedSignature)) {
      return { valid: false, error: 'Invalid signature' };
    }

    return { valid: true };
  }

  /**
   * Create test webhook payload
   */
  static createTestPayload(
    eventType: string,
    data: unknown,
    options?: {
      timestamp?: number;
      webhookId?: string;
    }
  ): {
    headers: Record<string, string>;
    body: string;
  } {
    const timestamp = options?.timestamp || Math.floor(Date.now() / 1000);
    const id = options?.webhookId || this.generateWebhookId();

    const bodyObj = {
      id,
      type: eventType,
      created_at: new Date(timestamp * 1000).toISOString(),
      data
    };

    const headers = {
      'x-webhook-id': id,
      'x-webhook-event': eventType,
      'x-webhook-timestamp': timestamp.toString()
    };

    return {
      headers,
      body: JSON.stringify(bodyObj)
    };
  }

  /**
   * Generate webhook headers
   */
  static generateWebhookHeaders(
    payload: string,
    secret: string,
    eventType?: string,
    webhookId?: string
  ): Record<string, string> {
    const timestamp = Math.floor(Date.now() / 1000).toString();
    const signature = this.calculateSignature(timestamp, payload, secret);

    const headers: Record<string, string> = {
      'X-Webhook-Signature': signature,
      'X-Webhook-Timestamp': timestamp,
      'Content-Type': 'application/json'
    };

    if (eventType) {
      headers['X-Webhook-Event'] = eventType;
    }

    if (webhookId) {
      headers['X-Webhook-Id'] = webhookId;
    }

    return headers;
  }
}
