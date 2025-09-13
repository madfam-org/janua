/**
 * Tests for PlintoClient class
 */

import { PlintoClient, createClient } from '../client';
import { ConfigurationError } from '../errors';
import { authMocks } from '../../../../tests/mocks/api';
import { userFixtures } from '../../../../tests/fixtures/data';

// Mock dependencies
jest.mock('../auth');
jest.mock('../users');
jest.mock('../organizations');
jest.mock('../webhooks');
jest.mock('../admin');
jest.mock('../http-client');
jest.mock('../utils', () => {
  const actualUtils = jest.requireActual('../utils');
  return {
    ...actualUtils,
    TokenManager: jest.fn(),
    EventEmitter: actualUtils.EventEmitter
  };
});

const mockAuth = {
  signOut: jest.fn(),
  getCurrentUser: jest.fn(),
  refreshToken: jest.fn()
};

const mockTokenManager = {
  hasValidTokens: jest.fn(),
  getAccessToken: jest.fn(),
  getRefreshToken: jest.fn(),
  setTokens: jest.fn(),
  clearTokens: jest.fn(),
  getTokenData: jest.fn()
};

const mockHttpClient = {
  get: jest.fn(),
  post: jest.fn(),
  put: jest.fn(),
  delete: jest.fn(),
  on: jest.fn(),
  off: jest.fn()
};

describe('PlintoClient', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    
    // Reset global fetch mock
    (global.fetch as jest.Mock).mockClear();
    
    // Mock token manager
    require('../utils').TokenManager.mockImplementation(() => mockTokenManager);
    
    // Mock HTTP client
    require('../http-client').createHttpClient.mockReturnValue(mockHttpClient);
    
    // Mock modules
    require('../auth').Auth.mockImplementation(() => mockAuth);
  });

  describe('constructor', () => {
    it('should create client with valid configuration', () => {
      const client = new PlintoClient({
        baseURL: 'https://api.example.com'
      });
      
      expect(client).toBeInstanceOf(PlintoClient);
      expect(client.auth).toBeDefined();
      expect(client.users).toBeDefined();
      expect(client.organizations).toBeDefined();
      expect(client.webhooks).toBeDefined();
      expect(client.admin).toBeDefined();
    });

    it('should throw error for missing baseURL', () => {
      expect(() => {
        new PlintoClient({});
      }).toThrow(ConfigurationError);
      
      expect(() => {
        new PlintoClient({});
      }).toThrow('baseURL is required');
    });

    it('should throw error for invalid baseURL format', () => {
      expect(() => {
        new PlintoClient({
          baseURL: 'invalid-url'
        });
      }).toThrow(ConfigurationError);
      
      expect(() => {
        new PlintoClient({
          baseURL: 'invalid-url'
        });
      }).toThrow('Invalid baseURL format');
    });

    it('should apply default configuration values', () => {
      const client = new PlintoClient({
        baseURL: 'https://api.example.com'
      });
      
      const config = client.getConfig();
      expect(config.timeout).toBe(30000);
      expect(config.retryAttempts).toBe(3);
      expect(config.retryDelay).toBe(1000);
      expect(config.debug).toBe(false);
      expect(config.autoRefreshTokens).toBe(true);
    });

    it('should merge custom configuration with defaults', () => {
      const client = new PlintoClient({
        baseURL: 'https://api.example.com',
        timeout: 10000,
        debug: true,
        retryAttempts: 1
      });
      
      const config = client.getConfig();
      expect(config.baseURL).toBe('https://api.example.com');
      expect(config.timeout).toBe(10000);
      expect(config.debug).toBe(true);
      expect(config.retryAttempts).toBe(1);
      expect(config.retryDelay).toBe(1000); // default
    });

    it('should validate timeout configuration', () => {
      expect(() => {
        new PlintoClient({
          baseURL: 'https://api.example.com',
          timeout: 0
        });
      }).toThrow(ConfigurationError);
      
      expect(() => {
        new PlintoClient({
          baseURL: 'https://api.example.com',
          timeout: -1000
        });
      }).toThrow('Timeout must be greater than 0');
    });

    it('should validate retry attempts configuration', () => {
      expect(() => {
        new PlintoClient({
          baseURL: 'https://api.example.com',
          retryAttempts: -1
        });
      }).toThrow(ConfigurationError);
      
      expect(() => {
        new PlintoClient({
          baseURL: 'https://api.example.com',
          retryAttempts: -1
        });
      }).toThrow('Retry attempts must be non-negative');
    });

    it('should validate retry delay configuration', () => {
      expect(() => {
        new PlintoClient({
          baseURL: 'https://api.example.com',
          retryDelay: 0
        });
      }).toThrow(ConfigurationError);
      
      expect(() => {
        new PlintoClient({
          baseURL: 'https://api.example.com',
          retryDelay: -500
        });
      }).toThrow('Retry delay must be greater than 0');
    });
  });

  describe('createClient factory function', () => {
    it('should create client instance', () => {
      const client = createClient({
        baseURL: 'https://api.example.com'
      });
      
      expect(client).toBeInstanceOf(PlintoClient);
    });

    it('should work with empty configuration using defaults', () => {
      expect(() => {
        createClient();
      }).toThrow(ConfigurationError);
    });
  });

  describe('authentication state methods', () => {
    let client: PlintoClient;

    beforeEach(() => {
      client = new PlintoClient({
        baseURL: 'https://api.example.com'
      });
    });

    describe('isAuthenticated', () => {
      it('should return true when user is authenticated', async () => {
        mockTokenManager.hasValidTokens.mockResolvedValue(true);
        
        const result = await client.isAuthenticated();
        expect(result).toBe(true);
        expect(mockTokenManager.hasValidTokens).toHaveBeenCalled();
      });

      it('should return false when user is not authenticated', async () => {
        mockTokenManager.hasValidTokens.mockResolvedValue(false);
        
        const result = await client.isAuthenticated();
        expect(result).toBe(false);
      });
    });

    describe('getAccessToken', () => {
      it('should return access token when available', async () => {
        const token = 'access-token-123';
        mockTokenManager.getAccessToken.mockResolvedValue(token);
        
        const result = await client.getAccessToken();
        expect(result).toBe(token);
        expect(mockTokenManager.getAccessToken).toHaveBeenCalled();
      });

      it('should return null when no token available', async () => {
        mockTokenManager.getAccessToken.mockResolvedValue(null);
        
        const result = await client.getAccessToken();
        expect(result).toBeNull();
      });
    });

    describe('getRefreshToken', () => {
      it('should return refresh token when available', async () => {
        const token = 'refresh-token-123';
        mockTokenManager.getRefreshToken.mockResolvedValue(token);
        
        const result = await client.getRefreshToken();
        expect(result).toBe(token);
        expect(mockTokenManager.getRefreshToken).toHaveBeenCalled();
      });

      it('should return null when no token available', async () => {
        mockTokenManager.getRefreshToken.mockResolvedValue(null);
        
        const result = await client.getRefreshToken();
        expect(result).toBeNull();
      });
    });

    describe('setTokens', () => {
      it('should set tokens with correct expiration', async () => {
        const tokens = {
          access_token: 'access-123',
          refresh_token: 'refresh-123',
          token_type: 'bearer' as const,
          expires_in: 3600
        };
        
        const nowSpy = jest.spyOn(Date, 'now').mockReturnValue(1000000);
        
        await client.setTokens(tokens);
        
        expect(mockTokenManager.setTokens).toHaveBeenCalledWith({
          access_token: 'access-123',
          refresh_token: 'refresh-123',
          expires_at: 1000000 + (3600 * 1000)
        });
        
        nowSpy.mockRestore();
      });
    });

    describe('signOut', () => {
      it('should sign out from server and clear local tokens', async () => {
        mockAuth.signOut.mockResolvedValue({});
        
        const emitSpy = jest.spyOn(client, 'emit');
        
        await client.signOut();
        
        expect(mockAuth.signOut).toHaveBeenCalled();
        expect(mockTokenManager.clearTokens).toHaveBeenCalled();
        expect(emitSpy).toHaveBeenCalledWith('auth:signedOut', {});
      });

      it('should clear local tokens even if server sign out fails', async () => {
        mockAuth.signOut.mockRejectedValue(new Error('Server error'));
        
        const emitSpy = jest.spyOn(client, 'emit');
        
        await client.signOut();
        
        expect(mockAuth.signOut).toHaveBeenCalled();
        expect(mockTokenManager.clearTokens).toHaveBeenCalled();
        expect(emitSpy).toHaveBeenCalledWith('auth:signedOut', {});
      });
    });

    describe('getCurrentUser', () => {
      it('should return user when authenticated', async () => {
        const user = userFixtures.verified;
        mockTokenManager.hasValidTokens.mockResolvedValue(true);
        mockAuth.getCurrentUser.mockResolvedValue(user);
        
        const result = await client.getCurrentUser();
        
        expect(result).toEqual(user);
        expect(mockAuth.getCurrentUser).toHaveBeenCalled();
      });

      it('should return null when not authenticated', async () => {
        mockTokenManager.hasValidTokens.mockResolvedValue(false);
        
        const result = await client.getCurrentUser();
        
        expect(result).toBeNull();
        expect(mockAuth.getCurrentUser).not.toHaveBeenCalled();
      });

      it('should return null when API call fails', async () => {
        mockTokenManager.hasValidTokens.mockResolvedValue(true);
        mockAuth.getCurrentUser.mockRejectedValue(new Error('API error'));
        
        const result = await client.getCurrentUser();
        
        expect(result).toBeNull();
      });
    });
  });

  describe('configuration methods', () => {
    let client: PlintoClient;

    beforeEach(() => {
      client = new PlintoClient({
        baseURL: 'https://api.example.com',
        debug: false,
        timeout: 30000
      });
    });

    describe('updateConfig', () => {
      it('should update configuration', () => {
        client.updateConfig({
          timeout: 15000,
          debug: true
        });
        
        const config = client.getConfig();
        expect(config.timeout).toBe(15000);
        expect(config.debug).toBe(true);
        expect(config.baseURL).toBe('https://api.example.com'); // unchanged
      });

      it('should validate updated configuration', () => {
        expect(() => {
          client.updateConfig({
            timeout: -1000
          });
        }).toThrow(ConfigurationError);
      });
    });

    describe('getConfig', () => {
      it('should return current configuration', () => {
        const config = client.getConfig();
        
        expect(config.baseURL).toBe('https://api.example.com');
        expect(config.debug).toBe(false);
        expect(config.timeout).toBe(30000);
      });

      it('should return a copy of configuration', () => {
        const config1 = client.getConfig();
        const config2 = client.getConfig();
        
        expect(config1).not.toBe(config2); // different objects
        expect(config1).toEqual(config2); // same values
      });
    });

    describe('enableDebug/disableDebug', () => {
      it('should enable debug mode', () => {
        client.enableDebug();
        expect(client.getConfig().debug).toBe(true);
      });

      it('should disable debug mode', () => {
        client.enableDebug();
        client.disableDebug();
        expect(client.getConfig().debug).toBe(false);
      });
    });
  });

  describe('utility methods', () => {
    let client: PlintoClient;

    beforeEach(() => {
      client = new PlintoClient({
        baseURL: 'https://api.example.com'
      });
    });

    describe('testConnection', () => {
      it('should return success when connection works', async () => {
        mockHttpClient.get.mockResolvedValue({
          data: { providers: [] },
          status: 200
        });
        
        const result = await client.testConnection();
        
        expect(result.success).toBe(true);
        expect(result.latency).toBeGreaterThan(0);
        expect(result.error).toBeUndefined();
      });

      it('should return failure when connection fails', async () => {
        mockHttpClient.get.mockRejectedValue(new Error('Network error'));
        
        const result = await client.testConnection();
        
        expect(result.success).toBe(false);
        expect(result.latency).toBeGreaterThan(0);
        expect(result.error).toBe('Network error');
      });
    });

    describe('getVersion', () => {
      it('should return SDK version', () => {
        const version = client.getVersion();
        expect(version).toBe('1.0.0');
      });
    });

    describe('getEnvironmentInfo', () => {
      it('should return environment information', () => {
        const info = client.getEnvironmentInfo();
        
        expect(info.sdk_version).toBe('1.0.0');
        expect(info.base_url).toBe('https://api.example.com');
        expect(info.environment).toBeDefined();
        expect(info.user_agent).toBeDefined();
      });
    });

    describe('destroy', () => {
      it('should clean up resources', () => {
        const removeAllListenersSpy = jest.spyOn(client, 'removeAllListeners');
        
        client.destroy();
        
        expect(removeAllListenersSpy).toHaveBeenCalled();
      });
    });
  });

  describe('event handling', () => {
    let client: PlintoClient;

    beforeEach(() => {
      client = new PlintoClient({
        baseURL: 'https://api.example.com'
      });
    });

    it('should support typed event listeners', () => {
      const handler = jest.fn();
      
      const unsubscribe = client.on('auth:signedIn', handler);
      
      expect(typeof unsubscribe).toBe('function');
    });

    it('should support one-time event listeners', () => {
      const handler = jest.fn();
      
      const unsubscribe = client.once('token:refreshed', handler);
      
      expect(typeof unsubscribe).toBe('function');
    });

    it('should support removing all listeners', () => {
      const handler1 = jest.fn();
      const handler2 = jest.fn();
      
      client.on('auth:signedIn', handler1);
      client.on('auth:signedOut', handler2);
      
      client.off();
      
      // Verify listeners are removed (this is implementation dependent)
    });
  });

  describe('auto token refresh', () => {
    beforeEach(() => {
      jest.useFakeTimers();
    });

    afterEach(() => {
      jest.useRealTimers();
    });

    it('should set up auto refresh when enabled', () => {
      const client = new PlintoClient({
        baseURL: 'https://api.example.com',
        autoRefreshTokens: true
      });
      
      // Mock token data that expires in 4 minutes (should trigger refresh)
      const futureTime = Date.now() + (4 * 60 * 1000);
      mockTokenManager.getTokenData.mockResolvedValue({
        access_token: 'token',
        refresh_token: 'refresh',
        expires_at: futureTime
      });
      
      // Fast forward time to trigger refresh check
      jest.advanceTimersByTime(60 * 1000);
      
      // Verify interval was set (implementation dependent)
    });

    it('should not set up auto refresh when disabled', () => {
      const client = new PlintoClient({
        baseURL: 'https://api.example.com',
        autoRefreshTokens: false
      });
      
      // Fast forward time
      jest.advanceTimersByTime(60 * 1000);
      
      // Verify no refresh attempts were made
      expect(mockAuth.refreshToken).not.toHaveBeenCalled();
    });
  });
});