export interface PlintoConfig {
  appId: string;
  apiKey?: string;
  apiUrl?: string;
  debug?: boolean;
}

export interface User {
  id: string;
  email: string;
  emailVerified: boolean;
  firstName?: string;
  lastName?: string;
  username?: string;
  profileImageUrl?: string;
  metadata?: Record<string, any>;
  createdAt: string;
  updatedAt: string;
  lastSignInAt?: string;
}

export interface Session {
  id: string;
  userId: string;
  expiresAt: string;
  lastActiveAt: string;
  status: 'active' | 'expired' | 'revoked';
}

export interface AuthTokens {
  accessToken: string;
  refreshToken: string;
  idToken?: string;
  expiresIn: number;
}

export interface SignUpRequest {
  email: string;
  password: string;
  firstName?: string;
  lastName?: string;
  username?: string;
  metadata?: Record<string, any>;
}

export interface SignInRequest {
  email?: string;
  username?: string;
  password: string;
}

export interface SignInResponse {
  user: User;
  session: Session;
  tokens: AuthTokens;
}

export interface SignUpResponse {
  user: User;
  session: Session;
  tokens: AuthTokens;
}

export interface PasswordResetRequest {
  email: string;
}

export interface PasswordResetConfirm {
  token: string;
  newPassword: string;
}

export interface UpdateUserRequest {
  firstName?: string;
  lastName?: string;
  username?: string;
  profileImageUrl?: string;
  metadata?: Record<string, any>;
}

export interface VerifyEmailRequest {
  token: string;
}

export interface MagicLinkRequest {
  email: string;
  redirectUrl?: string;
}

export interface OAuthProvider {
  provider: 'google' | 'github' | 'microsoft' | 'apple' | 'discord' | 'twitter' | 'linkedin';
  redirectUrl?: string;
  scopes?: string[];
}

export interface PasskeyRegistrationOptions {
  username?: string;
  displayName?: string;
  authenticatorAttachment?: 'platform' | 'cross-platform';
}

export interface OrganizationInfo {
  id: string;
  name: string;
  slug: string;
  logoUrl?: string;
  createdAt: string;
  updatedAt: string;
}

export interface OrganizationMembership {
  id: string;
  organizationId: string;
  userId: string;
  role: string;
  permissions: string[];
  createdAt: string;
  updatedAt: string;
}

export interface PlintoError extends Error {
  code: string;
  statusCode?: number;
  details?: any;
}