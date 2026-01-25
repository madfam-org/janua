/// Session model for the Janua Flutter SDK.

/// Represents a user session.
class Session {
  /// Unique identifier for the session.
  final String id;

  /// The user ID associated with this session.
  final String userId;

  /// Session token.
  final String? token;

  /// Session status.
  final String status;

  /// IP address of the client.
  final String? ipAddress;

  /// User agent string.
  final String? userAgent;

  /// Device information.
  final DeviceInfo? deviceInfo;

  /// Location information.
  final LocationInfo? location;

  /// When the session was created.
  final DateTime createdAt;

  /// When the session was last updated.
  final DateTime updatedAt;

  /// When the session expires.
  final DateTime expiresAt;

  /// When the user was last active.
  final DateTime lastActivityAt;

  const Session({
    required this.id,
    required this.userId,
    this.token,
    this.status = 'active',
    this.ipAddress,
    this.userAgent,
    this.deviceInfo,
    this.location,
    required this.createdAt,
    required this.updatedAt,
    required this.expiresAt,
    required this.lastActivityAt,
  });

  /// Whether the session has expired.
  bool get isExpired => DateTime.now().isAfter(expiresAt);

  /// Whether the session is active.
  bool get isActive => status == 'active' && !isExpired;

  /// Creates a Session from JSON.
  factory Session.fromJson(Map<String, dynamic> json) {
    return Session(
      id: json['id'] as String,
      userId: json['user_id'] as String,
      token: json['token'] as String?,
      status: json['status'] as String? ?? 'active',
      ipAddress: json['ip_address'] as String?,
      userAgent: json['user_agent'] as String?,
      deviceInfo: json['device_info'] != null
          ? DeviceInfo.fromJson(json['device_info'] as Map<String, dynamic>)
          : null,
      location: json['location'] != null
          ? LocationInfo.fromJson(json['location'] as Map<String, dynamic>)
          : null,
      createdAt: DateTime.parse(json['created_at'] as String),
      updatedAt: DateTime.parse(json['updated_at'] as String),
      expiresAt: DateTime.parse(json['expires_at'] as String),
      lastActivityAt: DateTime.parse(json['last_activity_at'] as String),
    );
  }

  /// Converts this Session to JSON.
  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'user_id': userId,
      'token': token,
      'status': status,
      'ip_address': ipAddress,
      'user_agent': userAgent,
      'device_info': deviceInfo?.toJson(),
      'location': location?.toJson(),
      'created_at': createdAt.toIso8601String(),
      'updated_at': updatedAt.toIso8601String(),
      'expires_at': expiresAt.toIso8601String(),
      'last_activity_at': lastActivityAt.toIso8601String(),
    };
  }

  @override
  String toString() => 'Session(id: $id, status: $status)';
}

/// Device information for a session.
class DeviceInfo {
  /// Device type (mobile, tablet, desktop).
  final String? type;

  /// Browser name.
  final String? browser;

  /// Operating system.
  final String? os;

  /// Device name or identifier.
  final String? name;

  const DeviceInfo({
    this.type,
    this.browser,
    this.os,
    this.name,
  });

  factory DeviceInfo.fromJson(Map<String, dynamic> json) {
    return DeviceInfo(
      type: json['type'] as String?,
      browser: json['browser'] as String?,
      os: json['os'] as String?,
      name: json['name'] as String?,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'type': type,
      'browser': browser,
      'os': os,
      'name': name,
    };
  }

  @override
  String toString() => 'DeviceInfo(type: $type, os: $os)';
}

/// Location information for a session.
class LocationInfo {
  /// City name.
  final String? city;

  /// Region or state.
  final String? region;

  /// Country name.
  final String? country;

  /// Country code (ISO 3166-1 alpha-2).
  final String? countryCode;

  const LocationInfo({
    this.city,
    this.region,
    this.country,
    this.countryCode,
  });

  factory LocationInfo.fromJson(Map<String, dynamic> json) {
    return LocationInfo(
      city: json['city'] as String?,
      region: json['region'] as String?,
      country: json['country'] as String?,
      countryCode: json['country_code'] as String?,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'city': city,
      'region': region,
      'country': country,
      'country_code': countryCode,
    };
  }

  /// Formatted location string.
  String get formatted {
    final parts = <String>[];
    if (city != null) parts.add(city!);
    if (region != null) parts.add(region!);
    if (country != null) parts.add(country!);
    return parts.join(', ');
  }

  @override
  String toString() => 'LocationInfo($formatted)';
}
