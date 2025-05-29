import 'package:flutter/foundation.dart' show immutable;

@immutable
class AgentListItemModel {
  // Renamed from Agent
  final String id;
  final String name;
  final String? description;
  final String? model;
  final List<String>? tool_types; // Matches backend key
  final String? createdAtDisplay;
  final String? samplePrompt;
  final Map<String, dynamic>? metadata;

  const AgentListItemModel({
    required this.id,
    required this.name,
    this.description,
    this.model,
    this.tool_types,
    this.createdAtDisplay,
    this.samplePrompt,
    this.metadata,
  });

  factory AgentListItemModel.fromJson(Map<String, dynamic> json) {
    return AgentListItemModel(
      id: json['id'] as String,
      name: json['name'] as String,
      description: json['description'] as String?,
      model: json['model'] as String?,
      tool_types: json['tool_types'] != null
          ? List<String>.from(json['tool_types'] as List<dynamic>)
          : null,
      createdAtDisplay: json['created_at_display'] as String?,
      samplePrompt: json['sample_prompt'] as String?,
      metadata: json['metadata'] as Map<String, dynamic>?,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'name': name,
      'description': description,
      'model': model,
      'tool_types': tool_types,
      'created_at_display': createdAtDisplay,
      'sample_prompt': samplePrompt,
      'metadata': metadata,
    };
  }

  @override
  bool operator ==(Object other) {
    if (identical(this, other)) return true;

    return other is AgentListItemModel && // Adjusted type check
        other.id == id &&
        other.name == name &&
        other.description == description &&
        other.model == model &&
        other.tool_types == tool_types && // Consider list equality if needed
        other.createdAtDisplay == createdAtDisplay &&
        other.samplePrompt == samplePrompt &&
        other.metadata == metadata;
  }

  @override
  int get hashCode =>
      id.hashCode ^
      name.hashCode ^
      description.hashCode ^
      model.hashCode ^
      tool_types.hashCode ^
      createdAtDisplay.hashCode ^
      samplePrompt.hashCode ^
      metadata.hashCode;
}

// --- New Models for Agent Detail Screen ---

@immutable
class AgentFileDetailModel {
  final String fileId;
  final String fileName;

  const AgentFileDetailModel({required this.fileId, required this.fileName});

  factory AgentFileDetailModel.fromJson(Map<String, dynamic> json) {
    return AgentFileDetailModel(
      fileId: json['file_id'] as String,
      fileName: json['file_name'] as String,
    );
  }

  Map<String, dynamic> toJson() {
    return {'file_id': fileId, 'file_name': fileName};
  }
}

@immutable
class ToolResourceFilesListModel {
  final List<String> fileIds; // For request
  final List<AgentFileDetailModel>?
  files; // For response (optional, might only be in AgentDetailModel)

  const ToolResourceFilesListModel({required this.fileIds, this.files});

  factory ToolResourceFilesListModel.fromJson(Map<String, dynamic> json) {
    return ToolResourceFilesListModel(
      fileIds: List<String>.from(json['file_ids'] as List<dynamic>? ?? []),
      files:
          (json['files'] as List<dynamic>?)
              ?.map(
                (e) => AgentFileDetailModel.fromJson(e as Map<String, dynamic>),
              )
              .toList(),
    );
  }

  Map<String, dynamic> toJson() {
    final Map<String, dynamic> data = {'file_ids': fileIds};
    if (files != null) {
      data['files'] = files!.map((v) => v.toJson()).toList();
    }
    return data;
  }
}

@immutable
class AgentToolResourcesModel {
  final ToolResourceFilesListModel? codeInterpreter;
  final ToolResourceFilesListModel? fileSearch;

  const AgentToolResourcesModel({this.codeInterpreter, this.fileSearch});

  factory AgentToolResourcesModel.fromJson(Map<String, dynamic> json) {
    return AgentToolResourcesModel(
      codeInterpreter:
          json['code_interpreter'] != null
              ? ToolResourceFilesListModel.fromJson(
                json['code_interpreter'] as Map<String, dynamic>,
              )
              : null,
      fileSearch:
          json['file_search'] != null
              ? ToolResourceFilesListModel.fromJson(
                json['file_search'] as Map<String, dynamic>,
              )
              : null,
    );
  }

  Map<String, dynamic> toJson() {
    final Map<String, dynamic> data = {};
    if (codeInterpreter != null) {
      data['code_interpreter'] = codeInterpreter!.toJson();
    }
    if (fileSearch != null) {
      data['file_search'] = fileSearch!.toJson();
    }
    return data;
  }
}

@immutable
class AgentDetailModel {
  final String id;
  final String name;
  final String? description;
  final String? instructions;
  final String? model;
  final List<Map<String, dynamic>> tools; // e.g. [{"type": "code_interpreter"}]
  final AgentToolResourcesModel? toolResources;
  final Map<String, dynamic>? metadata;

  const AgentDetailModel({
    required this.id,
    required this.name,
    this.description,
    this.instructions,
    this.model,
    required this.tools,
    this.toolResources,
    this.metadata,
  });

  factory AgentDetailModel.fromJson(Map<String, dynamic> json) {
    return AgentDetailModel(
      id: json['id'] as String,
      name: json['name'] as String,
      description: json['description'] as String?,
      instructions: json['instructions'] as String?,
      model: json['model'] as String?,
      tools: List<Map<String, dynamic>>.from(
        json['tools'] as List<dynamic>? ?? [],
      ),
      toolResources:
          json['tool_resources'] != null
              ? AgentToolResourcesModel.fromJson(
                json['tool_resources'] as Map<String, dynamic>,
              )
              : null,
      metadata: json['metadata'] as Map<String, dynamic>?,
    );
  }

  Map<String, dynamic> toJson() {
    // For sending create/update requests
    return {
      'id': id, // Usually not sent for create, but useful for updates
      'name': name,
      if (description != null) 'description': description,
      if (instructions != null) 'instructions': instructions,
      if (model != null) 'model': model,
      'tools': tools,
      if (toolResources != null) 'tool_resources': toolResources!.toJson(),
      if (metadata != null) 'metadata': metadata,
    };
  }
}
