/// Token models for the Janua Flutter SDK.
import 'package:jwt_decoder/jwt_decoder.dart';

/// Represents authentication tokens returned by Janua.
class AuthTokens {
  /// The access token for API authentication.
  final String accessToken;

  /// The refresh token for obtaining new access tokens.
  final String? refreshToken;

  /// The ID token containing user claims.
  final String? idToken;

  /// The token type (usually "Bearer").
  final String tokenType;

  /// How long until the access token expires (in seconds).
  final int expiresIn;

  /// The OAuth scope, if applicable.
  final String? scope;

  const AuthTokens({
    required this.accessToken,
    this.refreshToken,
    this.idToken,
    this.tokenType = 'Bearer',
    required this.expiresIn,
    this.scope,
  });

  /// Whether the access token has expired.
  bool get isExpired {
    try {
      return JwtDecoder.isExpired(accessToken);
    } catch (_) {
      return true;
    }
  }

  /// The expiration date of the access token.
  DateTime? get expirationDate {
    try {
      return JwtDecoder.getExpirationDate(accessToken);
    } catch (_) {
      return null;
    }
  }

  /// The decoded claims from the access token.
  Map<String, dynamic>? get claims {
    try {
      return JwtDecoder.decode(accessToken);
    } catch (_) {
      return null;
    }
  }

  /// The decoded claims from the ID token.
  Map<String, dynamic>? get idTokenClaims {
    if (idToken == null) return null;
    try {
      return JwtDecoder.decode(idToken!);
    } catch (_) {
      return null;
    }
  }

  /// Creates AuthTokens from JSON.
  factory AuthTokens.fromJson(Map<String, dynamic> json) {
    return AuthTokens(
      accessToken: json['access_token'] as String,
      refreshToken: json['refresh_token'] as String?,
      idToken: json['id_token'] as String?,
      tokenType: json['token_type'] as String? ?? 'Bearer',
      expiresIn: json['expires_in'] as int? ?? 3600,
      scope: json['scope'] as String?,
    );
  }

  /// Converts this AuthTokens to JSON.
  Map<String, dynamic> toJson() {
    return {
      'access_token': accessToken,
      'refresh_token': refreshToken,
      'id_token': idToken,
      'token_type': tokenType,
      'expires_in': expiresIn,
      'scope': scope,
    };
  }

  @override
  String toString() => 'AuthTokens(tokenType: $tokenType, expiresIn: $expiresIn)';
}

/// MFA challenge response.
class MFAChallenge {
  /// The challenge ID.
  final String challengeId;

  /// Available MFA methods.
  final List<String> methods;

  const MFAChallenge({
    required this.challengeId,
    required this.methods,
  });

  factory MFAChallenge.fromJson(Map<String, dynamic> json) {
    return MFAChallenge(
      challengeId: json['challenge_id'] as String,
      methods: (json['methods'] as List<dynamic>).cast<String>(),
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'challenge_id': challengeId,
      'methods': methods,
    };
  }
}

/// MFA setup response.
class MFASetupResponse {
  /// The TOTP secret.
  final String secret;

  /// QR code image data (base64 or URL).
  final String qrCode;

  /// Backup codes for recovery.
  final List<String> backupCodes;

  const MFASetupResponse({
    required this.secret,
    required this.qrCode,
    required this.backupCodes,
  });

  factory MFASetupResponse.fromJson(Map<String, dynamic> json) {
    return MFASetupResponse(
      secret: json['secret'] as String,
      qrCode: json['qr_code'] as String,
      backupCodes: (json['backup_codes'] as List<dynamic>).cast<String>(),
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'secret': secret,
      'qr_code': qrCode,
      'backup_codes': backupCodes,
    };
  }
}
