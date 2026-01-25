/// Secure storage for the Janua Flutter SDK.
import 'dart:convert';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import '../models/tokens.dart';
import '../models/user.dart';

/// Handles secure storage of authentication tokens and user data.
class JanuaSecureStorage {
  static const _accessTokenKey = 'janua_access_token';
  static const _refreshTokenKey = 'janua_refresh_token';
  static const _idTokenKey = 'janua_id_token';
  static const _tokensKey = 'janua_tokens';
  static const _userKey = 'janua_user';

  final FlutterSecureStorage _storage;

  JanuaSecureStorage({FlutterSecureStorage? storage})
      : _storage = storage ??
            const FlutterSecureStorage(
              aOptions: AndroidOptions(
                encryptedSharedPreferences: true,
              ),
              iOptions: IOSOptions(
                accessibility: KeychainAccessibility.first_unlock_this_device,
              ),
            );

  // === Access Token ===

  /// Stores the access token.
  Future<void> setAccessToken(String token) async {
    await _storage.write(key: _accessTokenKey, value: token);
  }

  /// Retrieves the access token.
  Future<String?> getAccessToken() async {
    return await _storage.read(key: _accessTokenKey);
  }

  /// Deletes the access token.
  Future<void> deleteAccessToken() async {
    await _storage.delete(key: _accessTokenKey);
  }

  // === Refresh Token ===

  /// Stores the refresh token.
  Future<void> setRefreshToken(String token) async {
    await _storage.write(key: _refreshTokenKey, value: token);
  }

  /// Retrieves the refresh token.
  Future<String?> getRefreshToken() async {
    return await _storage.read(key: _refreshTokenKey);
  }

  /// Deletes the refresh token.
  Future<void> deleteRefreshToken() async {
    await _storage.delete(key: _refreshTokenKey);
  }

  // === ID Token ===

  /// Stores the ID token.
  Future<void> setIdToken(String token) async {
    await _storage.write(key: _idTokenKey, value: token);
  }

  /// Retrieves the ID token.
  Future<String?> getIdToken() async {
    return await _storage.read(key: _idTokenKey);
  }

  /// Deletes the ID token.
  Future<void> deleteIdToken() async {
    await _storage.delete(key: _idTokenKey);
  }

  // === Full Tokens Object ===

  /// Stores all authentication tokens.
  Future<void> setTokens(AuthTokens tokens) async {
    await _storage.write(key: _tokensKey, value: jsonEncode(tokens.toJson()));
    await setAccessToken(tokens.accessToken);
    if (tokens.refreshToken != null) {
      await setRefreshToken(tokens.refreshToken!);
    }
    if (tokens.idToken != null) {
      await setIdToken(tokens.idToken!);
    }
  }

  /// Retrieves all authentication tokens.
  Future<AuthTokens?> getTokens() async {
    final data = await _storage.read(key: _tokensKey);
    if (data == null) return null;
    try {
      return AuthTokens.fromJson(jsonDecode(data) as Map<String, dynamic>);
    } catch (_) {
      return null;
    }
  }

  /// Deletes all tokens.
  Future<void> deleteTokens() async {
    await Future.wait([
      _storage.delete(key: _tokensKey),
      _storage.delete(key: _accessTokenKey),
      _storage.delete(key: _refreshTokenKey),
      _storage.delete(key: _idTokenKey),
    ]);
  }

  // === User Data ===

  /// Stores the current user.
  Future<void> setUser(User user) async {
    await _storage.write(key: _userKey, value: jsonEncode(user.toJson()));
  }

  /// Retrieves the current user.
  Future<User?> getUser() async {
    final data = await _storage.read(key: _userKey);
    if (data == null) return null;
    try {
      return User.fromJson(jsonDecode(data) as Map<String, dynamic>);
    } catch (_) {
      return null;
    }
  }

  /// Deletes the current user.
  Future<void> deleteUser() async {
    await _storage.delete(key: _userKey);
  }

  // === Bulk Operations ===

  /// Clears all Janua-related data from storage.
  Future<void> clearAll() async {
    await Future.wait([
      deleteTokens(),
      deleteUser(),
    ]);
  }

  /// Checks if there are stored tokens.
  Future<bool> hasTokens() async {
    final accessToken = await getAccessToken();
    return accessToken != null;
  }

  /// Checks if the stored access token is valid (not expired).
  Future<bool> hasValidTokens() async {
    final tokens = await getTokens();
    if (tokens == null) return false;
    return !tokens.isExpired;
  }
}
