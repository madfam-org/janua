/**
 * Tests for error classes
 */

import {
  PlintoError,
  AuthenticationError,
  ValidationError,
  PermissionError,
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
  ErrorHandler,
  isAuthenticationError,
  isValidationError,
  isPermissionError,
  isNotFoundError,
  isRateLimitError,
  isNetworkError,
  isServerError,
  isPlintoError
} from '../errors';

describe('Error Classes', () => {
  describe('PlintoError', () => {
    it('should create base error with message', () => {
      const error = new PlintoError('Test error');
      
      expect(error.name).toBe('PlintoError');
      expect(error.message).toBe('Test error');
      expect(error.code).toBe('PLINTO_ERROR');
      expect(error.statusCode).toBeUndefined();
      expect(error.details).toBeUndefined();
    });

    it('should create error with all parameters', () => {
      const details = { field: 'value' };
      const error = new PlintoError('Test error', 'CUSTOM_CODE', 400, details);
      
      expect(error.name).toBe('PlintoError');
      expect(error.message).toBe('Test error');
      expect(error.code).toBe('CUSTOM_CODE');
      expect(error.statusCode).toBe(400);
      expect(error.details).toBe(details);
    });

    it('should convert to JSON correctly', () => {
      const details = { field: 'value' };
      const error = new PlintoError('Test error', 'CUSTOM_CODE', 400, details);
      const json = error.toJSON();
      
      expect(json.name).toBe('PlintoError');
      expect(json.message).toBe('Test error');
      expect(json.code).toBe('CUSTOM_CODE');
      expect(json.statusCode).toBe(400);
      expect(json.details).toBe(details);
      expect(json.stack).toBeDefined();
    });

    it('should create from API error response', () => {
      const apiError = {
        error: 'validation_failed',
        message: 'Validation failed',
        details: { email: 'Invalid email format' },
        status_code: 400
      };
      
      const error = PlintoError.fromApiError(apiError);
      
      // Since status_code is 400, it should return ValidationError
      expect(error).toBeInstanceOf(ValidationError);
      expect(error.name).toBe('ValidationError');
      expect(error.message).toBe('Validation failed');
      expect(error.code).toBe('VALIDATION_ERROR');
      expect(error.statusCode).toBe(400);
      expect(error.details).toEqual({ email: 'Invalid email format' });
    });

    it('should maintain proper stack trace', () => {
      const error = new PlintoError('Test error');
      expect(error.stack).toBeDefined();
      expect(error.stack).toContain('PlintoError');
    });
  });

  describe('AuthenticationError', () => {
    it('should create authentication error', () => {
      const error = new AuthenticationError('Invalid credentials');
      
      expect(error).toBeInstanceOf(PlintoError);
      expect(error).toBeInstanceOf(AuthenticationError);
      expect(error.name).toBe('AuthenticationError');
      expect(error.message).toBe('Invalid credentials');
      expect(error.code).toBe('AUTHENTICATION_ERROR');
    });

    it('should create with custom code and status', () => {
      const error = new AuthenticationError('Token expired', 'TOKEN_EXPIRED', 401);
      
      expect(error.code).toBe('TOKEN_EXPIRED');
      expect(error.statusCode).toBe(401);
    });
  });

  describe('ValidationError', () => {
    it('should create validation error with violations', () => {
      const violations = [
        { field: 'email', message: 'Invalid email' },
        { field: 'password', message: 'Too short' }
      ];
      const error = new ValidationError('Validation failed', violations);
      
      expect(error).toBeInstanceOf(PlintoError);
      expect(error.name).toBe('ValidationError');
      expect(error.message).toBe('Validation failed');
      expect(error.code).toBe('VALIDATION_ERROR');
      expect(error.violations).toEqual(violations);
    });

    it('should create without violations', () => {
      const error = new ValidationError('Invalid input');
      
      expect(error.violations).toEqual([]);
    });
  });

  describe('PermissionError', () => {
    it('should create permission error', () => {
      const error = new PermissionError('Access denied');
      
      expect(error).toBeInstanceOf(PlintoError);
      expect(error.name).toBe('PermissionError');
      expect(error.code).toBe('PERMISSION_ERROR');
      expect(error.statusCode).toBe(403);
    });
  });

  describe('NotFoundError', () => {
    it('should create not found error', () => {
      const error = new NotFoundError('Resource not found');
      
      expect(error).toBeInstanceOf(PlintoError);
      expect(error.name).toBe('NotFoundError');
      expect(error.code).toBe('NOT_FOUND');
      expect(error.statusCode).toBe(404);
    });
  });

  describe('ConflictError', () => {
    it('should create conflict error', () => {
      const error = new ConflictError('Email already exists');
      
      expect(error).toBeInstanceOf(PlintoError);
      expect(error.name).toBe('ConflictError');
      expect(error.code).toBe('CONFLICT');
      expect(error.statusCode).toBe(409);
    });
  });

  describe('RateLimitError', () => {
    it('should create rate limit error with retry info', () => {
      const rateLimitInfo = {
        limit: 100,
        remaining: 0,
        reset: Date.now() + 3600000,
        retry_after: 3600
      };
      const error = new RateLimitError('Rate limit exceeded', rateLimitInfo);
      
      expect(error).toBeInstanceOf(PlintoError);
      expect(error.name).toBe('RateLimitError');
      expect(error.code).toBe('RATE_LIMIT_EXCEEDED');
      expect(error.statusCode).toBe(429);
      expect(error.rateLimitInfo).toEqual(rateLimitInfo);
    });

    it('should create without rate limit info', () => {
      const error = new RateLimitError('Too many requests');
      
      expect(error.rateLimitInfo).toBeUndefined();
    });
  });

  describe('ServerError', () => {
    it('should create server error', () => {
      const error = new ServerError('Internal server error');
      
      expect(error).toBeInstanceOf(PlintoError);
      expect(error.name).toBe('ServerError');
      expect(error.code).toBe('SERVER_ERROR');
      expect(error.statusCode).toBe(500);
    });
  });

  describe('NetworkError', () => {
    it('should create network error', () => {
      const error = new NetworkError('Connection timeout');
      
      expect(error).toBeInstanceOf(PlintoError);
      expect(error.name).toBe('NetworkError');
      expect(error.code).toBe('NETWORK_ERROR');
    });

    it('should create with underlying error', () => {
      const cause = new Error('Connection failed');
      const error = new NetworkError('Network failure', cause);
      
      expect(error.cause).toBe(cause);
    });
  });

  describe('TokenError', () => {
    it('should create token error', () => {
      const error = new TokenError('Invalid token format');
      
      expect(error).toBeInstanceOf(PlintoError);
      expect(error.name).toBe('TokenError');
      expect(error.code).toBe('TOKEN_ERROR');
    });
  });

  describe('ConfigurationError', () => {
    it('should create configuration error', () => {
      const error = new ConfigurationError('Missing API key');
      
      expect(error).toBeInstanceOf(PlintoError);
      expect(error.name).toBe('ConfigurationError');
      expect(error.code).toBe('CONFIGURATION_ERROR');
    });
  });

  describe('MFAError', () => {
    it('should create MFA error', () => {
      const error = new MFAError('Invalid MFA code');
      
      expect(error).toBeInstanceOf(PlintoError);
      expect(error.name).toBe('MFAError');
      expect(error.code).toBe('MFA_ERROR');
    });
  });

  describe('WebhookError', () => {
    it('should create webhook error', () => {
      const error = new WebhookError('Webhook delivery failed');
      
      expect(error).toBeInstanceOf(PlintoError);
      expect(error.name).toBe('WebhookError');
      expect(error.code).toBe('WEBHOOK_ERROR');
    });
  });

  describe('OAuthError', () => {
    it('should create OAuth error', () => {
      const error = new OAuthError('OAuth provider error');
      
      expect(error).toBeInstanceOf(PlintoError);
      expect(error.name).toBe('OAuthError');
      expect(error.code).toBe('OAUTH_ERROR');
    });
  });

  describe('PasskeyError', () => {
    it('should create passkey error', () => {
      const error = new PasskeyError('Passkey registration failed');
      
      expect(error).toBeInstanceOf(PlintoError);
      expect(error.name).toBe('PasskeyError');
      expect(error.code).toBe('PASSKEY_ERROR');
    });
  });
});

describe('Error Type Guards', () => {
  describe('isPlintoError', () => {
    it('should identify PlintoError instances', () => {
      const plintoError = new PlintoError('Test');
      const authError = new AuthenticationError('Test');
      const regularError = new Error('Test');
      
      expect(isPlintoError(plintoError)).toBe(true);
      expect(isPlintoError(authError)).toBe(true);
      expect(isPlintoError(regularError)).toBe(false);
      expect(isPlintoError(null)).toBe(false);
      expect(isPlintoError(undefined)).toBe(false);
    });
  });

  describe('isAuthenticationError', () => {
    it('should identify AuthenticationError instances', () => {
      const authError = new AuthenticationError('Test');
      const validationError = new ValidationError('Test');
      const regularError = new Error('Test');
      
      expect(isAuthenticationError(authError)).toBe(true);
      expect(isAuthenticationError(validationError)).toBe(false);
      expect(isAuthenticationError(regularError)).toBe(false);
    });
  });

  describe('isValidationError', () => {
    it('should identify ValidationError instances', () => {
      const validationError = new ValidationError('Test');
      const authError = new AuthenticationError('Test');
      
      expect(isValidationError(validationError)).toBe(true);
      expect(isValidationError(authError)).toBe(false);
    });
  });

  describe('isPermissionError', () => {
    it('should identify PermissionError instances', () => {
      const permissionError = new PermissionError('Test');
      const authError = new AuthenticationError('Test');
      
      expect(isPermissionError(permissionError)).toBe(true);
      expect(isPermissionError(authError)).toBe(false);
    });
  });

  describe('isNotFoundError', () => {
    it('should identify NotFoundError instances', () => {
      const notFoundError = new NotFoundError('Test');
      const authError = new AuthenticationError('Test');
      
      expect(isNotFoundError(notFoundError)).toBe(true);
      expect(isNotFoundError(authError)).toBe(false);
    });
  });

  describe('isRateLimitError', () => {
    it('should identify RateLimitError instances', () => {
      const rateLimitError = new RateLimitError('Test');
      const authError = new AuthenticationError('Test');
      
      expect(isRateLimitError(rateLimitError)).toBe(true);
      expect(isRateLimitError(authError)).toBe(false);
    });
  });

  describe('isNetworkError', () => {
    it('should identify NetworkError instances', () => {
      const networkError = new NetworkError('Test');
      const authError = new AuthenticationError('Test');
      
      expect(isNetworkError(networkError)).toBe(true);
      expect(isNetworkError(authError)).toBe(false);
    });
  });

  describe('isServerError', () => {
    it('should identify ServerError instances', () => {
      const serverError = new ServerError('Test');
      const authError = new AuthenticationError('Test');
      
      expect(isServerError(serverError)).toBe(true);
      expect(isServerError(authError)).toBe(false);
    });
  });
});

describe('ErrorHandler', () => {
  let mockLogger: {
    error: jest.Mock;
    warn: jest.Mock;
    info: jest.Mock;
  };

  beforeEach(() => {
    mockLogger = {
      error: jest.fn(),
      warn: jest.fn(),
      info: jest.fn()
    };
  });

  it('should create error handler with logger', () => {
    const handler = new ErrorHandler(mockLogger);
    expect(handler).toBeInstanceOf(ErrorHandler);
  });

  it('should handle errors and log appropriately', () => {
    const handler = new ErrorHandler(mockLogger);
    const error = new AuthenticationError('Auth failed');
    
    handler.handleError(error);
    
    expect(mockLogger.error).toHaveBeenCalledWith('Authentication error:', error);
  });

  it('should categorize errors correctly', () => {
    const handler = new ErrorHandler(mockLogger);
    
    // Test different error types get appropriate log levels
    const authError = new AuthenticationError('Auth failed');
    const validationError = new ValidationError('Validation failed');
    const serverError = new ServerError('Server failed');
    
    handler.handleError(authError);
    handler.handleError(validationError);
    handler.handleError(serverError);
    
    expect(mockLogger.error).toHaveBeenCalledTimes(3);
  });

  it('should handle non-Plinto errors', () => {
    const handler = new ErrorHandler(mockLogger);
    const error = new Error('Regular error');
    
    handler.handleError(error);
    
    expect(mockLogger.error).toHaveBeenCalledWith('Unknown error:', error);
  });
});