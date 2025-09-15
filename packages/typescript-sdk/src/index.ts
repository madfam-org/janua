/**
 * Plinto TypeScript SDK
 * 
 * Official TypeScript/JavaScript SDK for the Plinto authentication API.
 * Provides a complete interface for user authentication, organization management,
 * webhooks, and administrative operations.
 */

// Main client exports
export { PlintoClient, createClient } from './client';
export { default } from './client';

// Module exports
export { Auth } from './auth';
export { Users } from './users';
export { Organizations } from './organizations';
export { Webhooks } from './webhooks';
export { Admin } from './admin';

// HTTP client exports
export { HttpClient, AxiosHttpClient, createHttpClient } from './http-client';

// Type exports
export type {
  // Core types
  UUID,
  ISODateString,
  Environment,
  PlintoConfig,
  

  
  // User types
  User,
  UserUpdateRequest,
  UserListParams,
  
  // Session types
  Session,
  SessionListParams,
  
  // Organization types
  Organization,
  OrganizationCreateRequest,
  OrganizationUpdateRequest,
  OrganizationMember,
  OrganizationInvitation,
  OrganizationInviteRequest,
  OrganizationListParams,
  
  // Auth types
  SignUpRequest,
  SignInRequest,
  RefreshTokenRequest,
  ForgotPasswordRequest,
  ResetPasswordRequest,
  ChangePasswordRequest,
  MagicLinkRequest,
  AuthResponse,
  TokenResponse,
  
  // MFA types
  MFAEnableRequest,
  MFAEnableResponse,
  MFAVerifyRequest,
  MFADisableRequest,
  MFAStatusResponse,
  MFABackupCodesResponse,
  
  // OAuth types
  OAuthProvidersResponse,
  LinkedAccountsResponse,
  
  // Passkey types
  Passkey,
  
  // Webhook types
  WebhookEndpoint,
  WebhookEndpointCreateRequest,
  WebhookEndpointUpdateRequest,
  WebhookEvent,
  WebhookDelivery,
  
  // Admin types
  AdminStatsResponse,
  SystemHealthResponse,
  
  // Pagination types
  PaginationParams,
  PaginatedResponse,
  
  // HTTP types
  RequestConfig,
  HttpResponse,
  RateLimitInfo,
  
  // Error types
  ApiError,
  
  // Event types
  SdkEventMap,
  SdkEventType,
  SdkEventHandler,
  
  // Token storage types
  TokenData
} from './types';

// Export enums as values too
export {
  UserStatus,
  OrganizationRole,
  OAuthProvider,
  WebhookEventType
} from './types';

// Error exports
export {
  // Base error
  PlintoError,
  
  // Specific errors
  AuthenticationError,
  PermissionError,
  ValidationError,
  NotFoundError,
  ConflictError,
  RateLimitError,
  ServerError,
  NetworkError,
  TokenError,
  ConfigurationError,
  MFAError,
  WebhookError,
  OAuthError,
  PasskeyError,
  
  // Error utilities
  ErrorHandler,
  
  // Type guards
  isAuthenticationError,
  isValidationError,
  isPermissionError,
  isNotFoundError,
  isRateLimitError,
  isNetworkError,
  isServerError,
  isPlintoError
} from './errors';

// Utility exports
export {
  // Base64 utilities
  Base64Url,
  
  // JWT utilities
  JwtUtils,
  
  // Token storage
  TokenStorage,
  LocalTokenStorage,
  SessionTokenStorage,
  MemoryTokenStorage,
  TokenManager,
  
  // Date utilities
  DateUtils,
  
  // URL utilities
  UrlUtils,
  
  // Validation utilities
  ValidationUtils,
  
  // Webhook utilities removed - WebhookUtils not implemented yet
  
  // Environment utilities
  EnvUtils,
  
  // Retry utilities
  RetryUtils,
  
  // Event emitter
  EventEmitter
} from './utils';

// Version and metadata
export const SDK_VERSION = '1.0.0';
export const SDK_NAME = 'plinto-typescript-sdk';

/**
 * Quick start examples and common usage patterns
 */
export const examples = {
  /**
   * Basic client initialization
   */
  basicClient: `
import { createClient } from '@plinto/typescript-sdk';

const client = createClient({
  baseURL: 'https://api.yourapp.com'
});
`,

  /**
   * Sign up a new user
   */
  signUp: `
const result = await client.auth.signUp({
  email: 'user@example.com',
  password: 'securepassword123',
  first_name: 'John',
  last_name: 'Doe'
});

console.log('User created:', result.user);
console.log('Access token:', result.tokens.access_token);
`,

  /**
   * Sign in existing user
   */
  signIn: `
const result = await client.auth.signIn({
  email: 'user@example.com',
  password: 'securepassword123'
});

console.log('User signed in:', result.user);
`,

  /**
   * Get current user
   */
  getCurrentUser: `
const user = await client.users.getCurrentUser();
console.log('Current user:', user);
`,

  /**
   * Create organization
   */
  createOrganization: `
const org = await client.organizations.createOrganization({
  name: 'My Company',
  slug: 'my-company'
});

console.log('Organization created:', org);
`,

  /**
   * Set up webhook
   */
  createWebhook: `
const webhook = await client.webhooks.createEndpoint({
  url: 'https://myapp.com/webhooks/plinto',
  events: ['user.created', 'user.signed_in'],
  description: 'User events webhook'
});

console.log('Webhook created:', webhook);
`,

  /**
   * Enable MFA
   */
  enableMFA: `
const mfaSetup = await client.auth.enableMFA({
  password: 'userpassword'
});

console.log('QR Code:', mfaSetup.qr_code);
console.log('Backup codes:', mfaSetup.backup_codes);

// After user scans QR code and enters verification code
await client.auth.verifyMFA({ code: '123456' });
`,

  /**
   * Error handling
   */
  errorHandling: `
import { isValidationError, isAuthenticationError } from '@plinto/typescript-sdk';

try {
  await client.auth.signIn({ email: 'invalid', password: 'wrong' });
} catch (error) {
  if (isAuthenticationError(error)) {
    console.log('Authentication failed:', error.message);
  } else if (isValidationError(error)) {
    console.log('Validation errors:', error.violations);
  } else {
    console.log('Other error:', error.message);
  }
}
`,

  /**
   * Event handling
   */
  eventHandling: `
// Listen for authentication events
client.on('auth:signedIn', ({ user }) => {
  console.log('User signed in:', user);
});

client.on('auth:signedOut', () => {
  console.log('User signed out');
});

client.on('token:refreshed', ({ tokens }) => {
  console.log('Tokens refreshed automatically');
});
`
};

/**
 * Common configuration presets
 */
export const presets = {
  /**
   * Development configuration
   */
  development: {
    baseURL: 'http://localhost:8000',
    debug: true,
    timeout: 30000,
    retryAttempts: 1
  },

  /**
   * Production configuration
   */
  production: {
    debug: false,
    timeout: 15000,
    retryAttempts: 3,
    autoRefreshTokens: true
  },

  /**
   * Browser-optimized configuration
   */
  browser: {
    tokenStorage: 'localStorage' as const,
    timeout: 30000,
    autoRefreshTokens: true
  },

  /**
   * Node.js server configuration
   */
  server: {
    tokenStorage: 'memory' as const,
    timeout: 10000,
    autoRefreshTokens: false
  }
};

/**
 * Utility function to create client with preset
 */
export function createClientWithPreset(
  preset: keyof typeof presets,
  overrides: Partial<import('./types').PlintoConfig> = {}
): import('./client').PlintoClient {
  const presetConfig = presets[preset];
  // Use the already imported createClient function from the top of the file
  return createClient({ ...presetConfig, ...overrides });
}