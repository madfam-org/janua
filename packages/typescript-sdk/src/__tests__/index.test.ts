/**
 * Tests for TypeScript SDK main exports
 */

import * as JanuaSDK from '../index';
import { JanuaClient } from '../client';
import { SDK_VERSION, SDK_NAME } from '../index';

describe('Janua TypeScript SDK - Main Exports', () => {
  describe('exports validation', () => {
    it('should export JanuaClient class', () => {
      expect(JanuaSDK.JanuaClient).toBeDefined();
      expect(typeof JanuaSDK.JanuaClient).toBe('function');
    });

    it('should export createClient function', () => {
      expect(JanuaSDK.createClient).toBeDefined();
      expect(typeof JanuaSDK.createClient).toBe('function');
    });

    it('should export default client', () => {
      expect(JanuaSDK.default).toBeDefined();
      expect(JanuaSDK.default).toBe(JanuaClient);
    });

    it('should export module classes', () => {
      expect(JanuaSDK.Auth).toBeDefined();
      expect(JanuaSDK.Users).toBeDefined();
      expect(JanuaSDK.Organizations).toBeDefined();
      expect(JanuaSDK.Webhooks).toBeDefined();
      expect(JanuaSDK.Admin).toBeDefined();
    });

    it('should export HTTP client classes', () => {
      expect(JanuaSDK.HttpClient).toBeDefined();
      expect(JanuaSDK.AxiosHttpClient).toBeDefined();
      expect(JanuaSDK.createHttpClient).toBeDefined();
    });

    it('should export error classes', () => {
      expect(JanuaSDK.JanuaError).toBeDefined();
      expect(JanuaSDK.AuthenticationError).toBeDefined();
      expect(JanuaSDK.ValidationError).toBeDefined();
      expect(JanuaSDK.NotFoundError).toBeDefined();
      expect(JanuaSDK.ConfigurationError).toBeDefined();
    });

    it('should export error type guards', () => {
      expect(JanuaSDK.isAuthenticationError).toBeDefined();
      expect(JanuaSDK.isValidationError).toBeDefined();
      expect(JanuaSDK.isJanuaError).toBeDefined();
    });

    it('should export utility classes', () => {
      expect(JanuaSDK.TokenManager).toBeDefined();
      expect(JanuaSDK.JwtUtils).toBeDefined();
      expect(JanuaSDK.EventEmitter).toBeDefined();
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
      expect(SDK_NAME).toBe('janua-typescript-sdk');
    });
  });

  describe('examples object', () => {
    it('should provide code examples', () => {
      expect(JanuaSDK.examples).toBeDefined();
      expect(typeof JanuaSDK.examples).toBe('object');

      // Check for key examples
      expect(JanuaSDK.examples.basicClient).toBeDefined();
      expect(JanuaSDK.examples.signUp).toBeDefined();
      expect(JanuaSDK.examples.signIn).toBeDefined();
      expect(JanuaSDK.examples.getCurrentUser).toBeDefined();
      expect(JanuaSDK.examples.errorHandling).toBeDefined();
    });

    it('should provide valid TypeScript/JavaScript code in examples', () => {
      const { basicClient, signUp, signIn } = JanuaSDK.examples;

      // Basic syntax checks
      expect(basicClient).toContain('createClient');
      expect(signUp).toContain('auth.signUp');
      expect(signIn).toContain('auth.signIn');
    });
  });

  describe('presets object', () => {
    it('should provide configuration presets', () => {
      expect(JanuaSDK.presets).toBeDefined();
      expect(typeof JanuaSDK.presets).toBe('object');

      // Check for key presets
      expect(JanuaSDK.presets.development).toBeDefined();
      expect(JanuaSDK.presets.production).toBeDefined();
      expect(JanuaSDK.presets.browser).toBeDefined();
      expect(JanuaSDK.presets.server).toBeDefined();
    });

    it('should have valid development preset', () => {
      const { development } = JanuaSDK.presets;

      expect(development.baseURL).toBe('http://localhost:8000');
      expect(development.debug).toBe(true);
      expect(development.timeout).toBe(30000);
      expect(development.retryAttempts).toBe(1);
    });

    it('should have valid production preset', () => {
      const { production } = JanuaSDK.presets;

      expect(production.debug).toBe(false);
      expect(production.timeout).toBe(15000);
      expect(production.retryAttempts).toBe(3);
      expect(production.autoRefreshTokens).toBe(true);
    });

    it('should have valid browser preset', () => {
      const { browser } = JanuaSDK.presets;

      expect(browser.tokenStorage).toBe('localStorage');
      expect(browser.timeout).toBe(30000);
      expect(browser.autoRefreshTokens).toBe(true);
    });

    it('should have valid server preset', () => {
      const { server } = JanuaSDK.presets;

      expect(server.tokenStorage).toBe('memory');
      expect(server.timeout).toBe(10000);
      expect(server.autoRefreshTokens).toBe(false);
    });
  });

  describe('createClientWithPreset function', () => {
    it('should create client with development preset', () => {
      const client = JanuaSDK.createClientWithPreset('development', {
        baseURL: 'http://localhost:4000'
      });

      expect(client).toBeInstanceOf(JanuaClient);
      expect(client.getConfig().baseURL).toBe('http://localhost:4000');
      expect(client.getConfig().debug).toBe(true);
      expect(client.getConfig().retryAttempts).toBe(1);
    });

    it('should create client with production preset', () => {
      const client = JanuaSDK.createClientWithPreset('production', {
        baseURL: 'https://api.example.com'
      });

      expect(client).toBeInstanceOf(JanuaClient);
      expect(client.getConfig().baseURL).toBe('https://api.example.com');
      expect(client.getConfig().debug).toBe(false);
      expect(client.getConfig().retryAttempts).toBe(3);
    });

    it('should override preset values with custom config', () => {
      const client = JanuaSDK.createClientWithPreset('development', {
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
      const config: JanuaSDK.JanuaConfig = {
        baseURL: 'https://api.example.com',
        debug: true
      };

      expect(config.baseURL).toBe('https://api.example.com');
      expect(config.debug).toBe(true);
    });

    it('should have User type with required fields', () => {
      const user: JanuaSDK.User = {
        id: 'user-123',
        email: 'test@example.com',
        email_verified: true,
        phone_verified: false,
        status: JanuaSDK.UserStatus.ACTIVE,
        mfa_enabled: false,
        is_admin: false,
        created_at: '2023-01-01T00:00:00Z',
        updated_at: '2023-01-01T00:00:00Z',
        user_metadata: {}
      };

      expect(user.id).toBe('user-123');
      expect(user.email).toBe('test@example.com');
      expect(user.status).toBe(JanuaSDK.UserStatus.ACTIVE);
    });

    it('should have proper enum values', () => {
      expect(JanuaSDK.UserStatus.ACTIVE).toBe('active');
      expect(JanuaSDK.UserStatus.SUSPENDED).toBe('suspended');
      expect(JanuaSDK.UserStatus.DELETED).toBe('deleted');

      expect(JanuaSDK.OrganizationRole.OWNER).toBe('owner');
      expect(JanuaSDK.OrganizationRole.ADMIN).toBe('admin');
      expect(JanuaSDK.OrganizationRole.MEMBER).toBe('member');

      expect(JanuaSDK.OAuthProvider.GOOGLE).toBe('google');
      expect(JanuaSDK.OAuthProvider.GITHUB).toBe('github');
    });
  });
});
