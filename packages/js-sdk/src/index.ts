// Main client
export { PlintoClient } from './client';
export { PlintoClient as default } from './client';

// Sub-clients
export { AuthClient } from './auth';
export { UserClient } from './users';
export { OrganizationClient } from './organizations';

// Types
export type {
  PlintoConfig,
  User,
  Session,
  AuthTokens,
  SignUpRequest,
  SignInRequest,
  SignInResponse,
  SignUpResponse,
  PasswordResetRequest,
  PasswordResetConfirm,
  UpdateUserRequest,
  VerifyEmailRequest,
  MagicLinkRequest,
  OAuthProvider,
  PasskeyRegistrationOptions,
  OrganizationInfo,
  OrganizationMembership,
  PlintoError,
} from './types';

// Organization types
export type {
  CreateOrganizationRequest,
  UpdateOrganizationRequest,
  InviteMemberRequest,
  UpdateMemberRequest,
} from './organizations';

// Utilities
export { createStorage } from './utils/storage';
export type { StorageAdapter } from './utils/storage';

// Version
export const VERSION = '0.1.0';

// Quick initialization helper
export function createClient(config: import('./types').PlintoConfig): import('./client').PlintoClient {
  return new (require('./client').PlintoClient)(config);
}