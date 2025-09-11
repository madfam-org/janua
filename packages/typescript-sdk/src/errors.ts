/**
 * Error classes for the Plinto TypeScript SDK
 */

import type { ApiError, RateLimitInfo } from './types';

/**
 * Base error class for all Plinto SDK errors
 */
export class PlintoError extends Error {
  public readonly code: string;
  public readonly statusCode?: number;
  public readonly details?: Record<string, any>;

  constructor(
    message: string,
    code = 'PLINTO_ERROR',
    statusCode?: number,
    details?: Record<string, any>
  ) {
    super(message);
    this.name = 'PlintoError';
    this.code = code;
    this.statusCode = statusCode;
    this.details = details;

    // Maintains proper stack trace for where our error was thrown (only available on V8)
    if (Error.captureStackTrace) {
      Error.captureStackTrace(this, PlintoError);
    }
  }

  /**
   * Convert error to JSON representation
   */
  toJSON(): Record<string, any> {
    return {
      name: this.name,
      message: this.message,
      code: this.code,
      statusCode: this.statusCode,
      details: this.details,
      stack: this.stack
    };
  }

  /**
   * Create PlintoError from API error response
   */
  static fromApiError(apiError: ApiError): PlintoError {
    const { error, message, details, status_code } = apiError;
    
    // Map common HTTP status codes to specific error classes
    switch (status_code) {
      case 400:
        return new ValidationError(message, details);
      case 401:
        return new AuthenticationError(message, details);
      case 403:
        return new PermissionError(message, details);
      case 404:
        return new NotFoundError(message, details);
      case 409:
        return new ConflictError(message, details);
      case 429:
        return new RateLimitError(message, details);
      case 500:
      case 502:
      case 503:
      case 504:
        return new ServerError(message, status_code, details);
      default:
        return new PlintoError(message, error, status_code, details);
    }
  }
}

/**
 * Authentication related errors (401)
 */
export class AuthenticationError extends PlintoError {
  constructor(message = 'Authentication failed', details?: Record<string, any>) {
    super(message, 'AUTHENTICATION_ERROR', 401, details);
    this.name = 'AuthenticationError';
  }
}

/**
 * Permission/authorization related errors (403)
 */
export class PermissionError extends PlintoError {
  constructor(message = 'Permission denied', details?: Record<string, any>) {
    super(message, 'PERMISSION_ERROR', 403, details);
    this.name = 'PermissionError';
  }
}

/**
 * Validation related errors (400)
 */
export class ValidationError extends PlintoError {
  public readonly field?: string;
  public readonly violations?: Record<string, string[]>;

  constructor(message = 'Validation failed', details?: Record<string, any>) {
    super(message, 'VALIDATION_ERROR', 400, details);
    this.name = 'ValidationError';
    
    // Extract field-specific validation errors if available
    if (details?.field) {
      this.field = details.field;
    }
    if (details?.violations) {
      this.violations = details.violations;
    }
  }
}

/**
 * Resource not found errors (404)
 */
export class NotFoundError extends PlintoError {
  public readonly resource?: string;

  constructor(message = 'Resource not found', details?: Record<string, any>) {
    super(message, 'NOT_FOUND_ERROR', 404, details);
    this.name = 'NotFoundError';
    
    if (details?.resource) {
      this.resource = details.resource;
    }
  }
}

/**
 * Conflict errors (409)
 */
export class ConflictError extends PlintoError {
  constructor(message = 'Resource conflict', details?: Record<string, any>) {
    super(message, 'CONFLICT_ERROR', 409, details);
    this.name = 'ConflictError';
  }
}

/**
 * Rate limiting errors (429)
 */
export class RateLimitError extends PlintoError {
  public readonly rateLimitInfo?: RateLimitInfo;
  public readonly retryAfter?: number;

  constructor(message = 'Rate limit exceeded', details?: Record<string, any>) {
    super(message, 'RATE_LIMIT_ERROR', 429, details);
    this.name = 'RateLimitError';
    
    if (details?.rateLimitInfo) {
      this.rateLimitInfo = details.rateLimitInfo;
    }
    if (details?.retry_after) {
      this.retryAfter = details.retry_after;
    }
  }
}

/**
 * Server errors (5xx)
 */
export class ServerError extends PlintoError {
  constructor(
    message = 'Internal server error',
    statusCode = 500,
    details?: Record<string, any>
  ) {
    super(message, 'SERVER_ERROR', statusCode, details);
    this.name = 'ServerError';
  }
}

/**
 * Network related errors
 */
export class NetworkError extends PlintoError {
  public readonly originalError?: Error;

  constructor(message = 'Network error', originalError?: Error) {
    super(message, 'NETWORK_ERROR');
    this.name = 'NetworkError';
    this.originalError = originalError;
  }
}

/**
 * Token related errors
 */
export class TokenError extends PlintoError {
  constructor(message = 'Token error', details?: Record<string, any>) {
    super(message, 'TOKEN_ERROR', undefined, details);
    this.name = 'TokenError';
  }
}

/**
 * Configuration errors
 */
export class ConfigurationError extends PlintoError {
  constructor(message = 'Configuration error', details?: Record<string, any>) {
    super(message, 'CONFIGURATION_ERROR', undefined, details);
    this.name = 'ConfigurationError';
  }
}

/**
 * MFA related errors
 */
export class MFAError extends PlintoError {
  public readonly mfaRequired?: boolean;
  public readonly availableMethods?: string[];

  constructor(
    message = 'MFA error',
    mfaRequired = false,
    availableMethods?: string[],
    details?: Record<string, any>
  ) {
    super(message, 'MFA_ERROR', undefined, details);
    this.name = 'MFAError';
    this.mfaRequired = mfaRequired;
    this.availableMethods = availableMethods;
  }
}

/**
 * Webhook related errors
 */
export class WebhookError extends PlintoError {
  constructor(message = 'Webhook error', details?: Record<string, any>) {
    super(message, 'WEBHOOK_ERROR', undefined, details);
    this.name = 'WebhookError';
  }
}

/**
 * OAuth related errors
 */
export class OAuthError extends PlintoError {
  public readonly provider?: string;
  public readonly oauthCode?: string;

  constructor(
    message = 'OAuth error',
    provider?: string,
    oauthCode?: string,
    details?: Record<string, any>
  ) {
    super(message, 'OAUTH_ERROR', undefined, details);
    this.name = 'OAuthError';
    this.provider = provider;
    this.oauthCode = oauthCode;
  }
}

/**
 * WebAuthn/Passkey related errors
 */
export class PasskeyError extends PlintoError {
  public readonly webauthnError?: string;

  constructor(message = 'Passkey error', webauthnError?: string, details?: Record<string, any>) {
    super(message, 'PASSKEY_ERROR', undefined, details);
    this.name = 'PasskeyError';
    this.webauthnError = webauthnError;
  }
}

/**
 * Error handler utility functions
 */
export class ErrorHandler {
  /**
   * Check if error is a specific type
   */
  static isType<T extends PlintoError>(error: any, errorClass: new (...args: any[]) => T): error is T {
    return error instanceof errorClass;
  }

  /**
   * Check if error is retryable
   */
  static isRetryable(error: any): boolean {
    if (error instanceof NetworkError) return true;
    if (error instanceof ServerError && error.statusCode && error.statusCode >= 500) return true;
    if (error instanceof RateLimitError) return true;
    return false;
  }

  /**
   * Get retry delay for retryable errors
   */
  static getRetryDelay(error: any, attempt: number, baseDelay = 1000): number {
    if (error instanceof RateLimitError && error.retryAfter) {
      return error.retryAfter * 1000; // Convert to milliseconds
    }
    
    // Exponential backoff with jitter
    const delay = baseDelay * Math.pow(2, attempt);
    const jitter = Math.random() * 0.1 * delay;
    return delay + jitter;
  }

  /**
   * Extract user-friendly message from error
   */
  static getUserMessage(error: any): string {
    if (error instanceof ValidationError) {
      return error.message;
    }
    if (error instanceof AuthenticationError) {
      return 'Please check your credentials and try again.';
    }
    if (error instanceof PermissionError) {
      return 'You do not have permission to perform this action.';
    }
    if (error instanceof NotFoundError) {
      return 'The requested resource was not found.';
    }
    if (error instanceof RateLimitError) {
      return 'Too many requests. Please try again later.';
    }
    if (error instanceof NetworkError) {
      return 'Network error. Please check your connection and try again.';
    }
    if (error instanceof ServerError) {
      return 'A server error occurred. Please try again later.';
    }
    if (error instanceof PlintoError) {
      return error.message;
    }
    
    return 'An unexpected error occurred. Please try again.';
  }
}

/**
 * Type guards for error checking
 */
export const isAuthenticationError = (error: any): error is AuthenticationError =>
  ErrorHandler.isType(error, AuthenticationError);

export const isValidationError = (error: any): error is ValidationError =>
  ErrorHandler.isType(error, ValidationError);

export const isPermissionError = (error: any): error is PermissionError =>
  ErrorHandler.isType(error, PermissionError);

export const isNotFoundError = (error: any): error is NotFoundError =>
  ErrorHandler.isType(error, NotFoundError);

export const isRateLimitError = (error: any): error is RateLimitError =>
  ErrorHandler.isType(error, RateLimitError);

export const isNetworkError = (error: any): error is NetworkError =>
  ErrorHandler.isType(error, NetworkError);

export const isServerError = (error: any): error is ServerError =>
  ErrorHandler.isType(error, ServerError);

export const isPlintoError = (error: any): error is PlintoError =>
  ErrorHandler.isType(error, PlintoError);