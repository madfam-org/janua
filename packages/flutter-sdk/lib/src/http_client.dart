/// HTTP client for the Janua Flutter SDK.
import 'dart:convert';
import 'dart:io';
import 'package:http/http.dart' as http;
import 'config.dart';
import 'exceptions/janua_exception.dart';

/// HTTP client wrapper for making API requests.
class JanuaHttpClient {
  final JanuaConfig config;
  final http.Client _client;

  String? _accessToken;

  JanuaHttpClient({
    required this.config,
    http.Client? client,
  }) : _client = client ?? http.Client();

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

      return _handleResponse(response);
    } on SocketException catch (e) {
      throw NetworkException(message: 'Network error: ${e.message}');
    } on http.ClientException catch (e) {
      throw NetworkException(message: 'HTTP client error: ${e.message}');
    } on FormatException catch (e) {
      throw JanuaException(
        message: 'Invalid response format: ${e.message}',
        code: 'INVALID_RESPONSE',
      );
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
