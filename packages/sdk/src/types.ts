export interface PlintoConfig {
  issuer: string;
  clientId: string;
  redirectUri: string;
  audience?: string;
  scope?: string;
  responseType?: 'code' | 'token';
  prompt?: 'none' | 'login' | 'consent' | 'select_account';
  maxAge?: number;
  uiLocales?: string;
  loginHint?: string;
  acrValues?: string;
  storage?: 'local' | 'session' | 'memory';
  cacheLocation?: 'localStorage' | 'sessionStorage' | 'memory';
  useRefreshTokens?: boolean;
  authorizeTimeoutInSeconds?: number;
}

export interface AuthTokens {
  access_token: string;
  refresh_token?: string;
  id_token?: string;
  token_type: string;
  expires_in: number;
  scope?: string;
}

export interface User {
  id: string;
  email: string;
  email_verified: boolean;
  name?: string;
  picture?: string;
  given_name?: string;
  family_name?: string;
  locale?: string;
  created_at: string;
  updated_at: string;
  metadata?: Record<string, any>;
}

export interface SignInCredentials {
  email: string;
  password: string;
  rememberMe?: boolean;
}

export interface SignUpCredentials {
  email: string;
  password: string;
  name?: string;
  given_name?: string;
  family_name?: string;
  picture?: string;
  metadata?: Record<string, any>;
}

export interface PasswordResetRequest {
  email: string;
}

export interface PasswordResetConfirmation {
  token: string;
  password: string;
}

export interface ChangePasswordRequest {
  current_password: string;
  new_password: string;
}

export interface UpdateUserRequest {
  name?: string;
  given_name?: string;
  family_name?: string;
  picture?: string;
  metadata?: Record<string, any>;
}

export interface Session {
  id: string;
  user_id: string;
  created_at: string;
  last_active: string;
  expires_at: string;
  ip_address: string;
  user_agent: string;
  device_name?: string;
  location?: {
    country?: string;
    city?: string;
  };
}

export interface Organization {
  id: string;
  name: string;
  slug: string;
  logo?: string;
  created_at: string;
  updated_at: string;
  metadata?: Record<string, any>;
}

export interface OrganizationMember {
  id: string;
  user_id: string;
  organization_id: string;
  role: string;
  permissions: string[];
  joined_at: string;
}

export interface TokenIntrospection {
  active: boolean;
  scope?: string;
  client_id?: string;
  username?: string;
  token_type?: string;
  exp?: number;
  iat?: number;
  nbf?: number;
  sub?: string;
  aud?: string | string[];
  iss?: string;
  jti?: string;
  email?: string;
  email_verified?: boolean;
}

export interface MFAEnrollment {
  secret: string;
  qr_code: string;
  backup_codes: string[];
  recovery_codes?: string[];
}

export interface MFAChallenge {
  mfa_token: string;
  mfa_required: boolean;
  methods: ('totp' | 'sms' | 'email')[];
}

export interface MFAVerification {
  mfa_token: string;
  code: string;
  method?: 'totp' | 'sms' | 'email';
}

export interface ErrorResponse {
  error: string;
  error_description?: string;
  error_uri?: string;
  state?: string;
}

export interface PlintoError extends Error {
  code?: string;
  status?: number;
  response?: ErrorResponse;
}

export interface RetryOptions {
  maxAttempts?: number;
  delay?: number;
  backoff?: number;
  retryCondition?: (error: any) => boolean;
}

export interface CookieOptions {
  expires?: Date | number;
  path?: string;
  domain?: string;
  secure?: boolean;
  sameSite?: 'Strict' | 'Lax' | 'None';
  httpOnly?: boolean;
}

export interface WebAuthnCredentialCreation {
  publicKey: PublicKeyCredentialCreationOptions;
}

export interface WebAuthnCredentialAssertion {
  publicKey: PublicKeyCredentialRequestOptions;
}

export interface PasskeyRegistration {
  id: string;
  name: string;
  created_at: string;
  last_used?: string;
}

export type EventCallback = (event: string, data?: any) => void;

export interface PlintoEventEmitter {
  on(event: string, callback: EventCallback): void;
  off(event: string, callback: EventCallback): void;
  once(event: string, callback: EventCallback): void;
  emit(event: string, data?: any): void;
}

export interface StorageAdapter {
  getItem(key: string): string | null | Promise<string | null>;
  setItem(key: string, value: string): void | Promise<void>;
  removeItem(key: string): void | Promise<void>;
  clear(): void | Promise<void>;
}