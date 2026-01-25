/**
 * Error handling utilities for the React SDK
 *
 * Provides React-specific error handling and mapping from
 * API responses to typed error states.
 */

import type { JanuaErrorCode, JanuaErrorState } from '../types';
import {
  JanuaError,
  AuthenticationError,
  isAuthenticationError,
  isValidationError,
  isNetworkError,
  isJanuaError,
} from '@janua/typescript-sdk';

/**
 * Create a JanuaErrorState from an error code and message
 */
export function createErrorState(
  code: JanuaErrorCode,
  message: string,
  status?: number,
  details?: unknown
): JanuaErrorState {
  return {
    code,
    message,
    status,
    details,
  };
}

/**
 * Map an HTTP status code and response detail to a JanuaErrorCode
 */
function mapStatusToErrorCode(status: number, detail?: string): JanuaErrorCode {
  switch (status) {
    case 401:
      if (detail?.toLowerCase().includes('invalid credentials')) {
        return 'INVALID_CREDENTIALS';
      }
      if (detail?.toLowerCase().includes('expired')) {
        return 'TOKEN_EXPIRED';
      }
      if (detail?.toLowerCase().includes('invalid token')) {
        return 'TOKEN_INVALID';
      }
      return 'UNAUTHORIZED';

    case 403:
      if (detail?.toLowerCase().includes('email not verified')) {
        return 'EMAIL_NOT_VERIFIED';
      }
      if (detail?.toLowerCase().includes('mfa required')) {
        return 'MFA_REQUIRED';
      }
      return 'UNAUTHORIZED';

    case 423:
      return 'ACCOUNT_SUSPENDED';

    default:
      return 'UNKNOWN_ERROR';
  }
}

/**
 * Map an unknown error to a JanuaErrorState
 *
 * Handles various error types from axios, JanuaError, and native errors
 */
export function mapErrorToState(error: unknown): JanuaErrorState {
  // Handle JanuaError types
  if (isAuthenticationError(error)) {
    const authError = error as AuthenticationError;
    const detail = authError.message || '';

    if (detail.toLowerCase().includes('invalid credentials')) {
      return createErrorState('INVALID_CREDENTIALS', 'Invalid email or password', 401);
    }
    if (detail.toLowerCase().includes('expired')) {
      return createErrorState('TOKEN_EXPIRED', 'Your session has expired', 401);
    }
    if (detail.toLowerCase().includes('invalid token')) {
      return createErrorState('TOKEN_INVALID', 'Invalid authentication token', 401);
    }

    return createErrorState('UNAUTHORIZED', authError.message, authError.statusCode);
  }

  if (isValidationError(error)) {
    return createErrorState(
      'INVALID_CREDENTIALS',
      (error as JanuaError).message,
      (error as JanuaError).statusCode,
      (error as JanuaError).details
    );
  }

  if (isNetworkError(error)) {
    return createErrorState('NETWORK_ERROR', 'Network request failed. Please check your connection.');
  }

  if (isJanuaError(error)) {
    const januaError = error as JanuaError;
    const code = mapStatusToErrorCode(januaError.statusCode || 0, januaError.message);
    return createErrorState(code, januaError.message, januaError.statusCode, januaError.details);
  }

  // Handle axios-like error responses
  if (error && typeof error === 'object' && 'response' in error) {
    const axiosError = error as {
      response?: {
        status?: number;
        data?: { detail?: string; message?: string; error?: string };
      };
      message?: string;
    };

    if (axiosError.response) {
      const status = axiosError.response.status || 0;
      const detail =
        axiosError.response.data?.detail ||
        axiosError.response.data?.message ||
        axiosError.response.data?.error ||
        axiosError.message ||
        'Unknown error';

      const code = mapStatusToErrorCode(status, detail);
      return createErrorState(code, detail, status, axiosError.response.data);
    }

    // Network error (no response)
    return createErrorState('NETWORK_ERROR', 'Network request failed. Please check your connection.');
  }

  // Handle native Error
  if (error instanceof Error) {
    if (error.message.toLowerCase().includes('network')) {
      return createErrorState('NETWORK_ERROR', error.message);
    }
    return createErrorState('UNKNOWN_ERROR', error.message);
  }

  // Unknown error type
  return createErrorState('UNKNOWN_ERROR', 'An unexpected error occurred');
}

/**
 * Check if an error indicates the user should re-authenticate
 */
export function isAuthRequiredError(error: JanuaErrorState | null): boolean {
  if (!error) return false;

  return (
    error.code === 'TOKEN_EXPIRED' ||
    error.code === 'TOKEN_INVALID' ||
    error.code === 'UNAUTHORIZED' ||
    error.code === 'REFRESH_FAILED'
  );
}

/**
 * Check if an error is a network/connectivity issue
 */
export function isNetworkIssue(error: JanuaErrorState | null): boolean {
  if (!error) return false;
  return error.code === 'NETWORK_ERROR';
}

/**
 * Get a user-friendly error message for display
 */
export function getUserFriendlyMessage(error: JanuaErrorState | null): string {
  if (!error) return '';

  switch (error.code) {
    case 'INVALID_CREDENTIALS':
      return 'Invalid email or password. Please try again.';
    case 'TOKEN_EXPIRED':
      return 'Your session has expired. Please sign in again.';
    case 'TOKEN_INVALID':
      return 'Invalid authentication. Please sign in again.';
    case 'REFRESH_FAILED':
      return 'Session refresh failed. Please sign in again.';
    case 'NETWORK_ERROR':
      return 'Network error. Please check your connection and try again.';
    case 'MFA_REQUIRED':
      return 'Multi-factor authentication is required.';
    case 'EMAIL_NOT_VERIFIED':
      return 'Please verify your email address to continue.';
    case 'ACCOUNT_SUSPENDED':
      return 'Your account has been suspended. Please contact support.';
    case 'OAUTH_ERROR':
      return 'Authentication with the provider failed. Please try again.';
    case 'PKCE_ERROR':
      return 'Security verification failed. Please try again.';
    case 'UNAUTHORIZED':
      return 'You are not authorized to perform this action.';
    case 'UNKNOWN_ERROR':
    default:
      return error.message || 'An unexpected error occurred. Please try again.';
  }
}

/**
 * Create a ReactJanuaError class for throwing in React context
 */
export class ReactJanuaError extends Error {
  code: JanuaErrorCode;
  status?: number;
  details?: unknown;

  constructor(code: JanuaErrorCode, message: string, status?: number, details?: unknown) {
    super(message);
    this.name = 'ReactJanuaError';
    this.code = code;
    this.status = status;
    this.details = details;

    if (Error.captureStackTrace) {
      Error.captureStackTrace(this, ReactJanuaError);
    }
  }

  toState(): JanuaErrorState {
    return {
      code: this.code,
      message: this.message,
      status: this.status,
      details: this.details,
    };
  }

  static fromState(state: JanuaErrorState): ReactJanuaError {
    return new ReactJanuaError(state.code, state.message, state.status, state.details);
  }
}
