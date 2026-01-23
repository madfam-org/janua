import { test, expect } from '@playwright/test';

test.describe('API Integration Tests', () => {
  const apiBaseUrl = process.env.API_URL || 'http://localhost:4100';

  test('Health endpoint returns success', async ({ request }) => {
    const response = await request.get(`${apiBaseUrl}/health`);
    expect(response.ok()).toBeTruthy();
    expect(response.status()).toBe(200);

    const data = await response.json();
    expect(data).toHaveProperty('status');
    expect(data.status).toBe('healthy');
  });

  test('Ready endpoint shows all services healthy', async ({ request }) => {
    const response = await request.get(`${apiBaseUrl}/ready`);
    expect(response.ok()).toBeTruthy();
    expect(response.status()).toBe(200);

    const data = await response.json();
    expect(data).toHaveProperty('status');
    expect(data).toHaveProperty('database');
    expect(data).toHaveProperty('redis');
    expect(data.database).toHaveProperty('healthy');
    expect(data.database.healthy).toBe(true);
  });

  test('OpenID configuration endpoint is accessible', async ({ request }) => {
    const response = await request.get(`${apiBaseUrl}/.well-known/openid-configuration`);
    expect(response.ok()).toBeTruthy();
    expect(response.status()).toBe(200);

    const data = await response.json();
    expect(data).toHaveProperty('issuer');
    expect(data).toHaveProperty('authorization_endpoint');
    expect(data).toHaveProperty('token_endpoint');
    expect(data).toHaveProperty('jwks_uri');
    expect(data).toHaveProperty('response_types_supported');
    expect(data).toHaveProperty('subject_types_supported');
    expect(data).toHaveProperty('id_token_signing_alg_values_supported');
  });

  test('JWKS endpoint returns valid key set', async ({ request }) => {
    const response = await request.get(`${apiBaseUrl}/.well-known/jwks.json`);
    expect(response.ok()).toBeTruthy();
    expect(response.status()).toBe(200);

    const data = await response.json();
    expect(data).toHaveProperty('keys');
    expect(Array.isArray(data.keys)).toBeTruthy();

    if (data.keys.length > 0) {
      const firstKey = data.keys[0];
      expect(firstKey).toHaveProperty('kty');
      expect(firstKey).toHaveProperty('use');
      expect(firstKey).toHaveProperty('kid');
      expect(firstKey).toHaveProperty('alg');
    }
  });

  test('API documentation is accessible', async ({ request }) => {
    const response = await request.get(`${apiBaseUrl}/docs`);
    expect(response.ok()).toBeTruthy();
    expect(response.status()).toBe(200);

    const contentType = response.headers()['content-type'];
    expect(contentType).toContain('text/html');
  });

  test('API redoc documentation is accessible', async ({ request }) => {
    const response = await request.get(`${apiBaseUrl}/redoc`);
    expect(response.ok()).toBeTruthy();
    expect(response.status()).toBe(200);

    const contentType = response.headers()['content-type'];
    expect(contentType).toContain('text/html');
  });

  test('Security headers are present', async ({ request }) => {
    const response = await request.get(`${apiBaseUrl}/health`);
    expect(response.ok()).toBeTruthy();

    const headers = response.headers();
    expect(headers).toHaveProperty('x-content-type-options');
    expect(headers).toHaveProperty('x-frame-options');
    expect(headers['x-content-type-options']).toBe('nosniff');
    expect(headers['x-frame-options']).toBe('DENY');
  });
});

test.describe('API Error Handling', () => {
  const apiBaseUrl = process.env.API_URL || 'http://localhost:4100';

  test('Returns 404 for non-existent endpoint', async ({ request }) => {
    const response = await request.get(`${apiBaseUrl}/non-existent-endpoint-12345`);
    expect(response.status()).toBe(404);

    const data = await response.json();
    expect(data).toHaveProperty('error');
    expect(data.error).toHaveProperty('code');
    expect(data.error).toHaveProperty('message');
    expect(data.error.code).toBe('HTTP_ERROR');
    expect(data.error.message).toBe('Not Found');
  });

  test('Handles malformed requests gracefully', async ({ request }) => {
    const response = await request.post(`${apiBaseUrl}/auth/token`, {
      data: 'invalid-json-data',
      headers: {
        'Content-Type': 'application/json'
      },
      failOnStatusCode: false
    });

    // Should return 4xx error, not crash
    expect(response.status()).toBeGreaterThanOrEqual(400);
    expect(response.status()).toBeLessThan(500);
  });
});

test.describe('API Performance', () => {
  const apiBaseUrl = process.env.API_URL || 'http://localhost:4100';

  test('Health endpoint responds quickly', async ({ request }) => {
    const startTime = Date.now();
    const response = await request.get(`${apiBaseUrl}/health`);
    const endTime = Date.now();

    expect(response.ok()).toBeTruthy();
    expect(endTime - startTime).toBeLessThan(2000); // Should respond in under 2 seconds
  });

  test('Concurrent requests are handled properly', async ({ request }) => {
    const requests = Array(10).fill(null).map(() =>
      request.get(`${apiBaseUrl}/health`)
    );

    const responses = await Promise.all(requests);

    // All requests should succeed
    responses.forEach(response => {
      expect(response.ok()).toBeTruthy();
    });
  });
});
