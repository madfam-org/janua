/// HTTP client for the Janua Flutter SDK.
import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'dart:math';
import 'package:http/http.dart' as http;
import 'config.dart';
import 'exceptions/janua_exception.dart';

/// Configuration for retry behavior.
class RetryConfig {
  /// Maximum number of retry attempts (including initial request).
  final int maxAttempts;

  /// Initial delay between retries in milliseconds.
  final int baseDelayMs;

  /// Maximum delay between retries in milliseconds.
  final int maxDelayMs;

  /// Base for exponential backoff (default: 2.0).
  final double exponentialBase;

  /// Whether to add random jitter to delay (prevents thundering herd).
  final bool jitter;

  /// HTTP status codes that should trigger a retry.
  final Set<int> retryOnStatusCodes;

  /// Callback called before each retry.
  final void Function(int attempt, Exception error, Duration delay)? onRetry;

  const RetryConfig({
    this.maxAttempts = 3,
    this.baseDelayMs = 1000,
    this.maxDelayMs = 60000,
    this.exponentialBase = 2.0,
    this.jitter = true,
    this.retryOnStatusCodes = const {429, 500, 502, 503, 504},
    this.onRetry,
  });

  /// Calculate delay before retry using exponential backoff with jitter.
  Duration calculateDelay(int attempt, {Duration? retryAfter}) {
    // Use retry-after header if provided (for rate limits)
    if (retryAfter != null) {
      return retryAfter;
    }

    // Calculate exponential backoff
    double delayMs = baseDelayMs * pow(exponentialBase, attempt).toDouble();

    // Apply max delay cap
    delayMs = min(delayMs, maxDelayMs.toDouble());

    // Apply jitter if enabled (±25%)
    if (jitter) {
      final random = Random();
      final jitterRange = delayMs * 0.25;
      delayMs = delayMs + (random.nextDouble() * 2 - 1) * jitterRange;
    }

    return Duration(milliseconds: max(0, delayMs.toInt()));
  }

  /// Determine if an error should trigger a retry.
  bool shouldRetry(Exception error, int attempt) {
    if (attempt >= maxAttempts - 1) {
      return false;
    }

    // Always retry on network errors
    if (error is NetworkException || error is SocketException) {
      return true;
    }

    // Retry on rate limit
    if (error is RateLimitException) {
      return true;
    }

    // Check if it's a server error with retryable status
    if (error is JanuaException && error.statusCode != null) {
      return retryOnStatusCodes.contains(error.statusCode);
    }

    return false;
  }

  /// Creates a copy with modified values.
  RetryConfig copyWith({
    int? maxAttempts,
    int? baseDelayMs,
    int? maxDelayMs,
    double? exponentialBase,
    bool? jitter,
    Set<int>? retryOnStatusCodes,
    void Function(int, Exception, Duration)? onRetry,
  }) {
    return RetryConfig(
      maxAttempts: maxAttempts ?? this.maxAttempts,
      baseDelayMs: baseDelayMs ?? this.baseDelayMs,
      maxDelayMs: maxDelayMs ?? this.maxDelayMs,
      exponentialBase: exponentialBase ?? this.exponentialBase,
      jitter: jitter ?? this.jitter,
      retryOnStatusCodes: retryOnStatusCodes ?? this.retryOnStatusCodes,
      onRetry: onRetry ?? this.onRetry,
    );
  }
}

/// Default retry configuration.
const defaultRetryConfig = RetryConfig();

/// User-friendly error messages for common error codes.
const Map<String, String> userMessages = {
  'AUTHENTICATION_ERROR': 'Invalid email or password. Please try again.',
  'TOKEN_ERROR': 'Your session is invalid. Please sign in again.',
  'EMAIL_NOT_VERIFIED': 'Please verify your email address to continue.',
  'MFA_REQUIRED': 'Please complete two-factor authentication.',
  'PASSWORD_EXPIRED': 'Your password has expired. Please reset it.',
  'ACCOUNT_LOCKED': 'Your account is temporarily locked. Please try again later.',
  'SESSION_EXPIRED': 'Your session has expired. Please sign in again.',
  'AUTHORIZATION_ERROR': "You don't have permission to perform this action.",
  'INSUFFICIENT_PERMISSIONS': 'You need additional permissions for this action.',
  'VALIDATION_ERROR': 'Please check your input and try again.',
  'NOT_FOUND': 'The requested resource was not found.',
  'CONFLICT_ERROR': 'This action conflicts with existing data.',
  'RATE_LIMIT_EXCEEDED': 'Too many requests. Please wait a moment and try again.',
  'INTERNAL_ERROR': 'An unexpected error occurred. Please try again later.',
  'NETWORK_ERROR': 'Unable to connect. Please check your internet connection.',
};

/// Get a user-friendly error message for an exception.
String getUserMessage(JanuaException error) {
  return userMessages[error.code] ?? error.message;
}

/// HTTP client wrapper for making API requests.
class JanuaHttpClient {
  final JanuaConfig config;
  final http.Client _client;
  final RetryConfig retryConfig;

  String? _accessToken;

  JanuaHttpClient({
    required this.config,
    http.Client? client,
    RetryConfig? retryConfig,
  })  : _client = client ?? http.Client(),
        retryConfig = retryConfig ?? defaultRetryConfig;

  /// Sets the access token for authenticated requests.
  void setAccessToken(String? token) {
    _accessToken = token;
  }

  /// Clears the access token.
  void clearAccessToken() {
    _accessToken = null;
  }

  /// Makes a GET request.
  Future<Map<String, dynamic>> get(
    String path, {
    Map<String, String>? queryParameters,
    bool authenticated = true,
  }) async {
    return _request('GET', path,
        queryParameters: queryParameters, authenticated: authenticated);
  }

  /// Makes a POST request.
  Future<Map<String, dynamic>> post(
    String path, {
    Map<String, dynamic>? body,
    bool authenticated = true,
  }) async {
    return _request('POST', path, body: body, authenticated: authenticated);
  }

  /// Makes a PUT request.
  Future<Map<String, dynamic>> put(
    String path, {
    Map<String, dynamic>? body,
    bool authenticated = true,
  }) async {
    return _request('PUT', path, body: body, authenticated: authenticated);
  }

  /// Makes a PATCH request.
  Future<Map<String, dynamic>> patch(
    String path, {
    Map<String, dynamic>? body,
    bool authenticated = true,
  }) async {
    return _request('PATCH', path, body: body, authenticated: authenticated);
  }

  /// Makes a DELETE request.
  Future<Map<String, dynamic>> delete(
    String path, {
    Map<String, dynamic>? body,
    bool authenticated = true,
  }) async {
    return _request('DELETE', path, body: body, authenticated: authenticated);
  }

  Future<Map<String, dynamic>> _request(
    String method,
    String path, {
    Map<String, dynamic>? body,
    Map<String, String>? queryParameters,
    bool authenticated = true,
  }) async {
    final uri = _buildUri(path, queryParameters);
    final headers = _buildHeaders(authenticated: authenticated);

    if (config.debug) {
      _logRequest(method, uri, headers, body);
    }

    int attempt = 0;
    Exception? lastError;
    Duration? retryAfterDuration;

    while (attempt < retryConfig.maxAttempts) {
      try {
        http.Response response;
        final timeout = Duration(seconds: config.timeoutSeconds);

        switch (method) {
          case 'GET':
            response = await _client.get(uri, headers: headers).timeout(timeout);
            break;
          case 'POST':
            response = await _client
                .post(uri, headers: headers, body: body != null ? jsonEncode(body) : null)
                .timeout(timeout);
            break;
          case 'PUT':
            response = await _client
                .put(uri, headers: headers, body: body != null ? jsonEncode(body) : null)
                .timeout(timeout);
            break;
          case 'PATCH':
            response = await _client
                .patch(uri, headers: headers, body: body != null ? jsonEncode(body) : null)
                .timeout(timeout);
            break;
          case 'DELETE':
            response = await _client.delete(uri, headers: headers).timeout(timeout);
            break;
          default:
            throw ArgumentError('Unsupported HTTP method: $method');
        }

        if (config.debug) {
          _logResponse(response);
        }

        // Parse Retry-After header if present (for rate limiting)
        retryAfterDuration = _parseRetryAfter(response.headers);

        return _handleResponse(response);
      } on SocketException catch (e) {
        lastError = NetworkException(message: 'Network error: ${e.message}');
        if (!retryConfig.shouldRetry(lastError, attempt)) {
          throw lastError;
        }
      } on TimeoutException catch (_) {
        lastError = NetworkException(message: 'Request timeout');
        if (!retryConfig.shouldRetry(lastError, attempt)) {
          throw lastError;
        }
      } on http.ClientException catch (e) {
        lastError = NetworkException(message: 'HTTP client error: ${e.message}');
        if (!retryConfig.shouldRetry(lastError, attempt)) {
          throw lastError;
        }
      } on FormatException catch (e) {
        // Don't retry format exceptions
        throw JanuaException(
          message: 'Invalid response format: ${e.message}',
          code: 'INVALID_RESPONSE',
        );
      } on AuthenticationException {
        // Don't retry auth errors
        rethrow;
      } on AuthorizationException {
        // Don't retry authorization errors
        rethrow;
      } on ValidationException {
        // Don't retry validation errors
        rethrow;
      } on NotFoundException {
        // Don't retry not found errors
        rethrow;
      } on RateLimitException catch (e) {
        lastError = e;
        if (!retryConfig.shouldRetry(e, attempt)) {
          rethrow;
        }
        // Use retry-after from exception if available
        if (e.retryAfter != null) {
          retryAfterDuration = e.retryAfter!.difference(DateTime.now());
          if (retryAfterDuration.isNegative) {
            retryAfterDuration = null;
          }
        }
      } on JanuaException catch (e) {
        lastError = e;
        if (!retryConfig.shouldRetry(e, attempt)) {
          rethrow;
        }
      }

      // Calculate delay and wait before retry
      if (attempt < retryConfig.maxAttempts - 1) {
        final delay = retryConfig.calculateDelay(attempt, retryAfter: retryAfterDuration);

        if (config.debug) {
          // ignore: avoid_print
          print('[Janua] Retry attempt ${attempt + 1}/${retryConfig.maxAttempts} after ${delay.inMilliseconds}ms');
        }

        // Call on_retry callback if configured
        if (retryConfig.onRetry != null && lastError != null) {
          retryConfig.onRetry!(attempt, lastError, delay);
        }

        await Future.delayed(delay);
      }

      attempt++;
      retryAfterDuration = null; // Reset for next attempt
    }

    // If we get here, we've exhausted retries
    if (lastError != null) {
      throw lastError;
    }
    throw JanuaException(
      message: 'Failed to complete request after ${retryConfig.maxAttempts} attempts',
      code: 'MAX_RETRIES_EXCEEDED',
    );
  }

  /// Parses the Retry-After header from response headers.
  Duration? _parseRetryAfter(Map<String, String> headers) {
    final retryAfter = headers['retry-after'] ?? headers['Retry-After'];
    if (retryAfter == null) return null;

    // Try to parse as seconds (integer)
    final seconds = int.tryParse(retryAfter);
    if (seconds != null) {
      return Duration(seconds: seconds);
    }

    // Try to parse as HTTP-date
    try {
      final date = HttpDate.parse(retryAfter);
      final duration = date.difference(DateTime.now());
      return duration.isNegative ? null : duration;
    } catch (_) {
      return null;
    }
  }

  Uri _buildUri(String path, Map<String, String>? queryParameters) {
    final baseUri = Uri.parse(config.baseUrl);
    final fullPath = path.startsWith('/') ? '/api/v1$path' : '/api/v1/$path';

    return Uri(
      scheme: baseUri.scheme,
      host: baseUri.host,
      port: baseUri.port,
      path: fullPath,
      queryParameters: queryParameters?.isNotEmpty == true ? queryParameters : null,
    );
  }

  Map<String, String> _buildHeaders({bool authenticated = true}) {
    final headers = <String, String>{
      'Content-Type': 'application/json',
      'Accept': 'application/json',
      'X-Tenant-ID': config.tenantId,
      'X-Client-ID': config.clientId,
      'X-SDK': 'flutter',
      'X-SDK-Version': '1.0.0',
    };

    if (authenticated && _accessToken != null) {
      headers['Authorization'] = 'Bearer $_accessToken';
    }

    if (config.customHeaders != null) {
      headers.addAll(config.customHeaders!);
    }

    return headers;
  }

  Map<String, dynamic> _handleResponse(http.Response response) {
    final statusCode = response.statusCode;
    Map<String, dynamic> data;

    try {
      if (response.body.isEmpty) {
        data = {'success': true};
      } else {
        data = jsonDecode(response.body) as Map<String, dynamic>;
      }
    } catch (_) {
      data = {'message': response.body};
    }

    if (statusCode >= 200 && statusCode < 300) {
      return data;
    }

    // Handle errors
    final message = data['message'] as String? ?? 'Unknown error';
    final code = data['code'] as String? ?? 'UNKNOWN_ERROR';
    final details = data['details'] as Map<String, dynamic>?;

    switch (statusCode) {
      case 400:
        throw ValidationException(
          message: message,
          code: code,
          details: details,
          statusCode: statusCode,
        );
      case 401:
        throw AuthenticationException(
          message: message,
          code: code,
          details: details,
          statusCode: statusCode,
        );
      case 403:
        throw AuthorizationException(
          message: message,
          code: code,
          details: details,
          statusCode: statusCode,
        );
      case 404:
        throw NotFoundException(
          message: message,
          code: code,
          details: details,
          statusCode: statusCode,
        );
      case 429:
        throw RateLimitException(
          message: message,
          code: code,
          details: details,
          statusCode: statusCode,
        );
      default:
        throw JanuaException(
          message: message,
          code: code,
          details: details,
          statusCode: statusCode,
        );
    }
  }

  void _logRequest(
    String method,
    Uri uri,
    Map<String, String> headers,
    Map<String, dynamic>? body,
  ) {
    // ignore: avoid_print
    print('[Janua] $method $uri');
    if (body != null) {
      // ignore: avoid_print
      print('[Janua] Body: ${jsonEncode(body)}');
    }
  }

  void _logResponse(http.Response response) {
    // ignore: avoid_print
    print('[Janua] Response ${response.statusCode}: ${response.body}');
  }

  /// Closes the HTTP client.
  void close() {
    _client.close();
  }
}
