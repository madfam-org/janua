/// Authentication service for the Janua Flutter SDK.
import 'dart:async';
import '../http_client.dart';
import '../config.dart';
import '../storage/secure_storage.dart';
import '../models/user.dart';
import '../models/tokens.dart';
import '../models/session.dart';
import '../models/auth_response.dart';
import '../exceptions/janua_exception.dart';

/// Handles all authentication operations.
class AuthService {
  final JanuaHttpClient _http;
  final JanuaConfig _config;
  final JanuaSecureStorage _storage;

  /// Stream controller for auth state changes.
  final _authStateController = StreamController<User?>.broadcast();

  /// Current user cache.
  User? _currentUser;

  AuthService({
    required JanuaHttpClient http,
    required JanuaConfig config,
    required JanuaSecureStorage storage,
  })  : _http = http,
        _config = config,
        _storage = storage;

  /// Stream of authentication state changes.
  Stream<User?> get authStateChanges => _authStateController.stream;

  /// The currently authenticated user.
  User? get currentUser => _currentUser;

  /// Whether the user is authenticated.
  bool get isAuthenticated => _currentUser != null;

  // === Email/Password Authentication ===

  /// Signs up a new user with email and password.
  Future<AuthResponse> signUp({
    required String email,
    required String password,
    String? firstName,
    String? lastName,
    Map<String, dynamic>? metadata,
  }) async {
    final response = await _http.post(
      '/auth/signup',
      body: {
        'email': email,
        'password': password,
        if (firstName != null) 'first_name': firstName,
        if (lastName != null) 'last_name': lastName,
        if (metadata != null) 'metadata': metadata,
      },
      authenticated: false,
    );

    final authResponse = AuthResponse.fromJson(response);
    await _handleAuthSuccess(authResponse);
    return authResponse;
  }

  /// Signs in a user with email and password.
  Future<AuthResponse> signIn({
    required String email,
    required String password,
    bool rememberMe = false,
  }) async {
    final response = await _http.post(
      '/auth/signin',
      body: {
        'email': email,
        'password': password,
        'remember_me': rememberMe,
      },
      authenticated: false,
    );

    final authResponse = AuthResponse.fromJson(response);
    await _handleAuthSuccess(authResponse);
    return authResponse;
  }

  /// Signs out the current user.
  Future<void> signOut() async {
    try {
      final refreshToken = await _storage.getRefreshToken();
      if (refreshToken != null) {
        await _http.post('/auth/signout', body: {'refresh_token': refreshToken});
      }
    } catch (_) {
      // Ignore errors during sign out
    } finally {
      await _clearAuth();
    }
  }

  /// Refreshes the authentication tokens.
  Future<AuthTokens> refreshToken() async {
    final refreshToken = await _storage.getRefreshToken();
    if (refreshToken == null) {
      throw const AuthenticationException(
        message: 'No refresh token available',
        code: 'NO_REFRESH_TOKEN',
      );
    }

    final response = await _http.post(
      '/auth/refresh',
      body: {'refresh_token': refreshToken},
      authenticated: false,
    );

    final tokens = AuthTokens.fromJson(response);
    await _storage.setTokens(tokens);
    _http.setAccessToken(tokens.accessToken);
    return tokens;
  }

  // === Password Management ===

  /// Requests a password reset email.
  Future<void> requestPasswordReset(String email) async {
    await _http.post(
      '/auth/password/reset',
      body: {'email': email},
      authenticated: false,
    );
  }

  /// Resets the password using a token.
  Future<void> resetPassword({
    required String token,
    required String newPassword,
  }) async {
    await _http.post(
      '/auth/password/confirm',
      body: {
        'token': token,
        'password': newPassword,
      },
      authenticated: false,
    );
  }

  /// Changes the current user's password.
  Future<void> changePassword({
    required String currentPassword,
    required String newPassword,
  }) async {
    await _http.post('/auth/password/change', body: {
      'current_password': currentPassword,
      'new_password': newPassword,
    });
  }

  // === Email Verification ===

  /// Requests email verification.
  Future<void> requestEmailVerification() async {
    await _http.post('/auth/email/verify');
  }

  /// Verifies an email using a token.
  Future<User> verifyEmail(String token) async {
    final response = await _http.post(
      '/auth/email/confirm',
      body: {'token': token},
      authenticated: false,
    );

    final user = User.fromJson(response['user'] as Map<String, dynamic>);
    if (_currentUser != null) {
      _currentUser = user;
      await _storage.setUser(user);
      _authStateController.add(user);
    }
    return user;
  }

  // === OAuth/Social Authentication ===

  /// Gets the OAuth authorization URL for a provider.
  Future<String> getOAuthUrl(OAuthProvider provider) async {
    final response = await _http.get(
      '/auth/oauth/${provider.name}/authorize',
      queryParameters: {
        if (_config.redirectUri != null) 'redirect_uri': _config.redirectUri!,
        'client_id': _config.clientId,
      },
      authenticated: false,
    );

    return response['authorization_url'] as String;
  }

  /// Handles the OAuth callback.
  Future<AuthResponse> handleOAuthCallback({
    required String code,
    String? state,
  }) async {
    final response = await _http.post(
      '/auth/oauth/callback',
      body: {
        'code': code,
        if (state != null) 'state': state,
        if (_config.redirectUri != null) 'redirect_uri': _config.redirectUri,
      },
      authenticated: false,
    );

    final authResponse = AuthResponse.fromJson(response);
    await _handleAuthSuccess(authResponse);
    return authResponse;
  }

  // === MFA ===

  /// Enables MFA for the current user.
  Future<MFASetupResponse> enableMFA({MFAMethod method = MFAMethod.totp}) async {
    final response = await _http.post('/auth/mfa/enable', body: {
      'method': method.name,
    });

    return MFASetupResponse.fromJson(response);
  }

  /// Verifies an MFA code.
  Future<AuthResponse> verifyMFA({
    required String code,
    required String challengeId,
  }) async {
    final response = await _http.post(
      '/auth/mfa/verify',
      body: {
        'code': code,
        'challenge_id': challengeId,
      },
      authenticated: false,
    );

    final authResponse = AuthResponse.fromJson(response);
    await _handleAuthSuccess(authResponse);
    return authResponse;
  }

  /// Disables MFA for the current user.
  Future<void> disableMFA(String password) async {
    await _http.post('/auth/mfa/disable', body: {'password': password});
  }

  // === Session Restoration ===

  /// Attempts to restore the session from storage.
  Future<bool> restoreSession() async {
    try {
      final tokens = await _storage.getTokens();
      if (tokens == null) return false;

      if (tokens.isExpired) {
        // Try to refresh
        final refreshToken = tokens.refreshToken;
        if (refreshToken == null) {
          await _clearAuth();
          return false;
        }

        try {
          await this.refreshToken();
        } catch (_) {
          await _clearAuth();
          return false;
        }
      } else {
        _http.setAccessToken(tokens.accessToken);
      }

      // Fetch current user
      final user = await _storage.getUser() ?? await getCurrentUser();
      _currentUser = user;
      _authStateController.add(user);
      return true;
    } catch (_) {
      await _clearAuth();
      return false;
    }
  }

  /// Gets the current user from the API.
  Future<User> getCurrentUser() async {
    final response = await _http.get('/auth/me');
    final user = User.fromJson(response);
    _currentUser = user;
    await _storage.setUser(user);
    return user;
  }

  // === Token Access ===

  /// Gets the current access token.
  Future<String?> getAccessToken() async {
    return await _storage.getAccessToken();
  }

  /// Gets the current ID token.
  Future<String?> getIdToken() async {
    return await _storage.getIdToken();
  }

  /// Gets the current refresh token.
  Future<String?> getRefreshToken() async {
    return await _storage.getRefreshToken();
  }

  // === Internal Methods ===

  Future<void> _handleAuthSuccess(AuthResponse response) async {
    await _storage.setTokens(response.tokens);
    await _storage.setUser(response.user);
    _http.setAccessToken(response.tokens.accessToken);
    _currentUser = response.user;
    _authStateController.add(response.user);
  }

  Future<void> _clearAuth() async {
    await _storage.clearAll();
    _http.clearAccessToken();
    _currentUser = null;
    _authStateController.add(null);
  }

  /// Disposes of resources.
  void dispose() {
    _authStateController.close();
  }
}
