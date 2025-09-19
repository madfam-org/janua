"use strict";
/**
 * Plinto TypeScript SDK
 *
 * Official TypeScript/JavaScript SDK for the Plinto authentication API.
 * Provides a complete interface for user authentication, organization management,
 * webhooks, and administrative operations.
 */
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.EnvUtils = exports.ValidationUtils = exports.UrlUtils = exports.DateUtils = exports.TokenManager = exports.MemoryTokenStorage = exports.SessionTokenStorage = exports.LocalTokenStorage = exports.JwtUtils = exports.Base64Url = exports.isPlintoError = exports.isServerError = exports.isNetworkError = exports.isRateLimitError = exports.isNotFoundError = exports.isPermissionError = exports.isValidationError = exports.isAuthenticationError = exports.ErrorHandler = exports.PasskeyError = exports.OAuthError = exports.WebhookError = exports.MFAError = exports.ConfigurationError = exports.TokenError = exports.NetworkError = exports.ServerError = exports.RateLimitError = exports.ConflictError = exports.NotFoundError = exports.ValidationError = exports.PermissionError = exports.AuthenticationError = exports.PlintoError = exports.WebhookEventType = exports.OAuthProvider = exports.OrganizationRole = exports.UserStatus = exports.createHttpClient = exports.AxiosHttpClient = exports.HttpClient = exports.Admin = exports.Webhooks = exports.Organizations = exports.Sessions = exports.Users = exports.Auth = exports.default = exports.createClient = exports.PlintoClient = void 0;
exports.createClientWithPreset = exports.presets = exports.examples = exports.SDK_NAME = exports.SDK_VERSION = exports.EventEmitter = exports.RetryUtils = void 0;
// Main client exports
var client_1 = require("./client");
Object.defineProperty(exports, "PlintoClient", { enumerable: true, get: function () { return client_1.PlintoClient; } });
Object.defineProperty(exports, "createClient", { enumerable: true, get: function () { return client_1.createClient; } });
var client_2 = require("./client");
Object.defineProperty(exports, "default", { enumerable: true, get: function () { return __importDefault(client_2).default; } });
// Import createClient for local use
const client_3 = require("./client");
// Module exports
var auth_1 = require("./auth");
Object.defineProperty(exports, "Auth", { enumerable: true, get: function () { return auth_1.Auth; } });
var users_1 = require("./users");
Object.defineProperty(exports, "Users", { enumerable: true, get: function () { return users_1.Users; } });
var sessions_1 = require("./sessions");
Object.defineProperty(exports, "Sessions", { enumerable: true, get: function () { return sessions_1.Sessions; } });
var organizations_1 = require("./organizations");
Object.defineProperty(exports, "Organizations", { enumerable: true, get: function () { return organizations_1.Organizations; } });
var webhooks_1 = require("./webhooks");
Object.defineProperty(exports, "Webhooks", { enumerable: true, get: function () { return webhooks_1.Webhooks; } });
var admin_1 = require("./admin");
Object.defineProperty(exports, "Admin", { enumerable: true, get: function () { return admin_1.Admin; } });
// HTTP client exports
var http_client_1 = require("./http-client");
Object.defineProperty(exports, "HttpClient", { enumerable: true, get: function () { return http_client_1.HttpClient; } });
Object.defineProperty(exports, "AxiosHttpClient", { enumerable: true, get: function () { return http_client_1.AxiosHttpClient; } });
Object.defineProperty(exports, "createHttpClient", { enumerable: true, get: function () { return http_client_1.createHttpClient; } });
// Export enums as values too
var types_1 = require("./types");
Object.defineProperty(exports, "UserStatus", { enumerable: true, get: function () { return types_1.UserStatus; } });
Object.defineProperty(exports, "OrganizationRole", { enumerable: true, get: function () { return types_1.OrganizationRole; } });
Object.defineProperty(exports, "OAuthProvider", { enumerable: true, get: function () { return types_1.OAuthProvider; } });
Object.defineProperty(exports, "WebhookEventType", { enumerable: true, get: function () { return types_1.WebhookEventType; } });
// Error exports
var errors_1 = require("./errors");
// Base error
Object.defineProperty(exports, "PlintoError", { enumerable: true, get: function () { return errors_1.PlintoError; } });
// Specific errors
Object.defineProperty(exports, "AuthenticationError", { enumerable: true, get: function () { return errors_1.AuthenticationError; } });
Object.defineProperty(exports, "PermissionError", { enumerable: true, get: function () { return errors_1.PermissionError; } });
Object.defineProperty(exports, "ValidationError", { enumerable: true, get: function () { return errors_1.ValidationError; } });
Object.defineProperty(exports, "NotFoundError", { enumerable: true, get: function () { return errors_1.NotFoundError; } });
Object.defineProperty(exports, "ConflictError", { enumerable: true, get: function () { return errors_1.ConflictError; } });
Object.defineProperty(exports, "RateLimitError", { enumerable: true, get: function () { return errors_1.RateLimitError; } });
Object.defineProperty(exports, "ServerError", { enumerable: true, get: function () { return errors_1.ServerError; } });
Object.defineProperty(exports, "NetworkError", { enumerable: true, get: function () { return errors_1.NetworkError; } });
Object.defineProperty(exports, "TokenError", { enumerable: true, get: function () { return errors_1.TokenError; } });
Object.defineProperty(exports, "ConfigurationError", { enumerable: true, get: function () { return errors_1.ConfigurationError; } });
Object.defineProperty(exports, "MFAError", { enumerable: true, get: function () { return errors_1.MFAError; } });
Object.defineProperty(exports, "WebhookError", { enumerable: true, get: function () { return errors_1.WebhookError; } });
Object.defineProperty(exports, "OAuthError", { enumerable: true, get: function () { return errors_1.OAuthError; } });
Object.defineProperty(exports, "PasskeyError", { enumerable: true, get: function () { return errors_1.PasskeyError; } });
// Error utilities
Object.defineProperty(exports, "ErrorHandler", { enumerable: true, get: function () { return errors_1.ErrorHandler; } });
// Type guards
Object.defineProperty(exports, "isAuthenticationError", { enumerable: true, get: function () { return errors_1.isAuthenticationError; } });
Object.defineProperty(exports, "isValidationError", { enumerable: true, get: function () { return errors_1.isValidationError; } });
Object.defineProperty(exports, "isPermissionError", { enumerable: true, get: function () { return errors_1.isPermissionError; } });
Object.defineProperty(exports, "isNotFoundError", { enumerable: true, get: function () { return errors_1.isNotFoundError; } });
Object.defineProperty(exports, "isRateLimitError", { enumerable: true, get: function () { return errors_1.isRateLimitError; } });
Object.defineProperty(exports, "isNetworkError", { enumerable: true, get: function () { return errors_1.isNetworkError; } });
Object.defineProperty(exports, "isServerError", { enumerable: true, get: function () { return errors_1.isServerError; } });
Object.defineProperty(exports, "isPlintoError", { enumerable: true, get: function () { return errors_1.isPlintoError; } });
// Utility exports
var utils_1 = require("./utils");
// Base64 utilities
Object.defineProperty(exports, "Base64Url", { enumerable: true, get: function () { return utils_1.Base64Url; } });
// JWT utilities
Object.defineProperty(exports, "JwtUtils", { enumerable: true, get: function () { return utils_1.JwtUtils; } });
Object.defineProperty(exports, "LocalTokenStorage", { enumerable: true, get: function () { return utils_1.LocalTokenStorage; } });
Object.defineProperty(exports, "SessionTokenStorage", { enumerable: true, get: function () { return utils_1.SessionTokenStorage; } });
Object.defineProperty(exports, "MemoryTokenStorage", { enumerable: true, get: function () { return utils_1.MemoryTokenStorage; } });
Object.defineProperty(exports, "TokenManager", { enumerable: true, get: function () { return utils_1.TokenManager; } });
// Date utilities
Object.defineProperty(exports, "DateUtils", { enumerable: true, get: function () { return utils_1.DateUtils; } });
// URL utilities
Object.defineProperty(exports, "UrlUtils", { enumerable: true, get: function () { return utils_1.UrlUtils; } });
// Validation utilities
Object.defineProperty(exports, "ValidationUtils", { enumerable: true, get: function () { return utils_1.ValidationUtils; } });
// Webhook utilities removed - WebhookUtils not implemented yet
// Environment utilities
Object.defineProperty(exports, "EnvUtils", { enumerable: true, get: function () { return utils_1.EnvUtils; } });
// Retry utilities
Object.defineProperty(exports, "RetryUtils", { enumerable: true, get: function () { return utils_1.RetryUtils; } });
// Event emitter
Object.defineProperty(exports, "EventEmitter", { enumerable: true, get: function () { return utils_1.EventEmitter; } });
// Version and metadata
exports.SDK_VERSION = '1.0.0';
exports.SDK_NAME = 'plinto-typescript-sdk';
/**
 * Quick start examples and common usage patterns
 */
exports.examples = {
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
  url: 'https://myapp.com/webhooks/plinto',
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
import { isValidationError, isAuthenticationError } from '@plinto/typescript-sdk';

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
exports.presets = {
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
        tokenStorage: 'localStorage',
        timeout: 30000,
        autoRefreshTokens: true
    },
    /**
     * Node.js server configuration
     */
    server: {
        tokenStorage: 'memory',
        timeout: 10000,
        autoRefreshTokens: false
    }
};
/**
 * Utility function to create client with preset
 */
function createClientWithPreset(preset, overrides = {}) {
    const presetConfig = exports.presets[preset];
    // Use the already imported createClient function from the top of the file
    return (0, client_3.createClient)({ ...presetConfig, ...overrides });
}
exports.createClientWithPreset = createClientWithPreset;
//# sourceMappingURL=index.js.map