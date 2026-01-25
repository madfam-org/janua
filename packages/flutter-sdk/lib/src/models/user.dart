/// User model for the Janua Flutter SDK.

/// Represents a Janua user.
class User {
  /// Unique identifier for the user.
  final String id;

  /// User's email address.
  final String email;

  /// Whether the email has been verified.
  final bool emailVerified;

  /// User's first name.
  final String? firstName;

  /// User's last name.
  final String? lastName;

  /// User's display name.
  final String? displayName;

  /// URL to the user's avatar image.
  final String? avatarUrl;

  /// User's phone number.
  final String? phoneNumber;

  /// Whether the phone has been verified.
  final bool phoneVerified;

  /// User's account status.
  final String status;

  /// Additional metadata associated with the user.
  final Map<String, dynamic> metadata;

  /// When the user account was created.
  final DateTime createdAt;

  /// When the user account was last updated.
  final DateTime updatedAt;

  /// When the user last signed in.
  final DateTime? lastSignInAt;

  /// Whether MFA is enabled.
  final bool mfaEnabled;

  /// Whether passkeys are enabled.
  final bool passkeysEnabled;

  const User({
    required this.id,
    required this.email,
    this.emailVerified = false,
    this.firstName,
    this.lastName,
    this.displayName,
    this.avatarUrl,
    this.phoneNumber,
    this.phoneVerified = false,
    this.status = 'active',
    this.metadata = const {},
    required this.createdAt,
    required this.updatedAt,
    this.lastSignInAt,
    this.mfaEnabled = false,
    this.passkeysEnabled = false,
  });

  /// The user's full name if available.
  String? get fullName {
    if (firstName != null && lastName != null) {
      return '$firstName $lastName';
    }
    return firstName ?? lastName ?? displayName;
  }

  /// Creates a User from JSON.
  factory User.fromJson(Map<String, dynamic> json) {
    return User(
      id: json['id'] as String,
      email: json['email'] as String,
      emailVerified: json['email_verified'] as bool? ?? false,
      firstName: json['first_name'] as String?,
      lastName: json['last_name'] as String?,
      displayName: json['display_name'] as String?,
      avatarUrl: json['avatar_url'] as String?,
      phoneNumber: json['phone_number'] as String?,
      phoneVerified: json['phone_verified'] as bool? ?? false,
      status: json['status'] as String? ?? 'active',
      metadata: (json['metadata'] as Map<String, dynamic>?) ?? {},
      createdAt: DateTime.parse(json['created_at'] as String),
      updatedAt: DateTime.parse(json['updated_at'] as String),
      lastSignInAt: json['last_sign_in_at'] != null
          ? DateTime.parse(json['last_sign_in_at'] as String)
          : null,
      mfaEnabled: json['mfa_enabled'] as bool? ?? false,
      passkeysEnabled: json['passkeys_enabled'] as bool? ?? false,
    );
  }

  /// Converts this User to JSON.
  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'email': email,
      'email_verified': emailVerified,
      'first_name': firstName,
      'last_name': lastName,
      'display_name': displayName,
      'avatar_url': avatarUrl,
      'phone_number': phoneNumber,
      'phone_verified': phoneVerified,
      'status': status,
      'metadata': metadata,
      'created_at': createdAt.toIso8601String(),
      'updated_at': updatedAt.toIso8601String(),
      'last_sign_in_at': lastSignInAt?.toIso8601String(),
      'mfa_enabled': mfaEnabled,
      'passkeys_enabled': passkeysEnabled,
    };
  }

  /// Creates a copy of this user with the given values replaced.
  User copyWith({
    String? id,
    String? email,
    bool? emailVerified,
    String? firstName,
    String? lastName,
    String? displayName,
    String? avatarUrl,
    String? phoneNumber,
    bool? phoneVerified,
    String? status,
    Map<String, dynamic>? metadata,
    DateTime? createdAt,
    DateTime? updatedAt,
    DateTime? lastSignInAt,
    bool? mfaEnabled,
    bool? passkeysEnabled,
  }) {
    return User(
      id: id ?? this.id,
      email: email ?? this.email,
      emailVerified: emailVerified ?? this.emailVerified,
      firstName: firstName ?? this.firstName,
      lastName: lastName ?? this.lastName,
      displayName: displayName ?? this.displayName,
      avatarUrl: avatarUrl ?? this.avatarUrl,
      phoneNumber: phoneNumber ?? this.phoneNumber,
      phoneVerified: phoneVerified ?? this.phoneVerified,
      status: status ?? this.status,
      metadata: metadata ?? this.metadata,
      createdAt: createdAt ?? this.createdAt,
      updatedAt: updatedAt ?? this.updatedAt,
      lastSignInAt: lastSignInAt ?? this.lastSignInAt,
      mfaEnabled: mfaEnabled ?? this.mfaEnabled,
      passkeysEnabled: passkeysEnabled ?? this.passkeysEnabled,
    );
  }

  @override
  String toString() => 'User(id: $id, email: $email)';

  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      other is User && runtimeType == other.runtimeType && id == other.id;

  @override
  int get hashCode => id.hashCode;
}
