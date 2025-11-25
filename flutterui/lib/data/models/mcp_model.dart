import 'package:flutter/foundation.dart' show immutable;
import 'package:flutter/material.dart' show Color, Colors;

@immutable
class McpToolModel {
  final String name;
  final String description;
  final Map<String, dynamic> inputSchema;

  const McpToolModel({
    required this.name,
    required this.description,
    required this.inputSchema,
  });

  factory McpToolModel.fromJson(Map<String, dynamic> json) {
    return McpToolModel(
      name: json['name'] as String,
      description: json['description'] as String,
      inputSchema: json['input_schema'] as Map<String, dynamic>? ?? {},
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'name': name,
      'description': description,
      'input_schema': inputSchema,
    };
  }

  @override
  bool operator ==(Object other) {
    if (identical(this, other)) return true;
    return other is McpToolModel &&
        other.name == name &&
        other.description == description;
  }

  @override
  int get hashCode => name.hashCode ^ description.hashCode;
}

@immutable
class McpResourceModel {
  final String uri;
  final String? name;
  final String? description;
  final String? mimeType;

  const McpResourceModel({
    required this.uri,
    this.name,
    this.description,
    this.mimeType,
  });

  factory McpResourceModel.fromJson(Map<String, dynamic> json) {
    return McpResourceModel(
      uri: json['uri'] as String,
      name: json['name'] as String?,
      description: json['description'] as String?,
      mimeType: json['mime_type'] as String?,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'uri': uri,
      'name': name,
      'description': description,
      'mime_type': mimeType,
    };
  }

  @override
  bool operator ==(Object other) {
    if (identical(this, other)) return true;
    return other is McpResourceModel && other.uri == uri && other.name == name;
  }

  @override
  int get hashCode => uri.hashCode ^ name.hashCode;
}

@immutable
class McpStatusModel {
  final int serversConfigured;
  final bool clientInitialized;

  const McpStatusModel({
    required this.serversConfigured,
    required this.clientInitialized,
  });

  factory McpStatusModel.fromJson(Map<String, dynamic> json) {
    return McpStatusModel(
      serversConfigured: json['servers_configured'] as int,
      clientInitialized: json['client_initialized'] as bool,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'servers_configured': serversConfigured,
      'client_initialized': clientInitialized,
    };
  }

  @override
  bool operator ==(Object other) {
    if (identical(this, other)) return true;
    return other is McpStatusModel &&
        other.serversConfigured == serversConfigured &&
        other.clientInitialized == clientInitialized;
  }

  @override
  int get hashCode => serversConfigured.hashCode ^ clientInitialized.hashCode;
}

// =============================================================================
// Grouped Response Models for Phase 2 UI
// =============================================================================

/// Connection status information for an MCP server
@immutable
class McpConnectionStatusInfo {
  final bool connected;
  final bool valid;
  final bool requiresAuthorization;
  final String? expiresAt;

  const McpConnectionStatusInfo({
    required this.connected,
    this.valid = true,
    this.requiresAuthorization = false,
    this.expiresAt,
  });

  /// Returns true if the connection is established but token is expired/invalid
  bool get needsAttention => connected && !valid;

  /// Returns true if no connection exists
  bool get needsConnection => !connected;

  /// Human-readable status text
  String get statusText {
    if (!connected) return 'Not Connected';
    if (!valid) return 'Expired';
    return 'Connected';
  }

  /// Status indicator color
  Color get statusColor {
    if (!connected) return Colors.grey;
    if (!valid) return Colors.red;
    return Colors.green;
  }

  factory McpConnectionStatusInfo.fromJson(Map<String, dynamic> json) {
    return McpConnectionStatusInfo(
      connected: json['connected'] as bool? ?? false,
      valid: json['valid'] as bool? ?? true,
      requiresAuthorization: json['requires_authorization'] as bool? ?? false,
      expiresAt: json['expires_at'] as String?,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'connected': connected,
      'valid': valid,
      'requires_authorization': requiresAuthorization,
      'expires_at': expiresAt,
    };
  }

  @override
  bool operator ==(Object other) {
    if (identical(this, other)) return true;
    return other is McpConnectionStatusInfo &&
        other.connected == connected &&
        other.valid == valid &&
        other.requiresAuthorization == requiresAuthorization &&
        other.expiresAt == expiresAt;
  }

  @override
  int get hashCode =>
      connected.hashCode ^
      valid.hashCode ^
      requiresAuthorization.hashCode ^
      expiresAt.hashCode;
}

/// MCP server metadata (without tools)
@immutable
class McpServerModel {
  final String serverName;
  final String displayName;
  final String? description;
  final String? iconUrl;
  final String authType;
  final McpConnectionStatusInfo connectionStatus;
  final int toolCount;

  const McpServerModel({
    required this.serverName,
    required this.displayName,
    this.description,
    this.iconUrl,
    this.authType = 'bond_jwt',
    required this.connectionStatus,
    required this.toolCount,
  });

  factory McpServerModel.fromJson(Map<String, dynamic> json) {
    return McpServerModel(
      serverName: json['server_name'] as String,
      displayName: json['display_name'] as String,
      description: json['description'] as String?,
      iconUrl: json['icon_url'] as String?,
      authType: json['auth_type'] as String? ?? 'bond_jwt',
      connectionStatus: McpConnectionStatusInfo.fromJson(
        json['connection_status'] as Map<String, dynamic>,
      ),
      toolCount: json['tool_count'] as int,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'server_name': serverName,
      'display_name': displayName,
      'description': description,
      'icon_url': iconUrl,
      'auth_type': authType,
      'connection_status': connectionStatus.toJson(),
      'tool_count': toolCount,
    };
  }

  @override
  bool operator ==(Object other) {
    if (identical(this, other)) return true;
    return other is McpServerModel &&
        other.serverName == serverName &&
        other.displayName == displayName;
  }

  @override
  int get hashCode => serverName.hashCode ^ displayName.hashCode;
}

/// MCP server with its tools
@immutable
class McpServerWithTools {
  final String serverName;
  final String displayName;
  final String? description;
  final String? iconUrl;
  final String authType;
  final McpConnectionStatusInfo connectionStatus;
  final List<McpToolModel> tools;
  final int toolCount;

  const McpServerWithTools({
    required this.serverName,
    required this.displayName,
    this.description,
    this.iconUrl,
    this.authType = 'bond_jwt',
    required this.connectionStatus,
    required this.tools,
    required this.toolCount,
  });

  factory McpServerWithTools.fromJson(Map<String, dynamic> json) {
    return McpServerWithTools(
      serverName: json['server_name'] as String,
      displayName: json['display_name'] as String,
      description: json['description'] as String?,
      iconUrl: json['icon_url'] as String?,
      authType: json['auth_type'] as String? ?? 'bond_jwt',
      connectionStatus: McpConnectionStatusInfo.fromJson(
        json['connection_status'] as Map<String, dynamic>,
      ),
      tools: (json['tools'] as List<dynamic>)
          .map((item) => McpToolModel.fromJson(item as Map<String, dynamic>))
          .toList(),
      toolCount: json['tool_count'] as int,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'server_name': serverName,
      'display_name': displayName,
      'description': description,
      'icon_url': iconUrl,
      'auth_type': authType,
      'connection_status': connectionStatus.toJson(),
      'tools': tools.map((t) => t.toJson()).toList(),
      'tool_count': toolCount,
    };
  }

  @override
  bool operator ==(Object other) {
    if (identical(this, other)) return true;
    return other is McpServerWithTools &&
        other.serverName == serverName &&
        other.displayName == displayName;
  }

  @override
  int get hashCode => serverName.hashCode ^ displayName.hashCode;
}

/// Grouped response containing all MCP servers with their tools
@immutable
class McpToolsGroupedResponse {
  final List<McpServerWithTools> servers;
  final int totalServers;
  final int totalTools;

  const McpToolsGroupedResponse({
    required this.servers,
    required this.totalServers,
    required this.totalTools,
  });

  /// Get all tools from all servers as a flat list
  List<McpToolModel> get allTools {
    return servers.expand((server) => server.tools).toList();
  }

  /// Check if any server needs attention (expired or not connected)
  bool get hasConnectionIssues {
    return servers.any(
      (server) =>
          server.connectionStatus.needsAttention ||
          server.connectionStatus.needsConnection,
    );
  }

  /// Get servers that need attention
  List<McpServerWithTools> get serversNeedingAttention {
    return servers
        .where(
          (server) =>
              server.connectionStatus.needsAttention ||
              server.connectionStatus.needsConnection,
        )
        .toList();
  }

  factory McpToolsGroupedResponse.fromJson(Map<String, dynamic> json) {
    return McpToolsGroupedResponse(
      servers: (json['servers'] as List<dynamic>)
          .map(
              (item) => McpServerWithTools.fromJson(item as Map<String, dynamic>))
          .toList(),
      totalServers: json['total_servers'] as int,
      totalTools: json['total_tools'] as int,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'servers': servers.map((s) => s.toJson()).toList(),
      'total_servers': totalServers,
      'total_tools': totalTools,
    };
  }

  @override
  bool operator ==(Object other) {
    if (identical(this, other)) return true;
    return other is McpToolsGroupedResponse &&
        other.totalServers == totalServers &&
        other.totalTools == totalTools;
  }

  @override
  int get hashCode => totalServers.hashCode ^ totalTools.hashCode;
}
