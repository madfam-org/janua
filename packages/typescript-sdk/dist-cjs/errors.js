"use strict";
/**
 * Error classes for the Plinto TypeScript SDK
 */
Object.defineProperty(exports, "__esModule", { value: true });
exports.isPlintoError = exports.isServerError = exports.isNetworkError = exports.isRateLimitError = exports.isNotFoundError = exports.isPermissionError = exports.isValidationError = exports.isAuthenticationError = exports.ErrorHandler = exports.PasskeyError = exports.OAuthError = exports.WebhookError = exports.MFAError = exports.ConfigurationError = exports.TokenError = exports.NetworkError = exports.ServerError = exports.RateLimitError = exports.ConflictError = exports.NotFoundError = exports.ValidationError = exports.PermissionError = exports.AuthenticationError = exports.PlintoError = void 0;
/**
 * Base error class for all Plinto SDK errors
 */
class PlintoError extends Error {
    constructor(message, code = 'PLINTO_ERROR', statusCode, details) {
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
    toJSON() {
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
    static fromApiError(apiError) {
        const { error, message, details, status_code } = apiError;
        // Map common HTTP status codes to specific error classes
        switch (status_code) {
            case 400:
                return new ValidationError(message, undefined, details);
            case 401:
                return new AuthenticationError(message, undefined, undefined, details);
            case 403:
                return new PermissionError(message, details);
            case 404:
                return new NotFoundError(message, details);
            case 409:
                return new ConflictError(message, details);
            case 429:
                return new RateLimitError(message, undefined, details);
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
exports.PlintoError = PlintoError;
/**
 * Authentication related errors (401)
 */
class AuthenticationError extends PlintoError {
    constructor(message = 'Authentication failed', code, statusCode, details) {
        super(message, code || 'AUTHENTICATION_ERROR', statusCode || 401, details);
        this.name = 'AuthenticationError';
    }
}
exports.AuthenticationError = AuthenticationError;
/**
 * Permission/authorization related errors (403)
 */
class PermissionError extends PlintoError {
    constructor(message = 'Permission denied', details) {
        super(message, 'PERMISSION_ERROR', 403, details);
        this.name = 'PermissionError';
    }
}
exports.PermissionError = PermissionError;
/**
 * Validation related errors (400)
 */
class ValidationError extends PlintoError {
    constructor(message = 'Validation failed', violations, details) {
        super(message, 'VALIDATION_ERROR', 400, details);
        this.name = 'ValidationError';
        this.violations = violations || [];
        // Extract field-specific validation errors if available
        if (details?.field) {
            this.field = details.field;
        }
    }
}
exports.ValidationError = ValidationError;
/**
 * Resource not found errors (404)
 */
class NotFoundError extends PlintoError {
    constructor(message = 'Resource not found', details) {
        super(message, 'NOT_FOUND', 404, details);
        this.name = 'NotFoundError';
        if (details?.resource) {
            this.resource = details.resource;
        }
    }
}
exports.NotFoundError = NotFoundError;
/**
 * Conflict errors (409)
 */
class ConflictError extends PlintoError {
    constructor(message = 'Resource conflict', details) {
        super(message, 'CONFLICT', 409, details);
        this.name = 'ConflictError';
    }
}
exports.ConflictError = ConflictError;
/**
 * Rate limiting errors (429)
 */
class RateLimitError extends PlintoError {
    constructor(message = 'Rate limit exceeded', rateLimitInfo, details) {
        super(message, 'RATE_LIMIT_EXCEEDED', 429, details);
        this.name = 'RateLimitError';
        this.rateLimitInfo = rateLimitInfo;
        if (rateLimitInfo?.retry_after) {
            this.retryAfter = rateLimitInfo.retry_after;
        }
    }
}
exports.RateLimitError = RateLimitError;
/**
 * Server errors (5xx)
 */
class ServerError extends PlintoError {
    constructor(message = 'Internal server error', statusCode = 500, details) {
        super(message, 'SERVER_ERROR', statusCode, details);
        this.name = 'ServerError';
    }
}
exports.ServerError = ServerError;
/**
 * Network related errors
 */
class NetworkError extends PlintoError {
    constructor(message = 'Network error', cause, details) {
        super(message, 'NETWORK_ERROR', undefined, details);
        this.name = 'NetworkError';
        this.cause = cause;
    }
}
exports.NetworkError = NetworkError;
/**
 * Token related errors
 */
class TokenError extends PlintoError {
    constructor(message = 'Token error', details) {
        super(message, 'TOKEN_ERROR', undefined, details);
        this.name = 'TokenError';
    }
}
exports.TokenError = TokenError;
/**
 * Configuration errors
 */
class ConfigurationError extends PlintoError {
    constructor(message = 'Configuration error', details) {
        super(message, 'CONFIGURATION_ERROR', undefined, details);
        this.name = 'ConfigurationError';
    }
}
exports.ConfigurationError = ConfigurationError;
/**
 * MFA related errors
 */
class MFAError extends PlintoError {
    constructor(message = 'MFA error', mfaRequired = false, availableMethods, details) {
        super(message, 'MFA_ERROR', undefined, details);
        this.name = 'MFAError';
        this.mfaRequired = mfaRequired;
        this.availableMethods = availableMethods;
    }
}
exports.MFAError = MFAError;
/**
 * Webhook related errors
 */
class WebhookError extends PlintoError {
    constructor(message = 'Webhook error', details) {
        super(message, 'WEBHOOK_ERROR', undefined, details);
        this.name = 'WebhookError';
    }
}
exports.WebhookError = WebhookError;
/**
 * OAuth related errors
 */
class OAuthError extends PlintoError {
    constructor(message = 'OAuth error', provider, oauthCode, details) {
        super(message, 'OAUTH_ERROR', undefined, details);
        this.name = 'OAuthError';
        this.provider = provider;
        this.oauthCode = oauthCode;
    }
}
exports.OAuthError = OAuthError;
/**
 * WebAuthn/Passkey related errors
 */
class PasskeyError extends PlintoError {
    constructor(message = 'Passkey error', webauthnError, details) {
        super(message, 'PASSKEY_ERROR', undefined, details);
        this.name = 'PasskeyError';
        this.webauthnError = webauthnError;
    }
}
exports.PasskeyError = PasskeyError;
/**
 * Error handler utility functions
 */
class ErrorHandler {
    constructor(logger) {
        this.logger = logger;
    }
    /**
     * Handle errors and log appropriately
     */
    handleError(error) {
        if (!this.logger)
            return;
        if (error instanceof AuthenticationError) {
            this.logger.error('Authentication error:', error);
        }
        else if (error instanceof ValidationError) {
            this.logger.error('Validation error:', error);
        }
        else if (error instanceof PermissionError) {
            this.logger.error('Permission error:', error);
        }
        else if (error instanceof NotFoundError) {
            this.logger.error('Not found error:', error);
        }
        else if (error instanceof RateLimitError) {
            this.logger.error('Rate limit error:', error);
        }
        else if (error instanceof ServerError) {
            this.logger.error('Server error:', error);
        }
        else if (error instanceof NetworkError) {
            this.logger.error('Network error:', error);
        }
        else if (error instanceof PlintoError) {
            this.logger.error('Plinto error:', error);
        }
        else {
            this.logger.error('Unknown error:', error);
        }
    }
    /**
     * Check if error is a specific type
     */
    static isType(error, errorClass) {
        return error instanceof errorClass;
    }
    /**
     * Check if error is retryable
     */
    static isRetryable(error) {
        if (error instanceof NetworkError)
            return true;
        if (error instanceof ServerError && error.statusCode && error.statusCode >= 500)
            return true;
        if (error instanceof RateLimitError)
            return true;
        return false;
    }
    /**
     * Get retry delay for retryable errors
     */
    static getRetryDelay(error, attempt, baseDelay = 1000) {
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
    static getUserMessage(error) {
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
exports.ErrorHandler = ErrorHandler;
/**
 * Type guards for error checking
 */
const isAuthenticationError = (error) => ErrorHandler.isType(error, AuthenticationError);
exports.isAuthenticationError = isAuthenticationError;
const isValidationError = (error) => ErrorHandler.isType(error, ValidationError);
exports.isValidationError = isValidationError;
const isPermissionError = (error) => ErrorHandler.isType(error, PermissionError);
exports.isPermissionError = isPermissionError;
const isNotFoundError = (error) => ErrorHandler.isType(error, NotFoundError);
exports.isNotFoundError = isNotFoundError;
const isRateLimitError = (error) => ErrorHandler.isType(error, RateLimitError);
exports.isRateLimitError = isRateLimitError;
const isNetworkError = (error) => ErrorHandler.isType(error, NetworkError);
exports.isNetworkError = isNetworkError;
const isServerError = (error) => ErrorHandler.isType(error, ServerError);
exports.isServerError = isServerError;
const isPlintoError = (error) => ErrorHandler.isType(error, PlintoError);
exports.isPlintoError = isPlintoError;
//# sourceMappingURL=errors.js.map