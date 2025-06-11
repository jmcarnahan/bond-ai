import 'package:flutter/foundation.dart' show immutable;

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
