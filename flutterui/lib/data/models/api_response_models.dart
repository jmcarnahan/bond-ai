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
  final String message;

  const FileUploadResponseModel({
    required this.providerFileId,
    required this.fileName,
    required this.message,
  });

  factory FileUploadResponseModel.fromJson(Map<String, dynamic> json) {
    return FileUploadResponseModel(
      providerFileId: json['provider_file_id'] as String,
      fileName: json['file_name'] as String,
      message: json['message'] as String,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'provider_file_id': providerFileId,
      'file_name': fileName,
      'message': message,
    };
  }
}

// Optional: If you need a model for the FileDeleteResponse
// @immutable
// class FileDeleteResponseModel {
//   final String providerFileId;
//   final String status;
//   final String? message;

//   const FileDeleteResponseModel({
//     required this.providerFileId,
//     required this.status,
//     this.message,
//   });

//   factory FileDeleteResponseModel.fromJson(Map<String, dynamic> json) {
//     return FileDeleteResponseModel(
//       providerFileId: json['provider_file_id'] as String,
//       status: json['status'] as String,
//       message: json['message'] as String?,
//     );
//   }
// }
