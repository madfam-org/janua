/**
 * PKCE (Proof Key for Code Exchange) utilities for OAuth 2.0
 *
 * Implements RFC 7636 for secure authorization code flow in browser applications.
 * https://datatracker.ietf.org/doc/html/rfc7636
 */

import { PKCE_STORAGE_KEYS } from '../types';

/**
 * Generate a cryptographically random code verifier
 * RFC 7636 recommends 43-128 characters from the unreserved character set
 *
 * @returns A random string of 43-128 characters
 */
export function generateCodeVerifier(): string {
  const array = new Uint8Array(32);
  crypto.getRandomValues(array);
  return base64UrlEncode(array);
}

/**
 * Generate code challenge from code verifier using SHA-256
 * RFC 7636 Section 4.2 - S256 method
 *
 * @param verifier - The code verifier string
 * @returns Promise resolving to the base64url-encoded SHA-256 hash
 */
export async function generateCodeChallenge(verifier: string): Promise<string> {
  const encoder = new TextEncoder();
  const data = encoder.encode(verifier);
  const hash = await crypto.subtle.digest('SHA-256', data);
  return base64UrlEncode(new Uint8Array(hash));
}

/**
 * Generate a random state parameter for CSRF protection
 *
 * @returns A random string for state validation
 */
export function generateState(): string {
  const array = new Uint8Array(16);
  crypto.getRandomValues(array);
  return base64UrlEncode(array);
}

/**
 * Base64url encode a Uint8Array
 * RFC 4648 Section 5 - Base64 with URL and Filename Safe Alphabet
 *
 * @param buffer - The data to encode
 * @returns Base64url-encoded string without padding
 */
function base64UrlEncode(buffer: Uint8Array): string {
  // Convert Uint8Array to binary string
  let binary = '';
  for (let i = 0; i < buffer.length; i++) {
    binary += String.fromCharCode(buffer[i]);
  }

  // Base64 encode and convert to URL-safe format
  return btoa(binary)
    .replace(/\+/g, '-')
    .replace(/\//g, '_')
    .replace(/=+$/, '');
}

/**
 * Store PKCE parameters in sessionStorage
 *
 * @param verifier - The code verifier
 * @param state - The state parameter
 */
export function storePKCEParams(verifier: string, state: string): void {
  try {
    sessionStorage.setItem(PKCE_STORAGE_KEYS.codeVerifier, verifier);
    sessionStorage.setItem(PKCE_STORAGE_KEYS.state, state);
  } catch (e) {
    // sessionStorage may be unavailable in some contexts
    console.warn('Failed to store PKCE parameters in sessionStorage:', e);
  }
}

/**
 * Retrieve and clear PKCE parameters from sessionStorage
 *
 * @returns Object containing verifier and state, or null if not found
 */
export function retrievePKCEParams(): { verifier: string; state: string } | null {
  try {
    const verifier = sessionStorage.getItem(PKCE_STORAGE_KEYS.codeVerifier);
    const state = sessionStorage.getItem(PKCE_STORAGE_KEYS.state);

    if (!verifier || !state) {
      return null;
    }

    return { verifier, state };
  } catch (e) {
    console.warn('Failed to retrieve PKCE parameters from sessionStorage:', e);
    return null;
  }
}

/**
 * Clear PKCE parameters from sessionStorage
 */
export function clearPKCEParams(): void {
  try {
    sessionStorage.removeItem(PKCE_STORAGE_KEYS.codeVerifier);
    sessionStorage.removeItem(PKCE_STORAGE_KEYS.state);
  } catch (e) {
    console.warn('Failed to clear PKCE parameters from sessionStorage:', e);
  }
}

/**
 * Validate OAuth callback state against stored state
 *
 * @param callbackState - The state returned in the OAuth callback
 * @returns True if state matches, false otherwise
 */
export function validateState(callbackState: string): boolean {
  try {
    const storedState = sessionStorage.getItem(PKCE_STORAGE_KEYS.state);
    return storedState === callbackState;
  } catch (e) {
    console.warn('Failed to validate state:', e);
    return false;
  }
}

/**
 * Parse OAuth callback URL for code and state parameters
 *
 * @param url - The callback URL (defaults to current window.location)
 * @returns Object with code, state, and optional error parameters
 */
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

/**
 * Build OAuth authorization URL with PKCE parameters
 *
 * @param baseURL - The API base URL
 * @param provider - The OAuth provider name
 * @param clientId - The client ID
 * @param redirectUri - The redirect URI
 * @param codeChallenge - The PKCE code challenge
 * @param state - The state parameter
 * @param scopes - Optional scopes (defaults to 'openid profile email')
 * @returns The complete authorization URL
 */
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
