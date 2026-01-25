/// Exception types for the Janua Flutter SDK.

/// Base exception for all Janua errors.
class JanuaException implements Exception {
  /// The error message.
  final String message;

  /// The error code.
  final String code;

  /// Additional error details.
  final Map<String, dynamic>? details;

  /// The HTTP status code, if applicable.
  final int? statusCode;

  const JanuaException({
    required this.message,
    required this.code,
    this.details,
    this.statusCode,
  });

  @override
  String toString() => 'JanuaException($code): $message';

  /// Creates an exception from an API error response.
  factory JanuaException.fromJson(Map<String, dynamic> json, {int? statusCode}) {
    return JanuaException(
      message: json['message'] as String? ?? 'Unknown error',
      code: json['code'] as String? ?? 'UNKNOWN_ERROR',
      details: json['details'] as Map<String, dynamic>?,
      statusCode: statusCode,
    );
  }
}

/// Exception thrown when authentication fails.
class AuthenticationException extends JanuaException {
  const AuthenticationException({
    required super.message,
    super.code = 'AUTHENTICATION_ERROR',
    super.details,
    super.statusCode,
  });
}

/// Exception thrown when authorization fails.
class AuthorizationException extends JanuaException {
  const AuthorizationException({
    required super.message,
    super.code = 'AUTHORIZATION_ERROR',
    super.details,
    super.statusCode,
  });
}

/// Exception thrown when validation fails.
class ValidationException extends JanuaException {
  const ValidationException({
    required super.message,
    super.code = 'VALIDATION_ERROR',
    super.details,
    super.statusCode,
  });
}

/// Exception thrown when a resource is not found.
class NotFoundException extends JanuaException {
  const NotFoundException({
    required super.message,
    super.code = 'NOT_FOUND',
    super.details,
    super.statusCode,
  });
}

/// Exception thrown when rate limited.
class RateLimitException extends JanuaException {
  /// When the rate limit resets.
  final DateTime? retryAfter;

  const RateLimitException({
    required super.message,
    super.code = 'RATE_LIMIT_EXCEEDED',
    super.details,
    super.statusCode,
    this.retryAfter,
  });
}

/// Exception thrown for network errors.
class NetworkException extends JanuaException {
  const NetworkException({
    required super.message,
    super.code = 'NETWORK_ERROR',
    super.details,
    super.statusCode,
  });
}

/// Exception thrown for configuration errors.
class ConfigurationException extends JanuaException {
  const ConfigurationException({
    required super.message,
    super.code = 'CONFIGURATION_ERROR',
    super.details,
    super.statusCode,
  });
}
