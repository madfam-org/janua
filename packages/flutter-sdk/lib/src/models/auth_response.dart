/// Authentication response models for the Janua Flutter SDK.
import 'user.dart';
import 'session.dart';
import 'tokens.dart';

/// Response from authentication operations (sign in, sign up, OAuth).
class AuthResponse {
  /// The authenticated user.
  final User user;

  /// The user's session.
  final Session? session;

  /// Authentication tokens.
  final AuthTokens tokens;

  /// MFA challenge if MFA is required.
  final MFAChallenge? mfaChallenge;

  const AuthResponse({
    required this.user,
    this.session,
    required this.tokens,
    this.mfaChallenge,
  });

  /// Whether MFA verification is required.
  bool get requiresMfa => mfaChallenge != null;

  factory AuthResponse.fromJson(Map<String, dynamic> json) {
    return AuthResponse(
      user: User.fromJson(json['user'] as Map<String, dynamic>),
      session: json['session'] != null
          ? Session.fromJson(json['session'] as Map<String, dynamic>)
          : null,
      tokens: AuthTokens.fromJson(json['tokens'] as Map<String, dynamic>),
      mfaChallenge: json['mfa'] != null
          ? MFAChallenge.fromJson(json['mfa'] as Map<String, dynamic>)
          : null,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'user': user.toJson(),
      'session': session?.toJson(),
      'tokens': tokens.toJson(),
      'mfa': mfaChallenge?.toJson(),
    };
  }

  @override
  String toString() =>
      'AuthResponse(user: ${user.email}, requiresMfa: $requiresMfa)';
}

/// Response from token refresh operation.
class TokenRefreshResponse {
  /// New authentication tokens.
  final AuthTokens tokens;

  const TokenRefreshResponse({required this.tokens});

  factory TokenRefreshResponse.fromJson(Map<String, dynamic> json) {
    return TokenRefreshResponse(
      tokens: AuthTokens.fromJson(json),
    );
  }

  Map<String, dynamic> toJson() => tokens.toJson();
}

/// Response from password reset request.
class PasswordResetResponse {
  /// Whether the request was successful.
  final bool success;

  /// Message to display to the user.
  final String message;

  const PasswordResetResponse({
    required this.success,
    required this.message,
  });

  factory PasswordResetResponse.fromJson(Map<String, dynamic> json) {
    return PasswordResetResponse(
      success: json['success'] as bool? ?? true,
      message: json['message'] as String? ?? 'Password reset email sent',
    );
  }
}

/// Response from email verification.
class EmailVerificationResponse {
  /// Whether the verification was successful.
  final bool verified;

  /// The verified user.
  final User? user;

  const EmailVerificationResponse({
    required this.verified,
    this.user,
  });

  factory EmailVerificationResponse.fromJson(Map<String, dynamic> json) {
    return EmailVerificationResponse(
      verified: json['verified'] as bool? ?? true,
      user: json['user'] != null
          ? User.fromJson(json['user'] as Map<String, dynamic>)
          : null,
    );
  }
}
