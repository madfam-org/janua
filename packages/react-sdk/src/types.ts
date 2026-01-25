/**
 * Type definitions for the Janua React SDK
 *
 * These types are designed for Dhanam compatibility while maintaining
 * consistency with the TypeScript SDK foundation.
 */

// Re-export core types from typescript-sdk for consistency
export type {
  User,
  Session,
  Organization,
  TokenResponse,
  JanuaConfig,
  Environment,
  UUID,
  ISODateString,
} from '@janua/typescript-sdk';

// Re-export error types and guards
export {
  JanuaError,
  AuthenticationError,
  ValidationError,
  NetworkError,
  TokenError,
  OAuthError,
  isAuthenticationError,
  isValidationError,
  isNetworkError,
  isJanuaError,
} from '@janua/typescript-sdk';

// Re-export OAuthProvider enum
export { OAuthProvider } from '@janua/typescript-sdk';

/**
 * Dhanam-compatible user type with computed fields
 * Maps the API User type to the format expected by Dhanam
 */
export interface JanuaUser {
  id: string;
  email: string;
  name: string | null;
  display_name: string | null;
  picture?: string;
  locale: string;
  timezone: string;
  mfa_enabled: boolean;
  email_verified: boolean;
  created_at: string;
  updated_at: string;
  organization_id?: string;
  organization_role?: string;
}

/**
 * Error codes for client-side error handling
 * Provides specific codes for common authentication scenarios
 */
export type JanuaErrorCode =
  | 'INVALID_CREDENTIALS'
  | 'TOKEN_EXPIRED'
  | 'TOKEN_INVALID'
  | 'REFRESH_FAILED'
  | 'NETWORK_ERROR'
  | 'MFA_REQUIRED'
  | 'EMAIL_NOT_VERIFIED'
  | 'ACCOUNT_SUSPENDED'
  | 'OAUTH_ERROR'
  | 'PKCE_ERROR'
  | 'UNAUTHORIZED'
  | 'UNKNOWN_ERROR';

/**
 * Simplified error interface for React components
 */
export interface JanuaErrorState {
  code: JanuaErrorCode;
  message: string;
  status?: number;
  details?: unknown;
}

/**
 * OAuth provider types (string literals for convenience)
 */
export type OAuthProviderName = 'google' | 'github' | 'microsoft' | 'apple' | 'discord' | 'twitter';

/**
 * OAuth callback result
 */
export interface OAuthCallbackResult {
  code: string;
  state: string;
  error?: string;
  error_description?: string;
}

/**
 * Storage keys used by the SDK
 * These match Dhanam's expected storage keys
 */
export const STORAGE_KEYS = {
  accessToken: 'janua_access_token',
  refreshToken: 'janua_refresh_token',
  user: 'janua_user',
  idToken: 'janua_id_token',
} as const;

/**
 * PKCE storage keys (sessionStorage)
 */
export const PKCE_STORAGE_KEYS = {
  codeVerifier: 'janua_pkce_verifier',
  state: 'janua_pkce_state',
} as const;

/**
 * Provider configuration for JanuaProvider
 * Extends the base JanuaConfig with React-specific options
 */
export interface JanuaProviderConfig {
  /** Base URL for the Janua API */
  baseURL: string;
  /** Optional API key for server-side requests */
  apiKey?: string;
  /** Client ID for OAuth flows */
  clientId?: string;
  /** Redirect URI for OAuth callbacks */
  redirectUri?: string;
  /** Environment setting */
  environment?: 'development' | 'staging' | 'production';
  /** Enable debug logging */
  debug?: boolean;
  /** Auto-refresh tokens before expiry */
  autoRefreshTokens?: boolean;
  /** Token storage type */
  tokenStorage?: 'localStorage' | 'sessionStorage' | 'memory';
}
