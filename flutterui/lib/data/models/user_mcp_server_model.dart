import 'package:flutter/foundation.dart' show immutable;

/// OAuth config display (client_secret redacted)
@immutable
class OAuthConfigDisplay {
  final String clientId;
  final String authorizeUrl;
  final String tokenUrl;
  final String? scopes;
  final String redirectUri;
  final String? provider;

  const OAuthConfigDisplay({
    required this.clientId,
    required this.authorizeUrl,
    required this.tokenUrl,
    this.scopes,
    required this.redirectUri,
    this.provider,
  });

  factory OAuthConfigDisplay.fromJson(Map<String, dynamic> json) {
    return OAuthConfigDisplay(
      clientId: json['client_id'] as String,
      authorizeUrl: json['authorize_url'] as String,
      tokenUrl: json['token_url'] as String,
      scopes: json['scopes'] as String?,
      redirectUri: json['redirect_uri'] as String,
      provider: json['provider'] as String?,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'client_id': clientId,
      'authorize_url': authorizeUrl,
      'token_url': tokenUrl,
      'scopes': scopes,
      'redirect_uri': redirectUri,
      'provider': provider,
    };
  }
}

/// User-defined MCP server configuration
@immutable
class UserMcpServerModel {
  final String id;
  final String serverName;
  final String displayName;
  final String? description;
  final String url;
  final String transport;
  final String authType;
  final bool hasHeaders;
  final bool hasOauthConfig;
  final OAuthConfigDisplay? oauthConfig;
  final Map<String, dynamic>? extraConfig;
  final bool isActive;
  final String? createdAt;
  final String? updatedAt;

  const UserMcpServerModel({
    required this.id,
    required this.serverName,
    required this.displayName,
    this.description,
    required this.url,
    this.transport = 'streamable-http',
    this.authType = 'none',
    this.hasHeaders = false,
    this.hasOauthConfig = false,
    this.oauthConfig,
    this.extraConfig,
    this.isActive = true,
    this.createdAt,
    this.updatedAt,
  });

  factory UserMcpServerModel.fromJson(Map<String, dynamic> json) {
    return UserMcpServerModel(
      id: json['id'] as String,
      serverName: json['server_name'] as String,
      displayName: json['display_name'] as String,
      description: json['description'] as String?,
      url: json['url'] as String,
      transport: json['transport'] as String? ?? 'streamable-http',
      authType: json['auth_type'] as String? ?? 'none',
      hasHeaders: json['has_headers'] as bool? ?? false,
      hasOauthConfig: json['has_oauth_config'] as bool? ?? false,
      oauthConfig: json['oauth_config'] != null
          ? OAuthConfigDisplay.fromJson(json['oauth_config'] as Map<String, dynamic>)
          : null,
      extraConfig: json['extra_config'] as Map<String, dynamic>?,
      isActive: json['is_active'] as bool? ?? true,
      createdAt: json['created_at'] as String?,
      updatedAt: json['updated_at'] as String?,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'server_name': serverName,
      'display_name': displayName,
      'description': description,
      'url': url,
      'transport': transport,
      'auth_type': authType,
      'has_headers': hasHeaders,
      'has_oauth_config': hasOauthConfig,
      'oauth_config': oauthConfig?.toJson(),
      'extra_config': extraConfig,
      'is_active': isActive,
      'created_at': createdAt,
      'updated_at': updatedAt,
    };
  }

  @override
  bool operator ==(Object other) {
    if (identical(this, other)) return true;
    return other is UserMcpServerModel && other.id == id;
  }

  @override
  int get hashCode => id.hashCode;
}

/// Response for listing user MCP servers
@immutable
class UserMcpServerListResponse {
  final List<UserMcpServerModel> servers;
  final int total;

  const UserMcpServerListResponse({
    required this.servers,
    required this.total,
  });

  factory UserMcpServerListResponse.fromJson(Map<String, dynamic> json) {
    return UserMcpServerListResponse(
      servers: (json['servers'] as List<dynamic>)
          .map((item) => UserMcpServerModel.fromJson(item as Map<String, dynamic>))
          .toList(),
      total: json['total'] as int,
    );
  }
}

/// Response for testing connectivity
@immutable
class TestConnectionResponse {
  final bool success;
  final int toolCount;
  final List<String> tools;
  final String? error;

  const TestConnectionResponse({
    required this.success,
    this.toolCount = 0,
    this.tools = const [],
    this.error,
  });

  factory TestConnectionResponse.fromJson(Map<String, dynamic> json) {
    return TestConnectionResponse(
      success: json['success'] as bool,
      toolCount: json['tool_count'] as int? ?? 0,
      tools: (json['tools'] as List<dynamic>?)
              ?.map((e) => e as String)
              .toList() ??
          [],
      error: json['error'] as String?,
    );
  }
}
