/// Models for external service connections (e.g., Atlassian, Google Drive).
class ConnectionStatus {
  final String name;
  final String displayName;
  final String? description;
  final bool connected;
  final bool valid; // false if token is expired
  final String authType;
  final String? iconUrl;
  final String? scopes;
  final String? expiresAt;
  final bool requiresAuthorization;

  ConnectionStatus({
    required this.name,
    required this.displayName,
    this.description,
    required this.connected,
    this.valid = true,
    required this.authType,
    this.iconUrl,
    this.scopes,
    this.expiresAt,
    this.requiresAuthorization = false,
  });

  factory ConnectionStatus.fromJson(Map<String, dynamic> json) {
    return ConnectionStatus(
      name: json['name'] as String,
      displayName: json['display_name'] as String,
      description: json['description'] as String?,
      connected: json['connected'] as bool? ?? false,
      valid: json['valid'] as bool? ?? true,
      authType: json['auth_type'] as String? ?? 'oauth2',
      iconUrl: json['icon_url'] as String?,
      scopes: json['scopes'] as String?,
      expiresAt: json['expires_at'] as String?,
      requiresAuthorization: json['requires_authorization'] as bool? ?? false,
    );
  }

  Map<String, dynamic> toJson() => {
    'name': name,
    'display_name': displayName,
    'description': description,
    'connected': connected,
    'valid': valid,
    'auth_type': authType,
    'icon_url': iconUrl,
    'scopes': scopes,
    'expires_at': expiresAt,
    'requires_authorization': requiresAuthorization,
  };

  /// Returns true if the connection needs attention (expired or not connected)
  bool get needsAttention => !connected || !valid;

  /// Human-readable status string
  String get statusText {
    if (!connected) return 'Not Connected';
    if (!valid) return 'Expired';
    return 'Connected';
  }
}

class ExpiredConnection {
  final String name;
  final String displayName;
  final String? expiresAt;

  ExpiredConnection({
    required this.name,
    required this.displayName,
    this.expiresAt,
  });

  factory ExpiredConnection.fromJson(Map<String, dynamic> json) {
    return ExpiredConnection(
      name: json['name'] as String,
      displayName: json['display_name'] as String,
      expiresAt: json['expires_at'] as String?,
    );
  }
}

class ConnectionsListResponse {
  final List<ConnectionStatus> connections;
  final List<ExpiredConnection> expired;

  ConnectionsListResponse({
    required this.connections,
    required this.expired,
  });

  factory ConnectionsListResponse.fromJson(Map<String, dynamic> json) {
    return ConnectionsListResponse(
      connections: (json['connections'] as List<dynamic>?)
          ?.map((e) => ConnectionStatus.fromJson(e as Map<String, dynamic>))
          .toList() ?? [],
      expired: (json['expired'] as List<dynamic>?)
          ?.map((e) => ExpiredConnection.fromJson(e as Map<String, dynamic>))
          .toList() ?? [],
    );
  }

  /// Check if any connections need attention
  bool get hasExpiredConnections => expired.isNotEmpty;
}

class AuthorizeResponse {
  final String authorizationUrl;
  final String connectionName;
  final String message;

  AuthorizeResponse({
    required this.authorizationUrl,
    required this.connectionName,
    required this.message,
  });

  factory AuthorizeResponse.fromJson(Map<String, dynamic> json) {
    return AuthorizeResponse(
      authorizationUrl: json['authorization_url'] as String,
      connectionName: json['connection_name'] as String,
      message: json['message'] as String,
    );
  }
}

class CheckExpiredResponse {
  final bool hasExpired;
  final List<ExpiredConnection> expiredConnections;

  CheckExpiredResponse({
    required this.hasExpired,
    required this.expiredConnections,
  });

  factory CheckExpiredResponse.fromJson(Map<String, dynamic> json) {
    return CheckExpiredResponse(
      hasExpired: json['has_expired'] as bool? ?? false,
      expiredConnections: (json['expired_connections'] as List<dynamic>?)
          ?.map((e) => ExpiredConnection.fromJson(e as Map<String, dynamic>))
          .toList() ?? [],
    );
  }
}

