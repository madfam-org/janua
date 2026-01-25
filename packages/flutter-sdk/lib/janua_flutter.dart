/// Janua Flutter SDK
///
/// A complete authentication solution for Flutter apps with support for
/// email/password, OAuth, MFA, passkeys, and biometric authentication.
///
/// Example usage:
/// ```dart
/// import 'package:janua_flutter/janua_flutter.dart';
///
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
/// // Check authentication
/// if (janua.isAuthenticated) {
///   final user = janua.currentUser;
/// }
/// ```
library janua_flutter;

// Main client
export 'src/janua.dart';
export 'src/config.dart';

// Services
export 'src/services/auth_service.dart';
export 'src/services/users_service.dart';
export 'src/services/sessions_service.dart';
export 'src/services/organizations_service.dart';

// Models
export 'src/models/user.dart';
export 'src/models/session.dart';
export 'src/models/tokens.dart';
export 'src/models/auth_response.dart';
export 'src/models/organization.dart';

// Storage
export 'src/storage/secure_storage.dart';

// Exceptions
export 'src/exceptions/janua_exception.dart';
