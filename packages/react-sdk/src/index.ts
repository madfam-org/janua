/**
 * @janua/react-sdk
 *
 * Official Janua SDK for React applications.
 * Provides authentication context, hooks, and components.
 */

// Provider and main hook
export { JanuaProvider, useJanua } from './provider';
export type { JanuaContextValue, JanuaProviderProps, SignUpOptions, JanuaAppearance } from './provider';

// Specialized hooks
export { useAuth } from './hooks/use-auth';
export type { UseAuthReturn } from './hooks/use-auth';
export { useOrganization } from './hooks/use-organization';
export { useSession } from './hooks/use-session';
export { useUser } from './hooks/use-user';
export type { UseUserReturn } from './hooks/use-user';
export { usePasskey } from './hooks/use-passkey';
export type { UsePasskeyReturn } from './hooks/use-passkey';
export { useMFA } from './hooks/use-mfa';
export type { UseMFAReturn } from './hooks/use-mfa';
export { useRealtime } from './hooks/use-realtime';
export type { UseRealtimeOptions, UseRealtimeReturn } from './hooks/use-realtime';

// Components
export { SignIn } from './components/SignIn';
export type { SignInProps } from './components/SignIn';
export { SignUp } from './components/SignUp';
export type { SignUpProps } from './components/SignUp';
export { UserProfile } from './components/UserProfile';
export type { UserProfileProps } from './components/UserProfile';
export { UserButton } from './components/UserButton';
export type { UserButtonProps } from './components/UserButton';
export { Protect } from './components/Protect';
export type { ProtectProps } from './components/Protect';
export { AuthGuard } from './components/AuthGuard';
export type { AuthGuardProps } from './components/AuthGuard';
export { OrgSwitcher } from './components/OrgSwitcher';
export type { OrgSwitcherProps } from './components/OrgSwitcher';
export { SignedIn } from './components/SignedIn';
export type { SignedInProps } from './components/SignedIn';
export { SignedOut } from './components/SignedOut';
export type { SignedOutProps } from './components/SignedOut';
export { MFAChallenge } from './components/MFAChallenge';
export type { MFAChallengeProps } from './components/MFAChallenge';

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
export const SDK_VERSION = '0.1.3';
export const SDK_NAME = '@janua/react-sdk';
