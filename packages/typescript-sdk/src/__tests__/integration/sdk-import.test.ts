/**
 * Integration test to ensure SDK can be imported and instantiated
 * This prevents regression of the circular dependency and module export issues
 */

import { PlintoClient, createClient } from '../../index';

describe('SDK Import and Instantiation', () => {
  test('SDK exports are available', () => {
    expect(PlintoClient).toBeDefined();
    expect(createClient).toBeDefined();
    expect(typeof PlintoClient).toBe('function');
    expect(typeof createClient).toBe('function');
  });

  test('Can instantiate PlintoClient directly', () => {
    const client = new PlintoClient({
      baseURL: 'https://api.plinto.dev'
    });

    expect(client).toBeInstanceOf(PlintoClient);
    expect(client.auth).toBeDefined();
    expect(client.users).toBeDefined();
    expect(client.sessions).toBeDefined();
    expect(client.organizations).toBeDefined();
    expect(client.webhooks).toBeDefined();
    expect(client.admin).toBeDefined();
  });

  test('Can create client using factory function', () => {
    const client = createClient({
      baseURL: 'https://api.plinto.dev'
    });

    expect(client).toBeInstanceOf(PlintoClient);
  });

  test('All convenience methods are present', () => {
    const client = new PlintoClient({
      baseURL: 'https://api.plinto.dev'
    });

    expect(typeof client.signIn).toBe('function');
    expect(typeof client.signUp).toBe('function');
    expect(typeof client.signOut).toBe('function');
    expect(typeof client.getCurrentUser).toBe('function');
    expect(typeof client.isAuthenticated).toBe('function');
    expect(typeof client.getAccessToken).toBe('function');
    expect(typeof client.getRefreshToken).toBe('function');
  });

  test('Enterprise features are accessible', () => {
    const client = new PlintoClient({
      baseURL: 'https://api.plinto.dev'
    });

    expect(typeof client.validateLicense).toBe('function');
    expect(typeof client.hasFeature).toBe('function');
    expect(typeof client.setLicenseKey).toBe('function');
    expect(typeof client.enableSSO).toBe('function');
    expect(typeof client.getAuditLogs).toBe('function');
  });

  test('No circular dependency errors on import', () => {
    // This test passes if the import statement at the top doesn't throw
    // The circular dependency issue manifested as "Cannot access 'PLANS' before initialization"
    expect(true).toBe(true);
  });
});