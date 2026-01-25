/// Configuration for the Janua Flutter SDK.

/// OAuth provider types supported by Janua.
enum OAuthProvider {
  google,
  github,
  microsoft,
  apple,
  facebook,
  twitter,
  linkedin,
  discord,
  slack,
}

/// MFA methods supported by Janua.
enum MFAMethod {
  totp,
  sms,
  email,
}

/// Configuration options for the Janua client.
class JanuaConfig {
  /// The base URL for the Janua API.
  final String baseUrl;

  /// The tenant ID for multi-tenant deployments.
  final String tenantId;

  /// The client ID for OAuth and API access.
  final String clientId;

  /// The redirect URI for OAuth callbacks.
  final String? redirectUri;

  /// Request timeout in seconds.
  final int timeoutSeconds;

  /// Enable debug logging.
  final bool debug;

  /// Custom headers to include in all requests.
  final Map<String, String>? customHeaders;

  const JanuaConfig({
    required this.baseUrl,
    required this.tenantId,
    required this.clientId,
    this.redirectUri,
    this.timeoutSeconds = 30,
    this.debug = false,
    this.customHeaders,
  });

  /// Creates a copy of this config with the given values replaced.
  JanuaConfig copyWith({
    String? baseUrl,
    String? tenantId,
    String? clientId,
    String? redirectUri,
    int? timeoutSeconds,
    bool? debug,
    Map<String, String>? customHeaders,
  }) {
    return JanuaConfig(
      baseUrl: baseUrl ?? this.baseUrl,
      tenantId: tenantId ?? this.tenantId,
      clientId: clientId ?? this.clientId,
      redirectUri: redirectUri ?? this.redirectUri,
      timeoutSeconds: timeoutSeconds ?? this.timeoutSeconds,
      debug: debug ?? this.debug,
      customHeaders: customHeaders ?? this.customHeaders,
    );
  }
}
