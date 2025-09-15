/**
 * Tests for webhook utilities
 */
import * as crypto from 'crypto';
import { WebhookUtils } from '../utils/webhook-utils';

describe('WebhookUtils', () => {
  describe('generateSignature', () => {
    it('should generate correct HMAC signature for string payload', () => {
      const payload = 'test payload';
      const secret = 'secret-key';
      
      const signature = WebhookUtils.generateSignature(payload, secret);
      
      // Verify by creating expected signature manually
      const expectedHmac = crypto.createHmac('sha256', secret);
      expectedHmac.update(payload);
      const expected = expectedHmac.digest('hex');
      
      expect(signature).toBe(expected);
    });

    it('should generate correct HMAC signature for Buffer payload', () => {
      const payload = Buffer.from('test payload');
      const secret = 'secret-key';
      
      const signature = WebhookUtils.generateSignature(payload, secret);
      
      const expectedHmac = crypto.createHmac('sha256', secret);
      expectedHmac.update(payload);
      const expected = expectedHmac.digest('hex');
      
      expect(signature).toBe(expected);
    });

    it('should use custom algorithm', () => {
      const payload = 'test payload';
      const secret = 'secret-key';
      const algorithm = 'sha1';
      
      const signature = WebhookUtils.generateSignature(payload, secret, algorithm);
      
      const expectedHmac = crypto.createHmac(algorithm, secret);
      expectedHmac.update(payload);
      const expected = expectedHmac.digest('hex');
      
      expect(signature).toBe(expected);
    });

    it('should generate different signatures for different payloads', () => {
      const secret = 'secret-key';
      const signature1 = WebhookUtils.generateSignature('payload1', secret);
      const signature2 = WebhookUtils.generateSignature('payload2', secret);
      
      expect(signature1).not.toBe(signature2);
    });

    it('should generate different signatures for different secrets', () => {
      const payload = 'test payload';
      const signature1 = WebhookUtils.generateSignature(payload, 'secret1');
      const signature2 = WebhookUtils.generateSignature(payload, 'secret2');
      
      expect(signature1).not.toBe(signature2);
    });
  });

  describe('timingSafeEqual', () => {
    it('should return true for identical strings', () => {
      const str1 = 'identical-string';
      const str2 = 'identical-string';
      
      const result = WebhookUtils.timingSafeEqual(str1, str2);
      
      expect(result).toBe(true);
    });

    it('should return false for different strings of same length', () => {
      const str1 = 'string-one';
      const str2 = 'string-two';
      
      const result = WebhookUtils.timingSafeEqual(str1, str2);
      
      expect(result).toBe(false);
    });

    it('should return false for strings of different lengths', () => {
      const str1 = 'short';
      const str2 = 'much-longer-string';
      
      const result = WebhookUtils.timingSafeEqual(str1, str2);
      
      expect(result).toBe(false);
    });

    it('should return false for empty vs non-empty strings', () => {
      const str1 = '';
      const str2 = 'non-empty';
      
      const result = WebhookUtils.timingSafeEqual(str1, str2);
      
      expect(result).toBe(false);
    });

    it('should return true for two empty strings', () => {
      const str1 = '';
      const str2 = '';
      
      const result = WebhookUtils.timingSafeEqual(str1, str2);
      
      expect(result).toBe(true);
    });
  });

  describe('verifySignature', () => {
    it('should return true for valid signature', () => {
      const payload = 'test payload';
      const secret = 'secret-key';
      const signature = WebhookUtils.generateSignature(payload, secret);
      
      const isValid = WebhookUtils.verifySignature(payload, signature, secret);
      
      expect(isValid).toBe(true);
    });

    it('should return false for invalid signature', () => {
      const payload = 'test payload';
      const secret = 'secret-key';
      const wrongSignature = 'invalid-signature';
      
      const isValid = WebhookUtils.verifySignature(payload, wrongSignature, secret);
      
      expect(isValid).toBe(false);
    });

    it('should return false when using wrong secret', () => {
      const payload = 'test payload';
      const secret = 'secret-key';
      const wrongSecret = 'wrong-secret';
      const signature = WebhookUtils.generateSignature(payload, secret);
      
      const isValid = WebhookUtils.verifySignature(payload, signature, wrongSecret);
      
      expect(isValid).toBe(false);
    });

    it('should work with custom algorithm', () => {
      const payload = 'test payload';
      const secret = 'secret-key';
      const algorithm = 'sha1';
      const signature = WebhookUtils.generateSignature(payload, secret, algorithm);
      
      const isValid = WebhookUtils.verifySignature(payload, signature, secret, algorithm);
      
      expect(isValid).toBe(true);
    });

    it('should work with Buffer payload', () => {
      const payload = Buffer.from('test payload');
      const secret = 'secret-key';
      const signature = WebhookUtils.generateSignature(payload, secret);
      
      const isValid = WebhookUtils.verifySignature(payload, signature, secret);
      
      expect(isValid).toBe(true);
    });
  });

  describe('verifyTimestamp', () => {
    beforeEach(() => {
      // Mock Date.now to return a fixed time
      jest.spyOn(Date, 'now').mockReturnValue(1000000 * 1000); // 1000000 seconds in milliseconds
    });

    afterEach(() => {
      jest.restoreAllMocks();
    });

    it('should return true for current timestamp', () => {
      const currentTimestamp = 1000000; // matches mocked Date.now
      
      const isValid = WebhookUtils.verifyTimestamp(currentTimestamp);
      
      expect(isValid).toBe(true);
    });

    it('should return true for timestamp within maxAge', () => {
      const timestamp = 1000000 - 100; // 100 seconds ago
      const maxAge = 300; // 5 minutes
      
      const isValid = WebhookUtils.verifyTimestamp(timestamp, maxAge);
      
      expect(isValid).toBe(true);
    });

    it('should return false for timestamp beyond maxAge', () => {
      const timestamp = 1000000 - 400; // 400 seconds ago
      const maxAge = 300; // 5 minutes
      
      const isValid = WebhookUtils.verifyTimestamp(timestamp, maxAge);
      
      expect(isValid).toBe(false);
    });

    it('should return true for future timestamp within maxAge', () => {
      const timestamp = 1000000 + 100; // 100 seconds in future
      const maxAge = 300;
      
      const isValid = WebhookUtils.verifyTimestamp(timestamp, maxAge);
      
      expect(isValid).toBe(true);
    });

    it('should return false for future timestamp beyond maxAge', () => {
      const timestamp = 1000000 + 400; // 400 seconds in future
      const maxAge = 300;
      
      const isValid = WebhookUtils.verifyTimestamp(timestamp, maxAge);
      
      expect(isValid).toBe(false);
    });

    it('should accept string timestamp', () => {
      const timestamp = '1000000';
      
      const isValid = WebhookUtils.verifyTimestamp(timestamp);
      
      expect(isValid).toBe(true);
    });

    it('should use default maxAge of 300 seconds', () => {
      const timestamp = 1000000 - 250; // 250 seconds ago, within default 300
      
      const isValid = WebhookUtils.verifyTimestamp(timestamp);
      
      expect(isValid).toBe(true);
    });
  });

  describe('parseHeaders', () => {
    it('should parse all webhook headers', () => {
      const headers = {
        'x-webhook-signature': 'signature-value',
        'x-webhook-timestamp': '1234567890',
        'x-webhook-event': 'user.created',
        'x-webhook-id': 'whk_123456'
      };
      
      const parsed = WebhookUtils.parseHeaders(headers);
      
      expect(parsed).toEqual({
        signature: 'signature-value',
        timestamp: '1234567890',
        eventType: 'user.created',
        webhookId: 'whk_123456'
      });
    });

    it('should handle missing headers', () => {
      const headers = {
        'x-webhook-signature': 'signature-value'
      };
      
      const parsed = WebhookUtils.parseHeaders(headers);
      
      expect(parsed).toEqual({
        signature: 'signature-value',
        timestamp: undefined,
        eventType: undefined,
        webhookId: undefined
      });
    });

    it('should handle array header values', () => {
      const headers = {
        'x-webhook-signature': ['signature-1', 'signature-2'],
        'x-webhook-timestamp': ['1234567890'],
        'x-webhook-event': ['user.created', 'user.updated'],
        'x-webhook-id': ['whk_123456']
      };
      
      const parsed = WebhookUtils.parseHeaders(headers);
      
      expect(parsed).toEqual({
        signature: 'signature-1', // first value from array
        timestamp: '1234567890',
        eventType: 'user.created',
        webhookId: 'whk_123456'
      });
    });

    it('should handle empty headers object', () => {
      const headers = {};
      
      const parsed = WebhookUtils.parseHeaders(headers);
      
      expect(parsed).toEqual({
        signature: undefined,
        timestamp: undefined,
        eventType: undefined,
        webhookId: undefined
      });
    });
  });

  describe('constructPayload', () => {
    it('should construct payload from timestamp and string body', () => {
      const timestamp = 1234567890;
      const body = 'test body content';
      
      const payload = WebhookUtils.constructPayload(timestamp, body);
      
      expect(payload).toBe('1234567890.test body content');
    });

    it('should construct payload from string timestamp and string body', () => {
      const timestamp = '1234567890';
      const body = 'test body content';
      
      const payload = WebhookUtils.constructPayload(timestamp, body);
      
      expect(payload).toBe('1234567890.test body content');
    });

    it('should construct payload from timestamp and object body', () => {
      const timestamp = 1234567890;
      const body = { type: 'user.created', data: { id: 123 } };
      
      const payload = WebhookUtils.constructPayload(timestamp, body);
      
      expect(payload).toBe('1234567890.{"type":"user.created","data":{"id":123}}');
    });

    it('should handle complex nested objects', () => {
      const timestamp = 1234567890;
      const body = {
        event: 'test',
        nested: {
          array: [1, 2, 3],
          object: { key: 'value' }
        }
      };
      
      const payload = WebhookUtils.constructPayload(timestamp, body);
      
      expect(payload).toBe('1234567890.{"event":"test","nested":{"array":[1,2,3],"object":{"key":"value"}}}');
    });
  });

  describe('verifyWebhook', () => {
    beforeEach(() => {
      jest.spyOn(Date, 'now').mockReturnValue(1000000 * 1000);
    });

    afterEach(() => {
      jest.restoreAllMocks();
    });

    it('should return valid for correct webhook', () => {
      const timestamp = 1000000;
      const body = { type: 'user.created', data: { id: 123 } };
      const secret = 'webhook-secret';
      
      const payload = WebhookUtils.constructPayload(timestamp, body);
      const signature = WebhookUtils.generateSignature(payload, secret);
      
      const headers = {
        'x-webhook-signature': signature,
        'x-webhook-timestamp': timestamp.toString()
      };
      
      const result = WebhookUtils.verifyWebhook(body, headers, secret);
      
      expect(result).toEqual({ valid: true });
    });

    it('should return invalid for missing signature header', () => {
      const body = { type: 'user.created' };
      const headers = {
        'x-webhook-timestamp': '1000000'
      };
      
      const result = WebhookUtils.verifyWebhook(body, headers, 'secret');
      
      expect(result).toEqual({
        valid: false,
        error: 'Missing signature header'
      });
    });

    it('should return invalid for missing timestamp header', () => {
      const body = { type: 'user.created' };
      const headers = {
        'x-webhook-signature': 'some-signature'
      };
      
      const result = WebhookUtils.verifyWebhook(body, headers, 'secret');
      
      expect(result).toEqual({
        valid: false,
        error: 'Missing timestamp header'
      });
    });

    it('should return invalid for old timestamp', () => {
      const oldTimestamp = 1000000 - 400; // 400 seconds ago
      const body = { type: 'user.created' };
      const secret = 'webhook-secret';
      
      const payload = WebhookUtils.constructPayload(oldTimestamp, body);
      const signature = WebhookUtils.generateSignature(payload, secret);
      
      const headers = {
        'x-webhook-signature': signature,
        'x-webhook-timestamp': oldTimestamp.toString()
      };
      
      const result = WebhookUtils.verifyWebhook(body, headers, secret);
      
      expect(result).toEqual({
        valid: false,
        error: 'Webhook timestamp too old'
      });
    });

    it('should return invalid for wrong signature', () => {
      const timestamp = 1000000;
      const body = { type: 'user.created' };
      const secret = 'webhook-secret';
      
      const headers = {
        'x-webhook-signature': 'wrong-signature',
        'x-webhook-timestamp': timestamp.toString()
      };
      
      const result = WebhookUtils.verifyWebhook(body, headers, secret);
      
      expect(result).toEqual({
        valid: false,
        error: 'Invalid signature'
      });
    });

    it('should use custom options', () => {
      const timestamp = 1000000 - 200; // 200 seconds ago
      const body = 'test body';
      const secret = 'webhook-secret';
      
      const payload = WebhookUtils.constructPayload(timestamp, body);
      const signature = WebhookUtils.generateSignature(payload, secret, 'sha1');
      
      const headers = {
        'x-webhook-signature': signature,
        'x-webhook-timestamp': timestamp.toString()
      };
      
      const result = WebhookUtils.verifyWebhook(body, headers, secret, {
        maxAge: 250, // Allow 250 seconds
        algorithm: 'sha1'
      });
      
      expect(result).toEqual({ valid: true });
    });
  });

  describe('createTestPayload', () => {
    beforeEach(() => {
      jest.spyOn(Date, 'now').mockReturnValue(1000000 * 1000);
      jest.spyOn(Math, 'random').mockReturnValue(0.123456789);
    });

    afterEach(() => {
      jest.restoreAllMocks();
    });

    it('should create test payload with default options', () => {
      const eventType = 'user.created';
      const data = { id: 123, name: 'John' };
      
      const result = WebhookUtils.createTestPayload(eventType, data);
      
      expect(result.headers).toEqual({
        'x-webhook-id': expect.stringMatching(/^whk_\d+_/),
        'x-webhook-event': 'user.created',
        'x-webhook-timestamp': '1000000'
      });
      
      const parsedBody = JSON.parse(result.body);
      expect(parsedBody).toEqual({
        id: expect.stringMatching(/^whk_\d+_/),
        type: 'user.created',
        created_at: '1970-01-12T13:46:40.000Z',
        data: { id: 123, name: 'John' }
      });
    });

    it('should use custom timestamp', () => {
      const eventType = 'user.updated';
      const data = { id: 456 };
      const customTimestamp = 2000000;
      
      const result = WebhookUtils.createTestPayload(eventType, data, {
        timestamp: customTimestamp
      });
      
      expect(result.headers['x-webhook-timestamp']).toBe('2000000');
      
      const parsedBody = JSON.parse(result.body);
      expect(parsedBody.created_at).toBe('1970-01-24T03:33:20.000Z');
    });

    it('should use custom webhook ID', () => {
      const eventType = 'user.deleted';
      const data = { id: 789 };
      const customWebhookId = 'custom_webhook_id';
      
      const result = WebhookUtils.createTestPayload(eventType, data, {
        webhookId: customWebhookId
      });
      
      expect(result.headers['x-webhook-id']).toBe('custom_webhook_id');
      
      const parsedBody = JSON.parse(result.body);
      expect(parsedBody.id).toBe('custom_webhook_id');
    });

    it('should handle complex data objects', () => {
      const eventType = 'order.completed';
      const data = {
        order: {
          id: 'order_123',
          items: [
            { id: 'item_1', quantity: 2 },
            { id: 'item_2', quantity: 1 }
          ],
          total: 29.99
        }
      };
      
      const result = WebhookUtils.createTestPayload(eventType, data);
      
      const parsedBody = JSON.parse(result.body);
      expect(parsedBody.data).toEqual(data);
      expect(parsedBody.type).toBe('order.completed');
    });
  });

  describe('generateWebhookId', () => {
    beforeEach(() => {
      jest.spyOn(Date, 'now').mockReturnValue(1234567890123);
      jest.spyOn(Math, 'random').mockReturnValue(0.123456789);
    });

    afterEach(() => {
      jest.restoreAllMocks();
    });

    it('should generate webhook ID with correct format', () => {
      const webhookId = WebhookUtils.generateWebhookId();
      
      expect(webhookId).toMatch(/^whk_\d+_[a-z0-9]{9}$/);
    });

    it('should generate consistent ID with mocked values', () => {
      const webhookId = WebhookUtils.generateWebhookId();
      
      expect(webhookId).toBe('whk_1234567890123_4fzzzxjyl');
    });

    it('should generate different IDs on subsequent calls', () => {
      jest.restoreAllMocks();
      
      const id1 = WebhookUtils.generateWebhookId();
      const id2 = WebhookUtils.generateWebhookId();
      
      expect(id1).not.toBe(id2);
      expect(id1).toMatch(/^whk_\d+_[a-z0-9]{9}$/);
      expect(id2).toMatch(/^whk_\d+_[a-z0-9]{9}$/);
    });
  });
});