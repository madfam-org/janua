/**
 * Tests for utility classes and functions
 */

import {
  Base64Url,
  JwtUtils,
  TokenStorage,
  LocalTokenStorage,
  SessionTokenStorage,
  MemoryTokenStorage,
  TokenManager,
  DateUtils,
  UrlUtils,
  ValidationUtils,
  WebhookUtils,
  EnvUtils,
  RetryUtils,
  EventEmitter
} from '../utils';
import { TokenError } from '../errors';

describe('Base64Url', () => {
  describe('encode', () => {
    it('should encode string to base64url format', () => {
      const input = 'Hello, World!';
      const encoded = Base64Url.encode(input);
      
      expect(encoded).toBe('SGVsbG8sIFdvcmxkIQ');
      expect(encoded).not.toContain('+');
      expect(encoded).not.toContain('/');
      expect(encoded).not.toContain('=');
    });

    it('should handle empty string', () => {
      const encoded = Base64Url.encode('');
      expect(encoded).toBe('');
    });

    it('should handle special characters', () => {
      const input = 'Hello+World/=';
      const encoded = Base64Url.encode(input);
      
      expect(encoded).toBeDefined();
      expect(encoded).not.toContain('+');
      expect(encoded).not.toContain('/');
      expect(encoded).not.toContain('=');
    });
  });

  describe('decode', () => {
    it('should decode base64url to original string', () => {
      const encoded = 'SGVsbG8sIFdvcmxkIQ';
      const decoded = Base64Url.decode(encoded);
      
      expect(decoded).toBe('Hello, World!');
    });

    it('should handle strings with missing padding', () => {
      const encoded = 'SGVsbG8'; // "Hello" without padding
      const decoded = Base64Url.decode(encoded);
      
      expect(decoded).toBe('Hello');
    });

    it('should handle empty string', () => {
      const decoded = Base64Url.decode('');
      expect(decoded).toBe('');
    });

    it('should be reversible', () => {
      const original = 'Test string with special chars: !@#$%^&*()';
      const encoded = Base64Url.encode(original);
      const decoded = Base64Url.decode(encoded);
      
      expect(decoded).toBe(original);
    });
  });
});

describe('JwtUtils', () => {
  const mockToken = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c';

  describe('parseToken', () => {
    it('should parse valid JWT token', () => {
      const parsed = JwtUtils.parseToken(mockToken);
      
      expect(parsed.header).toBeDefined();
      expect(parsed.payload).toBeDefined();
      expect(parsed.signature).toBeDefined();
      expect(parsed.payload.sub).toBe('1234567890');
      expect(parsed.payload.name).toBe('John Doe');
    });

    it('should throw error for invalid token format', () => {
      expect(() => {
        JwtUtils.parseToken('invalid.token');
      }).toThrow(TokenError);
    });

    it('should throw error for malformed JSON', () => {
      const invalidToken = 'header.invalidjson.signature';
      expect(() => {
        JwtUtils.parseToken(invalidToken);
      }).toThrow(TokenError);
    });
  });

  describe('isExpired', () => {
    it('should return true for expired token', () => {
      const expiredPayload = { exp: Math.floor(Date.now() / 1000) - 3600 }; // 1 hour ago
      const isExpired = JwtUtils.isExpired(expiredPayload);
      
      expect(isExpired).toBe(true);
    });

    it('should return false for valid token', () => {
      const validPayload = { exp: Math.floor(Date.now() / 1000) + 3600 }; // 1 hour from now
      const isExpired = JwtUtils.isExpired(validPayload);
      
      expect(isExpired).toBe(false);
    });

    it('should return false when no exp claim', () => {
      const payloadWithoutExp = { sub: '123' };
      const isExpired = JwtUtils.isExpired(payloadWithoutExp);
      
      expect(isExpired).toBe(false);
    });
  });

  describe('getTimeToExpiry', () => {
    it('should return time to expiry in seconds', () => {
      const expiryTime = Math.floor(Date.now() / 1000) + 3600; // 1 hour from now
      const payload = { exp: expiryTime };
      const timeToExpiry = JwtUtils.getTimeToExpiry(payload);
      
      expect(timeToExpiry).toBeGreaterThan(3500); // Should be close to 3600
      expect(timeToExpiry).toBeLessThanOrEqual(3600);
    });

    it('should return 0 for expired token', () => {
      const expiredPayload = { exp: Math.floor(Date.now() / 1000) - 3600 };
      const timeToExpiry = JwtUtils.getTimeToExpiry(expiredPayload);
      
      expect(timeToExpiry).toBe(0);
    });

    it('should return Infinity when no exp claim', () => {
      const payloadWithoutExp = { sub: '123' };
      const timeToExpiry = JwtUtils.getTimeToExpiry(payloadWithoutExp);
      
      expect(timeToExpiry).toBe(Infinity);
    });
  });
});

describe('Token Storage Classes', () => {
  describe('MemoryTokenStorage', () => {
    let storage: MemoryTokenStorage;

    beforeEach(() => {
      storage = new MemoryTokenStorage();
    });

    it('should store and retrieve tokens', async () => {
      const key = 'test-key';
      const value = 'test-value';
      
      await storage.setItem(key, value);
      const retrieved = await storage.getItem(key);
      
      expect(retrieved).toBe(value);
    });

    it('should return null for non-existent keys', async () => {
      const retrieved = await storage.getItem('non-existent');
      expect(retrieved).toBeNull();
    });

    it('should remove items', async () => {
      const key = 'test-key';
      const value = 'test-value';
      
      await storage.setItem(key, value);
      await storage.removeItem(key);
      const retrieved = await storage.getItem(key);
      
      expect(retrieved).toBeNull();
    });
  });

  describe('LocalTokenStorage', () => {
    let storage: LocalTokenStorage;
    let mockLocalStorage: {
      getItem: jest.Mock;
      setItem: jest.Mock;
      removeItem: jest.Mock;
    };

    beforeEach(() => {
      mockLocalStorage = {
        getItem: jest.fn(),
        setItem: jest.fn(),
        removeItem: jest.fn()
      };
      
      // Mock localStorage
      Object.defineProperty(window, 'localStorage', {
        value: mockLocalStorage,
        writable: true
      });
      
      storage = new LocalTokenStorage();
    });

    it('should use localStorage for storage operations', async () => {
      const key = 'test-key';
      const value = 'test-value';
      
      mockLocalStorage.getItem.mockReturnValue(value);
      
      await storage.setItem(key, value);
      expect(mockLocalStorage.setItem).toHaveBeenCalledWith(key, value);
      
      const retrieved = await storage.getItem(key);
      expect(mockLocalStorage.getItem).toHaveBeenCalledWith(key);
      expect(retrieved).toBe(value);
      
      await storage.removeItem(key);
      expect(mockLocalStorage.removeItem).toHaveBeenCalledWith(key);
    });

    it('should handle localStorage errors gracefully', async () => {
      mockLocalStorage.setItem.mockImplementation(() => {
        throw new Error('Storage quota exceeded');
      });
      
      // Should not throw
      await expect(storage.setItem('key', 'value')).resolves.toBeUndefined();
    });
  });

  describe('SessionTokenStorage', () => {
    let storage: SessionTokenStorage;
    let mockSessionStorage: {
      getItem: jest.Mock;
      setItem: jest.Mock;
      removeItem: jest.Mock;
    };

    beforeEach(() => {
      mockSessionStorage = {
        getItem: jest.fn(),
        setItem: jest.fn(),
        removeItem: jest.fn()
      };
      
      // Mock sessionStorage
      Object.defineProperty(window, 'sessionStorage', {
        value: mockSessionStorage,
        writable: true
      });
      
      storage = new SessionTokenStorage();
    });

    it('should use sessionStorage for storage operations', async () => {
      const key = 'test-key';
      const value = 'test-value';
      
      mockSessionStorage.getItem.mockReturnValue(value);
      
      await storage.setItem(key, value);
      expect(mockSessionStorage.setItem).toHaveBeenCalledWith(key, value);
      
      const retrieved = await storage.getItem(key);
      expect(mockSessionStorage.getItem).toHaveBeenCalledWith(key);
      expect(retrieved).toBe(value);
      
      await storage.removeItem(key);
      expect(mockSessionStorage.removeItem).toHaveBeenCalledWith(key);
    });
  });
});

describe('TokenManager', () => {
  let tokenManager: TokenManager;
  let mockStorage: MemoryTokenStorage;

  beforeEach(() => {
    mockStorage = new MemoryTokenStorage();
    tokenManager = new TokenManager(mockStorage);
  });

  describe('token operations', () => {
    // Create a valid JWT token with future expiration
    const futureExp = Math.floor(Date.now() / 1000) + 3600; // 1 hour from now
    const mockPayload = { sub: '123', exp: futureExp };
    const mockHeader = { alg: 'HS256', typ: 'JWT' };
    const validAccessToken = [
      Base64Url.encode(JSON.stringify(mockHeader)),
      Base64Url.encode(JSON.stringify(mockPayload)),
      'mock-signature'
    ].join('.');
    
    const mockTokenData = {
      access_token: validAccessToken,
      refresh_token: 'refresh-123',
      expires_at: Date.now() + 3600000 // 1 hour from now
    };

    it('should set and get token data', async () => {
      await tokenManager.setTokens(mockTokenData);
      const retrieved = await tokenManager.getTokenData();
      
      expect(retrieved).toEqual(mockTokenData);
    });

    it('should get individual tokens', async () => {
      await tokenManager.setTokens(mockTokenData);
      
      const accessToken = await tokenManager.getAccessToken();
      const refreshToken = await tokenManager.getRefreshToken();
      
      expect(accessToken).toBe(mockTokenData.access_token);
      expect(refreshToken).toBe(mockTokenData.refresh_token);
    });

    it('should clear tokens', async () => {
      await tokenManager.setTokens(mockTokenData);
      await tokenManager.clearTokens();
      
      const tokenData = await tokenManager.getTokenData();
      expect(tokenData).toBeNull();
    });

    it('should check if tokens are valid', async () => {
      // Valid tokens
      await tokenManager.setTokens(mockTokenData);
      const isValid = await tokenManager.hasValidTokens();
      expect(isValid).toBe(true);
      
      // Expired tokens
      const expiredTokenData = {
        ...mockTokenData,
        expires_at: Date.now() - 3600000 // 1 hour ago
      };
      await tokenManager.setTokens(expiredTokenData);
      const isExpired = await tokenManager.hasValidTokens();
      expect(isExpired).toBe(false);
    });
  });
});

describe('DateUtils', () => {
  describe('isExpired', () => {
    it('should return true for past timestamps', () => {
      const pastTime = Date.now() - 1000;
      expect(DateUtils.isExpired(pastTime)).toBe(true);
    });

    it('should return false for future timestamps', () => {
      const futureTime = Date.now() + 1000;
      expect(DateUtils.isExpired(futureTime)).toBe(false);
    });
  });

  describe('formatISO', () => {
    it('should format date to ISO string', () => {
      const date = new Date('2023-01-01T12:00:00Z');
      const formatted = DateUtils.formatISO(date);
      
      expect(formatted).toBe('2023-01-01T12:00:00.000Z');
    });
  });

  describe('parseISO', () => {
    it('should parse ISO string to date', () => {
      const isoString = '2023-01-01T12:00:00.000Z';
      const parsed = DateUtils.parseISO(isoString);
      
      expect(parsed).toBeInstanceOf(Date);
      expect(parsed.getTime()).toBe(new Date(isoString).getTime());
    });
  });
});

describe('UrlUtils', () => {
  describe('buildUrl', () => {
    it('should build URL with path', () => {
      const url = UrlUtils.buildUrl('https://api.example.com', '/users');
      expect(url).toBe('https://api.example.com/users');
    });

    it('should handle trailing slashes', () => {
      const url1 = UrlUtils.buildUrl('https://api.example.com/', '/users');
      const url2 = UrlUtils.buildUrl('https://api.example.com', 'users');
      
      expect(url1).toBe('https://api.example.com/users');
      expect(url2).toBe('https://api.example.com/users');
    });

    it('should add query parameters', () => {
      const params = { page: 1, limit: 10 };
      const url = UrlUtils.buildUrl('https://api.example.com', '/users', params);
      
      expect(url).toBe('https://api.example.com/users?page=1&limit=10');
    });
  });

  describe('parseQueryString', () => {
    it('should parse query string to object', () => {
      const queryString = 'page=1&limit=10&search=test';
      const parsed = UrlUtils.parseQueryString(queryString);
      
      expect(parsed).toEqual({
        page: '1',
        limit: '10',
        search: 'test'
      });
    });

    it('should handle empty query string', () => {
      const parsed = UrlUtils.parseQueryString('');
      expect(parsed).toEqual({});
    });
  });
});

describe('ValidationUtils', () => {
  describe('isValidEmail', () => {
    it('should validate correct email addresses', () => {
      const validEmails = [
        'test@example.com',
        'user.name@domain.co.uk',
        'user+tag@example.org'
      ];
      
      validEmails.forEach(email => {
        expect(ValidationUtils.isValidEmail(email)).toBe(true);
      });
    });

    it('should reject invalid email addresses', () => {
      const invalidEmails = [
        'invalid-email',
        '@example.com',
        'user@',
        'user..name@example.com'
      ];
      
      invalidEmails.forEach(email => {
        expect(ValidationUtils.isValidEmail(email)).toBe(false);
      });
    });
  });

  describe('isValidPassword', () => {
    it('should validate passwords meeting criteria', () => {
      const validPasswords = [
        'Password123!',
        'SecureP@ss1',
        'MyStr0ng#Pass'
      ];
      
      validPasswords.forEach(password => {
        expect(ValidationUtils.isValidPassword(password)).toBe(true);
      });
    });

    it('should reject weak passwords', () => {
      const invalidPasswords = [
        '123456',
        'password',
        'Pass1',
        'verylongpasswordwithoutuppercase1'
      ];
      
      invalidPasswords.forEach(password => {
        expect(ValidationUtils.isValidPassword(password)).toBe(false);
      });
    });
  });
});

describe('EnvUtils', () => {
  describe('environment detection', () => {
    it('should detect Node.js environment', () => {
      // In the test environment, we're running in Node.js
      expect(EnvUtils.isNode()).toBe(true);
      expect(EnvUtils.isBrowser()).toBe(false);
    });

    it('should have getDefaultStorage method', () => {
      const storage = EnvUtils.getDefaultStorage();
      expect(storage).toBeDefined();
      // In Node environment, should return MemoryTokenStorage
      expect(storage).toBeInstanceOf(MemoryTokenStorage);
    });
  });
});

describe('EventEmitter', () => {
  let emitter: EventEmitter<{ test: { data: string } }>;

  beforeEach(() => {
    emitter = new EventEmitter();
  });

  describe('event handling', () => {
    it('should add and trigger event listeners', () => {
      const handler = jest.fn();
      
      emitter.on('test', handler);
      emitter.emit('test', { data: 'hello' });
      
      expect(handler).toHaveBeenCalledWith({ data: 'hello' });
    });

    it('should remove event listeners', () => {
      const handler = jest.fn();
      
      const unsubscribe = emitter.on('test', handler);
      unsubscribe();
      emitter.emit('test', { data: 'hello' });
      
      expect(handler).not.toHaveBeenCalled();
    });

    it('should support one-time listeners', () => {
      const handler = jest.fn();
      
      emitter.once('test', handler);
      emitter.emit('test', { data: 'hello' });
      emitter.emit('test', { data: 'world' });
      
      expect(handler).toHaveBeenCalledTimes(1);
      expect(handler).toHaveBeenCalledWith({ data: 'hello' });
    });

    it('should remove all listeners', () => {
      const handler1 = jest.fn();
      const handler2 = jest.fn();
      
      emitter.on('test', handler1);
      emitter.on('test', handler2);
      emitter.removeAllListeners('test');
      emitter.emit('test', { data: 'hello' });
      
      expect(handler1).not.toHaveBeenCalled();
      expect(handler2).not.toHaveBeenCalled();
    });
  });
});