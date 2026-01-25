/// Sessions service for the Janua Flutter SDK.
import '../http_client.dart';
import '../models/session.dart';

/// Handles session management operations.
class SessionsService {
  final JanuaHttpClient _http;

  SessionsService({required JanuaHttpClient http}) : _http = http;

  /// Gets the current session.
  Future<Session> getCurrentSession() async {
    final response = await _http.get('/sessions/current');
    return Session.fromJson(response);
  }

  /// Lists all active sessions for the current user.
  Future<List<Session>> listSessions() async {
    final response = await _http.get('/sessions');
    final sessions = response['sessions'] as List<dynamic>;
    return sessions
        .map((s) => Session.fromJson(s as Map<String, dynamic>))
        .toList();
  }

  /// Gets a specific session by ID.
  Future<Session> getSession(String sessionId) async {
    final response = await _http.get('/sessions/$sessionId');
    return Session.fromJson(response);
  }

  /// Revokes a specific session.
  Future<void> revokeSession(String sessionId) async {
    await _http.delete('/sessions/$sessionId');
  }

  /// Revokes all sessions except the current one.
  Future<void> revokeAllOtherSessions() async {
    await _http.delete('/sessions');
  }

  /// Revokes all sessions including the current one.
  Future<void> revokeAllSessions() async {
    await _http.delete('/sessions/all');
  }
}
