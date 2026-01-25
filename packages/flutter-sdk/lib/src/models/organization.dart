/// Organization models for the Janua Flutter SDK.
import 'user.dart';

/// Represents an organization.
class Organization {
  /// Unique identifier for the organization.
  final String id;

  /// Organization name.
  final String name;

  /// URL-friendly slug.
  final String slug;

  /// Organization description.
  final String? description;

  /// URL to the organization logo.
  final String? logoUrl;

  /// Organization website URL.
  final String? websiteUrl;

  /// Additional metadata.
  final Map<String, dynamic> metadata;

  /// Organization settings.
  final Map<String, dynamic> settings;

  /// When the organization was created.
  final DateTime createdAt;

  /// When the organization was last updated.
  final DateTime updatedAt;

  /// Number of members.
  final int memberCount;

  /// ID of the organization owner.
  final String ownerId;

  const Organization({
    required this.id,
    required this.name,
    required this.slug,
    this.description,
    this.logoUrl,
    this.websiteUrl,
    this.metadata = const {},
    this.settings = const {},
    required this.createdAt,
    required this.updatedAt,
    this.memberCount = 0,
    required this.ownerId,
  });

  factory Organization.fromJson(Map<String, dynamic> json) {
    return Organization(
      id: json['id'] as String,
      name: json['name'] as String,
      slug: json['slug'] as String,
      description: json['description'] as String?,
      logoUrl: json['logo_url'] as String?,
      websiteUrl: json['website_url'] as String?,
      metadata: (json['metadata'] as Map<String, dynamic>?) ?? {},
      settings: (json['settings'] as Map<String, dynamic>?) ?? {},
      createdAt: DateTime.parse(json['created_at'] as String),
      updatedAt: DateTime.parse(json['updated_at'] as String),
      memberCount: json['member_count'] as int? ?? 0,
      ownerId: json['owner_id'] as String,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'name': name,
      'slug': slug,
      'description': description,
      'logo_url': logoUrl,
      'website_url': websiteUrl,
      'metadata': metadata,
      'settings': settings,
      'created_at': createdAt.toIso8601String(),
      'updated_at': updatedAt.toIso8601String(),
      'member_count': memberCount,
      'owner_id': ownerId,
    };
  }

  @override
  String toString() => 'Organization(id: $id, name: $name)';
}

/// Organization member roles.
enum OrganizationRole {
  owner,
  admin,
  member,
  viewer,
}

/// Represents an organization member.
class OrganizationMember {
  /// Unique identifier.
  final String id;

  /// Organization ID.
  final String organizationId;

  /// User ID.
  final String userId;

  /// The member's user object.
  final User? user;

  /// Member role.
  final OrganizationRole role;

  /// Member permissions.
  final List<String> permissions;

  /// When the member joined.
  final DateTime joinedAt;

  /// When the membership was last updated.
  final DateTime updatedAt;

  const OrganizationMember({
    required this.id,
    required this.organizationId,
    required this.userId,
    this.user,
    required this.role,
    this.permissions = const [],
    required this.joinedAt,
    required this.updatedAt,
  });

  factory OrganizationMember.fromJson(Map<String, dynamic> json) {
    return OrganizationMember(
      id: json['id'] as String,
      organizationId: json['organization_id'] as String,
      userId: json['user_id'] as String,
      user: json['user'] != null
          ? User.fromJson(json['user'] as Map<String, dynamic>)
          : null,
      role: OrganizationRole.values.firstWhere(
        (r) => r.name == json['role'],
        orElse: () => OrganizationRole.member,
      ),
      permissions: (json['permissions'] as List<dynamic>?)?.cast<String>() ?? [],
      joinedAt: DateTime.parse(json['joined_at'] as String),
      updatedAt: DateTime.parse(json['updated_at'] as String),
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'organization_id': organizationId,
      'user_id': userId,
      'user': user?.toJson(),
      'role': role.name,
      'permissions': permissions,
      'joined_at': joinedAt.toIso8601String(),
      'updated_at': updatedAt.toIso8601String(),
    };
  }

  @override
  String toString() => 'OrganizationMember(userId: $userId, role: $role)';
}

/// Represents an organization invitation.
class OrganizationInvitation {
  /// Unique identifier.
  final String id;

  /// Organization ID.
  final String organizationId;

  /// Invited email address.
  final String email;

  /// Assigned role.
  final OrganizationRole role;

  /// ID of the user who sent the invitation.
  final String invitedById;

  /// Whether the invitation has been accepted.
  final bool accepted;

  /// When the invitation expires.
  final DateTime expiresAt;

  /// When the invitation was created.
  final DateTime createdAt;

  /// When the invitation was accepted.
  final DateTime? acceptedAt;

  const OrganizationInvitation({
    required this.id,
    required this.organizationId,
    required this.email,
    required this.role,
    required this.invitedById,
    this.accepted = false,
    required this.expiresAt,
    required this.createdAt,
    this.acceptedAt,
  });

  /// Whether the invitation has expired.
  bool get isExpired => DateTime.now().isAfter(expiresAt);

  factory OrganizationInvitation.fromJson(Map<String, dynamic> json) {
    return OrganizationInvitation(
      id: json['id'] as String,
      organizationId: json['organization_id'] as String,
      email: json['email'] as String,
      role: OrganizationRole.values.firstWhere(
        (r) => r.name == json['role'],
        orElse: () => OrganizationRole.member,
      ),
      invitedById: json['invited_by_id'] as String,
      accepted: json['accepted'] as bool? ?? false,
      expiresAt: DateTime.parse(json['expires_at'] as String),
      createdAt: DateTime.parse(json['created_at'] as String),
      acceptedAt: json['accepted_at'] != null
          ? DateTime.parse(json['accepted_at'] as String)
          : null,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'organization_id': organizationId,
      'email': email,
      'role': role.name,
      'invited_by_id': invitedById,
      'accepted': accepted,
      'expires_at': expiresAt.toIso8601String(),
      'created_at': createdAt.toIso8601String(),
      'accepted_at': acceptedAt?.toIso8601String(),
    };
  }

  @override
  String toString() => 'OrganizationInvitation(email: $email, role: $role)';
}
