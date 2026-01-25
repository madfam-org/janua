/**
 * Janua React Native SDK - TypeScript Definitions
 * Complete authentication solution for React Native apps
 */

// === Configuration Types ===

export interface JanuaConfig {
  /** Base URL for the Janua API */
  baseURL?: string;
  /** Tenant ID for multi-tenant deployments */
  tenantId: string;
  /** Client ID for OAuth and API access */
  clientId: string;
  /** Redirect URI for OAuth callbacks */
  redirectUri: string;
  /** Custom storage implementation (defaults to AsyncStorage) */
  storage?: Storage;
  /** Custom secure storage implementation (defaults to react-native-keychain) */
  secureStorage?: SecureStorage;
}

export interface Storage {
  getItem(key: string): Promise<string | null>;
  setItem(key: string, value: string): Promise<void>;
  removeItem(key: string): Promise<void>;
}

export interface SecureStorage {
  getInternetCredentials(server: string): Promise<{ username: string; password: string } | false>;
  setInternetCredentials(server: string, username: string, password: string, options?: SecureStorageOptions): Promise<void>;
  resetInternetCredentials(server: string): Promise<void>;
  getSupportedBiometryType(): Promise<BiometryType | null>;
}

export interface SecureStorageOptions {
  accessControl?: string;
  authenticatePrompt?: string;
}

export type BiometryType = 'TouchID' | 'FaceID' | 'Fingerprint' | 'Iris';

// === Core Data Types ===

export interface User {
  id: string;
  email: string;
  first_name?: string;
  last_name?: string;
  email_verified: boolean;
  phone?: string;
  phone_verified?: boolean;
  avatar_url?: string;
  metadata?: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface AuthTokens {
  access_token: string;
  refresh_token: string;
  id_token?: string;
  token_type: string;
  expires_in: number;
}

export interface Session {
  id: string;
  user_id: string;
  device_info: DeviceInfo;
  ip_address: string;
  user_agent: string;
  last_activity: string;
  expires_at: string;
  created_at: string;
}

export interface DeviceInfo {
  type: string;
  browser?: string;
  os: string;
  location?: string;
}

export interface Organization {
  id: string;
  name: string;
  slug: string;
  description?: string;
  logo_url?: string;
  metadata?: Record<string, unknown>;
  settings?: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface OrganizationMember {
  id: string;
  user_id: string;
  organization_id: string;
  role: string;
  user?: User;
  joined_at: string;
}

export interface OrganizationInvite {
  id: string;
  email: string;
  role: string;
  organization_id: string;
  expires_at: string;
  created_at: string;
}

// === OAuth Types ===

export type OAuthProvider =
  | 'google'
  | 'github'
  | 'microsoft'
  | 'apple'
  | 'facebook'
  | 'twitter'
  | 'linkedin'
  | 'discord'
  | 'slack';

// === MFA Types ===

export type MFAMethod = 'totp' | 'sms' | 'email';

export interface MFAChallenge {
  challenge_id: string;
  methods: MFAMethod[];
}

export interface MFASetupResponse {
  secret: string;
  qr_code: string;
  backup_codes: string[];
}

// === WebAuthn/Passkey Types ===

export interface PasskeyCredential {
  id: string;
  raw_id: string;
  type: string;
  response: PasskeyCredentialResponse;
}

export interface PasskeyCredentialResponse {
  client_data_json: string;
  attestation_object?: string;
  authenticator_data?: string;
  signature?: string;
  user_handle?: string | null;
}

export interface PasskeyOptions {
  challenge: string;
  rp: {
    name: string;
    id: string;
  };
  user?: {
    id: string;
    name: string;
    displayName: string;
  };
  pubKeyCredParams?: Array<{
    type: string;
    alg: number;
  }>;
  timeout?: number;
  attestation?: string;
  authenticatorSelection?: {
    authenticatorAttachment?: string;
    residentKey?: string;
    userVerification?: string;
  };
  allowCredentials?: Array<{
    type: string;
    id: string;
    transports?: string[];
  }>;
}

// === Request/Response Types ===

export interface SignUpParams {
  email: string;
  password: string;
  firstName?: string;
  lastName?: string;
  metadata?: Record<string, unknown>;
}

export interface SignInParams {
  email: string;
  password: string;
}

export interface AuthResponse {
  user: User;
  session?: Session;
  tokens: AuthTokens;
  mfa?: MFAChallenge;
}

export interface TokenRefreshResponse {
  tokens: AuthTokens;
}

export interface BiometricEnableResponse {
  biometryType: BiometryType;
}

export interface BiometricSignInResponse {
  success: boolean;
  tokens: AuthTokens;
}

export interface UpdateProfileParams {
  first_name?: string;
  last_name?: string;
  phone?: string;
  metadata?: Record<string, unknown>;
}

export interface CreateOrganizationParams {
  name: string;
  slug?: string;
  description?: string;
  logo_url?: string;
  metadata?: Record<string, unknown>;
  settings?: Record<string, unknown>;
}

export interface UpdateOrganizationParams {
  name?: string;
  description?: string;
  logo_url?: string;
  metadata?: Record<string, unknown>;
  settings?: Record<string, unknown>;
}

// === Error Types ===

export class JanuaError extends Error {
  /** Error code for programmatic handling */
  code: string;
  /** Additional error details */
  details: Record<string, unknown>;

  constructor(message: string, code: string, details?: Record<string, unknown>);
}

// === Service Classes ===

export class AuthService {
  constructor(client: JanuaClient);

  /**
   * Sign up a new user with email and password
   */
  signUp(params: SignUpParams): Promise<AuthResponse>;

  /**
   * Sign in with email and password
   */
  signIn(params: SignInParams): Promise<AuthResponse>;

  /**
   * Sign out the current user
   */
  signOut(): Promise<void>;

  /**
   * Refresh the access token
   */
  refreshToken(): Promise<TokenRefreshResponse>;

  /**
   * Request a password reset email
   */
  requestPasswordReset(email: string): Promise<void>;

  /**
   * Reset password using a token
   */
  resetPassword(token: string, newPassword: string): Promise<void>;

  /**
   * Verify email using a token
   */
  verifyEmail(token: string): Promise<void>;

  /**
   * Enable MFA for the current user
   */
  enableMFA(method?: MFAMethod): Promise<MFASetupResponse>;

  /**
   * Verify MFA code
   */
  verifyMFA(code: string, challengeId: string): Promise<AuthResponse>;

  /**
   * Disable MFA for the current user
   */
  disableMFA(password: string): Promise<void>;

  /**
   * Get OAuth authorization URL for a provider
   */
  signInWithProvider(provider: OAuthProvider): Promise<string>;

  /**
   * Handle OAuth callback with authorization code
   */
  handleOAuthCallback(code: string, state: string): Promise<AuthResponse>;

  /**
   * Start passkey registration
   */
  registerPasskey(): Promise<PasskeyCredential>;

  /**
   * Sign in with a passkey
   */
  signInWithPasskey(): Promise<AuthResponse>;

  /**
   * Enable biometric authentication
   */
  enableBiometric(): Promise<BiometricEnableResponse>;

  /**
   * Sign in with biometric authentication
   */
  signInWithBiometric(): Promise<BiometricSignInResponse>;
}

export class UsersService {
  constructor(client: JanuaClient);

  /**
   * Get the current authenticated user
   */
  getCurrentUser(): Promise<User>;

  /**
   * Update the current user's profile
   */
  updateProfile(updates: UpdateProfileParams): Promise<User>;

  /**
   * Upload an avatar image
   */
  uploadAvatar(imageUri: string): Promise<User>;

  /**
   * Change the current user's password
   */
  changePassword(currentPassword: string, newPassword: string): Promise<void>;

  /**
   * Delete the current user's account
   */
  deleteAccount(password: string): Promise<void>;
}

export class SessionsService {
  constructor(client: JanuaClient);

  /**
   * List all active sessions for the current user
   */
  listSessions(): Promise<Session[]>;

  /**
   * Revoke a specific session
   */
  revokeSession(sessionId: string): Promise<void>;

  /**
   * Revoke all sessions except the current one
   */
  revokeAllSessions(): Promise<void>;

  /**
   * Get the current session
   */
  getCurrentSession(): Promise<Session>;
}

export class OrganizationsService {
  constructor(client: JanuaClient);

  /**
   * List all organizations for the current user
   */
  listOrganizations(): Promise<Organization[]>;

  /**
   * Create a new organization
   */
  createOrganization(data: CreateOrganizationParams): Promise<Organization>;

  /**
   * Get an organization by ID
   */
  getOrganization(orgId: string): Promise<Organization>;

  /**
   * Update an organization
   */
  updateOrganization(orgId: string, updates: UpdateOrganizationParams): Promise<Organization>;

  /**
   * Delete an organization
   */
  deleteOrganization(orgId: string): Promise<void>;

  /**
   * Get members of an organization
   */
  getMembers(orgId: string): Promise<OrganizationMember[]>;

  /**
   * Invite a member to an organization
   */
  inviteMember(orgId: string, email: string, role: string): Promise<OrganizationInvite>;

  /**
   * Remove a member from an organization
   */
  removeMember(orgId: string, userId: string): Promise<void>;

  /**
   * Accept an organization invite
   */
  acceptInvite(inviteToken: string): Promise<OrganizationMember>;
}

// === Main Client Class ===

declare class JanuaClient {
  /** Base URL for API requests */
  readonly baseURL: string;
  /** Tenant ID */
  readonly tenantId: string;
  /** Client ID */
  readonly clientId: string;
  /** Redirect URI for OAuth */
  readonly redirectUri: string;

  /** Authentication service */
  readonly auth: AuthService;
  /** User management service */
  readonly users: UsersService;
  /** Session management service */
  readonly sessions: SessionsService;
  /** Organization management service */
  readonly organizations: OrganizationsService;

  constructor(config: JanuaConfig);

  /**
   * Make an authenticated HTTP request
   */
  request<T = unknown>(
    method: string,
    path: string,
    data?: unknown,
    options?: RequestOptions
  ): Promise<T>;

  /**
   * Get the current access token
   */
  getAccessToken(): Promise<string | null>;

  /**
   * Store authentication tokens
   */
  setTokens(tokens: AuthTokens): Promise<void>;

  /**
   * Clear all stored tokens
   */
  clearTokens(): Promise<void>;
}

export interface RequestOptions {
  headers?: Record<string, string>;
  skipAuth?: boolean;
  params?: Record<string, string>;
}

export default JanuaClient;
export { JanuaClient };
