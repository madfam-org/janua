/**
 * PKCE (Proof Key for Code Exchange) utilities for OAuth 2.0
 * Implements RFC 7636 for secure authorization code flow in browser applications.
 *
 * This is the single source of truth — framework SDKs re-export from here.
 */

const PKCE_STORAGE_KEYS = {
  codeVerifier: 'janua_pkce_verifier',
  state: 'janua_pkce_state',
} as const;

/**
 * Base64url encode a Uint8Array (RFC 4648 Section 5)
 */
function base64UrlEncode(buffer: Uint8Array): string {
  let binary = '';
  for (let i = 0; i < buffer.length; i++) {
    binary += String.fromCharCode(buffer[i]);
  }
  return btoa(binary)
    .replace(/\+/g, '-')
    .replace(/\//g, '_')
    .replace(/=+$/, '');
}

/** Generate a cryptographically random code verifier (43-128 chars) */
export function generateCodeVerifier(): string {
  const array = new Uint8Array(32);
  crypto.getRandomValues(array);
  return base64UrlEncode(array);
}

/** Generate code challenge from verifier using SHA-256 (S256 method) */
export async function generateCodeChallenge(verifier: string): Promise<string> {
  const encoder = new TextEncoder();
  const data = encoder.encode(verifier);
  const hash = await crypto.subtle.digest('SHA-256', data);
  return base64UrlEncode(new Uint8Array(hash));
}

/** Generate a random state parameter for CSRF protection */
export function generateState(): string {
  const array = new Uint8Array(16);
  crypto.getRandomValues(array);
  return base64UrlEncode(array);
}

/** Store PKCE parameters in sessionStorage */
export function storePKCEParams(verifier: string, state: string): void {
  try {
    sessionStorage.setItem(PKCE_STORAGE_KEYS.codeVerifier, verifier);
    sessionStorage.setItem(PKCE_STORAGE_KEYS.state, state);
  } catch (e) {
    console.warn('Failed to store PKCE parameters:', e);
  }
}

/** Retrieve PKCE parameters from sessionStorage */
export function retrievePKCEParams(): { verifier: string; state: string } | null {
  try {
    const verifier = sessionStorage.getItem(PKCE_STORAGE_KEYS.codeVerifier);
    const state = sessionStorage.getItem(PKCE_STORAGE_KEYS.state);
    if (!verifier || !state) return null;
    return { verifier, state };
  } catch (e) {
    console.warn('Failed to retrieve PKCE parameters:', e);
    return null;
  }
}

/** Clear PKCE parameters from sessionStorage */
export function clearPKCEParams(): void {
  try {
    sessionStorage.removeItem(PKCE_STORAGE_KEYS.codeVerifier);
    sessionStorage.removeItem(PKCE_STORAGE_KEYS.state);
  } catch (e) {
    console.warn('Failed to clear PKCE parameters:', e);
  }
}

/** Validate OAuth callback state against stored state */
export function validateState(callbackState: string): boolean {
  try {
    const storedState = sessionStorage.getItem(PKCE_STORAGE_KEYS.state);
    return storedState === callbackState;
  } catch (e) {
    console.warn('Failed to validate state:', e);
    return false;
  }
}

/** Parse OAuth callback URL for code and state parameters */
export function parseOAuthCallback(url?: string): {
  code?: string;
  state?: string;
  error?: string;
  error_description?: string;
} {
  const searchParams = new URLSearchParams(
    url ? new URL(url).search : window.location.search
  );
  return {
    code: searchParams.get('code') || undefined,
    state: searchParams.get('state') || undefined,
    error: searchParams.get('error') || undefined,
    error_description: searchParams.get('error_description') || undefined,
  };
}

/** Build OAuth authorization URL with PKCE parameters */
export function buildAuthorizationUrl(
  baseURL: string,
  provider: string,
  clientId: string,
  redirectUri: string,
  codeChallenge: string,
  state: string,
  scopes = 'openid profile email'
): string {
  const url = new URL(`${baseURL}/api/v1/auth/oauth/authorize/${provider}`);
  url.searchParams.set('client_id', clientId);
  url.searchParams.set('redirect_uri', redirectUri);
  url.searchParams.set('response_type', 'code');
  url.searchParams.set('scope', scopes);
  url.searchParams.set('code_challenge', codeChallenge);
  url.searchParams.set('code_challenge_method', 'S256');
  url.searchParams.set('state', state);
  return url.toString();
}

export { PKCE_STORAGE_KEYS };
