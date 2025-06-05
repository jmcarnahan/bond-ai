import 'package:flutter/foundation.dart' show immutable;

@immutable
class AgentResponseModel {
  final String agentId;
  final String name;

  const AgentResponseModel({required this.agentId, required this.name});

  factory AgentResponseModel.fromJson(Map<String, dynamic> json) {
    return AgentResponseModel(
      agentId: json['agent_id'] as String,
      name: json['name'] as String,
    );
  }

  Map<String, dynamic> toJson() {
    return {'agent_id': agentId, 'name': name};
  }
}

@immutable
class FileUploadResponseModel {
  final String providerFileId;
  final String fileName;
  final String mimeType;
  final String suggestedTool;
  final String message;

  const FileUploadResponseModel({
    required this.providerFileId,
    required this.fileName,
    required this.mimeType,
    required this.suggestedTool,
    required this.message,
  });

  factory FileUploadResponseModel.fromJson(Map<String, dynamic> json) {
    return FileUploadResponseModel(
      providerFileId: json['provider_file_id'] as String,
      fileName: json['file_name'] as String,
      mimeType: json['mime_type'] as String,
      suggestedTool: json['suggested_tool'] as String,
      message: json['message'] as String,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'provider_file_id': providerFileId,
      'file_name': fileName,
      'mime_type': mimeType,
      'suggested_tool': suggestedTool,
      'message': message,
    };
  }
}

@immutable
class FileDetailsResponseModel {
  final String fileId;
  final String filePath;
  final String fileHash;
  final String mimeType;
  final String ownerUserId;

  const FileDetailsResponseModel({
    required this.fileId,
    required this.filePath,
    required this.fileHash,
    required this.mimeType,
    required this.ownerUserId,
  });

  factory FileDetailsResponseModel.fromJson(Map<String, dynamic> json) {
    return FileDetailsResponseModel(
      fileId: json['file_id'] as String,
      filePath: json['file_path'] as String,
      fileHash: json['file_hash'] as String,
      mimeType: json['mime_type'] as String,
      ownerUserId: json['owner_user_id'] as String,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'file_id': fileId,
      'file_path': filePath,
      'file_hash': fileHash,
      'mime_type': mimeType,
      'owner_user_id': ownerUserId,
    };
  }

  String get fileName {
    // Extract filename from file path
    return filePath.split('/').last;
  }
}
