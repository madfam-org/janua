/// Organizations service for the Janua Flutter SDK.
import '../http_client.dart';
import '../models/organization.dart';

/// Handles organization management operations.
class OrganizationsService {
  final JanuaHttpClient _http;

  OrganizationsService({required JanuaHttpClient http}) : _http = http;

  // === Organization CRUD ===

  /// Lists all organizations the user belongs to.
  Future<List<Organization>> listOrganizations() async {
    final response = await _http.get('/organizations');
    final orgs = response['organizations'] as List<dynamic>;
    return orgs
        .map((o) => Organization.fromJson(o as Map<String, dynamic>))
        .toList();
  }

  /// Creates a new organization.
  Future<Organization> createOrganization({
    required String name,
    String? slug,
    String? description,
    String? logoUrl,
    String? websiteUrl,
    Map<String, dynamic>? metadata,
  }) async {
    final response = await _http.post('/organizations', body: {
      'name': name,
      if (slug != null) 'slug': slug,
      if (description != null) 'description': description,
      if (logoUrl != null) 'logo_url': logoUrl,
      if (websiteUrl != null) 'website_url': websiteUrl,
      if (metadata != null) 'metadata': metadata,
    });

    return Organization.fromJson(response);
  }

  /// Gets an organization by ID.
  Future<Organization> getOrganization(String orgId) async {
    final response = await _http.get('/organizations/$orgId');
    return Organization.fromJson(response);
  }

  /// Updates an organization.
  Future<Organization> updateOrganization(
    String orgId, {
    String? name,
    String? description,
    String? logoUrl,
    String? websiteUrl,
    Map<String, dynamic>? metadata,
    Map<String, dynamic>? settings,
  }) async {
    final response = await _http.put('/organizations/$orgId', body: {
      if (name != null) 'name': name,
      if (description != null) 'description': description,
      if (logoUrl != null) 'logo_url': logoUrl,
      if (websiteUrl != null) 'website_url': websiteUrl,
      if (metadata != null) 'metadata': metadata,
      if (settings != null) 'settings': settings,
    });

    return Organization.fromJson(response);
  }

  /// Deletes an organization.
  Future<void> deleteOrganization(String orgId) async {
    await _http.delete('/organizations/$orgId');
  }

  // === Members ===

  /// Lists members of an organization.
  Future<List<OrganizationMember>> listMembers(String orgId) async {
    final response = await _http.get('/organizations/$orgId/members');
    final members = response['members'] as List<dynamic>;
    return members
        .map((m) => OrganizationMember.fromJson(m as Map<String, dynamic>))
        .toList();
  }

  /// Gets a member by user ID.
  Future<OrganizationMember> getMember(String orgId, String userId) async {
    final response = await _http.get('/organizations/$orgId/members/$userId');
    return OrganizationMember.fromJson(response);
  }

  /// Updates a member's role.
  Future<OrganizationMember> updateMemberRole(
    String orgId,
    String userId,
    OrganizationRole role,
  ) async {
    final response = await _http.put(
      '/organizations/$orgId/members/$userId',
      body: {'role': role.name},
    );

    return OrganizationMember.fromJson(response);
  }

  /// Removes a member from an organization.
  Future<void> removeMember(String orgId, String userId) async {
    await _http.delete('/organizations/$orgId/members/$userId');
  }

  // === Invitations ===

  /// Invites a user to an organization.
  Future<OrganizationInvitation> inviteMember({
    required String orgId,
    required String email,
    OrganizationRole role = OrganizationRole.member,
    bool sendEmail = true,
  }) async {
    final response = await _http.post('/organizations/$orgId/invites', body: {
      'email': email,
      'role': role.name,
      'send_email': sendEmail,
    });

    return OrganizationInvitation.fromJson(response);
  }

  /// Lists pending invitations for an organization.
  Future<List<OrganizationInvitation>> listInvitations(String orgId) async {
    final response = await _http.get('/organizations/$orgId/invites');
    final invites = response['invitations'] as List<dynamic>;
    return invites
        .map((i) => OrganizationInvitation.fromJson(i as Map<String, dynamic>))
        .toList();
  }

  /// Revokes an invitation.
  Future<void> revokeInvitation(String orgId, String invitationId) async {
    await _http.delete('/organizations/$orgId/invites/$invitationId');
  }

  /// Accepts an organization invitation.
  Future<OrganizationMember> acceptInvitation(String inviteToken) async {
    final response = await _http.post(
      '/organizations/invites/accept',
      body: {'token': inviteToken},
    );

    return OrganizationMember.fromJson(response);
  }

  /// Declines an organization invitation.
  Future<void> declineInvitation(String inviteToken) async {
    await _http.post('/organizations/invites/decline', body: {
      'token': inviteToken,
    });
  }

  // === User's Organization Memberships ===

  /// Lists the current user's organization memberships.
  Future<List<OrganizationMember>> listMyMemberships() async {
    final response = await _http.get('/users/me/organizations');
    final memberships = response['memberships'] as List<dynamic>;
    return memberships
        .map((m) => OrganizationMember.fromJson(m as Map<String, dynamic>))
        .toList();
  }

  /// Leaves an organization.
  Future<void> leaveOrganization(String orgId) async {
    await _http.delete('/organizations/$orgId/members/me');
  }
}
