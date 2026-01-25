/**
 * @janua/react-sdk
 *
 * Official Janua SDK for React applications.
 * Provides authentication context, hooks, and components.
 */

// Provider and main hook
export { JanuaProvider, useJanua } from './provider';
export type { JanuaContextValue, JanuaProviderProps, SignUpOptions } from './provider';

// Specialized hooks
export { useAuth } from './hooks/use-auth';
export type { UseAuthReturn } from './hooks/use-auth';
export { useOrganization } from './hooks/use-organization';
export { useSession } from './hooks/use-session';

// Components
export { SignIn } from './components/SignIn';
export { SignUp } from './components/SignUp';
export { UserProfile } from './components/UserProfile';

// Types
export type {
  // Dhanam-compatible user type
  JanuaUser,
  // Error types
  JanuaErrorCode,
  JanuaErrorState,
  // OAuth types
  OAuthProviderName,
  OAuthCallbackResult,
  // Config type
  JanuaProviderConfig,
} from './types';

// Storage key constants
export { STORAGE_KEYS, PKCE_STORAGE_KEYS } from './types';

// Re-export core types from typescript-sdk for convenience
export type {
  User,
  Session,
  Organization,
  TokenResponse,
  JanuaConfig,
  Environment,
} from './types';

// Re-export error types from typescript-sdk
export {
  JanuaError,
  AuthenticationError,
  ValidationError,
  NetworkError,
  TokenError,
  OAuthError,
  OAuthProvider,
  isAuthenticationError,
  isValidationError,
  isNetworkError,
  isJanuaError,
} from './types';

// Utilities
export {
  // PKCE utilities for custom OAuth flows
  generateCodeVerifier,
  generateCodeChallenge,
  generateState,
  storePKCEParams,
  retrievePKCEParams,
  clearPKCEParams,
  validateState,
  parseOAuthCallback,
  buildAuthorizationUrl,
  // Error utilities
  createErrorState,
  mapErrorToState,
  isAuthRequiredError,
  isNetworkIssue,
  getUserFriendlyMessage,
  ReactJanuaError,
} from './utils';

// Version
export const SDK_VERSION = '0.1.0';
export const SDK_NAME = '@janua/react-sdk';
