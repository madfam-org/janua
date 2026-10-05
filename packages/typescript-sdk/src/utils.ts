/**
 * Utility functions for the Janua TypeScript SDK
 * This file re-exports utilities from modular files for backward compatibility
 */

// Re-export all utilities from modular files
export {
  // Token utilities
  Base64Url,
  JwtUtils,
  LocalTokenStorage,
  SessionTokenStorage,
  MemoryTokenStorage,
  TokenManager,

  // Validation utilities
  ValidationUtils,

  // Event utilities
  EventEmitter,

  // Date utilities
  DateUtils,

  // URL and HTTP utilities
  UrlUtils,
  HttpStatusUtils,

  // Environment utilities
  EnvUtils,

  // Retry utilities
  RetryUtils,
  type RetryOptions,

  // Webhook utilities
  WebhookUtils,

  // PKCE utilities
  generateCodeVerifier,
  generateCodeChallenge,
  generateState,
  storePKCEParams,
  retrievePKCEParams,
  clearPKCEParams,
  validateState,
  parseOAuthCallback,
  buildAuthorizationUrl,
  buildJanuaAuthorizeUrl,
  stripTrailingSlashes,
  PKCE_STORAGE_KEYS,

  // WebAuthn binary encoding (base64url <-> ArrayBuffer)
  base64UrlToArrayBuffer,
  arrayBufferToBase64Url,
} from './utils/index';

// Re-export type aliases for backward compatibility
export type { TokenStorage, TokenStorage as ITokenStorage } from './utils/index';
