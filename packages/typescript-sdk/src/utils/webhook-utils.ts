/**
 * Webhook utilities for signature verification and payload handling
 */

import * as crypto from 'crypto';

export class WebhookUtils {
  /**
   * Verify webhook signature using HMAC
   */
  static verifySignature(
    payload: string | Buffer,
    signature: string,
    secret: string,
    algorithm: string = 'sha256'
  ): boolean {
    const expectedSignature = this.generateSignature(payload, secret, algorithm);
    return this.timingSafeEqual(signature, expectedSignature);
  }

  /**
   * Generate webhook signature
   */
  static generateSignature(
    payload: string | Buffer,
    secret: string,
    algorithm: string = 'sha256'
  ): string {
    const hmac = crypto.createHmac(algorithm, secret);
    hmac.update(payload);
    return hmac.digest('hex');
  }

  /**
   * Timing-safe string comparison
   */
  static timingSafeEqual(a: string, b: string): boolean {
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
  static verifyTimestamp(
    timestamp: string | number,
    maxAge: number = 300 // 5 minutes default
  ): boolean {
    const webhookTime = typeof timestamp === 'string' ? parseInt(timestamp, 10) : timestamp;
    const currentTime = Math.floor(Date.now() / 1000);

    return Math.abs(currentTime - webhookTime) <= maxAge;
  }

  /**
   * Parse webhook headers
   */
  static parseHeaders(headers: Record<string, string | string[]>): {
    signature?: string;
    timestamp?: string;
    eventType?: string;
    webhookId?: string;
  } {
    const normalizeHeader = (value: string | string[]): string => {
      return Array.isArray(value) ? value[0] : value;
    };

    return {
      signature: headers['x-webhook-signature']
        ? normalizeHeader(headers['x-webhook-signature'])
        : undefined as string | undefined,
      timestamp: headers['x-webhook-timestamp']
        ? normalizeHeader(headers['x-webhook-timestamp'])
        : undefined as string | undefined,
      eventType: headers['x-webhook-event']
        ? normalizeHeader(headers['x-webhook-event'])
        : undefined as string | undefined,
      webhookId: headers['x-webhook-id']
        ? normalizeHeader(headers['x-webhook-id'])
        : undefined as string | undefined
    };
  }

  /**
   * Construct webhook payload for signing
   */
  static constructPayload(
    timestamp: string | number,
    body: string | object
  ): string {
    const bodyString = typeof body === 'object' ? JSON.stringify(body) : body;
    return `${timestamp}.${bodyString}`;
  }

  /**
   * Verify complete webhook request
   */
  static verifyWebhook(
    body: string | object,
    headers: Record<string, string | string[]>,
    secret: string,
    options: {
      maxAge?: number;
      algorithm?: string;
    } = {}
  ): { valid: boolean; error?: string } {
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
    const valid = this.verifySignature(
      payload,
      signature,
      secret,
      options.algorithm
    );

    return valid
      ? { valid: true }
      : { valid: false, error: 'Invalid signature' };
  }

  /**
   * Create webhook test payload
   */
  static createTestPayload(
    eventType: string,
    data: any,
    options: {
      webhookId?: string;
      timestamp?: number;
    } = {}
  ): {
    headers: Record<string, string>;
    body: string;
  } {
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
  static generateWebhookId(): string {
    return `whk_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  }
}