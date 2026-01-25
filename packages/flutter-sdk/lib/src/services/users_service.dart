/// Users service for the Janua Flutter SDK.
import '../http_client.dart';
import '../models/user.dart';

/// Handles user profile operations.
class UsersService {
  final JanuaHttpClient _http;

  UsersService({required JanuaHttpClient http}) : _http = http;

  /// Gets the current user's profile.
  Future<User> getCurrentUser() async {
    final response = await _http.get('/users/me');
    return User.fromJson(response);
  }

  /// Updates the current user's profile.
  Future<User> updateProfile({
    String? firstName,
    String? lastName,
    String? displayName,
    String? phoneNumber,
    Map<String, dynamic>? metadata,
  }) async {
    final response = await _http.put('/users/me', body: {
      if (firstName != null) 'first_name': firstName,
      if (lastName != null) 'last_name': lastName,
      if (displayName != null) 'display_name': displayName,
      if (phoneNumber != null) 'phone_number': phoneNumber,
      if (metadata != null) 'metadata': metadata,
    });

    return User.fromJson(response);
  }

  /// Updates the user's avatar URL.
  Future<User> updateAvatar(String avatarUrl) async {
    final response = await _http.put('/users/me', body: {
      'avatar_url': avatarUrl,
    });

    return User.fromJson(response);
  }

  /// Deletes the current user's account.
  Future<void> deleteAccount({required String password}) async {
    await _http.delete('/users/me', body: {'password': password});
  }

  /// Gets a user by ID (requires admin permissions).
  Future<User> getUser(String userId) async {
    final response = await _http.get('/users/$userId');
    return User.fromJson(response);
  }

  /// Lists users (requires admin permissions).
  Future<UsersListResponse> listUsers({
    int page = 1,
    int limit = 10,
    String? search,
    String? sortBy,
    String? sortOrder,
  }) async {
    final response = await _http.get(
      '/users',
      queryParameters: {
        'page': page.toString(),
        'limit': limit.toString(),
        if (search != null) 'search': search,
        if (sortBy != null) 'sort_by': sortBy,
        if (sortOrder != null) 'sort_order': sortOrder,
      },
    );

    return UsersListResponse.fromJson(response);
  }
}

/// Response from listing users.
class UsersListResponse {
  /// The list of users.
  final List<User> users;

  /// Total number of users.
  final int total;

  /// Current page.
  final int page;

  /// Items per page.
  final int limit;

  /// Total number of pages.
  final int pages;

  /// Whether there's a next page.
  final bool hasNext;

  /// Whether there's a previous page.
  final bool hasPrev;

  const UsersListResponse({
    required this.users,
    required this.total,
    required this.page,
    required this.limit,
    required this.pages,
    required this.hasNext,
    required this.hasPrev,
  });

  factory UsersListResponse.fromJson(Map<String, dynamic> json) {
    return UsersListResponse(
      users: (json['users'] as List<dynamic>)
          .map((u) => User.fromJson(u as Map<String, dynamic>))
          .toList(),
      total: json['total'] as int,
      page: json['page'] as int,
      limit: json['limit'] as int,
      pages: json['pages'] as int,
      hasNext: json['has_next'] as bool,
      hasPrev: json['has_prev'] as bool,
    );
  }
}
