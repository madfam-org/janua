/**
 * Janua TypeScript SDK
 *
 * Official TypeScript/JavaScript SDK for the Janua authentication API.
 * Provides a complete interface for user authentication, organization management,
 * webhooks, and administrative operations.
 */

// Main client exports
export { JanuaClient, createClient } from './client';
export { default } from './client';

// Import createClient for local use
import { createClient } from './client';

// Module exports
export { Auth } from './auth';
export { Users } from './users';
export { Sessions } from './sessions';
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
  JanuaConfig,



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
  TokenData,

  // Additional type exports
  TokenPair
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
  JanuaError,

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
  isJanuaError
} from './errors';

// Utility exports
export {
  // Base64 utilities
  Base64Url,

  // JWT utilities
  JwtUtils,

  // Token storage (classes)
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

// Token storage type export (interface)
export type { TokenStorage } from './utils';

// WebAuthn helper exports
export { WebAuthnHelper, checkWebAuthnSupport } from './webauthn-helper';
export type { WebAuthnSupport } from './webauthn-helper';

// GraphQL exports
export { GraphQL, createGraphQLClient } from './graphql';
export type {
  GraphQLConfig,
  GraphQLQueryOptions,
  GraphQLMutationOptions,
  GraphQLSubscriptionOptions,
} from './graphql';

// WebSocket exports
export { WebSocket, createWebSocketClient } from './websocket';
export type {
  WebSocketConfig,
  WebSocketMessage,
  WebSocketEventMap,
  WebSocketStatus,
} from './websocket';

// Plugin exports
export {
  PolarPlugin,
  createPolarPlugin,
  type PolarPluginConfig,
  type PolarCheckoutOptions,
  type PolarCheckoutSession,
  type PolarSubscription,
  type PolarCustomer,
  type PolarCustomerPortalData,
  type PolarBenefit,
  type PolarOrder,
  type PolarUsageEvent
} from './plugins';

// Version and metadata
export const SDK_VERSION = '1.0.0';
export const SDK_NAME = 'janua-typescript-sdk';

/**
 * Quick start examples and common usage patterns
 */
export const examples = {
  /**
   * Basic client initialization
   */
  basicClient: `
import { createClient } from '@janua/typescript-sdk';

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

// User created: result.user
// Access token: result.tokens.access_token
`,

  /**
   * Sign in existing user
   */
  signIn: `
const result = await client.auth.signIn({
  email: 'user@example.com',
  password: 'securepassword123'
});

// User signed in: result.user
`,

  /**
   * Get current user
   */
  getCurrentUser: `
const user = await client.users.getCurrentUser();
// Current user: user
`,

  /**
   * Create organization
   */
  createOrganization: `
const org = await client.organizations.createOrganization({
  name: 'My Company',
  slug: 'my-company'
});

// Organization created: org
`,

  /**
   * Set up webhook
   */
  createWebhook: `
const webhook = await client.webhooks.createEndpoint({
  url: 'https://myapp.com/webhooks/janua',
  events: ['user.created', 'user.signed_in'],
  description: 'User events webhook'
});

// Webhook created: webhook
`,

  /**
   * Enable MFA
   */
  enableMFA: `
const mfaSetup = await client.auth.enableMFA({
  password: 'userpassword'
});

// QR Code: mfaSetup.qr_code
// Backup codes: mfaSetup.backup_codes

// After user scans QR code and enters verification code
await client.auth.verifyMFA({ code: '123456' });
`,

  /**
   * Error handling
   */
  errorHandling: `
import { isValidationError, isAuthenticationError } from '@janua/typescript-sdk';

try {
  await client.auth.signIn({ email: 'invalid', password: 'wrong' });
} catch (error) {
  if (isAuthenticationError(error)) {
    // Authentication failed: error.message
  } else if (isValidationError(error)) {
    // Validation errors: error.violations
  } else {
    // Other error: error.message
  }
}
`,

  /**
   * Event handling
   */
  eventHandling: `
// Listen for authentication events
client.on('auth:signedIn', ({ user }) => {
  // User signed in: user
});

client.on('auth:signedOut', () => {
  // User signed out
});

client.on('token:refreshed', ({ tokens }) => {
  // Tokens refreshed automatically
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
  overrides: Partial<import('./types').JanuaConfig> = {}
): import('./client').JanuaClient {
  const presetConfig = presets[preset];
  // Use the already imported createClient function from the top of the file
  return createClient({ ...presetConfig, ...overrides });
}
