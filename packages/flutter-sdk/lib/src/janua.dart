/// Main Janua client for the Flutter SDK.
import 'dart:async';
import 'config.dart';
import 'http_client.dart';
import 'storage/secure_storage.dart';
import 'services/auth_service.dart';
import 'services/users_service.dart';
import 'services/sessions_service.dart';
import 'services/organizations_service.dart';
import 'models/user.dart';
import 'models/tokens.dart';

/// Main entry point for the Janua Flutter SDK.
///
/// Example:
/// ```dart
/// final janua = Janua(
///   baseUrl: 'https://api.janua.dev',
///   tenantId: 'your-tenant-id',
///   clientId: 'your-client-id',
/// );
///
/// await janua.initialize();
///
/// // Sign in
/// final result = await janua.auth.signIn(
///   email: 'user@example.com',
///   password: 'password123',
/// );
///
/// // Access current user
/// final user = janua.currentUser;
///
/// // Check authentication
/// if (janua.isAuthenticated) {
///   // User is signed in
/// }
/// ```
class Janua {
  /// Configuration for the Janua client.
  final JanuaConfig config;

  late final JanuaHttpClient _http;
  late final JanuaSecureStorage _storage;

  /// Authentication service.
  late final AuthService auth;

  /// Users service.
  late final UsersService users;

  /// Sessions service.
  late final SessionsService sessions;

  /// Organizations service.
  late final OrganizationsService organizations;

  bool _initialized = false;

  /// Creates a new Janua client.
  ///
  /// [baseUrl] - The base URL for the Janua API.
  /// [tenantId] - Your tenant ID.
  /// [clientId] - Your client ID.
  /// [redirectUri] - OAuth redirect URI.
  /// [debug] - Enable debug logging.
  Janua({
    required String baseUrl,
    required String tenantId,
    required String clientId,
    String? redirectUri,
    bool debug = false,
    Map<String, String>? customHeaders,
  }) : config = JanuaConfig(
          baseUrl: baseUrl,
          tenantId: tenantId,
          clientId: clientId,
          redirectUri: redirectUri,
          debug: debug,
          customHeaders: customHeaders,
        ) {
    _initServices();
  }

  /// Creates a new Janua client from a config object.
  Janua.fromConfig(this.config) {
    _initServices();
  }

  void _initServices() {
    _storage = JanuaSecureStorage();
    _http = JanuaHttpClient(config: config);

    auth = AuthService(
      http: _http,
      config: config,
      storage: _storage,
    );

    users = UsersService(http: _http);
    sessions = SessionsService(http: _http);
    organizations = OrganizationsService(http: _http);
  }

  /// Initializes the Janua client and attempts to restore the session.
  ///
  /// Call this method when your app starts to restore any existing session.
  /// Returns `true` if a valid session was restored.
  Future<bool> initialize() async {
    if (_initialized) return isAuthenticated;

    _initialized = true;
    return await auth.restoreSession();
  }

  /// The currently authenticated user.
  User? get currentUser => auth.currentUser;

  /// Whether the user is authenticated.
  bool get isAuthenticated => auth.isAuthenticated;

  /// Stream of authentication state changes.
  ///
  /// Emits the current user when authenticated, or `null` when signed out.
  Stream<User?> get authStateChanges => auth.authStateChanges;

  /// Gets the current access token.
  ///
  /// Returns `null` if not authenticated.
  Future<String?> getAccessToken() => auth.getAccessToken();

  /// Gets the current ID token.
  ///
  /// Returns `null` if not authenticated or no ID token is available.
  Future<String?> getIdToken() => auth.getIdToken();

  /// Gets the current refresh token.
  ///
  /// Returns `null` if not authenticated.
  Future<String?> getRefreshToken() => auth.getRefreshToken();

  /// Signs out the current user.
  Future<void> signOut() => auth.signOut();

  /// Disposes of resources.
  ///
  /// Call this when the Janua client is no longer needed.
  void dispose() {
    auth.dispose();
    _http.close();
  }
}
