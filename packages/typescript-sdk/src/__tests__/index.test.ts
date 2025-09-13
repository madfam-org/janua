/**
 * Tests for TypeScript SDK main exports
 */

import * as PlintoSDK from '../index';
import { PlintoClient, createClient } from '../client';
import { SDK_VERSION, SDK_NAME } from '../index';

describe('Plinto TypeScript SDK - Main Exports', () => {
  describe('exports validation', () => {
    it('should export PlintoClient class', () => {
      expect(PlintoSDK.PlintoClient).toBeDefined();
      expect(typeof PlintoSDK.PlintoClient).toBe('function');
    });

    it('should export createClient function', () => {
      expect(PlintoSDK.createClient).toBeDefined();
      expect(typeof PlintoSDK.createClient).toBe('function');
    });

    it('should export default client', () => {
      expect(PlintoSDK.default).toBeDefined();
      expect(PlintoSDK.default).toBe(PlintoClient);
    });

    it('should export module classes', () => {
      expect(PlintoSDK.Auth).toBeDefined();
      expect(PlintoSDK.Users).toBeDefined();
      expect(PlintoSDK.Organizations).toBeDefined();
      expect(PlintoSDK.Webhooks).toBeDefined();
      expect(PlintoSDK.Admin).toBeDefined();
    });

    it('should export HTTP client classes', () => {
      expect(PlintoSDK.HttpClient).toBeDefined();
      expect(PlintoSDK.AxiosHttpClient).toBeDefined();
      expect(PlintoSDK.createHttpClient).toBeDefined();
    });

    it('should export error classes', () => {
      expect(PlintoSDK.PlintoError).toBeDefined();
      expect(PlintoSDK.AuthenticationError).toBeDefined();
      expect(PlintoSDK.ValidationError).toBeDefined();
      expect(PlintoSDK.NotFoundError).toBeDefined();
      expect(PlintoSDK.ConfigurationError).toBeDefined();
    });

    it('should export error type guards', () => {
      expect(PlintoSDK.isAuthenticationError).toBeDefined();
      expect(PlintoSDK.isValidationError).toBeDefined();
      expect(PlintoSDK.isPlintoError).toBeDefined();
    });

    it('should export utility classes', () => {
      expect(PlintoSDK.TokenManager).toBeDefined();
      expect(PlintoSDK.JwtUtils).toBeDefined();
      expect(PlintoSDK.EventEmitter).toBeDefined();
    });
  });

  describe('SDK metadata', () => {
    it('should export correct SDK version', () => {
      expect(SDK_VERSION).toBeDefined();
      expect(typeof SDK_VERSION).toBe('string');
      expect(SDK_VERSION).toMatch(/^\d+\.\d+\.\d+/);
    });

    it('should export correct SDK name', () => {
      expect(SDK_NAME).toBeDefined();
      expect(SDK_NAME).toBe('plinto-typescript-sdk');
    });
  });

  describe('examples object', () => {
    it('should provide code examples', () => {
      expect(PlintoSDK.examples).toBeDefined();
      expect(typeof PlintoSDK.examples).toBe('object');
      
      // Check for key examples
      expect(PlintoSDK.examples.basicClient).toBeDefined();
      expect(PlintoSDK.examples.signUp).toBeDefined();
      expect(PlintoSDK.examples.signIn).toBeDefined();
      expect(PlintoSDK.examples.getCurrentUser).toBeDefined();
      expect(PlintoSDK.examples.errorHandling).toBeDefined();
    });

    it('should provide valid TypeScript/JavaScript code in examples', () => {
      const { basicClient, signUp, signIn } = PlintoSDK.examples;
      
      // Basic syntax checks
      expect(basicClient).toContain('createClient');
      expect(signUp).toContain('auth.signUp');
      expect(signIn).toContain('auth.signIn');
    });
  });

  describe('presets object', () => {
    it('should provide configuration presets', () => {
      expect(PlintoSDK.presets).toBeDefined();
      expect(typeof PlintoSDK.presets).toBe('object');
      
      // Check for key presets
      expect(PlintoSDK.presets.development).toBeDefined();
      expect(PlintoSDK.presets.production).toBeDefined();
      expect(PlintoSDK.presets.browser).toBeDefined();
      expect(PlintoSDK.presets.server).toBeDefined();
    });

    it('should have valid development preset', () => {
      const { development } = PlintoSDK.presets;
      
      expect(development.baseURL).toBe('http://localhost:8000');
      expect(development.debug).toBe(true);
      expect(development.timeout).toBe(30000);
      expect(development.retryAttempts).toBe(1);
    });

    it('should have valid production preset', () => {
      const { production } = PlintoSDK.presets;
      
      expect(production.debug).toBe(false);
      expect(production.timeout).toBe(15000);
      expect(production.retryAttempts).toBe(3);
      expect(production.autoRefreshTokens).toBe(true);
    });

    it('should have valid browser preset', () => {
      const { browser } = PlintoSDK.presets;
      
      expect(browser.tokenStorage).toBe('localStorage');
      expect(browser.timeout).toBe(30000);
      expect(browser.autoRefreshTokens).toBe(true);
    });

    it('should have valid server preset', () => {
      const { server } = PlintoSDK.presets;
      
      expect(server.tokenStorage).toBe('memory');
      expect(server.timeout).toBe(10000);
      expect(server.autoRefreshTokens).toBe(false);
    });
  });

  describe('createClientWithPreset function', () => {
    it('should create client with development preset', () => {
      const client = PlintoSDK.createClientWithPreset('development', {
        baseURL: 'http://localhost:4000'
      });
      
      expect(client).toBeInstanceOf(PlintoClient);
      expect(client.getConfig().baseURL).toBe('http://localhost:4000');
      expect(client.getConfig().debug).toBe(true);
      expect(client.getConfig().retryAttempts).toBe(1);
    });

    it('should create client with production preset', () => {
      const client = PlintoSDK.createClientWithPreset('production', {
        baseURL: 'https://api.example.com'
      });
      
      expect(client).toBeInstanceOf(PlintoClient);
      expect(client.getConfig().baseURL).toBe('https://api.example.com');
      expect(client.getConfig().debug).toBe(false);
      expect(client.getConfig().retryAttempts).toBe(3);
    });

    it('should override preset values with custom config', () => {
      const client = PlintoSDK.createClientWithPreset('development', {
        baseURL: 'http://localhost:4000',
        debug: false,
        timeout: 10000
      });
      
      const config = client.getConfig();
      expect(config.baseURL).toBe('http://localhost:4000');
      expect(config.debug).toBe(false); // overridden
      expect(config.timeout).toBe(10000); // overridden
      expect(config.retryAttempts).toBe(1); // from preset
    });
  });

  describe('TypeScript types', () => {
    it('should be able to import and use types', () => {
      // This test ensures TypeScript compilation works
      const config: PlintoSDK.PlintoConfig = {
        baseURL: 'https://api.example.com',
        debug: true
      };
      
      expect(config.baseURL).toBe('https://api.example.com');
      expect(config.debug).toBe(true);
    });

    it('should have User type with required fields', () => {
      const user: PlintoSDK.User = {
        id: 'user-123',
        email: 'test@example.com',
        email_verified: true,
        phone_verified: false,
        status: PlintoSDK.UserStatus.ACTIVE,
        mfa_enabled: false,
        is_admin: false,
        created_at: '2023-01-01T00:00:00Z',
        updated_at: '2023-01-01T00:00:00Z',
        user_metadata: {}
      };
      
      expect(user.id).toBe('user-123');
      expect(user.email).toBe('test@example.com');
      expect(user.status).toBe(PlintoSDK.UserStatus.ACTIVE);
    });

    it('should have proper enum values', () => {
      expect(PlintoSDK.UserStatus.ACTIVE).toBe('active');
      expect(PlintoSDK.UserStatus.SUSPENDED).toBe('suspended');
      expect(PlintoSDK.UserStatus.DELETED).toBe('deleted');
      
      expect(PlintoSDK.OrganizationRole.OWNER).toBe('owner');
      expect(PlintoSDK.OrganizationRole.ADMIN).toBe('admin');
      expect(PlintoSDK.OrganizationRole.MEMBER).toBe('member');
      
      expect(PlintoSDK.OAuthProvider.GOOGLE).toBe('google');
      expect(PlintoSDK.OAuthProvider.GITHUB).toBe('github');
    });
  });
});