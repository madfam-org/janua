/**
 * Tests for the "Sign in with Janua" OIDC PROVIDER flow.
 *
 * These cover the dedicated OIDC methods (getJanuaAuthorizeUrl /
 * initiateJanuaSSO / handleJanuaSSOCallback) that target Janua's own
 * authorization server (`/api/v1/oauth/authorize` + `/api/v1/oauth/token`),
 * NOT the social OAuth proxy path.
 */

import { webcrypto } from 'crypto';
import { TextEncoder as NodeTextEncoder } from 'util';
import { Auth } from '../../auth';
import { HttpClient } from '../../http-client';
import { TokenManager } from '../../utils';
import { clearPKCEParams, retrievePKCEParams, PKCE_STORAGE_KEYS } from '../../utils';

// jsdom does not ship WebCrypto SubtleCrypto; use Node's implementation so
// generateCodeVerifier / generateCodeChallenge (S256) work in tests.
beforeAll(() => {
  if (!globalThis.crypto || !globalThis.crypto.subtle) {
    Object.defineProperty(globalThis, 'crypto', {
      value: webcrypto,
      configurable: true,
    });
  }
  if (typeof (globalThis as any).TextEncoder === 'undefined') {
    (globalThis as any).TextEncoder = NodeTextEncoder;
  }
});

const BASE_URL = 'https://auth.madfam.io';

describe('Auth - Sign in with Janua (OIDC provider flow)', () => {
  let auth: Auth;
  let mockHttpClient: jest.Mocked<HttpClient>;
  let mockTokenManager: jest.Mocked<TokenManager>;
  let mockOnSignIn: jest.Mock;

  beforeEach(() => {
    jest.clearAllMocks();
    clearPKCEParams();

    mockHttpClient = {
      get: jest.fn(),
      post: jest.fn(),
      put: jest.fn(),
      delete: jest.fn(),
      patch: jest.fn(),
    } as any;

    mockTokenManager = {
      setTokens: jest.fn(),
      clearTokens: jest.fn(),
      getAccessToken: jest.fn(),
      getRefreshToken: jest.fn(),
      hasValidTokens: jest.fn(),
    } as any;

    mockOnSignIn = jest.fn();

    auth = new Auth(mockHttpClient, mockTokenManager, mockOnSignIn, jest.fn(), BASE_URL);
  });

  describe('getJanuaAuthorizeUrl', () => {
    it('builds the OIDC provider authorize URL with PKCE and persists verifier + state', async () => {
      const result = await auth.getJanuaAuthorizeUrl({
        clientId: 'dhanam-web',
        redirectUri: 'https://app.dhan.am/auth/callback',
      });

      const url = new URL(result.url);

      // Correct endpoint — the OIDC PROVIDER path, NOT the social proxy path.
      expect(url.origin + url.pathname).toBe(`${BASE_URL}/api/v1/oauth/authorize`);
      expect(url.pathname).not.toContain('/auth/oauth/authorize/janua');

      expect(url.searchParams.get('response_type')).toBe('code');
      expect(url.searchParams.get('client_id')).toBe('dhanam-web');
      expect(url.searchParams.get('redirect_uri')).toBe('https://app.dhan.am/auth/callback');
      expect(url.searchParams.get('scope')).toBe('openid profile email');
      expect(url.searchParams.get('code_challenge_method')).toBe('S256');

      const challenge = url.searchParams.get('code_challenge');
      expect(challenge).toBeTruthy();
      // base64url — no +, /, or = padding
      expect(challenge).not.toMatch(/[+/=]/);

      const state = url.searchParams.get('state');
      expect(state).toBe(result.state);

      // Verifier + state persisted for the callback.
      const persisted = retrievePKCEParams();
      expect(persisted?.verifier).toBe(result.codeVerifier);
      expect(persisted?.state).toBe(result.state);
      expect(sessionStorage.getItem(PKCE_STORAGE_KEYS.codeVerifier)).toBe(result.codeVerifier);
    });

    it('honors custom scopes, nonce, prompt, and explicit state', async () => {
      const result = await auth.getJanuaAuthorizeUrl({
        clientId: 'enclii-dispatch',
        redirectUri: 'https://admin.enclii.dev/callback',
        scopes: ['openid', 'email'],
        nonce: 'n-123',
        prompt: 'none',
        state: 'fixed-state',
      });

      const url = new URL(result.url);
      expect(url.searchParams.get('scope')).toBe('openid email');
      expect(url.searchParams.get('nonce')).toBe('n-123');
      expect(url.searchParams.get('prompt')).toBe('none');
      expect(url.searchParams.get('state')).toBe('fixed-state');
      expect(result.state).toBe('fixed-state');
    });

    it('throws when clientId is missing', async () => {
      await expect(
        auth.getJanuaAuthorizeUrl({ clientId: '', redirectUri: 'https://x/cb' })
      ).rejects.toThrow(/clientId/i);
    });

    it('throws when redirectUri is missing', async () => {
      await expect(
        auth.getJanuaAuthorizeUrl({ clientId: 'x', redirectUri: '' })
      ).rejects.toThrow(/redirectUri/i);
    });

    it('throws when no base URL is configured or provided', async () => {
      const noBaseAuth = new Auth(mockHttpClient, mockTokenManager, mockOnSignIn, jest.fn());
      await expect(
        noBaseAuth.getJanuaAuthorizeUrl({ clientId: 'x', redirectUri: 'https://x/cb' })
      ).rejects.toThrow(/base URL/i);
    });
  });

  describe('handleJanuaSSOCallback', () => {
    beforeEach(() => {
      (global.fetch as jest.Mock).mockReset();
    });

    it('exchanges the code at the OIDC token endpoint (form-encoded) and stores tokens', async () => {
      // Seed a matching state + verifier as if initiation happened.
      const { state, codeVerifier } = await auth.getJanuaAuthorizeUrl({
        clientId: 'dhanam-web',
        redirectUri: 'https://app.dhan.am/auth/callback',
      });

      (global.fetch as jest.Mock).mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => ({
          access_token: 'oidc_access',
          refresh_token: 'oidc_refresh',
          token_type: 'Bearer',
          expires_in: 3600,
          id_token: 'oidc_id',
          scope: 'openid profile email',
        }),
      });

      const tokens = await auth.handleJanuaSSOCallback('auth-code-123', state, {
        clientId: 'dhanam-web',
        redirectUri: 'https://app.dhan.am/auth/callback',
      });

      // Correct endpoint + form-encoded body with PKCE verifier.
      const [calledUrl, init] = (global.fetch as jest.Mock).mock.calls[0];
      expect(calledUrl).toBe(`${BASE_URL}/api/v1/oauth/token`);
      expect(init.method).toBe('POST');
      expect(init.headers['Content-Type']).toBe('application/x-www-form-urlencoded');

      const sent = new URLSearchParams(init.body as string);
      expect(sent.get('grant_type')).toBe('authorization_code');
      expect(sent.get('code')).toBe('auth-code-123');
      expect(sent.get('client_id')).toBe('dhanam-web');
      expect(sent.get('redirect_uri')).toBe('https://app.dhan.am/auth/callback');
      expect(sent.get('code_verifier')).toBe(codeVerifier);

      expect(tokens.access_token).toBe('oidc_access');
      expect(tokens.id_token).toBe('oidc_id');

      expect(mockTokenManager.setTokens).toHaveBeenCalledWith(
        expect.objectContaining({
          access_token: 'oidc_access',
          refresh_token: 'oidc_refresh',
        })
      );
      expect(mockOnSignIn).toHaveBeenCalled();

      // PKCE material cleared after a successful exchange.
      expect(retrievePKCEParams()).toBeNull();
    });

    it('rejects a mismatched state (CSRF) without calling the token endpoint', async () => {
      await auth.getJanuaAuthorizeUrl({
        clientId: 'dhanam-web',
        redirectUri: 'https://app.dhan.am/auth/callback',
      });

      await expect(
        auth.handleJanuaSSOCallback('code', 'not-the-stored-state', {
          clientId: 'dhanam-web',
          redirectUri: 'https://app.dhan.am/auth/callback',
        })
      ).rejects.toThrow(/state/i);

      expect(global.fetch).not.toHaveBeenCalled();
      expect(mockTokenManager.setTokens).not.toHaveBeenCalled();
    });

    it('surfaces token-endpoint errors and clears PKCE material', async () => {
      const { state } = await auth.getJanuaAuthorizeUrl({
        clientId: 'dhanam-web',
        redirectUri: 'https://app.dhan.am/auth/callback',
      });

      (global.fetch as jest.Mock).mockResolvedValue({
        ok: false,
        status: 400,
        json: async () => ({ detail: 'invalid_grant: PKCE verification failed' }),
      });

      await expect(
        auth.handleJanuaSSOCallback('bad-code', state, {
          clientId: 'dhanam-web',
          redirectUri: 'https://app.dhan.am/auth/callback',
        })
      ).rejects.toThrow(/PKCE verification failed/);

      expect(mockTokenManager.setTokens).not.toHaveBeenCalled();
      expect(retrievePKCEParams()).toBeNull();
    });

    it('throws when no PKCE verifier is available', async () => {
      // Provide a matching state so state-validation passes, but no verifier.
      sessionStorage.setItem(PKCE_STORAGE_KEYS.state, 'the-state');

      await expect(
        auth.handleJanuaSSOCallback('code', 'the-state', {
          clientId: 'dhanam-web',
          redirectUri: 'https://app.dhan.am/auth/callback',
        })
      ).rejects.toThrow(/code_verifier/i);
    });
  });

  describe('deliberate account switching', () => {
    const registration = { clientId: 'fixture-rp', redirectUri: 'https://rp.example.test/callback' };

    it('forces the hosted chooser and preserves current tokens until the RP callback completes', async () => {
      const start = jest.spyOn(auth, 'initiateJanuaSSO').mockResolvedValue(undefined);
      await auth.switchAccount({ ...registration, prompt: 'none' } as any);
      expect(start).toHaveBeenCalledWith({ ...registration, prompt: 'select_account' });
      expect(mockTokenManager.clearTokens).not.toHaveBeenCalled();
      expect(mockTokenManager.setTokens).not.toHaveBeenCalled();
      expect(mockHttpClient.post).not.toHaveBeenCalled();
      expect(mockOnSignIn).not.toHaveBeenCalled();
    });

    it('adds another account through fresh credential and MFA proof, without logout', async () => {
      const start = jest.spyOn(auth, 'initiateJanuaSSO').mockResolvedValue(undefined);
      await auth.addAccount({ ...registration, prompt: 'none' } as any);
      expect(start).toHaveBeenCalledWith({ ...registration, prompt: 'login' });
      expect(mockTokenManager.clearTokens).not.toHaveBeenCalled();
      expect(mockHttpClient.post).not.toHaveBeenCalled();
    });

    it('does not discard the active RP session when selection cannot start', async () => {
      jest.spyOn(auth, 'initiateJanuaSSO').mockRejectedValue(new Error('Cannot start authorization'));
      await expect(auth.switchAccount(registration)).rejects.toThrow('Cannot start authorization');
      expect(mockTokenManager.clearTokens).not.toHaveBeenCalled();
      expect(mockTokenManager.setTokens).not.toHaveBeenCalled();
    });
  });
});
